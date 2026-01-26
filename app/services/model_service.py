import pandas as pd
import numpy as np
import io
import joblib
import shap

from sklearn.ensemble import IsolationForest, RandomForestRegressor

from fastapi import HTTPException

from app.core.local_storage import (
    load_decrypted,
    write_encrypted_output,
    delete_key,
)

# Load model + pipeline (once at import)
# -----------------------------------
pipeline = joblib.load("models/fraud_model.pkl")
pre = pipeline.named_steps["preprocess"]
model = pipeline.named_steps["model"]

THRESHOLD = 0.65
ANOM_CONTAMINATION = 0.02
ANOM_FLAG_QUANTILE = 0.98


def process_local_and_predict(input_key: str):
    # Load + decrypt CSV
    data = load_decrypted(input_key)
    delete_key(input_key)

    try:
        df = pd.read_csv(io.BytesIO(data))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV.")

    # Validate required columns (keep it simple)
    required = {"timestamp", "merchant", "amount", "mcc", "city", "country", "channel"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {sorted(missing)}")

    # Parse + sort
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["timestamp"].isna().any():
        raise HTTPException(status_code=400, detail="Invalid timestamp values found.")

    df = df.sort_values("timestamp").reset_index(drop=True)

    # -----------------------------------
    # Feature Engineering (per upload = single account baseline)
    # -----------------------------------
    df["hour"] = df["timestamp"].dt.hour
    df["weekday"] = df["timestamp"].dt.weekday
    df["month"] = df["timestamp"].dt.month

    df["merchant_freq"] = df.groupby("merchant")["merchant"].transform("count")
    df["mcc_freq"] = df.groupby("mcc")["mcc"].transform("count")

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

    df["merchant_novelty"] = 1 / (df["merchant_freq"] + 1)

    merchant_hour_avg = df.groupby("merchant")["hour"].transform("mean")
    df["hour_dev"] = (df["hour"] - merchant_hour_avg).abs()

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
        "days_since_merchant",
        "is_online",
        "merchant_novelty",
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

    # Fraud prediction (RF)
    # -----------------------------------
    probs = pipeline.predict_proba(X_raw)[:, 1]
    preds = (probs >= THRESHOLD).astype(int)

    df["fraud_confidence"] = probs.round(3)
    df["is_fraud"] = preds

    # New: Anomaly detection (IsolationForest)
    # -----------------------------------
    iso = IsolationForest(
        n_estimators=300,
        contamination=ANOM_CONTAMINATION,
        random_state=42,
    )
    iso.fit(X_transformed)

    normality = iso.score_samples(X_transformed)      # higher = more normal
    df["anomaly_score"] = (-normality).astype(float)  # higher = more anomalous

    anom_threshold = df["anomaly_score"].quantile(ANOM_FLAG_QUANTILE)
    df["anomaly_flag"] = (df["anomaly_score"] >= anom_threshold).astype(int)

    # Review priority combines both signals
    anom = df["anomaly_score"].values
    anom_norm = (anom - anom.min()) / (anom.max() - anom.min() + 1e-9)
    df["review_priority"] = 0.7 * anom_norm + 0.3 * probs

    # SHAP: fraud explanations
    # -----------------------------------
    explainer = shap.Explainer(model, X_transformed, algorithm="tree")
    shap_output = explainer(X_transformed)
    shap_vals_fraud = shap_output.values[:, :, 1]  # class 1

    # SHAP: anomaly explanations via surrogate
    # -----------------------------------
    surrogate = RandomForestRegressor(
        n_estimators=400,
        random_state=42,
        n_jobs=-1,
    )
    surrogate.fit(X_transformed, df["anomaly_score"].values)

    sur_explainer = shap.Explainer(surrogate, X_transformed, algorithm="tree")
    sur_shap = sur_explainer(X_transformed)
    shap_vals_anom = sur_shap.values  # (rows, features)

    # Human-readable explanations
    # -----------------------------------
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
        "num__is_online": "Unusual purchase channel",
        "num__merchant_novelty": "New or uncommon merchant",
        "num__hour_dev": "Transaction time deviates from usual pattern",
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

    def build_reason_text(shap_row, x_row, top_n=3):
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

    fraud_reasoning = [""] * len(df)
    anom_reasoning = [""] * len(df)

    for i in range(len(df)):
        if preds[i] == 1:
            txt = build_reason_text(shap_vals_fraud[i], X_transformed[i], top_n=3)
            fraud_reasoning[i] = f"{txt} (confidence={df.loc[i, 'fraud_confidence']:.2f})"

        if df.loc[i, "anomaly_flag"] == 1:
            txt = build_reason_text(shap_vals_anom[i], X_transformed[i], top_n=3)
            anom_reasoning[i] = f"{txt} (anomaly_score={df.loc[i, 'anomaly_score']:.3f})"

    df["reasoning"] = fraud_reasoning
    df["anomaly_reasoning"] = anom_reasoning

    # Sort for review (highest priority first)
    df = df.sort_values("review_priority", ascending=False).reset_index(drop=True)

    # Encrypt + return
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return write_encrypted_output(buf.getvalue().encode(), prefix="flagged")

# TODO: Limit explanations to top-N features per row
# TODO: Analyze use of anomaly SHAP unless we really need it
# TODO: Hyperparameter tuning on SHAP surrogate for anomaly detection