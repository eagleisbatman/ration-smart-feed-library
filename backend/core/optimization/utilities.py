"""
Utility functions for diet optimization.

This module contains general-purpose helper functions used throughout
the optimization system, including:
- Data preprocessing and validation
- Mathematical operations with safety checks
- Variable naming conventions
- Temperature adjustments
"""

import pandas as pd
import numpy as np


def adjust_dmi_temperature(DMI, Temp):
    """
    Adjust DMI based on temperature conditions.
    
    Args:
        DMI (float): Dry Matter Intake
        Temp (float): Current temperature
        
    Returns:
        float: Temperature-adjusted DMI
    """
    if Temp > 20:
        return DMI * (1 - (Temp - 20) * 0.005922)
    elif Temp < 5:
        return DMI * (1 - (5 - Temp) * 0.004644)
    else:
        return DMI


def preprocess_dataframe(df):
    """
    Preprocess DataFrame by converting data types and handling NaN values.
    
    Args:
        df (DataFrame): Input DataFrame to preprocess
        
    Returns:
        DataFrame: Preprocessed DataFrame
    """
    for col in df.columns:
        # Convert integers to float
        if pd.api.types.is_integer_dtype(df[col]):
            df[col] = df[col].astype(np.float64)
        
        # Replace NaN values with 0
        df[col] = df[col].fillna(0)
    
    return df


def rename_variable(variable_name):
    """
    Rename variable by replacing 'Fd_' with 'Dt_' and adding 'In' suffix.
    
    Args:
        variable_name (str): Original variable name
        
    Returns:
        str: Renamed variable
    """
    new_name = variable_name.replace("Fd_", "Dt_") + "In"
    return new_name


def replace_na_and_negatives(col):
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


def safe_divide(numerator, denominator, default_value=0.0):
    """Safely divide, avoiding division by zero"""
    if abs(denominator) < 1e-12:  # Very small number
        return default_value
    return numerator / denominator


def safe_sum(array):
    """Safely sum an array, handling NaN values"""
    array = np.array(array)
    array = np.nan_to_num(array, nan=0.0)  # Replace NaN with 0
    return np.sum(array)


def _msg(level, code, where, summary, detail=None, hint=None, autofix=False):
    """
    Create a standardized message dictionary.
    
    Args:
        level (str): Message level (e.g., 'info', 'warning', 'error')
        code (str): Message code identifier
        where (str): Location where message originated
        summary (str): Brief summary of the message
        detail (str, optional): Detailed message content
        hint (str, optional): Hint for resolving the issue
        autofix (bool, optional): Whether an autofix was applied
        
    Returns:
        dict: Standardized message dictionary
    """
    return {
        "level": level, "code": code, "where": where,
        "summary": summary, "detail": detail, "hint": hint,
        "autofix_applied": bool(autofix)
    }

