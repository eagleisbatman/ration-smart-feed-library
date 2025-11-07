import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import time
import warnings
import multiprocessing
import random
import re
from pathlib import Path
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
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# Animal inputs

def abc_calculate_an_requirements(animal_inputs):
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

    # Base DMI calculation
    if An_StatePhys == "Lactating Cow":
        Dt_DMIn = ((3.7 + 5.7 * (An_Parity - 1) + 0.305 * Trg_NEmilkOut + 0.022 * An_BW +
                   (-0.689 - 1.87 * (An_Parity - 1)) * An_BCS) * \
                  (1 - (0.212 + 0.136 * (An_Parity - 1)) * np.exp(-0.053 * An_LactDay))-1)

        FCM = (0.4 * Trg_MilkProd) + (15 * Trg_MilkFatp * Trg_MilkProd / 100)
        DMI_NRC = ((0.372 * FCM + 0.0968 * An_MBW) * (1 - np.exp(-0.192 * (An_LactDay / 7 + 3.67)))-1)
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

# Load feed library

def abc_process_feed_library(feed_library_path, sheet_name="Fd_selected"):
    """
    Process feed library data and calculate nutritional parameters for optimization.
    
    Parameters:
    -----------
    feed_library_path : str
        Path to the Excel file containing feed library data
    sheet_name : str, optional
        Name of the Excel sheet to read (default: "Fd_selected")
        
    Returns:
    --------
    tuple : (f_nd, Dt)
        f_nd : dict - Dictionary with feed data arrays for optimization
        Dt : DataFrame - Summary DataFrame with intake information
    """
    
    # Load the feed table
    f = pd.read_excel(feed_library_path, sheet_name=sheet_name)

    # RE-Define column names 
    correct_columns = { 
        "fd_name": "Fd_Name", "fd_category": "Fd_Category", "fd_type": "Fd_Type", 
        "fd_cost": "Fd_Cost", "fd_dm": "Fd_DM", "fd_ash": "Fd_Ash", "fd_cp": "Fd_CP",
        "fd_npn_cp": "Fd_NPN_CP", "fd_ee": "Fd_EE", "fd_cf": "Fd_CF", "fd_nfe": "NFE (%)", 
        "fd_st": "Fd_St", "fd_ndf": "Fd_NDF", "fd_hemicellulose": "Fd_Hemicellulose", 
        "fd_adf": "Fd_ADF", "fd_cellulose": "Fd_Cellulose", "fd_lg": "Fd_Lg", 
        "fd_ndin": "Fd_NDIN", "fd_adin": "Fd_ADIN", "fd_ca": "Fd_Ca", "fd_p": "Fd_P", 
        "fd_country": "Fd_Country"
    }

    # Rename to original casing
    f.rename(columns=correct_columns, inplace=True)

    f = f.dropna(subset=["Fd_Name"]) # Remove rows with NA values in the Fd_Name column

    # Energy values according to NRC 2001

    # Apply to your DataFrame
    f['Fd_PAF'] = 1 # general PAF value for all feeds

    # Calculate missing parameters of feed ingredients
    # # Organic matter
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

    # Animal Protein special case
    # mask_animal_protein = f["Fd_Category"] == "Animal Protein"
    # f.loc[mask_animal_protein, "Fd_DE"] = (
    #     (f.loc[mask_animal_protein, "Fd_tdNFC"] / 100) * de_NFC +
    #     (f.loc[mask_animal_protein, "Fd_tdCP"] / 100) * de_CP +
    #     (f.loc[mask_animal_protein, "Fd_ctdFA"] / 100) * de_FA
    #     - loss_constant
    # )

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
    f["Fd_TDN"] = 100 * (f["Fd_DE"] / 4.4) # % of DM
    f["Fd_TDN"] = f["Fd_TDN"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)

    f["Fd_NEl"] = 0.0245 * f["Fd_TDN"] - 0.12 # Mcal/kg
    f["Fd_NEl"] = f["Fd_NEl"].apply(lambda x: 0 if pd.isna(x) or x < 0 else x)

    # Feeds - Extra logic used sometimes - better to keep it here

    f["Fd_Conc"] = f.apply(lambda row: 100 if row["Fd_Type"] == "Concentrate" else 0, axis=1)
    f["Fd_For"] = 100 - f["Fd_Conc"]
    f["Fd_ForWet"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] < 71 else 0, axis=1)
    f["Fd_ForDry"] = f.apply(lambda row: row["Fd_For"] if row["Fd_For"] > 50 and row["Fd_DM"] >= 71 else 0, axis=1)
    f["Fd_Past"] = f.apply(lambda row: 100 if row["Fd_Category"] == "Pasture" else 0, axis=1)

    f["Fd_ForNDF"] = (1 - f["Fd_Conc"] / 100) * f["Fd_NDF"]
    f["Fd_NDFnf"] = f["Fd_NDF"] - f["Fd_NDFIP"] # NDF N free

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

    f["Fd_CP_kg"] = f["Fd_CP"] / 100                                          # CP kg
    f["Fd_NDF_kg"] = f["Fd_NDF"] / 100                                        # NDF
    f["Fd_ForNDF_kg"] = np.where(f["Fd_Type"] == "Forage", f["Fd_NDF_kg"], 0) # NDF from forage type
    f["Fd_St_kg"] = f["Fd_St"] / 100                                          # Starch
    f["Fd_EE_kg"] = f["Fd_EE"] / 100                                          # EE
    f["Fd_Ca_kg"] = (f["Fd_Ca"] * f["Fd_acCa"]) / 100                         # Ca multiplied by its absoprtion coefficient
    f["Fd_P_kg"] = (f["Fd_P"] * f["Fd_acP"]) / 100                            # P multiplied by its absoprtion coefficient

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

    # Create a DataFrame with the required columns
    Dt = pd.DataFrame({
        "Ingr_Category": f["Fd_Category"], 
        "Ingr_Type": f["Fd_Type"], 
        "Ingr_Name": f["Fd_Name"], 
        "Intake_DM": f["Fd_DMIn"], 
        "Intake_AF": f["Fd_AFIn"]
    })

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
    
    return f_nd, Dt

# Diet Supply Model

def abc_safe_divide(numerator, denominator, default_value=0.0):
    """Safely divide, avoiding division by zero"""
    if abs(denominator) < 1e-12:  # Very small number
        return default_value
    return numerator / denominator

def abc_safe_sum(array):
    """Safely sum an array, handling NaN values"""
    array = np.array(array)
    array = np.nan_to_num(array, nan=0.0)  # Replace NaN with 0
    return np.sum(array)

def abc_calculate_discount(TotalTDN, DMI, An_MBW):
    """Calculate the nutritional discount based on TDN and DMI."""
    if DMI < 1e-6: # secure division by zero
        return 1.0
    if TotalTDN < 0:
        return 1.0  # No TDN, no discount
    TDNconc = abc_safe_divide(TotalTDN , DMI, default_value=0) * 100 # transform in % of DM
    DMI_to_maint = TotalTDN / (0.035 * An_MBW) if TotalTDN >= (0.035 * An_MBW) else 1
    if TDNconc < 60:
        return 1.0
    return (TDNconc - ((0.18 * TDNconc - 10.3) * (DMI_to_maint - 1))) / TDNconc

def abc_calculate_MEact(f_nd):     # As NRC ... NASEM eq ME = DE - UE - GAS_E (I do not have all parameters to calculate UE currently)
    """Calculate the actual ME based on DE and other parameters."""
    Fd_DEact = np.nan_to_num(f_nd["Fd_DEact"], nan=0.0)
    Fd_EE = np.nan_to_num(f_nd["Fd_EE"], nan=0.0)
    Fd_isFat = f_nd["Fd_isFat"]
    Fd_isMi = f_nd["Fd_isMi"]

    MEact = 1.01 * Fd_DEact - 0.45

    mask_EE = Fd_EE >= 3
    MEact[mask_EE] += 0.0046 * (Fd_EE[mask_EE] - 3)

    MEact[Fd_isFat == 1] = Fd_DEact[Fd_isFat == 1]
    MEact[Fd_isMi == 1] = 0

    return np.clip(MEact, a_min=0, a_max=None)

def abc_diet_supply(x, f_nd, animal_requirements):
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
        TotalTDN = abc_safe_sum(x * (local_f["Fd_TDN"]/100))  # kg of TDN
        discount = abc_calculate_discount(TotalTDN, DMI, An_MBW)

        local_f["Fd_TDNact"] = local_f["Fd_TDN"] * discount
        local_f["Fd_DEact"] = local_f["Fd_DE"] * discount
    
        # Energy values for Cows 
        local_f["Fd_MEact"] = abc_calculate_MEact(local_f)
        NEl_diet = abc_safe_sum(x * local_f["Fd_MEact"]) * 0.66    # Mcal/d - NEL according to NASEM 2021 for Lactating and Dry cows

        # Maintenance protein dynamic equation

        NDF_diet = abc_safe_divide(abc_safe_sum((f_nd["Fd_NDF"]) * x), DMI, default_value=0) # % of NDF in diet

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

        Energy = (abc_safe_sum(x * local_f["Fd_DEact"]) * 0.82) if is_heifer else NEl_diet

        # Apply NASEM 2021 safety for heifers
        if is_heifer:
            MP_min = (53 - 25 * (An_BW / An_BW_mature)) * (An_NEL / 0.66)  # g/d
            if Total_MP_Req < MP_min:
                Total_MP_Req = MP_min

        Total_MP_Requirement = Total_MP_Req/ 1000  # kg/d

        local_f["Fd_CP_g_d"] = local_f["Fd_CP"] / 100 * x * 1000
        local_f["Fd_ME_MJ"] = local_f["Fd_MEact"] * 4.184 * x
        total_ME_MJ_d = abc_safe_sum(local_f["Fd_ME_MJ"])
        total_CP_g_d = abc_safe_sum(local_f["Fd_CP_g_d"])
        Util_CP = 8.76 * total_ME_MJ_d + 0.36 * total_CP_g_d
        MP_GER = (Util_CP * 0.73 * 0.85) / 1000  # kg/d
        Protein_Balance = MP_GER - Total_MP_Requirement

        Supply_DMIn = DMI # kg/d
        Supply_Energy = Energy # Mcal/d - ME for heifers and NEL for cows
        Supply_MP = (total_CP_g_d * 0.67) / 1000 # kg/d
        Supply_Ca = abc_safe_sum(x * local_f["Fd_Ca_kg"])  # kg/d
        Supply_P = abc_safe_sum(x * local_f["Fd_P_kg"]) # kg/d
        Supply_NDF = abc_safe_sum(x * local_f["Fd_NDF_kg"])   # kg/d
        Supply_NDFfor = abc_safe_sum(x * local_f["Fd_ForNDF_kg"]) # kg/d
        Supply_St = abc_safe_sum(x * local_f["Fd_St_kg"]) # kg/d
        Supply_EE = abc_safe_sum(x * local_f["Fd_EE_kg"]) # kg/d
        Supply_NEl = NEl_diet
        Supply_ME = abc_safe_sum(x * local_f["Fd_DEact"]) * 0.82  # Mcal/d - ME for heifers
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
        n_outputs = 11
        diet_summary_values = np.full(n_outputs, np.nan)
        intermediate_results_values = np.full(5, np.nan)
        return (diet_summary_values, intermediate_results_values, 0)

# Milk support prediction

def abc_predict_total_milk_supported(Supply_NEl, Supply_MP, Supply_DMIn, Trg_Dt_DMIn,
                               An_NELm, An_NEgest, An_NELgain, An_NELlact, 
                               An_MPm, An_MPg, An_MPp, 
                               Trg_NEmilk_Milk, Trg_MilkTPp, Trg_MilkProd, An_LactDay,
                               An_BW, ingredient_amounts_DM, f_nd, An_StatePhys, animal_requirements):
        
    MP_efficiency = 0.67  # NRC 2001 - high? 
    # MP per kg milk (g/kg)
    MP_per_kg_milk = (Trg_MilkTPp / 100) / MP_efficiency * 1000
    
    # Milk supported by energy (kg/d)
    NEL_available = Supply_NEl - An_NELm - An_NEgest - An_NELgain
    milk_energy_supported = max(0, NEL_available / Trg_NEmilk_Milk)
    
    # Milk supported by protein (kg/d)
    MP_available = (Supply_MP * 1000) - (An_MPm + An_MPg + An_MPp)
    milk_protein_supported = max(0, MP_available / MP_per_kg_milk)
    MP_Available_kg = MP_available / 1000

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
    
    # Calculate diet cost (as-fed basis)
    # Convert DM intake to AF intake for each ingredient
    inclusion_DM_kg = f_nd["Fd_DMIn"]
    inclusion_AF_kg = inclusion_DM_kg / (f_nd["Fd_DM"] / 100)  # Convert DM intake to as-fed intake 
    diet_cost_total_af = sum(inclusion_AF_kg * f_nd["Fd_Cost"])  
    
    # Calculate feed cost per kg milk
    milk_produced = min(milk_energy_supported, milk_protein_supported)
    feed_cost_per_kg_milk = diet_cost_total_af / milk_produced if milk_produced > 0 else 0

    Dt_DMInSum = sum(ingredient_amounts_DM)  # Total DM intake from all ingredients

    An_BW = animal_requirements["An_BW"]
    Trg_MilkTPp = animal_requirements["Trg_MilkTPp"]
    Trg_MilkFatp = animal_requirements["Trg_MilkFatp"]

    # Calculate diet composition values
    EE_diet = (sum(ingredient_amounts_DM * (f_nd["Fd_EE"] / 100)) / Dt_DMInSum) * 100
    FA_diet = (sum(ingredient_amounts_DM * (f_nd["Fd_FA"] / 100)) / Dt_DMInSum) * 100
    NDF_diet = (sum(ingredient_amounts_DM * (f_nd["Fd_NDF"] / 100)) / Dt_DMInSum) * 100
    CP_diet = sum(ingredient_amounts_DM * (f_nd["Fd_CP"]/100)) / Dt_DMInSum * 100
    
    GE_diet = (f_nd["Fd_GE"] * ingredient_amounts_DM).sum()  # Mcal/d
   
    # Calculate Methane in g/d
    if An_StatePhys == "Lactating Cow":
        CH4 = (76.0 + 13.5 * Dt_DMInSum - 9.55 * EE_diet + 2.24 * NDF_diet)
    elif An_StatePhys == "Dry Cow":
        CH4 = (0.69 + 0.053 * GE_diet - 0.0789 * FA_diet) * 4184 / 55.5
    elif An_StatePhys == "Heifer":
        CH4 = (-0.038 + 0.051 * GE_diet - 0.0091 * NDF_diet) * 4184 / 55.5
    else:
        CH4 = 0  # Default for unknown animal types
    
    # Methane Intensity
    CH4_intensity = -0.101 - 0.215 * Dt_DMInSum - 0.118 * CP_diet - 0.323 * EE_diet + 0.120 * NDF_diet - 0.253 * Trg_MilkFatp + 3.44 * Trg_MilkTPp + 0.00947 * An_BW

    # Methane metrics
    CH4_MJ = CH4 * 55.5/1000  # convert from g to MJ
    GE_MJ = GE_diet * 4.184   # convert from Mcal to MJ
    CH4_grams_per_kg_DMI = CH4 / Dt_DMInSum if Dt_DMInSum > 0 else 0
    MCR = (CH4_MJ / GE_MJ) * 100 if GE_MJ > 0 else 0
    
    return {
        "Milk_Target_Production": round(Trg_MilkProd, 2),
        "Milk_Energy_Supported": round(milk_energy_supported, 2),
        "Milk_Protein_Supported": round(milk_protein_supported, 2),
        "Milk_Supported": round(min(milk_energy_supported, milk_protein_supported), 2),
        "Limiting_Nutrient": limiting_factor,
        "NEL_Available": round(NEL_available, 2),
        "MP_Available_kg": round(MP_Available_kg, 2),
        "DMI_Status": dmi_status,
        "DMI_Actual": round(Supply_DMIn, 2),
        "DMI_Target": round(Trg_Dt_DMIn, 2),
        "DMI_Difference": round(dmi_difference, 2),
        "DMI_Percent": round(dmi_percent, 2),
        "Diet_Cost_Total_AF": round(diet_cost_total_af, 2),
        "Feed_Cost_Per_kg_Milk": round(feed_cost_per_kg_milk, 2),
        "CH4_MJ": round(CH4_MJ, 2),
        "CH4_grams": round(CH4, 2),
        "CH4_grams_per_kg_DMI": round(CH4_grams_per_kg_DMI, 2),
        "CH4_intensity": round(CH4_intensity, 2),
        "MCR": round(MCR, 2)
    }

def abc_report_diet_eval(results_dict):
    
    display_names = {
        "Milk_Target_Production": "Milk Production Target (kg/d)",
        "Milk_Energy_Supported": "Milk Supported by Energy (kg/d)",
        "Milk_Protein_Supported": "Milk Supported by Protein (kg/d)",
        "Milk_Supported": "Actual Milk Production  Supported(kg/d)",
        "Limiting_Nutrient": "Limiting Nutrient",
        "NEL_Available": "Energy Available (Mcal)",
        "MP_Available_kg": "Metabolizable Protein Available (kg)",
        "DMI_Status": "Intake Status",
        "DMI_Actual": "Actual Intake (kg/d)",
        "DMI_Target": "Target Intake (kg/d)",
        "DMI_Difference": "Intake Difference (kg/d)",
        "Diet_Cost_Total_AF": "Total Diet Cost (as-fed)",
        "Feed_Cost_Per_kg_Milk": "Feed Cost per kg of Milk",
        "CH4_MJ": "Methane Emission (MJ/d)",
        "CH4_grams": "Methane Production (g/d)",
        "CH4_grams_per_kg_DMI": "Methane Yield (g/kg DMI)",
        "CH4_intensity": "Methane Intensity (g/kg ECM)",
        "MCR": "Methane Conversion Rate (%)"
        #"MCR_Range": "Methane Conversion Range"
    }
    sections = {
        "Milk Production": [
            "Milk_Target_Production",
            "Milk_Energy_Supported",
            "Milk_Protein_Supported",
            "Milk_Supported",
            "Limiting_Nutrient",
            "NEL_Available",
            "MP_Available_kg"
        ],
        "Intake": [
            "DMI_Status",
            "DMI_Actual",
            "DMI_Target",
            "DMI_Difference"
        ],
        "Diet Cost": [
            "Diet_Cost_Total_AF",
            "Feed_Cost_Per_kg_Milk"
        ],
        "Methane Output": [
            "CH4_MJ",
            "CH4_grams",
            "CH4_grams_per_kg_DMI",
            "CH4_intensity",
            "MCR"
        ]
    }
    
    formatted_output = ""
    for section, keys in sections.items():
        formatted_output += f"\n--- {section} ---\n"
        for key in keys:
            if key in results_dict:
                value = results_dict[key]
                label = display_names.get(key, key)  # Use display name if available
                if isinstance(value, (int, float)):
                    formatted_output += f"{label}: {value:.2f}\n"
                else:
                    formatted_output += f"{label}: {value}\n"
    return formatted_output

# ===================================================================
# DIET PROPORTIONS FUNCTIONS
# ===================================================================

def abc_rename_variable(variable_name):
    """
    Rename variable by replacing 'Fd_' with 'Dt_' and adding 'In' suffix.
    
    Args:
        variable_name (str): Original variable name
        
    Returns:
        str: Renamed variable
    """
    new_name = variable_name.replace("Fd_", "Dt_") + "In"
    return new_name

def abc_replace_na_and_negatives(col):
    """
    Replace NaN and negative values with 0 in numeric columns.
    
    Args:
        col (Series): DataFrame column to process
        
    Returns:
        Series: Processed column
    """
    if col.dtype.kind in 'biufc':  # Check if the column is of numeric type
        col = col.apply(lambda x: 0 if pd.isna(x) or x < 0 else x)
    return col

def abc_create_proportions_dataframe_eval(ingredient_amounts_AF, ingredient_amounts_DM, f_nd):
    """
    Create proportions DataFrame adapted for evaluation system
    """
    Dt_DMInSum = sum(ingredient_amounts_DM)
    
    # Create base dataframe with ingredient info
    diet_data = []
    for i, name in enumerate(f_nd["Fd_Name"]):
        if ingredient_amounts_AF[i] > 0:
            diet_data.append({
                "Ingr_Type": f_nd["Fd_Type"][i],
                "Ingr_Name": name,
                "Intake_DM": round(float(ingredient_amounts_DM[i]), 2),
                "Intake_AF": round(float(ingredient_amounts_AF[i]), 2),
                "Dt_DMInp": round(float(ingredient_amounts_DM[i] / Dt_DMInSum * 100), 2),
                "Dt_AFInp": round(float(ingredient_amounts_AF[i] / sum(ingredient_amounts_AF) * 100), 2),
                "Ingr_Cost": round(float(f_nd["Fd_Cost"][i] * ingredient_amounts_AF[i]), 2)
            })
    
    Dt_proportions = pd.DataFrame(diet_data)
    
    # Calculate nutrient intake in %
    Col_names = [
        "Fd_ADF", "Fd_NDF", "Fd_Lg", "Fd_CP", "Fd_St", "Fd_EE", "Fd_FA", 
        "Fd_Ash", "Fd_NFC", "Fd_TDN", "Fd_Ca", "Fd_P"
    ]
    
    for nutrient in Col_names:
        if nutrient in f_nd:
            renamed_nutrient = abc_rename_variable(nutrient)
            # Calculate nutrient contribution for each ingredient
            nutrient_values = []
            for i, name in enumerate(f_nd["Fd_Name"]):
                if ingredient_amounts_AF[i] > 0:
                    nutrient_intake = ingredient_amounts_DM[i] * (f_nd[nutrient][i] / 100)
                    nutrient_percentage = (nutrient_intake / Dt_DMInSum) * 100
                    nutrient_values.append(round(float(nutrient_percentage), 2))
            
            if len(nutrient_values) == len(Dt_proportions):
                Dt_proportions[renamed_nutrient] = nutrient_values

    # Replace NA and negative numbers with 0
    Dt_proportions = Dt_proportions.apply(abc_replace_na_and_negatives)

    # Add totals row
    column_sums = Dt_proportions.select_dtypes(include=[np.number]).sum()
    total_row = pd.DataFrame([column_sums])
    total_row['Ingr_Type'] = ''
    total_row['Ingr_Name'] = 'Total'
    Dt_proportions = pd.concat([Dt_proportions, total_row], ignore_index=True)

    # Rename columns for report
    Dt_proportions = Dt_proportions.rename(columns={
        'Ingr_Type': 'Type',
        'Ingr_Name': 'Name',
        'Intake_DM': 'DM (kg)',
        'Intake_AF': 'AF (kg)',
        'Dt_DMInp': 'DM (%)',
        'Dt_AFInp': 'AF (%)',
        'Ingr_Cost': 'Cost',
        'Dt_CPIn': 'CP (%)',
        'Dt_NDFIn': 'NDF (%)',
        'Dt_ADFIn': 'ADF (%)',
        'Dt_LgIn': 'Lignin (%)',
        'Dt_StIn': 'Starch (%)',
        'Dt_EEIn': 'EE (%)',
        'Dt_FAIn': 'FA (%)',
        'Dt_AshIn': 'Ash (%)',
        'Dt_NFCIn': 'NFC (%)',
        'Dt_TDNIn': 'TDN (%)',
        'Dt_CaIn': 'Ca (%)',
        'Dt_PIn': 'P (%)'
    })

    # Fix total row values - ensure totals are correctly calculated
    total_row_index = Dt_proportions[Dt_proportions['Name'] == 'Total'].index
    if len(total_row_index) > 0:
        idx = total_row_index[0]
        # Calculate correct totals for nutrient columns
        nutrient_cols = ['CP (%)', 'NDF (%)', 'ADF (%)', 'Lignin (%)', 'Starch (%)', 
                        'EE (%)', 'FA (%)', 'Ash (%)', 'NFC (%)', 'TDN (%)', 'Ca (%)', 'P (%)']
        for col in nutrient_cols:
            if col in Dt_proportions.columns:
                col_total = Dt_proportions.loc[Dt_proportions['Name'] != 'Total', col].sum()
                Dt_proportions.loc[idx, col] = round(float(col_total), 2)

    return Dt_proportions

def abc_create_proportions_dataframe_eval_transposed(ingredient_amounts_AF, ingredient_amounts_DM, f_nd):
    """
    Create transposed proportions DataFrame adapted for evaluation system
    Nutrients as rows, ingredients as columns
    """
    Dt_DMInSum = sum(ingredient_amounts_DM)
    
    # Get ingredient names for columns
    ingredient_names = []
    for i, name in enumerate(f_nd["Fd_Name"]):
        if ingredient_amounts_AF[i] > 0:
            ingredient_names.append(name)
    
    # Add "Total" column
    ingredient_names.append("Total")
    
    # Create base dataframe with nutrients as rows
    nutrient_data = []
    
    # Add basic intake information
    nutrient_data.append({"Nutrient": "DM (kg)", "Unit": "kg"})
    nutrient_data.append({"Nutrient": "AF (kg)", "Unit": "kg"})
    nutrient_data.append({"Nutrient": "DM (%)", "Unit": "%"})
    nutrient_data.append({"Nutrient": "AF (%)", "Unit": "%"})
    
    # Add nutrient percentages
    Col_names = [
        "Fd_ADF", "Fd_NDF", "Fd_Lg", "Fd_CP", "Fd_St", "Fd_EE", "Fd_FA", 
        "Fd_Ash", "Fd_NFC", "Fd_TDN", "Fd_Ca", "Fd_P"
    ]
    
    for nutrient in Col_names:
        if nutrient in f_nd:
            renamed_nutrient = abc_rename_variable(nutrient)
            nutrient_data.append({"Nutrient": renamed_nutrient, "Unit": "%"})
    
    Dt_proportions = pd.DataFrame(nutrient_data)
    
    # Fill in the data for each ingredient column
    for j, name in enumerate(ingredient_names[:-1]):  # Exclude "Total" for now
        # Find the ingredient index
        ingr_idx = None
        for i, f_name in enumerate(f_nd["Fd_Name"]):
            if f_name == name and ingredient_amounts_AF[i] > 0:
                ingr_idx = i
                break
        
        if ingr_idx is not None:
            # Add intake data
            Dt_proportions.loc[0, name] = round(float(ingredient_amounts_DM[ingr_idx]), 2)
            Dt_proportions.loc[1, name] = round(float(ingredient_amounts_AF[ingr_idx]), 2)
            Dt_proportions.loc[2, name] = round(float(ingredient_amounts_DM[ingr_idx] / Dt_DMInSum * 100), 2)
            Dt_proportions.loc[3, name] = round(float(ingredient_amounts_AF[ingr_idx] / sum(ingredient_amounts_AF) * 100), 2)
            
            # Add nutrient percentages
            row_idx = 4
            for nutrient in Col_names:
                if nutrient in f_nd:
                    nutrient_intake = ingredient_amounts_DM[ingr_idx] * (f_nd[nutrient][ingr_idx] / 100)
                    nutrient_percentage = (nutrient_intake / Dt_DMInSum) * 100
                    Dt_proportions.loc[row_idx, name] = round(float(nutrient_percentage), 2)
                    row_idx += 1
    
    # Calculate totals column
    for i in range(len(Dt_proportions)):
        if i < 4:  # For intake data, sum the values
            total_value = Dt_proportions.iloc[i, 2:].sum()  # Sum all ingredient columns
            Dt_proportions.loc[i, "Total"] = round(float(total_value), 2)
        else:  # For nutrient percentages, sum the values
            total_value = Dt_proportions.iloc[i, 2:].sum()  # Sum all ingredient columns
            Dt_proportions.loc[i, "Total"] = round(float(total_value), 2)
    
    # Replace NA and negative numbers with 0
    Dt_proportions = Dt_proportions.apply(abc_replace_na_and_negatives)
    
    return Dt_proportions

# ===================================================================
# HTML REPORT GENERATION FUNCTIONS
# ===================================================================

def abc_create_animal_info_dataframe(animal_requirements):
    """
    Create Animal Information DataFrame for HTML report
    """
    animal_data = {
        "Parameter": [
            "Animal State",
            "Breed", 
            "Body Weight",
            "Body Condition Score",
            "Lactation Day",
            "Parity",
            "Gestation Day",
            "Target Frame Gain",
            "Target Milk Production",
            "Milk Fat %",
            "Milk Protein %",
            "Current Temperature",
            "Distance Grazing",
            "Topography"
        ],
        "Value": [
            animal_requirements.get("An_StatePhys", ""),
            animal_requirements.get("An_Breed", ""),
            animal_requirements.get("An_BW", 0),
            animal_requirements.get("An_BCS", 0),
            animal_requirements.get("An_LactDay", 0),
            animal_requirements.get("An_Parity", 0),
            animal_requirements.get("An_GestDay", 0),
            animal_requirements.get("Trg_FrmGain", 0),
            animal_requirements.get("Trg_MilkProd_L", 0),
            animal_requirements.get("Trg_MilkFatp", 0),
            animal_requirements.get("Trg_MilkTPp", 0),
            animal_requirements.get("Env_TempCurr", 0),
            animal_requirements.get("Env_Dist_km", 0),
            ["Flat", "Hilly", "Mountainous"][min(animal_requirements.get("Env_Topog", 0), 2)]
        ],
        "Unit": [
            "N/A",
            "N/A",
            "kg",
            "N/A",
            "days",
            "N/A",
            "days", 
            "kg/d",
            "L/d",
            "%",
            "%",
            "°C",
            "km",
            "N/A"
        ]
    }
    return pd.DataFrame(animal_data)

def abc_create_diet_dataframe(ingredient_amounts_AF, ingredient_amounts_DM, f_nd):
    """
    Create Diet DataFrame with columns in order: Ingredient, As-Fed(kg/d), Dry Matter, Price/kg, Cost(AF)
    """
    diet_data = []
    for i, name in enumerate(f_nd["Fd_Name"]):
        if ingredient_amounts_AF[i] > 0:
            diet_data.append({
                "Ingredient": name,
                "AF(kg/day)": round(float(ingredient_amounts_AF[i]), 2),
                "DM(kg/day)": round(float(ingredient_amounts_DM[i]), 2),
                "Price/kg": round(float(f_nd["Fd_Cost"][i]), 2),
                "Cost (AF)": round(float(f_nd["Fd_Cost"][i] * ingredient_amounts_AF[i]), 2)
            })
    
    # Add totals row
    total_af = sum(ingredient_amounts_AF)
    total_dm = sum(ingredient_amounts_DM)
    total_cost = sum([f_nd["Fd_Cost"][i] * ingredient_amounts_AF[i] for i in range(len(ingredient_amounts_AF)) if ingredient_amounts_AF[i] > 0])
    
    diet_data.append({
        "Ingredient": "TOTAL",
        "AF(kg/day)": round(float(total_af), 2),
        "DM(kg/day)": round(float(total_dm), 2),
        "Price/kg": "-",  # No total for price per kg
        "Cost (AF)": round(float(total_cost), 2)
    })
    
    return pd.DataFrame(diet_data)

def abc_create_milk_production_dataframe(allowable_milk):
    """
    Create Milk Production DataFrame for HTML report
    """
    milk_data = {
        "Parameter": [
            "Target Milk Production",
            "Milk Supported by Energy", 
            "Milk Supported by Protein",
            "Actual Milk Supported",
            "Limiting Nutrient"
        ],
        "Value": [
            allowable_milk.get("Milk_Target_Production", 0),
            allowable_milk.get("Milk_Energy_Supported", 0),
            allowable_milk.get("Milk_Protein_Supported", 0),
            allowable_milk.get("Milk_Supported", 0),
            allowable_milk.get("Limiting_Nutrient", "")
        ],
        "Unit": [
            "L/day",
            "L/day", 
            "L/day",
            "L/day",
            ""
        ]
    }
    return pd.DataFrame(milk_data).round(2)

def abc_create_intake_dataframe(allowable_milk):
    """
    Create Intake DataFrame for HTML report
    """
    intake_data = {
        "Parameter": [
            "Intake Status",
            "Actual Dry Matter Intake",
            "Target Dry Matter Intake", 
            "Intake Difference",
            "Intake as % of Target"
        ],
        "Value": [
            allowable_milk.get("DMI_Status", ""),
            allowable_milk.get("DMI_Actual", 0),
            allowable_milk.get("DMI_Target", 0),
            allowable_milk.get("DMI_Difference", 0),
            allowable_milk.get("DMI_Percent", 0)
        ],
        "Unit": [
            "",
            "kg/d",
            "kg/d",
            "kg/d", 
            "%"
        ]
    }
    return pd.DataFrame(intake_data).round(2)

def abc_create_cost_dataframe(allowable_milk):
    """
    Create Diet Cost DataFrame for HTML report
    """
    cost_data = {
        "Parameter": [
            "Total Diet Cost (As-Fed)",
            "Feed Cost per Liter Milk"
        ],
        "Value": [
            allowable_milk.get("Diet_Cost_Total_AF", 0),
            allowable_milk.get("Feed_Cost_Per_kg_Milk", 0)
        ],
        "Unit": [
            "VND/d",
            "VND/Liter milk"
        ]
    }
    return pd.DataFrame(cost_data).round(2)

def abc_create_environmental_dataframe(allowable_milk):
    """
    Create Environmental Impact DataFrame for HTML report
    """
    environmental_data = {
        "Parameter": [
            "Methane Production", 
            "Methane Yield",
            "Methane Intensity",
            "Methane Conversion Rate"
        ],
        "Value": [
            allowable_milk.get("CH4_grams", 0),
            allowable_milk.get("CH4_grams_per_kg_DMI", 0),
            allowable_milk.get("CH4_intensity", 0),
            allowable_milk.get("MCR", 0)
        ],
        "Unit": [
            "g/d",
            "g/kg DMI",
            "g/kg ECM",
            "%"
        ]
    }
    return pd.DataFrame(environmental_data)

def abc_generate_evaluation_report(animal_requirements, ingredient_amounts_AF, ingredient_amounts_DM, f_nd, allowable_milk, output_file="ration_evaluation_report.html", report_id=None, simulation_id=None, country_id=None, user_id=None, db=None):
    """
    Generate HTML report for ration evaluation results
    """
    
    # Get user and country information
    from datetime import datetime
    user_name = "Unknown User"
    country_name = "Unknown Country"
    
    if db and user_id:
        from core.evaluation.eval_support_methods import get_user_name_by_id, get_country_name_by_id
        user_name = get_user_name_by_id(user_id, db)
        country_name = get_country_name_by_id(country_id, db)
    
    # Create DataFrames for each section
    animal_info = abc_create_animal_info_dataframe(animal_requirements)
    diet_info = abc_create_diet_dataframe(ingredient_amounts_AF, ingredient_amounts_DM, f_nd)
    cost_info = abc_create_cost_dataframe(allowable_milk)
    proportions_info = abc_create_proportions_dataframe_eval_transposed(ingredient_amounts_AF, ingredient_amounts_DM, f_nd)
    milk_production = abc_create_milk_production_dataframe(allowable_milk)
    intake_info = abc_create_intake_dataframe(allowable_milk)
    environmental_info = abc_create_environmental_dataframe(allowable_milk)
    
    # Round numeric columns for animal_info and environmental_info 
    for df in [animal_info, environmental_info]:
        if not df.empty:
            num_cols = df.select_dtypes(include=[np.number]).columns
            df[num_cols] = df[num_cols].round(2)
    
    # Ensure diet dataframe shows proper decimal formatting
    if not diet_info.empty:
        num_cols = diet_info.select_dtypes(include=[np.number]).columns
        diet_info[num_cols] = diet_info[num_cols].round(2)
    
    # Proportions are already rounded at source

    # Custom CSS for modern, beautiful design (same as RationSmart)
    style = """
    <style>
      * { box-sizing: border-box; }
      
      body { 
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
        margin: 0; 
        padding: 5px; 
        line-height: 1.6; 
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        min-height: 100vh;
      }
      
      .container {
        max-width: 1200px;
        margin: 0 auto;
        background: white;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        overflow: hidden;
      }
      
      .header {
        background: linear-gradient(135deg, #2e7d32 0%, #388e3c 100%);
        color: white;
        padding: 5px;
        text-align: center;
      }
      
      .header h1 {
        margin: 0;
        font-size: 1.1em;
        font-weight: bold;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
      }
      
      .report-meta {
        display: grid;
        grid-template-columns: repeat(5, 1fr);
        gap: 3px;
        margin-top: 4px;
        padding: 3px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        backdrop-filter: blur(10px);
      }
      
      .meta-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        flex: 1;
      }
      
      .meta-item strong {
        font-size: 0.8em;
        opacity: 0.9;
        margin-bottom: 1px;
      }
      
      .meta-value {
        font-size: 0.9em;
        font-weight: 500;
      }
      
      .content {
        padding: 4px;
      }
      
      h2 { 
        color: #2e7d32; 
        margin-top: 8px; 
        margin-bottom: 4px; 
        font-size: 1.0em; 
        font-weight: 500;
        border-bottom: 3px solid #4caf50;
        padding-bottom: 5px;
        display: flex;
        align-items: center;
        gap: 10px;
      }
      
      h3 { 
        color: #388e3c; 
        margin-top: 25px; 
        margin-bottom: 15px; 
        font-size: 1.3em; 
        font-weight: 500;
      }
      
      .table-container {
        background: white;
        border-radius: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin: 5px 0;
        overflow: hidden;
        max-width: 100%;
        overflow-x: auto;
      }
      
      table { 
        border-collapse: collapse; 
        width: auto;
        min-width: 100%;
        margin: 0;
        font-size: 12px;
        background: white;
        table-layout: fixed;
      }
      
      th, td { 
        padding: 5px 7px; 
        text-align: left; 
        border-bottom: 0.5px solid #e0e0e0;
        word-wrap: break-word;
        overflow-wrap: break-word;
        hyphens: auto;
      }
      
      th { 
        background: #4caf50;
        color: white;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      
      tr:hover { 
        background-color: #f8f9fa; 
        transition: background-color 0.3s ease;
      }
      
      tr:nth-child(even) { 
        background-color: #fafafa; 
      }
      
      /* Clear background for animal info and diet tables - ALL rows */
      .animal-info-table tr,
      .diet-table tr { 
        background-color: white !important; 
      }
      
      .animal-info-table tr:hover,
      .diet-table tr:hover { 
        background-color: #f8f9fa !important; 
      }
      
      /* Remove green background from total row in diet table */
      .diet-table .total-row {
        background-color: white !important;
        font-weight: 600;
        border-top: 0.5px solid #ddd !important;
      }
      
      /* Clear borders for animal info and diet tables */
      .animal-info-table td,
      .diet-table td {
        border-bottom: 0.5px solid #e0e0e0 !important;
      }
      
      /* Normal font weight for animal info and diet tables */
      .animal-info-table td,
      .diet-table td {
        font-weight: normal !important;
      }
      
      /* Proportions table styling */
      .proportions-table th:nth-child(1),
      .proportions-table td:nth-child(1) { width: 81px; }
      .proportions-table th:nth-child(2),
      .proportions-table td:nth-child(2) { width: 54px; }
      .proportions-table th:nth-child(3),
      .proportions-table td:nth-child(3) { width: 36px; }
      .proportions-table th:nth-child(4),
      .proportions-table td:nth-child(4) { width: 36px; }
      .proportions-table th:nth-child(5),
      .proportions-table td:nth-child(5) { width: 36px; }
      
      .summary-box { 
        background: linear-gradient(135deg, #e8f5e8 0%, #c8e6c9 100%);
        border: none;
        border-radius: 15px; 
        padding: 25px; 
        margin: 25px 0; 
        box-shadow: 0 4px 15px rgba(76, 175, 80, 0.2);
      }
      
      .cost-highlight { 
        background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%);
        font-weight: 600;
        padding: 8px 15px;
        border-radius: 8px;
        border-left: 4px solid #ff9800;
      }
      
      .metric-card {
        background: white;
        border-radius: 10px;
        padding: 5px;
        margin: 15px 0;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border-left: 4px solid #4caf50;
      }
      
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin: 5px 0;
      }
      
      .metric-item {
        background: white;
        border-radius: 10px;
        padding: 5px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        text-align: center;
        border-top: 4px solid #4caf50;
      }
      
      .metric-value {
        font-size: 2em;
        font-weight: 600;
        color: #2e7d32;
        margin: 10px 0;
      }
      
      .metric-label {
        color: #666;
        font-size: 0.9em;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      
      .section {
        margin: 15px 0;
        padding: 15px;
        background: white;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
      }
      
      .emoji {
        font-size: 1.0em;
      }
      
      .total-row {
        background-color: white !important;
        font-weight: 600;
        border-top: 0.5px solid #ddd !important;
      }
      
      /* PDF-specific improvements */
      @page { 
        margin: 0.5in; 
        size: A4; 
      }
      
      /* Page break controls for section separation */
      .page-break-before {
        page-break-before: always;
      }
      
      .page-break-after {
        page-break-after: always;
      }
      
      .section {
        page-break-inside: avoid;
        break-inside: avoid;
      }
      
      .table-container {
        page-break-inside: avoid;
        break-inside: avoid;
      }
      
      table { 
        page-break-inside: avoid;
        break-inside: avoid;
      }
      
      /* Ensure text doesn't get cut off */
      body {
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
      }
      
      /* PDF-friendly column width adjustments */
      .animal-info-table th:nth-child(1),
      .animal-info-table td:nth-child(1) { width: 25%; }
      .animal-info-table th:nth-child(2),
      .animal-info-table td:nth-child(2) { width: 25%; }
      .animal-info-table th:nth-child(3),
      .animal-info-table td:nth-child(3) { width: 25%; }
      .animal-info-table th:nth-child(4),
      .animal-info-table td:nth-child(4) { width: 25%; }
      
      .diet-table th:nth-child(1),
      .diet-table td:nth-child(1) { width: 25%; }
      .diet-table th:nth-child(2),
      .diet-table td:nth-child(2) { width: 15%; text-align: center; }
      .diet-table th:nth-child(3),
      .diet-table td:nth-child(3) { width: 20%; text-align: center; }
      .diet-table th:nth-child(4),
      .diet-table td:nth-child(4) { width: 20%; text-align: center; }
      .diet-table th:nth-child(5),
      .diet-table td:nth-child(5) { width: 20%; text-align: center; }
      
      .cost-table th:nth-child(1),
      .cost-table td:nth-child(1) { width: 34.5%; }
      .cost-table th:nth-child(2),
      .cost-table td:nth-child(2) { width: 32.75%; text-align: center; }
      .cost-table th:nth-child(3),
      .cost-table td:nth-child(3) { width: 32.75%; text-align: center; }
      
      .proportions-table th:nth-child(1),
      .proportions-table td:nth-child(1) { width: 12%; }
      .proportions-table th:nth-child(2),
      .proportions-table td:nth-child(2) { width: 16%; text-align: center; }
      .proportions-table th:nth-child(3),
      .proportions-table td:nth-child(3) { width: 19.2%; text-align: center; }
      .proportions-table th:nth-child(4),
      .proportions-table td:nth-child(4) { width: 19.2%; text-align: center; }
      .proportions-table th:nth-child(5),
      .proportions-table td:nth-child(5) { width: 19.2%; text-align: center; }
      .proportions-table th:nth-child(6),
      .proportions-table td:nth-child(6) { width: 14.4%; text-align: center; }
      
      .milk-table th:nth-child(1),
      .milk-table td:nth-child(1) { width: 34.5%; }
      .milk-table th:nth-child(2),
      .milk-table td:nth-child(2) { width: 32.75%; text-align: center; }
      .milk-table th:nth-child(3),
      .milk-table td:nth-child(3) { width: 32.75%; text-align: center; }
      
      .intake-table th:nth-child(1),
      .intake-table td:nth-child(1) { width: 34.5%; }
      .intake-table th:nth-child(2),
      .intake-table td:nth-child(2) { width: 32.75%; text-align: center; }
      .intake-table th:nth-child(3),
      .intake-table td:nth-child(3) { width: 32.75%; text-align: center; }
      
      .environmental-table th:nth-child(1),
      .environmental-table td:nth-child(1) { width: 37.95%; }
      .environmental-table th:nth-child(2),
      .environmental-table td:nth-child(2) { width: 31.025%; text-align: center; }
      .environmental-table th:nth-child(3),
      .environmental-table td:nth-child(3) { width: 31.025%; text-align: center; }
      
      @media (max-width: 768px) {
        .container {
          margin: 10px;
          border-radius: 10px;
        }
        
        .content {
          padding: 5px;
        }
        
        .header h1 {
          font-size: 2em;
        }
        
        .metric-grid {
          grid-template-columns: 1fr;
        }
        
        table {
          font-size: 12px;
        }
        
        th, td {
          padding: 8px 10px;
        }
      }
    </style>
    """

    # Assemble HTML with modern structure
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        "<meta charset='utf-8'/>",
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "<title>Ration Evaluation Report</title>",
        style,
        "</head><body>",
        
        "<div class='container'>",
        "<div class='header'>",
        "<h1>🐄 Ration Evaluation Report</h1>",
        "<div class='report-meta'>",
        f"<div class='meta-item'><strong>User</strong><span class='meta-value'>{user_name}</span></div>",
        f"<div class='meta-item'><strong>Country</strong><span class='meta-value'>{country_name}</span></div>",
        f"<div class='meta-item'><strong>Simulation ID</strong><span class='meta-value'>{simulation_id}</span></div>",
        f"<div class='meta-item'><strong>Report ID</strong><span class='meta-value'>{report_id or 'N/A'}</span></div>",
        f"<div class='meta-item'><strong>Generated</strong><span class='meta-value'>{datetime.now().strftime('%B %d, %Y at %I:%M %p')}</span></div>",
        "</div>",
        "</div>",
        
        "<div class='content'>",
        
        # Page 1: Animal Information + Diet (reduced gap)
        "<div class='section'>",
        "<h2><span class='emoji'>🐄</span>Animal Information</h2>",
        "<div class='table-container'>",
        animal_info.to_html(index=False, escape=False, classes='animal-info-table'),
        "</div>",
        "</div>",
        
        # Diet Section (reduced gap from Animal Information)
        "<div class='section page-break-after'>",
        "<h2><span class='emoji'>🍽️</span>Diet</h2>",
        "<div class='table-container'>",
        diet_info.to_html(index=False, escape=False, classes='diet-table', float_format='{:.2f}'.format),
        "</div>",
        "</div>",

        # Page 2: Diet Cost + Diet Composition
        "<div class='section'>",
        "<h2><span class='emoji'>💰</span>Diet Cost</h2>",
        "<div class='table-container'>",
        cost_info.to_html(index=False, escape=False, classes='cost-table', float_format='{:.2f}'.format),
        "</div>",
        "</div>",
        
        # Diet Proportions Section
        "<div class='section page-break-after'>",
        "<h2><span class='emoji'>📊</span>Diet Composition (%)</h2>",
        "<div class='table-container'>",
        proportions_info.to_html(index=False, escape=False, classes='proportions-table', float_format='{:.2f}'.format),
        "</div>",
        "</div>",
        
        # Page 3: Milk Production + Intake + Environmental
        "<div class='section'>",
        "<h2><span class='emoji'>🥛</span>Milk Production</h2>",
        "<div class='table-container'>",
        milk_production.to_html(index=False, escape=False, classes='milk-table', float_format='{:.2f}'.format),
        "</div>",
        "</div>",
        
        # Intake Section (moved to page 3)
        "<div class='section'>",
        "<h2><span class='emoji'>📊</span>Dry Matter Intake Assessment</h2>",
        "<div class='table-container'>",
        intake_info.to_html(index=False, escape=False, classes='intake-table', float_format='{:.2f}'.format),
        "</div>",
        "</div>",
        
        # Environmental Impact Section (moved to page 3)
        "<div class='section'>",
        "<h2><span class='emoji'>🌍</span>Environmental Impact</h2>",
        "<div class='table-container'>",
        environmental_info.to_html(index=False, escape=False, classes='environmental-table'),
        "</div>",
        "</div>",
        
        "</div>",  # Close content
        "</div>",  # Close container
        
        "</body></html>"
    ]

    html_content = "\n".join(html_parts)
    
    # Apply special styling to total row in diet table
    html_content = html_content.replace('<td>TOTAL</td>', '<td class="total-row">TOTAL</td>')
    
    # Find and style the entire total row
    total_row_pattern = r'(<tr[^>]*>.*?<td[^>]*>TOTAL</td>.*?</tr>)'
    def replace_total_row(match):
        row = match.group(1)
        return row.replace('<tr>', '<tr class="total-row">')
    
    html_content = re.sub(total_row_pattern, replace_total_row, html_content, flags=re.DOTALL)
    
    # Ensure file gets overwritten
    try:
        # Remove existing file if it exists
        if os.path.exists(output_file):
            os.remove(output_file)
    
        # Write new file
        Path(output_file).write_text(html_content, encoding="utf-8")
        print(f"✅ HTML Report generated: {output_file}")
        
        # PDF generation is now handled by the API endpoint
        # (moved to follow the same pattern as diet-recommendation API)
    
    except Exception as e:
        print(f"❌ Error writing report: {e}")
        print(f"   Attempted to write to: {os.path.abspath(output_file)}")

# ===================================================================
# MAIN EXECUTION SECTION
# ===================================================================

def abc_main(animal_inputs, f_nd, simulation_id, country_id, user_id, feed_evaluation_data, db=None):
    """
    Main diet evaluation function that performs ration evaluation.
    
    Parameters:
    -----------
    animal_inputs : dict
        Animal parameters for requirements calculation
    f_nd : dict
        Feed nutritional data dictionary
    simulation_id : str
        Simulation ID for report naming
    country_id : str
        Country ID for context
    user_id : str
        User ID for context
    feed_evaluation_data : list
        List of feed evaluation data with quantities and prices
    db : Session
        Database session for report ID generation
        
    Returns:
    --------
    dict : Dictionary containing evaluation results
    """
    # Generate report_id at the very beginning
    from core.evaluation.eval_support_methods import generate_eval_report_id
    report_id = generate_eval_report_id(db) if db else f"eval-{simulation_id}"
    # Calculate animal requirements
    animal_requirements = abc_calculate_an_requirements(animal_inputs)

    # Extract required variables
    Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
    An_NEL = animal_requirements["An_NEL"]
    An_MBW = animal_requirements["An_MBW"]
    An_BW = animal_requirements["An_BW"]
    An_StatePhys = animal_requirements["An_StatePhys"]
    Body_NP_CP = 0.86  # Constant
    An_MPg = animal_requirements["An_MPg"]
    An_MPp = animal_requirements["An_MPp"]
    An_MPl = animal_requirements["An_MPl"]
    An_NELm = animal_requirements["An_NELm"]
    An_NEgest = animal_requirements["An_NEgest"]
    An_NELgain = animal_requirements["An_NELgain"]
    An_NELlact = animal_requirements["An_NELlact"]
    Trg_MilkProd = animal_requirements["Trg_MilkProd"]
    Trg_NEmilk_Milk = animal_requirements["Trg_NEmilk_Milk"]
    Trg_MilkTPp = animal_inputs["Trg_MilkTPp"]
    An_LactDay = animal_inputs["An_LactDay"]

    # ===================================================================
    # PREPARE FEED DATA FROM API REQUEST
    # ===================================================================
    
    # Initialize arrays for ingredient amounts
    num_feeds = len(f_nd["Fd_Name"])
    ingredient_amounts_AF = np.zeros(num_feeds)
    
    # Process feed evaluation data from API request
    for feed_item in feed_evaluation_data:
        feed_id = feed_item["feed_id"]
        quantity_as_fed = feed_item["quantity_as_fed"]
        price_per_kg = feed_item["price_per_kg"]
        
        # Find the feed in f_nd by name (assuming feed_id is the feed name)
        feed_index = None
        for i, feed_name in enumerate(f_nd["Fd_Name"]):
            if feed_name == feed_id:
                feed_index = i
                break
        
        if feed_index is not None:
            # Set the quantity
            ingredient_amounts_AF[feed_index] = quantity_as_fed
            # Override the price
            f_nd["Fd_Cost"][feed_index] = price_per_kg
        else:
            print(f"Warning: Feed '{feed_id}' not found in feed database")

    # Convert As-Fed amounts to Dry Matter amounts
    ingredient_amounts_DM = ingredient_amounts_AF * (f_nd["Fd_DM"] / 100)

    # Add the DM amounts to f_nd for calculations
    f_nd["Fd_DMIn"] = ingredient_amounts_DM
    f_nd["Fd_AFIn"] = ingredient_amounts_AF

    # Print summary
    print("=== RATION EVALUATION INPUT ===")
    print("Ingredient amounts (As-Fed vs Dry Matter):")
    for i, name in enumerate(f_nd["Fd_Name"]):
        if ingredient_amounts_AF[i] > 0:
            dm_percent = f_nd["Fd_DM"][i]
            print(f"{name}: {ingredient_amounts_AF[i]:.2f} kg AF → {ingredient_amounts_DM[i]:.2f} kg DM (DM: {dm_percent:.1f}%)")

    print(f"\nTotal As-Fed Intake: {np.sum(ingredient_amounts_AF):.2f} kg/day")
    print(f"Total DM Intake: {np.sum(ingredient_amounts_DM):.2f} kg/day")
    print(f"Target DMI: {Trg_Dt_DMIn:.2f} kg/day")
    print("-" * 50)

    # ===================================================================
    # DIET SUPPLY CALCULATION
    # ===================================================================

    diet_summary_values, intermediate_results_values, An_MPm = abc_diet_supply(
        x=ingredient_amounts_DM,
        f_nd=f_nd,
        animal_requirements=animal_requirements
    )

    # ===================================================================
    # MILK ALLOWANCE CALCULATION
    # ===================================================================

    allowable_milk = abc_predict_total_milk_supported(
        Supply_NEl=diet_summary_values[1],
        Supply_MP=diet_summary_values[2],
        Supply_DMIn=diet_summary_values[0],
        Trg_Dt_DMIn=Trg_Dt_DMIn,
        An_NELm=An_NELm,
        An_NEgest=An_NEgest,
        An_NELgain=An_NELgain,
        An_NELlact=An_NELlact,
        An_MPm=An_MPm,
        An_MPg=An_MPg,
        An_MPp=An_MPp,
        Trg_NEmilk_Milk=Trg_NEmilk_Milk,
        Trg_MilkTPp=Trg_MilkTPp,
        Trg_MilkProd=Trg_MilkProd,
        An_LactDay=An_LactDay,
        An_BW=An_BW, 
        ingredient_amounts_DM=ingredient_amounts_DM,
        f_nd=f_nd,
        An_StatePhys=An_StatePhys,
        animal_requirements=animal_requirements
    )
    
    # ===================================================================
    # RESULTS DISPLAY
    # ===================================================================

    print("\n" + "="*60)
    print("🐄 RATION EVALUATION RESULTS")
    print("="*60)
    print(abc_report_diet_eval(allowable_milk))
    
    # ===================================================================
    # GENERATE HTML REPORT
    # ===================================================================
    output_file = f"result_html/diet_eval_{report_id}.html"
    abc_generate_evaluation_report(
        animal_requirements=animal_requirements,
        ingredient_amounts_AF=ingredient_amounts_AF,
        ingredient_amounts_DM=ingredient_amounts_DM,
        f_nd=f_nd,
        allowable_milk=allowable_milk,
        output_file=output_file,
        report_id=report_id,
        simulation_id=simulation_id,
        country_id=country_id,
        user_id=user_id,
        db=db
    )
    
    # ===================================================================
    # RETURN RESULTS FOR API
    # ===================================================================
    return {
        "animal_requirements": animal_requirements,
        "ingredient_amounts_AF": ingredient_amounts_AF.tolist(),
        "ingredient_amounts_DM": ingredient_amounts_DM.tolist(),
        "f_nd": {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in f_nd.items()},
        "allowable_milk": allowable_milk,
        "simulation_id": simulation_id,
        "country_id": country_id,
        "user_id": user_id,
        "report_id": report_id
    }

# python RFT_Y2_Diet_Eval.py