"""
Constraint evaluation module.

This module contains all constraint evaluation logic for diet optimization:
- Constraint satisfaction checking
- Tolerance range evaluation
- Constraint deviation calculation
- Constraint naming and formatting
- Band-based constraint classification
"""

import numpy as np
from dataclasses import dataclass

# Import configuration
from .config import Constraints, CONSTRAINT_TOLERANCE_RANGES

# Import utilities
from .utilities import safe_divide

def evaluate_constraints(x, nutritional_supply, nutrient_targets, epsilon, f_nd, Trg_Dt_DMIn, thr, categories, animal_requirements, *, energy_offset=1.0, mp_offset=0.10, dmi_lo=0.90, dmi_hi=1.05, cfg=None, constraint_names=None):

    # Single source of truth for per-constraint severities and final flag.

    animal_type = animal_requirements.get("An_StatePhys", "Lactating Cow")

    constraint_severities = {}

    # Map indices for known constraints
    name_to_tolerance_key = {}
    if constraint_names is None:
        constraint_names = []
    for cn in constraint_names:
        if cn in ("DMI_max", "DMI_min"):
            name_to_tolerance_key[cn] = (0, 0, "dmi")
        elif cn in ("Energy_max", "Energy_min"):
            name_to_tolerance_key[cn] = (1, 1, "energy")
        elif cn in ("MP_max", "MP_min"):
            name_to_tolerance_key[cn] = (2, 2, "protein")
        elif cn == "Ca_min":
            name_to_tolerance_key[cn] = (3, 3, "ca")
        elif cn == "P_min":
            name_to_tolerance_key[cn] = (4, 4, "p")
        elif cn == "NDF_max":
            name_to_tolerance_key[cn] = (5, 5, "ndf")
        elif cn == "NDFfor_min":
            name_to_tolerance_key[cn] = (6, 6, "ndf_for")
        elif cn == "Starch_max":
            name_to_tolerance_key[cn] = (7, 7, "starch")
        elif cn == "EE_max":
            name_to_tolerance_key[cn] = (8, 8, "fat")

    # Evaluate core constraints present in the built list
    for original_name, (supply_idx, target_idx, tol_key) in name_to_tolerance_key.items():
        if target_idx < len(nutrient_targets) and nutrient_targets[target_idx] > 0:
            actual_value = float(nutritional_supply[supply_idx])
            target_value = float(nutrient_targets[target_idx])
            tolerance_config = CONSTRAINT_TOLERANCE_RANGES[animal_type].get(tol_key)
            if not tolerance_config:
                continue
            basis = tolerance_config.get("basis", "target")
            tol_type = tolerance_config.get("tolerance_type")
            eps = 1e-9

            is_min = original_name.endswith("_min")
            is_max = original_name.endswith("_max")

            if basis == "target":
                if tol_type == "both":
                    if is_min:
                        deviation_pct = (
                            ((target_value - actual_value) / max(target_value, 1e-12) * 100.0)
                            if actual_value < target_value else 0.0
                        )
                    elif is_max:
                        deviation_pct = (
                            ((actual_value - target_value) / max(target_value, 1e-12) * 100.0)
                            if actual_value > target_value else 0.0
                        )
                    else:
                        deviation_pct = abs((actual_value - target_value) / max(target_value, 1e-12) * 100.0)
                elif tol_type == "minimum":
                    deviation_pct = (
                        ((target_value - actual_value) / max(target_value, 1e-12) * 100.0)
                        if actual_value < target_value else 0.0
                    )
                else:
                    deviation_pct = abs((actual_value - target_value) / max(target_value, 1e-12) * 100.0)

                severity = "infeasible"
                for level in ["perfect", "good", "marginal", "infeasible"]:
                    if level in tolerance_config:
                        lo, hi = tolerance_config[level]
                        if level == "perfect":
                            if (deviation_pct + eps) >= lo and (deviation_pct - eps) <= hi:
                                severity = level
                                break
                        else:
                            if lo <= deviation_pct + eps < hi + eps:
                                severity = level
                                break
            else:  # basis == "limit"
                deviation_pct = (
                    ((actual_value - target_value) / max(target_value, 1e-12) * 100.0)
                    if actual_value > target_value else 0.0
                )
                if CONSTRAINT_TOLERANCE_RANGES[animal_type].get(tol_key, {}).get("perfect_zero", False) and deviation_pct <= 1e-9:
                    severity = "perfect"
                else:
                    severity = "infeasible"
                    for level in ["perfect", "good", "marginal", "infeasible"]:
                        if level in tolerance_config:
                            lo, hi = tolerance_config[level]
                            if lo <= deviation_pct + 1e-9 < hi + 1e-9:
                                severity = level
                                break

            constraint_severities[ca_constraint_name(original_name)] = severity

    # Derived/conditional constraints that depend on diet structure
    total_dmi = float(nutritional_supply[0])

    # conc_max
    if ("Conc_max" in constraint_names) and (total_dmi > 0):
        conc_kg = float(np.sum(x[categories.get('mask_conc_all', np.zeros_like(x, dtype=bool))]))
        conc_limit = float(thr.get("conc_max", 0.6) * Trg_Dt_DMIn)
        if conc_limit > 0:
            if conc_kg > conc_limit:
                dev = ((conc_kg - conc_limit) / conc_limit) * 100.0
            else:
                dev = 0.0
            tol = CONSTRAINT_TOLERANCE_RANGES[animal_type].get("conc_max")
            if tol:
                sev = "infeasible"
                for lvl in ["perfect", "good", "marginal", "infeasible"]:
                    if lvl in tol:
                        lo, hi = tol[lvl]
                        if lo <= dev < hi:
                            sev = lvl; break
                constraint_severities["conc_max"] = sev

    # moist_forage_min
    if ("MoistForage_min" in constraint_names) and (total_dmi > 0):
        moist_kg = float(np.sum(x[categories.get('mask_moist_forage', np.zeros_like(x, dtype=bool))]))
        moist_req = float(thr.get("moist_forage_min", 0.2) * Trg_Dt_DMIn)
        dev = ((moist_req - moist_kg) / max(moist_req, 1e-12) * 100.0) if moist_kg < moist_req else 0.0
        tol = CONSTRAINT_TOLERANCE_RANGES[animal_type].get("moist_forage_min")
        if tol:
            sev = "infeasible"
            for lvl in ["perfect", "good", "marginal", "infeasible"]:
                if lvl in tol:
                    lo, hi = tol[lvl]
                    if lo <= dev < hi:
                        sev = lvl; break
            constraint_severities["moist_forage_min"] = sev

    # forage_straw_max
    if ("Straw_max" in constraint_names) and (total_dmi > 0):
        straw_kg = float(np.sum(x[categories.get('mask_straw', np.zeros_like(x, dtype=bool))]))
        straw_lim = float(thr.get("forage_straw_max", 0.25) * Trg_Dt_DMIn)
        dev = ((straw_kg - straw_lim) / max(straw_lim, 1e-12) * 100.0) if straw_kg > straw_lim else 0.0
        tol = CONSTRAINT_TOLERANCE_RANGES[animal_type].get("forage_straw_max")
        if tol:
            sev = "infeasible"
            for lvl in ["perfect", "good", "marginal", "infeasible"]:
                if lvl in tol:
                    lo, hi = tol[lvl]
                    if lo <= dev < hi:
                        sev = lvl; break
            constraint_severities["forage_straw_max"] = sev

    # forage_fibrous_max
    if ("LQF_max" in constraint_names) and (total_dmi > 0):
        lqf_kg = float(np.sum(x[categories.get('mask_lqf', np.zeros_like(x, dtype=bool))]))
        lqf_lim = float(thr.get("forage_fibrous_max", 0.80) * Trg_Dt_DMIn)
        dev = ((lqf_kg - lqf_lim) / max(lqf_lim, 1e-12) * 100.0) if lqf_kg > lqf_lim else 0.0
        tol = CONSTRAINT_TOLERANCE_RANGES[animal_type].get("forage_fibrous_max")
        if tol:
            sev = "infeasible"
            for lvl in ["perfect", "good", "marginal", "infeasible"]:
                if lvl in tol:
                    lo, hi = tol[lvl]
                    if lo <= dev < hi:
                        sev = lvl; break
            constraint_severities["forage_fibrous_max"] = sev

    # conc_byprod_max
    if ("Byprod_max" in constraint_names) and (total_dmi > 0):
        byprod_kg = float(np.sum(x[categories.get('mask_wet_byprod', np.zeros_like(x, dtype=bool))]))
        byprod_lim = float(thr.get("conc_byprod_max", 0.30) * Trg_Dt_DMIn)
        dev = ((byprod_kg - byprod_lim) / max(byprod_lim, 1e-12) * 100.0) if byprod_kg > byprod_lim else 0.0
        tol = CONSTRAINT_TOLERANCE_RANGES[animal_type].get("conc_byprod_max")
        if tol:
            sev = "infeasible"
            for lvl in ["perfect", "good", "marginal", "infeasible"]:
                if lvl in tol:
                    lo, hi = tol[lvl]
                    if lo <= dev < hi:
                        sev = lvl; break
            constraint_severities["conc_byprod_max"] = sev

    # other_wet_ingr_max
    if ("WetOther_max" in constraint_names) and (total_dmi > 0):
        other_wet_kg = float(np.sum(x[categories.get('mask_wet_other', np.zeros_like(x, dtype=bool))]))
        other_wet_lim = float(thr.get("other_wet_ingr_max", 0.30) * Trg_Dt_DMIn)
        dev = ((other_wet_kg - other_wet_lim) / max(other_wet_lim, 1e-12) * 100.0) if other_wet_kg > other_wet_lim else 0.0
        tol = CONSTRAINT_TOLERANCE_RANGES[animal_type].get("other_wet_ingr_max")
        if tol:
            sev = "infeasible"
            for lvl in ["perfect", "good", "marginal", "infeasible"]:
                if lvl in tol:
                    lo, hi = tol[lvl]
                    if lo <= dev < hi:
                        sev = lvl; break
            constraint_severities["other_wet_ingr_max"] = sev

    # Final satisfaction flag using severity map and density conflicts
    eps = 1e-6
    dmi_cap = (dmi_hi + epsilon) * nutrient_targets[0]
    emin_req = (nutrient_targets[1] * 0.95 - epsilon)
    mpmin_req = (nutrient_targets[2] * 0.95 - epsilon)

    E_density = float(nutritional_supply[1]) / max(float(nutritional_supply[0]), eps)
    MP_density = float(nutritional_supply[2]) / max(float(nutritional_supply[0]), eps)

    dmi_needed_for_E = emin_req / max(E_density, eps)
    dmi_needed_for_MP = mpmin_req / max(MP_density, eps)

    conflict_E = dmi_needed_for_E > dmi_cap + 1e-9
    conflict_MP = dmi_needed_for_MP > dmi_cap + 1e-9

    # Define safety-critical constraints (any violation = INFEASIBLE)
    safety_violation_levels = {
        "dmi_min": {"marginal", "infeasible"},      # DMI too low = safety risk
        "dmi_max": {"marginal", "infeasible"},      # DMI too high = safety risk
        "energy_min": {"infeasible"},               # Energy deficit = immediate safety risk
        "energy_max": {"infeasible"},               # Energy excess = safety risk
        "protein_min": {"infeasible"},              # Protein deficit = immediate safety risk
        "protein_max": {"infeasible"},              # Protein excess = safety risk
    }

    # Count violations by type and severity
    safety_violations = 0
    infeasible_violations = 0
    critical_infeasible = 0  # Count infeasible violations in critical nutrients
    
    critical_nutrients = [ca_constraint_name(name) for name in ["DMI_min", "DMI_max", "Energy_min", "Energy_max", "MP_min", "MP_max"]]
    
    for cname, sev in constraint_severities.items():
        # Count safety violations (marginal or infeasible in safety-critical constraints)
        lvls = safety_violation_levels.get(cname)
        if lvls and sev in lvls:
            safety_violations += 1
        
        # Count all infeasible violations
        if sev == "infeasible":
            infeasible_violations += 1
            # Count critical nutrient infeasible violations separately
            if cname in critical_nutrients:
                critical_infeasible += 1

    # Hierarchical classification logic (more stringent)
    if conflict_E or conflict_MP:
        # Structural impossibility - physically cannot meet requirements
        if conflict_E and conflict_MP:
            satisfaction_flag = "INFEASIBLE|CONFLICT:E&MP"
        elif conflict_E:
            satisfaction_flag = "INFEASIBLE|CONFLICT:E"
        else:
            satisfaction_flag = "INFEASIBLE|CONFLICT:MP"
    elif critical_infeasible > 0:
        # Any infeasible critical nutrient = INFEASIBLE
        satisfaction_flag = "INFEASIBLE"
    elif safety_violations > 1:
        # More than 1 safety violation = INFEASIBLE
        satisfaction_flag = "INFEASIBLE" 
    elif infeasible_violations > 1:
        # More than 1 infeasible violation total = INFEASIBLE (stricter than before)
        satisfaction_flag = "INFEASIBLE"
    else:
        # Positive classification based on constraint quality
        perfect_count = sum(1 for s in constraint_severities.values() if s == "perfect")
        good_count = sum(1 for s in constraint_severities.values() if s == "good")
        marginal_count = sum(1 for s in constraint_severities.values() if s == "marginal")
        infeasible_count = sum(1 for s in constraint_severities.values() if s == "infeasible")
        total_constraints = len(constraint_severities)
        
        if total_constraints > 0:
            # Enforce "≥4 marginal/infeasible → INFEASIBLE" rule
            marginal_infeasible_count = marginal_count + infeasible_count
            if marginal_infeasible_count >= 4:
                satisfaction_flag = "INFEASIBLE"  # ≥4 marginal/infeasible constraints
            # Stricter thresholds for PERFECT and GOOD
            elif perfect_count >= (total_constraints * 0.85):  # Increased from 0.8
                satisfaction_flag = "PERFECT"
            elif (perfect_count + good_count) >= (total_constraints * 0.75):  # Increased from 0.7
                satisfaction_flag = "GOOD"
            else:
                satisfaction_flag = "MARGINAL"
        else:
            satisfaction_flag = "MARGINAL"

    return constraint_severities, satisfaction_flag


def build_conditional_constraints(x, nutritional_supply, nutrient_targets, epsilon, f_nd, Trg_Dt_DMIn, thr, categories, animal_requirements, energy_offset=1.0, mp_offset=0.10,
                                  apply_offset_on_max=True, dmi_lo=0.90, dmi_hi=1.05, cfg=None):
    G = []
    scales = []
    constraint_names = []
    
    #Core nutritional constraints (always applied)
    
    # DMI constraints
    G.extend([
        nutritional_supply[0] - ((dmi_hi + epsilon) * nutrient_targets[0]),   # DMI max
        ((dmi_lo - epsilon) * nutrient_targets[0]) - nutritional_supply[0]    # DMI min
    ])
    scales.extend([nutrient_targets[0], nutrient_targets[0]])
    constraint_names.extend(["DMI_max", "DMI_min"])
    
    # Energy constraints 
    E_req = 0.95 * nutrient_targets[1]  # Hard minimum (no offset)
    E_tgt = nutrient_targets[1] + energy_offset  # For max constraint only
    if apply_offset_on_max:
        # Allow more energy surplus to avoid false infeasibilities
        G.append(nutritional_supply[1] - (1.20 + epsilon) * E_tgt)   
        scales.append(E_tgt)
        constraint_names.append("Energy_max")
    G.append((E_req - epsilon) - nutritional_supply[1])    # Energy_min (no offset)
    scales.append(E_req)
    constraint_names.append("Energy_min")
    
    # Protein constraints  
    MP_req = 0.95 * nutrient_targets[2]  # Hard minimum (no offset)
    MP_tgt = nutrient_targets[2] + mp_offset  # For max constraint only
    if apply_offset_on_max:
        # Allow more protein surplus to avoid expensive protein waste penalties
        G.append(nutritional_supply[2] - (1.20 + epsilon) * MP_tgt)  # max 
        scales.append(MP_tgt)
        constraint_names.append("MP_max")
    G.append((MP_req - epsilon) - nutritional_supply[2])      # MP_min (no offset)
    scales.append(MP_req)
    constraint_names.append("MP_min")
    
    # Mineral constraints 
    G.extend([
        nutrient_targets[3] - nutritional_supply[3],  # Min Calcium
        nutrient_targets[4] - nutritional_supply[4]   # Min Phosphorus
    ])
    scales.extend([nutrient_targets[3], nutrient_targets[4]])
    constraint_names.extend(["Ca_min", "P_min"])
    
    # Nutrient limits 
    G.extend([
        nutritional_supply[5] - (nutrient_targets[5] + epsilon),  # Max NDF
        (nutrient_targets[6] - epsilon) - nutritional_supply[6],  # Min NDF from forage
        nutritional_supply[7] - (nutrient_targets[7] + epsilon),  # Max Starch
        nutritional_supply[8] - (nutrient_targets[8] + epsilon)   # Max EE
    ])
    scales.extend([nutrient_targets[5], nutrient_targets[6], nutrient_targets[7], nutrient_targets[8]])
    constraint_names.extend(["NDF_max", "NDFfor_min", "Starch_max", "EE_max"])
    
    # Conditional ingredient-specific constraints
    # enforce level for the sum of the ingredients, not individual ingredients
    
    # Straw/Stover constraints          MAX
    if categories['has_straw']:
        straw_amount = np.sum(x[categories['mask_straw']])
        straw_limit = thr["forage_straw_max"] * Trg_Dt_DMIn
        G.append(straw_amount - straw_limit)
        scales.append(straw_limit)
        constraint_names.append("Straw_max")
    
    # Moist forage minimum constraint (DM < 80%)          MIN
    if categories['has_moist_forage'] and "moist_forage_min" in thr:
        moist_forage_amount = np.sum(x[categories['mask_moist_forage']])
        moist_forage_requirement = thr["moist_forage_min"] * Trg_Dt_DMIn
        G.append(moist_forage_requirement - moist_forage_amount)  
        scales.append(moist_forage_requirement)
        constraint_names.append("MoistForage_min")
    
    # Low-quality fibrous forage constraints          MAX
    if categories['has_lqf']:
        lqf_amount = np.sum(x[categories['mask_lqf']])
        lqf_limit = thr["forage_fibrous_max"] * Trg_Dt_DMIn
        G.append(lqf_amount - lqf_limit)
        scales.append(lqf_limit)
        constraint_names.append("LQF_max")
    
    # By-product concentrate constraints          MAX
    if categories['has_wet_byprod']:
        byprod_amount = np.sum(x[categories['mask_wet_byprod']])
        byprod_limit = thr["conc_byprod_max"] * Trg_Dt_DMIn
        G.append(byprod_amount - byprod_limit)
        scales.append(byprod_limit)
        constraint_names.append("Byprod_max")
    
    # Wet other ingredients constraints          MAX
    if categories['has_wet_other']:
        wet_other_amount = np.sum(x[categories['mask_wet_other']])
        wet_other_limit = thr["other_wet_ingr_max"] * Trg_Dt_DMIn
        G.append(wet_other_amount - wet_other_limit)
        scales.append(wet_other_limit)
        constraint_names.append("WetOther_max")
    
    total_dmi = nutritional_supply[0]

    #Build masks if they aren't provided by categories
    if 'mask_conc_all' in categories:
        mask_conc_all = categories['mask_conc_all']
    else:
        fd_type_lower = np.char.strip(np.char.lower(np.array(f_nd["Fd_Type"], dtype=str)))
        # treat "minerals" separately so they don't count as concentrate mass
        mask_conc_all = (fd_type_lower == "concentrate")

    conc_kg = np.sum(x[mask_conc_all])   if np.any(mask_conc_all)   else 0.0

    if "conc_max" in thr and total_dmi > 0:
        G.append(conc_kg - (thr["conc_max"] * total_dmi))
        scales.append(max(thr["conc_max"] * max(total_dmi, 1e-6), 1e-3))
        constraint_names.append("Conc_max")

    
    # Central classification handled elsewhere
    return G, scales, constraint_names


def evaluate_constraint_adequacy(actual, target, constraint_key, animal_requirements, constraint_name, units=""):
    """Evaluate constraint using CONSTRAINT_TOLERANCE_RANGES logic for adequacy display"""
    animal_type = animal_requirements.get("An_StatePhys", "Lactating Cow")
    tolerance_ranges = CONSTRAINT_TOLERANCE_RANGES.get(animal_type, {})
    
    if constraint_key not in tolerance_ranges:
        return None
        
    config = tolerance_ranges[constraint_key]
    basis = config.get("basis", "target")
    tolerance_type = config.get("tolerance_type", "both")
    
    # Calculate deviation percentage based on basis type
    if basis == "target":
        if tolerance_type == "minimum":
            # Only check if below target (shortfall)
            deviation_pct = ((target - actual) / max(target, 1e-12) * 100.0) if actual < target else 0.0
        elif tolerance_type == "both":
            # Check deviation in either direction
            deviation_pct = abs((actual - target) / max(target, 1e-12) * 100.0)
        else:
            deviation_pct = abs((actual - target) / max(target, 1e-12) * 100.0)
    else:  # basis == "limit"
        # Only check excess above limit
        deviation_pct = ((actual - target) / max(target, 1e-12) * 100.0) if actual > target else 0.0
    
    # Determine severity level
    severity = "infeasible"
    for level in ["perfect", "good", "marginal", "infeasible"]:
        if level in config:
            lo, hi = config[level]
            if level == "perfect":
                if (deviation_pct + 1e-9) >= lo and (deviation_pct - 1e-9) <= hi:
                    severity = level
                    break
            else:
                if lo <= deviation_pct + 1e-9 < hi + 1e-9:
                    severity = level
                    break
    
    # Determine status icon and adequacy percentage
    is_violated = severity in ["marginal", "infeasible"]
    status = "⚠️" if is_violated else "✓"
    
    adequacy_pct = 100.0 * actual / max(target, 1e-12)
    
    # Determine constraint type description
    if basis == "target":
        if tolerance_type == "minimum":
            type_desc = f"(supply {actual:.2f} / REQ {target:.2f} {units})"
        else:
            type_desc = f"(supply {actual:.2f} / REQ {target:.2f} {units})"
    else:  # basis == "limit"
        type_desc = f"(supply {actual:.2f} / LIMIT {target:.2f} {units})"
    
    return f"{status} {adequacy_pct:.1f}% {severity.upper()} {type_desc}"


def ca_constraint_name(name: str, format_type: str = "canonical", severity=None, deviation_percent=None) -> str:
    # constraint name function - handles all constraint name operations
    if not name:
        return ""
    
    # Normalize input: lowercase, replace spaces/hyphens with underscores
    normalized_name = str(name).strip().lower().replace(" ", "_").replace("-", "_")
    
    # Find canonical key and config
    canonical_key = None
    constraint_config = None
    
    # Search through all constraint configs in all animal types for aliases
    for animal_type, constraints in CONSTRAINT_TOLERANCE_RANGES.items():
        for key, config in constraints.items():
            # Check if it's already the canonical key
            if normalized_name == key:
                canonical_key = key
                constraint_config = config
                break
            
            # Check aliases if they exist
            aliases = config.get("aliases", [])
            for alias in aliases:
                alias_normalized = alias.strip().lower().replace(" ", "_").replace("-", "_")
                if normalized_name == alias_normalized:
                    canonical_key = key
                    constraint_config = config
                    break
            
            if canonical_key:
                break
        if canonical_key:
            break
    
    # If not found, use normalized name
    if not canonical_key:
        canonical_key = normalized_name
    
    # Get base display value based on format_type
    if format_type == "canonical":
        display_value = canonical_key
    elif format_type == "clean_display" and constraint_config:
        # Get display name and remove common suffixes
        display_name = constraint_config.get("display_name", canonical_key)
        suffixes_to_remove = [
            " (Minimum)", " (Maximum)", " (Min)", " (Max)",
            " Requirement", " Content"
        ]
        for suffix in suffixes_to_remove:
            if display_name.endswith(suffix):
                display_name = display_name[:-len(suffix)]
                break
        display_value = display_name
    elif constraint_config and format_type in constraint_config:
        display_value = constraint_config[format_type]
    elif constraint_config and format_type == "display_name":
        # Fallback to display_name if available
        display_value = constraint_config.get("display_name", canonical_key)
    else:
        # Fallback to canonical key
        display_value = canonical_key
    
    # Add severity and deviation if provided 
    if severity and deviation_percent is not None:
        return f"{display_value} ({severity}, {deviation_percent:.1f}% dev)"
    elif severity:
        return f"{display_value} ({severity})"
    else:
        return display_value

# --- Uniform messaging utility ----------------------------------------------
# --- Cleaning -------------------------------------------------------------

CONSTRAINT_META = {
    # Core constraints - only 'type' field needed
    "dmi":                 {"type": "both"},
    "moist_forage_min":    {"type": "min"},
    "energy":              {"type": "both"},
    "protein":             {"type": "both"},
    "ca":                  {"type": "min"},
    "p":                   {"type": "min"},
    "ndf_for":             {"type": "min"},
    "forage_straw_max":    {"type": "max"},
    "forage_fibrous_max":  {"type": "max"},
    "starch":              {"type": "max"},
    "conc_max":            {"type": "max"},
    "conc_byprod_max":     {"type": "max"},
    "fat":                 {"type": "max"},
    "ndf":                 {"type": "max"},
    "other_wet_ingr_max":  {"type": "max"},
    "mineral_min":         {"type": "min"},
    "mineral_max":         {"type": "max"},
    "urea_max":            {"type": "max"},
    "forage_wet_max":      {"type": "max"},
}

# --- Which constraint/direction should be COUNTED toward marginal / infeasible totals
#   min/both: count UNDER for marginal/infeasible
#   max:      count OVER  for marginal/infeasible
COUNT_OVERRIDES = {
    # CRITICALS
    "dmi":              {"marg_under": True,  "marg_over": True,  "inf_under": True,  "inf_over": True},
    "energy":           {"marg_under": True,  "marg_over": False, "inf_under": True,  "inf_over": True},   # NEL: marginal+ = OK (warn), marginal- = counts
    "protein":          {"marg_under": True,  "marg_over": False, "inf_under": True,  "inf_over": True},   # MP:  marginal+ = OK (warn), marginal- = counts

    # MINERALS (ok if over; only under should count)
    "ca":               {"marg_under": False, "marg_over": False, "inf_under": True,  "inf_over": False},
    "p":                {"marg_under": False, "marg_over": False, "inf_under": True,  "inf_over": False},

    # STRUCTURAL FIBER MINIMUM
    "ndf_for":          {"marg_under": False, "marg_over": False, "inf_under": True,  "inf_over": False},

    # TOTAL FIBER MAX (over = OK-with-warning at marginal; only infeasible over counts)
    "ndf":              {"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},

    # RAPID CARBS / FAT / CONCENTRATE CAPS (over = OK-with-warning at marginal; still counts when infeasible)
    "starch":           {"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},
    "fat":              {"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},
    "conc_max":         {"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},
    "conc_byprod_max":  {"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},
    "other_wet_ingr_max":{"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},
    "forage_straw_max": {"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},
    "forage_fibrous_max":{"marg_under": False, "marg_over": False, "inf_under": False, "inf_over": True},

    # MOIST FORAGE MIN (only severe under should fail; marginal under = OK with warning)
    "moist_forage_min": {"marg_under": False, "marg_over": False, "inf_under": True,  "inf_over": False},
}

def _constraint_type(cname: str) -> str:
    #Get constraint type: 'min' | 'max' | 'both' (from CONSTRAINT_META)
    return CONSTRAINT_META.get(cname, {}).get("type", "both")

def _counts_as_marginal(cname: str, ce) -> bool:

    if ce.status_band != "marginal":
        return False
    t = _constraint_type(cname)
    dirn = ce.direction  # "over"|"under"|"within"
    ov = COUNT_OVERRIDES.get(cname, {})
    if t in ("min", "both") and dirn == "under":
        return ov.get("marg_under", True)   # default True
    if t in ("max", "both") and dirn == "over":
        return ov.get("marg_over", True)    # default True
    return False

def _counts_as_infeasible(cname: str, ce) -> bool:
    if ce.status_band != "infeasible":
        return False
    t = _constraint_type(cname)
    dirn = ce.direction
    ov = COUNT_OVERRIDES.get(cname, {})
    if t in ("min", "both") and dirn == "under":
        return ov.get("inf_under", True)    # default True
    if t in ("max", "both") and dirn == "over":
        return ov.get("inf_over", True)     # default True
    # If it's infeasible but direction doesn't match the type (rare), don't count.
    return False
 
# Presentation knobs 

PRESENTATION = {
    "max_crit": 4,     # show at most this many critical lines
    "max_actions": 4,  # show at most this many actions
}

CRITICAL_REQS = {"protein", "energy", "dmi", "ndf_for"}


@dataclass
class ConstraintEval:
    status_band: str       # "perfect"|"good"|"marginal"|"infeasible"
    direction: str         # "over"|"under"|"within"
    norm_distance: float   # 0.0..1.0 scaled by band span
    raw_deviation: float   # % deviation (+/-)


def _compute_signed_deviation(actual, target, constraint_key):
    """
    Compute signed deviation percentage.
    
    Parameters:
    -----------
    actual : float
        Actual value supplied
    target : float
        Target/requirement value
    constraint_key : str
        Constraint identifier (for future use)
    
    Returns:
    --------
    float : Signed percentage deviation
            Positive = above target/limit
            Negative = below target/limit
    """
    # All constraint types use the same formula: (actual - target) / target * 100
    # Semantics: positive = above target/limit, negative = below target/limit
    return ((actual - target) / max(target, 1e-12)) * 100.0

def _set_deviation(deviations_dict, key, value):
    """
    Set deviation with canonical constraint name.
    
    Parameters:
    -----------
    deviations_dict : dict
        Dictionary to store deviations
    key : str
        Constraint key
    value : float
        Deviation value to store
    """
    canonical_key = ca_constraint_name(key)
    deviations_dict[canonical_key] = float(value)

def pick_band_and_distance(constraint_name: str, pct_dev: float, ranges: dict) -> ConstraintEval:
    """
    pct_dev: signed percent deviation relative to target/limit.
      - For max-type: positive means 'over limit' (bad), negative 'under' (fine).
      - For min-type: negative means 'under target' (bad), positive 'over' (fine).
      - For both-type: +/- both can be bad depending on distance.
    """
    if constraint_name not in CONSTRAINT_META:
        return ConstraintEval("perfect", "within", 0.0, float(pct_dev))
        
    if constraint_name not in ranges:
        return ConstraintEval("perfect", "within", 0.0, float(pct_dev))
        
    info = ranges[constraint_name]
    basis = info["basis"]
    tol_type = (info.get("tolerance_type") or "").lower()
    is_min = tol_type in ("min", "minimum")

    def band_tuple(name): 
        if name not in info:
            return (0.0, 100.0)
        return tuple(info[name])

    # Decide "direction" and effective |distance|
    if basis == "limit":  # max-type
        direction = "over" if pct_dev > 0 else "within"
        magnitude = max(0.0, pct_dev)
    else:  # "target"
        if is_min:
            direction = "under" if pct_dev < 0 else "within"
            magnitude = max(0.0, -pct_dev)
        else:  # "both"
            direction = "over" if pct_dev > 0 else ("under" if pct_dev < 0 else "within")
            magnitude = abs(pct_dev)

    # Place magnitude into band
    for band in ("perfect", "good", "marginal", "infeasible"):
        lo, hi = band_tuple(band)
        if lo <= magnitude < hi:
            span = max(1e-9, hi - lo)
            norm = (magnitude - lo) / span
            return ConstraintEval(band, direction, float(norm), float(pct_dev))

    # Edge-case: very large → infeasible cap
    lo, hi = band_tuple("infeasible")
    span = max(1e-9, hi - lo)
    norm = min(1.0, (magnitude - lo) / span)
    return ConstraintEval("infeasible", direction, float(norm), float(pct_dev))


def extract_constraint_deviations(diet_summary_values, intermediate_results_values, animal_requirements, f_nd, best_q=None, categories=None):
    """
    Extract signed percent deviations from existing adequacy evaluation system.
    This leverages the existing evaluate_constraint_adequacy() function to avoid code duplication.
    Returns a dict of {constraint_name: signed_percent_deviation}
    """
    if diet_summary_values is None or intermediate_results_values is None:
        return {}
    
    # Handle numpy arrays - check if they're empty
    if hasattr(diet_summary_values, '__len__') and len(diet_summary_values) == 0:
        return {}
    if hasattr(intermediate_results_values, '__len__') and len(intermediate_results_values) == 0:
        return {}
    
    # Get animal type and constraints (same method as adequacy analysis)
    animal_type = animal_requirements.get("An_StatePhys", "Lactating Cow")
    # Use the same Constraints as defined in this file (app.py), not constraints.py
    thr = Constraints[animal_type]  # Use local Constraints definition
    tolerance_ranges = CONSTRAINT_TOLERANCE_RANGES.get(animal_type, {})
    
    # Get requirements
    dmi_req = float(animal_requirements["Trg_Dt_DMIn"])
    st = animal_requirements.get("An_StatePhys", "").strip().lower()
    is_heifer = "heifer" in st
    energy_req = float(animal_requirements["An_ME"] if is_heifer else animal_requirements["An_NEL"])
    protein_req = float(intermediate_results_values[2])  # MP requirement
    ca_req = float(animal_requirements.get("An_Ca_req", 0.0))
    p_req = float(animal_requirements.get("An_P_req", 0.0))
    
    # Get actual values from diet
    dmi_supply, energy_supply, protein_supply, ca_supply, p_supply, ndf_supply, ndffor_supply, starch_supply, ee_supply = map(float, diet_summary_values[:9])
    
    deviations = {}
    
    # Core nutritional constraints
    _set_deviation(deviations, "dmi", _compute_signed_deviation(dmi_supply, dmi_req, "dmi"))
    _set_deviation(deviations, "energy", _compute_signed_deviation(energy_supply, energy_req, "energy"))
    _set_deviation(deviations, "protein", _compute_signed_deviation(protein_supply, protein_req, "protein"))
    
    # Minerals
    if ca_req > 0:
        _set_deviation(deviations, "ca", _compute_signed_deviation(ca_supply, ca_req, "ca"))
    if p_req > 0:
        _set_deviation(deviations, "p", _compute_signed_deviation(p_supply, p_req, "p"))
    
    # Fiber constraints
    ndffor_min = thr["ndf_for"] * dmi_req
    ndf_limit = thr["ndf"] * dmi_req
    
    # Debug NDF calculation
    ndf_deviation = _compute_signed_deviation(ndf_supply, ndf_limit, "ndf")
    
    _set_deviation(deviations, "ndf_for", _compute_signed_deviation(ndffor_supply, ndffor_min, "ndf_for"))
    _set_deviation(deviations, "ndf", ndf_deviation)
    
    # Nutrient limits
    starch_limit = thr.get("starch_max", float('inf')) * dmi_req
    ee_limit = thr.get("ee_max", float('inf')) * dmi_req
    if starch_limit < float('inf'):
        _set_deviation(deviations, "starch", _compute_signed_deviation(starch_supply, starch_limit, "starch"))
    if ee_limit < float('inf'):
        _set_deviation(deviations, "fat", _compute_signed_deviation(ee_supply, ee_limit, "fat"))
    
    # Ingredient-specific constraints (if available)
    if best_q is not None and len(best_q) > 0 and categories is not None:
        total_dmi = dmi_supply
        
        # Concentrate constraint
        if 'mask_conc_all' in categories and np.any(categories['mask_conc_all']):
            conc_kg = float(np.sum(best_q[categories['mask_conc_all']]))
            conc_limit = thr.get("conc_max", 0.6) * total_dmi
            _set_deviation(deviations, "conc_max", _compute_signed_deviation(conc_kg, conc_limit, "conc_max"))
        
        # Moist forage minimum - use canonical constraint name in thr.get()
        if 'mask_moist_forage' in categories:
            moist_forage_supply = float(np.sum(best_q[categories['mask_moist_forage']])) if np.any(categories['mask_moist_forage']) else 0.0
            moist_forage_requirement = thr.get("moist_forage_min", 0.4) * dmi_req
            _set_deviation(deviations, "moist_forage_min", _compute_signed_deviation(moist_forage_supply, moist_forage_requirement, "moist_forage_min"))
    
    return deviations


ACTION_TEMPLATES = {
    # Intake (cannot change target; make diet denser / less bulky)
    "dmi": {
        "under": [
            "Swap to more digestible forages; reduce straw/low-quality fibrous forages."
        ],
        "over": [
            "Increase nutrient density: replace some forage with concentrates."
        ],
    },
    "energy": {
        "under": [
            "Add high-energy concentrates (e.g., corn/barley)."
        ],
        "over": [
            "Reduce cereal grains; or add fibrous by-products/forage.",
        ],
    },
    "protein": {
        "under": [
            "Add true-protein meals (e.g., soybean meal)."
        ],
        "over": [
            "Trim protein supplements; replace with energy sources.",
        ],
    },

    # Minerals (min-type)
    "ca": {"under": ["Increase mineral premix."]},
    "p":  {"under": ["Increase mineral premix."]},

    # Structure & total fiber
    "ndf_for": {
        "under": [
            "Add forage ingredients (hay/silage)."
        ]
    },
    "ndf": {  # max-type
        "over": [
            "Dilute fiber: reduce straw/low-quality fibrous forages; replace with higher-energy forage or concentrates."
        ]
    },

    # Rapid carbs / fat / concentrate caps (max-type)
    "starch": {
        "over": [
            "Cut cereal grains; use digestible fiber sources to dilute starch."
        ]
    },
    "fat": {
        "over": [
            "Reduce high-fat ingredients (oils/whole oilseeds/bypass fat)."
        ]
    },
    "conc_max": {
        "over": [
            "Lower total concentrates; replace with high-quality forage."
        ]
    },
    "conc_byprod_max": {
        "over": [
            "Reduce wet by-products; shift to dry concentrates or forage."
        ]
    },
    "other_wet_ingr_max": {
        "over": [
            "Reduce wet non-forage ingredients; replace with dry concentrates/forage."
        ]
    },
    "forage_straw_max": {
        "over": [
            "Cut straw; use moderate-NDF forage for structure instead."
        ]
    },
    "forage_fibrous_max": {
        "over": [
            "Replace low-quality fibrous forage with higher-quality forage."
        ]
    },

    # Moist forage minimum (min-type)
    "moist_forage_min": {
        "under": [
            "Add moist forages (e.g., silage/pasture)."
        ]
    },

    # Safety / specials
    "urea_max": {
        "over": [
            "Reduce urea/NPN; supply true protein sources instead."
        ]
    },
}
# --- Context-aware helpers ---
def _is_over(evals, key):
    ce = evals.get(key)
    return bool(ce and ce.status_band in ("marginal", "infeasible") and ce.direction == "over")

def _is_under(evals, key):
    ce = evals.get(key)
    return bool(ce and ce.status_band in ("marginal", "infeasible") and ce.direction == "under")

def _append_actions_for_constraint(actions, cname, ce, evals):
    """Use ACTION_TEMPLATES to add brief, direction-aware actions with context awareness."""
    tmpl = ACTION_TEMPLATES.get(cname, {})
    dirn = ce.direction if ce.direction in ("over","under") else None
    if not dirn or dirn not in tmpl:
        return

    items = list(tmpl[dirn])

    # 1) DMI short + concentrates already high  → forage-first density (no "add concentrates")
    if cname == "dmi" and dirn == "under" and _is_over(evals, "conc_max"):
        items = [
            "Raise forage energy density (corn silage/high-digestibility forage).",
            "Free space for forage: trim cereal grains; add long-fiber forage to restore structure.",
            "Maintain energy with fibrous by-products, not more grain."
        ]

    # 2) Protein over + energy over  → don't say "replace with energy"
    if cname == "protein" and dirn == "over" and _is_over(evals, "energy"):
        items = [s.replace("replace with energy sources",
                           "replace with forage or fibrous by-products")
                 for s in items]

    # 3) Energy under + conc_max over  → prefer higher-NEL forage (avoid "add concentrates")
    if cname == "energy" and dirn == "under" and _is_over(evals, "conc_max"):
        items = ["Prefer higher-NEL forage (corn silage) over adding more concentrates."]

    actions.extend(items)

def _resolve_action_conflicts(actions, evals):
    """Resolve cross-constraint conflicts after deduplication."""
    energy_over = _is_over(evals, "energy")
    conc_over   = _is_over(evals, "conc_max")
    dmi_under   = _is_under(evals, "dmi")

    resolved = []
    for a in actions:
        # If concentrates are already high, drop any explicit "Add high-energy concentrates"
        if conc_over and "Add high-energy concentrates" in a:
            continue
        # If energy is already high, drop "replace with energy sources"
        if energy_over and "replace with energy sources" in a:
            continue
        resolved.append(a)

    # Tiny phrasing cleanups
    resolved = [a.replace("Reduce cereal grains; or", "Reduce cereal grains;") for a in resolved]
    return resolved
