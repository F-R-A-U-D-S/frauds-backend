from __future__ import annotations

from typing import Dict

import numpy as np
import pandas as pd
import shap

from app.ml.constants import RF_PERCENTILE, TRANSLATION_MAP
from app.ml.model_loader import MODELS


def attach_explanations(
    df: pd.DataFrame,
    x_dense: np.ndarray,
    feature_names: np.ndarray,
) -> pd.DataFrame:
    df = df.copy()

    try:
        explainer = shap.Explainer(MODELS.xgb_model, x_dense, algorithm="tree")
        shap_output = explainer(x_dense)
    except Exception:
        df["reasoning"] = [""] * len(df)
        df["anomaly_reasoning"] = [""] * len(df)
        df["rf_reasoning"] = [""] * len(df)
        return df

    shap_values = shap_output.values
    if shap_values.ndim == 3:
        shap_values_fraud = shap_values[:, :, 1]
    else:
        shap_values_fraud = shap_values

    anomaly_thresholds = compute_anomaly_reason_thresholds(df)

    xgb_reasoning: list[str] = [""] * len(df)
    anomaly_reasoning: list[str] = [""] * len(df)
    rf_reasoning: list[str] = [""] * len(df)

    for i in range(len(df)):
        if int(df.loc[i, "xgb_flag"]) == 1:
            reason_text = build_shap_reason_text(
                shap_row=np.asarray(shap_values_fraud[i], dtype=float),
                feature_names=feature_names,
                x_row=np.asarray(x_dense[i], dtype=float),
                top_n=3,
            )
            xgb_reasoning[i] = reason_text or "Model flagged unusual pattern"

        if int(df.loc[i, "anomaly_flag"]) == 1:
            reason_text = build_anomaly_reason_text(df.loc[i], anomaly_thresholds, top_n=3)
            anomaly_reasoning[i] = reason_text or "Unusual overall behavior"

        if int(df.loc[i, "rf_flag"]) == 1:
            rf_reasoning[i] = (
                f"RF also flagged (rf={df.loc[i, 'rf_confidence']:.2f}; "
                f"top={int((1 - RF_PERCENTILE) * 100)}%)"
            )

    df["reasoning"] = xgb_reasoning
    df["anomaly_reasoning"] = anomaly_reasoning
    df["rf_reasoning"] = rf_reasoning

    return df


def compute_anomaly_reason_thresholds(df: pd.DataFrame) -> dict[str, float]:
    p_high = 0.95
    days_valid = df.loc[df["days_since_merchant"] >= 0, "days_since_merchant"]
    days_threshold = float(days_valid.quantile(p_high)) if not days_valid.empty else float("inf")

    return {
        "z_amount_merchant": float(df["z_amount_merchant"].quantile(p_high)),
        "hour_dev": float(df["hour_dev"].quantile(p_high)),
        "amount_dev_abs": float(df["amount_dev"].abs().quantile(p_high)),
        "days_since_merchant": days_threshold,
        "merchant_freq_rare": float(df["merchant_freq"].quantile(0.10)),
    }


def translate_feature(name: str) -> str:
    if name in TRANSLATION_MAP:
        return TRANSLATION_MAP[name]
    if name.startswith("cat__merchant_"):
        return f"Unusual merchant ({name.replace('cat__merchant_', '')})"
    if name.startswith("cat__mcc_"):
        return f"Unusual merchant category (MCC {name.replace('cat__mcc_', '')})"
    if name.startswith("cat__city_"):
        return f"Unfamiliar city ({name.replace('cat__city_', '')})"
    if name.startswith("cat__country_"):
        return f"Unfamiliar country ({name.replace('cat__country_', '')})"
    return name


def build_shap_reason_text(
    shap_row: np.ndarray,
    feature_names: np.ndarray,
    x_row: np.ndarray,
    top_n: int = 3,
) -> str:
    sorted_indices = np.argsort(shap_row)[::-1]
    reasons: list[str] = []

    for idx in sorted_indices:
        if float(shap_row[idx]) <= 0:
            break

        feature_name = str(feature_names[idx])

        if feature_name.startswith("cat__") and float(x_row[idx]) < 0.5:
            continue

        reasons.append(translate_feature(feature_name))

        if len(reasons) >= top_n:
            break

    return "; ".join(reasons)


def build_anomaly_reason_text(
    row: pd.Series,
    thresholds: Dict[str, float],
    top_n: int = 3,
) -> str:
    reasons: list[str] = []

    if float(row["z_amount_merchant"]) >= thresholds["z_amount_merchant"]:
        reasons.append("Amount unusually high for this merchant")
    if abs(float(row["amount_dev"])) >= thresholds["amount_dev_abs"]:
        reasons.append("Amount far from typical for this merchant")
    if float(row["hour_dev"]) >= thresholds["hour_dev"]:
        reasons.append("Transaction time is unusual for this merchant")
    if (
        float(row["days_since_merchant"]) >= 0
        and float(row["days_since_merchant"]) >= thresholds["days_since_merchant"]
    ):
        reasons.append("Merchant not used recently")
    if float(row["merchant_freq"]) <= thresholds["merchant_freq_rare"]:
        reasons.append("Rare or new merchant for this account")
    if int(row["new_country"]) == 1:
        reasons.append("Unfamiliar country")
    if int(row["new_city"]) == 1:
        reasons.append("Unfamiliar city")
    if int(row["is_online"]) == 1:
        reasons.append("Online purchase")

    return "; ".join(reasons[:top_n])