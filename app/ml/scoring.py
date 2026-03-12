from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd
from fastapi import HTTPException
from sklearn.ensemble import IsolationForest
from sklearn.exceptions import NotFittedError

from app.ml.constants import (
    ANOMALY_ROBUST_Z_THRESHOLD,
    REVIEW_PRIORITY_HIGH,
    REVIEW_PRIORITY_LOW,
    RF_PERCENTILE,
    XGB_THRESHOLD,
)
from app.ml.model_loader import MODELS


def transform_features(x_raw: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    try:
        transformed = MODELS.preprocessor.transform(x_raw)
    except NotFittedError as exc:
        raise RuntimeError("Preprocessor is not fitted.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to preprocess input data.") from exc

    try:
        if hasattr(transformed, "toarray"):
            x_dense = transformed.toarray().astype(float)
        else:
            x_dense = np.asarray(transformed, dtype=float)

        feature_names = np.asarray(MODELS.preprocessor.get_feature_names_out())
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to prepare model features.") from exc

    return x_dense, feature_names


def apply_supervised_models(df: pd.DataFrame, x_raw: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    xgb_proba = MODELS.xgb_pipeline.predict_proba(x_raw)[:, 1]
    rf_proba = MODELS.rf_pipeline.predict_proba(x_raw)[:, 1]

    rf_threshold = float(np.quantile(rf_proba, RF_PERCENTILE))

    df["xgb_proba_raw"] = xgb_proba
    df["rf_proba_raw"] = rf_proba

    df["xgb_confidence"] = np.round(xgb_proba, 3)
    df["xgb_flag"] = (xgb_proba >= XGB_THRESHOLD).astype(int)

    df["rf_confidence"] = np.round(rf_proba, 3)
    df["rf_flag"] = (rf_proba >= rf_threshold).astype(int)

    return df


def apply_anomaly_detection(df: pd.DataFrame, x_dense: np.ndarray) -> pd.DataFrame:
    df = df.copy()

    try:
        iso = IsolationForest(n_estimators=300, random_state=42)
        iso.fit(x_dense)
        df["anomaly_score"] = (-iso.score_samples(x_dense)).astype(float)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Anomaly detection failed.") from exc

    median_score = float(df["anomaly_score"].median())
    mad = float((df["anomaly_score"] - median_score).abs().median())
    mad = mad if mad > 1e-9 else 1e-9

    df["anom_robust_z"] = 0.6745 * (df["anomaly_score"] - median_score) / mad
    df["anomaly_flag"] = (df["anom_robust_z"] >= ANOMALY_ROBUST_Z_THRESHOLD).astype(int)

    p05 = float(df["anomaly_score"].quantile(0.05))
    p95 = float(df["anomaly_score"].quantile(0.95))
    anomaly_norm = (df["anomaly_score"] - p05) / (p95 - p05 + 1e-9)
    df["anomaly_norm"] = anomaly_norm.clip(0.0, 1.0)

    return df


def calculate_review_priority(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    xgb_proba = df["xgb_proba_raw"].to_numpy(dtype=float)
    rf_proba = df["rf_proba_raw"].to_numpy(dtype=float)

    rf_weight = np.where(
        (xgb_proba >= REVIEW_PRIORITY_LOW) & (xgb_proba < REVIEW_PRIORITY_HIGH),
        1.0,
        0.25,
    )

    df["review_priority"] = (
        0.60 * xgb_proba +
        0.15 * df["anomaly_norm"].to_numpy(dtype=float) +
        0.10 * (rf_weight * rf_proba) +
        0.15 * df["rule_risk_score"].to_numpy(dtype=float)
    )

    return df