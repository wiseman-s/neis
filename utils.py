# api/utils.py
import os
import pandas as pd

DATA_PATH = os.path.join(os.path.dirname(__file__), "../data")  # adjust path to your data folder

# Expected columns
GEN_COLUMNS = ["date", "generation_mwh", "county"]
EM_COLUMNS = ["date", "emissions_tCO2", "county"]

def load_csv_safe(filename, expected_columns):
    """
    Loads a CSV and ensures all expected columns exist.
    Fills missing columns with default values (0 or empty string).
    """
    file_path = os.path.join(DATA_PATH, filename)
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
    else:
        df = pd.DataFrame(columns=expected_columns)

    # Add missing columns
    for col in expected_columns:
        if col not in df.columns:
            df[col] = 0 if "mwh" in col or "emissions" in col else ""

    # Optional: fill NaNs with defaults
    for col in df.columns:
        if df[col].dtype.kind in 'iufc':  # numeric columns
            df[col] = df[col].fillna(0)
        else:
            df[col] = df[col].fillna("")

    return df

# Load generation and emissions data
GEN_DF = load_csv_safe("generation.csv", GEN_COLUMNS)
EM_DF = load_csv_safe("emissions.csv", EM_COLUMNS)
