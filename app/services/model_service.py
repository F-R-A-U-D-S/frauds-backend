from __future__ import annotations

import io
import logging

import pandas as pd
from fastapi import HTTPException

from app.core.local_storage import delete_key, load_decrypted, write_encrypted_output
from app.ml.constants import (
    CATEGORICAL_FEATURE_COLUMNS,
    NUMERIC_FEATURE_COLUMNS,
    REQUIRED_COLUMNS,
)
from app.ml.explanations import attach_explanations
from app.ml.feature_engineering import apply_rule_logic, engineer_base_features
from app.ml.scoring import (
    apply_anomaly_detection,
    apply_supervised_models,
    calculate_review_priority,
    transform_features,
)

logger = logging.getLogger(__name__)

def process_local_and_predict(input_key: str) -> str:
    try:
        df = load_and_validate_input(input_key)
        df = engineer_base_features(df)
        df = apply_rule_logic(df)

        x_raw = df[NUMERIC_FEATURE_COLUMNS + CATEGORICAL_FEATURE_COLUMNS].copy()
        x_dense, feature_names = transform_features(x_raw)

        df = apply_supervised_models(df, x_raw)
        df = apply_anomaly_detection(df, x_dense)
        df = calculate_review_priority(df)
        df = attach_explanations(df, x_dense, feature_names)

        df = df.sort_values("review_priority", ascending=False).reset_index(drop=True)
        return write_output(df)

    except HTTPException:
        raise
    except RuntimeError:
        raise
    except Exception as exc:
        logger.exception("Unexpected failure during fraud prediction pipeline.")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while processing prediction request.",
        ) from exc


def load_and_validate_input(input_key: str) -> pd.DataFrame:
    try:
        data = load_decrypted(input_key)
    except FileNotFoundError as exc:
        logger.exception("Input file not found for key: %s", input_key)
        raise HTTPException(status_code=404, detail="Input file not found.") from exc
    except Exception as exc:
        logger.exception("Failed to load input file for key: %s", input_key)
        raise HTTPException(status_code=500, detail="Failed to load input file.") from exc

    try:
        delete_key(input_key)
    except Exception:
        logger.warning("Failed to delete input key after load: %s", input_key, exc_info=True)

    try:
        df = pd.read_csv(io.BytesIO(data))
    except Exception as exc:
        logger.exception("Could not read CSV input.")
        raise HTTPException(status_code=400, detail="Could not read CSV.") from exc

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {sorted(missing)}")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    invalid_timestamp_count = int(df["timestamp"].isna().sum())
    if invalid_timestamp_count > 0:
        logger.warning("Dropping %s rows with invalid timestamps.", invalid_timestamp_count)

    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

    if df.empty:
        raise HTTPException(
            status_code=400,
            detail="No valid rows after parsing timestamps.",
        )

    return df

def clean_numeric_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace(r"\s+", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")

def write_output(df: pd.DataFrame) -> str:
    try:
        buffer = io.StringIO()
        df.to_csv(buffer, index=False)
        return write_encrypted_output(buffer.getvalue().encode(), prefix="flagged")
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Failed to write output file.") from exc