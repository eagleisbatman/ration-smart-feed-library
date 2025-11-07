"""
Diet Recommendation New - API-specific functions
This file contains functions specifically adapted for the API needs,
extracted and modified from diet_recommendation.py
"""

import pandas as pd
import numpy as np
import warnings
import time
import multiprocessing
import random
from itertools import combinations
from pathlib import Path
import os
from pymoo.core.problem import Problem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.problems import get_problem
from pymoo.optimize import minimize
from pymoo.core.evaluator import Evaluator
from pymoo.visualization.scatter import Scatter
from pymoo.termination import get_termination
from pymoo.operators.crossover.sbx import SimulatedBinaryCrossover
from pymoo.operators.mutation.pm import PolynomialMutation
from pymoo.core.sampling import Sampling             
from pymoo.operators.sampling.rnd import FloatRandomSampling
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings('ignore')

def calculate_methane_emissions(Dt, Dt_DMInSum, f_nd, animal_requirements, best_solution_vector):
    """
    Calculate methane emissions
    """
    An_StatePhys = animal_requirements["An_StatePhys"]
    
    # Calculate diet composition values
    EE_diet = sum(best_solution_vector * (f_nd["Fd_EE"]/100)) / Dt_DMInSum * 100
    FA_diet = sum(best_solution_vector * (f_nd["Fd_FA"]/100)) / Dt_DMInSum * 100
    NDF_diet = sum(best_solution_vector * (f_nd["Fd_NDF"]/100)) / Dt_DMInSum * 100
    
    GE_diet = (f_nd["Fd_GE"] * best_solution_vector).sum()  # Mcal/d
   
    # Calculate Methane in g/d
    if An_StatePhys == "Lactating Cow":
        CH4 = (76.0 + 13.5 * Dt_DMInSum - 9.55 * EE_diet + 2.24 * NDF_diet)
    elif An_StatePhys == "Dry Cow":
        CH4 = (0.69 + 0.053 * GE_diet - 0.0789 * FA_diet) * 4184 / 55.5
    elif An_StatePhys == "Heifer":
        CH4 = (-0.038 + 0.051 * GE_diet - 0.0091 * NDF_diet) * 4184 / 55.5
    else:
        CH4 = 0  # Default for unknown animal types

    # Methane metrics
    CH4_MJ = CH4 * 55.5/1000  # convert from g to MJ
    GE_MJ = GE_diet * 4.184   # convert from Mcal to MJ
    CH4_grams_per_kg_DMI = CH4 / Dt_DMInSum if Dt_DMInSum > 0 else 0
    MCR = (CH4_MJ / GE_MJ) * 100 if GE_MJ > 0 else 0

    # Interpret MCR
    if MCR < 3.5:
        MCR_range = "Extremely Low"
    elif MCR < 4.5:
        MCR_range = "Very Low"
    elif MCR < 5.5:
        MCR_range = "Low"
    elif MCR < 6.5:
        MCR_range = "Average"
    elif MCR < 7.5:
        MCR_range = "Average"
    elif MCR < 8.5:
        MCR_range = "Very High"
    elif MCR < 9.5:
        MCR_range = "Extremely High"
    else:
        MCR_range = "Above Normal Range"

    # Combine results into a DataFrame
    Methane_Report = pd.DataFrame({
        "Metric": [
            "Methane Emission (MJ/day)",
            "Methane Emission (grams/day)",
            "Methane Emission (grams/kg DMI)",
            "Methane Conversion Rate (%)",
            "MCR Range"
        ],
        "Value": [
            round(CH4_MJ, 2),
            round(CH4, 2),
            round(CH4_grams_per_kg_DMI, 2),
            round(MCR, 2),
            MCR_range
        ]
    })
    
    return Methane_Report
    
def create_proportions_dataframe(Dt, Dt_DMInSum):
    """
    Create proportions DataFrame with forage/concentrate separation
    """
    # Calculate Dt dataframe in % of DM
    Dt_proportions = Dt[['Ingr_Type', 'Ingr_Name', 'Intake_DM', 'Intake_AF', 'Dt_DMInp', 'Dt_AFInp', 'Ingr_Cost']].copy()

    # Calculate nutrient intake in %
    Col_names = [
       "Fd_ADF", "Fd_NDF", "Fd_Lg", "Fd_CP", "Fd_St", "Fd_EE", "Fd_FA", 
       "Fd_Ash", "Fd_NFC", "Fd_TDN", "Fd_Ca", "Fd_P"
    ]
    
    for nutrient in Col_names:
        if f"Dt_{nutrient[3:]}In" in Dt.columns:
            renamed_nutrient = rename_variable(nutrient)
            Dt_proportions[renamed_nutrient] = Dt[renamed_nutrient] / Dt_DMInSum * 100

    Dt_proportions = Dt_proportions.apply(replace_na_and_negatives)

    # Check if totals row already exists before adding
    if not (Dt_proportions['Ingr_Name'] == 'Total').any():
        # Add totals row only if it doesn't exist
        column_sums = Dt_proportions.select_dtypes(include=[np.number]).sum()
        Dt_proportions = pd.concat([Dt_proportions, pd.DataFrame([column_sums])], ignore_index=True)
        Dt_proportions.iloc[-1, Dt_proportions.columns.get_loc('Ingr_Name')] = 'Total'

    # Edit the Dt_proportions dataframe for report
    Dt_proportions = Dt_proportions.round(2).rename(columns={
        'Ingr_Type': 'Ingr_Type',
        'Ingr_Name': 'Name',
        'Intake_DM': 'DM_kg',
        'Intake_AF': 'AF_kg',
        'Dt_DMInp': 'DM_prop',
        'Dt_AFInp': 'AF_prop',
        'Ingr_Cost': 'Cost',
        'Dt_CPIn': 'CP',
        'Dt_NDFIn': 'NDF',
        'Dt_ADFIn': 'ADF',
        'Dt_LgIn': 'Lig',
        'Dt_StIn': 'St',
        'Dt_EEIn': 'EE',
        'Dt_FAIn': 'FA',
        'Dt_AshIn': 'Ash',
        'Dt_NFCIn': 'NFC',
        'Dt_TDNIn': 'TDN',
        'Dt_CaIn': 'Ca',
        'Dt_PIn': 'P'
    })

    # Fix total row NaN values
    total_row_index = Dt_proportions[Dt_proportions['Name'] == 'Total'].index
    if len(total_row_index) > 0:
        idx = total_row_index[0]
        # Replace NaN with empty string in Ingr_Type column
        Dt_proportions.loc[idx, 'Ingr_Type'] = ''
    
        # Replace NaN with calculated totals for nutrient columns
        numeric_cols = ['ADF', 'NDF', 'Lig', 'CP', 'St', 'EE', 'FA', 'Ash', 'NFC', 'TDN', 'Ca', 'P']
        for col in numeric_cols:
            if col in Dt_proportions.columns:
                col_total = Dt_proportions.loc[Dt_proportions['Name'] != 'Total', col].sum()
                Dt_proportions.loc[idx, col] = col_total
                
    # Filter and add a Total row for Forage
    Dt_forages = Dt_proportions[Dt_proportions['Ingr_Type'] == 'Forage'].copy()
    if not Dt_forages.empty:
        forage_total = Dt_forages.select_dtypes(include=[np.number]).sum()
        forage_total['Ingr_Type'] = 'Forage'
        forage_total['Name'] = 'Total'
        Dt_forages = pd.concat([Dt_forages, forage_total.to_frame().T], ignore_index=True)

    # Filter and add a Total row for Concentrate
    Dt_concentrates = Dt_proportions[(Dt_proportions['Ingr_Type'] == 'Concentrate') | 
                                     (Dt_proportions['Ingr_Type'] == 'Minerals')].copy()
    if not Dt_concentrates.empty:
        concentrate_total = Dt_concentrates.select_dtypes(include=[np.number]).sum()
        concentrate_total['Ingr_Type'] = 'Concentrate'
        concentrate_total['Name'] = 'Total'
        Dt_concentrates = pd.concat([Dt_concentrates, concentrate_total.to_frame().T], ignore_index=True)

    Dt_results = Dt_proportions[['Name', 'DM_kg', 'AF_kg', 'Cost']]
    
    return Dt_proportions, Dt_forages, Dt_concentrates, Dt_results



def create_animal_inputs_dataframe(animal_requirements):
    """
    Create Animal Inputs DataFrame
    """
    # Extract values with defaults for missing keys
    An_Breed = animal_requirements.get("An_Breed", "Unknown")
    An_StatePhys = animal_requirements.get("An_StatePhys", "Unknown")
    An_BW = animal_requirements.get("An_BW", 0)
    An_BCS = animal_requirements.get("An_BCS", 0)
    Trg_FrmGain = animal_requirements.get("Trg_FrmGain", 0)
    An_BW_mature = animal_requirements.get("An_BW_mature", 0)
    An_Parity = animal_requirements.get("An_Parity", 0)
    An_LactDay = animal_requirements.get("An_LactDay", 0)
    An_GestDay = animal_requirements.get("An_GestDay", 0)
    Env_TempCurr = animal_requirements.get("Env_TempCurr", 20)
    Env_Dist_km = animal_requirements.get("Env_Dist_km", 0)
    Env_Topo = animal_requirements.get("Env_Topo", 0)
    Trg_MilkProd_L = animal_requirements.get("Trg_MilkProd_L", 0)
    Trg_MilkTPp = animal_requirements.get("Trg_MilkTPp", 0)
    Trg_MilkFatp = animal_requirements.get("Trg_MilkFatp", 0)
    
    Animal_inputs = pd.DataFrame({
        "Parameter": [
            "Breed", "Animal Type", "Animal BW", "Body Condition Score",
            "Daily BW Gain", "Mature BW", "Parity", "Days in Milk", "Days of Pregnancy",
            "Current Temperature", "Distance Walked", "Topography", "Milk Production",
            "Milk True Protein Content", "Milk Fat Content"
        ],
        
        "Value": [
            An_Breed, An_StatePhys, An_BW, An_BCS, 
            Trg_FrmGain, An_BW_mature, An_Parity, An_LactDay, An_GestDay,
            Env_TempCurr, Env_Dist_km, Env_Topo, Trg_MilkProd_L,
            Trg_MilkTPp, Trg_MilkFatp
        ],
        
        "Unit": [
            "", "", "kg", "", "kg/day", "kg", "", "days", "days",
            "°C", "km", "m", "L", "%", "%"
        ]
    })
    
    return Animal_inputs


# Utility functions
def rename_variable(variable_name):
    """Rename variable from Fd_ prefix to Dt_ prefix with In suffix"""
    new_name = variable_name.replace("Fd_", "Dt_") + "In"
    return new_name

def replace_na_and_negatives(col):
    """Replace NaN and negative values with 0 in numeric columns"""
    if col.dtype.kind in 'biufc':  # Check if the column is of numeric type
        col = col.apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
    return col

def create_ration_evaluation(diet_summary_values, intermediate_results_values, 
                           animal_requirements, diet_table, f_nd, best_solution_vector):
    """
    Create Ration Evaluation DataFrame - preserving Jupyter logic
    """
    An_StatePhys = animal_requirements["An_StatePhys"]
    is_heifer = An_StatePhys.strip().lower() == "heifer"
    energy_label = "ME" if is_heifer else "NEL"
    energy_req = animal_requirements["An_ME"] if is_heifer else animal_requirements["An_NEL"]
    energy_name = "Metabolizable Energy (ME)" if is_heifer else "Net Energy (NEL)"
    
    Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
    An_Ca_req = animal_requirements["An_Ca_req"]
    An_P_req = animal_requirements["An_P_req"]

    # diet_summary_values[10] is Supply_ME; [9] is Supply_NEL 
    energy_supply = diet_summary_values[10] if is_heifer else diet_summary_values[9]
    energy_balance = energy_supply - energy_req

    # Ration Evaluation DataFrame 
    Ration_Evaluation = pd.DataFrame({
        "Parameter": ["DMI", energy_label, "MP", "Ca", "P"],
        
        "Requirement": [
            Trg_Dt_DMIn,
            energy_req,                      # ME or NEL
            intermediate_results_values[2],
            An_Ca_req,
            An_P_req
        ],
        
        "Supply": [
            diet_summary_values[0],           # DMI
            energy_supply,                    # ME or NEL
            diet_summary_values[2],           # MP
            diet_table["Inclusion_DM_kg"].mul(f_nd["Fd_Ca"]/100).sum(),
            diet_table["Inclusion_DM_kg"].mul(f_nd["Fd_P"]/100).sum()
        ],
        
        "Balance": [
            diet_summary_values[0] - Trg_Dt_DMIn,
            energy_balance,                     # ME−ME_req or NEL−NEL_req
            diet_summary_values[2] - intermediate_results_values[2],
            (best_solution_vector * f_nd["Fd_Ca"] / 100).sum() - An_Ca_req,
            (best_solution_vector * f_nd["Fd_P"]/100).sum() - An_P_req
        ]
    }).round(2)
    
    return Ration_Evaluation



def calculate_water_intake(Dt_DMInSum, Dt_AFIn, f_nd, animal_requirements, best_solution_vector):
    """
    Calculate water intake 
    """
    An_StatePhys = animal_requirements["An_StatePhys"]
    Env_TempCurr = animal_requirements.get("Env_TempCurr") 
    
    # Nutrient concentrations in the diet
    Dt_DMprop = Dt_DMInSum / Dt_AFIn * 100
    
    # Calculate diet composition using best_solution_vector directly
    ASH_diet = sum(best_solution_vector * (f_nd["Fd_Ash"]/100)) / Dt_DMInSum * 100 # (amount opt * kg of ash in diet / DMI) * 100 = % of DM
    CP_diet = sum(best_solution_vector * (f_nd["Fd_CP"]/100)) / Dt_DMInSum * 100
    
    # Water intake calculations
    An_WaIn_Lact = (
        -68.8 + 2.89 * Dt_DMInSum + 0.44 * Dt_DMprop +
        5.60 * ASH_diet + 1.81 * CP_diet
    )
    An_WaIn_Dry = (
        1.16 * Dt_DMInSum + 0.23 * Dt_DMprop +
        0.44 * Env_TempCurr + 0.061 * (Env_TempCurr - 16.4) ** 2
    )

    if An_StatePhys == "Lactating Cow":
        An_WaIn = An_WaIn_Lact
    elif An_StatePhys == "Heifer":
        An_WaIn = An_WaIn_Dry
    else:
        An_WaIn = An_WaIn_Dry
    
    return An_WaIn




def create_final_diet_dataframe(diet_table, f_nd):
    """
    Create final Dt DataFrame with all nutritional information
    """
    
    # Create base DataFrame
    Dt = pd.DataFrame({
        "Ingr_Category": f_nd["Fd_Category"],
        "Ingr_Type": f_nd["Fd_Type"],
        "Ingr_Name": f_nd["Fd_Name"],
        "Intake_DM": diet_table["Inclusion_DM_kg"],
        "Intake_AF": diet_table["Inclusion_AF_kg"],
        "Cost_per_kg": diet_table["Cost_per_kg"],
        "Ingr_Cost": diet_table["Total_Cost"]
    })

    Dt['DM'] = f_nd['Fd_DM']

    # Sum the nutrient intake for the diet
    Dt_DMInSum = Dt["Intake_DM"].sum() 
    Dt_AFIn = Dt["Intake_AF"].sum()

    # Calculate the AF and DM ingredient proportions
    Dt['Dt_DMInp'] = Dt['Intake_DM'] / Dt_DMInSum * 100
    Dt['Dt_AFInp'] = Dt['Intake_AF'] / Dt_AFIn * 100

    # Vector to get the variable names desired
    Col_names = [
       "Fd_ADF", "Fd_NDF", "Fd_Lg", "Fd_CP", "Fd_St", "Fd_EE", "Fd_FA", 
       "Fd_Ash", "Fd_NFC", "Fd_TDN", "Fd_Ca", "Fd_P"
    ]

    # Calculate nutrient intake in Kg/d
    for nutrient in Col_names:
        if nutrient in f_nd:
            renamed_nutrient = rename_variable(nutrient)
            Dt[renamed_nutrient] = Dt['Intake_DM'] * f_nd[nutrient] / 100

    Dt = Dt.apply(replace_na_and_negatives)

    # Add totals row
    column_sums = Dt.select_dtypes(include=[np.number]).sum()
    Dt_kg = pd.concat([Dt, pd.DataFrame([column_sums])], ignore_index=True)
    Dt_kg.iloc[-1, Dt_kg.columns.get_loc('Ingr_Name')] = 'Total'
    
    # Remove sum of columns Cost per kg and DM 
    total_idx = Dt_kg.index[-1]
    for col in ['DM', 'Cost_per_kg']:
        if col in Dt_kg.columns:
            Dt_kg.at[total_idx, col] = np.nan

    return Dt, Dt_kg, Dt_DMInSum, Dt_AFIn


def generate_nutrient_comparison(diet_summary_values, intermediate_results_values, 
                               animal_requirements, f_nd):
    """
    Generate nutrient comparison table
    """
    
    # Determine energy requirement
    An_StatePhys = animal_requirements["An_StatePhys"]
    is_heifer = "heifer" in An_StatePhys.strip().lower()
    energy_req = animal_requirements["An_ME"] if is_heifer else animal_requirements["An_NEL"]
    
    # Get constraint values from animal_requirements
    Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
    An_Ca_req = animal_requirements["An_Ca_req"]
    An_P_req = animal_requirements["An_P_req"]
    An_NDFfor_req = animal_requirements.get("An_NDFfor_req", np.nan)
    An_NDF_req = animal_requirements.get("An_NDF_req", np.nan)
    An_St_req = animal_requirements.get("An_St_req", np.nan)
    An_EE_req = animal_requirements.get("An_EE_req", np.nan)
    
    nutrient_labels = [
        "DMI (kg/day)",
        "Energy (Mcal/day)",
        "MP (g/day)",
        "Ca (g/day)",
        "P (g/day)",
        "NDF (% DM)",
        "NDF forage (% DM)",
        "Starch (% DM)",
        "Fat (% DM)"
    ]
    
    supplied = [
        diet_summary_values[0],  # DMI
        diet_summary_values[1],  # Energy
        diet_summary_values[2],  # MP
        diet_summary_values[3],  # Ca
        diet_summary_values[4],  # P
        diet_summary_values[5],  # NDF
        diet_summary_values[6],  # NDF forage
        diet_summary_values[7],  # Starch
        diet_summary_values[8]   # Fat
    ]
    
    targets = [
        Trg_Dt_DMIn,
        energy_req,
        intermediate_results_values[2],  # MP requirement
        An_Ca_req,
        An_P_req,
        np.nan,  # NDF (max constraint)
        np.nan,  # NDF forage (min constraint)
        np.nan,  # Starch (max constraint)
        np.nan   # Fat (max constraint)
    ]
    
    min_targets = [
        np.nan, np.nan, np.nan,
        An_Ca_req, An_P_req,
        np.nan, An_NDFfor_req,
        np.nan, np.nan
    ]
    
    max_targets = [
        np.nan, np.nan, np.nan,
        np.nan, np.nan,
        An_NDF_req, np.nan,
        An_St_req, An_EE_req
    ]
    
    # Calculate balance
    balance = []
    for i, (sup, targ, min_targ, max_targ) in enumerate(zip(supplied, targets, min_targets, max_targets)):
        if pd.notna(targ):
            balance.append(sup - targ)
        elif pd.notna(min_targ) and pd.notna(max_targ):
            if min_targ <= sup <= max_targ:
                balance.append("Within range")
            else:
                balance.append(f"Outside range")
        elif pd.notna(max_targ):
            if sup <= max_targ:
                balance.append("Within range")
            else:
                balance.append(f"Exceeds limit")
        elif pd.notna(min_targ):
            if sup >= min_targ:
                balance.append("Within range")
            else:
                balance.append(f"Below minimum")
        else:
            balance.append("No constraint")
    
    return pd.DataFrame({
        'Nutrient': nutrient_labels,
        'Supplied': supplied,
        'Target': targets,
        'Min Target': min_targets,
        'Max Target': max_targets,
        'Balance': balance
    })


# Result processing and diet table generation

def create_diet_table(best_solution_vector, f_nd):
    """
    Create diet table with ingredient proportions
    """
    # Calculate the inclusion in As-Fed
    inclusion_DM_kg = best_solution_vector
    inclusion_AF_kg = inclusion_DM_kg / (f_nd["Fd_DM"] / 100)
    ingredient_cost = f_nd["Fd_Cost"]
    total_cost_per_ingredient = inclusion_AF_kg * ingredient_cost
    total_real_cost = np.sum(total_cost_per_ingredient)
    
    df = pd.DataFrame({
        "Ingredient": f_nd["Fd_Name"],
        "Inclusion_DM_kg": inclusion_DM_kg,
        "Inclusion_AF_kg": inclusion_AF_kg,
        "Cost_per_kg": ingredient_cost,
        "Total_Cost": total_cost_per_ingredient
    })

    return df, total_real_cost


def analyze_infeasibility(res, f_nd):
    """
    Analyzes the final population from a failed optimization run to identify
    the most common reasons for failure (i.e., constraint violations).

    Parameters:
    -----------
    res : pymoo Result object
        The result from a failed optimization.
    f_nd : dict
        Feed nutritional data.

    Returns:
    --------
    dict : A dictionary summarizing the feasibility issues.
    """
    print("--- Running Infeasibility Analysis ---")
    
    # The violation details are stored in the problem object after the last evaluation
    violation_details = res.problem.last_violation_details
    
    if not violation_details:
        print("No violation data available to analyze.")
        return {"error": "No violation data available."}

    # Count how many times each constraint was violated
    violation_counts = {}
    for solution_violations in violation_details:
        for constraint_name in solution_violations.keys():
            violation_counts[constraint_name] = violation_counts.get(constraint_name, 0) + 1
            
    if not violation_counts:
        print("No constraint violations were found in the final population.")
        print("The issue might be with the objective function or a complete failure to evaluate.")
        return {"message": "No specific constraint violations found."}

    # Sort the violations by frequency
    sorted_violations = sorted(violation_counts.items(), key=lambda item: item[1], reverse=True)
    
    total_solutions = len(violation_details)
    
    print("Top 5 most frequent constraint violations:")
    feedback = {
        "message": "The optimization struggled to meet the following constraints:",
        "top_issues": []
    }

    for i, (name, count) in enumerate(sorted_violations[:5]):
        percentage = (count / total_solutions) * 100
        print(f"{i+1}. '{name}': Violated in {count}/{total_solutions} solutions ({percentage:.1f}%)")
        feedback["top_issues"].append({
            "constraint": name,
            "violation_count": count,
            "violation_percentage": percentage
        })
        
    return feedback



# Result classification and selection

def solution_selection(res, f_nd, animal_requirements):
    """
    Solution selection using satisfaction flags from optimization.
    """
    
    if res.X is None or res.F is None or len(res.X) == 0:
        print("NO SOLUTIONS FOUND")
        return None, "VERY_LOW", "INFEASIBLE"
    
    solutions = res.X
    objectives = res.F
    costs = objectives[:, 0]

    if hasattr(res.problem, 'last_satisfaction_flags'):
        satisfaction_flags = res.problem.last_satisfaction_flags
        print(f"✅ Using stored satisfaction flags for {len(solutions)} solutions")
    else:
        print("⚠️ No stored satisfaction flags, falling back to evaluation")
        satisfaction_flags = ["UNKNOWN"] * len(solutions)

    # Group solutions by stored satisfaction level
    solution_groups = {"PERFECT": [], "GOOD": [], "MARGINAL": [], "SUBOPTIMAL": [], "INFEASIBLE": []}

    for i, (solution, cost, flag) in enumerate(zip(solutions, costs, satisfaction_flags)):
        solution_groups[flag].append({
            'index': i,
            'solution': solution,
            'cost': cost,
            'satisfaction_flag': flag
        })
    
    # Display distribution (same as before)
    for category, solutions_list in solution_groups.items():
        print(f"{category} solutions: {len(solutions_list)}")
    
    selection_order = [("PERFECT", "HIGH", "OPTIMAL"), ("GOOD", "HIGH", "GOOD"), ("MARGINAL", "MEDIUM", "MARGINAL")]

    best_solution = None
    confidence_level = "VERY_LOW"
    status = "INFEASIBLE"

    for category, conf_level, status_temp in selection_order:
        candidates = solution_groups[category]
        if candidates:
            best_solution = min(candidates, key=lambda x: x['cost'])
            confidence_level = conf_level
            status = status_temp

            print(f"\n{status} SOLUTION SELECTED from {len(candidates)} {category} solutions")
            print(f"Selected cost: ${best_solution['cost']:.2f}/day")
            
            break
        
    if not best_solution:
        print("NO ACCEPTABLE SOLUTIONS FOUND")
        return None, "VERY_LOW", "INFEASIBLE"
    
    # ONLY EVALUATE THE SELECTED SOLUTION (not all solutions!)
    diet_summary_values, intermediate_results_values, An_MPm = diet_supply(
        best_solution['solution'], f_nd, animal_requirements
    )
    
    # Calculate adequacy metrics from the single evaluation
    energy_supply = diet_summary_values[1]
    protein_supply = diet_summary_values[2]
    dmi_supply = diet_summary_values[0]
    
    An_StatePhys = animal_requirements["An_StatePhys"]
    is_heifer = "heifer" in An_StatePhys.strip().lower()
    energy_req = animal_requirements["An_ME"] if is_heifer else animal_requirements["An_NEL"]
    protein_req = intermediate_results_values[2]
    dmi_req = animal_requirements["Trg_Dt_DMIn"]

    # Solution adequacy metrics
    solution_metrics = {
    'total_cost': best_solution['cost'],
    'satisfaction_flag': best_solution['satisfaction_flag'],
    'energy_adequacy': (energy_supply / energy_req) * 100 if energy_req > 0 else 0,
    'protein_adequacy': (protein_supply / protein_req) * 100 if protein_req > 0 else 0,
    'dmi_adequacy': (dmi_supply / dmi_req) * 100 if dmi_req > 0 else 0
    }
    
    print(f"SOLUTION DETAILS:")
    print(f"Cost: ${solution_metrics['total_cost']:.2f}/day")
    print(f"Energy: {solution_metrics['energy_adequacy']:.1f}% of requirement")
    print(f"Protein: {solution_metrics['protein_adequacy']:.1f}% of requirement") 
    print(f"DMI: {solution_metrics['dmi_adequacy']:.1f}% of target")
    
    return best_solution['solution'], solution_metrics, status


# Utility functions
def adjust_dmi_temperature(DMI, Temp):
    """Adjust DMI based on environmental temperature"""
    if Temp > 20:
        return DMI * (1 - (Temp - 20) * 0.005922)
    elif Temp < 5:
        return DMI * (1 - (5 - Temp) * 0.004644)
    else:
        return DMI

def preprocess_dataframe(df):
    """Preprocess DataFrame by converting integers to float and replacing NaN with 0"""
    for col in df.columns:
        # Convert integers to float
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].astype(np.float64)
        
        # Replace NaN values with 0
        df[col] = df[col].fillna(0)
    
    return df

# Global constants and constraints
# Constraints for optimization 
Constraints = {
    "Lactating Cow": {
        # Forage
        "forage_straw_max":       0.20,      
        "forage_wet_max":         0.100,
        "forage_fibrous_max":     0.100,
        "ndf":                    0.80,  
        "ndf_for":                0.20,   
        # Concentrate
        "starch_max":             0.26,  
        "ee_max":                 0.07,   
        "conc_byprod_max":        0.40,
        # Other feeds
        "other_wet_ingr_max":     0.20
    },
    "Dry Cow": {
        "forage_straw_max":       0.20,
        "forage_wet_max":         0.40,
        "forage_fibrous_max":     0.50,
        "ndf":                    0.75,   
        "ndf_for":                0.25,   
        "starch_max":             0.15,   
        "ee_max":                 0.06,   
        "conc_byprod_max":        0.20,
        "other_wet_ingr_max":     0.10
    },
    "Heifer": {
        "forage_straw_max":       0.15,
        "forage_wet_max":         0.40,
        "forage_fibrous_max":     0.50,
        "ndf":                    0.75,   
        "ndf_for":                0.25,  
        "starch_max":             0.18,   
        "ee_max":                 0.06,   
        "conc_byprod_max":        0.20,
        "other_wet_ingr_max":     0.08
    }
}

def calculate_an_requirements(animal_inputs):
    """
    Calculate animal nutritional requirements based on input parameters.
    
    Parameters:
    -----------
    animal_inputs : dict
        Dictionary containing all animal and environment parameters
        
    Returns:
    --------
    dict : Dictionary containing all calculated requirements and intermediate values
    """
    
    # ===================================================================
    # INPUTS
    # ===================================================================
    
    # Required inputs with defaults
    VALID_STATES = ["Lactating Cow", "Dry Cow", "Heifer", "Baby Calf/Heifer"] # State of the animal: "Lactating Cow", "Dry Cow", "Heifer", "Baby Calf/Heifer"
    An_StatePhys = animal_inputs.get("An_StatePhys", "Lactating Cow") 
    if An_StatePhys not in VALID_STATES:
        raise ValueError(f"Invalid animal state: {An_StatePhys}")
    

    An_Breed = animal_inputs.get("An_Breed", "Holstein")  # Breed of the animal: "Holstein", "Indigenous", "Crossbred"
    An_BW = animal_inputs.get("An_BW", 600) # Body weight of the animal in kg
    
    # if user selects "Baby Calf/Heifer" the body weight input can be defauls as 40 kg and the input box should not take values > 100 kg
    
    Trg_FrmGain = animal_inputs.get("Trg_FrmGain", 0.2)          # Target gain in kg/day  Default value: 0.2 kg/day

    # Specify in the front end:
    # Baby_Calf - milk intake only =< 8 weeks of age

    # -------- Only for lactating cows ----------#
    # If animals is not lactating, the following inputs should be disabled : An_ BCS, An_LactDay, Trg_MilkProd_L, Trg_MilkTPp, Trg_MilkFatp, Trg_MilkLacp, An_Parity
    An_BCS = animal_inputs.get("An_BCS", 3.0)              # Body condition score (BCS) of the animal
    An_LactDay = animal_inputs.get("An_LactDay", 100)      # Lactation day of the animal
    Trg_MilkProd_L = animal_inputs.get("Trg_MilkProd_L", 25)         # Target milk production in liters/day
    Trg_MilkTPp = animal_inputs.get("Trg_MilkTPp", 3.2)        # Target milk protein percentage
    Trg_MilkFatp = animal_inputs.get("Trg_MilkFatp", 3.8)         # Target milk fat percentage
    An_Parity = animal_inputs.get("An_Parity", 2)              # Parity of the animal
    # -------------------------------------------#

    An_GestDay = animal_inputs.get("An_GestDay", 0)     # Dry cows and heifer can also be pregnant
    Env_TempCurr = animal_inputs.get("Env_TempCurr", 20)  # Current temperature in Celsius
    Env_Grazing = animal_inputs.get("Env_Grazing", 1) # Grazing environment (0 for grazing, 1 for non-grazing)
    Env_Dist_km = animal_inputs.get("Env_Dist_km", 0)  # Distance to grazing area in kilometers
    Env_Topog = animal_inputs.get("Env_Topog", 0)  # Topography (0 for flat, 1 for hilly, 2 for mountainous)           

    # ===================================================================
    # Only defauls in the backend
    # ===================================================================

    Trg_MilkLacp = 4.85        # Target milk lactose percentage
    Trg_RsrvGain = 0           # Target reserve gain in kg/day
    An_305RHA_MlkTP = 396      # 305-day rolling herd average milk protein in kg
    An_AgeCalv1st = 729.6      # Age at first calving in days 
    Fet_BWbrth = 44.1          # Body weight of the fetus in kg
    An_GestLength = 280        # Gestation length in days
    An_AgeConcept1st = 491     # Age at first conception in days
    CalfInt = 370              # Interval between calves in days

    # ===================================================================
    # ANIMAL INPUTS PROCESSING
    # ===================================================================
    
    An_BW_mature = 600 if An_Breed in ["Holstein", "Crossbred"] else 550
    An_MBW = An_BW ** 0.75
    An_BWgain = Trg_FrmGain + Trg_RsrvGain
    Trg_BWgain_g = An_BWgain * 1000
    An_Parity = 2 if An_Parity > 1 else 1
    An_Parity = 0 if An_StatePhys == 'Heifer' else An_Parity
    Env_Topo = 50 if Env_Topog == 1 else 200 if Env_Topog == 2 else 500 if Env_Topog >= 3 else 0
    Env_Dist = Env_Dist_km * 1000
    Trg_MilkProd = Trg_MilkProd_L * 1.03
    An_GestDay = 0 if An_GestDay < 0 or An_GestDay is None else An_GestDay
    An_GestDay = 0 if An_GestDay > An_GestLength + 10 else An_GestDay
    An_PrePartDay = An_GestDay - An_GestLength
    An_PrePartWk = An_PrePartDay / 7
    An_PostPartDay = 0 if An_LactDay <= 0 else An_LactDay
    An_PostPartDay = 100 if An_LactDay > 100 else An_LactDay
    An_PrePartWklim = -3 if An_PrePartWk < -3 else 0 if An_PrePartWk > 0 else An_PrePartWk
    An_PrePartWkDurat = An_PrePartWklim * 2
    
    # ===================================================================
    # Requirements
    # ===================================================================
    
    # Dry matter intake (DMI) requirements 

    Trg_NEmilk_Milk = (9.29 * Trg_MilkFatp / 100 + 5.85 * Trg_MilkTPp / 100 + 3.95 * Trg_MilkLacp / 100)
    Trg_NEmilkOut = Trg_NEmilk_Milk * Trg_MilkProd if Trg_MilkProd > 0 else 0

    Dt_DMIn = 0.0

    # Base DMI calculation
    if An_StatePhys == "Lactating Cow":
        Dt_DMIn = (3.7 + 5.7 * (An_Parity - 1) + 0.305 * Trg_NEmilkOut + 0.022 * An_BW +
                   (-0.689 - 1.87 * (An_Parity - 1)) * An_BCS) * \
                  (1 - (0.212 + 0.136 * (An_Parity - 1)) * np.exp(-0.053 * An_LactDay))

        FCM = (0.4 * Trg_MilkProd) + (15 * Trg_MilkFatp * Trg_MilkProd / 100)
        DMI_NRC = (0.372 * FCM + 0.0968 * An_MBW) * (1 - np.exp(-0.192 * (An_LactDay / 7 + 3.67)))
        Dt_DMIn = DMI_NRC * 0.87 + 1.3131 if An_Breed == "Indigenous" else Dt_DMIn
        Dt_DMIn = adjust_dmi_temperature(Dt_DMIn, Env_TempCurr)

    elif An_StatePhys == "Dry Cow":                                                             
        Dt_DMIn_DryCow_AdjGest = An_BW * (-0.756 * np.exp(0.154 * (An_GestDay - An_GestLength))) / 100
        Dt_DMIn_DryCow_AdjGest = 0 if (An_GestDay - An_GestLength) < -21 else Dt_DMIn_DryCow_AdjGest
        Dt_DMIn = An_BW * 1.979 / 100 + Dt_DMIn_DryCow_AdjGest

    elif An_StatePhys == "Heifer":
        if An_Breed == "Holstein":
            Dt_DMIn = 15.36 * (1 - np.exp(-0.0022 * An_BW))
        else:  # Crossbred or others
            Dt_DMIn = 12.91 * (1 - np.exp(-0.00295 * An_BW))

    elif An_StatePhys == "Baby Calf/Heifer":
         Dt_DMIn = 0.10 * An_BW

    Trg_Dt_DMIn = Dt_DMIn # Target DMI
    Dt_DMIn_BW = (Dt_DMIn / An_BW) * 100
    Dt_DMIn_MBW = (Dt_DMIn / An_MBW) * 100

    # For baby calf the Trg_Dt_DMIn is the amount of milk that should be fed in L a day; half in the morning and half in the evening.
    # Feed recomendation end here and report can be displayed as following:

    if An_StatePhys == "Baby Calf/Heifer":
        milk_total = round(Trg_Dt_DMIn)  
        milk_morning = round(milk_total / 2, 1)
        milk_evening = round(milk_total / 2, 1)
    else:
        milk_total = milk_morning = milk_evening = 0

    # Report summary if "Baby Calf/Heifer"
    # For this category formulation stops here
    # This table can be displayed in the front end as a summary of the milk feeding recommendation and be available for exporting
    # Feel fre to modify it to fit the app style

    # Only create and plot the table if the animal is a Baby Calf/Heifer
    if An_StatePhys == "Baby Calf/Heifer":
        # Create df
        data = {
            "Feeding Time": ["Morning", "Evening", "Total per Day"],
            "Milk Amount (liters)": [milk_morning, milk_evening, milk_total]
        }
        df = pd.DataFrame(data)

        # Plot the result in a table format
        fig, ax = plt.subplots(figsize=(6, 2))
        ax.axis('off')
        table = ax.table(
            cellText=df.values,
            colLabels=df.columns,
            cellLoc='center',
            loc='center',
            colColours=['#f2f2f2'] * 2
        )
        table.auto_set_font_size(False)
        table.set_fontsize(12)
        table.scale(1.2, 1.5)
        plt.title(f"Milk Feeding Recommendation", fontsize=14, weight='bold')
        plt.tight_layout()
        plt.show()

    # Energy requirements 

    # Maintenance Energy, Mcal/d 

    Km_ME_NE = 0.63 if An_StatePhys == "Heifer" else 0.66  # dry & lactating cows = 0.66
    Kl_ME_NE = 0.554 # efficiency for tropical catte = 0.554 - NASEM = 0.66

    # Same for Lact, Dry and Heifer (Kelly et al., 2021) 0.10 in Nasem and 0.08 in Kelly et al., 2021
    An_ME_maint = 0.15 *  An_MBW # Mcal/d                                                # only for heifers
    An_NEL_maint = 0.08 * An_MBW if An_StatePhys == "Lactating Cow" else (An_ME_maint * Km_ME_NE)  # Mcal/d

    An_NEmUse_Env = 0
    An_NEm_Act = (0.00035 * Env_Dist / 1000) * An_BW  # Walking
    An_NEm_Act_Topo = 0.0067 * Env_Topo / 1000 * An_BW  # Topography
    An_NEmUse_Act = An_NEm_Act + An_NEm_Act_Topo
    An_NEm = An_NEL_maint + An_NEmUse_Env + An_NEmUse_Act
    An_ME_m = An_NEm / Km_ME_NE  # Maintenance ME, Mcal/d

    # Total Maintenance Energy
    An_NELm = An_NEm

    # Lactation Energy, Mcal/kg of Milk
    An_NELlact = Trg_NEmilkOut  # Mcal/d

    # Gestation energy requirements (NASEM, 2021)

    An_Preg = (An_GestDay > 0) and (An_GestDay <= An_GestLength)

    GrUter_BWgain = 0.0
    Uter_Wt = 0.204
    Fet_Wt = 0.0
    Fet_BWgain = 0.0
    Uter_BWgain = 0.0
    Conc_BWgain = 0.0

    if not An_Preg:
        Gest_REgain = 0.0
        Gest_MEuse = 0.0
        An_MEgest = 0.0
        An_NEgest = 0.0
        Ky_ME_NE = 0.14
        GrUter_BWgain = 0.0
        GrUter_Wt = 0.0
        Uter_Wt = 0.0
        Fet_Wt = 0.0
        Uter_BWgain = 0.0
        Fet_BWgain = 0.0
        Conc_BWgain = 0.0
    else:
        # Calf birth weight (heifers produce slightly smaller calves)
        Fet_BWbrth = 0.058 * An_BW_mature if An_StatePhys == "Heifer" else 0.063 * An_BW_mature

       # NASEM constants
        GrUterWt_FetBWbrth = 1.816
        UterWt_FetBWbrth  = 0.2311
        NE_GrUtWt = 0.950
        GrUter_Ksyn = 2.43e-2
        GrUter_KsynDecay = 2.45e-5
        Fet_Ksyn = 5.16e-2
        Fet_KsynDecay = 7.59e-5
        Uter_Ksyn  = 2.42e-2
        Uter_KsynDecay = 3.53e-5
        Uter_Kdeg  = 0.20

        # Maternal uterus tissue
        Uter_Wtpart = Fet_BWbrth * UterWt_FetBWbrth
        Uter_Wt_base = 0.204
        if An_GestDay > 0:
            Uter_Wt = Uter_Wtpart * np.exp(-(Uter_Ksyn - Uter_KsynDecay * An_GestDay) *
                                           (An_GestLength - An_GestDay))
        elif 0 < An_LactDay < 100:
            Uter_Wt = ((Uter_Wtpart - Uter_Wt_base) *
                       np.exp(-Uter_Kdeg * An_LactDay) + Uter_Wt_base)
        else:
            Uter_Wt = Uter_Wt_base
    
        if An_Parity > 0 and Uter_Wt < 0.204:
            Uter_Wt = 0.204

        # Gravid uterus weight
        if An_GestDay > 0:
            GrUter_Wtpart = Fet_BWbrth * GrUterWt_FetBWbrth
            GrUter_Wt = (GrUter_Wtpart *
                        np.exp(-(GrUter_Ksyn - GrUter_KsynDecay * An_GestDay) *
                                (An_GestLength - An_GestDay)))
            GrUter_Wt = max(GrUter_Wt, Uter_Wt)
        else:
            GrUter_Wt = 0
    
        # Fetal weight prediction
        if An_GestDay > 0:
            Fet_Wt = Fet_BWbrth * np.exp(-(Fet_Ksyn - Fet_KsynDecay * An_GestDay) *
                                         (An_GestLength - An_GestDay))
        else:
            Fet_Wt = 0.0

        # Maternal and fetal tissue growth rates
        if An_GestDay > 0:
            Uter_BWgain = (Uter_Ksyn - Uter_KsynDecay * An_GestDay) * Uter_Wt
        elif 0 < An_LactDay < 100:
            Uter_BWgain = -Uter_Kdeg * Uter_Wt
        else:
            Uter_BWgain = 0.0

        if An_GestDay > 0:
            Fet_BWgain = (Fet_Ksyn - Fet_KsynDecay * An_GestDay) * Fet_Wt
        else:
            Fet_BWgain = 0.0

        # Daily gain/loss of gravid uterus tissue
        if An_GestDay > 0:
            GrUter_BWgain = (GrUter_Ksyn - GrUter_KsynDecay * An_GestDay) * GrUter_Wt
        elif 0 < An_LactDay < 100:
            GrUter_BWgain = Uter_BWgain
        else:
            GrUter_BWgain = 0.0

        Conc_BWgain = GrUter_BWgain - Uter_BWgain

        # Net energy retained and ME use
        Gest_REgain = GrUter_BWgain * NE_GrUtWt
        Ky_ME_NE = 0.14 if Gest_REgain >= 0 else 0.89
        An_MEgest = Gest_REgain / Ky_ME_NE
        An_NEgest = An_MEgest * Kl_ME_NE  # NEL equivalent

    # Changes in BW
    BW_BCS = 0.094 * An_BW  # Each BCS represents 94 g of weight per kg of BW
    An_BWnp = An_BW - GrUter_Wt  # Non-pregnant BW
    An_BWnp3 = An_BWnp / (1 + 0.094 * (An_BCS - 3))  # BWnp standardized to BCS of 3 using 9.4% of BW/unit of BCS

    # Frame and reserve gains (kg/d)
    Frm_Gain = Trg_FrmGain
    Rsrv_Gain = Trg_RsrvGain
    Body_Gain = Frm_Gain + Rsrv_Gain

    # Gut fill adjustment (as in NASEM)
    An_GutFill_BW = 0.06 # calf starter
    if An_StatePhys == "Heifer":
        An_GutFill_BW = 0.15
    elif An_StatePhys in ("Dry Cow", "Lactating Cow") and An_Parity > 0:
        An_GutFill_BW = 0.18

    Rsrv_Gain_empty = Rsrv_Gain

    An_GutFill_Wt = An_GutFill_BW * An_BWnp
    An_BW_empty = An_BW - An_GutFill_Wt
    An_BWmature_empty = An_BW_mature * (1 - An_GutFill_BW)
    An_BWnp_empty = An_BWnp3 - An_GutFill_Wt  # Non-pregnant empty BW
    An_BWnp3_empty = An_BWnp3 - An_GutFill_Wt  # Non-pregnant empty BW standardized to BCS of 3

    # Body composition
    Body_Fat_EBW = 0.067 + 0.188 * An_BW / An_BW_mature # eq 11-4a empty
    Frm_Gain_empty = Frm_Gain * (1 - An_GutFill_BW)
    Prot_BW_empty = 0.215 * Frm_Gain_empty # Protein in empty in kg/d

    # Fat and protein gains
    FatGain_Frm = 0.067 + 0.375 * (An_BW / An_BW_mature) # eq 11.5a gain
    NonFatGain_FrmGain = 1 - FatGain_Frm    # eq 11.5b
    Prot_EBG = 0.215 * NonFatGain_FrmGain

    FatGain_Rsrv = 0.622
    Frm_Fatgain = FatGain_Frm * Frm_Gain_empty
    Rsrv_Fatgain = FatGain_Rsrv * Rsrv_Gain_empty 
    Body_Fatgain = Frm_Fatgain + Rsrv_Fatgain

    Body_NP_CP = 0.86

    CPGain_Frm = 0.201 - 0.081 * (An_BW / An_BW_mature) #CP gain / gain for heifers
    NPGain_Frm = CPGain_Frm * Body_NP_CP #Convert to CP to TP gain / gain
    Frm_NPgain = NPGain_Frm * Frm_Gain_empty #TP gain
    CPGain_Rsrv = 0.068
    NPGain_Rsrv = CPGain_Rsrv * Body_NP_CP
    Rsrv_NPgain = NPGain_Rsrv * Rsrv_Gain_empty
    Body_CPgain = (Frm_NPgain + Rsrv_NPgain) / Body_NP_CP #CP gain

    # Retained energy (NE) for gain
    Frm_CPgain = Frm_NPgain /  Body_NP_CP   #CP gain
    Rsrv_CPgain = CPGain_Frm * Rsrv_Gain_empty

    Frm_NEgain = 9.4 * Frm_Fatgain + 5.55 * Frm_CPgain
    Rsrv_NEgain = 9.4 * Rsrv_Fatgain + 5.55 * Rsrv_CPgain

    # ME efficiencies
    Kf_ME_RE = 0.4 if An_BW < 250 else 0.63  # dry & lactating cows = 0.66.  # Nasem mixed this eff. for heifer sometimes 0.4 and sometimes 0.63 ??
    Kf_ME_RE = Kf_ME_RE if An_StatePhys == "Heifer" else 0.66  # dry & lactating cows = 0.66
    Kr_ME_RE = 0.60                      # reserves gain (heifers and dry cows)
    if Trg_MilkProd > 0 and Trg_RsrvGain > 0:
        Kr_ME_RE = 0.75                  # lactating cows gaining reserves
    if Trg_RsrvGain <= 0:
        Kr_ME_RE = 0.89                  # cows losing reserves

    # Convert to ME and then to NEL
    Frm_MEgain = Frm_NEgain / Kf_ME_RE
    Rsrv_MEgain = Rsrv_NEgain / Kr_ME_RE
    An_MEgain = Frm_MEgain + Rsrv_MEgain
    An_NELgain = An_MEgain * Kf_ME_RE if An_StatePhys == "Heifer" else Kl_ME_NE #NEL equivalent

    An_ME = An_ME_m + An_MEgest + An_MEgain # Only for heifers

    An_NEL = An_NELm + An_NELlact + An_NEgest + An_NELgain # For dry and lact cows

    # Protein requirements 
    # Maintenance protein, g/d

    Km_MP_NP = 0.69

    # Scurf
    #Scrf_CP_g = 0.20 * An_BW**0.60 
    #Scrf_MP_g = Scrf_CP_g / Km_MP_NP
    #Scrf_NP_g = Scrf_CP_g * Body_NP_CP
    # Fecal                                                           #dynamic part calculated inside the diet supply function
    #Fecal_CPend_g = ((12 + 0.12 * NDF in diet) * DMI) 
    #Fecal_MPend_g = Fecal_CPend_g / Km_MP_NP
    #Fe_NPend_g = Fe_CPend_g * 0.73 
    # Urinary
    # Urinary endogenous protein
    #Ur_NPend_g  = 0.053 * An_BW
    #Ur_MPend_g = Ur_NPend_g / Km_MP_NP
    #Ur_NPend_g = Ur_NPend_g * 6.25

    # Total maintenance NP and CP use
    #An_NPm_Use = Scrf_NP_g + Ur_NPend_g # + Fe_NPend_g   Add to diet supply function
    #An_CPm_Use = Scrf_CP_g + Ur_NPend_g # + Fe_CPend_g   Add to diet supply function

    # An_MPm = An_NPm_Use / Km_MP_NP  # Maintenance MP, g/d

    # Lactation
    An_MPl = Trg_MilkProd * Trg_MilkTPp / 100 / 0.67 * 1000

    # Growth

    # Net protein gain from frame and reserves gain (kg/d)
    Body_NPgain = Frm_NPgain + Rsrv_NPgain
    Body_NPgain_g = Body_NPgain * 1000

    # MP efficiency for growth
    if An_Parity == 0:  # heifers
        Kg_MP_NP = 0.60 * Body_NP_CP
        if An_BW_empty / An_BWmature_empty > 0.12:
            Kg_MP_NP = (0.64 - 0.3 * (An_BW_empty / An_BWmature_empty)) * Body_NP_CP
        if Kg_MP_NP < 0.394 * Body_NP_CP:
            Kg_MP_NP = 0.394 * Body_NP_CP
    else:  # cows (lactating or dry)
         Kg_MP_NP = 0.69

    An_MPg = Body_NPgain_g / Kg_MP_NP if Kg_MP_NP > 0 else 0

    # Pregnancy 

    CP_GrUtWt = 0.123
    # Net protein gain in the gravid uterus
    Gest_NCPgain_g = GrUter_BWgain * CP_GrUtWt * 1000
    Gest_NPgain_g = Gest_NCPgain_g * Body_NP_CP
    Gest_NPother_g = 0  # Other protein gain in gestation, defaults to 0
    Gest_NPuse_g = Gest_NPgain_g + Gest_NPother_g     # Gest_NPother_g defaults to 0
    Gest_CPuse_g = Gest_NPuse_g / Body_NP_CP

    Ky_MP_NP_Trg = 0.33

    if Gest_NPuse_g >= 0:
        An_MPp = Gest_NPuse_g / Ky_MP_NP_Trg
    else:
        An_MPp = Gest_NPuse_g * 1  # or just MP_p = Gest_NPuse_g

    An_MP = An_MPl + An_MPg + An_MPp           # # Incomplete requirement - Maintenance requirement (An_MPm) is calculated during optimization

    # Mineral requirements g/d unless specified otherwise

    # Calcium requirements 
    Fe_Ca_m = 0.9 * Dt_DMIn
    An_Ca_g = (9.83 * An_BW_mature ** 0.22 * An_BW ** -0.22) * An_BWgain
    An_Ca_y = (0.0245 * np.exp((0.05581 - 0.00007 * An_GestDay) * An_GestDay) - 0.0245 * np.exp((0.05581 - 0.00007 * (An_GestDay - 1)) * (An_GestDay - 1))) * An_BW / 715
    An_Ca_l = (0.295 + 0.239 * Trg_MilkTPp) * Trg_MilkProd

    # total Ca requirement
    An_Ca_r = Fe_Ca_m + An_Ca_g + An_Ca_y + An_Ca_l # g/day
    An_Ca_req = An_Ca_r / 1000 # convert to kg      # absorbed requirement

    # Phosphorus requirements
    Ur_P_m = 0.0006 * An_BW
    Fe_P_m = 0.8 * Dt_DMIn if An_Parity == 0 else 1.0 * Dt_DMIn
    An_P_m = Ur_P_m + Fe_P_m

    An_P_g = (1.2 + (4.635 * An_BW_mature ** 0.22 * An_BW ** -0.22)) * An_BWgain
    An_P_y = (0.02743 * np.exp((0.05527 - 0.000075 * An_GestDay) * An_GestDay) - 0.02743 * np.exp((0.05527 - 0.000075 * (An_GestDay - 1)) * (An_GestDay - 1))) * An_BW / 715
    An_P_l = 0 if Trg_MilkProd <= 0 else (0.48 + 0.13 * Trg_MilkTPp) * Trg_MilkProd

    # total P requirement
    An_P_r = An_P_m + An_P_g + An_P_y + An_P_l
    An_P_req = An_P_r / 1000 # convert to kg.       # absorbed requirement

    # Magnesium requirements
    Ur_Mg_m = 0.0007 * An_BW
    Fe_Mg_m = 0.3 * Dt_DMIn
    An_Mg_m = Ur_Mg_m + Fe_Mg_m
    An_Mg_g = 0.45 * An_BWgain
    An_Mg_y = 0.3 * (An_BW / 715) if An_GestDay > 190 else 0
    An_Mg_l = 0 if Trg_MilkProd <= 0 else 0.11 * Trg_MilkProd
    An_Mg_req = An_Mg_m + An_Mg_g + An_Mg_y + An_Mg_l
    An_Mg_prod = An_Mg_y + An_Mg_l + An_Mg_g

    # Sodium requirements
    Fe_Na_m = 1.45 * Dt_DMIn
    An_Na_g = 1.4 * An_BWgain
    An_Na_y = 1.4 * An_BW / 715 if An_GestDay > 190 else 0
    An_Na_l = 0 if Trg_MilkProd <= 0 else 0.4 * Trg_MilkProd
    An_Na_req = Fe_Na_m + An_Na_g + An_Na_y + An_Na_l
    An_Na_prod = An_Na_y + An_Na_l + An_Na_g

    # Chloride requirements
    Fe_Cl_m = 1.11 * Dt_DMIn
    An_Cl_g = 1.0 * An_BWgain
    An_Cl_y = 1.0 * An_BW / 715 if An_GestDay > 190 else 0
    An_Cl_l = 0 if Trg_MilkProd <= 0 else 1.0 * Trg_MilkProd
    An_Cl_req = Fe_Cl_m + An_Cl_g + An_Cl_y + An_Cl_l
    An_Cl_prod = An_Cl_y + An_Cl_l + An_Cl_g

    # Potassium requirements
    Ur_K_m = 0.2 * An_BW if Trg_MilkProd > 0 else 0.07 * An_BW
    Fe_K_m = 2.5 * Dt_DMIn
    An_K_m = Ur_K_m + Fe_K_m
    An_K_g = 2.5 * An_BWgain
    An_K_y = 1.03 * (An_BW / 715) if An_GestDay > 190 else 0
    An_K_l = 0 if Trg_MilkProd <= 0 else 1.5 * Trg_MilkProd
    An_K_req = An_K_m + An_K_g + An_K_y + An_K_l
    An_K_prod = An_K_y + An_K_l + An_K_g

    # Sulfur requirements
    An_S_req = 2 * Dt_DMIn

    # Cobalt requirements
    An_Co_req = 0.2 * Dt_DMIn

    # Copper requirements
    An_Cu_m = 0.0145 * An_BW
    An_Cu_g = 2.0 * An_BWgain
    An_Cu_y = 0 if An_GestDay < 90 else 0.0023 * An_BW if An_GestDay > 190 else 0.0003 * An_BW
    An_Cu_l = 0 if Trg_MilkProd <= 0 else 0.04 * Trg_MilkProd
    An_Cu_req = An_Cu_m + An_Cu_g + An_Cu_y + An_Cu_l
    An_Cu_prod = An_Cu_y + An_Cu_l + An_Cu_g

    # Iodine requirements
    An_I_req = 0.216 * An_BW ** 0.528 + 0.1 * Trg_MilkProd

    # Iron requirements
    An_Fe_m = 0
    An_Fe_g = 34 * An_BWgain
    An_Fe_y = 0.025 * An_BW if An_GestDay > 190 else 0
    An_Fe_l = 0 if Trg_MilkProd <= 0 else 1.0 * Trg_MilkProd
    An_Fe_req = An_Fe_m + An_Fe_g + An_Fe_y + An_Fe_l
    An_Fe_prod = An_Fe_y + An_Fe_l + An_Fe_g

    # Manganese requirements
    An_Mn_m = 0.0026 * An_BW
    An_Mn_g = 2.0 * An_BWgain
    An_Mn_y = 0.00042 * An_BW if An_GestDay > 190 else 0
    An_Mn_l = 0 if Trg_MilkProd <= 0 else 0.03 * Trg_MilkProd
    An_Mn_req = An_Mn_m + An_Mn_g + An_Mn_y + An_Mn_l
    An_Mn_prod = An_Mn_y + An_Mn_l + An_Mn_g

    # Selenium requirements
    An_Se_req = 0.3 * Dt_DMIn

    # Zinc requirements
    An_Zn_m = 5.0 * Dt_DMIn
    An_Zn_g = 24 * An_BWgain
    An_Zn_y = 0.017 * An_BW if An_GestDay > 190 else 0
    An_Zn_l = 0 if Trg_MilkProd <= 0 else 4.0 * Trg_MilkProd
    An_Zn_req = An_Zn_m + An_Zn_g + An_Zn_y + An_Zn_l
    An_Zn_prod = An_Zn_y + An_Zn_l + An_Zn_g

    # Vitamin A requirements
    An_VitA_req = 110 * An_BW + 1000 * (Trg_MilkProd - 35) if Trg_MilkProd > 35 else 110 * An_BW

    # Vitamin D requirements
    An_VitD_req = 40 * An_BW if Trg_MilkProd > 0 else 32 * An_BW

    # Vitamin E requirements
    An_VitE_req = 2.0 * An_BW if Trg_MilkProd == 0 and An_Parity >= 1 else 0.8 * An_BW
    An_VitE_req = 3.0 * An_BW if An_GestDay >= 259 and An_Preg == 1 else An_VitE_req
    An_VitE_req = 0 if An_VitE_req < 0 else An_VitE_req
    
    
    # ===================================================================
    # 5. RETURN RESULTS DICTIONARY
    # ===================================================================
    
    results = {
        # Animal inputs (processed)
        "An_StatePhys": An_StatePhys,
        "An_Breed": An_Breed,
        "An_BW": An_BW,
        "An_BCS": An_BCS,
        "An_LactDay": An_LactDay,
        "An_Parity": An_Parity,
        "An_BW_mature": An_BW_mature,
        "An_MBW": An_MBW,
        
        # Milk production
        "Trg_MilkProd": Trg_MilkProd,
        "Trg_MilkProd_L": Trg_MilkProd_L,
        "Trg_MilkFatp": Trg_MilkFatp,
        "Trg_MilkTPp": Trg_MilkTPp,
        "Trg_MilkLacp": Trg_MilkLacp,
        "Trg_NEmilk_Milk": Trg_NEmilk_Milk,
        "Trg_NEmilkOut": Trg_NEmilkOut,
        
        # Environment
        "Env_TempCurr": Env_TempCurr,
        "Env_Grazing": Env_Grazing,
        "Env_Dist": Env_Dist,
        "Env_Topo": Env_Topo,
        
        # Growth
        "Trg_FrmGain": Trg_FrmGain,
        "Trg_RsrvGain": Trg_RsrvGain,
        "An_BWgain": An_BWgain,
        
        # DMI calculations
        "Dt_DMIn": Dt_DMIn,
        "Trg_Dt_DMIn": Trg_Dt_DMIn,
        "Dt_DMIn_BW": Dt_DMIn_BW,
        "Dt_DMIn_MBW": Dt_DMIn_MBW,
        
        # Milk feeding (for baby calves)
        "milk_total": milk_total,
        "milk_morning": milk_morning,
        "milk_evening": milk_evening,

        # Energy requirements
        "An_NEmUse_Env": An_NEmUse_Env,
        "An_NEm_Act": An_NEm_Act,
        "An_NEm_Act_Topo": An_NEm_Act_Topo,
        "An_ME_m": An_ME_m,
        "An_NEm": An_NEm,
        "An_NELm": An_NELm,
        "An_NELlact": An_NELlact,
        "An_Preg": An_Preg,
        "An_MEgest": An_MEgest,
        "An_NEgest": An_NEgest,
        "An_MEgain": An_MEgain,
        "An_NELgain": An_NELgain,
        "An_ME": An_ME,
        "An_NEL": An_NEL,

        # Protein requirements
        "An_MPl": An_MPl,
        "An_MPg": An_MPg,
        "An_MPp": An_MPp,
        "An_MP": An_MP,

        # Mineral requirements
        "An_Ca_req": An_Ca_req,
        "An_P_req": An_P_req,
        "An_Mg_req": An_Mg_req,
        "An_Na_req": An_Na_req,
        "An_Cl_req": An_Cl_req,
        "An_K_req": An_K_req,
        "An_S_req": An_S_req,
        "An_Co_req": An_Co_req,
        "An_Cu_req": An_Cu_req,
        "An_I_req": An_I_req,
        "An_Fe_req": An_Fe_req,
        "An_Mn_req": An_Mn_req,
        "An_Se_req": An_Se_req,
        "An_Zn_req": An_Zn_req,
        "An_VitA_req": An_VitA_req,
        "An_VitD_req": An_VitD_req,
        "An_VitE_req": An_VitE_req,

        # Status
        "status": "success"
    }
    
    return results

# Additional functions needed for optimization
def safe_divide(numerator, denominator, default_value=0.0):
    """Safely divide two numbers, returning default_value if denominator is zero"""
    if denominator == 0 or pd.isna(denominator):
        return default_value
    return numerator / denominator

def safe_sum(array):
    """Safely sum an array, handling NaN values"""
    if array is None or len(array) == 0:
        return 0.0
    return np.nansum(array)

def calculate_discount(TotalTDN, DMI, An_MBW):
    """Calculate discount factor for TDN"""
    if DMI == 0:
        return 1.0
    discount_factor = 1.0 - (0.18 * (DMI / An_MBW - 0.02))
    return max(0.5, min(1.0, discount_factor))

def calculate_MEact(f_nd):
    """Calculate metabolizable energy activity"""
    n = len(f_nd["Fd_Name"])
    MEact = np.zeros(n)
    
    for i in range(n):
        DE = f_nd["Fd_DE"][i]
        CP = f_nd["Fd_CP"][i]
        EE = f_nd["Fd_EE"][i]
        
        # Calculate ME from DE using NRC equations
        if CP > 0 and EE > 0:
            MEact[i] = DE * (0.96 - 0.004 * CP) * (1 - 0.01 * EE)
        else:
            MEact[i] = DE * 0.96
    
    return MEact

def diet_supply(x, f_nd, animal_requirements):
    """
    Calculate the diet supply based on the input vector x and feed data.
    
    Parameters:
    -----------
    x : array-like
        Feed amounts in kg/day for each ingredient
    f_nd : dict
        Feed nutritional data dictionary from process_feed_library()
    animal_requirements : dict
        Animal requirements dictionary from calculate_an_requirements()
        
    Returns:
    --------
    tuple : (diet_summary_values, intermediate_results_values, An_MPm)
        diet_summary_values : array - Supply values for optimization
        intermediate_results_values : array - Balance calculations
        An_MPm : float - Maintenance protein requirement
    """
    try:
        # Extract required values from animal requirements
        Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
        An_MBW = animal_requirements["An_MBW"]
        An_BW = animal_requirements["An_BW"]
        Body_NP_CP = 0.86  
        An_MPg = animal_requirements["An_MPg"]
        An_MPp = animal_requirements["An_MPp"]
        An_MPl = animal_requirements["An_MPl"]
        An_ME = animal_requirements["An_ME"]
        An_NEL = animal_requirements["An_NEL"]
        An_StatePhys = animal_requirements["An_StatePhys"]
        An_BW_mature = animal_requirements["An_BW_mature"]
        
        if len(x) != len(f_nd["Fd_Name"]):
           raise ValueError(f"Input vector length {len(x)} doesn't match feed count {len(f_nd['Fd_Name'])}")
        if np.any(x < 0):
                raise ValueError("Negative feed amounts not allowed")

        # Work on a local copy so we don't mutate the original structure during optimization
        local_f = {k: v.copy() for k, v in f_nd.items()}

        DMI = sum(x) # sum of ingredient amounts in kg/d
        if DMI < 1e-6:
            raise ValueError("Total DMI is too small or zero")

        # Calculate nutitional discount at a diet level
        TotalTDN = safe_sum(x * (local_f["Fd_TDN"]/100))  # kg of TDN
        discount = calculate_discount(TotalTDN, DMI, An_MBW)

        local_f["Fd_TDNact"] = local_f["Fd_TDN"] * discount
        local_f["Fd_DEact"] = local_f["Fd_DE"] * discount
    
        # Energy values for Cows 
        local_f["Fd_MEact"] = calculate_MEact(local_f)
        NEl_diet = safe_sum(x * local_f["Fd_MEact"]) * 0.66    # Mcal/d - NEL according to NASEM 2021 for Lactating and Dry cows

        # Maintenance protein dynamic equation

        NDF_diet = safe_divide(safe_sum((f_nd["Fd_NDF"]) * x), DMI, default_value=0) # % of NDF in diet

        # Scurf
        Km_MP_NP = 0.65 
        Scrf_CP_g = 0.20 * An_BW**0.60 
        Scrf_NP_g = Scrf_CP_g * Body_NP_CP
        # Fecal                                                #dynamic part of protein requirement 
        Fe_CPend_g = ((12 + 0.12 * NDF_diet) * DMI) 
        Fe_NPend_g = Fe_CPend_g * 0.73 
        # Urinary endogenous protein
        Ur_NPend_g  = 0.053 * An_BW
        Ur_NPend_g = Ur_NPend_g * 6.25

        # Total maintenance NP and CP use
        An_NPm_Use = Scrf_NP_g + Ur_NPend_g + Fe_NPend_g 
        An_CPm_Use = Scrf_CP_g + Ur_NPend_g + Fe_CPend_g  

        An_MPm = An_NPm_Use / Km_MP_NP  # Maintenance MP, g/d #not with safe divide 

        Total_MP_Req = An_MPm + An_MPg + An_MPp + An_MPl # g/d

        state = An_StatePhys.strip().lower()
        is_heifer = (state == "heifer")

        Energy = (safe_sum(x * local_f["Fd_DEact"]) * 0.82) if is_heifer else NEl_diet

        # Apply NASEM 2021 safety for heifers
        if is_heifer:
            MP_min = (53 - 25 * (An_BW / An_BW_mature)) * (An_NEL / 0.66)  # g/d
            if Total_MP_Req < MP_min:
                Total_MP_Req = MP_min

        Total_MP_Requirement = Total_MP_Req/ 1000  # kg/d

        local_f["Fd_CP_g_d"] = local_f["Fd_CP"] / 100 * x * 1000
        local_f["Fd_ME_MJ"] = local_f["Fd_MEact"] * 4.184 * x
        total_ME_MJ_d = safe_sum(local_f["Fd_ME_MJ"])
        total_CP_g_d = safe_sum(local_f["Fd_CP_g_d"])
        Util_CP = 8.76 * total_ME_MJ_d + 0.36 * total_CP_g_d
        MP_GER = (Util_CP * 0.73 * 0.85) / 1000  # kg/d
        Protein_Balance = MP_GER - Total_MP_Requirement

        Supply_DMIn = DMI # kg/d
        Supply_Energy = Energy # Mcal/d - ME for heifers and NEL for cows
        Supply_MP = MP_GER # kg/d
        Supply_Ca = safe_sum(x * local_f["Fd_Ca_kg"])  # kg/d
        Supply_P = safe_sum(x * local_f["Fd_P_kg"]) # kg/d
        Supply_NDF = safe_sum(x * local_f["Fd_NDF_kg"])   # kg/d
        Supply_NDFfor = safe_sum(x * local_f["Fd_ForNDF_kg"]) # kg/d
        Supply_St = safe_sum(x * local_f["Fd_St_kg"]) # kg/d
        Supply_EE = safe_sum(x * local_f["Fd_EE_kg"]) # kg/d
        Supply_NEl = NEl_diet
        Supply_ME = safe_sum(x * local_f["Fd_DEact"]) * 0.82  # Mcal/d - ME for heifers
        NEL_balance = Supply_NEl - An_NEL # Mcal/d
        ME_balance = Supply_ME - An_ME # kg/d # for heifers
    
        diet_summary_values = np.array([
            Supply_DMIn, Supply_Energy, Supply_MP, Supply_Ca, Supply_P,
            Supply_NDF, Supply_NDFfor, Supply_St, Supply_EE, Supply_NEl, Supply_ME
        ])
        intermediate_results_values = np.array([DMI, NEL_balance, Total_MP_Requirement, Protein_Balance, ME_balance])

        return (diet_summary_values, intermediate_results_values, An_MPm)
    
    except Exception as e:
        print(f"Error in diet_supply: {e}")
        # Return default values
        diet_summary_values = np.full(11, np.nan)
        intermediate_results_values = np.full(5, np.nan)
        return (diet_summary_values, intermediate_results_values, 0)

def detect_present_categories(f_nd):
    """
    Detect which ingredient categories are present in the selected feed list.
    
    Parameters:
    f_nd: dict - Feed data dictionary
    
    Returns:
    dict - Boolean flags for each category presence
    """
    fd_type = np.char.strip(np.char.lower(np.array(f_nd["Fd_Type"], dtype=str)))
    fd_cp = f_nd["Fd_CP"]
    fd_ndf = f_nd["Fd_NDF"]
    fd_dm = f_nd["Fd_DM"]
    
    mask_for = fd_type == "forage"
    n = len(f_nd["Fd_Name"])
    
    # Forage categories
    mask_straw = mask_for & (fd_dm > 85) 
    mask_wet_forage = mask_for & (fd_dm < 21)
    mask_lqf = mask_for & (fd_cp < 7) & (fd_ndf > 72) & (~mask_straw)  # Low-quality fibrous
    
    # Concentrate categories
    is_byprod = f_nd.get("Fd_isbyprod", np.zeros(n)) > 0
    is_wet = fd_dm < 30
    is_wet_byprod = is_byprod & is_wet
    
    # Other categories
    mask_wet_other = (fd_dm < 21) & (~mask_for)  # Wet non-forage ingredients
    
    return {
        'has_straw': np.any(mask_straw),
        'has_wet_forage': np.any(mask_wet_forage),
        'has_lqf': np.any(mask_lqf),
        'has_wet_byprod': np.any(is_wet_byprod),
        'has_wet_other': np.any(mask_wet_other),
        # Store masks for constraint building
        'mask_straw': mask_straw,
        'mask_wet_forage': mask_wet_forage,
        'mask_lqf': mask_lqf,
        'mask_wet_byprod': is_wet_byprod,
        'mask_wet_other': mask_wet_other
    }

def build_conditional_constraints(x, nutritional_supply, nutrient_targets, epsilon, f_nd, Trg_Dt_DMIn, thr, categories, animal_requirements):
    """
    Build constraints only for ingredient categories that are present.
    
    Parameters:
    x: array - Current solution (feed amounts)
    nutritional_supply: array - Supplied nutrients
    nutrient_targets: array - Target nutrients
    epsilon: float - Current epsilon value for constraint relaxation
    f_nd: dict - Feed data dictionary
    Trg_Dt_DMIn: float - Target DMI
    thr: dict - Constraint thresholds for current animal state
    categories: dict - Category presence flags and masks
    
    Returns:
    tuple: (constraints_list, scales_list, constraint_names, satisfaction_flag)
    """
    G = []
    scales = []
    constraint_names = []
    
    # Core nutritional constraints (always applied)
    
    # DMI constraints
    G.extend([
        nutritional_supply[0] - (1.05 + epsilon) * nutrient_targets[0],  # DMI max
        (nutrient_targets[0] - epsilon) - nutritional_supply[0]  # DMI min
    ])
    scales.extend([nutrient_targets[0], nutrient_targets[0]])
    constraint_names.extend(["DMI_max", "DMI_min"])
    
    # Energy constraints
    G.extend([
        nutritional_supply[1] - (1.05 + epsilon) * (nutrient_targets[1] + 1),  # Energy max
        ((nutrient_targets[1] + 1) - epsilon) - nutritional_supply[1]  # Energy min
    ])
    scales.extend([nutrient_targets[1], nutrient_targets[1]])
    constraint_names.extend(["Energy_max", "Energy_min"])
    
    # Protein constraints
    G.extend([
        nutritional_supply[2] - (1.05 + epsilon) * (nutrient_targets[2] + 0.1),  # MP max
        ((nutrient_targets[2] + 0.1) - epsilon) - nutritional_supply[2]  # MP min
    ])
    scales.extend([nutrient_targets[2], nutrient_targets[2]])
    constraint_names.extend(["MP_max", "MP_min"])
    
    # Mineral constraints (always applied)
    G.extend([
        nutrient_targets[3] - nutritional_supply[3],  # Min Calcium
        nutrient_targets[4] - nutritional_supply[4]   # Min Phosphorus
    ])
    scales.extend([nutrient_targets[3], nutrient_targets[4]])
    constraint_names.extend(["Ca_min", "P_min"])
    
    # Nutrient limits (always applied)
    G.extend([
        nutritional_supply[5] - (nutrient_targets[5] + epsilon),  # Max NDF
        (nutrient_targets[6] - epsilon) - nutritional_supply[6],  # Min NDF from forage
        nutritional_supply[7] - (nutrient_targets[7] + epsilon),  # Max Starch
        nutritional_supply[8] - (nutrient_targets[8] + epsilon)   # Max EE
    ])
    scales.extend([nutrient_targets[5], nutrient_targets[6], nutrient_targets[7], nutrient_targets[8]])
    constraint_names.extend(["NDF_max", "NDFfor_min", "Starch_max", "EE_max"])
    
    # Conditional ingredient-specific constraints
    
    # Straw/Stover constraints
    if categories['has_straw']:
        straw_amount = np.sum(x[categories['mask_straw']])
        straw_limit = thr["forage_straw_max"] * Trg_Dt_DMIn
        G.append(straw_amount - straw_limit)
        scales.append(straw_limit)
        constraint_names.append("Straw_max")
    
    # Wet forage constraints
    if categories['has_wet_forage']:
        wet_forage_amount = np.sum(x[categories['mask_wet_forage']])
        wet_forage_limit = thr["forage_wet_max"] * Trg_Dt_DMIn
        G.append(wet_forage_amount - wet_forage_limit)
        scales.append(wet_forage_limit)
        constraint_names.append("WetForage_max")
    
    # Low-quality fibrous forage constraints
    if categories['has_lqf']:
        lqf_amount = np.sum(x[categories['mask_lqf']])
        lqf_limit = thr["forage_fibrous_max"] * Trg_Dt_DMIn
        G.append(lqf_amount - lqf_limit)
        scales.append(lqf_limit)
        constraint_names.append("LQF_max")
    
    # By-product concentrate constraints
    if categories['has_wet_byprod']:
        byprod_amount = np.sum(x[categories['mask_wet_byprod']])
        byprod_limit = thr["conc_byprod_max"] * Trg_Dt_DMIn
        G.append(byprod_amount - byprod_limit)
        scales.append(byprod_limit)
        constraint_names.append("Byprod_max")
    
    # Wet other ingredients constraints
    if categories['has_wet_other']:
        wet_other_amount = np.sum(x[categories['mask_wet_other']])
        wet_other_limit = thr["other_wet_ingr_max"] * Trg_Dt_DMIn
        G.append(wet_other_amount - wet_other_limit)
        scales.append(wet_other_limit)
        constraint_names.append("WetOther_max")

    # CONSTRAINT SATISFACTION CHECKS 

    # Calculate absolute margins
    energy_margin = nutritional_supply[1] - nutrient_targets[1]
    protein_margin = nutritional_supply[2] - nutrient_targets[2]
    dmi_margin = nutritional_supply[0] - nutrient_targets[0]
    
    # Perfect ranges 
    energy_perfect = 0.0 <= energy_margin <= 1.8
    protein_perfect = 0.0 <= protein_margin <= 0.8
    dmi_perfect = -0.5 <= dmi_margin <= 0.5
    
   # CORE SAFETY CHECK
    tolerance = 0.01
    energy_safe = nutritional_supply[1] >= (nutrient_targets[1] * 0.95 - tolerance)  # 95% energy minimum
    protein_safe = nutritional_supply[2] >= (nutrient_targets[2] * 0.90 - tolerance)  # 90% protein minimum
    dmi_safe = (nutritional_supply[0] >= nutrient_targets[0] * 0.90 - tolerance) and \
            (nutritional_supply[0] <= nutrient_targets[0] * 1.15 + tolerance)  # DMI 90-115%

    core_safety_ok = energy_safe and protein_safe and dmi_safe

    # OPTIMIZATION QUALITY SCORING (0-100 for each constraint)
    optimization_scores = []

    # Mineral adequacy scores
    ca_adequacy = min(100, (nutritional_supply[3] / nutrient_targets[3]) * 100) if nutrient_targets[3] > 0 else 100
    p_adequacy = min(100, (nutritional_supply[4] / nutrient_targets[4]) * 100) if nutrient_targets[4] > 0 else 100
    optimization_scores.extend([ca_adequacy, p_adequacy])

    # Fiber optimization scores
    if nutrient_targets[5] > 0:  # NDF max
        ndf_violation = max(0, nutritional_supply[5] - nutrient_targets[5]) / nutrient_targets[5]
        ndf_score = max(0, 100 - (ndf_violation * 100))
    else:
        ndf_score = 100
    optimization_scores.append(ndf_score)

    if nutrient_targets[6] > 0:  # NDF forage min
        ndf_for_adequacy = min(100, (nutritional_supply[6] / nutrient_targets[6]) * 100)
    else:
        ndf_for_adequacy = 100
    optimization_scores.append(ndf_for_adequacy)

    # Starch optimization score
    if nutrient_targets[7] > 0:  # Starch max
        starch_violation = max(0, nutritional_supply[7] - nutrient_targets[7]) / nutrient_targets[7]
        starch_score = max(0, 100 - (starch_violation * 100))
    else:
        starch_score = 100
    optimization_scores.append(starch_score)

    # Fat optimization score
    if nutrient_targets[8] > 0:  # EE max
        ee_violation = max(0, nutritional_supply[8] - nutrient_targets[8]) / nutrient_targets[8]
        ee_score = max(0, 100 - (ee_violation * 100))
    else:
        ee_score = 100
        optimization_scores.append(ee_score)

    # Calculate overall optimization score
    overall_optimization_score = np.mean(optimization_scores) if optimization_scores else 100
    
    # Classification logic
    if not core_safety_ok:
        satisfaction_flag = "INFEASIBLE"  # Only if core safety fails
    else:
        # Within safety bounds, classify by optimization quality and margins
        if (energy_perfect and protein_perfect and dmi_perfect and overall_optimization_score >= 85):
            satisfaction_flag = "PERFECT"
        elif (energy_margin >= -0.2 and protein_margin >= -0.05 and overall_optimization_score >= 70):
            satisfaction_flag = "GOOD"
        elif overall_optimization_score >= 50:
            satisfaction_flag = "MARGINAL"
        else:
            satisfaction_flag = "SUBOPTIMAL"  # Safe but poor optimization
    
    return G, scales, constraint_names, satisfaction_flag

def run_optimization(animal_requirements, f_nd, optimization_params=None):
    """
    Run ration optimization using NSGA-II algorithm with safe ThreadPool multiprocessing.
    
    Parameters:
    -----------
    animal_requirements : dict
        Animal requirements from calculate_an_requirements()
    f_nd : dict
        Feed nutritional data from process_feed_library()
    optimization_params : dict, optional
        Optimization parameters (pop_size, generations, etc.)
        
    Returns:
    --------
    res : pymoo Result object
        Complete optimization results compatible with your post-optimization module
    """
    
    # Default optimization parameters
    default_params = {
        "pop_size": 100,
        "generations": 100,
        "initial_epsilon": 0.5,
        "final_epsilon": 0.01,  
        "crossover_prob": 0.9,
        "crossover_eta": 5,
        "mutation_prob": 0.3,
        "mutation_eta": 5,
        "seed": 42,
        "verbose": True,
        "n_workers": 7  # ThreadPool workers
    }
    
    if optimization_params:
        default_params.update(optimization_params)
    
    params = default_params
    
    # Extract values from animal requirements
    An_StatePhys = animal_requirements["An_StatePhys"]
    Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
    An_NEL = animal_requirements["An_NEL"]
    An_ME = animal_requirements["An_ME"]
    An_Ca_req = animal_requirements["An_Ca_req"]
    An_P_req = animal_requirements["An_P_req"]
    
    thr = Constraints[An_StatePhys]
    
    # Nutrient constraints 
    An_NDF_req = thr["ndf"] * Trg_Dt_DMIn # Maximum of NDF
    An_NDFfor_req = thr["ndf_for"] * Trg_Dt_DMIn # min of NDF from forage ingredients
    An_St_req = thr["starch_max"] * Trg_Dt_DMIn # Maximum of Starch 
    An_EE_req = thr["ee_max"] * Trg_Dt_DMIn # Maximum of EE
    
    # Variable bounds 
    xl = np.zeros(len(f_nd["Fd_Name"])) 
    xu = np.full(len(f_nd["Fd_Name"]), Trg_Dt_DMIn) 
    
    # Upper bound for mineral ingredients 
    is_mineral = np.array(f_nd["Fd_Category"]) == "Minerals"
    xu[is_mineral] = 0.5 # Max 0.5 kg/d
    
    # Upper bound for additives
    is_urea = np.array(f_nd["Fd_CP"]) >= 100
    xu[is_urea] = Trg_Dt_DMIn * 0.01 # Max 1% of DMI 
    
    # Create optimization problem
    problem = DietOptimizationProblem(
        f_nd=f_nd,
        animal_requirements=animal_requirements,  # Pass the full dictionary
        thr=thr,
        An_NDF_req=An_NDF_req,
        An_NDFfor_req=An_NDFfor_req,
        An_St_req=An_St_req,
        An_EE_req=An_EE_req,
        initial_epsilon=params["initial_epsilon"],
        final_epsilon=params["final_epsilon"],
        max_generations=params["generations"],
        xl=xl,
        xu=xu,
        n_workers=params["n_workers"],  # Add ThreadPool workers
        diet_supply=diet_supply
    )
    
    # Set the algorithm (NSGA-II)
    algorithm = NSGA2(
        pop_size=params["pop_size"],
        sampling=FloatRandomSampling(),
        crossover=SimulatedBinaryCrossover(prob=params["crossover_prob"], eta=params["crossover_eta"]),  
        mutation=PolynomialMutation(prob=params["mutation_prob"], eta=params["mutation_eta"]),
        eliminate_duplicates=True,
        save_history=True
    )
    
    callback = EpsilonUpdateCallback(problem)
    start_time = time.time()
    stop_criteria = get_termination("n_gen", params["generations"])
    
    # Optimize with ThreadPool multiprocessing 
    try:
        res = minimize(
            problem,
            algorithm,
            stop_criteria,
            seed=params["seed"],
            verbose=params["verbose"],
            callback=callback
            # Note: No 'workers' parameter - ThreadPool is handled inside the problem class
        )
        
        end_time = time.time()
        
        # Results
        print("Best results:")
        print(res.X)
        print("Obj functions:")
        print(res.F)
        print(f"Total time: {end_time - start_time:.2f} seconds")
        
        return res
        
    except Exception as e:
        print(f"Optimization failed: {e}")
        return None

class DietOptimizationProblem(Problem):
    def __init__(self, f_nd, animal_requirements, thr, An_NDF_req, An_NDFfor_req, An_St_req, An_EE_req,
                 initial_epsilon=0.3, final_epsilon=0.01, max_generations=1000, xl=None, xu=None, 
                 n_workers=4, diet_supply=None):
    
        self.initial_epsilon = initial_epsilon
        self.final_epsilon = final_epsilon
        self.max_generations = max_generations
        self.current_gen = 0
        self.thr = thr  # Store constraint thresholds
        self.diet_supply = diet_supply  # Store diet_supply function
        self.n_workers = n_workers  # ThreadPool workers
        
        self.animal_requirements = animal_requirements
        
        self.Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
        self.An_NEL = animal_requirements["An_NEL"]
        self.An_ME = animal_requirements["An_ME"]
        self.An_Ca_req = animal_requirements["An_Ca_req"]
        self.An_P_req = animal_requirements["An_P_req"]
        self.An_StatePhys = animal_requirements["An_StatePhys"]
        
        # Store nutrient requirements
        self.An_NDF_req = An_NDF_req
        self.An_NDFfor_req = An_NDFfor_req
        self.An_St_req = An_St_req
        self.An_EE_req = An_EE_req
    
        # Detect present categories for conditional constraints
        self.categories = detect_present_categories(f_nd)
    
        # Calculate maximum possible constraints (for initialization)
        # Core constraints: 12 (DMI, Energy, MP, Ca, P, NDF, NDFfor, Starch, EE)
        max_constraints = 12
        # Add potential conditional constraints
        if self.categories['has_straw']: max_constraints += 1
        if self.categories['has_wet_forage']: max_constraints += 1
        if self.categories['has_lqf']: max_constraints += 1
        if self.categories['has_wet_byprod']: max_constraints += 1
        if self.categories['has_wet_other']: max_constraints += 1
    
        self.max_constraints = max_constraints
        self.last_violation_details = []

        super().__init__(
            n_var=len(f_nd["Fd_Name"]),  
            n_obj=2,                      
            n_constr=max_constraints,
            xl=xl,                         
            xu=xu                          
        )

        # Store feed data
        self.f_nd = f_nd
        
        # Print detected categories for user information
        #print("\\n🔍 Detected ingredient categories:")
        category_labels = {
            'has_straw': 'Straw/Stover/Hay',
            'has_wet_forage': 'Wet forages',
            'has_lqf': 'Low-quality fibrous forages',
            'has_wet_byprod': 'By-product wet',
            'has_wet_other': 'Wet non-forage ingredients'
        }
    
        active_categories = []
        for key, label in category_labels.items():
            if self.categories[key]:
                active_categories.append(label)

    def advance_generation(self, n_gen):
        self.current_gen = n_gen
    
    def _evaluate_single(self, x):
        """
        Evaluate a single solution - designed for ThreadPool execution.
        Pure function with no side effects.
        """
        try:
            diet_summary_values, intermediate_results_values, An_MPm = self.diet_supply(
                x, self.f_nd, self.animal_requirements
            )

            # unpack
            DMI = diet_summary_values[0]
            Energy = diet_summary_values[1]
            MP = diet_summary_values[2]
            Ca, P, NDF, NDFfor, St, EE = diet_summary_values[3:9]

            # Select the appropriate energy value for optimization ME (heifers) or NEL (cows)
            state = self.An_StatePhys.strip().lower()
            is_heifer = "heifer" in state
            energy_supply = Energy
            energy_target = self.An_ME if is_heifer else self.An_NEL

            An_MP_req = intermediate_results_values[2]
            # Check if the diet summary values are not None
            if diet_summary_values is None:
                 raise ValueError(f"Error in diet_supply: Returned None")

            energy_target_with_margin = energy_target + 1  # Same as constraint
            protein_target_with_margin = An_MP_req + 0.1   # Same as constraint

            nutrient_targets = np.array([self.Trg_Dt_DMIn, energy_target_with_margin, protein_target_with_margin, 
                self.An_Ca_req, self.An_P_req, self.An_NDF_req, self.An_NDFfor_req,
                self.An_St_req, self.An_EE_req   
            ])
        
            nutritional_supply = np.array([DMI, energy_supply, MP, Ca, P, NDF, NDFfor, St, EE])

            total_cost = (x * (self.f_nd["Fd_CostDM"])).sum()

            ns = diet_summary_values[[0, 1, 2]] 
            nt = nutrient_targets[[0, 1, 2]] 
            dev = nt - ns
            total_dev = np.sum(np.abs(dev))  # Sum of absolute deviations
            
            # Restrictions (G <= 0) - Using conditional constraints
            current_gen = self.current_gen
            # Linear epsilon decay
            if self.max_generations > 1:
                epsilon = self.initial_epsilon - (self.initial_epsilon - self.final_epsilon) * (current_gen / (self.max_generations - 1))
            else:
                epsilon = self.final_epsilon

            # Build conditional constraints
            G, scales, constraint_names, satisfaction_flag = build_conditional_constraints(
            x, nutritional_supply, nutrient_targets, epsilon, 
            self.f_nd, self.Trg_Dt_DMIn, self.thr, self.categories, self.animal_requirements
            )

            violated_constraints = {}
            for i, g_val in enumerate(G):
                if g_val > 0: # A constraint is violated if its value is > 0
                    # Store the name and how much it was violated by (after normalization)
                    violated_constraints[constraint_names[i]] = g_val / scales[i]
            
            # Normalize the restrictions
            scales = np.maximum(np.abs(np.array(scales)), 1e-3)
            G_n = np.array(G) / scales
            
            # Pad constraints to match maximum constraint count for pymoo
            if len(G_n) < self.max_constraints:
                padding = np.zeros(self.max_constraints - len(G_n))
                G_n = np.concatenate([G_n, padding])

            return total_cost, total_dev, G_n, satisfaction_flag, violated_constraints

        except Exception as e:
            # Return penalty values for failed evaluations
            return 1e9, 1e9, np.full(self.max_constraints, 1e9), "INFEASIBLE"
    
    def _evaluate(self, X, out, *args, **kwargs):
        """
        Evaluate population using safe ThreadPoolExecutor.
        """
        cost = []
        total_deviation = []
        restr = []
        satisfaction_flags = []
        violation_details_list = []
        
        failed_evaluations = 0
        
        # Use ThreadPoolExecutor for safe parallel evaluation
        with ThreadPoolExecutor(max_workers=self.n_workers) as executor:
            # Submit all evaluations
            future_to_index = {executor.submit(self._evaluate_single, x): i for i, x in enumerate(X)}
            
            # Collect results in order
            results = [None] * len(X)
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    print(f"\\n❌ Evaluation failed for solution {index}: {e}")
                    results[index] = (1e9, 1e9, np.full(self.max_constraints, 1e9), "INFEASIBLE")
                    failed_evaluations += 1
        
        # Extract results
        for result in results:
            cost.append(result[0])
            total_deviation.append(result[1])
            restr.append(result[2])
            satisfaction_flags.append(result[3])
            violation_details_list.append(result[4])
        
        if failed_evaluations > 0:
            print(f"{failed_evaluations}/{len(X)} evaluations failed and received penalty values")

        # Output
        out["F"] = np.column_stack([cost, total_deviation])  # Objective values
        out["G"] = np.array(restr)

        self.last_satisfaction_flags = satisfaction_flags  
        self.last_solutions = X.copy()
        self.last_violation_details = violation_details_list  # Store violation details for analysis

class EpsilonUpdateCallback:
    def __init__(self, problem):
        self.problem = problem  # Store a reference to the optimization problem

    def __call__(self, algorithm):
        """ This makes the class callable, updating the generation count dynamically """
        self.problem.advance_generation(algorithm.n_gen)

def run_post_optimization_analysis(res, f_nd, animal_requirements):
    """
    Main function to run complete post-optimization analysis with all missing components
    """
    # Select best solution
    best_solution_result, best_metrics_result, status = solution_selection(
        res, f_nd, animal_requirements
    )
    
    if best_solution_result is None:
        print("No acceptable solution found. Analysis terminated.")
        # Analyze infeasibility and return feedback
        feasibility_feedback = analyze_infeasibility(res, f_nd)

        # Return dictionary format for failure case
        return {
            'status': 'FAILURE',
            'status_classification': 'INFEASIBLE',
            'best_metrics_result': 'VERY_LOW',
            'total_cost': 0,
            'water_intake': 0,
            'nutrient_comparison': pd.DataFrame(),
            'Dt_kg': pd.DataFrame(),
            'error_message': 'No acceptable solution found',
            'feasibility_feedback': feasibility_feedback
        }
    
    # Extract best solution vector
    best_solution_vector = best_solution_result

    # Solution cleanup with ingredient-type 
    forage_concentrate_threshold = 0.1    # 100g for forages/concentrates
    mineral_additive_threshold = 0.005    # 5g for minerals/additives

    #print(f"   Before: {sum(1 for x in best_solution_vector if x > 0)} non-zero ingredients")
    #print(f"   Small amounts (<0.1): {sum(1 for x in best_solution_vector if 0 < x < 0.1)}")

    # Convert f_nd to DataFrame for easy access (local copy only)
    f_nd_local = pd.DataFrame(f_nd)
    cleaned_count = 0

    for i, ingredient_amount in enumerate(best_solution_vector):
        if i >= len(f_nd_local):  # Safety check
            continue
        
        try:
            ingredient_type = f_nd_local.iloc[i]['Fd_Type']
            ingredient_category = f_nd_local.iloc[i]['Fd_Category']
            ingredient_name = f_nd_local.iloc[i]['Fd_Name']
        
            # Determine appropriate threshold based on ingredient type
            if (ingredient_type in ['Minerals', 'Additive'] or 
                ingredient_category in ['Minerals', 'Additive'] or
                'urea' in ingredient_name.lower() or
                'premix' in ingredient_name.lower()):
                threshold = mineral_additive_threshold
                type_label = "Mineral/Additive"
            else:
                threshold = forage_concentrate_threshold
                type_label = "Forage/Concentrate"
        
            # Apply cleanup
            if ingredient_amount < threshold:
                print(f"   Cleaning: {ingredient_name} ({type_label}) {ingredient_amount:.3f} kg → 0.000 kg")
                best_solution_vector[i] = 0.0
                cleaned_count += 1
            elif ingredient_amount < 0.1:  # Show what we're keeping
                print(f"   Keeping: {ingredient_name} ({type_label}) {ingredient_amount:.3f} kg (above {threshold:.3f} threshold)")
            
        except Exception as e:
            print(f"Error processing ingredient {i}: {e}")
            continue

    #print(f"   After: {sum(1 for x in best_solution_vector if x > 0)} non-zero ingredients")
    #print(f"   Cleaned: {cleaned_count} negligible ingredients")
    #print(f"   Remaining small amounts: {sum(1 for x in best_solution_vector if 0 < x < 0.1)}")

    # Calculate diet supply ONE TIME for the selected solution
    diet_summary_values, intermediate_results_values, An_MPm = diet_supply(
        best_solution_vector, f_nd, animal_requirements
    )
    
    # Create diet table
    diet_table, total_real_cost = create_diet_table(best_solution_vector, f_nd)
    
    # Generate nutrient comparison
    nutrient_comparison = generate_nutrient_comparison(
        diet_summary_values, intermediate_results_values, animal_requirements, f_nd
    )
    
    # Create final diet DataFrame
    Dt, final_diet_df, Dt_DMInSum, Dt_AFIn = create_final_diet_dataframe(diet_table, f_nd)
    
    water_intake = calculate_water_intake(Dt_DMInSum, Dt_AFIn, f_nd, animal_requirements, best_solution_vector)
    
    ration_evaluation = create_ration_evaluation(
        diet_summary_values, intermediate_results_values, animal_requirements, diet_table, f_nd, best_solution_vector
    )
    
    # Create Animal Inputs DataFrame 
    animal_inputs = create_animal_inputs_dataframe(animal_requirements)
    
    # Create proportions DataFrame with forage/concentrate separation
    dt_proportions, dt_forages, dt_concentrates, dt_results = create_proportions_dataframe(
        Dt, Dt_DMInSum
    )
    
    # Calculate methane emissions 
    methane_report = calculate_methane_emissions(Dt, Dt_DMInSum, f_nd, animal_requirements, best_solution_vector)
    
    print(f"Analysis complete!")
    #print(f"Total cost: ${total_real_cost:.2f}/day")
    #print(f"Total DMI: {Dt_DMInSum:.2f} kg/day")
    #print(f"Total AF intake: {Dt_AFIn:.2f} kg/day")
    #print(f"Water intake: {water_intake:.2f} L/day")
    
    # Return dictionary format instead of tuple
    return {
        'status': 'SUCCESS',
        'status_classification': status,
        'confidence_level': {'OPTIMAL': 'HIGH', 'MARGINAL': 'MEDIUM', 'INFEASIBLE': 'LOW'}.get(status, 'MEDIUM'),
        'total_cost': total_real_cost,
        'water_intake': water_intake,
        'nutrient_comparison': nutrient_comparison,
        'Dt_kg': final_diet_df,
        'best_solution_result': best_solution_result,
        'diet_summary_values': diet_summary_values,
        'intermediate_results_values': intermediate_results_values,
        'diet_table': diet_table,
        'ration_evaluation': ration_evaluation,
        'animal_inputs': animal_inputs,
        'dt_proportions': dt_proportions,
        'dt_forages': dt_forages,
        'methane_report': methane_report
    }

def generate_report(post_results, animal_requirements, output_file="final_report.html"):
    """
    Generate HTML report from post-optimization analysis results.
    
    Parameters:
    -----------
    post_results : dict
        Dictionary returned from run_post_optimization_analysis()
    animal_requirements : dict
        Animal requirements dictionary from calculate_an_requirements()
    output_file : str
        Output HTML file path
    """
    
    # Check if analysis was successful
    if post_results['status'] != 'SUCCESS':
        print(f"❌ Cannot generate report: Analysis status is {post_results['status']}")
        return
    
    # Create a simple HTML report
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Diet Recommendation Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #2e7d32; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: #d4edda; }}
        </style>
    </head>
    <body>
        <h1>🐄 Diet Recommendation Report</h1>
        <h2>Status: {post_results['status_classification']}</h2>
        <h2>Total Cost: ${post_results['total_cost']:.2f}/day</h2>
        <h2>Water Intake: {post_results['water_intake']:.1f} L/day</h2>
        
        <h2>Diet Proportions</h2>
        {post_results['dt_proportions'].to_html(index=False) if not post_results['dt_proportions'].empty else '<p>No diet data available.</p>'}
        
        <p><em>Report generated by Feed Formulation API</em></p>
    </body>
    </html>
    """
    
    try:
        # Write the report file
        Path(output_file).write_text(html_content, encoding="utf-8")
        print(f"✅ Report generated: {output_file}")
    except Exception as e:
        print(f"Error writing report: {e}")
