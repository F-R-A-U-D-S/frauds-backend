import pandas as pd
import numpy as np
import io
import joblib
import shap

from fastapi import HTTPException

from app.core.local_storage import (
    load_decrypted,
    write_encrypted_output,
    delete_key,
)

# -----------------------------------
# Load model + pipeline
# -----------------------------------
pipeline = joblib.load("models/fraud_model.pkl")
pre = pipeline.named_steps["preprocess"]
model = pipeline.named_steps["model"]


def process_local_and_predict(input_key: str):

    # Load + decrypt CSV
    data = load_decrypted(input_key)
    df = pd.read_csv(io.BytesIO(data))
    delete_key(input_key)

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Build engineered features
    # basic time features
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday
    df["month"] = df["timestamp"].dt.month

    # merchant + mcc frequency
    df["merchant_freq"] = df.groupby("merchant")["merchant"].transform("count")
    df["mcc_freq"] = df.groupby("mcc")["mcc"].transform("count")

    # Merchant novelty
    df["merchant_novelty"] = 1 / (df["merchant_freq"] + 1)

    # merchant amount profile
    merchant_avg = df.groupby("merchant")["amount"].transform("mean")
    df["merchant_avg"] = merchant_avg
    df["amount_dev"] = df["amount"] - merchant_avg

    # per-merchant Z-score
    merchant_std = df.groupby("merchant")["amount"].transform("std").replace(0, 1)
    df["z_amount_merchant"] = (df["amount"] - merchant_avg) / merchant_std

    # recency
    df["last_seen"] = df.groupby("merchant")["timestamp"].shift()
    df["days_since_merchant"] = (df["timestamp"] - df["last_seen"]).dt.days.fillna(-1)

    # channel
    df["is_online"] = (df["channel"] == "ONLINE").astype(int)

    # location risk
    city_risk_map = {
        "Toronto": 0.0,
        "Mississauga": 0.5,
        "Ottawa": 0.8,
        "Montreal": 0.8,
        "Vancouver": 1.0,
        "Calgary": 1.0,
    }
    df["location_risk"] = df["city"].map(city_risk_map).fillna(1.0)
    df["location_risk"] += np.random.normal(0, 0.05, df.shape[0])

    # odd-hour
    df["odd_hour"] = df["hour"].apply(lambda h: 1 if (h < 8 or h > 21) else 0)

    # hour deviation
    merchant_hour_avg = df.groupby("merchant")["hour"].transform("mean")
    df["hour_dev"] = abs(df["hour"] - merchant_hour_avg)

    # Feature set
    numeric_cols = [
        "amount",
        "hour",
        "weekday",
        "month",
        "merchant_freq",
        "mcc_freq",
        "merchant_avg",
        "amount_dev",
        "z_amount_merchant",
        "merchant_novelty",
        "days_since_merchant",
        "is_online",
        "location_risk",
        "odd_hour",
        "hour_dev",
    ]

    categorical_cols = ["merchant", "mcc", "city", "country"]

    X_raw = df[numeric_cols + categorical_cols].copy()

    # Transform into model feature space
    X_transformed = pre.transform(X_raw)
    if hasattr(X_transformed, "toarray"):
        X_transformed = X_transformed.toarray()

    X_transformed = X_transformed.astype(float)
    feature_names = pre.get_feature_names_out()

    # SHAP values
    explainer = shap.Explainer(model, X_transformed, algorithm="tree")
    shap_output = explainer(X_transformed)
    shap_vals_fraud = shap_output.values[:, :, 1]

    # Predictions + confidence score
    preds = pipeline.predict(X_raw)
    probs = pipeline.predict_proba(X_raw)[:, 1]

    df["prediction"] = preds
    df["fraud_confidence"] = probs.round(3)

    # Translation map
    translation_map = {
        "num__amount": "Unusual transaction amount",
        "num__amount_dev": "Amount far from typical for this merchant",
        "num__z_amount_merchant": "Amount unusually high for this merchant",
        "num__hour": "Unusual transaction time",
        "num__weekday": "Unusual day of week for spending",
        "num__month": "Out-of-pattern month",
        "num__merchant_freq": "Merchant rarely used",
        "num__mcc_freq": "Merchant category rarely used",
        "num__merchant_avg": "Amount inconsistent with user’s average at this merchant",
        "num__days_since_merchant": "Merchant not used recently",
        "num__is_online": "Unusual channel (online vs in-person)",
        "num__location_risk": "Transaction occurred in a higher-risk location",
        "num__odd_hour": "Transaction occurred outside normal active hours",
        "num__hour_dev": "Transaction time inconsistent with user’s typical pattern",
    }

    def translate_feature(name):
        if name in translation_map:
            return translation_map[name]

        if name.startswith("cat__merchant_"):
            return f"Unusual merchant ({name.replace('cat__merchant_', '')})"

        if name.startswith("cat__mcc_"):
            return f"Unusual merchant category (MCC {name.replace('cat__mcc_', '')})"

        if name.startswith("cat__city_"):
            return f"Unfamiliar city ({name.replace('cat__city_', '')})"

        if name.startswith("cat__country_"):
            return f"Unfamiliar country ({name.replace('cat__country_', '')})"

        return name

    # Build reasoning text
    reasons = [""] * len(df)

    for i in range(len(df)):
        if preds[i] == 1:
            shap_row = shap_vals_fraud[i]
            idx_sorted = np.argsort(shap_row)[::-1]

            top = []
            for j in idx_sorted:
                if shap_row[j] <= 0:
                    break
                fname = feature_names[j]
                if fname.startswith("cat__") and X_transformed[i][j] < 0.5:
                    continue
                top.append(translate_feature(fname))
                if len(top) >= 3:
                    break

            conf = df.loc[i, "fraud_confidence"]
            reasons[i] = f"{'; '.join(top)} (confidence={conf:.2f})"

    df["reasoning"] = reasons

    # Encrypt + return
    buf = io.StringIO()
    df.to_csv(buf, index=False)

    return write_encrypted_output(buf.getvalue().encode(), prefix="flagged")