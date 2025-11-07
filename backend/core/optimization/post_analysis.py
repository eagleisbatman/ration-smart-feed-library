"""
Post-optimization analysis module.

This module contains post-optimization analysis and validation:
- Solution cleaning and validation
- Post-optimization analysis orchestration
- Warning system and policy engine
- Constraint violation analysis
- User-facing guidance generation
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass

# Import from config
from .config import Constraints, CONSTRAINT_TOLERANCE_RANGES

# Import from utilities
from .utilities import _msg

# Import from optimization_core
from .optimization_core import (
    rsm_decode_solution_to_q,
    rsm_diet_supply,
    rsm_detect_present_categories
)

# Import from constraints
from .constraints import (
    extract_constraint_deviations,
    pick_band_and_distance,
    ca_constraint_name,
    _counts_as_marginal,
    _counts_as_infeasible,
    _append_actions_for_constraint,
    _resolve_action_conflicts,
    CONSTRAINT_META,
    PRESENTATION,
    CRITICAL_REQS
)

# Import from solution_selection
from .solution_selection import rsm_solution_selection

# Import from animal_requirements (for creating dataframes)
from .animal_requirements import rsm_create_animal_inputs_dataframe

# Import from diet_tables
from .diet_tables import (
    rsm_create_diet_table,
    rsm_generate_nutrient_comparison,
    rsm_create_final_diet_dataframe,
    rsm_calculate_water_intake,
    rsm_create_ration_evaluation,
    rsm_create_proportions_dataframe,
    rsm_calculate_methane_emissions
)

def rsm_clean_solution(best_q, f_nd,
                   forage_conc_th=0.1, mineral_add_th=0.005):
    # Clean very small ingredient amount of final result
    messages = []
    if best_q is None:
        return None, f_nd, messages, []

    f_df = pd.DataFrame(f_nd)
    q = np.asarray(best_q, dtype=float).copy()
    cleaning_log = []

    # Basic shape guard
    n = len(q)
    if "Fd_Name" not in f_nd or len(f_nd["Fd_Name"]) != n:
        messages.append(_msg("ERROR","RFT-INP-001","clean_solution",
                             "Mismatch between solution length and feed library.",
                             detail=f"best_q={n}, Fd_Name={len(f_nd.get('Fd_Name',[]))}",
                             hint="Re-run optimization or rebuild feed list."))
        n = min(n, len(f_nd.get("Fd_Name", [])))
        q = q[:n]

    for i, amt in enumerate(q):
        nm = str(f_df.iloc[i].get('Fd_Name', f'idx-{i}'))
        t  = str(f_df.iloc[i].get('Fd_Type', ''))
        c  = str(f_df.iloc[i].get('Fd_Category', ''))
        if np.isnan(amt) or amt < 0:
            messages.append(_msg("WARN","RFT-INP-002","clean_solution",
                                 f"Invalid amount for {nm} set to 0.",
                                 detail=f"amt={amt}"))
            amt = 0.0
            q[i] = 0.0

        # Determine threshold and label based on feed type/category
        if (t in ['Minerals','Additive'] or c in ['Minerals','Additive']
              or 'urea' in nm.lower() or 'premix' in nm.lower()):
            th = mineral_add_th; label = "Mineral/Additive"
        else:
            th = forage_conc_th; label = "Forage/Concentrate"

        if amt < th:
            cleaning_log.append(f"{nm} ({label}) {amt:.3f} → 0.000")
            q[i] = 0.0

    return q, f_nd, messages, cleaning_log

def rsm_run_post_optimization_analysis(res, f_nd, animal_requirements):
    messages = []

    # 1) Selection 
    best_q, best_metrics_result, status = rsm_solution_selection(res, f_nd, animal_requirements, use_cv_ranking=True)

    if best_q is None or status == "INFEASIBLE":
        # Run full constraint analysis to provide detailed guidance for infeasible solutions
        
        # Try to get the best available solution from optimization results instead of creating fake baseline
        analysis_solution = None
        if res is not None and hasattr(res, 'X') and res.X is not None and len(res.X) > 0:
            # Use the best solution found by optimizer (even if infeasible)
            X = np.asarray(res.X)
            F = np.asarray(res.F) if hasattr(res, 'F') and res.F is not None else None
            
            if F is not None and F.ndim >= 2 and F.shape[0] > 0 and F.shape[1] >= 3:
                # Find solution with best dev2 and dev3 (lowest combined deviation) - with NaN safety
                combined = F[:, 1] + F[:, 2]  # dev2 + dev3
                if np.any(np.isfinite(combined)):
                    best_idx = np.nanargmin(combined)
                    analysis_solution = X[best_idx]
                    print(f"Using best optimizer solution (index {best_idx}) based on lowest deviation for constraint analysis")
                else:
                    # All values are NaN/infinite - use first solution
                    best_idx = 0
                    analysis_solution = X[best_idx]
                    print("Using first optimizer solution for constraint analysis (all deviations are NaN/infinite)")
            elif F is not None and F.ndim >= 2 and F.shape[0] > 0:
                # F exists but has incomplete objectives
                best_idx = 0
                analysis_solution = X[best_idx]
                print("Using first optimizer solution for constraint analysis (incomplete objectives)")
            else:
                # No valid F matrix - use first solution
                best_idx = 0
                analysis_solution = X[best_idx]
                print("Using first optimizer solution for constraint analysis (no valid objectives)")
        
        # Handle optimization failure cases - Use policy engine
        if analysis_solution is None or (best_q is None and status == "INFEASIBLE"):
            # Determine the specific failure reason
            if analysis_solution is None:
                if res is not None and hasattr(res, 'X') and res.X is not None and len(res.X) > 0:
                    # We have a population but no acceptable solutions
                    reason = "POPULATION_ALL_INFEASIBLE"
                else:
                    # No population generated at all
                    reason = "NO_POPULATION"
            else:
                # We have analysis_solution but best_q is None and status is INFEASIBLE
                # This means all solutions in population are infeasible
                reason = "POPULATION_ALL_INFEASIBLE"
                
            violation_report = user_warnings(
                diet_summary_values=None,
                intermediate_results_values=None,
                animal_requirements=animal_requirements,
                f_nd=f_nd,
                best_q=None,
                debug=False, 
                categories=None,  # Let user_warnings compute lazily
                reason=reason   
            )
            
            # Return early with policy engine's analysis
            return {
                'status': 'FAILURE',
                'status_classification': 'INFEASIBLE',
                'error_message': 'No acceptable solution found',
                'violation_report': violation_report,
                'messages': [],
                'cleaning_log': []
            }
        
        try:
            # Decode the optimization solution to feed quantities before analysis
            decision_mode = getattr(getattr(res, "problem", None), "decision_mode", "kg")
            trg_dmi = float(animal_requirements["Trg_Dt_DMIn"])
            analysis_q = rsm_decode_solution_to_q(analysis_solution, decision_mode, trg_dmi)[0]
            
            # Calculate what the analysis solution would provide
            diet_summary_values, intermediate_results_values, _ = rsm_diet_supply(analysis_q, f_nd, animal_requirements)
            
            # Run full constraint violation analysis to get integrated guidance
            violation_report = user_warnings(
                diet_summary_values, intermediate_results_values, animal_requirements, f_nd, 
                analysis_q, debug=False, categories=None  # Let user_warnings compute lazily
            )
            
            # Policy engine in user_warnings now handles all messaging
            # Just pass through the violation_report with policy payload
            messages.append(_msg("INFO", "RFT-INF-001", "infeasibility_analysis",
                                 "Detailed infeasibility analysis completed using policy engine."))
            
        except Exception as e:
            # Fallback if analysis fails - use same policy as no population
            violation_report = user_warnings(
                diet_summary_values=None,
                intermediate_results_values=None,
                animal_requirements=animal_requirements,
                f_nd=f_nd,
                best_q=None,
                debug=False,
                categories=None,  # Let user_warnings compute lazily
                reason="ANALYSIS_FAILED"   
            )
            
            messages.append(_msg("ERROR", "RFT-INF-002", "infeasibility_analysis",
                                 "Failed to analyze infeasibility reasons.",
                                 detail=str(e), hint="Check feed library and animal requirements."))
        
        # Create consistent best_metrics_result dict structure
        best_metrics_result_stub = {
            "cost": 0.0,
            "total_cost_norm": 0.0,
            "satisfaction_flag": "INFEASIBLE",
            "fallback_index": None,
            "dev2": float('inf'),
            "dev3": float('inf'),
            "constraint_severities": {},
            "dmi_adequacy": None,
            "energy_adequacy": None,
            "protein_adequacy": None,
            "rank": "VERY_LOW"
        }
        
        return {
            'status': 'FAILURE',
            'status_classification': 'INFEASIBLE',
            'best_metrics_result': best_metrics_result_stub,
            'total_cost': 0,
            'water_intake': 0,
            'nutrient_comparison': pd.DataFrame(),
            'Dt_kg': pd.DataFrame(),
            'error_message': 'No acceptable solution found',
            'violation_report': violation_report,
            'messages': messages,
            'cleaning_log': []
        }
    
    # 2) Clean
    best_q, f_nd, msgA, cleaning_log = rsm_clean_solution(best_q, f_nd)
    messages.extend(msgA)

    # 3) Recalculate nutritional values after cleaning
    try:
        diet_summary, intermediates, An_MPm = rsm_diet_supply(best_q, f_nd, animal_requirements)
    except Exception as e:
        messages.append(_msg("BLOCKER", "RFT-ANL-001", "diet_supply",
                             "Failed to recalculate the diet after cleaning.",
                             detail=str(e), hint="Check feed library rows and units."))
        raise

    # 4) Update adequacy % into best_metrics_result 
    st = animal_requirements.get("An_StatePhys", "").strip().lower()
    is_heifer = "heifer" in st
    energy_req = float(animal_requirements["An_ME"] if is_heifer else animal_requirements["An_NEL"])
    protein_req = float(intermediates[2])   # MP req (kg/d)
    dmi_req = float(animal_requirements["Trg_Dt_DMIn"])
    dmi_supply, energy_supply, protein_supply = map(float, diet_summary[:3])
    for metric, supply, req in [
        ('dmi_adequacy', dmi_supply, dmi_req),
        ('energy_adequacy', energy_supply, energy_req),
        ('protein_adequacy', protein_supply, protein_req)
    ]:
        best_metrics_result[metric] = 100.0 * supply / max(req, 1e-9)

    # 5) Constraint analysis
    categories = rsm_detect_present_categories(f_nd)
    
    #For manual constraint deviation input
    constraint_deviations = extract_constraint_deviations(
        diet_summary, intermediates, animal_requirements, f_nd, best_q, categories
    )
    violation_report = user_warnings(
        diet_summary, intermediates, animal_requirements, f_nd, best_q,
        debug=False, categories=categories, reason=None,
        constraint_pct_devs=constraint_deviations
    )

    policy_status = violation_report.get("recommended_status", "OPTIMAL")
    block_report = bool(violation_report.get("block_report", False))

    # 7) Tables & reports — Generate all reports, let frontend decide display
    diet_table, total_real_cost = rsm_create_diet_table(best_q, f_nd)
    nutrient_comparison = rsm_generate_nutrient_comparison(diet_summary, intermediates, animal_requirements, f_nd)
    Dt, final_diet_df, Dt_DMInSum, Dt_AFIn = rsm_create_final_diet_dataframe(diet_table, f_nd)
    water_intake = rsm_calculate_water_intake(Dt_DMInSum, Dt_AFIn, f_nd, animal_requirements, best_q)
    ration_evaluation = rsm_create_ration_evaluation(diet_summary, intermediates, animal_requirements, diet_table, f_nd, best_q)
    animal_inputs = rsm_create_animal_inputs_dataframe(animal_requirements)
    dt_proportions, dt_forages, dt_concentrates, dt_results = rsm_create_proportions_dataframe(Dt, Dt_DMInSum)
    methane_report = rsm_calculate_methane_emissions(Dt, Dt_DMInSum, f_nd, animal_requirements, best_q)

    # 8) Compose neat result - Pass through policy engine's status
    return {
        'status': 'SUCCESS',
        'status_classification': policy_status,
        'confidence_level': {
            'OPTIMAL': 'HIGH', 'GOOD': 'HIGH', 'MARGINAL': 'MEDIUM', 'INFEASIBLE': 'LOW'
        }.get(policy_status, 'MEDIUM'),

        'total_cost': total_real_cost,
        'water_intake': water_intake,
        'best_solution_result': best_q,  # kg/d

        'diet_summary_values': diet_summary,
        'intermediate_results_values': intermediates,
        'diet_table': diet_table,
        'animal_inputs': animal_inputs,
        'ration_evaluation': ration_evaluation,

        'Dt_kg': final_diet_df,
        'dt_proportions': dt_proportions,
        'dt_forages': dt_forages,

        'methane_report': methane_report,
        'best_metrics_result': best_metrics_result,
        'violation_report': violation_report,
        'counts': {
            "marginal_count": violation_report.get("marginal_count", 0),
            "infeasible_count": violation_report.get("infeasible_count", 0),
            "critical_infeasible": violation_report.get("critical_infeasible", False)
        },

        'messages': messages,
        'cleaning_log': cleaning_log,
    }

# ==================================================================
# WARNINGS
# ==================================================================

def _should_flip(constraint: str, ce) -> bool:
    band = ce.status_band
    dirn = ce.direction  # "over" | "under" | "within"

    if constraint == "dmi":
        return band in ("marginal", "infeasible")

    if constraint in ("energy", "protein"):
        return (band == "marginal" and dirn == "under") or (band == "infeasible")

    if constraint in ("ca", "p"):
        return band == "infeasible" and dirn == "under"

    if constraint == "ndf_for":
        return band == "infeasible" and dirn == "under"

    if constraint in ("ndf", "starch", "fat", "conc_max", "conc_byprod_max",
                      "other_wet_ingr_max", "forage_straw_max", "forage_fibrous_max"):
        return band == "infeasible" and dirn == "over"

    if constraint == "moist_forage_min":
        return band == "infeasible" and dirn == "under"

    return False

def _dev_text(ce, constraint_type: str):
    # Generate human-readable deviation text like '+31% over target' or 'short by 30%'
    dev = abs(ce.raw_deviation)
    if ce.direction == "over":
        return f"~+{dev:.0f}% over target"
    if ce.direction == "under" and constraint_type in ("min", "both"):
        return f"~{dev:.0f}% short of target"
    # fallback
    sign = "+" if ce.raw_deviation >= 0 else ""
    return f"{sign}{ce.raw_deviation:.0f}%"

# Short, category-level actions keyed by constraint + direction

def build_tech_note_messages(evals):
    """
    Returns a list[str] with two compact sections only:
    1) Critical violations (table-flip items)
    2) Brief action needed (constraint-aware, direction-specific guidance)
    """
    lines = []
    max_crit = PRESENTATION.get("max_crit", 3)
    max_actions = PRESENTATION.get("max_actions", 3)

    # ---------- 1) Critical violations ----------
    crit = []
    order = ["dmi", "energy", "protein", "ndf_for", "conc_max", "starch", "fat", "ndf",
             "moist_forage_min", "ca", "p", "forage_straw_max", "forage_fibrous_max",
             "conc_byprod_max", "other_wet_ingr_max", "urea_max"]
    for c in order:
        ce = evals.get(c)
        if not ce: 
            continue
        if _should_flip(c, ce):
            disp = ca_constraint_name(c, "clean_display")
            ctype = CONSTRAINT_META.get(c, {}).get("type", "both")
            crit.append(f"• {disp}: {_dev_text(ce, ctype)}")
    crit = crit[:max_crit]
    if crit:
        lines.append("Critical violations:")
        lines.extend(crit)

    # ---------- 2) Brief action needed ----------
    actions = []

    # Add specific actions driven by the actual violated constraints
    # Only show actions for constraints that count toward decision (filter out warn-only)
    for c in order:
        ce = evals.get(c)
        if ce and ce.status_band in ("marginal", "infeasible") and (
            _counts_as_marginal(c, ce) or _counts_as_infeasible(c, ce)
        ):
            _append_actions_for_constraint(actions, c, ce, evals)

    # De-dup → resolve → cap
    seen, dedup = set(), []
    for a in actions:
        if a not in seen:
            dedup.append(a); seen.add(a)
    actions_clean = _resolve_action_conflicts(dedup, evals)[:max_actions]
    if actions_clean:
        lines.append("Action needed:")
        lines.extend([f"• {a}" for a in actions_clean])

    return lines

def user_warnings(
    diet_summary_values, intermediate_results_values, animal_requirements, f_nd,
    best_q=None, debug=False, categories=None, reason=None,
    constraint_pct_devs: dict = None,
    ranges_by_class: dict = None
):
    # warning system that groups related constraints and provides actionable guidance

    # TYPE-1 passthrough (existing logic for critical failures)
    if reason in {"NO_POPULATION", "POPULATION_ALL_INFEASIBLE", "ANALYSIS_FAILED"}:
        # Determine specific message based on reason
        if reason == "NO_POPULATION":
            primary_message = "Current ingredients cannot meet animal requirements"
            dev_context = "Complete optimization failure. No population generated"
        elif reason == "POPULATION_ALL_INFEASIBLE":
            primary_message = "Current ingredients cannot satisfy animal requirements"
            dev_context = "Population generated but all solutions infeasible. Ingredient combination insufficient or excessive"
        elif reason == "ANALYSIS_FAILED":
            primary_message = "Unable to evaluate diet constraints"
            dev_context = "Diet analysis system error during constraint evaluation"
        else:
            primary_message = "No viable diet solution found"
            dev_context = "Unknown failure mode - requires investigation"
        
        return {
            "has_violations": True,
            "violations": [],
            "summary": "Critical foundation issue: Ingredient combination insufficient",
            "recommended_status": "INFEASIBLE",
            "formatted_messages": [
                primary_message,
                "Critical violation: Insufficient nutrient density in available ingredients",
                "What to change: Add nutrient-dense forages and concentrates",
                "Verification: Check animal inputs and ingredient selection"
            ],
            "console_output": f"{primary_message}\nWhat to change: Add nutrient-dense forages and concentrates",
            "policy": {
                "type": "TYPE_1_OPTIMIZATION_BLANK",
                "code": "RFT-POL-001",
                "title": "RationSmart Analysis: Critical foundation issue",
                "summary": "Ingredient combination insufficient",
                "user_messages": [
                    primary_message,
                    "Critical violation: Insufficient nutrient density in available ingredients",
                    "What to change: Add nutrient-dense forages and concentrates", 
                    "Verification: Check animal inputs and ingredient selection"
                ],
                "dev_notes": [
                    dev_context,
                    "No solution population generated or all solutions infeasible",
                    "Requires fundamental ingredient addition, not parameter adjustment"
                ]
            },
            "pattern_overlays": []
        }

    # Solid fallback for tolerance ranges
    cow_class = (animal_requirements.get("An_StatePhys") or "Lactating Cow")
    cow_class = "Lactating Cow" if "lact" in cow_class.lower() else cow_class 
    if ranges_by_class is None:
        ranges_by_class = {cow_class: CONSTRAINT_TOLERANCE_RANGES.get(cow_class, CONSTRAINT_TOLERANCE_RANGES.get("Lactating Cow", {}))}
    RANGES = ranges_by_class.get(cow_class, {})

    # If no constraint deviations provided, compute them from diet data
    if constraint_pct_devs is None and diet_summary_values is not None and intermediate_results_values is not None:
        constraint_pct_devs = extract_constraint_deviations(
            diet_summary_values, intermediate_results_values, animal_requirements, f_nd, best_q, categories
        )

    # Build a canonicalized copy first
    canon_devs = {}
    for k, v in (constraint_pct_devs or {}).items():
        canon_devs[ca_constraint_name(k)] = float(v)
    
    # Per-constraint evaluation using canonical names
    evals = {}
    if debug:
        print(f"DEBUG: Available constraint deviations: {list((constraint_pct_devs or {}).keys())}")
        print(f"DEBUG: Canonicalized deviations: {list(canon_devs.keys())}")
        print(f"DEBUG: Expected constraints in CONSTRAINT_META: {list(CONSTRAINT_META.keys())}")
    
    for c, dev in canon_devs.items():
        if c not in CONSTRAINT_META: 
            if debug: 
                print(f"DEBUG: skipping unknown constraint '{c}'")
            continue
        if c not in RANGES:
            if debug: 
                print(f"DEBUG: '{c}' missing from RANGES for this class")
            continue
        evals[c] = pick_band_and_distance(c, dev, RANGES)
    
    if debug:
        print(f"DEBUG: Successfully evaluated constraints: {list(evals.keys())}")
        for c, eval_result in evals.items():
            print(f"DEBUG: {c}: {eval_result.status_band} (deviation: {eval_result.raw_deviation:.1f}%)")

    # ---------------- DECISION RULES ----------------
    # Count marginal and infeasible according to classification table.
    marginal_count = sum(1 for c, ce in evals.items() if _counts_as_marginal(c, ce))
    infeasible_count = sum(1 for c, ce in evals.items() if _counts_as_infeasible(c, ce))

    # Critical override: if any of {protein, energy, dmi} is infeasible (in any direction that counts) → flip to infeasible
    critical_infeasible = any(
        c in CRITICAL_REQS and _counts_as_infeasible(c, ce)
        for c, ce in evals.items()
    )

    # Case 1: all constraints perfect/good  → Feasible
    # Guard against empty evals (all() returns True for empty sequences)
    any_evaluated = bool(evals)
    all_good_or_perfect = any_evaluated and all(ce.status_band in ("perfect","good") for ce in evals.values()) and (reason is None)

    # Decide overall
    overall = None
    block_report = False   # whether UI should block full diet report rendering

    if all_good_or_perfect:
        overall = "OPTIMAL"  

    else:
        # Your explicit count rules
        if critical_infeasible:
            overall = "INFEASIBLE"
            block_report = True
        elif infeasible_count > 2:
            overall = "INFEASIBLE"
            block_report = True
        elif infeasible_count <= 2:
            if marginal_count >= 4:
                overall = "INFEASIBLE"
                block_report = True
            else:
                # Diet can be displayed with warnings
                overall = "MARGINAL" if (marginal_count or infeasible_count) else "GOOD"
                block_report = False

    # Fallback if not set
    if overall is None:
        overall = "MARGINAL" if (marginal_count or infeasible_count) else "GOOD"

    # ---------------- END OF DECISION RULES ----------------

    # Build the formatted user messages
    if overall in ("OPTIMAL", "GOOD"):
        formatted_messages = []  # clean pass
    else:
        formatted_messages = build_tech_note_messages(evals)

    result = {
        "recommended_status": overall,
        "block_report": block_report,   # UI to BLOCK the diet table/export
        "has_violations": overall not in ("OPTIMAL", "GOOD"),
        "violation_count": len([ce for ce in evals.values() if ce.status_band in ("marginal", "infeasible")]),
        "summary": ("Diet meets animal requirements."
                    if overall in ("OPTIMAL", "GOOD") else
                    f"Diet has {overall.lower()} imbalances — see guidance."),
        "formatted_messages": formatted_messages,
        "console_output": "\n".join(formatted_messages),
        "policy": {
            "type": "DIRECT_CONSTRAINT_EVALUATION",
            "title": f"RationSmart Analysis — {'Action needed' if overall=='INFEASIBLE' else overall}",
            "summary": ("Diet meets animal requirements." 
                       if overall in ("OPTIMAL", "GOOD") else
                       f"Diet has {overall.lower()} imbalances requiring attention. Please review ingredient selection and adjust it as needed."),
            "user_messages": formatted_messages
        },
        "marginal_count": marginal_count,
        "infeasible_count": infeasible_count,
        "critical_infeasible": critical_infeasible
    }
    
    return result

# ===================================================================
# Report generation
# ===================================================================
