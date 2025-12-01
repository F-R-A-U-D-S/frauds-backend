import os
import pandas as pd
from fastapi import HTTPException

COUNTRIES = {"USA","CANADA","INDIA","UK","UAE","CHINA","JAPAN","FRANCE","GERMANY"}
CHANNELS = ["online", "pos", "mobile", "atm"]

def validate_file_extension(filename: str):
    """
    Validate uploaded file extension.
    Raise HTTPException if invalid.
    """
    allowed_extensions = [".csv",".xls",".xlsx"]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file extension '{ext}'. Please Upload a {allowed_extensions} File"
        )
    return 'File Extension Valid. Uploaded Successfully.'

from fastapi import HTTPException

def validate_file_size(file_size: int, max_size_mb: int = 5):
    """
    Validates the uploaded file size against a configurable limit.

    Args:
        file_size (int): Size of the uploaded file in bytes.
        max_size_mb (int): Maximum allowed file size in MB (default: 5MB).

    Raises:
        HTTPException: If the file exceeds the allowed size limit.

    Returns:
        str: Success message if validation passes.
    """

    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds the allowed limit of {max_size_mb} MB."
        )

    return "File size is valid."


def validate_required_columns(df: pd.DataFrame):

    required_fields = ["timestamp", "merchant", "amount", "mcc", "city", "country", "channel"]

    inferred = {}
    used_cols = set()

    # ------------------------------------------
    # 1. DIRECT NAME MATCHING (priority)
    # ------------------------------------------
    def match_by_name(df, target):
        target_lower = target.lower()
        for col in df.columns:
            col_lower = col.lower().strip().replace(" ", "")
            if col_lower == target_lower or target_lower in col_lower:
                return col
        return None

    for field in required_fields:
        col = match_by_name(df, field)
        if col:
            inferred[field] = col
            used_cols.add(col)

    # ------------------------------------------
    # 2. SMART INFERENCE HELPERS
    # ------------------------------------------
    def infer_timestamp():
        for col in df.columns:
            if col in used_cols: continue
            s = df[col].astype(str)
            if s.str.contains(r"\d{1,2}:\d{2}").mean() > 0.8:
                return col
        return None

    def infer_amount():
        for col in df.columns:
            if col in used_cols: continue
            try:
                numeric = pd.to_numeric(df[col])
                if numeric.min() >= 0 and numeric.max() < 100000:
                    return col
            except: 
                pass
        return None

    def infer_mcc():
        for col in df.columns:
            if col in used_cols: continue
            try:
                num = pd.to_numeric(df[col], errors="coerce")
                if num.dropna().astype(int).between(1000, 9999).mean() > 0.7:
                    return col
            except:
                pass
        return None

    def infer_country():
        for col in df.columns:
            if col in used_cols: continue
            s = df[col].astype(str).str.upper()
            if s.str.match(r"^[A-Z]{2}$").mean() > 0.8:
                return col
        return None

    def infer_channel():
        for col in df.columns:
            if col in used_cols: continue
            s = df[col].astype(str).str.lower()
            if s.isin(CHANNELS).mean() > 0.5:
                return col
        return None

    def infer_city():
        for col in df.columns:
            if col in used_cols: continue
            s = df[col].astype(str)

            if (
                s.str.replace(" ", "").str.isalpha().mean() > 0.9 and
                s.nunique() < len(s) * 0.5 and
                s.str.len().mean() < 20
            ):
                return col
        return None

    def infer_merchant():
        for col in df.columns:
            if col in used_cols: continue

            s = df[col].astype(str)
            unique_ratio = s.nunique() / len(s)
            alpha_ratio = s.str.replace(" ", "").str.isalpha().mean()
            multi_word_ratio = s.str.contains(r"\s").mean()
            special_char_ratio = s.str.contains(r"[^A-Za-z0-9 ]").mean()

            if (
                unique_ratio > 0.3 and
                alpha_ratio < 0.95 and
                (multi_word_ratio > 0.2 or special_char_ratio > 0.1)
            ):
                return col
        return None

    # ------------------------------------------
    # 3. RUN INFERENCE FOR MISSING FIELDS
    # ------------------------------------------
    infer_map = {
        "timestamp": infer_timestamp,
        "amount": infer_amount,
        "mcc": infer_mcc,
        "country": infer_country,
        "channel": infer_channel,
        "city": infer_city,
        "merchant": infer_merchant,
    }

    for field in required_fields:
        if field not in inferred:
            col = infer_map[field]()
            if col:
                inferred[field] = col
                used_cols.add(col)

    # ------------------------------------------
    # 4. FINAL CHECK FOR MISSING FIELDS
    # ------------------------------------------
    missing = [f for f in required_fields if f not in inferred]

    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Could not infer required columns",
                "missing_columns": missing,
                "detected_columns": inferred
            }
        )

    return inferred




def clean_uploaded_df(df: pd.DataFrame):
    """
    Clean CSV content before feature engineering or prediction.
    Raise HTTPException with descriptive error messages if invalid.
    """

    # check for null values (not last_seen which is allowed to be null)
    if df.drop(columns=["last_seen"], errors="ignore").isnull().sum().sum() > 0:
        null_counts = df.drop(columns=["last_seen"], errors="ignore").isnull().sum().to_dict()
        raise HTTPException(
            status_code=400,
            detail=f"CSV contains null values: {null_counts}"
        )


    # validate timestamp format
    try:
        pd.to_datetime(df["timestamp"])
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Column 'timestamp' is not a valid datetime format."
        )

    return True

