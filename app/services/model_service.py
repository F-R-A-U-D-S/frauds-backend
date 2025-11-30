import pandas as pd
import io
import os
import joblib
from fastapi import HTTPException

from app.core.local_storage import (
    load_decrypted,
    write_encrypted_output,
    delete_key,
)

model = joblib.load("models/fraud_model.pkl")

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


def validate_uploaded_df(df: pd.DataFrame):
    """
    Validate CSV integrity before feature engineering or prediction.
    Raise HTTPException with descriptive error messages if invalid.
    """

    # required columns
    required_cols = [
        "timestamp", "merchant", "amount", "mcc",
        "city", "country", "channel"
    ]

    # check for missing columns
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {missing}"
        )

    # check if empty file
    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="CSV is empty."
        )

    # check for null values (not last_seen which is allowed to be null)
    if df.drop(columns=["last_seen"], errors="ignore").isnull().sum().sum() > 0:
        null_counts = df.drop(columns=["last_seen"], errors="ignore").isnull().sum().to_dict()
        raise HTTPException(
            status_code=400,
            detail=f"CSV contains null values: {null_counts}"
        )

    # validate numeric types
    numeric_cols = ["amount", "mcc"]
    for col in numeric_cols:
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise HTTPException(
                status_code=400,
                detail=f"Column '{col}' contains non-numeric values."
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


def process_local_and_predict(input_key: str):
    # decrypt uploaded CSV into memory
    data = load_decrypted(input_key)
    df = pd.read_csv(io.BytesIO(data))

    # delete encrypted uploaded file immediately
    delete_key(input_key)

    # VALIDATE
    validate_uploaded_df(df)

    # safe conversion
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # FEATURE ENGINEERING
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday
    df["month"] = df["timestamp"].dt.month

    df["merchant_freq"] = df.groupby("merchant")["merchant"].transform("count")
    df["mcc_freq"] = df.groupby("mcc")["mcc"].transform("count")

    df = df.sort_values("timestamp")
    df["last_seen"] = df.groupby("merchant")["timestamp"].shift()
    df["days_since_merchant"] = (
        df["timestamp"] - df["last_seen"]
    ).dt.days.fillna(-1)

    df["is_online"] = (df["channel"] == "ONLINE").astype(int)

    merchant_avg = df.groupby("merchant")["amount"].transform("mean")
    df["merchant_avg"] = merchant_avg
    df["amount_dev"] = df["amount"] - merchant_avg

    numeric_cols = [
        "amount", "hour", "weekday", "month",
        "merchant_freq", "mcc_freq", "merchant_avg",
        "amount_dev", "days_since_merchant", "is_online"
    ]

    categorical_cols = ["merchant", "mcc", "city", "country"]

    X = df[numeric_cols + categorical_cols]

    # prediction
    df["fraud_prediction"] = model.predict(X)

    # write output as encrypted file
    out_buf = io.StringIO()
    df.to_csv(out_buf, index=False)
    out_bytes = out_buf.getvalue().encode()

    output_key = write_encrypted_output(out_bytes, prefix="flagged")
    return output_key
