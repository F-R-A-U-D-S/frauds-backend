import io
import joblib
import numpy as np
import pandas as pd
import shap

from sklearn.ensemble import IsolationForest
from fastapi import HTTPException

from app.core.local_storage import (
    load_decrypted,
    write_encrypted_output,
    delete_key,
)

# Load pipelines
# =========================
xgb_pipeline = joblib.load("models/fraud_model_xgb.pkl")  # MAIN
rf_pipeline = joblib.load("models/fraud_model_rf.pkl")    # SECONDARY

pre = xgb_pipeline.named_steps["preprocess"]
xgb_model = xgb_pipeline.named_steps["model"]


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

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="No valid rows after parsing timestamps.")

    # Feature Engineering
    # =========================
    df["hour"] = df["timestamp"].dt.hour.fillna(0).astype(int)
    df["weekday"] = df["timestamp"].dt.weekday.fillna(0).astype(int)
    df["month"] = df["timestamp"].dt.month.fillna(1).astype(int)

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
    df["z_amount_merchant"] = df["z_amount_merchant"].replace([np.inf, -np.inf], 0).fillna(0)

    df["last_seen"] = df.groupby("merchant")["timestamp"].shift()
    df["days_since_merchant"] = (df["timestamp"] - df["last_seen"]).dt.days.fillna(-1)

    df["is_online"] = (df["channel"] == "ONLINE").astype(int)

    df["merchant_novelty"] = 1 / (df["merchant_freq"] + 1)

    merchant_hour_avg = df.groupby("merchant")["hour"].transform("mean")
    df["hour_dev"] = (df["hour"] - merchant_hour_avg).abs()

    # First time in city/country (per-file baseline)
    df["new_city"] = (df.groupby("city").cumcount() == 0).astype(int)
    df["new_country"] = (df.groupby("country").cumcount() == 0).astype(int)

    # New: Rule-based fraud logic (aka scenario flags)
    # =========================
    df["prev_ts"] = df["timestamp"].shift()
    df["minutes_since_prev"] = (
        (df["timestamp"] - df["prev_ts"]).dt.total_seconds() / 60
    ).fillna(1e9)

    df["prev_country"] = df["country"].shift()

    # Rolling count of transactions in last N minutes
    window_minutes = 10
    counts = []
    start = 0
    for i in range(len(df)):
        while start < i and (
            df.loc[i, "timestamp"] - df.loc[start, "timestamp"]
        ).total_seconds() > window_minutes * 60:
            start += 1
        counts.append(i - start + 1)
    df["txn_count_10m"] = counts

    # Data-driven thresholds (per-account / per-file)
    P99_amt = df["amount"].quantile(0.99)
    P95_z = df["z_amount_merchant"].quantile(0.95)
    P95_amtdev = df["amount_dev"].abs().quantile(0.95)

    days_valid = df.loc[df["days_since_merchant"] >= 0, "days_since_merchant"]
    DORMANT_DAYS = float(days_valid.quantile(0.90)) if len(days_valid) else 90.0
    DORMANT_DAYS = max(DORMANT_DAYS, 30.0)

    rare_merchant_thr = df["merchant_freq"].quantile(0.10)
    rare_mcc_thr = df["mcc_freq"].quantile(0.10)

    df["rule_geo_jump"] = (
        (df["country"] != df["prev_country"]) &
        (df["minutes_since_prev"] <= 60)
    ).astype(int)

    df["rule_new_country_high_amt"] = (
        (df["new_country"] == 1) &
        (df["amount"] >= P99_amt)
    ).astype(int)

    df["rule_dormant_spike"] = (
        (df["days_since_merchant"] >= DORMANT_DAYS) &
        (df["amount_dev"].abs() >= P95_amtdev)
    ).astype(int)

    df["rule_online_rare_spike"] = (
        (df["is_online"] == 1) &
        (df["merchant_freq"] <= rare_merchant_thr) &
        (df["z_amount_merchant"] >= P95_z)
    ).astype(int)

    df["rule_high_velocity"] = (df["txn_count_10m"] >= 3).astype(int)
    df["rule_rare_mcc"] = (df["mcc_freq"] <= rare_mcc_thr).astype(int)

    rule_weights = {
        "rule_geo_jump": 0.25,
        "rule_new_country_high_amt": 0.20,
        "rule_dormant_spike": 0.15,
        "rule_online_rare_spike": 0.15,
        "rule_high_velocity": 0.15,
        "rule_rare_mcc": 0.10,
    }

    df["rule_risk_raw"] = 0.0
    for col, w in rule_weights.items():
        df["rule_risk_raw"] += w * df[col]
    df["rule_risk_score"] = df["rule_risk_raw"].clip(0, 1)

    rule_text = {
        "rule_geo_jump": "Country changed within 60 minutes",
        "rule_new_country_high_amt": "New country + unusually high amount",
        "rule_dormant_spike": "Dormant merchant + amount spike",
        "rule_online_rare_spike": "Online + rare merchant + unusually high amount",
        "rule_high_velocity": "High velocity (3+ txns in 10 minutes)",
        "rule_rare_mcc": "Rare merchant category (MCC) for this account",
    }

    def build_rule_reasoning(row, top_n=3):
        triggered = [rule_text[k] for k in rule_weights.keys() if row.get(k, 0) == 1]
        return "; ".join(triggered[:top_n]) if triggered else ""

    df["rule_reasoning"] = df.apply(build_rule_reasoning, axis=1)

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
        "days_since_merchant",
        "is_online",
        "merchant_novelty",
        "hour_dev",
    ]
    categorical_cols = ["merchant", "mcc", "city", "country"]
    X_raw = df[numeric_cols + categorical_cols].copy()

    # Transform (for anomaly and SHAP)
    X_transformed = pre.transform(X_raw)
    if hasattr(X_transformed, "toarray"):
        X_dense = X_transformed.toarray().astype(float)
    else:
        X_dense = np.asarray(X_transformed, dtype=float)

    feature_names = pre.get_feature_names_out()

    # Main model: XGBoost fraud probability
    # =========================
    xgb_proba = xgb_pipeline.predict_proba(X_raw)[:, 1]
    df["xgb_confidence"] = np.round(xgb_proba, 3)

    XGB_THRESHOLD = 0.65
    df["xgb_flag"] = (xgb_proba >= XGB_THRESHOLD).astype(int)

    # Secondary model: RandomForest probability
    # =========================
    rf_proba = rf_pipeline.predict_proba(X_raw)[:, 1]
    df["rf_confidence"] = np.round(rf_proba, 3)

    RF_PCT = 0.95
    rf_thr = float(np.quantile(rf_proba, RF_PCT))
    df["rf_flag"] = (rf_proba >= rf_thr).astype(int)

    # Anomaly detection (using robust z threshold)
    # Previous implementation used n%
    # =========================
    iso = IsolationForest(n_estimators=300, random_state=42)
    iso.fit(X_dense)

    df["anomaly_score"] = (-iso.score_samples(X_dense)).astype(float)

    med = float(df["anomaly_score"].median())
    mad = float((df["anomaly_score"] - med).abs().median())
    mad = mad if mad > 1e-9 else 1e-9

    df["anom_robust_z"] = 0.6745 * (df["anomaly_score"] - med) / mad
    K = 3.5
    df["anomaly_flag"] = (df["anom_robust_z"] >= K).astype(int)

    # Normalize anomaly to 0..1 using p05..p95
    p05 = float(df["anomaly_score"].quantile(0.05))
    p95 = float(df["anomaly_score"].quantile(0.95))
    anom_norm = (df["anomaly_score"] - p05) / (p95 - p05 + 1e-9)
    df["anomaly_norm"] = anom_norm.clip(0, 1)

    # Combined review priority
    # =========================
    LOW, HIGH = 0.45, 0.65
    rf_weight = np.where((xgb_proba >= LOW) & (xgb_proba < HIGH), 1.0, 0.25)

    df["review_priority"] = (
        0.60 * xgb_proba +
        0.15 * df["anomaly_norm"].values +
        0.10 * (rf_weight * rf_proba) +
        0.15 * df["rule_risk_score"].values
    )

    # SHAP explanations (XGBoost is MAIN)
    # Only attaches when xgb_flag == 1
    # =========================
    explainer = shap.Explainer(xgb_model, X_dense, algorithm="tree")
    shap_output = explainer(X_dense)

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
        "num__merchant_freq": "Merchant rarely used",
        "num__mcc_freq": "Merchant category rarely used",
        "num__merchant_avg": "Amount inconsistent with typical spending at this merchant",
        "num__days_since_merchant": "Merchant not used recently",
        "num__is_online": "Online purchase",
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

    def build_reason_text(shap_row, feature_names_arr, x_row, top_n=3):
        idx_sorted = np.argsort(shap_row)[::-1]
        reasons = []
        for j in idx_sorted:
            if shap_row[j] <= 0:
                break
            fname = feature_names_arr[j]
            if fname.startswith("cat__") and x_row[j] < 0.5:
                continue
            reasons.append(translate_feature(fname))
            if len(reasons) >= top_n:
                break
        return "; ".join(reasons)

    # Rule-based anomaly reasons
    # =========================
    P_HIGH = 0.95
    thr_z = float(df["z_amount_merchant"].quantile(P_HIGH))
    thr_hour = float(df["hour_dev"].quantile(P_HIGH))
    thr_amtdev = float(df["amount_dev"].abs().quantile(P_HIGH))

    days_valid2 = df.loc[df["days_since_merchant"] >= 0, "days_since_merchant"]
    thr_days = float(days_valid2.quantile(P_HIGH)) if len(days_valid2) else np.inf

    thr_rare_freq = float(df["merchant_freq"].quantile(0.10))

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
        if row["is_online"] == 1:
            reasons.append("Online purchase")

        return "; ".join(reasons[:top_n])

    # Attach explanations
    # =========================
    xgb_reasoning = [""] * len(df)
    anom_reasoning = [""] * len(df)
    rf_reasoning = [""] * len(df)

    for i in range(len(df)):
        if df.loc[i, "xgb_flag"] == 1:
            reason_text = build_reason_text(
                shap_vals_fraud[i],
                feature_names,
                X_dense[i],
                top_n=3,
            )
            if reason_text.strip() == "":
                reason_text = "Model flagged unusual pattern"
            xgb_reasoning[i] = f"{reason_text} (xgb={df.loc[i, 'xgb_confidence']:.2f})"

        if df.loc[i, "anomaly_flag"] == 1:
            reason_text = anomaly_reasons_rule(df.loc[i], top_n=3)
            if reason_text.strip() == "":
                reason_text = "Unusual overall behavior"
            anom_reasoning[i] = f"{reason_text} (anom={df.loc[i, 'anomaly_score']:.3f})"

        if df.loc[i, "rf_flag"] == 1:
            rf_reasoning[i] = (
                f"RF also flagged (rf={df.loc[i, 'rf_confidence']:.2f}; "
                f"top={int((1 - RF_PCT) * 100)}%)"
            )

    df["reasoning"] = xgb_reasoning
    df["anomaly_reasoning"] = anom_reasoning
    df["rf_reasoning"] = rf_reasoning
    # df["rule_reasoning"] already exists
    # df["rule_risk_score"] already exists

    # Sort output for review by review priority
    # =========================
    df = df.sort_values("review_priority", ascending=False).reset_index(drop=True)

    # Encrypt + return
    # =========================
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    return write_encrypted_output(buf.getvalue().encode(), prefix="flagged")