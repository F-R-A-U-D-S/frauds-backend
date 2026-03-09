from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class FeatureMatrix:
    x_raw: pd.DataFrame
    x_dense: np.ndarray
    feature_names: np.ndarray

@dataclass(frozen=True)
class LoadedModels:
    xgb_pipeline: object
    rf_pipeline: object
    preprocessor: object
    xgb_model: object