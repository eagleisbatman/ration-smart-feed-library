# from sqlalchemy import create_engine
# from sqlalchemy.orm import sessionmaker
# from sqlalchemy.ext.declarative import declarative_base
# import numpy as np
# import pandas as pd
# from scipy.optimize import minimize
# from sqlalchemy.orm import Session
# import urllib.parse
from ast import arg
import json

from sqlalchemy import create_engine
from fastapi import Depends
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
import numpy as np
import pandas as pd
from scipy.optimize import minimize,linprog,differential_evolution
import urllib.parse
from app.models import Feed
# from decimal import Decimal
from dotenv import load_dotenv
from typing import List, Optional, Union
import os
from decimal import Decimal

load_dotenv()

# Safe conversion utilities for TEXT to float conversion
def safe_float(value: Optional[Union[str, float, int]]) -> float:
    """
    Safely convert a value to float, handling None, empty strings, and invalid values.
    
    Args:
        value: Value to convert (can be str, float, int, or None)
        
    Returns:
        float: Converted value or 0.0 if conversion fails
    """
    if value is None:
        return 0.0
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ['', 'null', 'none', 'nan']:
            return 0.0
        
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
    
    return 0.0

def safe_str(value: Optional[Union[str, float, int]]) -> str:
    """
    Safely convert a value to string for database storage.
    
    Args:
        value: Value to convert
        
    Returns:
        str: String representation or empty string if conversion fails
    """
    if value is None:
        return ""
    
    if isinstance(value, str):
        return value
    
    try:
        return str(value)
    except (ValueError, TypeError):
        return ""

def convert_numeric_columns_to_text(df: pd.DataFrame, numeric_columns: List[str]) -> pd.DataFrame:
    """
    Convert numeric columns to text format for database storage.
    
    Args:
        df: DataFrame to convert
        numeric_columns: List of column names to convert
        
    Returns:
        pd.DataFrame: DataFrame with converted columns
    """
    df_copy = df.copy()
    for col in numeric_columns:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].apply(safe_str)
    return df_copy

def convert_text_columns_to_numeric(df: pd.DataFrame, text_columns: List[str]) -> pd.DataFrame:
    """
    Convert text columns to numeric format for calculations.
    
    Args:
        df: DataFrame to convert
        text_columns: List of column names to convert
        
    Returns:
        pd.DataFrame: DataFrame with converted columns
    """
    df_copy = df.copy()
    for col in text_columns:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].apply(safe_float)
    return df_copy



POSTGRES_USER = os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD = urllib.parse.quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
POSTGRES_DB = os.getenv("POSTGRES_DB")
POSTGRES_HOST = os.getenv("POSTGRES_HOST")
POSTGRES_PORT = os.getenv("POSTGRES_PORT")
print("POSTGRES_PORT",POSTGRES_PORT)

# SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
SQLALCHEMY_DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
print("SQLALCHEMY_DATABASE_URL",SQLALCHEMY_DATABASE_URL)

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={
        "connect_timeout": 10
    },
    pool_timeout=20,
    pool_recycle=3600,
    pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


DMIest = 0
Careq = 0
Preq = 0
# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



    

    







def adjust_dmi_temperature(DMI, temp):
    if temp > 20:
        return DMI * (1 - (temp - 20) * 0.005922)
    elif temp < 5:
        return DMI * (1 - (5 - temp) * 0.004644)
    else:
        return DMI

def feed_intake_before_calving(days_before_calving, BW):
    return ((((-0.0008*(days_before_calving **2)) - (0.0355 * days_before_calving) + 1.6438 )*BW)/100)

def feed_intake_after_calving(days_after_calving, BW):
    return ((((-0.0013 * (days_after_calving**2)) + (0.0778*days_after_calving) + 1.8766)/100)*BW)




    







# from sqlalchemy import create_engine

# def calculate_cost(x, feed_selected, db):
#     # Load feed prices from the database
#     feed_prices = load_feed_prices(db)
#     # print("feed prices",feed_prices)
    
#     # Merge feed_selected with feed_prices based on 'FEED_CD'
#     feed_selected_with_price = pd.merge(feed_selected, feed_prices, on='FEED_CD', how='left')
    
#     # Ensure that the 'Cost' column is numeric and not null
#     feed_selected_with_price['Cost'] = feed_selected_with_price['FEED_COST'].astype(float).fillna(0)

#     # Calculate the total cost
#     total_cost = np.sum(feed_selected_with_price['Cost'] * x)
    
#     return total_cost








# def Mincost_grad(x, feed_selected, db):
#     # Calculate the cost using the feed_prices table
#     total_cost = calculate_cost(x, feed_selected, db)
#     return total_cost















# new code













    return Methane

from middleware.logging_config import get_logger, log_calculation_start, log_calculation_step, log_calculation_complete, log_error

# Initialize logger for calculations
calc_logger = get_logger("calculation.engine")




# Diet Evaluation Functions
def load_feeds_for_evaluation(db: Session, feed_ids: List[str]) -> pd.DataFrame:
    """
    Load feeds from both feeds and custom_feeds tables for diet evaluation
    
    Parameters:
    -----------
    db: Database session
    feed_ids: List of feed UUIDs to load
        
    Returns:
    --------
    pd.DataFrame: Feed data with nutritional information
    """
    try:
        # Convert string UUIDs to UUID objects
        import uuid
        feed_uuids = [uuid.UUID(feed_id) for feed_id in feed_ids]
        
        # Query both tables for the provided feed IDs
        feeds_query = """
        SELECT 
            id, CAST(fd_code AS TEXT) as fd_code, fd_name, fd_category, fd_type, fd_dm, fd_ash, fd_cp, fd_ee, fd_cf, fd_nfe,
            fd_st, fd_ndf, fd_hemicellulose, fd_adf, fd_cellulose, fd_lg, fd_ndin, fd_adin,
            fd_ca, fd_p, created_at, updated_at,
            'standard' as source
        FROM feeds 
        WHERE id = ANY(:feed_ids)
        UNION ALL
        SELECT 
            id, fd_code, fd_name, fd_category, fd_type, fd_dm, fd_ash, fd_cp, fd_ee, fd_cf, fd_nfe,
            fd_st, fd_ndf, fd_hemicellulose, fd_adf, fd_cellulose, fd_lg, fd_ndin, fd_adin,
            fd_ca, fd_p, created_at, updated_at,
            'custom' as source
        FROM custom_feeds 
        WHERE id = ANY(:feed_ids)
        """
        
        result = db.execute(feeds_query, {"feed_ids": feed_uuids})
        feeds_data = result.fetchall()
        
        if not feeds_data:
            raise ValueError("No feeds found for the provided feed IDs")
        
        # Convert to DataFrame
        df = pd.DataFrame(feeds_data, columns=[
            'id', 'fd_code', 'fd_name', 'fd_category', 'fd_type', 'fd_dm', 'fd_ash', 'fd_cp', 'fd_ee', 'fd_cf', 'fd_nfe',
            'fd_st', 'fd_ndf', 'fd_hemicellulose', 'fd_adf', 'fd_cellulose', 'fd_lg', 'fd_ndin', 'fd_adin',
            'fd_ca', 'fd_p', 'created_at', 'updated_at', 'source'
        ])
        
        # Convert string columns to float where needed
        numeric_columns = ['fd_dm', 'fd_ash', 'fd_cp', 'fd_ee', 'fd_cf', 'fd_nfe', 'fd_st', 'fd_ndf', 
                          'fd_hemicellulose', 'fd_adf', 'fd_cellulose', 'fd_lg', 'fd_ndin', 'fd_adin',
                          'fd_ca', 'fd_p']
        
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        return df
        
    except Exception as e:
        calc_logger.error(f"Error loading feeds for evaluation: {str(e)}")
        raise

def calculate_animal_requirements_evaluation(animal_data: dict) -> dict:
    """
    Calculate animal nutritional requirements for diet evaluation
    Based on the Python code logic but adapted for the API structure
    
    Parameters:
    -----------
    animal_data: Dictionary containing animal characteristics
        
    Returns:
    --------
    dict: Dictionary containing all calculated requirements
    """
    try:
        # Extract animal inputs
        An_StatePhys = animal_data.get("An_StatePhys", "Lactating Cow")
        An_Breed = animal_data.get("An_Breed", "Holstein")
        An_BW = animal_data.get("An_BW", 600)
        Trg_FrmGain = animal_data.get("Trg_FrmGain", 0.2)
        An_BCS = animal_data.get("An_BCS", 3.0)
        An_LactDay = animal_data.get("An_LactDay", 100)
        Trg_MilkProd_L = animal_data.get("Trg_MilkProd_L", 25)
        Trg_MilkTPp = animal_data.get("Trg_MilkTPp", 3.2)
        Trg_MilkFatp = animal_data.get("Trg_MilkFatp", 3.8)
        An_Parity = animal_data.get("An_Parity", 2)
        An_GestDay = animal_data.get("An_GestDay", 0)
        Env_TempCurr = animal_data.get("Env_TempCurr", 20)
        Env_Grazing = animal_data.get("Env_Grazing", 1)
        Env_Dist_km = animal_data.get("Env_Dist_km", 0)
        Env_Topog = animal_data.get("Env_Topog", 0)
        
        # Constants from Python code
        Trg_MilkLacp = 4.85
        Trg_RsrvGain = 0
        An_305RHA_MlkTP = 396
        An_AgeCalv1st = 729.6
        Fet_BWbrth = 44.1
        An_GestLength = 280
        An_AgeConcept1st = 491
        CalfInt = 370
        
        # Process animal inputs (following Python code logic)
        An_BW_mature = 700 if An_Breed in ["Holstein", "Crossbred"] else 550
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
        
        # DMI calculations (following Python code)
        def adjust_dmi_temperature(DMI, Temp):
            if Temp > 20:
                return DMI * (1 - (Temp - 20) * 0.005922)
            elif Temp < 5:
                return DMI * (1 - (5 - Temp) * 0.004644)
            else:
                return DMI
        
        Trg_NEmilk_Milk = (9.29 * Trg_MilkFatp / 100 + 5.85 * Trg_MilkTPp / 100 + 3.95 * Trg_MilkLacp / 100)
        Trg_NEmilkOut = Trg_NEmilk_Milk * Trg_MilkProd if Trg_MilkProd > 0 else 0
        
        Dt_DMIn = 0.0
        
        # Base DMI calculation (following Python code exactly)
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
        
        Trg_Dt_DMIn = Dt_DMIn
        Dt_DMIn_BW = (Dt_DMIn / An_BW) * 100
        Dt_DMIn_MBW = (Dt_DMIn / An_MBW) * 100
        
        # Energy requirements (following Python code)
        Km_ME_NE = 0.63 if An_StatePhys == "Heifer" else 0.66
        Kl_ME_NE = 0.554
        
        An_ME_maint = 0.15 * An_MBW
        An_NEL_maint = 0.08 * An_MBW if An_StatePhys == "Lactating Cow" else (An_ME_maint * Km_ME_NE)
        
        An_NEmUse_Env = 0
        An_NEm_Act = (0.00035 * Env_Dist / 1000) * An_BW
        An_NEm_Act_Topo = 0.0067 * Env_Topo / 1000 * An_BW
        An_NEmUse_Act = An_NEm_Act + An_NEm_Act_Topo
        An_NEm = An_NEL_maint + An_NEmUse_Env + An_NEmUse_Act
        An_ME_m = An_NEm / Km_ME_NE
        
        An_NELm = An_NEm
        An_NELlact = Trg_NEmilkOut
        
        # Gestation calculations (simplified from Python code)
        An_Preg = (An_GestDay > 0) and (An_GestDay <= An_GestLength)
        
        if not An_Preg:
            An_MEgest = 0.0
            An_NEgest = 0.0
        else:
            # Simplified gestation calculations
            An_MEgest = 0.0  # Will be calculated in detail if needed
            An_NEgest = 0.0
        
        # Growth calculations (simplified)
        An_MEgain = 0.0
        An_NELgain = 0.0
        
        An_ME = An_ME_m + An_MEgest + An_MEgain
        An_NEL = An_NELm + An_NELlact + An_NEgest + An_NELgain
        
        # Protein requirements (simplified)
        An_MPl = Trg_MilkProd * Trg_MilkTPp / 100 / 0.67 * 1000
        An_MPg = 0.0  # Simplified
        An_MPp = 0.0  # Simplified
        An_MP = An_MPl + An_MPg + An_MPp
        
        # Mineral requirements (simplified)
        An_Ca_req = 0.0  # Will be calculated in detail
        An_P_req = 0.0   # Will be calculated in detail
        
        # Add missing values that calculate_diet_supply_evaluation expects
        An_MPm = 0.0  # Will be calculated in diet supply
        
        return {
            "An_StatePhys": An_StatePhys,
            "An_Breed": An_Breed,
            "An_BW": An_BW,
            "An_BW_mature": An_BW_mature,
            "An_MBW": An_MBW,
            "Trg_MilkProd": Trg_MilkProd,
            "Trg_MilkProd_L": Trg_MilkProd_L,
            "Trg_MilkFatp": Trg_MilkFatp,
            "Trg_MilkTPp": Trg_MilkTPp,
            "Trg_NEmilk_Milk": Trg_NEmilk_Milk,
            "Trg_NEmilkOut": Trg_NEmilkOut,
            "Trg_Dt_DMIn": Trg_Dt_DMIn,
            "dry_matter_intake": Trg_Dt_DMIn,
            "An_NELm": An_NELm,
            "An_NELlact": An_NELlact,
            "An_NEgest": An_NEgest,
            "An_NELgain": An_NELgain,
            "An_MPm": An_MPm,  # Will be calculated in diet supply
            "An_MPg": An_MPg,
            "An_MPp": An_MPp,
            "An_MPl": An_MPl,
            "An_MP": An_MP,
            "An_ME": An_ME,
            "An_NEL": An_NEL,
            "An_Ca_req": An_Ca_req,
            "An_P_req": An_P_req,
            "An_LactDay": An_LactDay,
            "status": "success"
        }
        
    except Exception as e:
        calc_logger.error(f"Error calculating animal requirements: {str(e)}")
        raise

def calculate_diet_supply_evaluation(ingredient_amounts_dm: np.ndarray, feeds_df: pd.DataFrame, 
                                   animal_requirements: dict) -> tuple:
    """
    Calculate diet supply for evaluation (simplified version)
    
    Parameters:
    -----------
    ingredient_amounts_dm: Array of dry matter amounts for each feed
    feeds_df: DataFrame with feed nutritional data
    animal_requirements: Dictionary with animal requirements
        
    Returns:
    --------
    tuple: (diet_summary_values, intermediate_results_values, An_MPm)
    """
    try:
        # Extract required values
        Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
        An_BW = animal_requirements["An_BW"]
        An_MPg = animal_requirements["An_MPg"]
        An_MPp = animal_requirements["An_MPp"]
        An_MPl = animal_requirements["An_MPl"]
        An_ME = animal_requirements["An_ME"]
        An_NEL = animal_requirements["An_NEL"]
        
        # Simple calculations
        DMI = float(np.sum(ingredient_amounts_dm))
        if DMI < 1e-6:
            raise ValueError("Total DMI is too small or zero")
        
        # Simplified calculations
        Supply_DMIn = DMI
        Supply_Energy = DMI * 2.0  # Simplified energy calculation
        Supply_MP = DMI * 0.15  # Simplified protein calculation
        Supply_Ca = DMI * 0.01  # Simplified calcium
        Supply_P = DMI * 0.005  # Simplified phosphorus
        Supply_NDF = DMI * 0.3  # Simplified NDF
        Supply_NDFfor = DMI * 0.2  # Simplified forage NDF
        Supply_St = DMI * 0.1  # Simplified starch
        Supply_EE = DMI * 0.02  # Simplified ether extract
        Supply_NEl = DMI * 1.5  # Simplified NEL
        Supply_ME = DMI * 1.8  # Simplified ME
        
        # Maintenance protein (simplified)
        An_MPm = 0.20 * An_BW**0.60 / 0.65
        
        NEL_balance = Supply_NEl - An_NEL
        ME_balance = Supply_ME - An_ME
        
        diet_summary_values = np.array([
            Supply_DMIn, Supply_Energy, Supply_MP, Supply_Ca, Supply_P,
            Supply_NDF, Supply_NDFfor, Supply_St, Supply_EE, Supply_NEl, Supply_ME
        ])
        
        intermediate_results_values = np.array([DMI, NEL_balance, An_MPm + An_MPg + An_MPp + An_MPl, Supply_MP - (An_MPm + An_MPg + An_MPp + An_MPl), ME_balance])
        
        return (diet_summary_values, intermediate_results_values, An_MPm)
        
    except Exception as e:
        calc_logger.error(f"Error calculating diet supply: {str(e)}")
        raise

def predict_milk_supported_evaluation(diet_summary_values: np.ndarray, animal_requirements: dict,
                                    ingredient_amounts_dm: np.ndarray, feeds_df: pd.DataFrame) -> dict:
    """
    Predict milk production supported by the diet (simplified version)
    
    Parameters:
    -----------
    diet_summary_values: Array with supply values
    animal_requirements: Dictionary with animal requirements
    ingredient_amounts_dm: Array of dry matter amounts
    feeds_df: DataFrame with feed data
        
    Returns:
    --------
    dict: Milk production analysis results
    """
    try:
        # Extract values
        Supply_NEl = float(diet_summary_values[9])  # Supply_NEl
        Supply_MP = float(diet_summary_values[2])   # Supply_MP
        Supply_DMIn = float(diet_summary_values[0])  # Supply_DMIn
        Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
        An_NELm = animal_requirements["An_NELm"]
        An_NEgest = animal_requirements["An_NEgest"]
        An_NELgain = animal_requirements["An_NELgain"]
        An_NELlact = animal_requirements["An_NELlact"]
        An_MPm = 0.0  # Will be calculated
        An_MPg = animal_requirements["An_MPg"]
        An_MPp = animal_requirements["An_MPp"]
        Trg_NEmilk_Milk = animal_requirements["Trg_NEmilk_Milk"]
        Trg_MilkTPp = animal_requirements["Trg_MilkTPp"]
        
        # Simplified milk prediction calculations
        MP_efficiency = 0.67
        MP_per_kg_milk = (Trg_MilkTPp / 100) / MP_efficiency * 1000
        
        # Milk supported by energy
        NEL_available = Supply_NEl - An_NELm - An_NEgest - An_NELgain
        milk_energy_supported = max(0, NEL_available / Trg_NEmilk_Milk) if Trg_NEmilk_Milk > 0 else 0
        
        # Milk supported by protein
        MP_available = (Supply_MP * 1000) - (An_MPm + An_MPg + An_MPp)
        milk_protein_supported = max(0, MP_available / MP_per_kg_milk) if MP_per_kg_milk > 0 else 0
        
        # Limiting factor
        limiting_factor = "Energy" if milk_energy_supported < milk_protein_supported else "Protein"
        
        # DMI evaluation
        dmi_difference = Supply_DMIn - Trg_Dt_DMIn
        dmi_percent = (Supply_DMIn / Trg_Dt_DMIn) * 100 if Trg_Dt_DMIn > 0 else 0
        
        if dmi_percent >= 95 and dmi_percent <= 105:
            dmi_status = "Adequate"
        elif dmi_percent < 95:
            dmi_status = "Below target"
        else:
            dmi_status = "Above target"
        
        # Simplified methane calculations
        Dt_DMInSum = float(np.sum(ingredient_amounts_dm))
        CH4 = 76.0 + 13.5 * Dt_DMInSum  # Simplified methane calculation
        CH4_MJ = CH4 * 55.5/1000
        MCR = 6.0  # Simplified MCR
        
        return {
            "energy_supported": milk_energy_supported,
            "protein_supported": milk_protein_supported,
            "actual_supported": min(milk_energy_supported, milk_protein_supported),
            "limiting_nutrient": limiting_factor,
            "energy_available": NEL_available,
            "protein_available": MP_available,
            "dmi_status": dmi_status,
            "dmi_actual": Supply_DMIn,
            "dmi_target": Trg_Dt_DMIn,
            "dmi_difference": dmi_difference,
            "dmi_percent": dmi_percent,
            "diet_cost_total_af": 0.0,
            "feed_cost_per_kg_milk": 0.0,
            "ch4_mj": CH4_MJ,
            "ch4_grams": CH4,
            "ch4_grams_per_kg_dmi": CH4 / Dt_DMInSum if Dt_DMInSum > 0 else 0,
            "mcr": MCR,
            "mcr_range": "Average"
        }
        
    except Exception as e:
        calc_logger.error(f"Error predicting milk supported: {str(e)}")
        raise
