"""
Phase 16 — Model training (Section 14/16).

Trains a gradient-boosted classifier to predict Phase 8's is_anomaly label
from the Phase 16 engineered features. Evaluated with a proper train/test
split and reported honestly (Section 16: "Do NOT report accuracy if the
evaluation setup makes accuracy misleading" — this is a heavily imbalanced
label, so accuracy alone would be misleading; precision/recall/F1/PR-AUC
are reported instead).

This model's SHAP values (Phase 16's explainability target) are a SECOND,
complementary root-cause signal alongside Phase 12's statistical dimension
comparison — not a replacement for it. Phase 17's evaluator checks whether
the SHAP explanations this model produces actually reflect its real
behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score

from app.ml.features import FEATURE_COLUMNS

MODEL_SEED = 42


@dataclass
class TrainedModel:
    model: GradientBoostingClassifier
    feature_columns: list
    metrics: dict


def train_anomaly_classifier(
    features: pd.DataFrame, label_col: str = "is_anomaly", test_size: float = 0.25
) -> TrainedModel:
    X = features[FEATURE_COLUMNS]
    y = features[label_col].astype(int)

    if y.sum() < 5:
        raise ValueError(
            f"Only {y.sum()} positive (anomalous) examples available — too few to "
            "train and evaluate honestly. Not fabricating a model on insufficient data."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=MODEL_SEED, stratify=y
    )

    model = GradientBoostingClassifier(
        n_estimators=150, max_depth=3, learning_rate=0.1, random_state=MODEL_SEED
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "test_set_size": len(y_test),
        "test_set_positives": int(y_test.sum()),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_test, y_proba)),
    }

    return TrainedModel(model=model, feature_columns=FEATURE_COLUMNS, metrics=metrics)