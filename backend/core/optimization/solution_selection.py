"""
Solution selection module.

This module contains all logic for selecting the best diet solution from the
optimization population:
- Solution ranking and scoring algorithms
- Practicality evaluation (forage percentage, ingredient diversity)
- Critical nutrient adequacy assessment (DMI, Energy, Protein)
- Constraint compliance scoring
- Multi-objective composite scoring with configurable weights
- Fallback logic for handling infeasible solutions
- Detailed adequacy calculation for all nutritional constraints
"""

import numpy as np
import pandas as pd
import re
from dataclasses import dataclass

# Import from config
from .config import Constraints, CONSTRAINT_TOLERANCE_RANGES

# Import from optimization_core
from .optimization_core import (
    rsm_decode_solution_to_q,
    rsm_diet_supply,
    rsm_detect_present_categories
)

# Import from constraints
from .constraints import (
    evaluate_constraint_adequacy,
    ca_constraint_name,
    CONSTRAINT_META
)

# ===================================================================
# SOLUTION SELECTION CONFIGURATION
# ===================================================================

SELECTION_CONFIG = {
        'objective_weights': {
            'critical_adequacy': 0.45,  # Critical nutrients (DMI, Energy, Protein) 
            'practicality': 0.20,       # Forage inclusion + diversity  
            'constraints': 0.25,        # Other constraint compliance 
            'cost': 0.10               # Cost efficiency 
        },
        'practicality_threshold': 0.3, 
        'forage_minimum_pct': 15.0      # Minimum forage inclusion required
    }

def _get_forage_percentage(solution, res, animal_requirements, f_nd, categories=None, cached_q=None):        
        #Calculate percentage of practical forage (moist forage) in solution using mask_moist_forage from detect_present_categories.
        #This excludes dry hay/straw and focuses on practical moist forages.
            
        try:
            # Use cached q if provided to avoid redundant calculations
            if cached_q is not None:
                q = cached_q
            else:
                decision_mode = getattr(getattr(res, "problem", None), "decision_mode", "kg")
                trg_dmi = float(animal_requirements["Trg_Dt_DMIn"])
                q = rsm_decode_solution_to_q(solution["x"], decision_mode, trg_dmi)[0]
            if len(q) == 0:
                return 0.0

            # Get categories from optimization result if available, otherwise calculate
            if categories is None:
                categories = rsm_detect_present_categories(f_nd)

            # Use mask_moist_forage for practical forage
            moist_forage_mask = categories.get("mask_moist_forage", None)
            if moist_forage_mask is None or len(moist_forage_mask) != len(q):
                # Fallback: treat all as non-forage if mask missing or wrong length
                return 0.0

            total_dm = np.sum(q)
            moist_forage_dm = np.sum(q[moist_forage_mask]) if np.any(moist_forage_mask) else 0.0
            moist_forage_percentage = (moist_forage_dm / total_dm * 100.0) if total_dm > 0 else 0.0
            return moist_forage_percentage
        except Exception as e:
            # Log the error for debugging but return conservative value
            print(f"WARNING: Forage percentage calculation failed: {e}")
            return 0.0  # Conservative fallback

def _calculate_practicality_score(solution, res, animal_requirements, f_nd, categories=None, cached_q=None):
        # Calculate how practical/realistic a solution is for actual feeding
        try:
            # Use cached q if provided to avoid redundant calculations
            if cached_q is not None:
                q = cached_q
            else:
                decision_mode = getattr(getattr(res, "problem", None), "decision_mode", "kg")
                trg_dmi = float(animal_requirements["Trg_Dt_DMIn"])
                q = rsm_decode_solution_to_q(solution["x"], decision_mode, trg_dmi)[0]
            
            # Forage inclusion scoring - use existing categories if available
            forage_pct = _get_forage_percentage(solution, res, animal_requirements, f_nd, categories, q)
            if forage_pct >= 45:
                forage_score = 1.0      # Excellent
            elif forage_pct >= 40:
                forage_score = 0.8      # Good
            elif forage_pct >= 25:
                forage_score = 0.5      # Marginal
            elif forage_pct >= 5:
                forage_score = 0.2      # Poor
            else:
                forage_score = 0.0      # Unrealistic (pure concentrate)
            
            # Ingredient diversity scoring (optimized for small producers)
            active_ingredients = np.sum(q > 0.001)  # Count significant ingredients
            # Target 3-6 ingredients for small producers (peak score at 4-5 ingredients)
            if active_ingredients <= 6:
                diversity_score = min(active_ingredients / 4.0, 1.0)  # Peak at 4+ ingredients
            else:
                # Penalty for too many ingredients (complexity for small producers)
                diversity_score = max(0.5, 1.0 - (active_ingredients - 6) * 0.1)
            
            # DOMINANCE 
            dominance_penalty = 1.0
            if len(q) > 0:
                max_ingredient_pct = (np.max(q) / np.sum(q)) * 100.0
                if max_ingredient_pct > 80.0:  # Hard penalty above 80%
                    dominance_penalty = 0.1  # Severe penalty
                elif max_ingredient_pct > 60.0:  # Soft penalty above 60%
                    dominance_penalty = 0.7  # Moderate penalty
            
            anchoring_bonus = 1.0
            if categories is not None:
                user_forage_count = np.sum((q > 0.01) & categories.get("mask_moist_forage", np.zeros_like(q, dtype=bool)))
                user_conc_count = np.sum((q > 0.01) & categories.get("mask_conc_all", np.zeros_like(q, dtype=bool)))
                if user_forage_count >= 1 and user_conc_count >= 1:
                    anchoring_bonus = 1.05  # 5% bonus for including both
            
            
            # Overall practicality score with dominance penalty and anchoring bonus
            # Redistributed: 60% forage + 40% diversity = 100%
            base_score = 0.6 * forage_score + 0.4 * diversity_score
            overall_score = base_score * dominance_penalty * anchoring_bonus
            
            return {
                'forage': forage_score,
                'diversity': diversity_score,
                'overall': overall_score,
                'forage_pct': forage_pct
            }
        except Exception:
            return {'forage': 0.5, 'diversity': 0.5, 'overall': 0.5, 'forage_pct': 25.0}

def _score_constraint_compliance(solution):
        """Score based on constraint compliance with graduated penalties"""
        try:
            # Use detailed constraint severities if available (preferred method)
            constraint_severities = solution.get("constraint_severities", {})
            if constraint_severities:
                # Score based on constraint severity distribution
                severity_scores = {"perfect": 1.0, "good": 0.8, "marginal": 0.5, "infeasible": 0.0}
                total_constraints = len(constraint_severities)
                if total_constraints > 0:
                    weighted_score = sum(severity_scores.get(sev, 0.0) for sev in constraint_severities.values())
                    compliance_score = weighted_score / total_constraints
                    return compliance_score
            
            # Fallback to CV-based scoring if constraint severities not available
            cv_value = solution.get("cv_total", 0.0)
            # Convert CV to compliance score (0 = heavily violated, 1 = perfect compliance)
            # Use exponential decay for penalty
            compliance_score = max(0.0, np.exp(-cv_value * 2.0))
            return compliance_score
        except Exception:
            return 0.5

def _extract_percentage_from_adequacy(adequacy_text):
        """Extract percentage value from adequacy result text"""
        try:
            import re
            match = re.search(r'(\d+\.?\d*)%', adequacy_text)
            return float(match.group(1)) if match else 0.0
        except:
            return 0.0

def _score_nutrient_by_tolerance(actual_pct, target_pct, nutrient_key, tolerance_ranges, is_energy_or_protein=False):
    """
    Score nutrient using CONSTRAINT_TOLERANCE_RANGES with specified scoring logic.
    
    Parameters:
    -----------
    actual_pct : float
        Actual percentage of nutrient supplied
    target_pct : float
        Target percentage (usually 100.0)
    nutrient_key : str
        Key for the nutrient ('dmi', 'energy', 'protein')
    tolerance_ranges : dict
        Dictionary of tolerance ranges by nutrient
    is_energy_or_protein : bool
        Whether scoring energy or protein (affects penalty logic)
    
    Returns:
    --------
    float : Score from 0.0 to 1.0
    """
    if nutrient_key not in tolerance_ranges:
        return 0.5  # Fallback
    
    config = tolerance_ranges[nutrient_key]
    deviation_pct = abs(actual_pct - target_pct)
    is_positive_deviation = actual_pct > target_pct
    is_negative_deviation = actual_pct < target_pct
    
    # Determine tolerance level
    if deviation_pct <= config["perfect"][1]:
        level = "perfect"
    elif deviation_pct <= config["good"][1]:
        level = "good"
    elif deviation_pct <= config["marginal"][1]:
        level = "marginal"
    else:
        level = "infeasible"
    
    # Apply scoring logic
    if level == "perfect":
        return 1.0  # Always okay for perfect (+ or -)
    elif level == "good":
        if is_energy_or_protein:
            # Energy/Protein: good only if positive, penalty if negative
            return 0.8 if is_positive_deviation else 0.6
        else:
            # DMI: penalty for good level (+ or -)
            return 0.8
    elif level == "marginal":
        if is_energy_or_protein:
            # Energy/Protein: okay if positive, penalty if negative
            return 0.6 if is_positive_deviation else 0.3
        else:
            # DMI: infeasible for marginal
            return 0.2
    else:  # infeasible
        return 0.1  # Always infeasible

def _calculate_critical_adequacy_score(solution_x, res, animal_requirements, f_nd):
        """Calculate critical adequacy score prioritizing Energy and Protein closeness to 100%"""
        try:
            adequacy_results = _calculate_detailed_adequacy(res, solution_x, f_nd, animal_requirements)
            
            # Extract critical nutrient percentages
            dmi_pct = _extract_percentage_from_adequacy(adequacy_results.get("DMI", "0%"))
            energy_pct = _extract_percentage_from_adequacy(adequacy_results.get("Energy", "0%"))
            protein_pct = _extract_percentage_from_adequacy(adequacy_results.get("Protein", "0%"))

            
            # Get tolerance ranges from global configuration
            animal_type = animal_requirements.get("An_StatePhys", "Lactating Cow")
            tolerance_ranges = CONSTRAINT_TOLERANCE_RANGES.get(animal_type, {})
            
            # Score each critical nutrient using tolerance ranges
            dmi_score = _score_nutrient_by_tolerance(dmi_pct, 100.0, "dmi", tolerance_ranges, is_energy_or_protein=False)
            energy_score = _score_nutrient_by_tolerance(energy_pct, 100.0, "energy", tolerance_ranges, is_energy_or_protein=True)
            protein_score = _score_nutrient_by_tolerance(protein_pct, 100.0, "protein", tolerance_ranges, is_energy_or_protein=True)
            
            # Weighted average: Energy and Protein are more important
            # DMI: 30% weight, Energy: 35% weight, Protein: 35% weight
            critical_adequacy_score = (
                0.30 * dmi_score +
                0.35 * energy_score + 
                0.35 * protein_score
            )
            
            # Additional bonus if Energy AND Protein are both ≥98%
            if energy_pct >= 98.0 and protein_pct >= 98.0:
                bonus_multiplier = 1.1  # 10% bonus for excellent Energy+Protein
                critical_adequacy_score = min(1.0, critical_adequacy_score * bonus_multiplier)
            
            return critical_adequacy_score
        except Exception as e:
            print(f"Error calculating critical adequacy: {e}")
            return 0.5  # Neutral score on error

def _calculate_composite_score(solution, res, f_nd, animal_requirements, categories=None, population_costs=None):
        """Calculate weighted composite score balancing all objectives with critical adequacy priority"""
        try:
            # Calculate critical adequacy score (DMI, Energy, Protein)
            critical_adequacy_score = _calculate_critical_adequacy_score(solution["x"], res, animal_requirements, f_nd)
            
            # Practicality score - pass cached q to avoid redundant calculations
            decision_mode = getattr(getattr(res, "problem", None), "decision_mode", "kg")
            trg_dmi = float(animal_requirements["Trg_Dt_DMIn"])
            cached_q = rsm_decode_solution_to_q(solution["x"], decision_mode, trg_dmi)[0]
            practicality_data = _calculate_practicality_score(solution, res, animal_requirements, f_nd, categories, cached_q)
            practicality_score = practicality_data['overall']
            
            # Constraint compliance
            constraint_score = _score_constraint_compliance(solution)
            
            # Cost efficiency (dynamic min-max normalization and invert)
            if population_costs and len(population_costs) > 1:
                min_cost = min(population_costs)
                max_cost = max(population_costs)
                cost_range = max_cost - min_cost
                if cost_range > 1e-9:  # Avoid division by zero
                    cost_normalized = (solution["cost"] - min_cost) / cost_range
                    cost_score = max(0.0, 1.0 - cost_normalized)  # Invert: lower cost = higher score
                else:
                    cost_score = 1.0  # All costs are the same
            else:
                cost_score = 1.0  # Single solution or no cost data
            
            # Weighted composite using configuration 
            weights = SELECTION_CONFIG['objective_weights']
            composite = (
                weights['critical_adequacy'] * critical_adequacy_score +
                weights['practicality'] * practicality_score +
                weights['constraints'] * constraint_score +
                weights['cost'] * cost_score
            )
            
            return {
                'composite': composite,
                'critical_adequacy': critical_adequacy_score, # Track critical adequacy
                'practicality': practicality_score,
                'constraints': constraint_score,
                'cost': cost_score,
                'practicality_data': practicality_data
            }
        except Exception as e:
            print(f"Error in composite scoring: {e}")
            return {'composite': 0.5, 'critical_adequacy': 0.5, 'practicality': 0.5, 
                   'constraints': 0.5, 'cost': 0.5, 'practicality_data': {'overall': 0.5, 'forage_pct': 25.0}}

def _apply_fallback_logic(candidates):
        """Smart fallback when top solutions are impractical"""
        
        if not candidates:
            print("No candidates available!")
            return None, "No candidates available"
        
        # Sort by composite score
        ranked = sorted(candidates, key=lambda x: x['scores']['composite'], reverse=True)
        
        # Check all candidates for practicality
        threshold = SELECTION_CONFIG['practicality_threshold']
        
        for i, candidate in enumerate(ranked):
            practicality = candidate['scores']['practicality_data']['overall']
            forage_pct = candidate['scores']['practicality_data']['forage_pct']
            
            # Only show details for first 10 candidates to prevent console spam
            if i < 10:
                # print(f"Candidate #{i+1}: practicality={practicality:.3f}, forage={forage_pct:.1f}%")
                pass
            
            if practicality >= threshold and forage_pct >= SELECTION_CONFIG['forage_minimum_pct']:
                print(f"MEETS CRITERIA - Selecting solution #{i+1}")
                return candidate, f"Selected candidate #{i+1}"
            else:
                if i < 10:  # Only show rejection reasons for first 10
                    reasons = []
                    if practicality < threshold:
                        reasons.append(f"low practicality ({practicality:.3f} < {threshold})")
                    if forage_pct < SELECTION_CONFIG['forage_minimum_pct']:
                        reasons.append(f"low forage ({forage_pct:.1f}% < {SELECTION_CONFIG['forage_minimum_pct']}%)")
                    # print(f"REJECTED: {', '.join(reasons)}")
                
            if i == 0:  # Log if #1 solution is impractical
                # print(f"Top solution rejected: practicality={practicality:.3f}, forage={forage_pct:.1f}%")
                pass
            elif i == 9 and len(ranked) > 10:  # Indicate if more candidates exist
                # print(f"... checking {len(ranked) - 10} more candidates silently ...")
                pass
        
        # Fallback: Find best solution above practicality threshold
        print(f"\n   🔍 EXTENDED FALLBACK SEARCH:")
        practical_candidates = [
            c for c in ranked 
            if (c['scores']['practicality_data']['overall'] >= threshold and 
                c['scores']['practicality_data']['forage_pct'] >= SELECTION_CONFIG['forage_minimum_pct'])
        ]
        
        print(f"   Found {len(practical_candidates)} practical candidates out of {len(ranked)} total")
        
        if practical_candidates:
            selected = practical_candidates[0]
            pract_score = selected['scores']['practicality_data']['overall']
            forage_pct = selected['scores']['practicality_data']['forage_pct']
            print(f"   🔄 FALLBACK SUCCESS: Selected practical solution #{ranked.index(selected)+1}")
            print(f"      Practicality: {pract_score:.3f}, Forage: {forage_pct:.1f}%")
            return selected, "Fallback to practical solution"
        
        # Last resort: Select best overall but flag as impractical
        print("LAST RESORT: No practical solutions found anywhere!")
        print(f"   Selecting best available (composite score: {ranked[0]['scores']['composite']:.3f})")
        return ranked[0], "Warning: No practical solutions found"

def _calculate_detailed_adequacy(res, solution_x, f_nd, animal_requirements):
    """Calculate detailed adequacy percentages aligned with CONSTRAINT_TOLERANCE_RANGES"""
    try:
        # Convert solution to quantities
        decision_mode = getattr(getattr(res, "problem", None), "decision_mode", "kg")
        trg_dmi = float(animal_requirements["Trg_Dt_DMIn"])
        q = rsm_decode_solution_to_q(solution_x, decision_mode, trg_dmi)[0]
        
        # Calculate nutritional supply
        diet_summary_values, intermediate_results_values, _ = rsm_diet_supply(q, f_nd, animal_requirements)
        
        # Get animal type and tolerance ranges
        animal_type = animal_requirements.get("An_StatePhys", "Lactating Cow")
        tolerance_ranges = CONSTRAINT_TOLERANCE_RANGES.get(animal_type, {})
        
        # Get animal requirements and thresholds
        st = animal_requirements["An_StatePhys"].strip().lower()
        is_heifer = ("heifer" in st)
        thr = Constraints[animal_requirements["An_StatePhys"]]
        
        adequacy_results = {}

        # Core nutritional constraints
        dmi_req = float(animal_requirements["Trg_Dt_DMIn"])
        energy_req = float(animal_requirements["An_ME"] if is_heifer else animal_requirements["An_NEL"])
        protein_req = float(intermediate_results_values[2])
        ca_req = float(animal_requirements.get("An_Ca_req", 0.0))
        p_req = float(animal_requirements.get("An_P_req", 0.0))
        
        dmi_supply = float(diet_summary_values[0])
        energy_supply = float(diet_summary_values[1])
        protein_supply = float(diet_summary_values[2])
        ca_supply = float(diet_summary_values[3])
        p_supply = float(diet_summary_values[4])
        ndf_supply = float(diet_summary_values[5])
        ndf_for_supply = float(diet_summary_values[6])
        starch_supply = float(diet_summary_values[7])
        ee_supply = float(diet_summary_values[8])
        
        # Evaluate core constraints
        if dmi_req > 0:
            result = evaluate_constraint_adequacy(dmi_supply, dmi_req, "dmi", animal_requirements, "DMI", "kg/day")
            if result: adequacy_results["DMI"] = result
            
        if energy_req > 0:
            result = evaluate_constraint_adequacy(energy_supply, energy_req, "energy", animal_requirements, "Energy", "Mcal/day")
            if result: adequacy_results["Energy"] = result
            
        if protein_req > 0:
            result = evaluate_constraint_adequacy(protein_supply, protein_req, "protein", animal_requirements, "Protein", "g/day")
            if result: adequacy_results["Protein"] = result
            
        if ca_req > 0:
            result = evaluate_constraint_adequacy(ca_supply, ca_req, "ca", animal_requirements, "Calcium", "kg/day")
            if result: adequacy_results["Calcium"] = result
            
        if p_req > 0:
            result = evaluate_constraint_adequacy(p_supply, p_req, "p", animal_requirements, "Phosphorus", "kg/day")
            if result: adequacy_results["Phosphorus"] = result
            
        # NDF forage minimum
        ndf_for_min_kg = float(thr.get("ndf_for", 0.20) * dmi_req)
        if ndf_for_min_kg > 0:
            result = evaluate_constraint_adequacy(ndf_for_supply, ndf_for_min_kg, "ndf_for", animal_requirements, "Forage NDF", "kg/day")
            if result: adequacy_results["Forage NDF"] = result
        
        # Maximum limits
        ndf_max_kg = float(thr["ndf"] * dmi_req)
        starch_max_kg = float(thr["starch_max"] * dmi_req)
        ee_max_kg = float(thr["ee_max"] * dmi_req)
        
        # Debug NDF adequacy calculation (removed - issue fixed)
            
        if ndf_max_kg > 0:
            result = evaluate_constraint_adequacy(ndf_supply, ndf_max_kg, "ndf", animal_requirements, "NDF", "kg/day")
            if result: adequacy_results["NDF"] = result
            
        if starch_max_kg > 0:
            result = evaluate_constraint_adequacy(starch_supply, starch_max_kg, "starch", animal_requirements, "Starch", "kg/day")
            if result: adequacy_results["Starch"] = result
            
        if ee_max_kg > 0:
            result = evaluate_constraint_adequacy(ee_supply, ee_max_kg, "fat", animal_requirements, "Fat", "kg/day")
            if result: adequacy_results["Fat"] = result
            
        # Conditional constraints
        categories = rsm_detect_present_categories(f_nd)
            
        # Concentrate maximum
        mask_conc_all = categories.get('mask_conc_all')
        if mask_conc_all is not None and len(mask_conc_all) == len(q):
            conc_kg = float(np.sum(q[mask_conc_all]) if np.any(mask_conc_all) else 0.0)
            conc_limit = float(thr.get("conc_max", 0.6) * dmi_req)
            if conc_limit > 0:
                result = evaluate_constraint_adequacy(conc_kg, conc_limit, "conc_max", animal_requirements, "Concentrate", "kg/day")
                if result: adequacy_results["Concentrate"] = result
        
        # Moist forage minimum
        mask_moist_forage = categories.get('mask_moist_forage')
        if mask_moist_forage is not None and len(mask_moist_forage) == len(q):
            moist_kg = float(np.sum(q[mask_moist_forage]) if np.any(mask_moist_forage) else 0.0)
            moist_req = float(thr.get("moist_forage_min", 0.2) * dmi_req)
            if moist_req > 0:
                result = evaluate_constraint_adequacy(moist_kg, moist_req, "moist_forage_min", animal_requirements, "Moist Forage", "kg/day")
                # Special formatting for moist forage to show MINIMUM
                if result:
                    result = result.replace("/ REQ ", "/ MINIMUM ")
                    adequacy_results["Moist Forage"] = result
        
        # Straw maximum  
        mask_straw = categories.get('mask_straw')
        if mask_straw is not None and len(mask_straw) == len(q):
            straw_kg = float(np.sum(q[mask_straw]) if np.any(mask_straw) else 0.0)
            straw_lim = float(thr.get("forage_straw_max", 0.25) * dmi_req)
            if straw_lim > 0:
                result = evaluate_constraint_adequacy(straw_kg, straw_lim, "forage_straw_max", animal_requirements, "Straw", "kg/day")
                if result: adequacy_results["Straw"] = result
        
        # Fibrous forage maximum
        mask_lqf = categories.get('mask_lqf')
        if mask_lqf is not None and len(mask_lqf) == len(q):
            lqf_kg = float(np.sum(q[mask_lqf]) if np.any(mask_lqf) else 0.0)
            lqf_lim = float(thr.get("forage_fibrous_max", 0.80) * dmi_req)
            if lqf_lim > 0:
                result = evaluate_constraint_adequacy(lqf_kg, lqf_lim, "forage_fibrous_max", animal_requirements, "Fibrous Forage", "kg/day")
                if result: adequacy_results["Fibrous Forage"] = result
        
        # By-product maximum
        mask_wet_byprod = categories.get('mask_wet_byprod')
        if mask_wet_byprod is not None and len(mask_wet_byprod) == len(q):
            byprod_kg = float(np.sum(q[mask_wet_byprod]) if np.any(mask_wet_byprod) else 0.0)
            byprod_lim = float(thr.get("conc_byprod_max", 0.30) * dmi_req)
            if byprod_lim > 0:
                result = evaluate_constraint_adequacy(byprod_kg, byprod_lim, "conc_byprod_max", animal_requirements, "By-product", "kg/day")
                if result: adequacy_results["By-product"] = result
        
        # Other wet ingredients maximum
        mask_wet_other = categories.get('mask_wet_other')
        if mask_wet_other is not None and len(mask_wet_other) == len(q):
            other_wet_kg = float(np.sum(q[mask_wet_other]) if np.any(mask_wet_other) else 0.0)
            other_wet_lim = float(thr.get("other_wet_ingr_max", 0.30) * dmi_req)
            if other_wet_lim > 0:
                result = evaluate_constraint_adequacy(other_wet_kg, other_wet_lim, "other_wet_ingr_max", animal_requirements, "Wet Other", "kg/day")
                if result: adequacy_results["Wet Other"] = result
        
        return adequacy_results
        
    except Exception as e:
        print(f"Error calculating detailed adequacy: {e}")
        return {}
            
def rsm_solution_selection(res, f_nd, animal_requirements, use_cv_ranking=True):
    
    # Handle empty population
    if (res is None) or (getattr(res, "X", None) is None) or (len(getattr(res, "X", [])) == 0):
        print("NO POPULATION: returning diagnostic-only")
        return None, {"satisfaction_flag": "NO_POPULATION"}, "NO_POPULATION"
    
    X = np.asarray(res.X)
    F = np.asarray(res.F) if getattr(res, "F", None) is not None else None

    costs = F[:, 0] if F is not None else np.zeros(len(X))
    intake_dev = F[:, 1] if F is not None else np.full(len(X), np.inf)
    total_dev  = F[:, 2] if (F is not None and F.shape[1] >= 3) else np.zeros(len(X))

    # Get satisfaction flags and per-constraint maps
    maps = None
    if hasattr(res.problem, 'last_satisfaction_flags'):
        flags = res.problem.last_satisfaction_flags
        print(f"Using stored satisfaction flags for {len(X)} solutions")
    else:
        # Default fallback when satisfaction flags are not available
        flags = ['MARGINAL'] * len(X)
        print(f"No satisfaction flags found, defaulting {len(X)} solutions to MARGINAL")
    
    if hasattr(res.problem, 'last_constraint_maps'):
        maps = res.problem.last_constraint_maps

    # Group solutions by satisfaction flag
    solution_groups = {"PERFECT": [], "GOOD": [], "MARGINAL": [], "INFEASIBLE": []}
    for i, (x, c, d2, d3, fl) in enumerate(zip(X, costs, intake_dev, total_dev, flags)):
        solution_groups.setdefault(fl, [])
        solution_groups[fl].append(dict(index=i, x=x, cost=float(c), dev2=float(d2), dev3=float(d3), flag=fl))

    # Handle unknown flags - map infeasible conflicts to INFEASIBLE, others to MARGINAL
    unknown_flags = set(flags) - set(solution_groups.keys())
    if unknown_flags:
        print(f"Warning: Unknown flags {unknown_flags} being processed")
        for i, (x, c, d2, d3, fl) in enumerate(zip(X, costs, intake_dev, total_dev, flags)):
            if fl in unknown_flags:
                # Map infeasible conflict flags to INFEASIBLE category
                if fl.startswith("INFEASIBLE"):
                    solution_groups["INFEASIBLE"].append(dict(
                        index=i, x=x, cost=float(c), dev2=float(d2), dev3=float(d3), flag="INFEASIBLE"
                    ))
                    print(f"  Mapped {fl} → INFEASIBLE")
                else:
                    # Map other unknown flags to MARGINAL
                    solution_groups["MARGINAL"].append(dict(
                        index=i, x=x, cost=float(c), dev2=float(d2), dev3=float(d3), flag="MARGINAL"
                    ))
                    print(f"  Mapped {fl} → MARGINAL")

    for k, v in solution_groups.items():
        print(f"{k} solutions: {len(v)}")

    # cross-group selection: evaluate PERFECT and GOOD together
    print(f"CROSS-GROUP SELECTION:")
    
    # Combine PERFECT and GOOD candidates for comparison
    perfect_candidates = solution_groups.get("PERFECT", [])
    good_candidates = solution_groups.get("GOOD", [])
    combined_candidates = perfect_candidates + good_candidates
    
    print(f"   PERFECT: {len(perfect_candidates)} candidates")
    print(f"   GOOD: {len(good_candidates)} candidates") 
    print(f"   COMBINED: {len(combined_candidates)} candidates")
    
    selected = None
    status = "INFEASIBLE"
    
    if combined_candidates:
        # Process all combined candidates        
        CV = getattr(res, "CV", None)
        categories = getattr(res, 'problem', None) and getattr(res.problem, 'categories', None)
        
        enhanced_candidates = []
        
        for item in combined_candidates:
            # Add constraint violation info
            cv_value = 0.0
            if CV is not None and len(CV) > 0:
                try:
                    idx = item.get("index", 0)
                    if idx < len(CV):
                        cv_value = float(CV[idx]) if CV[idx] is not None else 0.0
                except Exception:
                    cv_value = 0.0
            item["cv_total"] = cv_value
            
            # Add detailed constraint severities if available
            if maps and item.get("index", 0) < len(maps):
                item["constraint_severities"] = maps[item.get("index", 0)] or {}
            
            # Calculate comprehensive scores using existing categories  
            population_costs = [c["cost"] for c in combined_candidates]
            item["scores"] = _calculate_composite_score(item, res, f_nd, animal_requirements, categories, population_costs)
            
            # Calculate detailed adequacy for evaluation
            adequacy_results = _calculate_detailed_adequacy(res, item["x"], f_nd, animal_requirements)
            dmi_pct = _extract_percentage_from_adequacy(adequacy_results.get("DMI", "0%"))
            energy_pct = _extract_percentage_from_adequacy(adequacy_results.get("Energy", "0%"))
            protein_pct = _extract_percentage_from_adequacy(adequacy_results.get("Protein", "0%"))
            
            # Add adequacy info to item for sorting
            item["critical_adequacies"] = {
                "dmi": dmi_pct,
                "energy": energy_pct, 
                "protein": protein_pct,
                "min_adequacy": min(dmi_pct, energy_pct, protein_pct)
            }
            
            enhanced_candidates.append(item)
        
        # Sort by composite score (which already includes critical adequacy weighting)
        enhanced_candidates.sort(key=lambda x: x['scores']['composite'], reverse=True)
        
        # Apply practicality filter and select best
        selected_candidate, selection_msg = _apply_fallback_logic(enhanced_candidates)
        
        if selected_candidate:
            selected = selected_candidate
            # Determine status based on original flag
            if selected["flag"] == "PERFECT":
                status = "OPTIMAL"
            elif selected["flag"] == "GOOD":
                status = "GOOD"
            else:
                status = "MARGINAL"
                
            # Display comprehensive selection info
            scores = selected["scores"]
            practicality_data = scores['practicality_data']
            adeq = selected['critical_adequacies']
            
            # print(f"🎯 FINAL SELECTED SOLUTION:")
            # print(f"  Original Flag: {selected['flag']} | Final Status: {status}")
            # print(f"  Cost: ${selected['cost']:.2f} | CV: {selected.get('cv_total', 0):.6f}")
            # print(f"  Critical Nutrients - DMI: {adeq['dmi']:.1f}% | Energy: {adeq['energy']:.1f}% | Protein: {adeq['protein']:.1f}%")
            # print(f"  Composite Score: {scores['composite']:.3f}")
            # print(f"  Critical Adequacy: {scores.get('critical_adequacy', 0):.3f}")
            # print(f"  Practicality: {scores['practicality']:.3f} (forage: {practicality_data['forage_pct']:.1f}%)")
            # print(f"  Selection Reason: {selection_msg}")
    
    # Fallback to MARGINAL if no PERFECT/GOOD solutions work
    if selected is None:
        # print(f"NO SUITABLE PERFECT/GOOD SOLUTION FOUND - TRYING MARGINAL")
        marginal_candidates = solution_groups.get("MARGINAL", [])
        
        if marginal_candidates:
            # Process marginal candidates with same logic
            CV = getattr(res, "CV", None)
            categories = getattr(res, 'problem', None) and getattr(res.problem, 'categories', None)
            
            marginal_enhanced = []
            for item in marginal_candidates:
                cv_value = 0.0
                if CV is not None and len(CV) > 0:
                    try:
                        idx = item.get("index", 0)
                        if idx < len(CV):
                            cv_value = float(CV[idx]) if CV[idx] is not None else 0.0
                    except Exception:
                        cv_value = 0.0
                item["cv_total"] = cv_value
                
                if maps and item.get("index", 0) < len(maps):
                    item["constraint_severities"] = maps[item.get("index", 0)] or {}
                
                marginal_costs = [c["cost"] for c in marginal_candidates]
                item["scores"] = _calculate_composite_score(item, res, f_nd, animal_requirements, categories, marginal_costs)
                marginal_enhanced.append(item)
            
            selected_candidate, selection_msg = _apply_fallback_logic(marginal_enhanced)
            if selected_candidate:
                selected = selected_candidate
                status = "MARGINAL"
                
                scores = selected["scores"]
                practicality_data = scores['practicality_data']
                
                # print(f"MARGINAL SOLUTION SELECTED:")
                # print(f"  Cost: ${selected['cost']:.2f} | CV: {selected.get('cv_total', 0):.6f}")
                # print(f"  Composite Score: {scores['composite']:.3f}")
                # print(f"  Critical Adequacy: {scores.get('critical_adequacy', 0):.3f}")
                # print(f"  Practicality: {scores['practicality']:.3f} (forage: {practicality_data['forage_pct']:.1f}%)")
                # print(f"  Selection: {selection_msg}")

    # Final fallback to INFEASIBLE solutions if no other options
    if selected is None:
        # print(f"NO SUITABLE MARGINAL SOLUTION FOUND - TRYING INFEASIBLE (BEST AVAILABLE)")
        infeasible_candidates = solution_groups.get("INFEASIBLE", [])
        
        if infeasible_candidates:
            # Process infeasible candidates with same logic
            CV = getattr(res, "CV", None)
            categories = getattr(res, 'problem', None) and getattr(res.problem, 'categories', None)
            
            infeasible_enhanced = []
            for item in infeasible_candidates:
                cv_value = 0.0
                if CV is not None and len(CV) > 0:
                    try:
                        idx = item.get("index", 0)
                        if idx < len(CV):
                            cv_value = float(CV[idx]) if CV[idx] is not None else 0.0
                    except Exception:
                        cv_value = 0.0
                item["cv_total"] = cv_value
                
                if maps and item.get("index", 0) < len(maps):
                    item["constraint_severities"] = maps[item.get("index", 0)] or {}
                
                infeasible_costs = [c["cost"] for c in infeasible_candidates]
                item["scores"] = _calculate_composite_score(item, res, f_nd, animal_requirements, categories, infeasible_costs)
                infeasible_enhanced.append(item)
            
            selected_candidate, selection_msg = _apply_fallback_logic(infeasible_enhanced)
            if selected_candidate:
                selected = selected_candidate
                status = "INFEASIBLE"  # Keep as INFEASIBLE to trigger proper analysis
                
                scores = selected["scores"]
                practicality_data = scores['practicality_data']
                
                print(f"INFEASIBLE SOLUTION SELECTED (BEST AVAILABLE):")
                print(f"  Cost: ${selected['cost']:.2f} | CV: {selected.get('cv_total', 0):.6f}")
                print(f"  Composite Score: {scores['composite']:.3f}")
                print(f"  Critical Adequacy: {scores.get('critical_adequacy', 0):.3f}")
                print(f"  Practicality: {scores['practicality']:.3f} (forage: {practicality_data['forage_pct']:.1f}%)")
                print(f"  Selection: {selection_msg}")
                print(f"  NOTE: This solution violates constraints and will trigger detailed analysis.")

    # No suitable solution found at all
    if selected is None:
        print('NO SOLUTIONS AVAILABLE - COMPLETE FAILURE')
        return None, None, "INFEASIBLE"

    # --- Use stored constraint analysis from evaluate_constraints ---
    solution_idx = selected.get("index", 0)
    
    # Get detailed constraint analysis from stored results
    constraint_severities = {}
    if maps and solution_idx < len(maps):
        raw_severities = maps[solution_idx] or {}
        # Apply canonical naming to constraint keys for consistency
        constraint_severities = {ca_constraint_name(k): v for k, v in raw_severities.items()}
    
    # Basic solution metrics using stored flags and constraint analysis
    solution_metrics = {
        "cost": float(selected["cost"]),
        "total_cost_norm": float(selected["cost"]),
        "satisfaction_flag": selected["flag"],
        "fallback_index": selected.get("index"),
        "dev2": float(selected["dev2"]),
        "dev3": float(selected["dev3"]),
        "constraint_severities": constraint_severities,
    }
    
    # Add adequacy summary based on constraint severities
    if constraint_severities:
        adequacy_summary = {}
        # Map constraint severities to adequacy levels
        severity_to_adequacy = {
            "perfect": "Excellent (>95%)",
            "good": "Good (90-95%)", 
            "marginal": "Marginal (80-90%)",
            "infeasible": "Inadequate (<80%)"
        }
        
        key_nutrients = {
            "dmi_min": "DMI adequacy",
            "energy_min": "Energy adequacy", 
            "protein_min": "Protein adequacy"
        }
        
        # Handle both lowercase and uppercase variants for robust matching
        for constraint, nutrient_name in key_nutrients.items():
            # Try canonical version first
            severity = None
            if constraint in constraint_severities:
                severity = constraint_severities[constraint]
            else:
                # Try uppercase variants (DMI_min, Energy_min, Protein_min)
                constraint_upper = constraint.replace("dmi", "DMI").replace("energy", "Energy").replace("protein", "Protein")
                canonical_upper = ca_constraint_name(constraint_upper)
                if canonical_upper in constraint_severities:
                    severity = constraint_severities[canonical_upper]
            
            if severity:
                adequacy_summary[nutrient_name] = severity_to_adequacy.get(severity, severity)
        
        solution_metrics["adequacy_summary"] = adequacy_summary

    #print(f'solution_metrics:{solution_metrics}')

    # Add enhanced metrics if available
    if "scores" in selected:
        solution_metrics.update({
            "composite_score": selected["scores"]["composite"],
            "practicality_score": selected["scores"]["practicality"],
            "forage_percentage": selected["scores"]["practicality_data"]["forage_pct"]
        })
    
    # Calculate and display detailed adequacy percentages for all constraints
    # print(f"  Detailed Adequacy Analysis:")
    adequacy_results = _calculate_detailed_adequacy(res, selected["x"], f_nd, animal_requirements)
    # for constraint_name, adequacy_info in adequacy_results.items():
    #     if adequacy_info:
    #         print(f"    {constraint_name}: {adequacy_info}")
    
    # Add adequacy results to solution metrics for further processing
    solution_metrics["detailed_adequacy"] = adequacy_results

    # Calculate final solution vector
    decision_mode = getattr(getattr(res, "problem", None), "decision_mode", "kg")
    trg_dmi = float(animal_requirements["Trg_Dt_DMIn"])
    q = rsm_decode_solution_to_q(selected["x"], decision_mode, trg_dmi)[0]
    
    return q, solution_metrics, status

