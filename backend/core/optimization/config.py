"""
Configuration constants for diet optimization.

This module contains all global configuration constants used throughout
the optimization system, including:
- Constraint limits and thresholds
- Tolerance ranges for constraint evaluation
- Animal type-specific parameters
"""

# ===================================================================
# GLOBAL CONSTANTS AND CONFIGURATIONS
# ===================================================================

# Constraints for optimization 
Constraints = {
    "Lactating Cow": {
        # Constraints for constraints (build_conditional constraints)
        # Max constraints
        # Forage
        "forage_straw_max":       0.25,      # Max straw as fraction of total forage DM
        "forage_fibrous_max":     0.80,      # Max fibrous forages as fraction of total forage DM
        "ndf":                    0.60,      # Max NDF as fraction of diet DM
        "ndf_for":                0.20,      # Min forage NDF as fraction of diet DM
        # Concentrate
        "conc_max":               0.60,      # Max concentrate as fraction of diet DM
        "starch_max":             0.26,      # Max starch as fraction of diet DM
        "ee_max":                 0.07,      # Max ether extract (fat) as fraction of diet DM
        "conc_byprod_max":        0.30,      # Max by-product in concentrate as fraction of diet DM
        # Other feeds
        "other_wet_ingr_max":     0.30,      # Max other wet ingredients as fraction of diet DM
        # Min constraints
        "moist_forage_min":       0.20,      # Min forages with DM < 80% as fraction of total diet DM

        # Constraint for bounds (bounds_xlxu)

        "urea_max":               0.01,       # Max urea as fraction of diet DM (1% safety limit)
        # Mineral constraints
        "mineral_min":            0.050,     # Min mineral intake in kg per day
        "mineral_max":            0.800      # Max mineral intake in kg per day
    }
}

CONSTRAINT_TOLERANCE_RANGES = {
    "Lactating Cow": {
        # CORE NUTRITIONAL CONSTRAINTS (min-type vs TARGET)
        "dmi": {
            "basis": "target",
            "tolerance_type": "both",
            "display_name": "Dry Matter Intake",
            "short_name": "DMI",
            "unit": "kg/day",
            "aliases": ["DMI_min", "DMI_max", "dmi_min", "dmi_max"],
            "perfect": (0, 5),        # 0-5% deviation = PERFECT
            "good": (5, 8),          # 5-8% deviation = GOOD  
            "marginal": (8, 15),     # 8-15% deviation = MARGINAL
            "infeasible": (15, 100)   # >20% deviation = INFEASIBLE
        },
        "energy": {
            "basis": "target",
            "tolerance_type": "both",
            "display_name": "Energy Requirement",
            "short_name": "Energy",
            "unit": "Mcal/day",
            "aliases": ["Energy_min", "Energy_max", "energy_min", "energy_max"],
            "perfect": (0, 5),        # 0-5% deviation = PERFECT (95-105% of target)
            "good": (5, 10),          # 5-10% deviation = GOOD (90-95% or 105-110% of target)  
            "marginal": (10, 20),     # 10-20% deviation = MARGINAL (80-90% or 110-120% of target)
            "infeasible": (20, 100)   # >20% deviation = INFEASIBLE (<80% or >120% of target)
        },
        "protein": {
            "basis": "target",
            "tolerance_type": "both",
            "display_name": "Metabolizable Protein",
            "short_name": "Protein",
            "unit": "kg/day",
            "aliases": ["MP_min", "MP_max", "protein_min", "protein_max", "mp_max", "mp_min"],
            "perfect": (0, 5),        # 0-5% deviation = PERFECT (95-105% of target)
            "good": (5, 10),          # 5-10% deviation = GOOD (90-95% or 105-110% of target)
            "marginal": (10, 20),     # 10-20% deviation = MARGINAL (80-90% or 110-120% of target)
            "infeasible": (20, 100)   # >20% deviation = INFEASIBLE (<80% or >120% of target)
        },
        "ca": {
            "basis": "target",
            "tolerance_type": "minimum",
            "display_name": "Calcium Requirement",
            "short_name": "Calcium",
            "unit": "kg/day",
            "aliases": ["Ca_min", "ca_min", "calcium"],
            "perfect": (0, 6),        # Minerals more tolerant
            "good": (6, 12),
            "marginal": (12, 25),
            "infeasible": (25, 100)
        },
        "p": {
            "basis": "target",
            "tolerance_type": "minimum",
            "display_name": "Phosphorus Requirement",
            "short_name": "Phosphorus",
            "unit": "kg/day",
            "aliases": ["P_min", "p_min", "phosphorus"],
            "perfect": (0, 6),
            "good": (6, 12),
            "marginal": (12, 25),
            "infeasible": (25, 100)
        },
        "ndf_for": {
            "basis": "target",
            "tolerance_type": "minimum",
            "display_name": "Forage Fiber (NDF)",
            "short_name": "Forage NDF",
            "unit": "kg/day",
            "aliases": ["NDFfor_min", "ndf_for_min", "forage_ndf"],
            "perfect": (0, 5),        # Fiber structure critical
            "good": (5, 10),
            "marginal": (10, 25),
            "infeasible": (25, 100)
        },
        
        # NUTRITIONAL LIMITS (max-type vs LIMIT) - handle excesses
        "ndf": {
            "basis": "limit",
            "display_name": "Total Fiber (NDF)",
            "short_name": "Total NDF",
            "unit": "kg/day",
            "aliases": ["NDF_max", "ndf_max"],
            "perfect": (0, 2.5),      # Generally tolerable
            "good": (2.5, 5),
            "marginal": (5, 15),      
            "infeasible": (15, 1e9)   # Add energy filler for dilution
        },
        "starch": {
            "basis": "limit",
            "display_name": "Starch Content",
            "short_name": "Starch",
            "unit": "kg/day",
            "aliases": ["Starch_max", "starch_max"],
            "perfect": (0, 2.5),
            "good": (2.5, 5),
            "marginal": (5, 10),      # Risk of acidosis
            "infeasible": (10, 1e9)
        },
        "fat": {  # ether extract (EE)
            "basis": "limit",
            "display_name": "Fat Content",
            "short_name": "Fat",
            "unit": "kg/day",
            "aliases": ["EE_max", "fat_max", "ee_max"],
            "perfect": (0, 2.5),
            "good": (2.5, 5),
            "marginal": (5, 10),      # Fat tolerance higher
            "infeasible": (10, 1e9)
        },
        
        # INGREDIENT CATEGORY CAPS (max-type vs LIMIT)
        "conc_max": {
            "basis": "limit",
            "display_name": "Total Concentrates",
            "short_name": "Concentrates",
            "unit": "kg/day",
            "aliases": ["Conc_max", "concentrate"],
            "perfect": (0, 5),        # Concentrate maximum
            "good": (5, 7),
            "marginal": (7, 10),
            "infeasible": (10, 1e9)
        },
        "conc_byprod_max": {
            "basis": "limit",
            "display_name": "By-Product Concentrates",
            "short_name": "By-Products",
            "unit": "kg/day",
            "aliases": ["Byprod_max", "by_product"],
            "perfect": (0, 2),        # Concentrate by-products
            "good": (2, 5),
            "marginal": (5, 10),
            "infeasible": (10, 1e9)
        },
        "other_wet_ingr_max": {
            "basis": "limit",
            "display_name": "Wet Ingredients",
            "short_name": "Wet Ingredients",
            "unit": "kg/day",
            "aliases": ["WetOther_max", "wet_other"],
            "perfect": (0, 2),        # Other wet ingredients
            "good": (2, 5),
            "marginal": (5, 10),
            "infeasible": (10, 1e9)
        },
        "forage_straw_max": {
            "basis": "limit",
            "display_name": "Straw/Stover Content",
            "short_name": "Straw",
            "unit": "kg/day",
            "aliases": ["Straw_max", "straw"],
            "perfect": (0, 1e-9),        # Straw: no slack for perfect
            "good": (1e-9, 2),
            "marginal": (2, 5),
            "infeasible": (5, 1e9)
        },
        "forage_fibrous_max": {
            "basis": "limit",
            "display_name": "Low-Quality Forage",
            "short_name": "Low-Quality Forage",
            "unit": "kg/day",
            "aliases": ["LQF_max", "fibrous_forage"],
            "perfect": (0, 1e-9),        # Low-quality forage: no slack for perfect
            "good": (1e-9, 2),
            "marginal": (2, 5),
            "infeasible": (5, 1e9)
        },
        
        # FORAGE MINIMUMS (min-type vs TARGET)
        "moist_forage_min": {
            "basis": "target",
            "tolerance_type": "minimum",
            "display_name": "Fresh Forage",
            "short_name": "Fresh Forage",
            "unit": "kg/day",
            "aliases": ["MoistForage_min", "moist_forage", "wet_forage_min"],
            "perfect": (0, 5),        # Allow minor shortfall for perfect
            "good": (5, 10),
            "marginal": (10, 20),
            "infeasible": (20, 100)
        }
    }
}

