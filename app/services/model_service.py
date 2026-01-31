import pandas as pd
import numpy as np
import io
import joblib
import shap

from sklearn.ensemble import IsolationForest
from fastapi import HTTPException

from app.core.local_storage import (
    load_decrypted,
    write_encrypted_output,
    delete_key,
)

# Load model + pipeline
# -----------------------------------
pipeline = joblib.load("models/fraud_model.pkl")
pre = pipeline.named_steps["preprocess"]
model = pipeline.named_steps["model"]


def process_local_and_predict(input_key: str):
    # Load + decrypt CSV
    data = load_decrypted(input_key)
    delete_key(input_key)

    try:
        df = pd.read_csv(io.BytesIO(data))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV.")

    # Basic validation
    needed = {"timestamp", "merchant", "mcc", "amount", "channel", "city", "country"}
    missing = needed - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    # Feature Engineering (per uploaded account)
    # =========================
    df["hour"] = df["timestamp"].dt.hour.fillna(0).astype(int)
    df["weekday"] = df["timestamp"].dt.weekday.fillna(0).astype(int)
    df["month"] = df["timestamp"].dt.month.fillna(1).astype(int)

    df["merchant_freq"] = df.groupby("merchant")["merchant"].transform("count")
    df["mcc_freq"] = df.groupby("mcc")["mcc"].transform("count")

    df["merchant_novelty"] = 1 / (df["merchant_freq"] + 1)

    merchant_avg = df.groupby("merchant")["amount"].transform("mean")
    df["merchant_avg"] = merchant_avg
    df["amount_dev"] = df["amount"] - merchant_avg

    merchant_std = (
        df.groupby("merchant")["amount"]
        .transform("std")
        .fillna(0)
        .replace(0, 1)
    )
    df["z_amount_merchant"] = (df["amount"] - merchant_avg) / merchant_std
    df["z_amount_merchant"] = (
        df["z_amount_merchant"]
        .replace([np.inf, -np.inf], 0)
        .fillna(0)
    )

    df["last_seen"] = df.groupby("merchant")["timestamp"].shift()
    df["days_since_merchant"] = (df["timestamp"] - df["last_seen"]).dt.days.fillna(-1)

    df["is_online"] = (df["channel"] == "ONLINE").astype(int)

    city_risk_map = {
        "Toronto": 0.0,
        "Mississauga": 0.5,
        "Ottawa": 0.8,
        "Montreal": 0.8,
        "Vancouver": 1.0,
        "Calgary": 1.0,
    }
    df["location_risk"] = df["city"].map(city_risk_map).fillna(1.0)
    df["location_risk"] = (df["location_risk"] + np.random.normal(0, 0.05, df.shape[0])).astype(float)

    df["odd_hour"] = df["hour"].apply(lambda h: 1 if (h < 8 or h > 21) else 0)

    merchant_hour_avg = df.groupby("merchant")["hour"].transform("mean")
    df["hour_dev"] = (df["hour"] - merchant_hour_avg).abs()

    # Per-upload novelty flags (rule reasons)
    df["new_city"] = (df.groupby("city").cumcount() == 0).astype(int)
    df["new_country"] = (df.groupby("country").cumcount() == 0).astype(int)

    # =========================
    # Model input
    # =========================
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

    # Fraud prediction
    # =========================
    probs = pipeline.predict_proba(X_raw)[:, 1]
    THRESHOLD = 0.65
    preds = (probs >= THRESHOLD).astype(int)

    df["is_fraud"] = preds
    df["fraud_confidence"] = probs.round(3)

    # Anomaly detection (per-upload baseline)
    # =========================
    iso = IsolationForest(
        n_estimators=300,
        contamination=0.02,
        random_state=42
    )
    iso.fit(X_transformed)

    normality = iso.score_samples(X_transformed)        # higher = more normal
    df["anomaly_score"] = (-normality).astype(float)    # higher = more anomalous

    pct = 0.98
    anom_threshold = df["anomaly_score"].quantile(pct)
    df["anomaly_flag"] = (df["anomaly_score"] >= anom_threshold).astype(int)

    # Review queue score
    anom = df["anomaly_score"].values
    anom_norm = (anom - anom.min()) / (anom.max() - anom.min() + 1e-9)
    df["review_priority"] = 0.7 * anom_norm + 0.3 * probs

    # SHAP explanations (RF only)
    # =========================
    explainer = shap.Explainer(model, X_transformed, algorithm="tree")
    shap_output = explainer(X_transformed)

    vals = shap_output.values
    if vals.ndim == 3:
        shap_vals_fraud = vals[:, :, 1]
    else:
        shap_vals_fraud = vals

    translation_map = {
        "num__amount": "Unusual transaction amount",
        "num__amount_dev": "Amount far from typical for this merchant",
        "num__z_amount_merchant": "Amount unusually high for this merchant",
        "num__hour": "Unusual transaction time",
        "num__weekday": "Unusual day of week for spending",
        "num__month": "Out-of-pattern month",
        "num__merchant_freq": "Merchant rarely used",
        "num__mcc_freq": "Merchant category rarely used",
        "num__merchant_avg": "Amount inconsistent with typical spending at this merchant",
        "num__days_since_merchant": "Merchant not used recently",
        "num__is_online": "Online purchase",
        "num__location_risk": "Higher-risk location",
        "num__odd_hour": "Outside normal active hours",
        "num__hour_dev": "Transaction time deviates from usual pattern",
        "num__merchant_novelty": "New or uncommon merchant",
    }

    def translate_feature(name: str) -> str:
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

    def build_reason_text(shap_row, feature_names, x_row, top_n=3):
        idx_sorted = np.argsort(shap_row)[::-1]
        reasons = []
        for j in idx_sorted:
            if shap_row[j] <= 0:
                break
            fname = feature_names[j]
            if fname.startswith("cat__") and x_row[j] < 0.5:
                continue
            reasons.append(translate_feature(fname))
            if len(reasons) >= top_n:
                break
        return "; ".join(reasons)

    # Rule-based anomaly reasons (no SHAP)
    # =========================
    P_HIGH = 0.95
    thr_z = df["z_amount_merchant"].quantile(P_HIGH)
    thr_hour = df["hour_dev"].quantile(P_HIGH)
    thr_amtdev = df["amount_dev"].abs().quantile(P_HIGH)

    days_valid = df.loc[df["days_since_merchant"] >= 0, "days_since_merchant"]
    thr_days = days_valid.quantile(P_HIGH) if len(days_valid) else np.inf

    thr_rare_freq = df["merchant_freq"].quantile(0.10)  # bottom 10%

    def anomaly_reasons_rule(row, top_n=3):
        reasons = []

        if row["z_amount_merchant"] >= thr_z:
            reasons.append("Amount unusually high for this merchant")

        if abs(row["amount_dev"]) >= thr_amtdev:
            reasons.append("Amount far from typical for this merchant")

        if row["hour_dev"] >= thr_hour:
            reasons.append("Transaction time is unusual for this merchant")

        if row["days_since_merchant"] >= 0 and row["days_since_merchant"] >= thr_days:
            reasons.append("Merchant not used recently")

        if row["merchant_freq"] <= thr_rare_freq:
            reasons.append("Rare or new merchant for this account")

        if row["new_country"] == 1:
            reasons.append("Unfamiliar country")

        if row["new_city"] == 1:
            reasons.append("Unfamiliar city")

        if row["odd_hour"] == 1:
            reasons.append("Outside normal active hours")

        if row["is_online"] == 1:
            reasons.append("Online purchase")

        return "; ".join(reasons[:top_n])

    # Attach explanations
    # =========================
    fraud_reasoning = [""] * len(df)
    anom_reasoning = [""] * len(df)

    for i in range(len(df)):
        # Fraud reasoning: only when flagged as fraud
        if df.loc[i, "is_fraud"] == 1:
            reason_text = build_reason_text(
                shap_vals_fraud[i],
                feature_names,
                X_transformed[i],
                top_n=3
            )
            if not reason_text.strip():
                reason_text = "Model flagged unusual pattern"
            conf = df.loc[i, "fraud_confidence"]
            fraud_reasoning[i] = f"{reason_text} (confidence={conf:.2f})"

        # only when anomaly_flag is checked
        if df.loc[i, "anomaly_flag"] == 1:
            reason_text = anomaly_reasons_rule(df.loc[i], top_n=3)
            if not reason_text.strip():
                reason_text = "Unusual overall behavior"
            score = df.loc[i, "anomaly_score"]
            anom_reasoning[i] = f"{reason_text} (anomaly_score={score:.3f})"

    df["reasoning"] = fraud_reasoning
    df["anomaly_reasoning"] = anom_reasoning

    # Sort output for review (highest priority first)
    df = df.sort_values("review_priority", ascending=False).reset_index(drop=True)

    # Encrypt + return
    buf = io.StringIO()
    df.to_csv(buf, index=False)

    return write_encrypted_output(buf.getvalue().encode(), prefix="flagged")