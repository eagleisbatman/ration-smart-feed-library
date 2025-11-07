from ast import Dict
from decimal import Decimal
from math import e
import os
import pdb
import uuid
from fastapi import APIRouter, HTTPException, Depends, Query, Request, status
from middleware.logging_config import get_logger
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field, validator
from app.models import AnimalCharacteristics, FeedAnalyticsResponse, FeedDetailsResponse, Feed, FeedAnalyticsCreate, FeedAnalytics, UserInformation, UserInformationModel, CountryModel, CustomFeed, generate_next_custom_feed_code, DietEvaluationRequest, DietEvaluationResponse, DietEvaluationSummary, MilkProductionAnalysis, IntakeEvaluation, CostAnalysis, MethaneAnalysis, NutrientBalance, FeedBreakdownItem, CattleInfo, DietRecommendationRequest, DietRecommendationResponse, FeedWithPrice, PDFReportMetadata, PDFReportList, PDFReportResponse, SaveReportRequest, SaveReportResponse, GetUserReportsResponse, UserReportItem
from typing import Any, List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import union
from app.dependencies import get_db, load_feeds_for_evaluation, calculate_animal_requirements_evaluation, calculate_diet_supply_evaluation, predict_milk_supported_evaluation, safe_float

from app.models import UserUpdateRequest, FeedDescriptionResponse, UpdateUserInformation
from services.auth_utils import get_user_by_email, get_country_by_id
from sqlalchemy.exc import SQLAlchemyError
import traceback
from fastapi.responses import FileResponse
# from weasyprint import HTML
from weasyprint import HTML
from services.pdf_service import PDFService, rec_pdf_report_generator
import numpy as np
import time
import warnings
import base64
import io
from core.evaluation.abc_diet_eval import abc_main, abc_process_feed_library


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

from scipy.optimize import differential_evolution
import re
from datetime import datetime

# Initialize router and logger
router = APIRouter(tags=["Animal Management"])
animal_logger = get_logger("animal")



# Add missing class definitions


def load_feed_table(db: Session, feeds: List[str]) -> pd.DataFrame:
    
    """
    Fetch feed data from the database dynamically and return as a DataFrame.

    Args:
        db (Session): Database session.
        feeds (List[str]): List of feed IDs to filter.

    Returns:
        pd.DataFrame: DataFrame containing all feed data from the database query.
    """
    # Query the database for the specified feeds using feed.id
    results = db.query(Feed).filter(Feed.id.in_(feeds)).all()

    # Dynamically convert the query results to a DataFrame
    feed_table = pd.DataFrame([row.__dict__ for row in results])

    # Remove SQLAlchemy's internal metadata key
    if '_sa_instance_state' in feed_table.columns:
        feed_table.drop(columns=['_sa_instance_state'], inplace=True)

    return feed_table

def calculate_dmi_requirements(data: AnimalCharacteristics):
    # Example: calculate dry matter intake (DMI)
    if data.An_StatePhys == "Lactating Cow":
        Trg_NEmilk_Milk = (
            9.29 * float(data.Trg_MilkFatp) / 100 +
            5.85 * float(data.Trg_MilkTPp) / 100 +
            3.95 * float(data.Trg_MilkLacp) / 100
        )
        Trg_NEmilkOut = Trg_NEmilk_Milk * float(data.Trg_MilkProd_L)
        Dt_DMIn = (
            (3.7 + 5.7 * (data.An_Parity - 1) + 0.305 * Trg_NEmilkOut +
             0.022 * float(data.An_BW) +
             (-0.689 - 1.87 * (data.An_Parity - 1)) * float(data.An_BCS)) *
            (1 - (0.212 + 0.136 * (data.An_Parity - 1)) * np.exp(-0.053 * float(data.An_LactDay)))
        )
    else:
        # Add logic for other physiological states
        Dt_DMIn = float(data.An_BW) * 1.979 / 100
    return Dt_DMIn


def optimize_diet(f: pd.DataFrame, constraints: Dict[str, float]):
    # Convert decimal.Decimal columns to float if necessary
    if 'Fd_Cost' in f.columns:
        f['Fd_Cost'] = f['Fd_Cost'].astype(float)

    # Define bounds for optimization
    bounds = [(0, constraints['DMI_max'])] * len(f)

    # Fitness function for optimization
    def fitness_function(Fd_DMInp):
        total_DMI = np.sum(Fd_DMInp)
        # Check for constraint violations
        violation = max(0, constraints['DMI_min'] - total_DMI) + max(0, total_DMI - constraints['DMI_max'])
        return violation if violation > 0 else np.sum(Fd_DMInp * f['Fd_Cost'])

    # Perform optimization using differential evolution
    result = differential_evolution(fitness_function, bounds, strategy='best1bin', maxiter=1000, tol=1e-6)
    print("🚀 ~ result:", result)

    # Add the optimized Fd_DMIn values back to the DataFrame
    f['Fd_DMIn'] = result.x
    return f


def convert_decimal_to_float(df):

    """
    Converts columns of type decimal.Decimal in a Pandas DataFrame to float.
    """
    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, Decimal)).any():
            df[col] = df[col].astype(float)
    return df

# Function to Generate Diet Warnings
def generate_diet_warnings(supplied_nutrients, nutrient_targets, min_targets, max_targets, nutrient_labels):
    
    messages = []
    issue_count = 0  # Track number of violations
    
    print("\n--- Debug: Checking Nutrient Warnings ---")
    print(f"Supplied: {supplied_nutrients}")
    print(f"Min Targets: {min_targets}")
    print(f"Max Targets: {max_targets}")
    for i, (supply, min_t, max_t, target) in enumerate(zip(supplied_nutrients, min_targets, max_targets, nutrient_targets)):
        # Convert values to numeric (force NaN if conversion fails)
        supply = pd.to_numeric(supply, errors="coerce")
        min_t = pd.to_numeric(min_t, errors="coerce")
        max_t = pd.to_numeric(max_t, errors="coerce")
        target = pd.to_numeric(target, errors="coerce")
        # --- Apply Rules Safely ---
        # If there is a min constraint, check if the nutrient is too low
        if not np.isnan(min_t) and i in [3, 4] and supply < min_t * 0.90:  # Allow 10% under only for Ca, P
            messages.append(f"{nutrient_labels[i]} is too low. Please adjust ingredient selection.")
            issue_count += 1
        elif not np.isnan(min_t) and i == 6 and supply < min_t * 0.95:  # Allow 5% under for Forage Fiber
            messages.append(f"{nutrient_labels[i]} is too low. Please adjust ingredient selection.")
            issue_count += 1
        # If there is a max constraint, check if the nutrient is too high
        if not np.isnan(max_t) and i == 5 and supply > max_t * 1.20:  # NDF must exceed by 20% to trigger
            messages.append(f"{nutrient_labels[i]} is too high. Please adjust ingredient selection.")
            issue_count += 1
        elif not np.isnan(max_t) and i in [7, 8] and supply > max_t * 1.10:  # Starch & EE must exceed by 10%
            messages.append(f"{nutrient_labels[i]} is too high. Please adjust ingredient selection.")
            issue_count += 1
        # Check deviation from target (DMI, Energy, Protein)
        if pd.notna(target) and i in [0, 1, 2]:  
            if supply < target * 0.95:  # Allow 5% below target
                messages.append(f"{nutrient_labels[i]} is too low ({supply:.2f} vs {target:.2f}). Consider adjusting ingredients.")
                issue_count += 1
            elif supply > target * 1.05:  # Allow 5% above target
                messages.append(f"{nutrient_labels[i]} is too high ({supply:.2f} vs {target:.2f}). Consider adjusting ingredients.")
                issue_count += 1
    # If more than 3 issues are found, replace with a general infeasibility warning
    if issue_count > 3:
        return ["Infeasible diet. Please adjust ingredient selection."]
    
    elif issue_count == 0:
        messages.append(" The diet is well-balanced and meets all nutrient requirements.")
        messages.append(f"Total Feed Intake: {supplied_nutrients[0]:.2f} kg (meets target)")
        messages.append(f"Energy Available: {supplied_nutrients[1]:.2f} Mcal (within safe range)")
        messages.append(f"Protein Supply: {supplied_nutrients[2]:.2f} kg (meets requirement)")
    return messages  # Return all generated messages

def calculate_feed_logic(
    DietID,
    An_StatePhys,
    An_Breed,
    An_BW,
    An_BCS,
    Trg_FrmGain,
    An_LactDay,
    An_Parity,
    An_GestDay,
    Trg_MilkProd_L,
    Trg_MilkTPp,
    Trg_MilkFatp,
    Env_TempCurr,
    Env_Grazing,
    Env_Dist_km,
    Env_Topog,
    Trg_MilkLacp,
    Trg_RsrvGain,
    An_305RHA_MlkTP,
    An_AgeCalv1st,
    Fet_BWbrth,
    An_GestLength,
    An_AgeConcept1st,
    CalfInt,
    f
):
    print("test >",An_Parity,An_GestDay,An_GestLength)
    
    variables = {
        "DietID": DietID,
        "An_StatePhys": An_StatePhys,
        "An_Breed": An_Breed,
        "An_BW": An_BW,
        "An_BCS": An_BCS,
        "Trg_FrmGain": Trg_FrmGain,
        "An_LactDay": An_LactDay,
        "An_Parity": An_Parity,
        "An_GestDay": An_GestDay,
        "Trg_MilkProd_L": Trg_MilkProd_L,
        "Trg_MilkTPp": Trg_MilkTPp,
        "Trg_MilkFatp": Trg_MilkFatp,
        "Env_TempCurr": Env_TempCurr,
        "Env_Grazing": Env_Grazing,
        "Env_Dist_km": Env_Dist_km,
        "Env_Topog": Env_Topog,
        "Trg_MilkLacp": Trg_MilkLacp,
        "Trg_RsrvGain": Trg_RsrvGain,
        "An_305RHA_MlkTP": An_305RHA_MlkTP,
        "An_AgeCalv1st": An_AgeCalv1st,
        "Fet_BWbrth": Fet_BWbrth,
        "An_GestLength": An_GestLength,
        "An_AgeConcept1st": An_AgeConcept1st,
        "CalfInt": CalfInt,
        "f (Excel Data)": f
    }

    print("All Values:")
    for key, value in variables.items():
        print(f"{key} = {value}")
        
    An_BW_mature = 650 if An_Breed in ["Holstein", "Crossbred"] else 550
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
    print("An_PrePartWk",An_PrePartWk)
    An_PostPartDay = 0 if An_LactDay <= 0 else An_LactDay
    An_PostPartDay = 100 if An_LactDay > 100 else An_LactDay
    An_PrePartWklim = -3 if An_PrePartWk < -3 else 0 if An_PrePartWk > 0 else An_PrePartWk
    An_PrePartWkDurat = An_PrePartWklim * 2

    ########################################### 2 - Requirements

    # Dry matter intake (DMI) requirements 
    
    def adjust_dmi_temperature(DMI, Temp):
        if Temp > 20:
            return DMI * (1 - (Temp - 20) * 0.005922)
        elif Temp < 5:
            return DMI * (1 - (5 - Temp) * 0.004644)
        else:
            return DMI

    if An_StatePhys == "Lactating Cow":
        Trg_NEmilk_Milk = 9.29 * Trg_MilkFatp / 100 + 5.85 * Trg_MilkTPp / 100 + 3.95 * Trg_MilkLacp / 100
        Trg_NEmilkOut = Trg_NEmilk_Milk * Trg_MilkProd
        Dt_DMIn = (3.7 + 5.7 * (An_Parity - 1) + 0.305 * Trg_NEmilkOut + 0.022 * An_BW + (-0.689 - 1.87 * (An_Parity - 1)) * An_BCS) * (1 - (0.212 + 0.136 * (An_Parity - 1)) * np.exp(-0.053 * An_LactDay))
        FCM = (0.4 * Trg_MilkProd) + (15 * Trg_MilkFatp * Trg_MilkProd / 100)
        DMI_NRC = (0.372 * FCM + 0.0968 * An_MBW) * (1 - np.exp(-0.192 * (An_LactDay / 7 + 3.67)))
        Dt_DMIn = DMI_NRC * 0.87 + 1.3131 if An_Breed == "Indigenous" else Dt_DMIn
    else:
        Dt_DMIn_DryCow_AdjGest = An_BW * (-0.756 * np.exp(0.154 * (An_GestDay - An_GestLength))) / 100
        Dt_DMIn_DryCow_AdjGest = 0 if (An_GestDay - An_GestLength) < -21 else Dt_DMIn_DryCow_AdjGest
        Dt_DMIn = An_BW * 1.979 / 100 + Dt_DMIn_DryCow_AdjGest

    Dt_DMIn = adjust_dmi_temperature(Dt_DMIn, Env_TempCurr) # Adjust DMI for temperature 

    Trg_Dt_DMIn = Dt_DMIn # Target DMI
    Dt_DMIn_BW = (Dt_DMIn / An_BW) * 100
    Dt_DMIn_MBW = (Dt_DMIn / An_MBW) * 100

    # Energy requirements 

    # Maintenance Energy, Mcal/d
    An_NEL_maint = 0.08 * An_MBW  
    An_NEmUse_Env = 0
    An_NEm_Act = (0.00035 * Env_Dist / 1000) * An_BW  # Walking
    An_NEm_Act_Topo = 0.0067 * Env_Topo / 1000 * An_BW  # Topography
    An_NEmUse_Act = An_NEm_Act + An_NEm_Act_Topo

    # Total Maintenance Energy
    An_NELm = An_NEL_maint + An_NEmUse_Env + An_NEmUse_Act

    # Lactation Energy, Mcal/kg of Milk
    An_NELlact = (9.29 * Trg_MilkFatp / 100 + 5.85 * Trg_MilkTPp / 100 + 3.95 * Trg_MilkLacp / 100) * Trg_MilkProd  # Mcal/d

    # Gestation Energy
    An_Preg = 1 if 0 < An_GestDay <= An_GestLength else 0
    An_CBW = 0.058 * An_MBW if An_StatePhys == "Heifer" else 0.063 * An_MBW  # Calf Birth weight
    GrUter_WT = An_CBW * 1.825
    Uter_WT = An_CBW * 0.2288
    GrUter_wt = GrUter_WT * np.exp(-(0.0243 - (0.0000245 * An_GestDay)) * (280 - An_GestDay))
    Uter_wt = Uter_WT * np.exp(-(0.0243 - (0.0000245 * An_GestDay)) * (280 - An_GestDay))
    GrUter_WtGain = (0.0243 - (0.0000245 * An_GestDay)) * GrUter_WT  # Gain during gestation

    An_NEgest = GrUter_WtGain * 4.16 if 12 < An_GestDay <= An_GestLength else 0  # Mcal/d

    # Changes in BW
    BW_BCS = 0.094 * An_BW  # Each BCS represents 94 g of weight per kg of BW
    An_BWnp = An_BW - GrUter_WT  # Non-pregnant BW
    An_BWnp3 = An_BWnp / (1 + 0.094 * (An_BCS - 3))  # BWnp standardized to BCS of 3 using 9.4% of BW/unit of BCS
    An_GutFill_BWmature = 0.18  # mature animals
    An_GutFill_BW = 0.06  # Milk fed calf, kg/kg BW
    if An_StatePhys == "Heifer":
        An_GutFill_BW = 0.15
    elif (An_StatePhys == "Dry Cow" or An_StatePhys == "Lactating Cow") and An_Parity > 0:
        An_GutFill_BW = An_GutFill_BWmature
    An_GutFill_Wt = An_GutFill_BW * An_BWnp
    An_BW_empty = An_BW - An_GutFill_Wt
    An_BWmature_empty = An_BW_mature * (1 - An_GutFill_BWmature)
    An_NEL_BW = BW_BCS * 5.6 if An_StatePhys == "Lactating Cow" else BW_BCS * 6.9  # Mcal/kg gain
    Fat_ADG = (0.067 + 0.375 * (An_BW / An_BW_mature)) * An_BWgain  # g/day
    Protein_ADG = (0.201 - 0.081 * (An_BW / An_BW_mature)) * An_BWgain  # 
    RE_FADG = 9.4 * Fat_ADG + 5.55 * Protein_ADG
    # Convert RE to ME and NEL
    ME_FADG = RE_FADG / 0.4
    An_NEL_FrmGain = RE_FADG / 0.61  # Mcal/d

    An_NEL = An_NELm + An_NELlact + An_NEgest + An_NEL_FrmGain  # Mcal/d

    # Protein requirements 

    # Growth
    An_CW = (18 + (An_GestDay - 190) * 0.665) * (An_CBW / 45) if An_GestDay > 190 else 0
    An_MPm = ((0.3 * (An_BW - An_CW) ** 0.6) + (4.1 * (An_BW - An_CW) ** 0.5))
    An_MSBW = 0.96 * An_BW_mature
    An_SBW = 0.96 * An_BW
    An_EBW = 0.891 * An_SBW
    An_EQSBW = (An_SBW - An_CW) * 478 / An_MSBW
    NPg = 0 if An_BWgain == 0 else An_BWgain * (268 - (29.4 * An_NEL_FrmGain / An_BWgain))
    EffMP_NPg = (83.4 - 0.114 * An_EQSBW) / 100 if An_EQSBW <= 478 else 0.28908
    An_MPg = NPg / EffMP_NPg
    # Pregnancy
    An_Preg = 1 if An_GestDay > 0 and An_GestDay <= An_GestLength else 0
    An_MPp = (An_GestDay > 190) * (0.69 * An_GestDay - 69.2) * (An_CBW / 45) / 0.33
    # Lactation
    An_MPl = Trg_MilkProd * Trg_MilkTPp / 100 / 0.67 * 1000

    # Incomplete requirement - Maintenance requirement is calculated dynamicaly during optimization
    An_MP =  An_MPm + An_MPg + An_MPp + An_MPl  #  An_MPm (missing at this stage)

    # Calcium requirements 

    Ca_Mlk = 1.03 if An_Breed == "Holstein" else 1.17 if An_Breed == "Jersey" else 0
    Fe_Ca_m = 0.9 * Dt_DMIn
    An_Ca_g = (9.83 * An_BW_mature ** 0.22 * An_BW ** -0.22) * An_BWgain
    An_Ca_y = (0.0245 * np.exp((0.05581 - 0.00007 * An_GestDay) * An_GestDay) - 0.0245 * np.exp((0.05581 - 0.00007 * (An_GestDay - 1)) * (An_GestDay - 1))) * An_BW / 715
    An_Ca_l = Ca_Mlk * Trg_MilkProd if An_Breed == "Holstein" else Ca_Mlk * Trg_MilkProd if An_Breed == "Jersey" else 0
    An_Ca_l = (0.295 + 0.239 * Trg_MilkTPp) * Trg_MilkProd if An_Ca_l == 0 else An_Ca_l
    # total Ca requirement
    An_Ca_r = Fe_Ca_m + An_Ca_g + An_Ca_y + An_Ca_l # g/day
    An_Ca_req = An_Ca_r / 1000 # convert to kg

    # Phosphorus requirements
    Ur_P_m = 0.0006 * An_BW
    Fe_P_m = 0.8 * Dt_DMIn if An_Parity == 0 else 1.0 * Dt_DMIn
    An_P_m = Ur_P_m + Fe_P_m
    An_P_g = (1.2 + (4.635 * An_BW_mature ** 0.22 * An_BW ** -0.22)) * An_BWgain
    An_P_y = (0.02743 * np.exp((0.05527 - 0.000075 * An_GestDay) * An_GestDay) - 0.02743 * np.exp((0.05527 - 0.000075 * (An_GestDay - 1)) * (An_GestDay - 1))) * An_BW / 715
    An_P_l = 0 if np.isnan(Trg_MilkProd) else (0.49 + 0.13 * Trg_MilkTPp) * Trg_MilkProd
    # total P requirement
    An_P_r = An_P_m + An_P_g + An_P_y + An_P_l
    An_P_req = An_P_r / 1000 # convert to kg

    # Magnesium requirements
    Ur_Mg_m = 0.0007 * An_BW
    Fe_Mg_m = 0.3 * Dt_DMIn
    An_Mg_m = Ur_Mg_m + Fe_Mg_m
    An_Mg_g = 0.45 * An_BWgain
    An_Mg_y = 0.3 * (An_BW / 715) if An_GestDay > 190 else 0
    An_Mg_l = 0 if np.isnan(Trg_MilkProd) else 0.11 * Trg_MilkProd
    An_Mg_req = An_Mg_m + An_Mg_g + An_Mg_y + An_Mg_l
    An_Mg_prod = An_Mg_y + An_Mg_l + An_Mg_g

    # Sodium requirements
    Fe_Na_m = 1.45 * Dt_DMIn
    An_Na_g = 1.4 * An_BWgain
    An_Na_y = 1.4 * An_BW / 715 if An_GestDay > 190 else 0
    An_Na_l = 0 if np.isnan(Trg_MilkProd) else 0.4 * Trg_MilkProd
    An_Na_req = Fe_Na_m + An_Na_g + An_Na_y + An_Na_l
    An_Na_prod = An_Na_y + An_Na_l + An_Na_g

    # Chloride requirements
    Fe_Cl_m = 1.11 * Dt_DMIn
    An_Cl_g = 1.0 * An_BWgain
    An_Cl_y = 1.0 * An_BW / 715 if An_GestDay > 190 else 0
    An_Cl_l = 0 if np.isnan(Trg_MilkProd) else 1.0 * Trg_MilkProd
    An_Cl_req = Fe_Cl_m + An_Cl_g + An_Cl_y + An_Cl_l
    An_Cl_prod = An_Cl_y + An_Cl_l + An_Cl_g

    # Potassium requirements
    Ur_K_m = 0.2 * An_BW if Trg_MilkProd > 0 else 0.07 * An_BW
    Fe_K_m = 2.5 * Dt_DMIn
    An_K_m = Ur_K_m + Fe_K_m
    An_K_g = 2.5 * An_BWgain
    An_K_y = 1.03 * (An_BW / 715) if An_GestDay > 190 else 0
    An_K_l = 0 if np.isnan(Trg_MilkProd) else 1.5 * Trg_MilkProd
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
    An_Cu_l = 0 if np.isnan(Trg_MilkProd) else 0.04 * Trg_MilkProd
    An_Cu_req = An_Cu_m + An_Cu_g + An_Cu_y + An_Cu_l
    An_Cu_prod = An_Cu_y + An_Cu_l + An_Cu_g

    # Iodine requirements
    An_I_req = 0.216 * An_BW ** 0.528 + 0.1 * Trg_MilkProd

    # Iron requirements
    An_Fe_m = 0
    An_Fe_g = 34 * An_BWgain
    An_Fe_y = 0.025 * An_BW if An_GestDay > 190 else 0
    An_Fe_l = 0 if np.isnan(Trg_MilkProd) else 1.0 * Trg_MilkProd
    An_Fe_req = An_Fe_m + An_Fe_g + An_Fe_y + An_Fe_l
    An_Fe_prod = An_Fe_y + An_Fe_l + An_Fe_g

    # Manganese requirements
    An_Mn_m = 0.0026 * An_BW
    An_Mn_g = 2.0 * An_BWgain
    An_Mn_y = 0.00042 * An_BW if An_GestDay > 190 else 0
    An_Mn_l = 0 if np.isnan(Trg_MilkProd) else 0.03 * Trg_MilkProd
    An_Mn_req = An_Mn_m + An_Mn_g + An_Mn_y + An_Mn_l
    An_Mn_prod = An_Mn_y + An_Mn_l + An_Mn_g

    # Selenium requirements
    An_Se_req = 0.3 * Dt_DMIn

    # Zinc requirements
    An_Zn_m = 5.0 * Dt_DMIn
    An_Zn_g = 24 * An_BWgain
    An_Zn_y = 0.017 * An_BW if An_GestDay > 190 else 0
    An_Zn_l = 0 if np.isnan(Trg_MilkProd) else 4.0 * Trg_MilkProd
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

    ########################################### 3. Feeds

    # Set working directory
    # os.chdir("/Users/jma/Library/CloudStorage/OneDrive-UniversityofCalifornia,Davis/RFT/RFT_2/fdlib")

    # Load the feed selection table

    # Remove rows with NA values in the Fd_Name column
    f = f.dropna(subset=["Fd_Name"])

    f["Fd_Conc"] = f.apply(lambda row: 100 if row["Fd_Type"] == "Concentrate" else 0, axis=1)
    f["Fd_For"] = 100 - f["Fd_Conc"]
    f["Fd_ForWet"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] < 71 else 0, axis=1)
    f["Fd_ForDry"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] >= 71 else 0, axis=1)
    f["Fd_Past"] = f.apply(lambda row: 100 if row["Fd_Category"] == "Pasture" else 0, axis=1)

    f["Fd_ForNDF"] = (1 - f["Fd_Conc"] / 100) * f["Fd_NDF"]
    f["Fd_NDFnf"] = f["Fd_NDF"] - f["Fd_NDFIP"]

    f["Fd_NPNCP"] = f["Fd_CP"] * f["Fd_NPN_CP"] / 100
    f["Fd_NPN"] = f["Fd_NPNCP"] / 6.25
    f["Fd_NPNDM"] = f["Fd_NPNCP"] / 2.81
    f["Fd_TP"] = f["Fd_CP"] - f["Fd_NPNCP"]

    f["Fd_fHydr_FA"] = 1 / 1.06
    f["Fd_fHydr_FA"] = f.apply(lambda row: 1 if row["Fd_Category"] == "Fatty Acid Supplement" else row["Fd_fHydr_FA"], axis=1)
    f["Fd_FAhydr"] = f["Fd_FA"] * f["Fd_fHydr_FA"]

    f["Fd_NFC"] = 100 - f["Fd_Ash"] - f["Fd_NDF"] - f["Fd_TP"] - f["Fd_NPNDM"] - f["Fd_FAhydr"]
    f["Fd_NFC"] = f.apply(lambda row: 0 if row["Fd_NFC"] < 0 else row["Fd_NFC"], axis=1)

    f["Fd_rOM"] = 100 - f["Fd_Ash"] - f["Fd_NDF"] - f["Fd_St"] - (f["Fd_FA"] * f["Fd_fHydr_FA"]) - f["Fd_TP"] - f["Fd_NPNDM"]

    En_FA = 9.4
    En_CP = 5.65
    En_NFC = 4.2
    En_NDF = 4.2
    En_NDFnf = 4.14
    En_NPNCP = 0.89
    En_rOM = 4.0
    En_St = 4.23
    En_WSC = 3.9
    En_Acet = 3.48
    En_Prop = 4.96
    En_Butr = 5.95

    f["Fd_GE"] = (f["Fd_CP"] / 100 * En_CP + f["Fd_FA"] / 100 * En_FA + f["Fd_St"] / 100 * En_St + f["Fd_NDF"] / 100 * En_NDF + (100 - f["Fd_CP"] - f["Fd_FA"] - f["Fd_St"] - f["Fd_NDF"] - f["Fd_Ash"]) / 100 * En_rOM)

    f["Fd_Kp"] = 0
    f["Fd_Kp"] = f.apply(lambda row: 7.11 if row["Fd_Type"] == "Concentrate" else row["Fd_Kp"], axis=1)
    f["Fd_Kp"] = f.apply(lambda row: 4.95 if row["Fd_Type"] == "Forage" else row["Fd_Kp"], axis=1)

    # Fd_CP_RDP = Rumen Degradable Protein in crude protein
    f["Fd_CP_RDP"] = f["Fd_CPARU"] + f["Fd_CPBRU"] * (f["Fd_KdRUP"] / (f["Fd_KdRUP"] + f["Fd_Kp"]))
    # Fd_CP_RUP = Rumen Undegradable Protein in crude protein
    f["Fd_CP_RUP"] = f["Fd_CPBRU"] * (f["Fd_Kp"] / (f["Fd_KdRUP"] + f["Fd_Kp"])) + f["Fd_CPCRU"]

    # Change RDP and RUP to % of DM
    f["Fd_RDP"] = f["Fd_CP_RDP"] * f["Fd_CP"] / 100
    f["Fd_RUP"] = f["Fd_CP_RUP"] * f["Fd_CP"] / 100

    # Change RDP and RUP to % of DM
    f["Fd_RDP"] = f["Fd_CP_RDP"] * f["Fd_CP"] / 100
    f["Fd_RUP"] = f["Fd_CP_RUP"] * f["Fd_CP"] / 100
    f["Fd_dcCP"] = (f["Fd_RDP"] + f["Fd_dcRUP"]) / f["Fd_CP"] # CP digestibility calculated

    if "Fd_acCa" not in f.columns:
        f["Fd_acCa"] = None
        f["Fd_acCa"] = f.apply(lambda row: 0.4 if row["Fd_Type"] == "Forage" else row["Fd_acCa"], axis=1)
        f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_Type"] == "Concentrate" else row["Fd_acCa"], axis=1)
        f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_Category"] == "Vitamin/Mineral" else row["Fd_acCa"], axis=1)
    else:
        f["Fd_acCa"] = f.apply(lambda row: 0.4 if row["Fd_acCa"] == 0 and row["Fd_Type"] == "Forage" else row["Fd_acCa"], axis=1)
        f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_acCa"] == 0 and row["Fd_Type"] == "Concentrate" else row["Fd_acCa"], axis=1)
        f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_acCa"] == 0 and row["Fd_Category"] == "Vitamin/Mineral" else row["Fd_acCa"], axis=1)

    if "Fd_acP" not in f.columns:
        f["Fd_acP"] = None
        f["Fd_acP"] = f.apply(lambda row: 0.64 if row["Fd_Type"] == "Forage" else row["Fd_acP"], axis=1)
        f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_Type"] == "Concentrate" else row["Fd_acP"], axis=1)
        f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_Category"] == "Vitamin/Mineral" else row["Fd_acP"], axis=1)
    else:
        f["Fd_acP"] = f.apply(lambda row: 0.64 if row["Fd_acP"] == 0 and row["Fd_Type"] == "Forage" else row["Fd_acP"], axis=1)
        f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_acP"] == 0 and row["Fd_Type"] == "Concentrate" else row["Fd_acP"], axis=1)
        f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_acP"] == 0 and row["Fd_Category"] == "Vitamin/Mineral" else row["Fd_acP"], axis=1)

    # Change unit of some parameters from % of DM 

    f["Fd_CostDM"] = f["Fd_Cost"] / (f["Fd_DM"] / 100)
    f["Fd_CP_kg"] = f["Fd_CP"] / 100                                          # CP kg
    f["Fd_NDF_kg"] = f["Fd_NDF"] / 100                                        # NDF
    f["Fd_ForNDF_kg"] = np.where(f["Fd_Type"] == "Forage", f["Fd_NDF_kg"], 0) # NDF from forage type
    f["Fd_St_kg"] = f["Fd_St"] / 100                                          # Starch
    f["Fd_EE_kg"] = f["Fd_EE"] / 100                                          # EE
    f["Fd_Ca_kg"] = (f["Fd_Ca"] * f["Fd_acCa"]) / 100                         # Ca multiplied by its absoprtion coefficient
    f["Fd_P_kg"] = (f["Fd_P"] * f["Fd_acP"]) / 100                            # P multiplied by its absoprtion coefficient

    f["Fd_Type"] = np.where((f["Fd_Type"] == "Concentrate") & (f["Fd_Category"] == "Vitamin/Mineral"), "Mineral_vitamin", f["Fd_Type"])
    fat_categories = {"Fat Supplement": 1, "Fatty Acid Supplement": 1}
    f["Fd_isFat"] = f["Fd_Category"].map(fat_categories).fillna(0).astype(int)
    f["Fd_isViMi"] = np.where(f["Fd_Type"] == "Mineral_vitamin", 1, 0)
    f["Fd_isconc"] = np.where(f["Fd_Type"] == "Concentrate", 1, 0)

    # Add Placeholders for the following columns
    f["Fd_DMIn"] = 1 
    f["Fd_AFIn"] = 1 
    f["Fd_TDNact"] = 1
    f["Fd_DEact"] = 1
    f["Fd_MEact"] = 1
    f["Fd_NEl_A"] = 1
    f["Fd_NEm"] = 1
    f["Fd_NEg"] = 1

    # Moved this table to post optimization 
    #Dt = pd.DataFrame({"Ingr_Category": f["Fd_Category"], "Ingr_Type": f["Fd_Type"], "Ingr_Name": f["Fd_Name"], "Intake_DM": f["Fd_DMIn"], "Intake_AF": f["Fd_AFIn"]})

    # Check df and change it to a dictionary
    def preprocess_dataframe(df):
        for col in df.columns:
            # Convert integers to float
            if pd.api.types.is_integer_dtype(df[col]):
                df[col] = df[col].astype(np.float64)
            
            # Replace NaN values with 0
            df[col] = df[col].fillna(0)
        
        return df

    # Apply the function
    f = preprocess_dataframe(f)

    f_nd = {col: f[col].to_numpy() for col in f.columns}

    ############################################ 4. Optimization

    # Diet supply

    def rsm_diet_supply(x, f_nd, Trg_Dt_DMIn, An_MBW, An_BW, An_CW, An_MPg, An_MPp, An_MPl):

        # 1. Verifique os inputs
        #print("\n--- START diet_supply ---")
        #print(f"Inputs (x): {x}")
        
        DMI = sum(x)
        Total_tdn = (x * f_nd["Fd_TDN"]).sum()
        TotalTDN = Total_tdn/100

        TDNconc = (TotalTDN / DMI) * 100 if DMI != 0 else 0
        DMI_to_maint = TotalTDN / (0.035 * An_MBW) if TotalTDN >= (0.035 * An_MBW) else 1
        Discount = (TDNconc - ((0.18 * TDNconc - 10.3) * (DMI_to_maint - 1))) / TDNconc if TDNconc >= 60 else 1
        f_nd["Fd_TDNact"] = f_nd["Fd_TDN"] * Discount
        f_nd["Fd_DEact"] = f_nd["Fd_DE"] * Discount

        f_nd["Fd_MEact"] = np.where(
            f_nd["Fd_isViMi"] == 1, 0,  
            np.where(
                f_nd["Fd_isFat"] == 1, f_nd["Fd_DEact"],  
                np.where(
                    f_nd["Fd_EE"] >= 3,
                    1.01 * f_nd["Fd_DEact"] - 0.45 + 0.0046 * (f_nd["Fd_EE"] - 3),  
                    1.01 * f_nd["Fd_DEact"] - 0.45  
                )
            )
        )

        f_nd["Fd_MEact"] = np.clip(f_nd["Fd_MEact"], a_min=0, a_max=None)

        f_nd["Fd_NEm"] = np.where(
            f_nd["Fd_isViMi"] == 1, 0,
            np.where(
                f_nd["Fd_isFat"] == 1,
                0.8 * f_nd["Fd_MEact"],
                1.37 * (0.82 * f_nd["Fd_DEact"]) - 0.138 * (0.82 * f_nd["Fd_DEact"])**2 +
                0.0105 * (0.82 * f_nd["Fd_DEact"])**3 - 1.12
            )
        )

        f_nd["Fd_NEm"] = np.clip(f_nd["Fd_NEm"], a_min=0, a_max=None)

        f_nd["Fd_NEl_A"] = np.where(
            f_nd["Fd_isViMi"] == 1, 0,
            np.where(
                f_nd["Fd_isFat"] == 1,
                0.8 * f_nd["Fd_DEact"],
                np.where(
                    f_nd["Fd_EE"] >= 3,
                    0.703 * f_nd["Fd_MEact"] - 0.19 + ((0.097 * f_nd["Fd_MEact"] + 0.19) / 97) * (f_nd["Fd_EE"] - 3),
                    0.703 * f_nd["Fd_MEact"] - 0.19
                )
            )
        )

        f_nd["Fd_NEl_A"] = np.clip(f_nd["Fd_NEl_A"], a_min=0, a_max=None)

        f_nd["Fd_NEg"] = np.where(
            f_nd["Fd_isViMi"] == 1, 0,
            np.where(
                f_nd["Fd_isFat"] == 1,
                0.55 * f_nd["Fd_MEact"],
                1.42 * (0.82 * f_nd["Fd_DEact"]) - 0.174 * (0.82 * f_nd["Fd_DEact"])**2 +
                0.0122 * (0.82 * f_nd["Fd_DEact"])**3 - 1.65
            )
        )

        f_nd["Fd_NEg"] = np.clip(f_nd["Fd_NEg"], a_min=0, a_max=None)

        NEm_diet = (x * f_nd["Fd_NEm"]).sum()
        NEl_diet = (x * f_nd["Fd_NEl_A"]).sum()
        NEg_diet = (x * f_nd["Fd_NEg"]).sum()

        TDNact_diet = (x * (f_nd["Fd_TDNact"] / 100)).sum()
        # Not used currently, but it will be used for the alternative protein model
        f_nd["Fd_isconc"]
        PercentConc = (sum(np.multiply(x, f_nd["Fd_isconc"])) / DMI) * 100 if DMI != 0 else 0

        # Protein requirements - dinamically calculated
        CPbact = 130 * TDNact_diet
        TPbact = 0.8 * CPbact 
        MPbact = 0.85 * TPbact 
        An_MPm = (0.3 * (An_BW - An_CW)**0.6) + (4.1 * (An_BW - An_CW)**0.5) + (DMI * 1000 * 0.03 - 0.5 * (MPbact / 0.8 - MPbact)) + (0.4 * 11.8 * DMI / 0.67)
        Total_MP_Req = An_MPm + An_MPg + An_MPp + An_MPl # g/d
        RUP_diet = Total_MP_Req - MPbact 
        CP_RUP_req = RUP_diet / 0.8   
        CP_kg_req = ((CPbact + CP_RUP_req)/1000)
        CP_MP_eff = CP_kg_req * 0.8
        MPsupply = ((x * f_nd["Fd_CP_kg"]).sum()) * 0.8 # Total metabolizable protein supplied by the diet
        Total_MP_Requirement = Total_MP_Req/1000 # Convert to kg
        P1 = Total_MP_Requirement
        P2 = MPsupply
        Protein_Balance = P2 - P1 # Protein balance  
        
        # Supply calculations for other nutrients
        Supply_DMIn = sum(x)
        Supply_NEl = (x * f_nd["Fd_NEl_A"]).sum()
        #print(f"Supply_DMIn: {Supply_DMIn}, Supply_NEl: {Supply_NEl}")
        Supply_CP = (((x * f_nd["Fd_CP_kg"]).sum()) * 0.8)
        Supply_Ca = (x * f_nd["Fd_Ca_kg"]).sum()
        Supply_P = (x * f_nd["Fd_P_kg"]).sum()
        Supply_NDF = (x * f_nd["Fd_NDF_kg"]).sum()
        Supply_NDFfor = (x * f_nd["Fd_ForNDF_kg"]).sum()
        Supply_St = (x * f_nd["Fd_St_kg"]).sum()
        Supply_EE = (x * f_nd["Fd_EE_kg"]).sum()
        NEL_balance = Supply_NEl - An_NEL

        # Results as arrays for compatibility with Numba
        diet_summary_values = np.array([
            Supply_DMIn, Supply_NEl, Supply_CP, Supply_Ca, Supply_P,
            Supply_NDF, Supply_NDFfor, Supply_St, Supply_EE
        ]) # intermediate_results_values = np.array([DMI, TotalTDN, TDNconc, DMI_to_maint, Discount, TDNact_diet, NEL_balance])
        intermediate_results_values = np.array([DMI, NEL_balance, Total_MP_Requirement, Protein_Balance, CP_MP_eff])
        #print("--- END diet_supply ---\n")
        return (diet_summary_values, intermediate_results_values)

    # Calculate some values for constraints in the optimization model
    An_NDF_req = Trg_Dt_DMIn * 0.40                # Maximum 40% of NDF 
    An_NDFfor_req = Trg_Dt_DMIn * 0.19             # Minimum 19% of forage NDF 
    An_St_req = Trg_Dt_DMIn * 0.28                 # Maximum 28% of starch 
    An_EE_req = Trg_Dt_DMIn * 0.07                 # Maximum 7% of EE 

    ########################################### Optimization with pymoo

    # DietOptimizationProblem class

    xl = np.zeros(len(f_nd["Fd_Name"])) 

    xu = np.full(len(f_nd["Fd_Name"]), Trg_Dt_DMIn) 
    is_vitamin_or_mineral = np.array(f_nd["Fd_Category"]) == "Vitamin/Mineral"
    xu[is_vitamin_or_mineral] = 0.5 

    class DietOptimizationProblem(Problem):
        def __init__(self, f_nd, Trg_Dt_DMIn, An_NEL, An_Ca_req, An_P_req, An_NDF_req, An_NDFfor_req, An_St_req, An_EE_req, An_MBW, An_BW, An_CW, An_MPg, An_MPp, An_MPl):
            super().__init__(
                n_var=len(f_nd["Fd_Name"]),  
                n_obj=2,                      
                n_constr=9,                  
                xl=xl,                         
                xu=xu                          
            )
        
            self.f_nd = f_nd
            self.Trg_Dt_DMIn = Trg_Dt_DMIn
            self.An_NEL = An_NEL
            self.An_Ca_req = An_Ca_req
            self.An_P_req = An_P_req
            self.An_NDF_req = An_NDF_req
            self.An_NDFfor_req = An_NDFfor_req
            self.An_St_req = An_St_req
            self.An_EE_req = An_EE_req
            self.An_MBW = An_MBW
            self.An_BW = An_BW
            self.An_CW = An_CW
            self.An_MPg = An_MPg
            self.An_MPp = An_MPp
            self.An_MPl = An_MPl
            self.cost_history = []
            self.deviation_history = []
            self.restrictions_history = []
            self.solution_history = []

        def _evaluate(self, X, out, *args, **kwargs):
            cost = []
            total_deviation = []
            restr = []

            for i, x in enumerate(X):
                #print(f"\nSolution {i}: {x}")  
                try:
                    diet_summary_values, intermediate_results_values = rsm_diet_supply(
                        x=x,
                        f_nd=self.f_nd,
                        Trg_Dt_DMIn=self.Trg_Dt_DMIn,
                        An_MBW=self.An_MBW,
                        An_BW=self.An_BW,
                        An_CW=self.An_CW,
                        An_MPg=self.An_MPg,
                        An_MPp=self.An_MPp,
                        An_MPl=self.An_MPl
                    )
                    An_MP_req = intermediate_results_values[2]
                    # Check if the diet summary values are not None
                    if diet_summary_values is None:
                        raise ValueError(f"Error in diet_supply: Returned None for solution {i} (x={x})")
                    
                    nutrient_targets = np.array([
                        self.Trg_Dt_DMIn,     
                        self.An_NEL,  
                        An_MP_req,
                        self.An_Ca_req,       
                        self.An_P_req,
                        self.An_NDF_req,
                        self.An_NDFfor_req,
                        self.An_St_req,
                        self.An_EE_req        
                    ])
                
                    nutritional_supply = diet_summary_values[[0, 1, 2, 3, 4, 5, 6, 7, 8]]
                    DMI, NEl, MP, Ca, P, NDF, NDFfor, St, EE = nutritional_supply

                    # Obj 1: cost
                    total_cost = (x * (f_nd["Fd_CostDM"])).sum()

                    # Obj 2: nutritional deviations
                    ns = diet_summary_values[[0, 1, 2]]
                    nt = nutrient_targets[[0, 1, 2]]
                    dev = nt - ns
                    total_dev = np.sum(np.abs(dev))  # Sum of absolute deviations (lower and higher) 
                    
                    # Restrictions (G <= 0)
                    DMI_min = self.Trg_Dt_DMIn * (1.02)
                    DMI_max = self.Trg_Dt_DMIn * (1.02)
                    NEl_min = nutrient_targets[1] * 0.85
                    NEl_max = nutrient_targets[1] * (1.03)
                
                    G = [
                        DMI - DMI_max,                 
                        NEl - NEl_max,                
                        nutrient_targets[2] - MP,              
                        nutrient_targets[3] - Ca,              
                        nutrient_targets[4] - P,               
                        NDF - nutrient_targets[5],             
                        nutrient_targets[6] - NDFfor,         
                        St - nutrient_targets[6],               
                        EE - nutrient_targets[7]                
                    ]
                    # Normalize the restrictions
                    epsilon = 1e-6 # Small value to avoid division by zero
                    G_n = np.array(G) / (np.abs(np.array(nutrient_targets)) + epsilon)  # Scale by nutrient targets

                    # Add to the lists
                    cost.append(total_cost)
                    total_deviation.append(total_dev)
                    restr.append(np.array (G_n))

                    # Prints para debug
                    #print(f"Solution {i}: {x}")
                    #print(f"Total Cost: {total_cost}")
                    #print(f"Total deviation: {total_dev}")
                    #print(f"Restrictions (G): {G}")

                except Exception as e:
                    # Get the traceback
                    #print(f"Error in evaluat sol {i}: {e}")
                    #print(f"Inputs: {x}")
                    cost.append(float("inf"))  
                    total_deviation.append(float("inf"))
                    restr.append([float("inf")] * self.n_constr)

            # Output
            out["F"] = np.column_stack([cost, total_deviation])
            out["G"] = np.array(restr)

    # NSGA-II algorithm

    problem = DietOptimizationProblem(
        f_nd=f_nd,
        Trg_Dt_DMIn=Trg_Dt_DMIn,
        An_NEL=An_NEL,
        An_Ca_req=An_Ca_req,
        An_P_req=An_P_req,
        An_NDF_req=An_NDF_req,
        An_NDFfor_req=An_NDFfor_req,
        An_St_req=An_St_req,
        An_EE_req=An_EE_req,
        An_MBW=An_MBW,
        An_BW=An_BW,
        An_CW=An_CW,
        An_MPg=An_MPg,
        An_MPp=An_MPp,
        An_MPl=An_MPl
    )

    # Set the algorithm (NSGA-II)
    algorithm = NSGA2(pop_size=70,
                    sampling=FloatRandomSampling(),
                    crossover=SimulatedBinaryCrossover(prob=0.9, eta=5),  
                    mutation=PolynomialMutation(prob=0.3, eta=5),
                    eliminate_duplicates=True,
                    save_history=True) 

    # it needs to be set as TRUE since to get the results the code will loop and select the best result with minimal deviation 

    start_time = time.time()
    stop_criteria = ("n_gen", 200)
    num_workers = 7

    # Optimize
    res = minimize(
        problem,
        algorithm,
        stop_criteria,  # Number of generations
        seed=42,          # Random seed   #1 / 42
        verbose=False,     # Print the results
        workers=num_workers
    )

    end_time = time.time()

    # Results
    print("Best results:")
    print(res.X)  # Feed proportions
    print("Obj functions:")
    print(res.F)  # Total cost and total deviation
    print(f"Total time: {end_time - start_time:.2f} seconds")

    # Results

    # This model does not generate a single solution, but a set of solutions
    # Its necessary to extract the best solutions from the set
    # Thus it may not be possible to hide outputs from the optimization process

    # Extract the results (top 5 solutions)
    # I was extracting the top 5 for comparison and testing purposes, you can extract the top 1
    # This is a multiobjective optimization (cost and deviation from nutrients)
    # Thus it generated more than a single optimum solution
    # currently the final result is the TOP 1 solution, but for future its scalabe to select 
    # the top 2, 3 and so on if it satisfy the user needs and reduce costs. 

    # So, as a final comment, the top 1 is selected as the best diet now, so if you want to not 
    # select the otehrs its okay. 
    print("check")
    if res.X is not None and res.F is not None:
        proportions = res.X  # Optimized ingredient proportions
        objectives = res.F  # Objective function values

        # Create a DataFrame with the results
        ingredient_names = f_nd["Fd_Name"]  
        data = pd.DataFrame(proportions, columns=ingredient_names)

        # Add the objectives to the DataFrame
        data["Cost"] = objectives[:, 0]  
        data["Deviation"] = objectives[:, 1] 

        # ---- Extract Top 5 Solutions Based on Best deviation ----
        # Check if top5 is empty or undefined
        

        top5 = data.nsmallest(5, "Deviation")  # Get 5 best solutions best deviation 

        print("Top 5 solutions extracted.")
    else:
        print("Infeasible diet. Please review your ingredient selection.")
        return False, False
    print("Ahead")
    # Get solutions from top 5 optimized diets

    # Function to recalculate diet details and return structured table
    def calculate_ingredient_proportions(Fd_DMInp):
        
        diet_summary_values, _ = rsm_diet_supply(
            x=Fd_DMInp,
            f_nd=f_nd,
            Trg_Dt_DMIn=Trg_Dt_DMIn,
            An_MBW=An_MBW,
            An_BW=An_BW,
            An_CW=An_CW,
            An_MPg=An_MPg,
            An_MPp=An_MPp,
            An_MPl=An_MPl
        )

        # Calculate the inclusion in As-Fed
        inclusion_DM_kg = Fd_DMInp 
        inclusion_AF_kg = inclusion_DM_kg / (f_nd["Fd_DM"] / 100)
        ingredient_cost = f_nd["Fd_Cost"]
        total_cost_per_ingredient = inclusion_AF_kg * ingredient_cost  

        # Compute total real cost of the diet
        total_real_cost = np.sum(total_cost_per_ingredient) 
        
        # Create DataFrame for the solution
        df = pd.DataFrame({
            "Ingredient": f_nd["Fd_Name"],
            "Inclusion_DM_kg": inclusion_DM_kg,
            "Inclusion_AF_kg": inclusion_AF_kg,
            "Cost_per_kg": ingredient_cost,
            "Total_Cost": total_cost_per_ingredient
        })

        return df, total_real_cost

    # Recalculate for Each of the Top 5 Solutions & Store in Separate DataFrames
    diet_tables = {}  # store DataFrames
    real_costs = np.zeros(5)  # store total costs

    
    for rank, (_, row) in enumerate(top5.iterrows(), start=1):
        solution = row[ingredient_names].values  # Extract ingredient proportions

        df, total_real_cost = calculate_ingredient_proportions(solution)
        diet_tables[f"Dt_top{rank}"] = df  # Store DataFrame
        real_costs[rank - 1] = total_real_cost  # Store real cost

    Dt_top1, Dt_top2, Dt_top3, Dt_top4, Dt_top5 = diet_tables.values()

    # Compute Nutrient Profile for Each Solution

    def compute_nutrient_profile_and_targets(solution, f_nd, Trg_Dt_DMIn, An_MBW, An_BW, An_CW, An_MPg, An_MPp, An_MPl):
        # Get diet summary and MP requirement using rsm_diet_supply
        diet_summary_values, intermediate_results_values = rsm_diet_supply(
            x=solution,
            f_nd=f_nd,
            Trg_Dt_DMIn=Trg_Dt_DMIn,
            An_MBW=An_MBW,
            An_BW=An_BW,
            An_CW=An_CW,
            An_MPg=An_MPg,
            An_MPp=An_MPp,
            An_MPl=An_MPl
        )
        
        # Extract dynamically calculated MP requirement
        An_MP_req = intermediate_results_values[2]  # Total MP requirement

        # Compute supplied nutrients
        supplied_nutrients = np.array([
            solution.sum(), diet_summary_values[1], diet_summary_values[2], diet_summary_values[3], 
            diet_summary_values[4], diet_summary_values[5], diet_summary_values[6], diet_summary_values[7], diet_summary_values[8]
        ], dtype=float)
        
        # Define nutrient targets, using dynamically updated MP target
        nutrient_targets = np.array([
            Trg_Dt_DMIn, An_NEL, An_MP_req, None, None, None, None, None, None
        ])

        nutrient_min_targets = np.array([
            None, None, None, An_Ca_req, An_P_req, None, An_NDFfor_req, None, None
        ])

        nutrient_max_targets = np.array([
            None, None, None, None, None, An_NDF_req, None, An_St_req, An_EE_req
        ])

        return supplied_nutrients, nutrient_targets, nutrient_min_targets, nutrient_max_targets

    # Function to Generate Nutrient Comparison Table
    nutrient_labels = ["Total Feed Intake", "Energy", "Protein", "Calcium", "Phosphorus", "Fiber", "Fiber (forage)", "Starch", "Fat"]
    def generate_nutrient_comparison(solution, solution_name,nutrient_labels):
        supplied_nutrients, nutrient_targets, min_targets, max_targets = compute_nutrient_profile_and_targets(
            solution, f_nd, Trg_Dt_DMIn, An_MBW, An_BW, An_CW, An_MPg, An_MPp, An_MPl
        )

        # Nutrient labels
        # nutrient_labels = ["DMI", "NEl", "MP", "Calcium", "Phosphorus", "NDF", "NDF (forage)", "Starch", "EE"]
        
        # Create a DataFrame
        df = pd.DataFrame({
            "Nutrient": nutrient_labels,
            "Supplied": supplied_nutrients,
            "Target": nutrient_targets,
            "Min Target": min_targets,
            "Max Target": max_targets
        })

        # Balance Calculation Logic
        balance = []
        for supply, min_t, max_t, target in zip(df["Supplied"], df["Min Target"], df["Max Target"], df["Target"]):
            if pd.notna(min_t) and supply < min_t:
                balance.append(supply - min_t)  # Negative balance if below min
            elif pd.notna(max_t) and supply > max_t:
                balance.append(supply - max_t)  # Positive balance if above max
            elif pd.notna(target) and pd.isna(min_t) and pd.isna(max_t):
                balance.append(supply - target)  # Deviation from target only if no min/max exist
            elif pd.isna(min_t) and pd.isna(max_t) and pd.isna(target):
                balance.append("No constraint")  # No specific requirement for this nutrient
            else:
                balance.append("Within range")

        
        # Add balance column
        df["Balance"] = balance

        # Replace NaN values with "--" for display purposes
        df = df.fillna(np.nan)

        return df

    # Compute Nutrient Comparison for Top 5 Solutions & Store in Separate DataFrames
    nutrient_tables = {}
    warnings_dict = {}

    for rank in range(1, 6):
        solution_name = f"Best Deviation Solution (Rank {rank})"
        solution = diet_tables[f"Dt_top{rank}"]["Inclusion_DM_kg"].values  # Extract DM inclusions

        df_nutrient = generate_nutrient_comparison(solution, solution_name, nutrient_labels)
        nutrient_tables[f"Nutr_supply_top{rank}"] = df_nutrient  # Store DataFrame

           
        warnings = generate_diet_warnings(
            supplied_nutrients=df_nutrient["Supplied"].values,
            nutrient_targets=df_nutrient["Target"].values,
            min_targets=df_nutrient["Min Target"].values,
            max_targets=df_nutrient["Max Target"].values,
            nutrient_labels=nutrient_labels
        )
        
        # Print warnings for debugging
        print(f"\nWarnings for {solution_name}:")
        for msg in warnings:
            print(msg)
        warnings_dict[f"Warnings_top{rank}"] = warnings
    # Extract only nutrient supply tables
    nutrient_tables_list = [nutrient_tables[f"Nutr_supply_top{rank}"] for rank in range(1, 6)]
    # Store warnings in a separate list if needed
    warnings_list = [warnings_dict[f"Warnings_top{rank}"] for rank in range(1, 6)]
    

    # Ca and P in the following data frames present the supply values adjusted for their correspondent absorption coefficients
    # So the total amount of minerals in the diet will be a little higher

    # Access the Stored DataFrames
    Nutr_supply_top1, Nutr_supply_top2, Nutr_supply_top3, Nutr_supply_top4, Nutr_supply_top5 = nutrient_tables.values()

    # Store Nutrient Supply DataFrames in a List for Easy Comparison
    nutrient_tables_list = [Nutr_supply_top1, Nutr_supply_top2, Nutr_supply_top3, Nutr_supply_top4, Nutr_supply_top5]

    # Create Final DataFrame `Dt`                                                   
    print("🚀 ~ f_nd:", f_nd)
    print("🚀 ~ Dt_top1:", Dt_top1)
    Dt = pd.DataFrame({
        "Ingr_Category": f_nd["Fd_Category"],
        "Ingr_Type": f_nd["Fd_Type"],
        "Ingr_Name": f_nd["Fd_Name"],
        "Intake_DM": Dt_top1["Inclusion_DM_kg"],
        "Intake_AF": Dt_top1["Inclusion_AF_kg"],
        "Cost_per_kg": Dt_top1["Cost_per_kg"],
        "Ingr_Cost": Dt_top1["Total_Cost"],
        "Fd_code": f["Fd_code"],
                # "price": f["Fd_Cost"],
    })

    Dt['DM'] = f['Fd_DM']
    # Sum the nutrient intake for the diet
    Dt_DMInSum = Dt["Intake_DM"].sum() 
    Dt_AFIn = Dt["Intake_AF"].sum()

    # Calculate the AF and DM ingredient inclusion rates
    Dt['Dt_DMInp'] = Dt['Intake_DM'] / Dt_DMInSum * 100
    Dt['Dt_AFInp'] = Dt['Intake_AF'] / Dt_AFIn * 100

    # Vector to get the variable names desired                                                              # removed some columns in kg to not mess up the calculations 
    Col_names = [
    "Fd_ADF", "Fd_NDF", "Fd_Lg", "Fd_CP", "Fd_RDP", "Fd_RUP", "Fd_St", "Fd_EE", "Fd_FA", "Fd_Ash", "Fd_NFC", "Fd_TDN", "Fd_Ca", "Fd_P", "Fd_Na", "Fd_K"
    ]

    # Rename variables names
    def rename_variable(variable_name):
        new_name = variable_name.replace("Fd_", "Dt_") + "In"
        return new_name

    # Calculate nutrient intake in Kg/d
    for nutrient in Col_names:
        renamed_nutrient = rename_variable(nutrient)
        Dt[renamed_nutrient] = Dt['Intake_DM'] * f[nutrient] / 100

    # Loop to replace NA and negative numbers with 0
    def replace_na_and_negatives(col):
        if col.dtype.kind in 'biufc':  # Check if the column is of numeric type
            col = col.apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        return col

    Dt = Dt.apply(replace_na_and_negatives)

    column_sums = Dt.select_dtypes(include=[np.number]).sum()
    Dt_kg = pd.concat([Dt, pd.DataFrame([column_sums])], ignore_index=True)
    Dt_kg.iloc[-1, Dt_kg.columns.get_loc('Ingr_Name')] = 'Total'    # remove sum of columns Cost per kg and DM 

    # Calculate Dt dataframe in % of DM
    Dt_proportions = Dt[['Ingr_Type', "Ingr_Category", 'Ingr_Name', 'Intake_DM', 'Intake_AF', 'Dt_DMInp', 'Dt_AFInp', 'Ingr_Cost',"Fd_code", "Cost_per_kg"]].copy()      ######## Had to change the name from previous version

    # Calculate nutrient intake in %
    for nutrient in Col_names:
        renamed_nutrient = rename_variable(nutrient)
        Dt_proportions[renamed_nutrient] = Dt[renamed_nutrient] / Dt_DMInSum * 100

    # Loop to replace NA and negative numbers with 0
    Dt_proportions = Dt_proportions.apply(replace_na_and_negatives)

    column_sums = Dt_proportions.select_dtypes(include=[np.number]).sum()
    Dt_proportions = pd.concat([Dt_proportions, pd.DataFrame([column_sums])], ignore_index=True)
    Dt_proportions.iloc[-1, Dt_proportions.columns.get_loc('Ingr_Name')] = 'Total'

    # Predict voluntary water intake, kg/d
    selected_column_sums = Dt[['Dt_NaIn', 'Dt_KIn', 'Dt_CPIn', 'Dt_FAIn', 'Dt_NDFIn']].sum()

    # Nutrient concentrations in the diet
    Dt_DMprop = Dt_DMInSum / Dt_AFIn * 100
    Dt_NaSum = selected_column_sums['Dt_NaIn']/(Dt_DMInSum) * 100
    Dt_KSum = selected_column_sums['Dt_KIn']/(Dt_DMInSum) * 100
    Dt_CPSum = selected_column_sums['Dt_CPIn']/Dt_DMInSum * 100
    Dt_FASum = selected_column_sums['Dt_FAIn']
    Dt_dNDFSum = selected_column_sums['Dt_NDFIn']

    An_WaIn_Lact = -91.1 + 2.93 * Dt_DMInSum + 0.61 * Dt_DMprop + 0.062 * (Dt_NaSum / 0.023 + Dt_KSum / 0.039) * 10 + 2.49 * Dt_CPSum + 0.76 * Env_TempCurr
    An_WaIn_Dry = 1.16 * Dt_DMInSum + 0.23 * Dt_DMprop + 0.44 * Env_TempCurr + 0.061 * (Env_TempCurr - 16.4) ** 2
    An_WaIn = An_WaIn_Lact if An_StatePhys == "Lactating Cow" else An_WaIn_Dry
    An_WaIn = An_WaIn_Dry if An_StatePhys == "Heifer" else An_WaIn

    # Edit the Dt_proportions dataframe for report
    Dt_proportions = Dt_proportions.round(2).rename(columns={
        'Ingr_Type': 'Ingr_Type',
        'Ingr_Name': 'Ingr_Name',
        'Intake_DM': 'Intake_DM_kg.d',
        'Intake_AF': 'Intake_AF_kg.d',
        'Dt_DMInp': 'DMI',
        'Ingr_Cost': 'Cost',
        'Dt_ADFIn': 'ADF_DM',
        'Dt_NDFIn': 'NDF_DM',
        'Dt_LgIn': 'Lignin_DM',
        'Dt_CPIn': 'Crude_Protein_DM',
        'Dt_StIn': 'Starch_DM',
        'Dt_EEIn': 'Fat_DM',
        'Dt_FAIn': 'Fatty_Acids_DM',
        'Dt_AshIn': 'Ash_DM',
        'Dt_NFCIn': 'NFC_DM',
        'Dt_TDNIn': 'TDN_DM',
        'Dt_CaIn': 'Calcium_DM',
        'Dt_PIn': 'Phosphorus_DM',
        'Dt_NaIn': 'Sodium_DM',
        'Dt_KIn': 'Potassium_DM'
    })

    Dt_proportions = Dt_proportions.drop(columns=["DMI",'Dt_AFInp'])

    # Filter and add a Total row for Forage
    Dt_forages = Dt_proportions[Dt_proportions['Ingr_Type'] == 'Forage']
    forage_total = Dt_forages.sum(numeric_only=True)  # Sum numeric columns
    forage_total['Ingr_Type'] = 'Forage'
    forage_total['Ingr_Name'] = 'Total'
    Dt_forages = pd.concat([Dt_forages, forage_total.to_frame().T], ignore_index=True)

    # Filter and add a Total row for Concentrate
    Dt_concentrates = Dt_proportions[(Dt_proportions['Ingr_Type'] == 'Concentrate') | 
                                    (Dt_proportions['Ingr_Type'] == 'Mineral_vitamin')]
    concentrate_total = Dt_concentrates.sum(numeric_only=True)  # Sum numeric columns
    concentrate_total['Ingr_Type'] = 'Concentrate'
    concentrate_total['Ingr_Name'] = 'Total'
    Dt_concentrates = pd.concat([Dt_concentrates, concentrate_total.to_frame().T], ignore_index=True)

    Dt_results = Dt_proportions[['Fd_code', 'Ingr_Type', "Ingr_Category", 'Ingr_Name', 'Intake_DM_kg.d', 'Intake_AF_kg.d', 'Cost',"Cost_per_kg"]]

    # Changed since slight because I'm no longer getting Dt_summary - in R I used to print tables, but in Python I was only returning values from the diet supply function

    # Extract best solution returned values from diet supply function
    best_solution_DM = diet_tables["Dt_top1"]["Inclusion_DM_kg"].values 

    # Recompute Diet Summary and Intermediate Results
    diet_summary_values, intermediate_results_values = rsm_diet_supply(
        x=best_solution_DM,  # Pass the best diet solution
        f_nd=f_nd,
        Trg_Dt_DMIn=Trg_Dt_DMIn,
        An_MBW=An_MBW,
        An_BW=An_BW,
        An_CW=An_CW,
        An_MPg=An_MPg,
        An_MPp=An_MPp,
        An_MPl=An_MPl
    )

    # Ration Evaluation
    Ration_Evaluation = pd.DataFrame({
        "Parameter": ["DMI", "NEL", "MP", "Ca", "P"],
        
        # Requirements (from target values)
        "Requirement": [Trg_Dt_DMIn, An_NEL, intermediate_results_values[2], An_Ca_req, An_P_req],
        
        # Supply (from diet summary and ingredient composition)
        "Supply": [
            diet_summary_values[0],  # DMI
            diet_summary_values[1],  # NEL
            diet_summary_values[2],  # MP
            Dt_top1["Inclusion_DM_kg"].mul(f["Fd_Ca"]/100).sum(),  # Ca from diet
            Dt_top1["Inclusion_DM_kg"].mul(f["Fd_P"]/100).sum()    # P from diet
        ],
        
        # Balance (Supply - Requirement)
        "Balance": [
            diet_summary_values[0] - Trg_Dt_DMIn,  
            diet_summary_values[1] - An_NEL,  
            diet_summary_values[2] - intermediate_results_values[2],  
            Dt_top1["Inclusion_DM_kg"].mul(f["Fd_Ca"]/100).sum() - An_Ca_req,  
            Dt_top1["Inclusion_DM_kg"].mul(f["Fd_P"]/100).sum() - An_P_req  
        ]
    }).round(2)

    # Animal inputs
    an = pd.DataFrame({
        "Diet_ID": [DietID],
        "Breed": [An_Breed],
        "Animal_Type": [An_StatePhys],
        "Animal_BW": [An_BW],
        "Body_Condition_Score": [An_BCS],
        "Daily_BW_Gain_kg": [Trg_FrmGain],
        "Mature_BW": [An_BW_mature],
        "Parity": [An_Parity],
        "Days_in_Milk": [An_LactDay],
        "Days_of_Pregnancy": [An_GestDay],
        "Current_Temperature_C": [Env_TempCurr],
        "Distance_Walked_km": [Env_Dist_km],
        "Topography": [Env_Topo],
        "Milk_Production_L": [Trg_MilkProd_L],
        "Milk_True_Protein_Content": [Trg_MilkTPp],
        "Milk_Fat_Content": [Trg_MilkFatp]
    }).T
    units = ["", "", "", "Kg", "", "kg/day", "Kg", "", "days", "days", "°C", "km", "meters", "L", "%", "%"]
    Animal_inputs = an
    Animal_inputs['Unit'] = units

    # Requirements
    An_Requirements = pd.DataFrame({
        "Dry_Matter_Intake": [Trg_Dt_DMIn],
        "Intake_%BW": [Dt_DMIn_BW],
        "Net_Energy_(NEL)": [An_NEL],
        "Metabolizable_Protein_(MP)": [intermediate_results_values[2]],
        "Crude_Protein": [(intermediate_results_values[2]/0.8)],
        "Water_Intake": [An_WaIn],
        "Calcium": [An_Ca_r],
        "Phosphorus": [An_P_r],
        "Magnesium": [An_Mg_req],
        "Sodium": [An_Na_req],
        "Chlorine": [An_Cl_req],
        "Potassium": [An_K_req],
        "Sulfur": [An_S_req],
        "Cobalt": [An_Co_req],
        "Chromium": [An_Cu_req],
        "Iodine": [An_I_req],
        "Iron": [An_Fe_req],
        "Manganese": [An_Mn_req],
        "Selenium": [An_Se_req],
        "Zinc": [An_Zn_req],
        "Vitamin_A": [An_VitA_req],
        "Vitamin_D": [An_VitD_req],
        "Vitamin_E": [An_VitE_req]
    }).T
    units = ["kg/d", "%BW", "Mcal/g", "kg/d", "kg/d", "L/d", "g/d", "g/d", "g/d", "g/d", "g/d", "g/d", "g/d", "mg/d", "mg/d", "mg/d", "mg/d", "mg/d", "mg/d", "mg/d", "IU/d", "IU/d", "IU/d"]
    An_Requirements['Unit'] = units
    An_Requirements = An_Requirements.round(2)

    # Methane Emission Report
    ASH = (Dt['Dt_AshIn'] * Dt['Intake_DM']).sum()
    NDF = (Dt['Dt_NDFIn'] * Dt['Intake_DM']).sum()
    CP = (Dt['Dt_CPIn'] * Dt['Intake_DM']).sum()
    EE = (Dt['Dt_EEIn'] * Dt['Intake_DM']).sum()

    SR = 100 - ASH - NDF - CP - EE
    Dt_GE = 0.263 * CP + 0.522 * EE + 0.198 * NDF + 0.160 * SR
    GEI = Dt_GE * Dt['Intake_DM'].sum()
    CH4 = -9.311 + 0.042 * GEI + 0.094 * NDF - 0.381 * EE + 0.008 * An_BW + 1.621 * Trg_MilkFatp

    # Methane metrics
    CH4_Mcal = CH4 / 4.184
    CH4_grams = CH4 / 55.5 * 1000
    CH4_grams_per_kg_DMI = CH4_grams / Trg_Dt_DMIn
    MCR = (CH4 / GEI) * 100

    # Results
    print("Methane Emission Report:")
    print(f"CH4 (MJ/day): {CH4}")
    print(f"CH4 (Mcal/day): {CH4_Mcal}")
    print(f"CH4 (g/day): {CH4_grams}")
    print(f"CH4 (g/kg DMI): {CH4_grams_per_kg_DMI}")
    print(f"Methane Conversion Rate (%): {MCR}")

    def interpret_mcr(mcr):
        if mcr < 3.5:
            return "Extremely Low"
        elif mcr < 4.5:
            return "Very Low"
        elif mcr < 5.5:
            return "Low"
        elif mcr < 6.5:
            return "Average"
        elif mcr < 7.5:
            return "Average"
        elif mcr < 8.5:
            return "Very High"
        elif mcr < 9.5:
            return "Extremely High"
        else:
            return "Above Normal Range"

    MCR_message = interpret_mcr(MCR)

    # Combine results into a data frame
    Methane_Report = pd.DataFrame({
        "Metric": [
            "Methane Emission (MJ/day)",
            "Methane Emission (Mcal/day)",
            "Methane Emission (g/day)",
            "Methane Emission (g/kg DMI)",
            "Methane Conversion Rate (%)",
            "MCR Range"
        ],
        "Value": [
            round(CH4, 2),
            round(CH4_Mcal, 2),
            round(CH4_grams, 2),
            round(CH4_grams_per_kg_DMI, 2),
            round(MCR, 2),
            MCR_message
        ]
    })
    print("Dt_results",Dt_results)
    return Dt_results,Methane_Report


from middleware.logging_config import get_logger, log_calculation_start, log_calculation_step, log_error

# Initialize logger for animal router
animal_logger = get_logger("animal.router")

import uuid
from datetime import datetime






@router.get("/unique-feed-type/{country_id}/{user_id}", response_model=List[str])
async def get_unique_feed_types(
    country_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch all unique feed types from both standard feeds and user's custom feeds
    filtered by country and user.
    
    - **country_id**: Country UUID to filter feeds by
    - **user_id**: User UUID to filter custom feeds by
    """
    try:
        animal_logger.info(f"Feed type request | Country ID: {country_id} | User ID: {user_id}")
        
        # Use SQL UNION for better performance - combines both standard and custom feeds
        
        # Query 1: Standard feeds from 'feeds' table
        standard_feeds_query = (
            db.query(Feed.fd_type)
            .filter(Feed.fd_country_id == country_id)
            .distinct()
        )
        
        # Query 2: Custom feeds from 'custom_feeds' table
        custom_feeds_query = (
            db.query(CustomFeed.fd_type)
            .filter(
                CustomFeed.fd_country_id == country_id,
                CustomFeed.user_id == user_id
            )
            .distinct()
        )
        
        # Combine both queries using UNION
        combined_query = standard_feeds_query.union(custom_feeds_query)
        
        # Execute the combined query
        unique_feed_types = combined_query.all()
        
        # Extract the unique feed types from the result tuples and sort
        unique_feed_types = [feed_type[0] for feed_type in unique_feed_types if feed_type[0] is not None]
        unique_feed_types = sorted(unique_feed_types)
        
        animal_logger.info(f"Feed types returned | Country: {country_id} | User: {user_id} | Types: {unique_feed_types}")
        return unique_feed_types
        
    except SQLAlchemyError as e:
        animal_logger.error(f"Database error in get_unique_feed_types | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        animal_logger.error(f"Unexpected error in get_unique_feed_types | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve feed types: {str(e)}")


# PDF Report Endpoints
@router.post("/generate-pdf-report/", response_model=PDFReportResponse)
async def generate_pdf_report(
    simulation_id: str,
    user_id: str,
    api_response: dict,
    db: Session = Depends(get_db)
):
    """
    Generate and store a PDF report for a diet recommendation
    
    Args:
        case_id: Case identifier
        user_id: User ID who requested the report
        api_response: Complete API response from diet recommendation
        db: Database session
        
    Returns:
        PDFReportResponse: Success status and report metadata
    """
    try:
        animal_logger.info(f"Generating PDF report for simulation_id: {simulation_id}, user_id: {user_id}")
        
        # Initialize PDF service
        pdf_service = PDFService(db)
        
        # Generate and store PDF
        report = pdf_service.generate_and_store_pdf(api_response, user_id, simulation_id)
        
        if report:
            # Get metadata
            metadata_dict = pdf_service.get_report_metadata(str(report.id), user_id)
            
            # Convert dict to PDFReportMetadata object
            metadata = PDFReportMetadata(**metadata_dict) if metadata_dict else None
            
            return PDFReportResponse(
                success=True,
                message="PDF report generated and stored successfully",
                report_id=str(report.id),
                report_metadata=metadata
            )
        else:
            return PDFReportResponse(
                success=False,
                message="Failed to generate PDF report"
            )
            
    except Exception as e:
        animal_logger.error(f"Error generating PDF report: {str(e)}")
        return PDFReportResponse(
            success=False,
            message=f"Error generating PDF report: {str(e)}"
        )

@router.get("/pdf-reports/{user_id}", response_model=PDFReportList)
async def get_user_pdf_reports(
    user_id: str,
    limit: int = Query(50, description="Maximum number of reports to return"),
    db: Session = Depends(get_db)
):
    """
    Get all PDF reports for a specific user
    
    Args:
        user_id: User ID
        limit: Maximum number of reports to return
        db: Database session
        
    Returns:
        PDFReportList: List of report metadata
    """
    try:
        animal_logger.info(f"Retrieving PDF reports for user_id: {user_id}")
        
        # Initialize PDF service
        pdf_service = PDFService(db)
        
        # Get reports
        reports = pdf_service.get_reports_by_user(user_id, limit)
        
        # Convert to metadata format
        report_metadata = []
        for report in reports:
            metadata_dict = pdf_service.get_report_metadata(str(report.id), user_id)
            if metadata_dict:
                # Convert dict to PDFReportMetadata object
                metadata = PDFReportMetadata(**metadata_dict)
                report_metadata.append(metadata)
        
        return PDFReportList(
            reports=report_metadata,
            total_count=len(report_metadata)
        )
        
    except Exception as e:
        animal_logger.error(f"Error retrieving PDF reports: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving PDF reports: {str(e)}"
        )

@router.get("/pdf-report/{report_id}/{user_id}")
async def download_pdf_report(
    report_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Download a specific PDF report
    
    Args:
        report_id: Report ID
        user_id: User ID (for security)
        db: Database session
        
    Returns:
        FileResponse: PDF file
    """
    try:
        animal_logger.info(f"Downloading PDF report {report_id} for user_id: {user_id}")
        
        # Initialize PDF service
        pdf_service = PDFService(db)
        
        # Get report
        report = pdf_service.get_report_by_id(report_id, user_id)
        
        if not report:
            raise HTTPException(
                status_code=404,
                detail="Report not found or access denied"
            )
        
        # Return PDF file
        from fastapi.responses import Response
        return Response(
            content=report.pdf_data,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={report.file_name}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error downloading PDF report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error downloading PDF report: {str(e)}"
        )

@router.delete("/pdf-report/{report_id}/{user_id}")
async def delete_pdf_report(
    report_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a specific PDF report
    
    Args:
        report_id: Report ID
        user_id: User ID (for security)
        db: Database session
        
    Returns:
        dict: Success message
    """
    try:
        animal_logger.info(f"Deleting PDF report {report_id} for user_id: {user_id}")
        
        # Initialize PDF service
        pdf_service = PDFService(db)
        
        # Delete report
        success = pdf_service.delete_report(report_id, user_id)
        
        if success:
            return {"message": "Report deleted successfully"}
        else:
            raise HTTPException(
                status_code=404,
                detail="Report not found or access denied"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error deleting PDF report: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting PDF report: {str(e)}"
        )

@router.get("/pdf-report-metadata/{report_id}/{user_id}", response_model=PDFReportMetadata)
async def get_pdf_report_metadata(
    report_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Get metadata for a specific PDF report (without the PDF data)
    
    Args:
        report_id: Report ID
        user_id: User ID (for security)
        db: Database session
        
    Returns:
        PDFReportMetadata: Report metadata
    """
    try:
        animal_logger.info(f"Retrieving metadata for PDF report {report_id}")
        
        # Initialize PDF service
        pdf_service = PDFService(db)
        
        # Get metadata
        metadata_dict = pdf_service.get_report_metadata(report_id, user_id)
        
        if not metadata_dict:
            raise HTTPException(
                status_code=404,
                detail="Report not found or access denied"
            )
        
        # Convert dict to PDFReportMetadata object
        metadata = PDFReportMetadata(**metadata_dict)
        return metadata
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error retrieving PDF report metadata: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error retrieving PDF report metadata: {str(e)}"
        )
@router.get("/unique-feed-category")
async def get_unique_feed_categories(
    feed_type: str = Query(..., description="Feed type to filter categories by"),
    country_id: str = Query(..., description="Country UUID to filter feeds by"),
    user_id: str = Query(..., description="User UUID to filter custom feeds by"),
    db: Session = Depends(get_db)
):
    """
    Fetch all unique feed categories from both standard feeds and user's custom feeds
    filtered by feed type, country and user.
    
    - **feed_type**: Feed type to filter categories by
    - **country_id**: Country UUID to filter feeds by
    - **user_id**: User UUID to filter custom feeds by
    """
    try:
        animal_logger.info(f"Feed category request | Feed Type: {feed_type} | Country ID: {country_id} | User ID: {user_id}")
        
        # Use SQL UNION for better performance - combines both standard and custom feeds
        
        # Query 1: Standard feeds from 'feeds' table
        standard_feeds_query = (
            db.query(Feed.fd_category)
            .filter(
                Feed.fd_type == feed_type,
                Feed.fd_country_id == country_id
            )
            .distinct()
        )
        
        # Query 2: Custom feeds from 'custom_feeds' table
        custom_feeds_query = (
            db.query(CustomFeed.fd_category)
            .filter(
                CustomFeed.fd_type == feed_type,
                CustomFeed.fd_country_id == country_id,
                CustomFeed.user_id == user_id
            )
            .distinct()
        )
        
        # Combine both queries using UNION
        combined_query = standard_feeds_query.union(custom_feeds_query)
        
        # Execute the combined query
        unique_feed_categories = combined_query.all()
        
        # Extract the unique feed categories from the result tuples and sort
        unique_feed_categories_list = [category[0] for category in unique_feed_categories if category[0] is not None]
        unique_feed_categories_list = sorted(unique_feed_categories_list)
        
        # Maintain the original response format
        response = {"feed_type": feed_type, "unique_feed_categories": unique_feed_categories_list}
        
        animal_logger.info(f"Feed categories returned | Feed Type: {feed_type} | Country: {country_id} | User: {user_id} | Categories: {unique_feed_categories_list}")
        return response
        
    except SQLAlchemyError as e:
        animal_logger.error(f"Database error in get_unique_feed_categories | Feed Type: {feed_type} | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        animal_logger.error(f"Unexpected error in get_unique_feed_categories | Feed Type: {feed_type} | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve feed categories: {str(e)}")


@router.get("/feed-name", response_model=List[FeedDescriptionResponse])
async def get_feed_names(
    feed_type: str = Query(..., description="Feed type to filter feeds by"),
    feed_category: str = Query(..., description="Feed category to filter feeds by"),
    country_id: str = Query(..., description="Country UUID to filter feeds by"),
    user_id: str = Query(..., description="User UUID to filter custom feeds by"),
    db: Session = Depends(get_db)
):
    """
    Fetch all unique feed names from both standard feeds and user's custom feeds
    filtered by feed type, feed category, country and user.
    
    - **feed_type**: Feed type to filter feeds by
    - **feed_category**: Feed category to filter feeds by
    - **country_id**: Country UUID to filter feeds by
    - **user_id**: User UUID to filter custom feeds by
    """
    try:
        # FastAPI automatically handles URL decoding for query parameters
        # No manual decoding needed
        
        animal_logger.info(f"Feed names request | Feed Type: {feed_type} | Category: {feed_category} | Country ID: {country_id} | User ID: {user_id}")
        
        # Use SQL UNION for better performance - combines both standard and custom feeds
        
        # Query 1: Standard feeds from 'feeds' table
        standard_feeds_query = (
            db.query(
                Feed.fd_code, Feed.id, Feed.fd_name, Feed.fd_category, Feed.fd_type
            )
            .filter(
                Feed.fd_type == feed_type,           # Filter by feed type
                Feed.fd_category == feed_category,   # Filter by feed category
                Feed.fd_country_id == country_id     # Filter by country
            )
            .distinct()
        )
        
        # Query 2: Custom feeds from 'custom_feeds' table
        custom_feeds_query = (
            db.query(
                CustomFeed.fd_code, CustomFeed.id, CustomFeed.fd_name, 
                CustomFeed.fd_category, CustomFeed.fd_type
            )
            .filter(
                CustomFeed.fd_type == feed_type,           # Filter by feed type
                CustomFeed.fd_category == feed_category,   # Filter by feed category
                CustomFeed.fd_country_id == country_id,    # Filter by country
                CustomFeed.user_id == user_id              # Filter by user
            )
            .distinct()
        )
        
        # Execute queries separately to avoid UNION type mismatch
        standard_feeds = standard_feeds_query.all()
        custom_feeds = custom_feeds_query.all()
        
        # Combine results manually
        feed_names = standard_feeds + custom_feeds
        
        # Execute the combined query
        # feed_names = combined_query.all()  # Removed this line since we're not using UNION anymore
        
        # Convert result into a response format with UUID as strings
        feed_names_list = [
            {
                "feed_cd": feed[0],         # fd_code (for display)
                "row_id": idx + 1,          # Use index as row_id
                "feed_uuid": str(feed[1]),  # feed.id (for identification)
                "feed_name": feed[2],       # fd_name (feed name)
                "feed_category": feed[3],   # fd_category (feed category)
                "feed_type": feed[4]        # fd_type (feed type)
            }
            for idx, feed in enumerate(feed_names)
        ]
        feed_names_list = sorted(feed_names_list, key=lambda x: x["feed_name"])
        
        # Log the feed names returned
        feed_names_log = [f"{feed['feed_name']} ({feed['feed_type']})" for feed in feed_names_list[:5]]  # Log first 5 feeds
        if len(feed_names_list) > 5:
            feed_names_log.append(f"... and {len(feed_names_list) - 5} more")
        animal_logger.info(f"Feed names returned | Feed Type: {feed_type} | Category: {feed_category} | Country: {country_id} | User: {user_id} | Feeds: {feed_names_log} | Total: {len(feed_names_list)}")
        
        return feed_names_list
        
    except SQLAlchemyError as e:
        animal_logger.error(f"Database error in get_feed_names | Feed Type: {feed_type} | Category: {feed_category} | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        animal_logger.error(f"Unexpected error in get_feed_names | Feed Type: {feed_type} | Category: {feed_category} | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve feed names: {str(e)}")

@router.get("/feed-details/{user_id}/{feed_id}", response_model=FeedDetailsResponse)
async def get_feed_details(
    user_id: str,
    feed_id: str,
    db: Session = Depends(get_db)
):
    """
    Get detailed feed information by feed ID for editing nutrient values
    
    - **user_id**: User UUID (required for authorization on custom feeds)
    - **feed_id**: Feed UUID to retrieve details for
    
    Returns complete feed information including all nutrient values for editing in the Android app.
    Supports both standard feeds (public) and custom feeds (user-authorized).
    """
    try:
        animal_logger.info(f"Feed details request | User ID: {user_id} | Feed ID: {feed_id}")
        
        # Validate UUID format for feed_id
        try:
            uuid.UUID(feed_id)
        except ValueError:
            animal_logger.warning(f"Invalid feed_id format: {feed_id}")
            raise HTTPException(
                status_code=400, 
                detail="Invalid feed_id format. Must be a valid UUID."
            )
        
        # Step 1: First try to find in standard feeds table (public access)
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        is_custom_feed = False
        
        # Step 2: If not found in standard feeds, check custom feeds table with user authorization
        if not feed:
            custom_feed = db.query(CustomFeed).filter(
                CustomFeed.id == feed_id,
                CustomFeed.user_id == user_id  # Authorization check - only owner can access
            ).first()
            
            if custom_feed:
                feed = custom_feed
                is_custom_feed = True
                animal_logger.info(f"Custom feed found | Feed: {feed.fd_name} | Owner: {user_id}")
            else:
                animal_logger.warning(f"Feed not found in either table | Feed ID: {feed_id} | User: {user_id}")
                raise HTTPException(
                    status_code=404,
                    detail="Feed not found"
                )
        
        # Get country information if available
        country_name = None
        if feed.fd_country_id:
            country = db.query(CountryModel).filter(CountryModel.id == feed.fd_country_id).first()
            country_name = country.name if country else None
        
        # Create response object based on feed type
        if is_custom_feed:
            # Handle CustomFeed model fields
            feed_details = FeedDetailsResponse(
                feed_id=str(feed.id),
                fd_code=feed.fd_code,  # ✅ Fixed: using exact database column name
                fd_name=feed.fd_name,  # ✅ Fixed: using exact database column name
                fd_type=feed.fd_type,  # ✅ Fixed: using exact database column name
                fd_category=feed.fd_category,  # ✅ Fixed: using exact database column name
                fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,  # ✅ Fixed: using exact database column name
                fd_country_name=country_name,  # ✅ Fixed: using exact database column name
                fd_country_cd=feed.fd_country_cd,  # ✅ Fixed: using exact database column name
                # Nutritional fields - using exact database column names
                fd_dm=safe_float(feed.fd_dm),  # ✅ Fixed: using exact database column name
                fd_ash=safe_float(feed.fd_ash),  # ✅ Fixed: using exact database column name
                fd_cp=safe_float(feed.fd_cp),  # ✅ Fixed: using exact database column name
                fd_ee=safe_float(feed.fd_ee),  # ✅ Fixed: using exact database column name
                fd_st=safe_float(feed.fd_st),  # ✅ Fixed: using exact database column name
                fd_ndf=safe_float(feed.fd_ndf),  # ✅ Fixed: using exact database column name
                fd_adf=safe_float(feed.fd_adf),  # ✅ Fixed: using exact database column name
                fd_lg=safe_float(feed.fd_lg),  # ✅ Fixed: using exact database column name
                # Additional nutritional fields - using exact database column names
                fd_ndin=safe_float(feed.fd_ndin),  # ✅ Fixed: using exact database column name
                fd_adin=safe_float(feed.fd_adin),  # ✅ Fixed: using exact database column name
                fd_ca=safe_float(feed.fd_ca),  # ✅ Fixed: using exact database column name
                fd_p=safe_float(feed.fd_p),  # ✅ Fixed: using exact database column name
                fd_cf=safe_float(feed.fd_cf),  # ✅ Fixed: using exact database column name
                fd_nfe=safe_float(feed.fd_nfe),  # ✅ Fixed: using exact database column name
                fd_hemicellulose=safe_float(feed.fd_hemicellulose),  # ✅ Fixed: using exact database column name
                fd_cellulose=safe_float(feed.fd_cellulose),  # ✅ Fixed: using exact database column name
                # Metadata fields - using exact database column names
                fd_orginin=feed.fd_orginin,  # ✅ Fixed: using exact database column name
                fd_ipb_local_lab=feed.fd_ipb_local_lab,  # ✅ Fixed: using exact database column name
                created_at=feed.created_at,
                updated_at=feed.updated_at
            )
            animal_logger.info(f"Custom feed details returned successfully | Feed: {feed.fd_name} | User: {user_id}")
        else:
            # Handle standard Feed model fields
            feed_details = FeedDetailsResponse(
                feed_id=str(feed.id),
                fd_code=feed.fd_code,  # ✅ Fixed: using exact database column name
                fd_name=feed.fd_name,  # ✅ Fixed: using exact database column name
                fd_type=feed.fd_type,  # ✅ Fixed: using exact database column name
                fd_category=feed.fd_category,  # ✅ Fixed: using exact database column name
                fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,  # ✅ Fixed: using exact database column name
                fd_country_name=country_name,  # ✅ Fixed: using exact database column name
                fd_country_cd=feed.fd_country_cd,  # ✅ Fixed: using exact database column name
                # Nutritional fields - using exact database column names
                fd_dm=safe_float(feed.fd_dm),  # ✅ Fixed: using exact database column name
                fd_ash=safe_float(feed.fd_ash),  # ✅ Fixed: using exact database column name
                fd_cp=safe_float(feed.fd_cp),  # ✅ Fixed: using exact database column name
                fd_ee=safe_float(feed.fd_ee),  # ✅ Fixed: using exact database column name
                fd_st=safe_float(feed.fd_st),  # ✅ Fixed: using exact database column name
                fd_ndf=safe_float(feed.fd_ndf),  # ✅ Fixed: using exact database column name
                fd_adf=safe_float(feed.fd_adf),  # ✅ Fixed: using exact database column name
                fd_lg=safe_float(feed.fd_lg),  # ✅ Fixed: using exact database column name
                # Additional nutritional fields - using exact database column names
                fd_ndin=safe_float(feed.fd_ndin),  # ✅ Fixed: using exact database column name
                fd_adin=safe_float(feed.fd_adin),  # ✅ Fixed: using exact database column name
                fd_ca=safe_float(feed.fd_ca),  # ✅ Fixed: using exact database column name
                fd_p=safe_float(feed.fd_p),  # ✅ Fixed: using exact database column name
                fd_cf=safe_float(feed.fd_cf),  # ✅ Fixed: using exact database column name
                fd_nfe=safe_float(feed.fd_nfe),  # ✅ Fixed: using exact database column name
                fd_hemicellulose=safe_float(feed.fd_hemicellulose),  # ✅ Fixed: using exact database column name
                fd_cellulose=safe_float(feed.fd_cellulose),  # ✅ Fixed: using exact database column name
                # Metadata fields - using exact database column names
                fd_orginin=feed.fd_orginin,  # ✅ Fixed: using exact database column name
                fd_ipb_local_lab=feed.fd_ipb_local_lab,  # ✅ Fixed: using exact database column name
                created_at=feed.created_at,
                updated_at=feed.updated_at
            )
            animal_logger.info(f"Standard feed details returned successfully | Feed: {feed.fd_name} | User: {user_id}")
        
        return feed_details
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error retrieving feed details | User: {user_id} | Feed: {feed_id} | Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve feed details: {str(e)}"
        )



@router.post("/feed-analytics/", response_model=FeedAnalyticsResponse)
async def create_feed_analytics(data: FeedAnalyticsCreate, db: Session = Depends(get_db)):
    try:
        # Create a new FeedAnalytics instance
        new_feed_analytics = FeedAnalytics(
            da_name=data.da_name,
            da_phone_num=data.da_phone_num,
            country_cd=data.country_cd,
            country_name=data.country_name,
            animal_info=data.animal_info,
            sys_rcmd=data.sys_rcmd,
            cust_rcmd=data.cust_rcmd,
            farmer_name=data.farmer_name,
            farmer_phone_num=data.farmer_phone_num,
            rcmd_dt=data.rcmd_dt,
            farmer_adopted=data.farmer_adopted
        )

        # Add and commit the new record to the database
        db.add(new_feed_analytics)
        db.commit()
        db.refresh(new_feed_analytics)

        # Return the new record, including row_id
        return new_feed_analytics

    except SQLAlchemyError as e:
        animal_logger.error(f"Error in feed-analytics: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        animal_logger.error(f"Unexpected error in feed-analytics: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/generate-report/")
async def generate_report(data: dict):
    print("🚀 ~ data:", data)
    """
    Generates a PDF report from the provided data and returns it as a response.
    """
    try:
        # Extract data from the request
        owner_name = data.get("name", "Unknown")
        country = data.get("country", "Unknown")
        location = data.get("location", "Unknown")
        daily_body_weight_gain = data.get("daily_body_weight_gain", "Unknown")
        body_condition_score = data.get("body_condition_score", "Unknown")
        body_weight = data.get("body_weight", "0")
        milk_expected = data.get("milk_production", "0")
        total_cost = str(data.get("total_cost", "0"))
        methane_emission = data.get("methane_emission", "0")
        feed_items = data.get("feed_items", [])
        cattle_id = data.get("cattle_id", "Unknown")
        lactating = "Yes" if data.get("lactating", "false") == "true" else "No"
        tp_milk = data.get("tp_milk", "Unknown")
        fat_milk = data.get("fat_milk", "Unknown")
        days_in_milk = data.get("days_in_milk", "0")
        days_of_pregnancy = data.get("days_of_pregnancy", "0")
        calving_interval = data.get("calving_interval", "0")
        parity = data.get("parity", "0")
        temperature = data.get("temperature", "0")
        topography = data.get("topography", "Unknown")
        grazing = data.get("grazing", "Unknown")
        distance = data.get("distance", "0")
        report_id = data.get("report_id", "0")
        breed = data.get("breed", "0")
        print("🚀 ~ logo_base64:test")

        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Construct the full path to the logo file
        logo_path = os.path.join(current_dir, 'app_logo.png')

        with open(logo_path, 'rb') as image_file:
            logo_data = image_file.read()

        logo_base64 = base64.b64encode(logo_data).decode('utf-8')       

        

        # Create HTML content for the PDF
        html_content = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                h1 {{
                    color: #1BA068;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                h2 {{
                    color: #3e3e3e;
                    border-bottom: 2px solid #4CAF50;
                    padding-bottom: 5px;
                    margin-top: 10px;
                }}
                p {{
                    margin: 5px 0;
                }}
                .section {{
                    margin-bottom: 20px;
                }}
                .highlight {{
                    background-color: #f9f9f9;
                    padding: 10px;
                    border-left: 5px solid #4CAF50;
                    margin-bottom: 20px;
                }}
                .summary {{
                    margin-top: 10px;
                    font-size: 1.1em;
                    background-color: #f9f9f9;
                    padding: 10px;
                    border: 2px dashed #4CAF50;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                }}
                th {{
                    background-color: #1BA068;
                    color: white;
                    padding-left: 10px;
                    padding-right: 10px;
                    text-align: left;
                }}
                td {{
                    padding: 8px;
                    border: 1px solid #ddd;
                }}
                .highlighted-text {{
                    font-weight: bold;
                    color: #1BA068;
                }}
                .two-column {{
    display: flex;
    justify-content: space-between;
}}
.two-column div {{
    width: 48%; /* Each column takes up half the width with some space in between */
}}
.two-column p {{
    margin: 5px 0;
}}

            </style>
        </head>
        <body>
        <div style="text-align: center; margin-bottom: 10px; margin-top: -10px;">
        <img src="data:image/png;base64,{logo_base64}" alt="Logo" style="max-width:100px;"/>
    </div>
            <h1>Least Cost Dairy Ration Fomulation</h1>
            <div class="section">
            <h2>Farmer Details</h2>
            <div class="two-column">
                
                <div>
                <p><span class="highlighted-text">Report ID:</span> {report_id}</p>
                <p><span class="highlighted-text">Owner Name:</span> {owner_name}</p>
                 
                </div>
                <div>
                <p><span class="highlighted-text">Cattle ID:</span> {cattle_id}</p>
                <p><span class="highlighted-text">Country:</span> {country}</p>
            </div>
            </div>
            </div>

            <div class="section">
    <h2>Animal Characteristics</h2>
    <div class="two-column">
        <div>
            <p><span class="highlighted-text">Breed:</span> {breed}</p>
            <p><span class="highlighted-text">Lactating:</span> {lactating}</p>
            <p><span class="highlighted-text">Body Weight:</span> {body_weight} kg</p>
            <p><span class="highlighted-text">Daily Body Weight Gain:</span> {daily_body_weight_gain} kg</p>
            <p><span class="highlighted-text">Milk Protein:</span> {tp_milk}</p>
            <p><span class="highlighted-text">Milk Fat:</span> {fat_milk}</p>
            <p><span class="highlighted-text">Milk Expected:</span> {milk_expected} liters</p>
            <p><span class="highlighted-text">Days in Milk:</span> {days_in_milk}</p>
        </div>
        <div>
            <p><span class="highlighted-text">Days of Pregnancy:</span> {days_of_pregnancy}</p>
            <p><span class="highlighted-text">Calving Interval:</span> {calving_interval}</p>
            <p><span class="highlighted-text">Parity:</span> {parity}</p>
            <p><span class="highlighted-text">Body Condition Score:</span> {body_condition_score}</p>
            <p><span class="highlighted-text">Temperature:</span> {temperature}°C</p>
            <p><span class="highlighted-text">Topography:</span> {topography}</p>
            <p><span class="highlighted-text">Grazing:</span> {grazing}</p>
            <p><span class="highlighted-text">Distance:</span> {distance} km</p>
        </div>
    </div>
</div>

            <div class="highlight">
                <h2>Feed Recommendations (Per Day)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Feed Name</th>
                            <th>Quantity (Kg)</th>
                            <th>Price</th>
                            <th>Cost</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        # Add feed items dynamically
        for feed in feed_items:
            html_content += f"""
                        <tr>
                            <td>{feed.get("feed_name", "Unknown")}</td>
                            <td>{feed.get("quantity", "0")}</td>
                            <td>{feed.get("price", "0")}</td>
                            <td>{feed.get("amount", "0")}</td>
                        </tr>
            """

        html_content += f"""
        
                    </tbody>
                </table>
            </div>

            <div class="summary">
                
                <p><strong>Total Cost:</strong> <span class="highlighted-text">{total_cost} USD</span></p>
                <p><strong>Methane Emission:</strong> <span class="highlighted-text">{methane_emission} g/day</span></p>
            </div>
        </body>
        </html>
        """

        # Generate the PDF file
        pdf_file_path = f"/tmp/{uuid.uuid4()}.pdf"
        HTML(string=html_content).write_pdf(pdf_file_path)

        # Return the generated PDF file
        return FileResponse(pdf_file_path, media_type="application/pdf", filename="Farm_Report.pdf")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred while generating the PDF: {str(e)}")
    
# Add new request and response models after the existing imports
class CheckInsertUpdateRequest(BaseModel):
    """Request model for check-insert-or-update endpoint"""
    feed_id: str = Field(..., description="Feed UUID to check")
    user_id: str = Field(..., description="User UUID")
    country_id: str = Field(..., description="Country UUID")

    @validator('feed_id', 'user_id', 'country_id')
    def validate_uuids(cls, v):
        """Validate that all IDs are valid UUIDs"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Must be a valid UUID')

class CheckInsertUpdateResponse(BaseModel):
    """Response model for check-insert-or-update endpoint"""
    insert_feed: bool = Field(..., description="True if standard feed, False if custom feed")
    user_id: str = Field(..., description="User UUID (echoed from request)")
    country_id: str = Field(..., description="Country UUID (echoed from request)")
    feed_details: FeedDetailsResponse = Field(..., description="Complete feed information")

    class Config:
        orm_mode = True

@router.post("/check-insert-or-update/", response_model=CheckInsertUpdateResponse)
async def check_insert_or_update(
    request: CheckInsertUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Check if a feed exists in standard feeds or custom feeds tables
    for display in BottomSheet Dialog
    
    - **feed_id**: Feed UUID to search for
    - **user_id**: User UUID making the request
    - **country_id**: Country UUID for context
    
    Returns feed details with insert_feed flag:
    - insert_feed=true: Feed found in standard feeds table
    - insert_feed=false: Feed found in custom feeds table
    - HTTP 404: Feed not found in either table
    """
    try:
        animal_logger.info(f"Check insert/update request | Feed ID: {request.feed_id} | User: {request.user_id} | Country: {request.country_id}")
        
        # Step 1: Check standard feeds table first
        standard_feed = db.query(Feed).filter(Feed.id == request.feed_id).first()
        
        if standard_feed:
            animal_logger.info(f"Standard feed found | Feed: {standard_feed.fd_name} | ID: {request.feed_id}")
            
            # Get country information if available
            country_name = None
            if standard_feed.fd_country_id:
                country = db.query(CountryModel).filter(CountryModel.id == standard_feed.fd_country_id).first()
                country_name = country.name if country else None
            
            # Create feed details response
            feed_details = FeedDetailsResponse(
                feed_id=str(standard_feed.id),
                fd_code=standard_feed.fd_code,  # ✅ Fixed: using exact column name
                fd_name=standard_feed.fd_name,  # ✅ Fixed: using exact column name
                fd_type=standard_feed.fd_type,  # ✅ Fixed: using exact column name
                fd_category=standard_feed.fd_category,  # ✅ Fixed: using exact column name
                fd_country_id=str(standard_feed.fd_country_id) if standard_feed.fd_country_id else None,  # ✅ Fixed: using exact column name
                fd_country_name=country_name,  # ✅ Fixed: using exact database column name
                fd_country_cd=standard_feed.fd_country_cd,  # ✅ Fixed: using exact database column name
                # Nutritional data - using exact database column names
                fd_dm=float(standard_feed.fd_dm) if standard_feed.fd_dm is not None else None,  # ✅ Fixed: using exact column name
                fd_ash=float(standard_feed.fd_ash) if standard_feed.fd_ash is not None else None,  # ✅ Fixed: using exact column name
                fd_cp=float(standard_feed.fd_cp) if standard_feed.fd_cp is not None else None,  # ✅ Fixed: using exact column name
                fd_ee=float(standard_feed.fd_ee) if standard_feed.fd_ee is not None else None,  # ✅ Fixed: using exact column name
                fd_st=float(standard_feed.fd_st) if standard_feed.fd_st is not None else None,  # ✅ Fixed: using exact column name
                fd_ndf=float(standard_feed.fd_ndf) if standard_feed.fd_ndf is not None else None,  # ✅ Fixed: using exact column name
                fd_adf=float(standard_feed.fd_adf) if standard_feed.fd_adf is not None else None,  # ✅ Fixed: using exact column name
                fd_lg=float(standard_feed.fd_lg) if standard_feed.fd_lg is not None else None,  # ✅ Fixed: using exact column name
                fd_ndin=float(standard_feed.fd_ndin) if standard_feed.fd_ndin is not None else None,  # ✅ Fixed: using exact column name
                fd_adin=float(standard_feed.fd_adin) if standard_feed.fd_adin is not None else None,  # ✅ Fixed: using exact column name
                fd_ca=float(standard_feed.fd_ca) if standard_feed.fd_ca is not None else None,  # ✅ Fixed: using exact column name
                fd_p=float(standard_feed.fd_p) if standard_feed.fd_p is not None else None,  # ✅ Fixed: using exact column name
                fd_cf=float(standard_feed.fd_cf) if standard_feed.fd_cf is not None else None,  # ✅ Fixed: using exact column name
                fd_nfe=float(standard_feed.fd_nfe) if standard_feed.fd_nfe is not None else None,  # ✅ Fixed: using exact column name
                fd_hemicellulose=float(standard_feed.fd_hemicellulose) if standard_feed.fd_hemicellulose is not None else None,  # ✅ Fixed: using exact column name
                fd_cellulose=float(standard_feed.fd_cellulose) if standard_feed.fd_cellulose is not None else None,  # ✅ Fixed: using exact column name
                fd_orginin=standard_feed.fd_orginin,  # ✅ Fixed: using exact column name
                fd_ipb_local_lab=standard_feed.fd_ipb_local_lab,  # ✅ Fixed: using exact column name
                created_at=standard_feed.created_at,
                updated_at=standard_feed.updated_at
            )
            
            return CheckInsertUpdateResponse(
                insert_feed=True,
                user_id=request.user_id,
                country_id=request.country_id,
                feed_details=feed_details
            )
        
        # Step 2: Check custom feeds table (no ownership validation as per Option A)
        custom_feed = db.query(CustomFeed).filter(CustomFeed.id == request.feed_id).first()
        
        if custom_feed:
            animal_logger.info(f"Custom feed found | Feed: {custom_feed.fd_name} | ID: {request.feed_id} | Owner: {custom_feed.user_id}")
            
            # Get country information if available
            country_name = None
            if custom_feed.fd_country_id:
                country = db.query(CountryModel).filter(CountryModel.id == custom_feed.fd_country_id).first()
                country_name = country.name if country else None
            
            # Create feed details response
            feed_details = FeedDetailsResponse(
                feed_id=str(custom_feed.id),
                fd_code=custom_feed.fd_code,  # ✅ Fixed: using exact column name
                fd_name=custom_feed.fd_name,  # ✅ Fixed: using exact column name
                fd_type=custom_feed.fd_type,  # ✅ Fixed: using exact column name
                fd_category=custom_feed.fd_category,  # ✅ Fixed: using exact column name
                fd_country_id=str(custom_feed.fd_country_id) if custom_feed.fd_country_id else None,  # ✅ Fixed: using exact column name
                fd_country_name=country_name,  # ✅ Fixed: using exact database column name
                fd_country_cd=custom_feed.fd_country_cd,  # ✅ Fixed: using exact database column name
                # Nutritional data - using exact database column names
                fd_dm=float(custom_feed.fd_dm) if custom_feed.fd_dm is not None else None,  # ✅ Fixed: using exact column name
                fd_ash=float(custom_feed.fd_ash) if custom_feed.fd_ash is not None else None,  # ✅ Fixed: using exact column name
                fd_cp=float(custom_feed.fd_cp) if custom_feed.fd_cp is not None else None,  # ✅ Fixed: using exact column name
                fd_ee=float(custom_feed.fd_ee) if custom_feed.fd_ee is not None else None,  # ✅ Fixed: using exact column name
                fd_st=float(custom_feed.fd_st) if custom_feed.fd_st is not None else None,  # ✅ Fixed: using exact column name
                fd_ndf=float(custom_feed.fd_ndf) if custom_feed.fd_ndf is not None else None,  # ✅ Fixed: using exact column name
                fd_adf=float(custom_feed.fd_adf) if custom_feed.fd_adf is not None else None,  # ✅ Fixed: using exact column name
                fd_lg=float(custom_feed.fd_lg) if custom_feed.fd_lg is not None else None,  # ✅ Fixed: using exact column name
                fd_ndin=float(custom_feed.fd_ndin) if custom_feed.fd_ndin is not None else None,  # ✅ Fixed: using exact column name
                fd_adin=float(custom_feed.fd_adin) if custom_feed.fd_adin is not None else None,  # ✅ Fixed: using exact column name
                fd_ca=float(custom_feed.fd_ca) if custom_feed.fd_ca is not None else None,  # ✅ Fixed: using exact column name
                fd_p=float(custom_feed.fd_p) if custom_feed.fd_p is not None else None,  # ✅ Fixed: using exact column name
                fd_cf=float(custom_feed.fd_cf) if custom_feed.fd_cf is not None else None,  # ✅ Fixed: using exact column name
                fd_nfe=float(custom_feed.fd_nfe) if custom_feed.fd_nfe is not None else None,  # ✅ Fixed: using exact column name
                fd_hemicellulose=float(custom_feed.fd_hemicellulose) if custom_feed.fd_hemicellulose is not None else None,  # ✅ Fixed: using exact column name
                fd_cellulose=float(custom_feed.fd_cellulose) if custom_feed.fd_cellulose is not None else None,  # ✅ Fixed: using exact column name
                fd_orginin=custom_feed.fd_orginin,  # ✅ Fixed: using exact column name
                fd_ipb_local_lab=custom_feed.fd_ipb_local_lab,  # ✅ Fixed: using exact column name
                created_at=custom_feed.created_at,
                updated_at=custom_feed.updated_at
            )
            
            return CheckInsertUpdateResponse(
                insert_feed=False,
                user_id=request.user_id,
                country_id=request.country_id,
                feed_details=feed_details
            )
        
        # Step 3: Feed not found in either table
        animal_logger.warning(f"Feed not found in either table | Feed ID: {request.feed_id} | User: {request.user_id}")
        raise HTTPException(
            status_code=404,
            detail="Feed not found. Please reselect the feed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error in check_insert_or_update | Feed: {request.feed_id} | User: {request.user_id} | Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )

# Create a nested feed details request model
class FeedDetailsRequest(BaseModel):
    """Nested feed details for request models"""
    feed_name: str = Field(..., max_length=100, description="Feed name")
    
    # Optional feed details - all nutritional fields are optional
    feed_type: Optional[str] = Field(None, max_length=50, description="Feed type")
    feed_category: Optional[str] = Field(None, max_length=50, description="Feed category")
    country_name: Optional[str] = Field(None, max_length=100, description="Country name")
    country_code: Optional[str] = Field(None, max_length=10, description="Country code")
    
    # Nutritional fields (all optional) - using exact database column names
    fd_dm: Optional[float] = Field(None, description="Dry Matter %")
    fd_ash: Optional[float] = Field(None, description="Ash %")
    fd_cp: Optional[float] = Field(None, description="Crude Protein %")
    fd_ee: Optional[float] = Field(None, description="Ether Extract %")
    fd_cf: Optional[float] = Field(None, description="Crude Fiber %")
    nfe_pct: Optional[float] = Field(None, description="Nitrogen Free Extract %")
    fd_st: Optional[float] = Field(None, description="Starch %")
    fd_ndf: Optional[float] = Field(None, description="Neutral Detergent Fiber %")
    fd_hemicellulose: Optional[float] = Field(None, description="Hemicellulose %")
    fd_adf: Optional[float] = Field(None, description="Acid Detergent Fiber %")
    fd_cellulose: Optional[float] = Field(None, description="Cellulose %")
    fd_lg: Optional[float] = Field(None, description="Lignin %")
    fd_ndin: Optional[float] = Field(None, description="Neutral Detergent Insoluble Nitrogen %")
    fd_adin: Optional[float] = Field(None, description="Acid Detergent Insoluble Nitrogen %")
    fd_ca: Optional[float] = Field(None, description="Calcium %")
    fd_p: Optional[float] = Field(None, description="Phosphorus %")
    
    # Metadata fields
    id_orginin: Optional[str] = Field(None, max_length=50, description="Origin ID")
    id_ipb_local_lab: Optional[str] = Field(None, max_length=50, description="IPB Local Lab ID")

# Add new request and response models for insert-custom-feed API
class InsertCustomFeedRequest(BaseModel):
    """Request model for insert-custom-feed endpoint"""
    user_id: str = Field(..., description="User UUID")
    country_id: str = Field(..., description="Country UUID")
    feed_insert: bool = Field(..., description="Must be true for insertion")
    feed_details: FeedDetailsRequest = Field(..., description="Feed details in nested structure")

    @validator('user_id', 'country_id')
    def validate_uuids(cls, v):
        """Validate that IDs are valid UUIDs"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Must be a valid UUID')
    
    @validator('feed_insert')
    def validate_feed_insert(cls, v):
        """Validate that feed_insert is exactly true"""
        if v is not True:
            raise ValueError('feed_insert must be true')
        return v

class InsertCustomFeedResponse(BaseModel):
    """Response model for insert-custom-feed endpoint"""
    user_id: str = Field(..., description="User UUID (echoed from request)")
    country_id: str = Field(..., description="Country UUID (echoed from request)")
    feed_details: FeedDetailsResponse = Field(..., description="Complete custom feed information")

    class Config:
        orm_mode = True

@router.post("/insert-custom-feed/", response_model=InsertCustomFeedResponse)
async def insert_custom_feed(
    request: InsertCustomFeedRequest,
    db: Session = Depends(get_db)
):
    """
    Insert a new custom feed into the custom_feeds table
    
    - **user_id**: User UUID (must exist in user_information table)
    - **country_id**: Country UUID (must exist in country table)
    - **feed_name**: Name of the custom feed
    - **feed_insert**: Must be true (boolean)
    - **All other fields**: Optional nutritional and metadata fields
    
    Returns complete feed details with user_id and country_id.
    This is an INSERT-only operation (no updates).
    """
    try:
        animal_logger.info(f"Insert custom feed request | User ID: {request.user_id} | Country: {request.country_id} | Feed Name: {request.feed_details.feed_name}")
        
        # Validate user exists (404 if not found)
        user = db.query(UserInformationModel).filter(UserInformationModel.id == request.user_id).first()
        if not user:
            animal_logger.warning(f"User not found: {request.user_id}")
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Validate country exists (404 if not found)
        country = db.query(CountryModel).filter(CountryModel.id == request.country_id).first()
        if not country:
            animal_logger.warning(f"Country not found: {request.country_id}")
            raise HTTPException(
                status_code=404,
                detail="Country not found"
            )
        
        # feed_insert validation is handled by Pydantic validator (400 if not true)
        # This will automatically return 422 if feed_insert != true due to validation
        
        # Generate the next available feed_code
        next_feed_code = generate_next_custom_feed_code(db)
        animal_logger.info(f"Generated feed_code: {next_feed_code}")
        
        # Create new custom feed
        custom_feed = CustomFeed(
            user_id=request.user_id,
            fd_code=next_feed_code,
            fd_name=request.feed_details.feed_name,
            fd_type=request.feed_details.feed_type,
            fd_category=request.feed_details.feed_category,
            fd_country_id=request.country_id,
            fd_country_name=request.feed_details.country_name or country.name,
            fd_country_cd=request.feed_details.country_code or country.country_code,
            # Convert float values to string for storage (matching feeds table format)
            fd_dm=str(request.feed_details.fd_dm) if request.feed_details.fd_dm is not None else None,
            fd_ash=str(request.feed_details.fd_ash) if request.feed_details.fd_ash is not None else None,
            fd_cp=str(request.feed_details.fd_cp) if request.feed_details.fd_cp is not None else None,
            fd_ee=str(request.feed_details.fd_ee) if request.feed_details.fd_ee is not None else None,
            fd_cf=str(request.feed_details.fd_cf) if request.feed_details.fd_cf is not None else None,
            fd_nfe=str(request.feed_details.nfe_pct) if request.feed_details.nfe_pct is not None else None,
            fd_st=str(request.feed_details.fd_st) if request.feed_details.fd_st is not None else None,  # Fixed: using fd_st instead of fd_starch
            fd_ndf=str(request.feed_details.fd_ndf) if request.feed_details.fd_ndf is not None else None,
            fd_hemicellulose=str(request.feed_details.fd_hemicellulose) if request.feed_details.fd_hemicellulose is not None else None,
            fd_adf=str(request.feed_details.fd_adf) if request.feed_details.fd_adf is not None else None,
            fd_cellulose=str(request.feed_details.fd_cellulose) if request.feed_details.fd_cellulose is not None else None,
            fd_lg=str(request.feed_details.fd_lg) if request.feed_details.fd_lg is not None else None,  # Fixed: using fd_lg instead of fd_lignin
            fd_ndin=str(request.feed_details.fd_ndin) if request.feed_details.fd_ndin is not None else None,
            fd_adin=str(request.feed_details.fd_adin) if request.feed_details.fd_adin is not None else None,
            fd_ca=str(request.feed_details.fd_ca) if request.feed_details.fd_ca is not None else None,  # Fixed: using fd_ca instead of fd_calcium
            fd_p=str(request.feed_details.fd_p) if request.feed_details.fd_p is not None else None,  # Fixed: using fd_p instead of fd_phosphorus
            fd_orginin=request.feed_details.id_orginin,
            fd_ipb_local_lab=request.feed_details.id_ipb_local_lab
        )
        
        # Add to database
        db.add(custom_feed)
        db.commit()
        db.refresh(custom_feed)
        
        # Create feed details response
        feed_details = FeedDetailsResponse(
            feed_id=str(custom_feed.id),
            fd_code=custom_feed.fd_code,  # Fixed: using fd_code instead of feed_code
            fd_name=custom_feed.fd_name,
            fd_type=custom_feed.fd_type,
            fd_category=custom_feed.fd_category,
            fd_country_id=str(custom_feed.fd_country_id),
            fd_country_name=custom_feed.fd_country_name,
            fd_country_cd=custom_feed.fd_country_cd,
            # Convert string values back to float for response (using exact database column names)
            fd_dm=float(custom_feed.fd_dm) if custom_feed.fd_dm is not None else None,
            fd_ash=float(custom_feed.fd_ash) if custom_feed.fd_ash is not None else None,
            fd_cp=float(custom_feed.fd_cp) if custom_feed.fd_cp is not None else None,
            fd_ee=float(custom_feed.fd_ee) if custom_feed.fd_ee is not None else None,
            fd_cf=float(custom_feed.fd_cf) if custom_feed.fd_cf is not None else None,
            fd_nfe=float(custom_feed.fd_nfe) if custom_feed.fd_nfe is not None else None,  # ✅ Fixed: using exact database column name
            fd_st=float(custom_feed.fd_st) if custom_feed.fd_st is not None else None,  # Fixed: using fd_st instead of fd_starch
            fd_ndf=float(custom_feed.fd_ndf) if custom_feed.fd_ndf is not None else None,
            fd_hemicellulose=float(custom_feed.fd_hemicellulose) if custom_feed.fd_hemicellulose is not None else None,
            fd_adf=float(custom_feed.fd_adf) if custom_feed.fd_adf is not None else None,
            fd_cellulose=float(custom_feed.fd_cellulose) if custom_feed.fd_cellulose is not None else None,
            fd_lg=float(custom_feed.fd_lg) if custom_feed.fd_lg is not None else None,  # Fixed: using fd_lg instead of fd_lignin
            fd_ndin=float(custom_feed.fd_ndin) if custom_feed.fd_ndin is not None else None,
            fd_adin=float(custom_feed.fd_adin) if custom_feed.fd_adin is not None else None,
            fd_ca=float(custom_feed.fd_ca) if custom_feed.fd_ca is not None else None,  # Fixed: using fd_ca instead of fd_calcium
            fd_p=float(custom_feed.fd_p) if custom_feed.fd_p is not None else None,  # Fixed: using fd_p instead of fd_phosphorus
            fd_orginin=custom_feed.fd_orginin,
            fd_ipb_local_lab=custom_feed.fd_ipb_local_lab,
            created_at=custom_feed.created_at,
            updated_at=custom_feed.updated_at
        )
        
        # Create nested response
        response = InsertCustomFeedResponse(
            user_id=request.user_id,
            country_id=request.country_id,
            feed_details=feed_details
        )
        
        animal_logger.info(f"Custom feed inserted successfully | User: {request.user_id} | Feed: {request.feed_details.feed_name} | ID: {custom_feed.id} | Code: {custom_feed.fd_code}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error inserting custom feed | User: {request.user_id} | Feed: {request.feed_details.feed_name} | Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to insert custom feed: {str(e)}"
        )

    

class UpdateCustomFeedRequest(BaseModel):
    """Request model for update-custom-feed endpoint"""
    user_id: str = Field(..., description="User UUID")
    country_id: str = Field(..., description="Country UUID")
    feed_id: str = Field(..., description="Custom feed UUID to update")
    feed_insert: bool = Field(..., description="Must be false for update")
    feed_details: FeedDetailsRequest = Field(..., description="Feed details in nested structure")

    @validator('user_id', 'country_id', 'feed_id')
    def validate_uuids(cls, v):
        """Validate that IDs are valid UUIDs"""
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('Must be a valid UUID')
    
    @validator('feed_insert')
    def validate_feed_insert(cls, v):
        """Validate that feed_insert is exactly false"""
        if v is not False:
            raise ValueError('feed_insert must be false')
        return v

class UpdateCustomFeedResponse(BaseModel):
    """Response model for update-custom-feed endpoint"""
    user_id: str = Field(..., description="User UUID (echoed from request)")
    country_id: str = Field(..., description="Country UUID (echoed from request)")
    feed_details: FeedDetailsResponse = Field(..., description="Complete updated custom feed information")

    class Config:
        orm_mode = True

@router.post("/update-custom-feed/", response_model=UpdateCustomFeedResponse)
async def update_custom_feed(
    request: UpdateCustomFeedRequest,
    db: Session = Depends(get_db)
):
    """
    Update an existing custom feed in the custom_feeds table
    
    - **user_id**: User UUID (must exist in user_information table)
    - **country_id**: Country UUID (must exist in country table)
    - **feed_id**: Custom feed UUID to update (must exist and belong to user)
    - **feed_name**: Updated name of the custom feed
    - **feed_insert**: Must be false (boolean)
    - **All other fields**: Optional nutritional and metadata fields to update
    
    Returns complete updated feed details with user_id and country_id.
    This is an UPDATE-only operation (no inserts).
    """
    try:
        animal_logger.info(f"Update custom feed request | User ID: {request.user_id} | Country: {request.country_id} | Feed ID: {request.feed_id} | Feed Name: {request.feed_details.feed_name}")
        
        # Validate user exists (404 if not found)
        user = db.query(UserInformationModel).filter(UserInformationModel.id == request.user_id).first()
        if not user:
            animal_logger.warning(f"User not found: {request.user_id}")
            raise HTTPException(
                status_code=404,
                detail="User not found"
            )
        
        # Validate country exists (404 if not found)
        country = db.query(CountryModel).filter(CountryModel.id == request.country_id).first()
        if not country:
            animal_logger.warning(f"Country not found: {request.country_id}")
            raise HTTPException(
                status_code=404,
                detail="Country not found"
            )
        
        # feed_insert validation is handled by Pydantic validator (422 if not false)
        # This will automatically return 422 if feed_insert != false due to validation
        
        # Validate custom feed exists and belongs to the user
        custom_feed = db.query(CustomFeed).filter(
            CustomFeed.id == request.feed_id,
            CustomFeed.user_id == request.user_id
        ).first()
        
        if not custom_feed:
            animal_logger.warning(f"Custom feed not found or does not belong to user | Feed ID: {request.feed_id} | User: {request.user_id}")
            raise HTTPException(
                status_code=404,
                detail="Custom feed not found or does not belong to the specified user"
            )
        
        # Update the custom feed with new values
        custom_feed.fd_name = request.feed_details.feed_name
        custom_feed.fd_type = request.feed_details.feed_type
        custom_feed.fd_category = request.feed_details.feed_category
        custom_feed.fd_country_id = request.country_id
        custom_feed.fd_country_name = request.feed_details.country_name or country.name
        custom_feed.fd_country_cd = request.feed_details.country_code or country.country_code
        
        # Update nutritional fields (convert float to string for storage)
        custom_feed.fd_dm = str(request.feed_details.fd_dm) if request.feed_details.fd_dm is not None else custom_feed.fd_dm
        custom_feed.fd_ash = str(request.feed_details.fd_ash) if request.feed_details.fd_ash is not None else custom_feed.fd_ash
        custom_feed.fd_cp = str(request.feed_details.fd_cp) if request.feed_details.fd_cp is not None else custom_feed.fd_cp
        custom_feed.fd_ee = str(request.feed_details.fd_ee) if request.feed_details.fd_ee is not None else custom_feed.fd_ee
        custom_feed.fd_cf = str(request.feed_details.fd_cf) if request.feed_details.fd_cf is not None else custom_feed.fd_cf
        custom_feed.fd_nfe = str(request.feed_details.nfe_pct) if request.feed_details.nfe_pct is not None else custom_feed.fd_nfe
        custom_feed.fd_st = str(request.feed_details.fd_st) if request.feed_details.fd_st is not None else custom_feed.fd_st
        custom_feed.fd_ndf = str(request.feed_details.fd_ndf) if request.feed_details.fd_ndf is not None else custom_feed.fd_ndf
        custom_feed.fd_hemicellulose = str(request.feed_details.fd_hemicellulose) if request.feed_details.fd_hemicellulose is not None else custom_feed.fd_hemicellulose
        custom_feed.fd_adf = str(request.feed_details.fd_adf) if request.feed_details.fd_adf is not None else custom_feed.fd_adf
        custom_feed.fd_cellulose = str(request.feed_details.fd_cellulose) if request.feed_details.fd_cellulose is not None else custom_feed.fd_cellulose
        custom_feed.fd_lg = str(request.feed_details.fd_lg) if request.feed_details.fd_lg is not None else custom_feed.fd_lg
        custom_feed.fd_ndin = str(request.feed_details.fd_ndin) if request.feed_details.fd_ndin is not None else custom_feed.fd_ndin
        custom_feed.fd_adin = str(request.feed_details.fd_adin) if request.feed_details.fd_adin is not None else custom_feed.fd_adin
        custom_feed.fd_ca = str(request.feed_details.fd_ca) if request.feed_details.fd_ca is not None else custom_feed.fd_ca
        custom_feed.fd_p = str(request.feed_details.fd_p) if request.feed_details.fd_p is not None else custom_feed.fd_p
        
        # Update metadata fields
        if request.feed_details.id_orginin is not None:
            custom_feed.fd_orginin = request.feed_details.id_orginin
        if request.feed_details.id_ipb_local_lab is not None:
            custom_feed.fd_ipb_local_lab = request.feed_details.id_ipb_local_lab
        
        # Update the updated_at timestamp
        custom_feed.updated_at = datetime.utcnow()
        
        # Commit the changes
        db.commit()
        db.refresh(custom_feed)
        
        # Create feed details response
        feed_details = FeedDetailsResponse(
            feed_id=str(custom_feed.id),
            fd_code=custom_feed.fd_code,  # Fixed: using fd_code instead of feed_code
            fd_name=custom_feed.fd_name,
            fd_type=custom_feed.fd_type,
            fd_category=custom_feed.fd_category,
            fd_country_id=str(custom_feed.fd_country_id),
            fd_country_name=custom_feed.fd_country_name,
            fd_country_cd=custom_feed.fd_country_cd,
            # Convert string values back to float for response
            fd_dm=float(custom_feed.fd_dm) if custom_feed.fd_dm is not None else None,
            fd_ash=float(custom_feed.fd_ash) if custom_feed.fd_ash is not None else None,
            fd_cp=float(custom_feed.fd_cp) if custom_feed.fd_cp is not None else None,
            fd_ee=float(custom_feed.fd_ee) if custom_feed.fd_ee is not None else None,
            fd_cf=float(custom_feed.fd_cf) if custom_feed.fd_cf is not None else None,
            fd_nfe=float(custom_feed.fd_nfe) if custom_feed.fd_nfe is not None else None,
            fd_st=float(custom_feed.fd_st) if custom_feed.fd_st is not None else None,
            fd_ndf=float(custom_feed.fd_ndf) if custom_feed.fd_ndf is not None else None,
            fd_hemicellulose=float(custom_feed.fd_hemicellulose) if custom_feed.fd_hemicellulose is not None else None,
            fd_adf=float(custom_feed.fd_adf) if custom_feed.fd_adf is not None else None,
            fd_cellulose=float(custom_feed.fd_cellulose) if custom_feed.fd_cellulose is not None else None,
            fd_lg=float(custom_feed.fd_lg) if custom_feed.fd_lg is not None else None,
            fd_ndin=float(custom_feed.fd_ndin) if custom_feed.fd_ndin is not None else None,
            fd_adin=float(custom_feed.fd_adin) if custom_feed.fd_adin is not None else None,
            fd_ca=float(custom_feed.fd_ca) if custom_feed.fd_ca is not None else None,
            fd_p=float(custom_feed.fd_p) if custom_feed.fd_p is not None else None,
            fd_orginin=custom_feed.fd_orginin,
            fd_ipb_local_lab=custom_feed.fd_ipb_local_lab,
            created_at=custom_feed.created_at,
            updated_at=custom_feed.updated_at
        )
        
        # Create nested response
        response = UpdateCustomFeedResponse(
            user_id=request.user_id,
            country_id=request.country_id,
            feed_details=feed_details
        )
        
        animal_logger.info(f"Custom feed updated successfully | User: {request.user_id} | Feed: {request.feed_details.feed_name} | ID: {custom_feed.id} | Code: {custom_feed.fd_code}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error updating custom feed | User: {request.user_id} | Feed: {request.feed_details.feed_name} | Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update custom feed: {str(e)}"
        )

@router.post("/diet-evaluation/", response_model=DietEvaluationResponse)
async def evaluate_diet(
    request: DietEvaluationRequest,
    db: Session = Depends(get_db)
):
    """
    Evaluate a diet based on feed selection and animal characteristics
    """
    case_identifier = request.simulation_id
    animal_logger = get_logger("animal")
    
    try:
        # No validation for simulation_id per requirements
        
        # Extract feed IDs from the request
        feed_ids = [item.feed_id for item in request.feed_evaluation]
        
        # Load feeds from database
        feeds_df = load_feeds_for_evaluation(db, feed_ids)
        
        if len(feeds_df) != len(feed_ids):
            missing_feeds = set(feed_ids) - set(feeds_df['id'].tolist())
            raise HTTPException(
                status_code=400,
                detail=f"Some feeds not found: {list(missing_feeds)}"
            )
        
        # Extract quantities and prices
        quantities_as_fed = [item.quantity_as_fed for item in request.feed_evaluation]
        prices_per_kg = [item.price_per_kg for item in request.feed_evaluation]
        
        # Convert to dry matter quantities
        dm_percentages = feeds_df['fd_dm'].values / 100
        quantities_dm = np.array(quantities_as_fed) * dm_percentages
        
        # Calculate animal requirements
        animal_requirements = calculate_animal_requirements_evaluation(
            request.cattle_info.dict()
        )
        
        # Calculate diet supply
        diet_supply_result = calculate_diet_supply_evaluation(
            quantities_dm, feeds_df, animal_requirements
        )
        diet_summary_values = diet_supply_result[0]  # Extract the first element of the tuple
        
        # Predict milk supported
        milk_analysis = predict_milk_supported_evaluation(
            diet_summary_values, animal_requirements, quantities_dm, feeds_df
        )
        
        # Generate warnings and recommendations
        recommendations_milk = []
        if milk_analysis['limiting_nutrient'] == 'Energy':
            recommendations_milk.append("Consider increasing energy-dense feeds")
        elif milk_analysis['limiting_nutrient'] == 'Protein':
            recommendations_milk.append("Consider increasing protein-rich feeds")
        
        # Calculate intake evaluation
        actual_intake = sum(quantities_dm)
        target_intake = animal_requirements['dry_matter_intake']
        intake_percentage = (actual_intake / target_intake) * 100 if target_intake > 0 else 0
        
        intake_status = "Adequate"
        if intake_percentage < 90:
            intake_status = "Below target"
        elif intake_percentage > 110:
            intake_status = "Above target"
        
        # Calculate cost analysis
        total_cost = sum(qty * price for qty, price in zip(quantities_as_fed, prices_per_kg))
        feed_cost_per_kg_milk = total_cost / request.cattle_info.milk_production if request.cattle_info.milk_production > 0 else 0
        
        # Generate nutrient balance warnings
        recommendations_nutrient = []
        # Note: diet_summary_values is a numpy array, not a dict
        # We'll use simplified logic for now
        if milk_analysis['energy_available'] < -1.0:
            recommendations_nutrient.append("Increase energy-dense feeds")
        if milk_analysis['protein_available'] < -0.5:
            recommendations_nutrient.append("Increase protein-rich feeds")
        
        # Calculate methane emissions
        total_dm_intake = sum(quantities_dm)
        methane_emission_mj = total_dm_intake * 0.065  # Simplified calculation
        methane_production_g = methane_emission_mj * 0.015  # Convert MJ to g CH4
        
        # Build feed breakdown
        feed_breakdown = []
        
        # Create mapping from feed_id to request data to ensure correct feed-quantity mapping
        feed_id_to_request_data = {}
        for i, feed_id in enumerate(feed_ids):
            feed_id_to_request_data[feed_id] = {
                'quantity': quantities_as_fed[i],
                'price': prices_per_kg[i]
            }
        
        for _, feed_row in feeds_df.iterrows():
            feed_id = str(feed_row['id'])
            
            if feed_id in feed_id_to_request_data:
                request_data = feed_id_to_request_data[feed_id]
                quantity = request_data['quantity']
                price = request_data['price']
                
                if quantity > 0:  # Only include feeds actually used
                    dm_quantity = quantity * (feed_row['fd_dm'] / 100)
                    total_cost_feed = quantity * price
                    contribution_percent = (total_cost_feed / total_cost) * 100 if total_cost > 0 else 0
                    
                    feed_breakdown.append(FeedBreakdownItem(
                        feed_id=feed_id,
                        feed_name=feed_row['fd_name'],
                        feed_type=feed_row.get('fd_type', 'Unknown'),
                        quantity_as_fed_kg_per_day=quantity,  # ✅ CORRECT: Uses feed_id-based mapping
                        quantity_dm_kg_per_day=dm_quantity,
                        price_per_kg=price,  # ✅ CORRECT: Uses feed_id-based mapping
                        total_cost=total_cost_feed,
                        contribution_percent=contribution_percent
                    ))
        
        # Determine overall status
        overall_status = "Adequate"
        limiting_factor = "None"
        
        if milk_analysis['limiting_nutrient'] != 'None':
            limiting_factor = f"{milk_analysis['limiting_nutrient']} deficiency"
            overall_status = "Marginal"
        
        if intake_percentage < 85:
            limiting_factor = "Inadequate dry matter intake"
            overall_status = "Inadequate"
        
        # Create response
        evaluation_summary = DietEvaluationSummary(
            overall_status=overall_status,
            limiting_factor=limiting_factor
        )
        
        milk_production_analysis = MilkProductionAnalysis(
            target_production_kg_per_day=request.cattle_info.milk_production,
            milk_supported_by_energy_kg_per_day=milk_analysis['energy_supported'],
            milk_supported_by_protein_kg_per_day=milk_analysis['protein_supported'],
            actual_milk_supported_kg_per_day=milk_analysis['actual_supported'],
            limiting_nutrient=milk_analysis['limiting_nutrient'],
            energy_available_mcal=milk_analysis['energy_available'],
            protein_available_g=milk_analysis['protein_available'],
            warnings=[],
            recommendations=recommendations_milk
        )
        
        intake_evaluation = IntakeEvaluation(
            intake_status=intake_status,
            actual_intake_kg_per_day=actual_intake,
            target_intake_kg_per_day=target_intake,
            intake_difference_kg_per_day=actual_intake - target_intake,
            intake_percentage=intake_percentage,
            warnings=[],
            recommendations=[]
        )
        
        cost_analysis = CostAnalysis(
            total_diet_cost_as_fed=total_cost,
            feed_cost_per_kg_milk=feed_cost_per_kg_milk,
            currency=request.currency,
            warnings=[],
            recommendations=[]
        )
        
        methane_analysis = MethaneAnalysis(
            methane_emission_mj_per_day=methane_emission_mj,
            methane_production_g_per_day=methane_production_g,
            methane_yield_g_per_kg_dmi=methane_production_g / total_dm_intake if total_dm_intake > 0 else 0,
            methane_conversion_rate_percent=6.5,
            methane_conversion_range="Normal",
            warnings=[],
            recommendations=[]
        )
        
        nutrient_balance = NutrientBalance(
            energy_balance_mcal=milk_analysis['energy_available'],
            protein_balance_kg=milk_analysis['protein_available'],
            calcium_balance_kg=0.0,  # Simplified
            phosphorus_balance_kg=0.0,  # Simplified
            ndf_balance_kg=0.0,  # Simplified
            warnings=[],
            recommendations=recommendations_nutrient
        )
        
        response = DietEvaluationResponse(
            simulation_id=case_identifier,
            currency=request.currency,
            evaluation_summary=evaluation_summary,
            milk_production_analysis=milk_production_analysis,
            intake_evaluation=intake_evaluation,
            cost_analysis=cost_analysis,
            methane_analysis=methane_analysis,
            nutrient_balance=nutrient_balance,
            feed_breakdown=feed_breakdown
        )
        
        animal_logger.info(f"[{case_identifier}] Diet evaluation completed successfully")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"[{case_identifier}] Diet evaluation failed: {str(e)}")
        animal_logger.error(f"[{case_identifier}] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Diet evaluation failed: {str(e)}"
        )

# Feed CRUD Endpoints
@router.get("/feeds/", response_model=List[FeedDetailsResponse])
async def get_feeds(
    country_id: Optional[str] = Query(None, description="Filter by country ID"),
    feed_type: Optional[str] = Query(None, description="Filter by feed type"),
    feed_category: Optional[str] = Query(None, description="Filter by feed category"),
    limit: int = Query(100, description="Maximum number of feeds to return"),
    offset: int = Query(0, description="Number of feeds to skip"),
    db: Session = Depends(get_db)
):
    """
    Get all feeds with optional filtering
    """
    try:
        query = db.query(Feed)
        
        if country_id:
            query = query.filter(Feed.fd_country_id == country_id)
        
        if feed_type:
            query = query.filter(Feed.fd_type == feed_type)
        
        if feed_category:
            query = query.filter(Feed.fd_category == feed_category)
        
        feeds = query.limit(limit).offset(offset).all()
        
        # Convert to response model
        feed_responses = []
        for feed in feeds:
            feed_responses.append(FeedDetailsResponse(
                feed_id=str(feed.id),
                fd_code=feed.fd_code,  # ✅ Fixed: using exact database column name
                fd_name=feed.fd_name,  # ✅ Fixed: using exact database column name
                fd_type=feed.fd_type,  # ✅ Fixed: using exact database column name
                fd_category=feed.fd_category,  # ✅ Fixed: using exact database column name
                fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,  # ✅ Fixed: using exact database column name
                fd_country_name=feed.fd_country_name,  # ✅ Fixed: using exact database column name
                fd_country_cd=feed.fd_country_cd,  # ✅ Fixed: using exact database column name
                fd_dm=feed.fd_dm,  # ✅ Fixed: using exact database column name
                fd_ash=feed.fd_ash,  # ✅ Fixed: using exact database column name
                fd_cp=feed.fd_cp,  # ✅ Fixed: using exact database column name
                fd_ee=feed.fd_ee,  # ✅ Fixed: using exact database column name
                fd_st=feed.fd_st,  # ✅ Fixed: using exact database column name
                fd_ndf=feed.fd_ndf,  # ✅ Fixed: using exact database column name
                fd_adf=feed.fd_adf,  # ✅ Fixed: using exact database column name
                fd_lg=feed.fd_lg,  # ✅ Fixed: using exact database column name
                fd_ndin=feed.fd_ndin,  # ✅ Fixed: using exact database column name
                fd_adin=feed.fd_adin,  # ✅ Fixed: using exact database column name
                fd_ca=feed.fd_ca,  # ✅ Fixed: using exact database column name
                fd_p=feed.fd_p,  # ✅ Fixed: using exact database column name
                fd_cf=feed.fd_cf,  # ✅ Fixed: using exact database column name
                fd_nfe=feed.fd_nfe,  # ✅ Fixed: using exact database column name
                fd_hemicellulose=feed.fd_hemicellulose,  # ✅ Fixed: using exact database column name
                fd_cellulose=feed.fd_cellulose,  # ✅ Fixed: using exact database column name
                fd_npn_cp=feed.fd_npn_cp,  # ✅ Fixed: using exact database column name
                fd_season=feed.fd_season,  # ✅ Fixed: using exact database column name
                fd_orginin=feed.fd_orginin,  # ✅ Fixed: using exact database column name
                fd_ipb_local_lab=feed.fd_ipb_local_lab,  # ✅ Fixed: using exact database column name
                created_at=feed.created_at,
                updated_at=feed.updated_at
            ))
        
        return feed_responses
        
    except Exception as e:
        logger.error(f"Error getting feeds: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feeds: {str(e)}"
        )

@router.get("/feeds/{feed_id}", response_model=FeedDetailsResponse)
async def get_feed_by_id(
    feed_id: str,
    db: Session = Depends(get_db)
):
    """
    Get a specific feed by ID
    """
    try:
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        
        if not feed:
            raise HTTPException(
                status_code=404,
                detail=f"Feed with ID {feed_id} not found"
            )
        
        return FeedDetailsResponse(
            feed_id=str(feed.id),
            fd_code=feed.fd_code,  # Fixed: using fd_code instead of feed_code
            fd_name=feed.fd_name,
            fd_type=feed.fd_type,
            fd_category=feed.fd_category,
            fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,
            fd_country_name=feed.fd_country_name,
            fd_country_cd=feed.fd_country_cd,
            fd_dm=feed.fd_dm,
            fd_ash=feed.fd_ash,
            fd_cp=feed.fd_cp,
            fd_ee=feed.fd_ee,
            fd_st=feed.fd_st,
            fd_ndf=feed.fd_ndf,
            fd_adf=feed.fd_adf,
            fd_lg=feed.fd_lg,
            fd_ndin=feed.fd_ndin,
            fd_adin=feed.fd_adin,
            fd_ca=feed.fd_ca,
            fd_p=feed.fd_p,
            fd_cf=feed.fd_cf,
            fd_nfe=feed.fd_nfe,
            fd_hemicellulose=feed.fd_hemicellulose,
            fd_cellulose=feed.fd_cellulose,
            fd_npn_cp=feed.fd_npn_cp,
            # fd_country=feed.fd_country,  # DEPRECATED: Use fd_country_name instead
            fd_season=feed.fd_season,
            fd_orginin=feed.fd_orginin,
            fd_ipb_local_lab=feed.fd_ipb_local_lab,
            created_at=feed.created_at,
            updated_at=feed.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Error getting feed {feed_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get feed: {str(e)}"
        )

@router.post("/feeds/create-new-feed/", response_model=FeedDetailsResponse, status_code=status.HTTP_201_CREATED)
async def create_feed(
    feed_data: dict,
    db: Session = Depends(get_db)
):
    """
    Create a new feed
    """
    try:
        # Create new feed instance
        new_feed = Feed(**feed_data)
        db.add(new_feed)
        db.commit()
        db.refresh(new_feed)
        
        return FeedDetailsResponse(
            feed_id=str(new_feed.id),
            fd_code=new_feed.fd_code,  # Fixed: using fd_code instead of feed_code
            fd_name=new_feed.fd_name,
            fd_type=new_feed.fd_type,
            fd_category=new_feed.fd_category,
            fd_country_id=str(new_feed.fd_country_id) if new_feed.fd_country_id else None,
            fd_country_name=new_feed.fd_country_name,
            fd_country_cd=new_feed.fd_country_cd,
            # Convert string values to float for response
            fd_dm=float(new_feed.fd_dm) if new_feed.fd_dm is not None else None,
            fd_ash=float(new_feed.fd_ash) if new_feed.fd_ash is not None else None,
            fd_cp=float(new_feed.fd_cp) if new_feed.fd_cp is not None else None,
            fd_ee=float(new_feed.fd_ee) if new_feed.fd_ee is not None else None,
            fd_st=float(new_feed.fd_st) if new_feed.fd_st is not None else None,
            fd_ndf=float(new_feed.fd_ndf) if new_feed.fd_ndf is not None else None,
            fd_adf=float(new_feed.fd_adf) if new_feed.fd_adf is not None else None,
            fd_lg=float(new_feed.fd_lg) if new_feed.fd_lg is not None else None,
            fd_ndin=float(new_feed.fd_ndin) if new_feed.fd_ndin is not None else None,
            fd_adin=float(new_feed.fd_adin) if new_feed.fd_adin is not None else None,
            fd_ca=float(new_feed.fd_ca) if new_feed.fd_ca is not None else None,
            fd_p=float(new_feed.fd_p) if new_feed.fd_p is not None else None,
            fd_cf=float(new_feed.fd_cf) if new_feed.fd_cf is not None else None,
            fd_nfe=float(new_feed.fd_nfe) if new_feed.fd_nfe is not None else None,
            fd_hemicellulose=float(new_feed.fd_hemicellulose) if new_feed.fd_hemicellulose is not None else None,
            fd_cellulose=float(new_feed.fd_cellulose) if new_feed.fd_cellulose is not None else None,
            fd_npn_cp=new_feed.fd_npn_cp,
            # fd_country=new_feed.fd_country,  # DEPRECATED: Use fd_country_name instead
            fd_season=new_feed.fd_season,  # Fixed: using fd_season instead of season
            fd_orginin=new_feed.fd_orginin,  # Fixed: using fd_orginin
            fd_ipb_local_lab=new_feed.fd_ipb_local_lab,  # Fixed: using fd_ipb_local_lab instead of id_ipb_local_lab
            created_at=new_feed.created_at,
            updated_at=new_feed.updated_at
        )
        
    except Exception as e:
        db.rollback()
        animal_logger.error(f"Error creating feed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create feed: {str(e)}"
        )

@router.put("/feeds/update-feed/{feed_id}", response_model=FeedDetailsResponse)
async def update_feed(
    feed_id: str,
    feed_data: dict,
    db: Session = Depends(get_db)
):
    """
    Update an existing feed
    """
    try:
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        
        if not feed:
            raise HTTPException(
                status_code=404,
                detail=f"Feed with ID {feed_id} not found"
            )
        
        # Update feed attributes
        for key, value in feed_data.items():
            if hasattr(feed, key):
                setattr(feed, key, value)
        
        feed.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(feed)
        
        return FeedDetailsResponse(
            feed_id=str(feed.id),
            fd_code=feed.fd_code,  # Fixed: using fd_code instead of feed_code
            fd_name=feed.fd_name,
            fd_type=feed.fd_type,
            fd_category=feed.fd_category,
            fd_country_id=str(feed.fd_country_id) if feed.fd_country_id else None,
            fd_country_name=feed.fd_country_name,
            fd_country_cd=feed.fd_country_cd,
            # Convert string values to float for response
            fd_dm=float(feed.fd_dm) if feed.fd_dm is not None else None,
            fd_ash=float(feed.fd_ash) if feed.fd_ash is not None else None,
            fd_cp=float(feed.fd_cp) if feed.fd_cp is not None else None,
            fd_ee=float(feed.fd_ee) if feed.fd_ee is not None else None,
            fd_st=float(feed.fd_st) if feed.fd_st is not None else None,
            fd_ndf=float(feed.fd_ndf) if feed.fd_ndf is not None else None,
            fd_adf=float(feed.fd_adf) if feed.fd_adf is not None else None,
            fd_lg=float(feed.fd_lg) if feed.fd_lg is not None else None,
            fd_ndin=float(feed.fd_ndin) if feed.fd_ndin is not None else None,
            fd_adin=float(feed.fd_adin) if feed.fd_adin is not None else None,
            fd_ca=float(feed.fd_ca) if feed.fd_ca is not None else None,
            fd_p=float(feed.fd_p) if feed.fd_p is not None else None,
            fd_cf=float(feed.fd_cf) if feed.fd_cf is not None else None,
            fd_nfe=float(feed.fd_nfe) if feed.fd_nfe is not None else None,
            fd_hemicellulose=float(feed.fd_hemicellulose) if feed.fd_hemicellulose is not None else None,
            fd_cellulose=float(feed.fd_cellulose) if feed.fd_cellulose is not None else None,
            fd_npn_cp=feed.fd_npn_cp,
            # fd_country=feed.fd_country,  # DEPRECATED: Use fd_country_name instead
            fd_season=feed.fd_season,  # Fixed: using fd_season instead of season
            fd_orginin=feed.fd_orginin,  # Fixed: using fd_orginin
            fd_ipb_local_lab=feed.fd_ipb_local_lab,  # Fixed: using fd_ipb_local_lab
            created_at=feed.created_at,
            updated_at=feed.updated_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating feed {feed_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update feed: {str(e)}"
        )

@router.delete("/feeds/delete-feed/{feed_id}")
async def delete_feed(
    feed_id: str,
    db: Session = Depends(get_db)
):
    """
    Delete a feed
    """
    try:
        feed = db.query(Feed).filter(Feed.id == feed_id).first()
        
        if not feed:
            raise HTTPException(
                status_code=404,
                detail=f"Feed with ID {feed_id} not found"
            )
        
        db.delete(feed)
        db.commit()
        
        return {"message": f"Feed with ID {feed_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting feed {feed_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete feed: {str(e)}"
        )


@router.post("/diet-recommendation-working/")
async def diet_recommendation_working(user_inputs: DietRecommendationRequest, db: Session = Depends(get_db)):
    """
    NEW WORKING VERSION: Generate diet recommendation using RFT_fv.py logic
    Based on the provided Python code, adapted for the Feed Formulation Backend API
    
    - **simulation_id**: Unique simulation identifier in format abc-1234
    - **cattle_info**: Cattle characteristics and requirements
    - **feed_selection**: Array of feed UUIDs to include in calculation
    """
    try:
        # Helper function to format values with units
        def format_value_with_unit(value, unit):
            """Format value with unit, handling smart decimal precision and null values"""
            if value is None or value == "":
                return None
            if value == 0:
                return 0
            
            # Check if value is a whole number
            if isinstance(value, (int, float)) and value == int(value):
                return f"{int(value)} {unit}"
            else:
                return f"{value:.2f} {unit}"
        
        # Generate report_id at the very beginning with database uniqueness check
        from services.pdf_service import generate_report_id
        report_id = generate_report_id('rec', db)
        
        # Extract simulation ID from request
        simulation_id = user_inputs.simulation_id
        case_identifier = f"SIM_{simulation_id}"
        
        # Log the complete user input for debugging and analysis
        animal_logger.info(f"[{case_identifier}] NEW WORKING VERSION - Diet recommendation request received | Report ID: {report_id} | User inputs: {user_inputs}")
        
        # Extract data from the Pydantic model
        feed_selection = user_inputs.feed_selection
        cattle_info = user_inputs.cattle_info
        
        # Validate feed selection is not empty
        if not feed_selection:
            # Import and use improved error handling
            from middleware.error_handlers import raise_user_friendly_http_exception
            
            # Raise user-friendly error
            raise_user_friendly_http_exception("Feed selection cannot be empty. Please select at least one feed.", simulation_id, animal_logger)
        
        # Extract feed IDs and create price mapping
        feed_ids = [feed.feed_id for feed in feed_selection]
        feed_prices = {feed.feed_id: feed.price_per_kg for feed in feed_selection}
        
        # Log the feed IDs and prices for debugging
        animal_logger.info(f"[{case_identifier}] Feed IDs: {feed_ids}")
        animal_logger.info(f"[{case_identifier}] Feed prices: {feed_prices}")
        
        # Step 1: Convert API format to diet_recommendation.py format
        # Map API format to diet_recommendation.py format (following exact pattern from diet_recommendation.py)
        
        # Topography mapping logic (following diet_recommendation.py pattern)
        topography_mapping = {
            "Flat": 0,
            "Hilly": 1,
            "Mountainous": 2
        }
        env_topog = topography_mapping.get(cattle_info.topography, 0)
        
        # Create animal_inputs dictionary with mapped values
        animal_inputs = {
            "An_StatePhys": "Lactating Cow",  # Always hardcoded as requested
            "An_Breed": cattle_info.breed,
            "An_BW": cattle_info.body_weight,
            "Trg_FrmGain": cattle_info.bw_gain,
            "An_BCS": cattle_info.bc_score,
            "An_LactDay": cattle_info.days_in_milk,
            "Trg_MilkProd_L": cattle_info.milk_production,
            "Trg_MilkTPp": cattle_info.tp_milk,
            "Trg_MilkFatp": cattle_info.fat_milk,
            "An_Parity": cattle_info.parity,
            "An_GestDay": cattle_info.days_of_pregnancy,
            "Env_TempCurr": cattle_info.temperature,
            "Env_Grazing": 1,  # Always set to 1 (non-grazing)
            "Env_Dist_km": cattle_info.distance,
            "Env_Topog": env_topog
        }
        
        animal_logger.info(f"[{case_identifier}] Converted cattle info to diet_recommendation format: {animal_inputs}")
        
        # Step 2: Process feeds from database
        # First try standard feeds, then custom feeds for missing ones
        standard_feeds = db.query(Feed).filter(Feed.id.in_(feed_ids)).all()
        found_standard_ids = {str(feed.id) for feed in standard_feeds}
        
        # Only query custom feeds for missing IDs
        missing_ids = [fid for fid in feed_ids if fid not in found_standard_ids]
        custom_feeds = []
        if missing_ids:
            custom_feeds = db.query(CustomFeed).filter(CustomFeed.id.in_(missing_ids)).all()
            found_custom_ids = {str(feed.id) for feed in custom_feeds}
            
            # Check if all missing IDs were found in custom feeds
            still_missing = [fid for fid in missing_ids if fid not in found_custom_ids]
            if still_missing:
                raise ValueError(f"Some feeds not found: {still_missing}")
        
        # Combine results
        feeds = list(standard_feeds) + list(custom_feeds)
        
        animal_logger.info(f"[{case_identifier}] Found {len(feeds)} feeds in database")
        
        # Convert database feeds to DataFrame format (same as Excel processing)
        import pandas as pd
        import numpy as np
        
        feed_data_list = []
        for feed in feeds:
            feed_id = str(feed.id)
            price = feed_prices.get(feed_id, 0.0)
            
            def safe_float(value):
                if value is None or value == '':
                    return 0.0
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0.0
            
            feed_data_list.append({
                'Fd_Name': feed.fd_name or "Unknown Feed",
                'Fd_Category': feed.fd_category or "Unknown",
                'Fd_Type': feed.fd_type or "Unknown",
                'Fd_Cost': price,
                'Fd_DM': safe_float(feed.fd_dm),
                'Fd_CP': safe_float(feed.fd_cp),
                'Fd_NDF': safe_float(feed.fd_ndf),
                'Fd_EE': safe_float(feed.fd_ee),
                'Fd_St': safe_float(feed.fd_st),
                'Fd_Ca': safe_float(feed.fd_ca),
                'Fd_P': safe_float(feed.fd_p),
                'Fd_Ash': safe_float(feed.fd_ash),
                'Fd_CF': safe_float(feed.fd_cf),
                'Fd_NPN_CP': feed.fd_npn_cp or 0,
                'Fd_NDIN': safe_float(feed.fd_ndin),
                'Fd_ADIN': safe_float(feed.fd_adin),
                'Fd_Lg': safe_float(feed.fd_lg),
                'Fd_Hemicellulose': safe_float(feed.fd_hemicellulose),
                'Fd_ADF': safe_float(feed.fd_adf),
                'Fd_Cellulose': safe_float(feed.fd_cellulose),
                'NFE (%)': safe_float(feed.fd_nfe),
                'Fd_Country': feed.fd_country_name or ""  # FIXED: Use fd_country_name
            })
        
        animal_logger.info(f"[{case_identifier}] Created feed_data_list with {len(feed_data_list)} feeds")
        
        # Create DataFrame from feed data (same as Excel processing)
        f = pd.DataFrame(feed_data_list)
        f = f.dropna(subset=["Fd_Name"])  # Remove rows with NA values in Fd_Name
        
        animal_logger.info(f"[{case_identifier}] Created DataFrame with {len(f)} feeds")
        
        # Apply same nutritional calculations as in diet_recommendation.py
        # Energy values according to NRC 2001
        f['Fd_PAF'] = 1  # general PAF value for all feeds
        
        # Calculate missing parameters of feed ingredients
        # Organic matter
        f["Fd_OM"] = 100 - f["Fd_Ash"]
        f["Fd_OM"] = f["Fd_OM"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Non Forage Carbohydrates
        f["Fd_NFC"] = f["Fd_OM"] - (f["Fd_NDF"] + f["Fd_EE"] + f["Fd_CP"])
        f["Fd_NFC"] = f["Fd_NFC"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Calculate Fd_NDFIP and Fd_ADFIP
        f["Fd_NDFIP"] = f["Fd_NDIN"] * 6.25
        f["Fd_ADFIP"] = f["Fd_ADIN"] * 6.25
        
        f["Fd_NDFn"] = f["Fd_NDF"] - f["Fd_NDFIP"]
        f["Fd_NDFn"] = f["Fd_NDFn"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        f["Fd_tdNFC"] = 0.98 * (100 - (f["Fd_NDFn"] + f["Fd_CP"] + f["Fd_EE"] + f["Fd_Ash"]) * f["Fd_PAF"])
        f["Fd_tdNFC"] = f["Fd_tdNFC"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Fd_tdCP
        f["Fd_tdCP"] = np.nan
        mask_forage = f["Fd_Type"] == "Forage"
        mask_conc = f["Fd_Type"] == "Concentrate"
        exp_val = lambda row: row["Fd_CP"] * np.exp(-1.2 * (row["Fd_ADFIP"] / row["Fd_CP"])) if row["Fd_CP"] != 0 else 0
        f.loc[mask_forage | mask_conc, "Fd_tdCP"] = f[mask_forage | mask_conc].apply(exp_val, axis=1)
        for cat in ["Minerals", "Additive", "Sugar/Sugar Alcohol"]:
            f.loc[f["Fd_Category"] == cat, "Fd_tdCP"] = 0
        
        # Fd_cFA and Fd_ctdFA
        f["Fd_FA"] = np.where(f["Fd_EE"] < 1, 0, f["Fd_EE"] - 1)
        f["Fd_ctdFA"] = f["Fd_FA"]
        
        # Fd_tdNDF
        f["Fd_tdNDF"] = 0.75 * (f["Fd_NDFn"] - f["Fd_Lg"]) * (1 - np.power((f["Fd_Lg"] / f["Fd_NDFn"]).replace(0, np.nan), 0.667))
        f["Fd_tdNDF"] = f["Fd_tdNDF"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Set constants
        de_NFC = 4.2
        de_NDF = 4.2
        de_CP = 5.6
        de_FA = 9.4
        loss_constant = 0.3
        
        # Weiss et al., 2018.
        f["Fd_GE"] = (f["Fd_CP"] * de_CP/100) + (f["Fd_FA"] * de_FA/100) + (100 - f["Fd_CP"] - f["Fd_FA"] - f["Fd_Ash"]) * 0.042
        f["Fd_GE"] = f["Fd_GE"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        mask_v_m = (f["Fd_Category"] == "Minerals")
        f.loc[mask_v_m, "Fd_GE"] = 0
        
        # Fd_DE NRC 2001
        f["Fd_DE"] = (
            ((f["Fd_tdNFC"] / 100) * de_NFC) +
            ((f["Fd_tdNDF"] / 100) * de_NDF) +
            ((f["Fd_tdCP"] / 100) * de_CP) +
            ((f["Fd_ctdFA"] / 100) * de_FA)
            - loss_constant
        )
        f["Fd_DE"] = f["Fd_DE"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # DE for additives with NPN (urea)
        mask_npn = (f["Fd_Category"] == "Additive") & (f["Fd_NPN_CP"] > 0)
        f.loc[mask_npn, "Fd_DE"] *= (
                1 - (f.loc[mask_npn, "Fd_CP"] * f.loc[mask_npn, "Fd_NPN_CP"] / 28200)
            )
        
        # Set to 0 for specific categories
        for cat in ["Minerals"]:
            f.loc[f["Fd_Category"] == cat, "Fd_DE"] = 0
        
        # Simplified - GEO # Mcal/kg
        f["Fd_ME"] = 0.82 * f["Fd_DE"]
        f["Fd_ME"] = f["Fd_ME"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Simplified - GEO
        f["Fd_TDN"] = 100 * (f["Fd_DE"] / 4.4)  # % of DM
        f["Fd_TDN"] = f["Fd_TDN"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        f["Fd_NEl"] = 0.0245 * f["Fd_TDN"] - 0.12  # Mcal/kg
        f["Fd_NEl"] = f["Fd_NEl"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Feeds - Extra logic used sometimes - better to keep it here
        f["Fd_Conc"] = f.apply(lambda row: 100 if row["Fd_Type"] == "Concentrate" else 0, axis=1)
        f["Fd_For"] = 100 - f["Fd_Conc"]
        f["Fd_ForWet"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] < 71 else 0, axis=1)
        f["Fd_ForDry"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] >= 71 else 0, axis=1)
        f["Fd_Past"] = f.apply(lambda row: 100 if row["Fd_Category"] == "Pasture" else 0, axis=1)
        
        f["Fd_ForNDF"] = (1 - f["Fd_Conc"] / 100) * f["Fd_NDF"]
        f["Fd_NDFnf"] = f["Fd_NDF"] - f["Fd_NDFIP"]  # NDF N free
        
        # Absorption coefficients for minerals
        if "Fd_acCa" not in f.columns:
            f["Fd_acCa"] = None
            f["Fd_acCa"] = f.apply(lambda row: 0.4 if row["Fd_Type"] == "Forage" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_Type"] == "Concentrate" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_Category"] == "Minerals" else row["Fd_acCa"], axis=1)
        else:
            f["Fd_acCa"] = f.apply(lambda row: 0.4 if row["Fd_acCa"] == 0 and row["Fd_Type"] == "Forage" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_acCa"] == 0 and row["Fd_Type"] == "Concentrate" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_acCa"] == 0 and row["Fd_Category"] == "Minerals" else row["Fd_acCa"], axis=1)
        
        if "Fd_acP" not in f.columns:
            f["Fd_acP"] = None
            f["Fd_acP"] = f.apply(lambda row: 0.64 if row["Fd_Type"] == "Forage" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_Type"] == "Concentrate" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_Category"] == "Minerals" else row["Fd_acP"], axis=1)
        else:
            f["Fd_acP"] = f.apply(lambda row: 0.64 if row["Fd_acP"] == 0 and row["Fd_Type"] == "Forage" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_acP"] == 0 and row["Fd_Type"] == "Concentrate" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_acP"] == 0 and row["Fd_Category"] == "Minerals" else row["Fd_acP"], axis=1)
        
        # Change unit of some parameters from % of DM to Kg
        f["Fd_CostDM"] = f["Fd_Cost"] / (f["Fd_DM"] / 100)
        
        f["Fd_CP_kg"] = f["Fd_CP"] / 100  # CP kg
        f["Fd_NDF_kg"] = f["Fd_NDF"] / 100  # NDF
        f["Fd_ForNDF_kg"] = np.where(f["Fd_Type"] == "Forage", f["Fd_NDF_kg"], 0)  # NDF from forage type
        f["Fd_St_kg"] = f["Fd_St"] / 100  # Starch
        f["Fd_EE_kg"] = f["Fd_EE"] / 100  # EE
        f["Fd_Ca_kg"] = (f["Fd_Ca"] * f["Fd_acCa"]) / 100  # Ca multiplied by its absorption coefficient
        f["Fd_P_kg"] = (f["Fd_P"] * f["Fd_acP"]) / 100  # P multiplied by its absorption coefficient
        
        f["Fd_Type"] = np.where((f["Fd_Type"] == "Concentrate") & (f["Fd_Category"] == "Minerals"), "Minerals", f["Fd_Type"])
        
        f["Fd_isFat"] = (f["Fd_EE"] > 50).astype(int)
        f["Fd_isMi"] = np.where(f["Fd_Type"] == "Minerals", 1, 0)
        f["Fd_isconc"] = np.where(f["Fd_Type"] == "Concentrate", 1, 0)
        f["Fd_isbyprod"] = f["Fd_Category"].str.contains(r"\bby[-\s]?prod", case=False, regex=True).astype(int)
        f["Fd_isconc_only"] = np.where((f["Fd_isconc"] == 1) & (f["Fd_isbyprod"] == 0) & (f["Fd_isFat"] == 0), 1, 0)
        
        # Add Placeholders for the following columns
        f["Fd_DMIn"] = 1
        f["Fd_AFIn"] = 1
        f["Fd_TDNact"] = 1
        f["Fd_DEact"] = 1
        f["Fd_MEact"] = 1
        f["Fd_NEl_A"] = 1
        f["Fd_NEm"] = 1
        f["Fd_NEg"] = 1
        
        animal_logger.info(f"[{case_identifier}] Applied all nutritional calculations")
        
        # Create f_nd and Dt with same structure as Excel processing
        from services.diet_recommendation import preprocess_dataframe
        f = preprocess_dataframe(f)
        
        # Create f_nd dictionary (same as Excel processing)
        f_nd = {col: f[col].to_numpy() for col in f.columns}
        
        # Create Dt DataFrame (same as Excel processing)
        Dt = pd.DataFrame({
            "Ingr_Category": f["Fd_Category"],
            "Ingr_Type": f["Fd_Type"],
            "Ingr_Name": f["Fd_Name"],
            "Intake_DM": f["Fd_DMIn"],
            "Intake_AF": f["Fd_AFIn"]
        })
        
        animal_logger.info(f"[{case_identifier}] Created f_nd and Dt with {len(f_nd)} columns and {len(Dt)} rows")
        
        # Step 3: Call dr_main() for optimization and analysis
        #from dr_use import dr_main
        from core.optimization.rationsmart import rsm_main
        
        animal_logger.info(f"[{case_identifier}] Starting diet optimization with rationsmart.py")
        
        # Get user_id from the request body
        user_id = user_inputs.user_id
        
        # Call rsm_main() with all required parameters
        optimization_results = rsm_main(
            animal_inputs=animal_inputs,
            feed_data=f,
            simulation_id=simulation_id,
            user_id=user_id,
            report_id=report_id
        )
        
        # Check if optimization was successful
        if optimization_results.get('status') == 'ERROR':
            error_message = optimization_results.get('error_message', 'Unknown error')
            animal_logger.error(f"[{case_identifier}] Diet optimization failed: {error_message}")
            raise HTTPException(status_code=500, detail=f"Diet optimization failed: {error_message}")
        
        animal_logger.info(f"[{case_identifier}] Diet optimization completed successfully")
        
        # Step 4: Generate HTML report from optimization results
        try:
            from core.optimization.report_generation import rsm_generate_report
            from services.auth_utils import get_user_by_id
            
            # Fetch user name from database
            user_info = get_user_by_id(db, user_inputs.user_id)
            user_name = user_info.name if user_info else user_inputs.user_id
            
            html_report_path = f"result_html/diet_report_{simulation_id}.html"
            rsm_generate_report(
                optimization_results['post_results'], 
                optimization_results['animal_requirements'], 
                html_report_path,
                user_name=user_name,
                simulation_id=simulation_id,
                report_id=report_id
            )
            animal_logger.info(f"[{case_identifier}] Generated HTML report: {html_report_path}")
        except Exception as e:
            animal_logger.error(f"[{case_identifier}] HTML report generation failed: {e}")
            html_report_path = None
        
        # Step 5: Generate PDF, upload to AWS S3, and store in reports table (async)
        pdf_url = None
        # Always generate PDF (removed dependency on local PDF generation)
        try:
            # Call the existing function to handle PDF generation, AWS upload, and reports table storage
            from services.pdf_service import rec_pdf_report_generator
            
            # Create the API response data for the function
            api_response_data = {
                'simulation_id': simulation_id,
                'report_id': report_id,
                'status': 'SUCCESS',
                'solution_status': optimization_results.get('status_classification', 'UNKNOWN'),
                'confidence_level': optimization_results.get('confidence_level', 'UNKNOWN'),
                'total_cost': optimization_results.get('total_cost', 0.0),
                'water_intake': optimization_results.get('water_intake', 0.0),
                'diet_proportions': optimization_results.get('dt_proportions', []),
                'animal_requirements': optimization_results.get('animal_requirements', {}),
                'ration_evaluation': optimization_results.get('ration_evaluation', {}),
                'methane_report': optimization_results.get('methane_report', {}),
                'html_report_path': html_report_path,
                'pdf_report_path': None,  # No longer needed since we generate PDF directly
                'generated_at': datetime.now().isoformat(),
                'user_id': user_id,
                'case_identifier': case_identifier
            }
            
            # Call the function asynchronously (fire-and-forget)
            rec_pdf_report_generator(api_response_data, user_id, simulation_id, report_id, db)
            
            animal_logger.info(f"[{case_identifier}] PDF generation and AWS upload initiated for report_id: {report_id}")
            
        except Exception as e:
            animal_logger.error(f"[{case_identifier}] Failed to initiate PDF generation and AWS upload: {str(e)}")
            pdf_url = None
        
        # Step 6: Create API response
        # Get user name from database
        from services.auth_utils import get_user_by_id
        user_info = get_user_by_id(db, user_id)
        user_name = user_info.name if user_info else "Unknown User"
        
        # Extract the actual optimization results from the nested structure
        post_results = optimization_results.get('post_results', {})
        
        # Debug logging to understand the data structure
        animal_logger.info(f"[{case_identifier}] DEBUG: optimization_results keys: {list(optimization_results.keys())}")
        animal_logger.info(f"[{case_identifier}] DEBUG: post_results keys: {list(post_results.keys())}")
        if 'animal_inputs' in post_results:
            animal_logger.info(f"[{case_identifier}] DEBUG: animal_inputs keys: {list(post_results['animal_inputs'].keys())}")
        if 'diet_table' in post_results:
            animal_logger.info(f"[{case_identifier}] DEBUG: diet_table type: {type(post_results['diet_table'])}")
            if hasattr(post_results['diet_table'], 'to_dict'):
                animal_logger.info(f"[{case_identifier}] DEBUG: diet_table shape: {post_results['diet_table'].shape}")
                try:
                    columns = list(post_results['diet_table'].columns)
                    animal_logger.info(f"[{case_identifier}] DEBUG: diet_table columns: {columns}")
                    head_data = post_results['diet_table'].head().to_dict('records')
                    animal_logger.info(f"[{case_identifier}] DEBUG: diet_table head: {head_data}")
                except Exception as e:
                    animal_logger.error(f"[{case_identifier}] DEBUG: Error getting diet_table details: {e}")
        if 'methane_report' in post_results:
            animal_logger.info(f"[{case_identifier}] DEBUG: methane_report type: {type(post_results['methane_report'])}")
            if hasattr(post_results['methane_report'], 'to_dict'):
                animal_logger.info(f"[{case_identifier}] DEBUG: methane_report shape: {post_results['methane_report'].shape}")
                animal_logger.info(f"[{case_identifier}] DEBUG: methane_report columns: {list(post_results['methane_report'].columns)}")
                animal_logger.info(f"[{case_identifier}] DEBUG: methane_report head: {post_results['methane_report'].head().to_dict('records')}")
        if 'Dt_kg' in post_results:
            animal_logger.info(f"[{case_identifier}] DEBUG: Dt_kg type: {type(post_results['Dt_kg'])}")
            if hasattr(post_results['Dt_kg'], 'to_dict'):
                animal_logger.info(f"[{case_identifier}] DEBUG: Dt_kg shape: {post_results['Dt_kg'].shape}")
                animal_logger.info(f"[{case_identifier}] DEBUG: Dt_kg columns: {list(post_results['Dt_kg'].columns)}")
                animal_logger.info(f"[{case_identifier}] DEBUG: Dt_kg head: {post_results['Dt_kg'].head().to_dict('records')}")
        
        # Extract animal information from post_results
        animal_inputs = post_results.get('animal_inputs', {})
        animal_information = {
            'breed': animal_inputs.get('An_Breed', '') or None,
            'body_weight': format_value_with_unit(animal_inputs.get('An_BW', 0.0), 'Kg'),
            'bw_gain': format_value_with_unit(animal_inputs.get('Trg_FrmGain', 0.0), 'kg/day'),
            'bc_score': animal_inputs.get('An_BCS', 0.0) or None,
            'days_in_milk': format_value_with_unit(animal_inputs.get('An_LactDay', 0), 'Days'),
            'milk_production': format_value_with_unit(animal_inputs.get('Trg_MilkProd_L', 0.0), 'Liter'),
            'tp_milk': format_value_with_unit(animal_inputs.get('Trg_MilkTPp', 0.0), '%'),
            'fat_milk': format_value_with_unit(animal_inputs.get('Trg_MilkFatp', 0.0), '%'),
            'parity': animal_inputs.get('An_Parity', 0) or None,
            'days_of_pregnancy': format_value_with_unit(animal_inputs.get('An_GestDay', 0), 'Days'),
            'temperature': format_value_with_unit(animal_inputs.get('Env_TempCurr', 0.0), '°C'),
            'distance': format_value_with_unit(animal_inputs.get('Env_Dist', 0.0), 'km'),
            'topography': 'Flat' if animal_inputs.get('Env_Topo', 0) == 0 else 'Hilly'
        }
        
        # Extract least cost diet data from post_results
        diet_table = post_results.get('diet_table', [])
        least_cost_diet = []
        total_diet_cost = 0.0
        
        if hasattr(diet_table, 'to_dict'):
            # If it's a DataFrame, convert to list of dicts
            diet_records = diet_table.to_dict('records')
        else:
            # If it's already a list
            diet_records = diet_table if isinstance(diet_table, list) else []
        
        for feed in diet_records:
            # Use correct column names from diet_table DataFrame
            quantity_kg_day = feed.get('Inclusion_AF_kg', 0.0)
            if quantity_kg_day > 0:  # Only include feeds with non-zero quantities
                feed_cost = feed.get('Total_Cost', 0.0)
                total_diet_cost += feed_cost
                
                feed_item = {
                    'feed_name': feed.get('Ingredient', ''),
                    'quantity_kg_per_day': round(quantity_kg_day, 2),
                    'price_per_kg': round(feed.get('Cost_per_kg', 0.0), 2),
                    'daily_cost': round(feed_cost, 2)
                }
                
                least_cost_diet.append(feed_item)
        
        # Extract environment impact data from post_results
        methane_report = post_results.get('methane_report', {})
        environmental_impact = {
            'methane_production_grams_per_day': str(0.0),
            'methane_yield_grams_per_kg_dmi': str(0.0),
            'methane_intensity_grams_per_kg_ecm': str(0.0),
            'methane_conversion_rate_percent': str(0.0)
        }
        
        # Handle methane_report as DataFrame with Metric/Value structure
        if hasattr(methane_report, 'to_dict'):
            # If it's a DataFrame, convert to dict and extract values
            methane_dict = methane_report.to_dict('records')
            if methane_dict and len(methane_dict) > 0:
                # Create a lookup dictionary from the Metric/Value structure
                methane_lookup = {row['Metric']: row['Value'] for row in methane_dict}
                environmental_impact = {
                    'methane_production_grams_per_day': str(methane_lookup.get('Methane Production (g/day)', 0.0)),
                    'methane_yield_grams_per_kg_dmi': str(methane_lookup.get('Methane Yield (g/kg DMI)', 0.0)),
                    'methane_intensity_grams_per_kg_ecm': str(methane_lookup.get('Methane Intensity (g/kg ECM)', 0.0)),
                    'methane_conversion_rate_percent': str(methane_lookup.get('Methane Conversion Rate (%)', 0.0))
                }
        elif isinstance(methane_report, dict):
            # If it's already a dict
            environmental_impact = {
                'methane_production_grams_per_day': str(methane_report.get('methane_production_grams_day', 0.0)),
                'methane_yield_grams_per_kg_dmi': str(methane_report.get('methane_yield_grams_kg_dmi', 0.0)),
                'methane_intensity_grams_per_kg_ecm': str(methane_report.get('methane_intensity_grams_kg_ecm', 0.0)),
                'methane_conversion_rate_percent': str(methane_report.get('methane_conversion_rate_percent', 0.0))
            }
        
        # Extract warnings and recommendations from post_results
        messages = post_results.get('messages', [])
        warnings = [msg for msg in messages if 'warning' in msg.lower() or 'error' in msg.lower()]
        recommendations = [msg for msg in messages if 'recommendation' in msg.lower() or 'suggestion' in msg.lower()]
        
        # Get dry matter intake from Dt_kg DataFrame
        dt_kg = post_results.get('Dt_kg', {})
        dry_matter_intake = 0.0
        
        if hasattr(dt_kg, 'to_dict'):
            # If it's a DataFrame, convert to dict and extract values
            dt_dict = dt_kg.to_dict('records')
            if dt_dict and len(dt_dict) > 0:
                # Look for the 'Total' row which contains the sum of Intake_DM
                for row in dt_dict:
                    if row.get('Ingr_Name') == 'Total':
                        dry_matter_intake = row.get('Intake_DM', 0.0)
                        break
                else:
                    # If no Total row found, sum the Intake_DM from all rows
                    dry_matter_intake = sum(row.get('Intake_DM', 0.0) for row in dt_dict)
        elif isinstance(dt_kg, dict):
            dry_matter_intake = dt_kg.get('Intake_DM', 0.0)
        
        # Create new response body structure
        response_data = {
            'report_info': {
                'simulation_id': simulation_id,
                'report_id': report_id,
                'user_name': user_name,
                'generated_date': datetime.now().isoformat()
            },
            'solution_summary': {
                'daily_cost': round(post_results.get('total_cost', 0.0), 2),
                'milk_production': animal_information.get('milk_production', 0.0),
                'dry_matter_intake': format_value_with_unit(dry_matter_intake, 'kg/day')
            },
            'animal_information': animal_information,
            'least_cost_diet': least_cost_diet if least_cost_diet else [],
            'total_diet_cost': round(total_diet_cost, 2),
            'environmental_impact': environmental_impact,
            'additional_information': {
                'warnings': warnings if warnings else [],
                'recommendations': recommendations if recommendations else []
            }
        }
        
        animal_logger.info(f"[{case_identifier}] Response generation completed successfully")
        
        # Return the complete response
        return response_data

    except Exception as e:
        animal_logger.error(f"[{case_identifier}] Error in diet recommendation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Diet recommendation failed: {str(e)}")

def create_diet_recommendation_response(post_results, animal_requirements, f_nd, simulation_id):
    """
    Create structured JSON response from post-optimization results.
    
    Parameters:
    -----------
    post_results : dict
        Results from run_post_optimization_analysis()
    animal_requirements : dict
        Animal requirements from calculate_an_requirements()
    f_nd : dict
        Feed nutritional data
    simulation_id : str
        Simulation identifier
        
    Returns:
    --------
    dict : Structured response data
    """
    try:
        # Extract key data from post_results
        dt_proportions = post_results.get('dt_proportions', pd.DataFrame())
        methane_report = post_results.get('methane_report', pd.DataFrame())
        ration_evaluation = post_results.get('ration_evaluation', pd.DataFrame())
        
        # Create animal characteristics data
        animal_characteristics = {
            "characteristics": [
                {"characteristic": "Body Weight", "value": animal_requirements.get("An_BW", 0), "unit": "kg"},
                {"characteristic": "Breed", "value": animal_requirements.get("An_Breed", ""), "unit": ""},
                {"characteristic": "Parity", "value": animal_requirements.get("An_Parity", 0), "unit": ""},
                {"characteristic": "Days in Milk", "value": animal_requirements.get("An_LactDay", 0), "unit": "days"},
                {"characteristic": "Milk Production", "value": animal_requirements.get("Trg_MilkProd_L", 0), "unit": "L/day"}
            ],
            "requirements": [
                {"characteristic": "Dry Matter Intake", "value": animal_requirements.get("Trg_Dt_DMIn", 0), "unit": "kg/day"},
                {"characteristic": "Net Energy Lactation", "value": animal_requirements.get("An_NEL", 0), "unit": "Mcal/kg"},
                {"characteristic": "Metabolizable Energy", "value": animal_requirements.get("An_ME", 0), "unit": "Mcal/kg"},
                {"characteristic": "Calcium Requirement", "value": animal_requirements.get("An_Ca_req", 0), "unit": "g/day"},
                {"characteristic": "Phosphorus Requirement", "value": animal_requirements.get("An_P_req", 0), "unit": "g/day"}
            ]
        }
        
        # Create diet summary detailed data
        selected_feeds = []
        if not dt_proportions.empty:
            for _, row in dt_proportions.iterrows():
                # Skip the 'Total' row
                if row.get('Name', '') == 'Total':
                    continue
                    
                # Get DM_kg value, handling different possible column names
                dm_kg = 0
                if 'DM_kg' in row:
                    dm_kg = row['DM_kg']
                elif 'Intake_DM_kg.d' in row:
                    dm_kg = row['Intake_DM_kg.d']
                elif 'Intake_DM' in row:
                    dm_kg = row['Intake_DM']
                
                if dm_kg > 0:  # Only include feeds with non-zero amounts
                    # Get feed name, handling different possible column names
                    feed_name = row.get('Name', row.get('Ingr_Name', 'Unknown'))
                    
                    # Get category, handling different possible column names
                    category = row.get('Ingr_Category', 'Unknown')
                    if pd.isna(category):
                        category = 'Unknown'
                    
                    # Get type, handling different possible column names
                    feed_type = row.get('Ingr_Type', 'Unknown')
                    if pd.isna(feed_type):
                        feed_type = 'Unknown'
                    
                    # Get AF_kg value, handling different possible column names
                    af_kg = 0
                    if 'AF_kg' in row:
                        af_kg = row['AF_kg']
                    elif 'Intake_AF_kg.d' in row:
                        af_kg = row['Intake_AF_kg.d']
                    elif 'Intake_AF' in row:
                        af_kg = row['Intake_AF']
                    
                    # Get DM percentage
                    dm_pct = row.get('DM_prop', row.get('DM_pct', 0))
                    
                    # Get cost per kg
                    cost_per_kg = row.get('Cost_per_kg', 0)
                    
                    # Get total cost
                    total_cost = row.get('Cost', 0)
                    
                    selected_feeds.append({
                        "name": str(feed_name),
                        "category": str(category),
                        "type": str(feed_type),
                        "dm_kg": float(dm_kg),
                        "af_kg": float(af_kg),
                        "dm_pct": float(dm_pct),
                        "cost_per_kg": float(cost_per_kg),
                        "total_cost": float(total_cost)
                    })
        
        # Calculate category breakdown
        category_breakdown = []
        if not dt_proportions.empty and len(selected_feeds) > 0:
            # Create a DataFrame from selected feeds for easier processing
            feeds_df = pd.DataFrame(selected_feeds)
            if not feeds_df.empty:
                category_totals = feeds_df.groupby('category').agg({
                    'dm_kg': 'sum',
                    'total_cost': 'sum'
                }).reset_index()
                
                total_dm = category_totals['dm_kg'].sum()
                
                for _, row in category_totals.iterrows():
                    if row['dm_kg'] > 0:
                        category_breakdown.append({
                            "category": row['category'],
                            "dm_kg": float(row['dm_kg']),
                            "percentage": float((row['dm_kg'] / total_dm) * 100) if total_dm > 0 else 0,
                            "cost": float(row['total_cost'])
                        })
        
        diet_summary_detailed = {
            "selected_feeds": selected_feeds,
            "total_dm": sum(feed['dm_kg'] for feed in selected_feeds),
            "total_cost": sum(feed['total_cost'] for feed in selected_feeds),
            "category_breakdown": category_breakdown
        }
        
        # Create diet summary (legacy format)
        diet_summary = {
            "total_dmi": sum(feed['dm_kg'] for feed in selected_feeds),
            "total_cost": sum(feed['total_cost'] for feed in selected_feeds),
            "feed_breakdown": selected_feeds
        }
        
        # Create nutrient comparison
        # Handle diet_summary_values as numpy array
        diet_summary_values = post_results.get('diet_summary_values', np.array([]))
        if isinstance(diet_summary_values, np.ndarray) and len(diet_summary_values) >= 11:
            # Based on the diet_supply function, the array contains:
            # [Supply_DMIn, Supply_Energy, Supply_MP, Supply_Ca, Supply_P, Supply_NDF, Supply_NDFfor, Supply_St, Supply_EE, Supply_NEl, Supply_ME]
            nel_supplied = float(diet_summary_values[9]) if len(diet_summary_values) > 9 else 0  # Supply_NEl
            me_supplied = float(diet_summary_values[10]) if len(diet_summary_values) > 10 else 0  # Supply_ME
            ca_supplied = float(diet_summary_values[3]) if len(diet_summary_values) > 3 else 0   # Supply_Ca
            p_supplied = float(diet_summary_values[4]) if len(diet_summary_values) > 4 else 0    # Supply_P
        else:
            nel_supplied = 0
            me_supplied = 0
            ca_supplied = 0
            p_supplied = 0
        
        nutrient_comparison = {
            "requirements": {
                "dm_intake": animal_requirements.get("Trg_Dt_DMIn", 0),
                "nel": animal_requirements.get("An_NEL", 0),
                "me": animal_requirements.get("An_ME", 0),
                "ca": animal_requirements.get("An_Ca_req", 0),
                "p": animal_requirements.get("An_P_req", 0)
            },
            "supplied": {
                "dm_intake": sum(feed['dm_kg'] for feed in selected_feeds),
                "nel": nel_supplied,
                "me": me_supplied,
                "ca": ca_supplied,
                "p": p_supplied
            }
        }
        
        # Create methane emissions data
        methane_emissions = {}
        if not methane_report.empty:
            # Extract methane data from the correct columns
            daily_emission = methane_report[methane_report['Metric'] == 'Methane Emission (g/day)']['Value'].iloc[0] if len(methane_report) > 0 else 0
            annual_emission = float(daily_emission) * 365 / 1000 if daily_emission != 0 else 0  # Convert g/day to kg/year
            emission_factor = methane_report[methane_report['Metric'] == 'Methane Emission (g/kg DMI)']['Value'].iloc[0] if len(methane_report) > 0 else 0
            
            methane_emissions = {
                "daily_emission": float(daily_emission),
                "annual_emission": float(annual_emission),
                "emission_factor": float(emission_factor)
            }
        
        # Create ration evaluation
        ration_eval = {}
        if not ration_evaluation.empty:
            ration_eval = {
                "status": post_results.get('status_classification', 'UNKNOWN'),
                "confidence": post_results.get('confidence_level', 'UNKNOWN'),
                "evaluation_summary": ration_evaluation.to_dict('records') if len(ration_evaluation) > 0 else []
            }
        
        # Create optimization details
        optimization_details = {
            "algorithm": "NSGA-II",
            "status": post_results.get('status_classification', 'UNKNOWN'),
            "iterations": post_results.get('optimization_iterations', 0),
            "convergence": post_results.get('convergence_status', 'UNKNOWN')
        }
        
        # Create warnings and recommendations
        warnings = []
        recommendations = []
        
        # Add warnings based on nutrient balance
        if nutrient_comparison['supplied']['dm_intake'] < nutrient_comparison['requirements']['dm_intake'] * 0.95:
            warnings.append("Dry matter intake is below recommended levels")
        
        if nutrient_comparison['supplied']['nel'] < nutrient_comparison['requirements']['nel'] * 0.95:
            warnings.append("Net energy lactation is below recommended levels")
        
        # Add recommendations
        if warnings:
            recommendations.append("Consider adjusting feed proportions to meet nutritional requirements")
        
        if diet_summary_detailed['total_cost'] > 0:
            recommendations.append("Review feed costs and consider alternative ingredients if needed")
        
        # Construct final response
        response_data = {
            "simulation_id": simulation_id,
            "animal_characteristics": animal_characteristics,
            "diet_summary_detailed": diet_summary_detailed,
            "diet_summary": diet_summary,
            "nutrient_comparison": nutrient_comparison,
            "animal_requirements": animal_requirements,
            "solution_status": post_results.get('status_classification', 'UNKNOWN'),
            "confidence_level": post_results.get('confidence_level', 'UNKNOWN'),
            "total_cost": sum(feed['total_cost'] for feed in selected_feeds),
            "water_intake": post_results.get('water_intake', 0),
            "methane_emissions": methane_emissions,
            "warnings": warnings,
            "recommendations": recommendations,
            "optimization_details": optimization_details,
            "ration_evaluation": ration_eval
        }
        
        return response_data
        
    except Exception as e:
        # Log the exception details
        import traceback
        print(f"Exception in create_diet_recommendation_response: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")
        
        # Return minimal response if processing fails
        return {
            "simulation_id": simulation_id,
            "error": f"Failed to create response: {str(e)}",
            "status": "ERROR"
        }
        
#------------------------------------------------------------------------------------------------
@router.get("/unique-feed-type/{country_id}/{user_id}", response_model=List[str])
async def get_unique_feed_types(
    country_id: str,
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch all unique feed types from both standard feeds and user's custom feeds
    filtered by country and user.
    
    - **country_id**: Country UUID to filter feeds by
    - **user_id**: User UUID to filter custom feeds by
    """
    try:
        animal_logger.info(f"Feed type request | Country ID: {country_id} | User ID: {user_id}")
        
        # Use SQL UNION for better performance - combines both standard and custom feeds
        
        # Query 1: Standard feeds from 'feeds' table
        standard_feeds_query = (
            db.query(Feed.fd_type)
            .filter(Feed.fd_country_id == country_id)
            .distinct()
        )
        
        # Query 2: Custom feeds from 'custom_feeds' table
        custom_feeds_query = (
            db.query(CustomFeed.fd_type)
            .filter(
                CustomFeed.fd_country_id == country_id,
                CustomFeed.user_id == user_id
            )
            .distinct()
        )
        
        # Combine both queries using UNION
        combined_query = standard_feeds_query.union(custom_feeds_query)
        
        # Execute the combined query
        unique_feed_types = combined_query.all()
        
        # Extract the unique feed types from the result tuples and sort
        unique_feed_types = [feed_type[0] for feed_type in unique_feed_types if feed_type[0] is not None]
        unique_feed_types = sorted(unique_feed_types)
        
        animal_logger.info(f"Feed types returned | Country: {country_id} | User: {user_id} | Types: {unique_feed_types}")
        return unique_feed_types
        
    except SQLAlchemyError as e:
        animal_logger.error(f"Database error in get_unique_feed_types | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        animal_logger.error(f"Unexpected error in get_unique_feed_types | Country: {country_id} | User: {user_id} | Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve feed types: {str(e)}")

@router.post("/save-report/", response_model=SaveReportResponse)
async def save_report(
    request: SaveReportRequest,
    db: Session = Depends(get_db)
):
    """
    Mark a PDF report as saved by the user
    
    - **report_id**: Report ID to mark as saved (e.g., "rec-abc123")
    - **user_id**: User UUID who owns the report
    
    Process:
    1. Retrieve report from reports table
    2. Check if bucket_url exists (PDF should already be uploaded by async task)
    3. Check if saved_to_bucket is True (PDF successfully uploaded to AWS)
    4. Update save_report flag to true
    5. Return success message with bucket URL
    """
    try:
        animal_logger.info(f"Save report request | Report ID: {request.report_id} | User ID: {request.user_id}")
        
        # Import AWS service and Report model
        from services.aws_service import aws_service
        from app.models import Report
        
        # 1. Retrieve the report from database
        report = db.query(Report).filter(
            Report.report_id == request.report_id,
            Report.user_id == request.user_id
        ).first()
        
        if not report:
            animal_logger.warning(f"Report not found | Report ID: {request.report_id} | User ID: {request.user_id}")
            return SaveReportResponse(
                success=False,
                message="Report not found or you don't have access to it",
                bucket_url=None,
                error_message="The report couldn't be saved in the database. Would you still like to share it?"
            )
        
        # Check if report is already saved to bucket
        if report.save_report and report.bucket_url:
            animal_logger.info(f"Report already marked as saved | Report ID: {request.report_id} | URL: {report.bucket_url}")
            return SaveReportResponse(
                success=True,
                message="Report already marked as saved",
                bucket_url=report.bucket_url
            )
        
        # Check if bucket_url exists (PDF should already be uploaded by async task)
        if not report.bucket_url:
            animal_logger.error(f"No bucket URL found for report | Report ID: {request.report_id}")
            return SaveReportResponse(
                success=False,
                message="Report not yet uploaded to bucket",
                bucket_url=None,
                error_message="The report is still being processed. Please try again later."
            )
        
        # Check if saved_to_bucket is True (PDF successfully uploaded to AWS)
        if not report.saved_to_bucket:
            animal_logger.info(f"Report not yet uploaded to AWS, waiting 10 seconds | Report ID: {request.report_id}")
            
            # Wait for 10 seconds to allow async PDF processing to complete
            import time
            time.sleep(10)
            
            # Refresh the report from database after the delay
            db.refresh(report)
            
            # Recheck if saved_to_bucket is now True
            if not report.saved_to_bucket:
                animal_logger.error(f"Report still not uploaded to AWS after 10-second wait | Report ID: {request.report_id}")
                return SaveReportResponse(
                    success=False,
                    message="The report could not be saved",
                    bucket_url=None,
                    error_message="The report could not be saved. Please contact the administrator."
                )
            else:
                animal_logger.info(f"Report successfully uploaded to AWS after 10-second wait | Report ID: {request.report_id}")
        
        # Update database to mark as saved by user (only if saved_to_bucket is True)
        report.save_report = True
        report.updated_at = datetime.utcnow()
        
        db.commit()
        
        animal_logger.info(f"Report successfully marked as saved by user | Report ID: {request.report_id} | URL: {report.bucket_url}")
        
        return SaveReportResponse(
            success=True,
            message="Report successfully marked as saved by user",
            bucket_url=report.bucket_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        animal_logger.error(f"Unexpected error in save_report_to_bucket | Report ID: {request.report_id} | Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save report to bucket: {str(e)}"
        )


@router.get("/get-user-reports/", response_model=GetUserReportsResponse)
async def get_user_reports(
    user_id: str = Query(..., description="User UUID to get reports for"),
    db: Session = Depends(get_db)
):
    """
    Get all reports for a specific user that have been explicitly saved by the user
    
    - **user_id**: User UUID to get reports for (query parameter)
    
    Returns:
    - Array of reports with bucket URLs and metadata
    - Only includes reports where save_report = true (explicitly saved by user)
    """
    try:
        animal_logger.info(f"Get user reports request | User ID: {user_id}")
        
        # Import Report model
        from app.models import Report
        
        # 1. Check if user exists in user_information table
        user = db.query(UserInformationModel).filter(UserInformationModel.id == uuid.UUID(user_id)).first()
        
        if not user:
            animal_logger.warning(f"User not found | User ID: {user_id}")
            return GetUserReportsResponse(
                success=False,
                message="No reports found for the current user",
                reports=[],
                total_count=0
            )
        
        # 2. Get all reports for the user where save_report = true (explicitly saved by user)
        reports = db.query(Report).filter(
            Report.user_id == uuid.UUID(user_id),
            Report.save_report == True
        ).order_by(Report.created_at.desc()).all()
        
        if not reports:
            animal_logger.info(f"No reports found for user | User ID: {user_id}")
            return GetUserReportsResponse(
                success=True,
                message="No reports found for the current user",
                reports=[],
                total_count=0
            )
        
        # 3. Process each report
        report_items = []
        for report in reports:
            try:
                # Extract simulation_id from json_result
                simulation_id = "Unknown"
                if report.json_result:
                    try:
                        # json_result is already a dict (JSONB column), no need to parse
                        simulation_id = report.json_result.get('simulation_id', 'Unknown')
                    except (KeyError, AttributeError):
                        simulation_id = "Unknown"
                
                # Map report_type
                report_type_display = "Diet Recommendation" if report.report_type == 'rec' else "Diet Evaluation"
                
                # Create report item
                report_item = UserReportItem(
                    bucket_url=report.bucket_url,
                    user_name=user.name,
                    report_id=report.report_id,
                    report_type=report_type_display,
                    report_created_date=report.created_at.isoformat() if report.created_at else "",
                    simulation_id=simulation_id
                )
                
                report_items.append(report_item)
                
            except Exception as e:
                animal_logger.error(f"Error processing report {report.report_id}: {str(e)}")
                # Continue with other reports even if one fails
                continue
        
        animal_logger.info(f"Successfully retrieved {len(report_items)} reports for user | User ID: {user_id}")
        
        return GetUserReportsResponse(
            success=True,
            message=f"Successfully retrieved {len(report_items)} reports",
            reports=report_items,
            total_count=len(report_items)
        )
        
    except Exception as e:
        animal_logger.error(f"Unexpected error in get_user_reports | User ID: {user_id} | Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve user reports: {str(e)}"
        )


@router.post("/diet-evaluation-working/")
async def diet_evaluation_working(user_inputs: DietEvaluationRequest, db: Session = Depends(get_db)):
    """
    NEW WORKING VERSION: Perform diet evaluation using abc_diet_eval.py logic
    Based on the provided Python code, adapted for the Feed Formulation Backend API
    
    - **simulation_id**: Unique simulation identifier in format sim-1234
    - **cattle_info**: Cattle characteristics and requirements
    - **feed_evaluation**: Array of feeds with quantities and prices for evaluation
    """
    try:
        # Extract data from the Pydantic model
        user_id = user_inputs.user_id
        country_id = user_inputs.country_id
        simulation_id = user_inputs.simulation_id
        case_identifier = f"SIM_{simulation_id}"
        
        # Log the complete user input for debugging and analysis
        animal_logger.info(f"[{case_identifier}] NEW WORKING VERSION - Diet evaluation request received | User inputs: {user_inputs}")
        
        # Validate user_id exists in database
        from app.models import UserInformationModel
        user = db.query(UserInformationModel).filter(UserInformationModel.id == user_id).first()
        if not user:
            from middleware.error_handlers import raise_user_friendly_http_exception
            raise_user_friendly_http_exception(f"User with ID '{user_id}' not found. Please provide a valid user ID.", simulation_id, animal_logger)
        
        # Validate country_id exists in database
        from app.models import CountryModel
        country = db.query(CountryModel).filter(CountryModel.id == country_id).first()
        if not country:
            from middleware.error_handlers import raise_user_friendly_http_exception
            raise_user_friendly_http_exception(f"Country with ID '{country_id}' not found. Please provide a valid country ID.", simulation_id, animal_logger)
        
        # Extract data from the Pydantic model
        feed_evaluation = user_inputs.feed_evaluation
        cattle_info = user_inputs.cattle_info
        currency = user_inputs.currency
        
        # Validate feed evaluation is not empty
        if not feed_evaluation:
            from middleware.error_handlers import raise_user_friendly_http_exception
            raise_user_friendly_http_exception("Feed evaluation cannot be empty. Please provide at least one feed.", simulation_id, animal_logger)
        
        # Extract feed IDs and create price mapping
        feed_ids = [feed.feed_id for feed in feed_evaluation]
        feed_prices = {feed.feed_id: feed.price_per_kg for feed in feed_evaluation}
        feed_quantities = {feed.feed_id: feed.quantity_as_fed for feed in feed_evaluation}
        
        # Log the feed IDs, prices, and quantities for debugging
        animal_logger.info(f"[{case_identifier}] Feed IDs: {feed_ids}")
        animal_logger.info(f"[{case_identifier}] Feed prices: {feed_prices}")
        animal_logger.info(f"[{case_identifier}] Feed quantities: {feed_quantities}")
        
        # Step 1: Convert API format to abc_diet_eval.py format
        # Topography mapping logic
        topography_mapping = {
            "Flat": 0,
            "Hilly": 1,
            "Mountainous": 2
        }
        env_topog = topography_mapping.get(cattle_info.topography, 0)
        
        # Create animal_inputs dictionary with mapped values
        animal_inputs = {
            "An_StatePhys": "Lactating Cow" if cattle_info.lactating else "Dry Cow",
            "An_Breed": cattle_info.breed,
            "An_BW": cattle_info.body_weight,
            "Trg_FrmGain": cattle_info.bw_gain,
            "An_BCS": cattle_info.bc_score,
            "An_LactDay": cattle_info.days_in_milk,
            "Trg_MilkProd_L": cattle_info.milk_production,
            "Trg_MilkTPp": cattle_info.tp_milk,
            "Trg_MilkFatp": cattle_info.fat_milk,
            "An_Parity": cattle_info.parity,
            "An_GestDay": cattle_info.days_of_pregnancy,
            "Env_TempCurr": cattle_info.temperature,
            "Env_Grazing": 1,  # Always set to 1 (non-grazing)
            "Env_Dist_km": cattle_info.distance,
            "Env_Topog": env_topog
        }
        
        animal_logger.info(f"[{case_identifier}] Converted cattle info to abc_diet_eval format: {animal_inputs}")
        
        # Step 2: Process feeds from database
        # First try standard feeds, then custom feeds for missing ones
        standard_feeds = db.query(Feed).filter(Feed.id.in_(feed_ids)).all()
        found_standard_ids = {str(feed.id) for feed in standard_feeds}
        
        # Only query custom feeds for missing IDs
        missing_ids = [fid for fid in feed_ids if fid not in found_standard_ids]
        custom_feeds = []
        if missing_ids:
            custom_feeds = db.query(CustomFeed).filter(CustomFeed.id.in_(missing_ids)).all()
            found_custom_ids = {str(feed.id) for feed in custom_feeds}
            
            # Check if all missing IDs were found in custom feeds
            still_missing = [fid for fid in missing_ids if fid not in found_custom_ids]
            if still_missing:
                raise ValueError(f"Some feeds not found: {still_missing}")
        
        # Combine results
        feeds = list(standard_feeds) + list(custom_feeds)
        
        animal_logger.info(f"[{case_identifier}] Found {len(feeds)} feeds in database")
        
        # Convert database feeds to DataFrame format (same as Excel processing)
        feed_data_list = []
        for feed in feeds:
            feed_id = str(feed.id)
            price = feed_prices.get(feed_id, 0.0)
            
            def safe_float(value):
                if value is None or value == '':
                    return 0.0
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return 0.0
            
            feed_data_list.append({
                'Fd_Name': feed.fd_name or "Unknown Feed",
                'Fd_Category': feed.fd_category or "Unknown",
                'Fd_Type': feed.fd_type or "Unknown",
                'Fd_Cost': price,
                'Fd_DM': safe_float(feed.fd_dm),
                'Fd_CP': safe_float(feed.fd_cp),
                'Fd_NDF': safe_float(feed.fd_ndf),
                'Fd_EE': safe_float(feed.fd_ee),
                'Fd_St': safe_float(feed.fd_st),
                'Fd_Ca': safe_float(feed.fd_ca),
                'Fd_P': safe_float(feed.fd_p),
                'Fd_Ash': safe_float(feed.fd_ash),
                'Fd_CF': safe_float(feed.fd_cf),
                'Fd_NPN_CP': feed.fd_npn_cp or 0,
                'Fd_NDIN': safe_float(feed.fd_ndin),
                'Fd_ADIN': safe_float(feed.fd_adin),
                'Fd_Lg': safe_float(feed.fd_lg),
                'Fd_Hemicellulose': safe_float(feed.fd_hemicellulose),
                'Fd_ADF': safe_float(feed.fd_adf),
                'Fd_Cellulose': safe_float(feed.fd_cellulose),
                'NFE (%)': safe_float(feed.fd_nfe),
                'Fd_Country': feed.fd_country_name or ""
            })
        
        animal_logger.info(f"[{case_identifier}] Created feed_data_list with {len(feed_data_list)} feeds")
        
        # Create DataFrame from feed data (same as Excel processing)
        f = pd.DataFrame(feed_data_list)
        f = f.dropna(subset=["Fd_Name"])  # Remove rows with NA values in Fd_Name
        
        animal_logger.info(f"[{case_identifier}] Created DataFrame with {len(f)} feeds")
        
        # Apply same nutritional calculations as in abc_process_feed_library
        # Energy values according to NRC 2001
        f['Fd_PAF'] = 1  # general PAF value for all feeds
        
        # Calculate missing parameters of feed ingredients
        # Organic matter
        f["Fd_OM"] = 100 - f["Fd_Ash"]
        f["Fd_OM"] = f["Fd_OM"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Non Forage Carbohydrates
        f["Fd_NFC"] = f["Fd_OM"] - (f["Fd_NDF"] + f["Fd_EE"] + f["Fd_CP"])
        f["Fd_NFC"] = f["Fd_NFC"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Calculate Fd_NDFIP and Fd_ADFIP
        f["Fd_NDFIP"] = f["Fd_NDIN"] * 6.25
        f["Fd_ADFIP"] = f["Fd_ADIN"] * 6.25
        
        f["Fd_NDFn"] = f["Fd_NDF"] - f["Fd_NDFIP"]
        f["Fd_NDFn"] = f["Fd_NDFn"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        f["Fd_tdNFC"] = 0.98 * (100 - (f["Fd_NDFn"] + f["Fd_CP"] + f["Fd_EE"] + f["Fd_Ash"]) * f["Fd_PAF"])
        f["Fd_tdNFC"] = f["Fd_tdNFC"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Fd_tdCP
        f["Fd_tdCP"] = np.nan
        mask_forage = f["Fd_Type"] == "Forage"
        mask_conc = f["Fd_Type"] == "Concentrate"
        exp_val = lambda row: row["Fd_CP"] * np.exp(-1.2 * (row["Fd_ADFIP"] / row["Fd_CP"])) if row["Fd_CP"] != 0 else 0
        f.loc[mask_forage | mask_conc, "Fd_tdCP"] = f[mask_forage | mask_conc].apply(exp_val, axis=1)
        for cat in ["Minerals", "Additive", "Sugar/Sugar Alcohol"]:
            f.loc[f["Fd_Category"] == cat, "Fd_tdCP"] = 0
        
        # Fd_cFA and Fd_ctdFA
        f["Fd_FA"] = np.where(f["Fd_EE"] < 1, 0, f["Fd_EE"] - 1)
        f["Fd_ctdFA"] = f["Fd_FA"]
        
        # Fd_tdNDF
        f["Fd_tdNDF"] = 0.75 * (f["Fd_NDFn"] - f["Fd_Lg"]) * (1 - np.power((f["Fd_Lg"] / f["Fd_NDFn"]).replace(0, np.nan), 0.667))
        f["Fd_tdNDF"] = f["Fd_tdNDF"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Set constants
        de_NFC = 4.2
        de_NDF = 4.2
        de_CP = 5.6
        de_FA = 9.4
        loss_constant = 0.3
        
        # Weiss et al., 2018.
        f["Fd_GE"] = (f["Fd_CP"] * de_CP/100) + (f["Fd_FA"] * de_FA/100) + (100 - f["Fd_CP"] - f["Fd_FA"] - f["Fd_Ash"]) * 0.042
        f["Fd_GE"] = f["Fd_GE"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        mask_v_m = (f["Fd_Category"] == "Minerals")
        f.loc[mask_v_m, "Fd_GE"] = 0
        
        # Fd_DE NRC 2001
        f["Fd_DE"] = (
            ((f["Fd_tdNFC"] / 100) * de_NFC) +
            ((f["Fd_tdNDF"] / 100) * de_NDF) +
            ((f["Fd_tdCP"] / 100) * de_CP) +
            ((f["Fd_ctdFA"] / 100) * de_FA)
            - loss_constant
        )
        f["Fd_DE"] = f["Fd_DE"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # DE for additives with NPN (urea)
        mask_npn = (f["Fd_Category"] == "Additive") & (f["Fd_NPN_CP"] > 0)
        f.loc[mask_npn, "Fd_DE"] *= (
                1 - (f.loc[mask_npn, "Fd_CP"] * f.loc[mask_npn, "Fd_NPN_CP"] / 28200)
            )
        
        # Set to 0 for specific categories
        for cat in ["Minerals"]:
            f.loc[f["Fd_Category"] == cat, "Fd_DE"] = 0
        
        # Simplified - GEO # Mcal/kg
        f["Fd_ME"] = 0.82 * f["Fd_DE"]
        f["Fd_ME"] = f["Fd_ME"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Simplified - GEO
        f["Fd_TDN"] = 100 * (f["Fd_DE"] / 4.4)  # % of DM
        f["Fd_TDN"] = f["Fd_TDN"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        f["Fd_NEl"] = 0.0245 * f["Fd_TDN"] - 0.12  # Mcal/kg
        f["Fd_NEl"] = f["Fd_NEl"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Feeds - Extra logic used sometimes - better to keep it here
        f["Fd_Conc"] = f.apply(lambda row: 100 if row["Fd_Type"] == "Concentrate" else 0, axis=1)
        f["Fd_For"] = 100 - f["Fd_Conc"]
        f["Fd_ForWet"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] < 71 else 0, axis=1)
        f["Fd_ForDry"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] >= 71 else 0, axis=1)
        f["Fd_Past"] = f.apply(lambda row: 100 if row["Fd_Category"] == "Pasture" else 0, axis=1)
        
        f["Fd_ForNDF"] = (1 - f["Fd_Conc"] / 100) * f["Fd_NDF"]
        f["Fd_NDFnf"] = f["Fd_NDF"] - f["Fd_NDFIP"]  # NDF N free
        
        # Absorption coefficients for minerals
        if "Fd_acCa" not in f.columns:
            f["Fd_acCa"] = None
            f["Fd_acCa"] = f.apply(lambda row: 0.4 if row["Fd_Type"] == "Forage" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_Type"] == "Concentrate" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_Category"] == "Minerals" else row["Fd_acCa"], axis=1)
        else:
            f["Fd_acCa"] = f.apply(lambda row: 0.4 if row["Fd_acCa"] == 0 and row["Fd_Type"] == "Forage" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_acCa"] == 0 and row["Fd_Type"] == "Concentrate" else row["Fd_acCa"], axis=1)
            f["Fd_acCa"] = f.apply(lambda row: 0.6 if row["Fd_acCa"] == 0 and row["Fd_Category"] == "Minerals" else row["Fd_acCa"], axis=1)
        
        if "Fd_acP" not in f.columns:
            f["Fd_acP"] = None
            f["Fd_acP"] = f.apply(lambda row: 0.64 if row["Fd_Type"] == "Forage" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_Type"] == "Concentrate" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_Category"] == "Minerals" else row["Fd_acP"], axis=1)
        else:
            f["Fd_acP"] = f.apply(lambda row: 0.64 if row["Fd_acP"] == 0 and row["Fd_Type"] == "Forage" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_acP"] == 0 and row["Fd_Type"] == "Concentrate" else row["Fd_acP"], axis=1)
            f["Fd_acP"] = f.apply(lambda row: 0.7 if row["Fd_acP"] == 0 and row["Fd_Category"] == "Minerals" else row["Fd_acP"], axis=1)
        
        # Change unit of some parameters from % of DM to Kg
        f["Fd_CostDM"] = f["Fd_Cost"] / (f["Fd_DM"] / 100)
        
        f["Fd_CP_kg"] = f["Fd_CP"] / 100  # CP kg
        f["Fd_NDF_kg"] = f["Fd_NDF"] / 100  # NDF
        f["Fd_ForNDF_kg"] = np.where(f["Fd_Type"] == "Forage", f["Fd_NDF_kg"], 0)  # NDF from forage type
        f["Fd_St_kg"] = f["Fd_St"] / 100  # Starch
        f["Fd_EE_kg"] = f["Fd_EE"] / 100  # EE
        f["Fd_Ca_kg"] = (f["Fd_Ca"] * f["Fd_acCa"]) / 100  # Ca multiplied by its absorption coefficient
        f["Fd_P_kg"] = (f["Fd_P"] * f["Fd_acP"]) / 100  # P multiplied by its absorption coefficient
        
        f["Fd_Type"] = np.where((f["Fd_Type"] == "Concentrate") & (f["Fd_Category"] == "Minerals"), "Minerals", f["Fd_Type"])
        
        f["Fd_isFat"] = (f["Fd_EE"] > 50).astype(int)
        f["Fd_isMi"] = np.where(f["Fd_Type"] == "Minerals", 1, 0)
        f["Fd_isconc"] = np.where(f["Fd_Type"] == "Concentrate", 1, 0)
        f["Fd_isbyprod"] = f["Fd_Category"].str.contains(r"\bby[-\s]?prod", case=False, regex=True).astype(int)
        f["Fd_isconc_only"] = np.where((f["Fd_isconc"] == 1) & (f["Fd_isbyprod"] == 0) & (f["Fd_isFat"] == 0), 1, 0)
        
        # Add Placeholders for the following columns
        f["Fd_DMIn"] = 1
        f["Fd_AFIn"] = 1
        f["Fd_TDNact"] = 1
        f["Fd_DEact"] = 1
        f["Fd_MEact"] = 1
        f["Fd_NEl_A"] = 1
        f["Fd_NEm"] = 1
        f["Fd_NEg"] = 1
        
        # Add missing calculated parameters that are required by abc_main
        # These are calculated in abc_process_feed_library but missing in API processing
        
        # Fd_FA (Fatty Acids) - calculated from EE
        f["Fd_FA"] = np.where(f["Fd_EE"] < 1, 0, f["Fd_EE"] - 1)
        f["Fd_ctdFA"] = f["Fd_FA"]
        
        # Fd_tdNDF (True Digestible NDF)
        f["Fd_tdNDF"] = 0.75 * (f["Fd_NDFn"] - f["Fd_Lg"]) * (1 - np.power((f["Fd_Lg"] / f["Fd_NDFn"]).replace(0, np.nan), 0.667))
        f["Fd_tdNDF"] = f["Fd_tdNDF"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Fd_GE (Gross Energy)
        de_NFC = 4.2
        de_NDF = 4.2
        de_CP = 5.6
        de_FA = 9.4
        f["Fd_GE"] = (f["Fd_CP"] * de_CP/100) + (f["Fd_FA"] * de_FA/100) + (100 - f["Fd_CP"] - f["Fd_FA"] - f["Fd_Ash"]) * 0.042
        f["Fd_GE"] = f["Fd_GE"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Set GE to 0 for minerals
        mask_v_m = (f["Fd_Category"] == "Minerals")
        f.loc[mask_v_m, "Fd_GE"] = 0
        
        # Fd_DE (Digestible Energy)
        loss_constant = 0.3
        f["Fd_DE"] = (
            ((f["Fd_tdNFC"] / 100) * de_NFC) +
            ((f["Fd_tdNDF"] / 100) * de_NDF) +
            ((f["Fd_tdCP"] / 100) * de_CP) +
            ((f["Fd_ctdFA"] / 100) * de_FA)
            - loss_constant
        )
        f["Fd_DE"] = f["Fd_DE"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # DE for additives with NPN (urea)
        mask_npn = (f["Fd_Category"] == "Additive") & (f["Fd_NPN_CP"] > 0)
        f.loc[mask_npn, "Fd_DE"] *= (
                1 - (f.loc[mask_npn, "Fd_CP"] * f.loc[mask_npn, "Fd_NPN_CP"] / 28200)
            )
        
        # Set to 0 for specific categories
        for cat in ["Minerals"]:
            f.loc[f["Fd_Category"] == cat, "Fd_DE"] = 0
        
        # Fd_ME (Metabolizable Energy)
        f["Fd_ME"] = 0.82 * f["Fd_DE"]
        f["Fd_ME"] = f["Fd_ME"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Fd_TDN (Total Digestible Nutrients)
        f["Fd_TDN"] = 100 * (f["Fd_DE"] / 4.4)  # % of DM
        f["Fd_TDN"] = f["Fd_TDN"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        # Fd_NEl (Net Energy for Lactation)
        f["Fd_NEl"] = 0.0245 * f["Fd_TDN"] - 0.12  # Mcal/kg
        f["Fd_NEl"] = f["Fd_NEl"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
        
        animal_logger.info(f"[{case_identifier}] Applied all nutritional calculations including missing parameters")
        
        # Preprocess dataframe (same as abc_process_feed_library)
        def preprocess_dataframe(df):
            for col in df.columns:
                # Convert integers to float
                if pd.api.types.is_integer_dtype(df[col]):
                    df[col] = df[col].astype(np.float64)
                
                # Replace NaN values with 0
                df[col] = df[col].fillna(0)
            
            return df
        
        # Apply the function
        f = preprocess_dataframe(f)
        
        # Create f_nd dictionary (same as abc_process_feed_library)
        f_nd = {col: f[col].to_numpy() for col in f.columns}
        
        animal_logger.info(f"[{case_identifier}] Created f_nd dictionary with {len(f_nd)} columns")
        
        # Step 3: Call abc_main with prepared data
        # Prepare feed evaluation data for abc_main
        feed_evaluation_data = []
        for feed_item in feed_evaluation:
            # Find the feed name from the database
            feed_name = None
            for feed in feeds:
                if str(feed.id) == feed_item.feed_id:
                    feed_name = feed.fd_name
                    break
            
            if feed_name:
                feed_evaluation_data.append({
                    "feed_id": feed_name,  # Use feed name as ID for abc_main
                    "quantity_as_fed": feed_item.quantity_as_fed,
                    "price_per_kg": feed_item.price_per_kg
                })
        
        animal_logger.info(f"[{case_identifier}] Prepared feed evaluation data: {feed_evaluation_data}")
        
        # Call abc_main function
        results = abc_main(
            animal_inputs=animal_inputs,
            f_nd=f_nd,
            simulation_id=simulation_id,
            country_id=country_id,
            user_id=user_id,
            feed_evaluation_data=feed_evaluation_data,
            db=db
        )
        
        animal_logger.info(f"[{case_identifier}] abc_main completed successfully")
        
        # Step 4: Extract results from abc_main
        allowable_milk = results["allowable_milk"]
        animal_requirements = results["animal_requirements"]
        ingredient_amounts_AF = results["ingredient_amounts_AF"]
        ingredient_amounts_DM = results["ingredient_amounts_DM"]
        f_nd_result = results["f_nd"]
        report_id = results["report_id"]
        
        # Calculate mineral balances
        # Convert lists back to numpy arrays for calculations
        ingredient_amounts_DM_array = np.array(ingredient_amounts_DM)
        
        # Calculate mineral supplies from the diet
        # Note: f_nd_result contains the feed data with mineral content
        if "Fd_Ca" in f_nd_result and "Fd_P" in f_nd_result and "Fd_NDF" in f_nd_result:
            # Calculate absorbed calcium supply (kg/d)
            ca_supply = np.sum(ingredient_amounts_DM_array * np.array(f_nd_result["Fd_Ca"]) / 100)
            
            # Calculate absorbed phosphorus supply (kg/d) 
            p_supply = np.sum(ingredient_amounts_DM_array * np.array(f_nd_result["Fd_P"]) / 100)
            
            # Calculate NDF supply (kg/d)
            ndf_supply = np.sum(ingredient_amounts_DM_array * np.array(f_nd_result["Fd_NDF"]) / 100)
            
            # Get requirements from animal_requirements
            ca_requirement = animal_requirements.get("An_Ca_req", 0)  # kg/d
            p_requirement = animal_requirements.get("An_P_req", 0)    # kg/d
            
            # Calculate balances (supply - requirement)
            ca_balance = ca_supply - ca_requirement
            p_balance = p_supply - p_requirement
            ndf_balance = ndf_supply  # NDF doesn't have a specific requirement, so just show supply
            
            animal_logger.info(f"[{case_identifier}] Calculated mineral balances - Ca: {ca_balance:.3f}, P: {p_balance:.3f}, NDF: {ndf_balance:.3f}")
        else:
            # Fallback if mineral data is not available
            ca_balance = 0.0
            p_balance = 0.0
            ndf_balance = 0.0
            animal_logger.warning(f"[{case_identifier}] Mineral data not available in f_nd_result")
        
        # Step 5: Generate PDF and insert report record (following diet-recommendation pattern)
        from services.pdf_service import generate_report_id
        from services.aws_service import aws_service
        from app.models import Report
        import json
        import uuid
        
        # Use the actual user_id from the request
        
        # Generate PDF from the HTML file that was created by abc_main
        html_file_path = f"result_html/diet_eval_{report_id}.html"
        pdf_url = None
        
        try:
            # Convert HTML to PDF using WeasyPrint
            from weasyprint import HTML
            html_doc = HTML(filename=html_file_path)
            pdf_bytes = html_doc.write_pdf()
            
            # Upload to AWS S3
            success, bucket_url, error_message = aws_service.upload_pdf_to_s3(
                pdf_data=pdf_bytes,
                user_id=user_id,
                report_id=report_id
            )
            
            if success:
                pdf_url = bucket_url
                animal_logger.info(f"[{case_identifier}] PDF uploaded to AWS: {bucket_url}")
            else:
                animal_logger.warning(f"[{case_identifier}] Failed to upload PDF: {error_message}")
                
        except Exception as e:
            animal_logger.error(f"[{case_identifier}] Error generating PDF: {str(e)}")
        
        # Note: Database insertion will be moved to after response creation
        
        # Step 6: Format response for API
        
        # Create feed breakdown
        feed_breakdown = []
        for i, feed_name in enumerate(f_nd_result["Fd_Name"]):
            if ingredient_amounts_AF[i] > 0:
                # Find the original feed_id
                original_feed_id = None
                for feed in feeds:
                    if feed.fd_name == feed_name:
                        original_feed_id = str(feed.id)
                        break
                
                if original_feed_id:
                    feed_breakdown.append(FeedBreakdownItem(
                        feed_id=original_feed_id,
                        feed_name=feed_name,
                        feed_type=f_nd_result["Fd_Type"][i],
                        quantity_as_fed_kg_per_day=round(ingredient_amounts_AF[i], 2),
                        quantity_dm_kg_per_day=round(ingredient_amounts_DM[i], 2),
                        price_per_kg=round(f_nd_result["Fd_Cost"][i], 2),
                        total_cost=round(ingredient_amounts_AF[i] * f_nd_result["Fd_Cost"][i], 2),
                        contribution_percent=round((ingredient_amounts_AF[i] / sum(ingredient_amounts_AF)) * 100, 2) if sum(ingredient_amounts_AF) > 0 else 0
                    ))
        
        # Add final safety check to ensure all values are JSON-compliant
        def ensure_json_safe(value):
            """Ensure value is JSON-serializable (no NaN, inf, etc.)"""
            import numpy as np
            if isinstance(value, (int, str, bool)) or value is None:
                return value
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    return 0.0
                return value
            if hasattr(value, 'item'):  # numpy scalar
                val = value.item()
                if np.isnan(val) or np.isinf(val):
                    return 0.0
                return val
            return value
        
        # Apply safety check to all allowable_milk values
        safe_allowable_milk = {k: ensure_json_safe(v) for k, v in allowable_milk.items()}
        
        # Get country name from database
        from core.evaluation.eval_support_methods import get_country_name_by_id
        country_name = get_country_name_by_id(country_id, db)
        
        # Create response
        response = DietEvaluationResponse(
                simulation_id=simulation_id,
                report_id=report_id,
                currency=currency,
                country=country_name,
            evaluation_summary=DietEvaluationSummary(
                overall_status="Adequate" if safe_allowable_milk["DMI_Status"] == "Adequate" else "Marginal",
                limiting_factor=safe_allowable_milk["Limiting_Nutrient"]
            ),
            milk_production_analysis=MilkProductionAnalysis(
                target_production_kg_per_day=safe_allowable_milk["Milk_Target_Production"],
                milk_supported_by_energy_kg_per_day=safe_allowable_milk["Milk_Energy_Supported"],
                milk_supported_by_protein_kg_per_day=safe_allowable_milk["Milk_Protein_Supported"],
                actual_milk_supported_kg_per_day=safe_allowable_milk["Milk_Supported"],
                limiting_nutrient=safe_allowable_milk["Limiting_Nutrient"],
                energy_available_mcal=safe_allowable_milk["NEL_Available"],
                protein_available_g=safe_allowable_milk["MP_Available_kg"] * 1000,
                warnings=[],
                recommendations=[]
            ),
            intake_evaluation=IntakeEvaluation(
                intake_status=safe_allowable_milk["DMI_Status"],
                actual_intake_kg_per_day=safe_allowable_milk["DMI_Actual"],
                target_intake_kg_per_day=safe_allowable_milk["DMI_Target"],
                intake_difference_kg_per_day=safe_allowable_milk["DMI_Difference"],
                intake_percentage=safe_allowable_milk["DMI_Percent"],
                warnings=[],
                recommendations=[]
            ),
            cost_analysis=CostAnalysis(
                total_diet_cost_as_fed=safe_allowable_milk["Diet_Cost_Total_AF"],
                feed_cost_per_kg_milk=safe_allowable_milk["Feed_Cost_Per_kg_Milk"],
                currency=currency,
                warnings=[],
                recommendations=[]
            ),
            methane_analysis=MethaneAnalysis(
                methane_emission_mj_per_day=safe_allowable_milk["CH4_MJ"],
                methane_production_g_per_day=safe_allowable_milk["CH4_grams"],
                methane_yield_g_per_kg_dmi=safe_allowable_milk["CH4_grams_per_kg_DMI"],
                methane_intensity_g_per_kg_ecm=safe_allowable_milk["CH4_intensity"],
                methane_conversion_rate_percent=safe_allowable_milk["MCR"],
                methane_conversion_range="Normal" if 5 <= safe_allowable_milk["MCR"] <= 7 else "High" if safe_allowable_milk["MCR"] > 7 else "Low",
                warnings=[],
                recommendations=[]
            ),
            nutrient_balance=NutrientBalance(
                energy_balance_mcal=safe_allowable_milk["NEL_Available"],
                protein_balance_kg=safe_allowable_milk["MP_Available_kg"],
                calcium_balance_kg=ensure_json_safe(ca_balance),
                phosphorus_balance_kg=ensure_json_safe(p_balance),
                ndf_balance_kg=ensure_json_safe(ndf_balance),
                warnings=[],
                recommendations=[]
            ),
            feed_breakdown=feed_breakdown
            )
        
        # Insert report record into database with actual response data
        try:
            # Validate user_id is a valid UUID before creating the report
            try:
                user_uuid = uuid.UUID(user_id)
            except ValueError as ve:
                animal_logger.error(f"[{case_identifier}] Invalid user_id format: {user_id} - {str(ve)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid user_id format. Please provide a valid UUID."
                )
            
            # Store the actual response data instead of placeholder
            json_result = response.dict()
            
            report = Report(
                report_id=report_id,
                report_type='eval',
                user_id=user_uuid,
                bucket_url=pdf_url,
                json_result=json_result,
                saved_to_bucket=bool(pdf_url),
                save_report=False,
                report=None
            )
            
            db.add(report)
            db.commit()
            
            animal_logger.info(f"[{case_identifier}] Report record inserted successfully: {report_id}")
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            animal_logger.error(f"[{case_identifier}] Failed to insert report record: {str(e)}")
            db.rollback()
            # Don't raise the exception here to avoid breaking the API response
            # The PDF was already generated and uploaded successfully
        
        animal_logger.info(f"[{case_identifier}] Diet evaluation completed successfully")
        return response
        
    except Exception as e:
        animal_logger.error(f"Error in diet_evaluation_working | Simulation ID: {simulation_id} | Error: {str(e)}")
        animal_logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Diet evaluation failed: {str(e)}"
        )

