from __future__ import annotations
import logging
import joblib
from typing import Any
from pathlib import Path

from app.ml.types import LoadedModels

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = BASE_DIR / "models"


def _load_pipeline(path: Path) -> Any:
    try:
        return joblib.load(path)
    except FileNotFoundError as exc:
        logger.exception("Model file not found: %s", path)
        raise RuntimeError(f"Required model file not found: {path}") from exc
    except Exception as exc:
        logger.exception("Failed to load model file: %s", path)
        raise RuntimeError(f"Failed to load model file: {path}") from exc


def load_models() -> LoadedModels:
    xgb_pipeline = _load_pipeline(MODEL_DIR / "fraud_model_xgb.pkl")
    rf_pipeline = _load_pipeline(MODEL_DIR / "fraud_model_rf.pkl")

    try:
        preprocessor = xgb_pipeline.named_steps["preprocess"]
        xgb_model = xgb_pipeline.named_steps["model"]
    except (AttributeError, KeyError) as exc:
        logger.exception("XGBoost pipeline missing required steps.")
        raise RuntimeError("XGBoost pipeline is missing required steps.") from exc

    return LoadedModels(
        xgb_pipeline=xgb_pipeline,
        rf_pipeline=rf_pipeline,
        preprocessor=preprocessor,
        xgb_model=xgb_model,
    )

MODELS = load_models()