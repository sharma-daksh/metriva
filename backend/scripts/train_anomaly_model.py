"""
Phase 16 — Trains the SHAP-explained anomaly classifier and writes the
artifacts app/api/routes/incidents.py's /explanation endpoint reads.

Trains on the demo dataset's daily_metrics.csv + anomalies.csv (Phase 6/8
output), not the active-dataset pointer — this model ships with the demo
and is a secondary, model-based signal alongside the statistical root
cause panel (Phase 12), not something recomputed per uploaded dataset.

Run:
    python -m scripts.train_anomaly_model

Requires data/processed/daily_metrics.csv and anomalies.csv to already
exist (run `python -m scripts.compute_incidents` first if they don't).

Output:
    backend/data/processed/model_features.csv
    backend/data/models/anomaly_classifier.joblib
"""
from __future__ import annotations

import joblib
import pandas as pd

from app.config import settings
from app.ml.features import build_features, attach_labels
from app.ml.models import train_anomaly_classifier


def main() -> None:
    daily_metrics_path = settings.PROCESSED_DATA_DIR / "daily_metrics.csv"
    anomalies_path = settings.PROCESSED_DATA_DIR / "anomalies.csv"

    if not daily_metrics_path.exists() or not anomalies_path.exists():
        raise SystemExit(
            f"{daily_metrics_path} and/or {anomalies_path} not found — "
            "run `python -m scripts.compute_incidents` first."
        )

    daily_metrics = pd.read_csv(daily_metrics_path, parse_dates=["date"])
    anomalies = pd.read_csv(anomalies_path, parse_dates=["date"])

    features = build_features(daily_metrics)
    labeled = attach_labels(features, anomalies)

    trained = train_anomaly_classifier(labeled)

    model_features_path = settings.PROCESSED_DATA_DIR / "model_features.csv"
    labeled.to_csv(model_features_path, index=False)

    models_dir = settings.BASE_DIR / "data" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    model_path = models_dir / "anomaly_classifier.joblib"
    joblib.dump(
        {"model": trained.model, "feature_columns": trained.feature_columns},
        model_path,
    )

    print(f"Trained on {len(labeled)} feature rows ({int(labeled['is_anomaly'].sum())} positive).")
    print(f"Metrics: {trained.metrics}")
    print(f"Wrote {model_features_path}")
    print(f"Wrote {model_path}")


if __name__ == "__main__":
    main()