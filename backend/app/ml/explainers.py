"""
Phase 16 — SHAP explainability for the anomaly classifier.

Wraps `shap.TreeExplainer` so the rest of the app only deals with a small,
serializable `Explanation` object instead of raw SHAP arrays (whose shape
varies by sklearn/shap version and model type).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import shap

from app.ml.features import FEATURE_DISPLAY_NAMES
from app.ml.models import TrainedModel


@dataclass
class Explanation:
    predicted_probability: float
    contributions: list[dict]  # [{feature, display_name, value, shap_value}, ...]


def build_explainer(trained: TrainedModel):
    return shap.TreeExplainer(trained.model)


def _positive_class_shap_row(shap_values, row_idx: int = 0) -> np.ndarray:
    """
    Normalizes across shap/sklearn version differences:
      - list of arrays (one per class) -> take the positive class (index 1)
      - 3D array (n_samples, n_features, n_classes) -> take [..., 1]
      - 2D array (n_samples, n_features) -> already single-output
    """
    if isinstance(shap_values, list):
        values = shap_values[1] if len(shap_values) > 1 else shap_values[0]
        return np.asarray(values)[row_idx]
    values = np.asarray(shap_values)
    if values.ndim == 3:
        return values[row_idx, :, 1]
    return values[row_idx]


def explain_instance(trained: TrainedModel, explainer, row: pd.Series, top_n: int = 6) -> Explanation:
    """
    trained: the fitted TrainedModel (model + feature_columns).
    explainer: from build_explainer(trained).
    row: a single row (pd.Series) containing at least trained.feature_columns,
         e.g. one row of model_features.csv for a specific merchant/date.
    """
    X = row[trained.feature_columns].to_frame().T.astype(float)

    predicted_probability = float(trained.model.predict_proba(X)[:, 1][0])
    shap_row = _positive_class_shap_row(explainer.shap_values(X))

    contributions = [
        {
            "feature": feature,
            "display_name": FEATURE_DISPLAY_NAMES.get(feature, feature),
            "value": float(X.iloc[0][feature]),
            "shap_value": float(shap_value),
        }
        for feature, shap_value in zip(trained.feature_columns, shap_row)
    ]
    contributions.sort(key=lambda c: abs(c["shap_value"]), reverse=True)

    return Explanation(
        predicted_probability=predicted_probability,
        contributions=contributions[:top_n],
    )