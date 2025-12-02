import pandas as pd
import io
import os
import re
import joblib
from fastapi import HTTPException
from app.services.data_service import clean_uploaded_df

from app.core.local_storage import (
    load_decrypted,
    write_encrypted_output,
    delete_key,
)

model = joblib.load("models/fraud_model.pkl")

def process_local_and_predict(input_key: str):

    print(f"[DEBUG] process_local_and_predict received: {input_key}")

    

    # decrypt uploaded CSV into memory
    data = load_decrypted(input_key)
    print(f"[DEBUG] Decryption successful, loading CSV into DataFrame")
    print(f"[DEBUG] Data size (bytes): {len(data)}")

    df = pd.read_csv(io.BytesIO(data))
    print(f"[DEBUG] CSV loaded into DataFrame with shape: {df.shape}")

    # delete encrypted uploaded file immediately
    delete_key(input_key)
    print(f"[DEBUG] Deleted input encrypted file and key: {input_key}")

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
    print(f"[DEBUG] Prediction complete, output stored with key: {output_key}")
    return output_key
