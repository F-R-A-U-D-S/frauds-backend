import pandas as pd
import numpy as np
import re    

# Helper functions for cleaning specific column types
def preprocess_dataframe(df: pd.DataFrame) -> pd.DataFrame:
   
   # Make a copy to avoid modifying original DataFrame
    df = df.copy()

    log = []

    original_shape = df.shape
    log.append(f"Loaded dataset with {original_shape[0]} rows and {original_shape[1]} columns.")



    # Standardize missing value representations
    missing_tokens = [
        "", " ", "  ", "\t", "nan", "NaN", "NAN", "null", "NULL", "None", "none",
        "n/a", "na", "n.a", "---", "-", "?", "--", "...", "missing", "(blank)", "_"
    ]
    df_before = df.isna().sum().sum()
    df = df.replace(missing_tokens, np.nan)
    df_after = df.isna().sum().sum()
    log.append(f"Standardized missing values: replaced common bad tokens. Missing cells before: {df_before}, after: {df_after}.")


    # If a column contains only NaN → remove it
    rows_before = len(df)
    df = df.dropna(axis=0, how="all")
    rows_after = len(df)
    removed_rows = rows_before - rows_after
    if removed_rows > 0:
        log.append(f"Removed {removed_rows} empty rows containing only NaN.")


    # Clean amount column
    if "amount" in df.columns:
        non_numeric_before = df["amount"].astype(str).apply(lambda x: bool(re.search(r"[^\d.-]", x))).sum()
        df["amount"] = (
            df["amount"]
            .astype(str)
            .apply(lambda x: re.sub(r"[^\d.-]", "", x))  
            .replace("", np.nan)
            .astype(float)
        )
        non_numeric_after = df["amount"].isna().sum()
        log.append(
            f"Cleaned 'amount' column: found {non_numeric_before} non-numeric values; "
            f"converted to numeric. Missing values after cleaning: {non_numeric_after}."
        )
        

    # Clean categorical columns
    for col in df.select_dtypes(include='object').columns:
        null_before = df[col].isna().sum()
        df[col] = df[col].astype(str).str.strip().str.lower().replace("nan", np.nan)
        null_after = df[col].isna().sum()
        if null_after != null_before:
            log.append(f"Cleaned categorical column '{col}': trimmed spaces, normalized case, cleaned bad tokens.")


    # Convert timestamps
    if "timestamp" in df.columns:
        invalid_before = df["timestamp"].isna().sum()
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
        invalid_after = df["timestamp"].isna().sum()
        log.append(
            f"Processed 'timestamp' column: {invalid_after - invalid_before} invalid timestamps converted to NaT."
        )

    # Impute missing values
    df, impute_log = impute_missing_values(df)
    log.extend(impute_log)

    # Remove negative amounts
    if "amount" in df.columns:
        negative_count = (df["amount"] < 0).sum()
        df = df[df["amount"] >= 0]
        if negative_count > 0:
            log.append(f"Removed {negative_count} rows with negative amounts.")

    final_shape = df.shape
    log.append(
        f"Final dataset shape: {final_shape[0]} rows, {final_shape[1]} columns (started with {original_shape[0]} rows, {original_shape[1]} cols)."
    )
    return df, log


# Helper function to impute missing values
def impute_missing_values(df: pd.DataFrame):
    """
    Impute missing values for numeric and categorical columns
    """
    log = []
    numeric_cols = df.select_dtypes(include='number').columns
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns

    # Numeric: median imputation
    for col in numeric_cols:
        missing_before = df[col].isna().sum()
        if missing_before > 0:
            median_val = df[col].median()
            df[col] = df[col].fillna(median_val)
            log.append(f"Imputed {missing_before} missing values in numeric column '{col}' using median={median_val}.")

    # Categorical: fill with 'unknown'
    for col in categorical_cols:
        missing_before = df[col].isna().sum()
        if missing_before > 0:
            df[col] = df[col].fillna("unknown")
            log.append(f"Imputed {missing_before} missing values in categorical column '{col}' with 'unknown'.")

    return df, log



