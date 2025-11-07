"""
Optimization core module.

This module contains the core optimization engine for diet formulation:
- Optimization problem definition (DietOptimizationProblem)
- Custom sampling and repair operators for constrained optimization
- NSGA-II multi-objective optimization implementation
- Diet supply calculations and nutritional evaluation
- Bounds calculation and feasibility checking
"""

import numpy as np
import logging
import time
from pymoo.core.problem import Problem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.optimize import minimize
from pymoo.termination import get_termination
from pymoo.operators.crossover.sbx import SimulatedBinaryCrossover
from pymoo.operators.mutation.pm import PolynomialMutation
from pymoo.core.sampling import Sampling
from pymoo.core.repair import Repair
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

# Import configuration
from .config import Constraints

# Import utilities
from .utilities import safe_divide, safe_sum

# Import constraint evaluation
from .constraints import evaluate_constraints, build_conditional_constraints

def rsm_bounds_xlxu(f_nd, animal_requirements, dmi_lo=0.90, dmi_hi=1.05):
    # Attribute lower (xl) and upper (xu) bounds for the decision variables
    # Initialize bounds
    n = len(f_nd["Fd_Name"])
    trg = float(animal_requirements["Trg_Dt_DMIn"])
    xl = np.zeros(n + 1, dtype=float)  # +1 for DMI
    xu = np.ones(n + 1, dtype=float)   # +1 for DMI
    
    # DMI bounds (last variable) in the array
    xl[-1] = trg * dmi_lo
    xu[-1] = trg * dmi_hi
    
    # Get constraint thresholds
    animal_state = animal_requirements.get("An_StatePhys", "Lactating Cow")
    thr = Constraints.get(animal_state, {})
    
    # === FEED CATEGORIZATION  ===
    feed_names = f_nd.get("Fd_Name", [])
    feed_types = f_nd.get("Feed_Type", f_nd.get("Fd_Type", []))
    feed_categories = f_nd.get("Fd_Category", f_nd.get("Category", []))
    dm_values = f_nd.get("Fd_DM", f_nd.get("DM_Percent", []))
    
    minerals = []
    urea_feeds = []
    
    for i, (name, ftype, category, dm) in enumerate(zip(feed_names, feed_types, feed_categories, dm_values)):
        if str(category).strip() == "Minerals":
            minerals.append(i)
        elif 'urea' in str(name).lower():
            urea_feeds.append(i)
    
    # Mineral minimum bounds and cap (kg → proportion conversion)
    # Read from Constraints configuration 
    mineral_min_kg = thr.get("mineral_min", 0.050)  # kg per day
    mineral_max_kg = thr.get("mineral_max", 0.800)  # kg per day
    
    # Convert from kg to proportions of total DMI
    mineral_min_proportion = mineral_min_kg / trg
    mineral_max_proportion = mineral_max_kg / trg
    
    for idx in minerals:
        xu[idx] = min(xu[idx], mineral_max_proportion)
        xl[idx] = max(xl[idx], mineral_min_proportion)
        # Fix inconsistent mineral bounds
        if xl[idx] > xu[idx]:
            print(f"   WARNING: Mineral bound conflict for {feed_names[idx]}, adjusting min to max")
            xl[idx] = xu[idx]
        print(f"   Mineral bounds: {feed_names[idx]} {xl[idx]*100:.1f}% - {xu[idx]*100:.1f}%")
    
    # Urea cap
    if "urea_max" in thr:
        urea_limit = thr["urea_max"]
        for idx in urea_feeds:
            xu[idx] = min(xu[idx], urea_limit)
            print(f"   Urea cap: {feed_names[idx]} ≤ {urea_limit*100:.1f}%")
    
    # Fix inconsistent bounds
    inconsistent = xl > xu
    if np.any(inconsistent[:n]):
        xl[inconsistent] = xu[inconsistent]
    
    # Check total requirements
    total_xl = np.sum(xl[:n])
    if total_xl > 1.0:
        scale_factor = 0.95 / total_xl
        xl[:n] *= scale_factor
        print(f"   Scaled bounds by {scale_factor:.3f}")
    
    final_total = np.sum(xl[:n])

    return xl, xu


def _project_to_simplex(v):
    # Project to simplex to ensure the sum of the values is 1
    v = np.maximum(v, 0.0)
    if v.sum() == 0.0:
        return np.full_like(v, 1.0 / len(v))
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    rho = np.nonzero(u * (np.arange(1, len(v) + 1)) > (cssv - 1))[0][-1]
    theta = (cssv[rho] - 1) / (rho + 1)
    w = np.maximum(v - theta, 0.0)

    s = w.sum()
    if s <= 0:
        w = np.full_like(v, 1.0 / len(v))
    else:
        w = w / s
    return w


class SimplexPlusDmiRepair(Repair):
    def __init__(self, xl, xu):
        super().__init__()
        self.xl = np.asarray(xl, dtype=float)
        self.xu = np.asarray(xu, dtype=float)

    def _do(self, problem, X, **kwargs):
        Y = np.asarray(X, dtype=float).copy()
        n_var = Y.shape[1]
        n = n_var - 1

        # clamp t (DMI)
        Y[:, -1] = np.clip(Y[:, -1], self.xl[-1], self.xu[-1])

        # Project to simplex and enforce bounds
        P = Y[:, :n]
        P[P < 0.0] = 0.0
        
        for i in range(P.shape[0]):
            P[i, :] = _project_to_simplex(P[i, :])     # Standard projection
            P[i, :] = np.maximum(P[i, :], self.xl[:n]) # Lower bounds
            P[i, :] = np.minimum(P[i, :], self.xu[:n]) # Upper bounds
            P[i, :] = P[i, :] / P[i, :].sum()          # Renormalize to simplex
        Y[:, :n] = P
        return Y


class SimplexPlusDmiSampling(Sampling):
    # Sampling in simplex
    def __init__(self, xl, xu):
        super().__init__()
        self.xl = np.asarray(xl, dtype=float)
        self.xu = np.asarray(xu, dtype=float)

    def _do(self, problem, n_samples, **kwargs):
        n_var = problem.n_var
        n = n_var - 1  # Last pos is t

        # Generate samples that respect bounds
        P = np.zeros((n_samples, n))
        
        for i in range(n_samples):
            # Start with Dirichlet sampling
            sample = np.random.dirichlet(np.ones(n))
            
            # Enforce bounds and renormalize
            sample = np.maximum(sample, self.xl[:n])  # Lower bounds
            sample = np.minimum(sample, self.xu[:n])  # Upper bounds
            sample = sample / sample.sum()           # Renormalize to simplex
            P[i, :] = sample

        # t uniform in interval
        t_lo, t_hi = self.xl[-1], self.xu[-1]
        T = np.random.uniform(t_lo, t_hi, size=(n_samples, 1))

        X = np.hstack([P, T])
        return X
    

def rsm_decode_solution_to_q(
    best_x,
    decision_mode,
    trg_dmi,
    n_ing=None,
    *,
    t_bounds=None,          # (t_lo, t_hi) in kg/d; pass your optimizer DMI bounds here
    strict_shape=True,      # if True, error on shape/length mismatches (recommended)
    allow_uniform_fallback=True  # if False, error instead of uniform when sums==0
):
    info = {"fallbacks": [], "warnings": []}
    x = np.asarray(best_x, dtype=float)

    # Basic NaN/inf check
    if not np.isfinite(x).all():
        raise ValueError("decode_solution_to_q: non-finite values in x")

    # Infer n_ing conservatively
    if n_ing is None:
        if str(decision_mode).lower() == "proportion":
            # Assume last entry is t only if vector length >= 2
            n_ing = x.size - 1 if x.size >= 2 else x.size
        else:
            n_ing = x.size
    n_ing = int(n_ing)

    if str(decision_mode).lower() == "proportion":
        # Expect exactly n_ing + 1
        if x.size == n_ing + 1:
            p_raw = np.clip(x[:n_ing], 0.0, None)
            s = p_raw.sum()
            if s <= 0:
                if not allow_uniform_fallback:
                    raise ValueError("decode_solution_to_q: sum(p_raw)==0")
                p = np.full(n_ing, 1.0 / n_ing)
                info["fallbacks"].append("uniform_p_due_to_zero_sum")
            else:
                p = p_raw / s
            t = float(x[-1])
        else:
            if strict_shape:
                raise ValueError(f"decode_solution_to_q: expected length {n_ing+1} for proportion mode, got {x.size}")
            # Defensive fallback (legacy): treat x as p only, use trg_dmi as t
            p_raw = np.clip(x[:n_ing], 0.0, None)
            s = p_raw.sum()
            if s <= 0:
                if not allow_uniform_fallback:
                    raise ValueError("decode_solution_to_q: sum(p_raw)==0 under fallback")
                p = np.full(n_ing, 1.0 / n_ing)
                info["fallbacks"].append("uniform_p_due_to_zero_sum_fallback")
            else:
                p = p_raw / s
            t = float(trg_dmi)
            info["fallbacks"].append("used_trg_dmi_due_to_missing_t")

        # Validate/repair t
        if not np.isfinite(t) or t <= 0:
            t = float(trg_dmi)
            info["fallbacks"].append("used_trg_dmi_due_to_bad_t")
        if t_bounds is not None:
            t_lo, t_hi = map(float, t_bounds)
            if (t < t_lo) or (t > t_hi):
                info["warnings"].append(f"t_clamped_from_{t:.3f}_to_bounds")
                t = float(np.clip(t, t_lo, t_hi))

        q = p * t
        return q, p, t, info

    # kg mode
    if x.size != n_ing:
        if strict_shape:
            raise ValueError(f"decode_solution_to_q: expected length {n_ing} for kg mode, got {x.size}")
        # Defensive: take first n_ing
        info["warnings"].append("kg_mode_trimmed_or_padded")
    q = np.clip(x[:n_ing], 0.0, None)
    s = q.sum()
    if s > 0:
        t = float(s)
        p = q / s
    else:
        if not allow_uniform_fallback:
            raise ValueError("decode_solution_to_q: sum(q)==0 in kg mode")
        t = float(trg_dmi)
        p = np.full(n_ing, 1.0 / n_ing)
        q = p * t
        info["fallbacks"].append("uniform_q_due_to_zero_sum")

    if t_bounds is not None:
        t_lo, t_hi = map(float, t_bounds)
        if (t < t_lo) or (t > t_hi):
            info["warnings"].append(f"t_clamped_from_{t:.3f}_to_bounds")
            # In kg mode we don't rescale q to the clamped t automatically—warn instead:
            t = float(np.clip(t, t_lo, t_hi))

    return q, p, t, info


def calculate_discount(TotalTDN, DMI, An_MBW):
    """Calculate the nutritional discount based on TDN and DMI."""
    if DMI < 1e-6: # secure division by zero
        return 1.0
    if TotalTDN < 0:
        return 1.0  # No TDN, no discount
    TDNconc = safe_divide(TotalTDN , DMI, default_value=0) * 100 # transform in % of DM
    DMI_to_maint = TotalTDN / (0.035 * An_MBW) if TotalTDN >= (0.035 * An_MBW) else 1
    if TDNconc < 60:
        return 1.0
    return (TDNconc - ((0.18 * TDNconc - 10.3) * (DMI_to_maint - 1))) / TDNconc


def calculate_MEact(f_nd):     # As NRC ... NASEM eq ME = DE - UE - GAS_E (I do not have all parameters to calculate UE currently)
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


def rsm_diet_supply(x, f_nd, animal_requirements):
    """
    Calculate the diet supply based on the input vector x and feed data.
    
    Parameters:
    -----------
    x : array-like
        Feed amounts in kg/day for each ingredient
    f_nd : dict
        Feed nutritional data dictionary from rsm_process_feed_library()
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

        # ENERGY UNIT HANDLING:
        # - Cows: Use NEL (Net Energy Lactation) in Mcal/d
        # - Heifers: Use ME (Metabolizable Energy) converted to Mcal/d via DE * 0.82
        # Both are stored in nutritional_supply[1] and nutrient_targets[1] but represent different units
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
        Supply_MP = (total_CP_g_d * 0.67) / 1000 # kg/d
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


def rsm_run_optimization(animal_requirements = None, f_nd = None, optimization_params=None, decision_mode=None, cfg=None):
    # Run ration optimization using NSGA-II algorithm.
    # Use config as single source of truth

    # Debug: Log the cfg parameter
    print(f"🔍 DEBUG: cfg parameter received: {cfg is not None}")
    if cfg:
        print(f"🔍 DEBUG: cfg values - generations: {cfg.get('generations')}, initial_epsilon: {cfg.get('initial_epsilon')}, n_workers: {cfg.get('n_workers')}")
    else:
        print("🔍 DEBUG: cfg is None - will use fallback values")

    if cfg is None:
        # Use the same RUN_CONFIG values as defined in rsm_main()
        cfg = {
            "pop_size": 100, "generations": 200, "initial_epsilon": 3.00, "final_epsilon": 0.05,
            "crossover_prob": 0.9, "crossover_eta": 5, "mutation_prob": 0.3, "mutation_eta": 5,
            "seed": 42, "verbose": True, "n_workers": 7, "dmi_lo": 0.90, "dmi_hi": 1.05,
            "energy_offset": 1.0, "mp_offset": 0.10, "decision_mode": "proportion"
        }
            
    # Extract parameters from config
    dmi_lo = cfg.get("dmi_lo", 0.90)
    dmi_hi = cfg.get("dmi_hi", 1.05)
    decision_mode = decision_mode or cfg.get("decision_mode", "proportion")
    
    # Default optimization parameters from config
    default_params = {
        "pop_size": cfg.get("pop_size", 100),
        "generations": cfg.get("generations", 100),
        "initial_epsilon": cfg.get("initial_epsilon", 2.0),
        "final_epsilon": cfg.get("final_epsilon", 0.05),
        "crossover_prob": cfg.get("crossover_prob", 0.9),
        "crossover_eta": cfg.get("crossover_eta", 5),
        "mutation_prob": cfg.get("mutation_prob", 0.3),
        "mutation_eta": cfg.get("mutation_eta", 5),
        "seed": cfg.get("seed", 42),
        "verbose": cfg.get("verbose", True),
        "n_workers": cfg.get("n_workers", 1)
    }
    
    # Legacy support: optimization_params can still override config
    params = {**default_params, **(optimization_params or {})}

     # --- feed-nutrient dict (f_nd) must be provided ---
    if f_nd is None or not isinstance(f_nd, dict) or "Fd_Name" not in f_nd or len(f_nd["Fd_Name"]) == 0:
        raise ValueError(
            "run_optimization requires a valid f_nd (feed nutrient dict). "
            "Make sure to pass the f_nd returned by rsm_process_feed_library(..., sheet_name='Fd_selected')."
        )
    
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

    if decision_mode == "proportion":
        # Calculate bounds with automatic constraint enforcement
        xl, xu = rsm_bounds_xlxu(f_nd, animal_requirements, dmi_lo=dmi_lo, dmi_hi=dmi_hi)
        sampling_op = SimplexPlusDmiSampling(xl, xu)
        repair_op   = SimplexPlusDmiRepair(xl, xu)
    else:
        # Legacy kg mode - create simple bounds (0 to DMI for each ingredient)
        n = len(f_nd["Fd_Name"])
        Trg_Dt_DMIn = animal_requirements["Trg_Dt_DMIn"]
        xl = np.zeros(n, dtype=float)
        xu = np.full(n, Trg_Dt_DMIn, dtype=float)
        sampling_op = FloatRandomSampling()
        repair_op   = None

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
        diet_supply=rsm_diet_supply,
        decision_mode=decision_mode,
        energy_offset=cfg.get("energy_offset", 1.0),
        mp_offset=cfg.get("mp_offset", 0.10),
        dmi_lo=dmi_lo,
        dmi_hi=dmi_hi,
        cfg=cfg  # Pass configuration for user-first constraints
    )
    
    # Set the algorithm (NSGA-II)
    algorithm = NSGA2(
        pop_size=params["pop_size"],
        #sampling=warm_start_sampling,
        sampling=sampling_op, 
        crossover=SimulatedBinaryCrossover(prob=params["crossover_prob"], eta=params["crossover_eta"]),  
        mutation=PolynomialMutation(prob=params["mutation_prob"], eta=params["mutation_eta"]),
        eliminate_duplicates=True,
        repair=repair_op,
        save_history=True
    )
    
    callback = EpsilonUpdateCallback(problem)
    start_time = time.time()
    stop_criteria = get_termination("n_gen", params["generations"])

    print(f"[run_opt] mode={decision_mode}  n_var={len(xl)}  pop={params['pop_size']}  gen={params['generations']}")
    
    # Optimize with ThreadPool multiprocessing 
    try:
        res = minimize(
            problem,
            algorithm,
            stop_criteria,
            seed=params["seed"],
            verbose=params["verbose"],
            callback=callback,
            save_history=True
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


def rsm_detect_present_categories(f_nd):
    fd_type = np.char.strip(np.char.lower(np.array(f_nd["Fd_Type"], dtype=str)))
    fd_cat   = np.array(f_nd["Fd_Category"], dtype=str)
    fd_cp = f_nd["Fd_CP"]
    fd_ndf = f_nd["Fd_NDF"]
    fd_dm = f_nd["Fd_DM"]
    
    mask_for = fd_type == "forage"
    is_mi    = fd_cat == "Minerals"
    mask_conc_all = ~mask_for & (~is_mi)
    n = len(f_nd["Fd_Name"])
    
    # Forage categories
    mask_straw = mask_for & (fd_dm > 85)
    mask_moist_forage = mask_for & (fd_dm < 80)  # Moist forages (regular grasses and silage)
    mask_lqf = mask_for & (fd_cp < 7) & (fd_ndf > 72) & (~mask_straw)  # Low-quality fibrous
    mask_wet_other = (fd_dm < 21) & (~mask_for)  # Wet non-forage ingredients

    # Concentrate categories
    is_byprod = f_nd.get("Fd_isbyprod", np.zeros(n)) > 0
    is_wet = fd_dm < 30
    is_wet_byprod = is_byprod & is_wet  # wet byproducts

    # Check for urea presence
    fd_names = np.char.strip(np.char.lower(np.array(f_nd["Fd_Name"], dtype=str)))
    mask_urea = np.char.find(fd_names, 'urea') >= 0
    
    return {
        'has_straw': np.any(mask_straw),
        'has_moist_forage': np.any(mask_moist_forage),
        'has_lqf': np.any(mask_lqf),
        'has_wet_byprod': np.any(is_wet_byprod),
        'has_wet_other': np.any(mask_wet_other),
        'has_concentrate': np.any(mask_conc_all),
        'has_urea': np.any(mask_urea),
        # Store masks for constraint building
        'mask_straw': mask_straw,
        'mask_moist_forage': mask_moist_forage,
        'mask_lqf': mask_lqf,
        'mask_wet_byprod': is_wet_byprod,
        'mask_wet_other': mask_wet_other,
        'mask_conc_all': mask_conc_all,
        'mask_urea': mask_urea
    }


class DietOptimizationProblem(Problem):
    def __init__(self, f_nd, animal_requirements, thr, An_NDF_req, An_NDFfor_req, An_St_req, An_EE_req,
                 initial_epsilon=0.3, final_epsilon=0.01, max_generations=1000, xl=None, xu=None, 
                 n_workers=None, diet_supply=None, decision_mode="kg", energy_offset=1.0, mp_offset=0.10,
                 dmi_lo=0.90, dmi_hi=1.05, cfg=None):
    
        self.initial_epsilon = initial_epsilon
        self.final_epsilon = final_epsilon
        self.max_generations = max_generations
        self.current_gen = 0
        self.thr = thr  # Store constraint thresholds
        self.diet_supply = diet_supply  # Store diet_supply function
        self.n_workers = n_workers  # ThreadPool workers
        self.decision_mode = decision_mode
        
        # Store energy and protein offsets from config
        self.energy_offset = energy_offset
        self.mp_offset = mp_offset
        
        # Store DMI bounds from config
        self.dmi_lo = dmi_lo
        self.dmi_hi = dmi_hi
        self.cfg = cfg  # Store configuration for user-first constraints

        # --- tracking & diagnostics ---
        self.current_epsilon = float(getattr(self, "initial_epsilon", 0.03))
        self.epsilon_history = []             
        self.last_satisfaction_flags = []       
        self.last_constraint_maps = []         
        self.final_epsilon = float(getattr(self, "final_epsilon", 0.01))
        
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
        self.categories = rsm_detect_present_categories(f_nd)

        # Exact constraint count = 12 core + conditionals + user-first
        base_constraints = 12  # DMI(2), Energy(2), MP(2), Ca(1), P(1), NDF(1), NDFfor(1), Starch(1), EE(1)
        conditional_count = sum([
            bool(self.categories['has_straw']),
            bool(self.categories['has_moist_forage']),
            bool(self.categories['has_lqf']),
            bool(self.categories['has_wet_byprod']),
            bool(self.categories['has_wet_other'])
        ])
        # Add user-first constraints if enabled
        user_first_count = 3 if cfg and cfg.get("enforce_user_constraints", False) else 0
        self.max_constraints = base_constraints + conditional_count + user_first_count

        n_var = len(xl) if xl is not None else len(f_nd["Fd_Name"])
        super().__init__(
            n_var=n_var,  
            n_obj=3,                      
            n_constr=self.max_constraints,
            xl=xl,                         
            xu=xu                          
        )

        # Store feed data
        self.f_nd = f_nd
        
        # Print detected categories 
        category_labels = {
            'has_straw': 'Straw/Stover/Hay',
            'has_moist_forage': 'Moist forages (DM < 80%)',
            'has_lqf': 'Low-quality fibrous forages',
            'has_wet_byprod': 'By-product wet',
            'has_wet_other': 'Wet non-forage ingredients',
            'has_urea': 'Urea (dangerous ingredient)'
        }
    
        active_categories = []
        for key, label in category_labels.items():
            if self.categories[key]:
                active_categories.append(label)

    def _decode_x_to_qpt(self, x):     
        #Decode the solution vector x to q, p, t (kg/d, proportions, kg/d)
        #light simplification of decode_solution_to_q.  Necessary here for optimization (Called several times)
        x = np.asarray(x, dtype=float)
        if self.decision_mode == "proportion":
            n_ing = self.n_var - 1
            p = np.clip(x[:n_ing], 0.0, None)
            s = p.sum()
            if s <= 0.0:
                p = np.full(n_ing, 1.0 / n_ing)
            else:
                p = p / s
            t = float(x[-1])
            q = p * t
        else:
            # legacy "kg" mode
            q = np.clip(x, 0.0, None)
            t = float(q.sum())
            if t <= 0.0:
                t = float(self.Trg_Dt_DMIn)
                p = np.full_like(q, 1.0 / len(q))
            else:
                p = q / t

        return q, p, t

    def advance_generation(self, n_gen):
        self.current_gen = n_gen
    
    def _evaluate_single(self, x):
        try:
            # decode x -> q,p,t (q is kg/d)
            q, p, t = self._decode_x_to_qpt(x)

            diet_summary_values, intermediate_results_values, An_MPm = rsm_diet_supply(
                q, self.f_nd, self.animal_requirements
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

            # Get offsets from config (align with Pre_optimization.py)
            energy_offset = getattr(self, 'energy_offset', 1.0)  # Default 1.0 to match Pre_optimization
            mp_offset = getattr(self, 'mp_offset', 0.10)

            # energy_target_with_margin = energy_target + energy_offset  # Same as constraint
            # protein_target_with_margin = An_MP_req + mp_offset   # Same as constraint

            # Use base targets (no margins) - build_conditional_constraints adds offsets internally
            nutrient_targets = np.array([self.Trg_Dt_DMIn, energy_target, An_MP_req, 
                self.An_Ca_req, self.An_P_req, self.An_NDF_req, self.An_NDFfor_req,
                self.An_St_req, self.An_EE_req   
            ])
        
            nutritional_supply = np.array([DMI, energy_supply, MP, Ca, P, NDF, NDFfor, St, EE])

            # Normilize objectives

            #Objective 1
            eps = 1e-3
            total_cost = float((q * self.f_nd["Fd_CostDM"]).sum())
            mean_cost_dm = float(np.mean(self.f_nd["Fd_CostDM"]))
            cost_scale = max(mean_cost_dm * self.Trg_Dt_DMIn, eps)
            total_cost = (total_cost / cost_scale) * 0.1

            #Objective 2
            total_intake_dev = abs(self.Trg_Dt_DMIn - DMI) / max(self.Trg_Dt_DMIn, eps)

            #Objective 3
            #dev_dmi = abs(DMI - self.Trg_Dt_DMIn) / max(self.Trg_Dt_DMIn, eps)
            dev_energy = abs(energy_supply - energy_target) / max(energy_target, eps)  
            dev_mp = abs(MP - An_MP_req) / max(An_MP_req, eps)
            total_dev = dev_energy + dev_mp       
            
            # Restrictions (G <= 0) - Using conditional constraints
            current_gen = self.current_gen
            # Linear epsilon decay
            if self.max_generations > 1:
                epsilon = self.initial_epsilon - (self.initial_epsilon - self.final_epsilon) * (current_gen / (self.max_generations - 1))
            else:
                epsilon = self.final_epsilon
            
            nutrient_targets = np.array([
                self.Trg_Dt_DMIn,                # DMI
                energy_target,                   # Energy (base target - offset added in build_conditional_constraints)
                An_MP_req,                       # MP (base target - offset added in build_conditional_constraints)
                self.An_Ca_req,                  # Ca
                self.An_P_req,                   # P
                self.An_NDF_req,                 # NDF max
                self.An_NDFfor_req,              # NDF forage min
                self.An_St_req,                  # Starch max
                self.An_EE_req                   # EE max
            ], dtype=float)

            nutritional_supply = np.array([DMI, Energy, MP, Ca, P, NDF, NDFfor, St, EE], dtype=float)

            # Build conditional constraints (no classification here)
            G, scales, constraint_names = build_conditional_constraints(
                q, nutritional_supply, nutrient_targets, epsilon, 
                self.f_nd, self.Trg_Dt_DMIn, self.thr, self.categories, self.animal_requirements, 
                energy_offset=energy_offset, mp_offset=mp_offset, apply_offset_on_max=True,
                dmi_lo=self.dmi_lo, dmi_hi=self.dmi_hi, cfg=self.cfg
            )

            violated_constraints = {}
            for i, g_val in enumerate(G):
                if g_val > 0: # A constraint is violated if its value is > 0
                    # Store the name and how much it was violated by (after normalization)
                    violated_constraints[constraint_names[i]] = g_val / scales[i]
            
            # Normalize the restrictions
            scales = np.maximum(np.abs(np.array(scales, dtype=float)), 1e-3)
            G_n = np.array(G, dtype=float) / scales
            
            # Evaluate severities and final satisfaction flag centrally
            constraint_map, satisfaction_flag = evaluate_constraints(
                q,
                nutritional_supply,
                nutrient_targets,
                epsilon,
                self.f_nd,
                self.Trg_Dt_DMIn,
                self.thr,
                self.categories,
                self.animal_requirements,
                energy_offset=energy_offset,
                mp_offset=mp_offset,
                dmi_lo=self.dmi_lo,
                dmi_hi=self.dmi_hi,
                cfg=self.cfg,
                constraint_names=constraint_names,
            )

            # Pad constraints to match maximum constraint count for pymoo
            if len(G_n) < self.max_constraints:
                G_n = np.pad(G_n, (0, self.max_constraints - len(G_n)))
            elif len(G_n) > self.max_constraints:
                G_n = G_n[:self.max_constraints]

            return total_cost, total_intake_dev, total_dev,  G_n, satisfaction_flag, violated_constraints, constraint_map

        except Exception as e:
            # LOG the actual error for debugging
            logging.error(f"Solution evaluation failed for x={x}: {e}")
            # MARK as invalid rather than fake data
            return None  # Or raise EvaluationFailedException
    
    def _evaluate(self, X, out, *args, **kwargs):
        # Evaluate population using safe ThreadPoolExecutor.
        cost = []
        total_intake_dev = []
        total_deviation = []
        restr = []
        satisfaction_flags = []
        violation_details_list = []
        constraint_maps_list = []
        
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
                    print(f"\n❌ Evaluation failed for solution {index}: {e}")
                    # Keep the same arity as _evaluate_single success path:
                    # (total_cost, total_intake_dev, total_dev, G_n, satisfaction_flag, violated_constraints, constraint_map)
                    results[index] = (
                        1e9,                      # total_cost
                        1e9,                      # total_intake_dev
                        1e9,                      # total_dev
                        np.full(self.max_constraints, 1e9),  # G_n
                        "INFEASIBLE",             # satisfaction_flag
                        {},                       # violated_constraints
                        {}                        # constraint_map
                    )
                    failed_evaluations += 1
        
        # Extract results
        for result in results:
            cost.append(result[0])
            total_intake_dev.append(result[1])
            total_deviation.append(result[2])
            restr.append(result[3])
            satisfaction_flags.append(result[4])
            violation_details_list.append(result[5])
            constraint_maps_list.append(result[6] if (result is not None and len(result) > 6) else {})
        
        if failed_evaluations > 0:
            print(f"{failed_evaluations}/{len(X)} evaluations failed and received penalty values")

        # Output
        out["F"] = np.column_stack([cost, total_intake_dev, total_deviation])  # Objective values
        out["G"] = np.array(restr)

        self.last_satisfaction_flags = satisfaction_flags  
        self.last_constraint_maps = constraint_maps_list


class EpsilonUpdateCallback:
    def __init__(self, problem):
        self.problem = problem  # Store a reference to the optimization problem

    def __call__(self, algorithm):
        """ This makes the class callable, updating the generation count dynamically """
        self.problem.advance_generation(algorithm.n_gen)
        if self.problem.max_generations > 1:
            eps = self.problem.initial_epsilon - \
                  (self.problem.initial_epsilon - self.problem.final_epsilon) * \
                  (self.problem.current_gen / (self.problem.max_generations - 1))
        else:
            eps = self.problem.final_epsilon
        # Save
        if not hasattr(self.problem, "epsilon_history") or self.problem.epsilon_history is None:
            self.problem.epsilon_history = []
        self.problem.epsilon_history.append(eps)
        self.problem.current_epsilon = eps


