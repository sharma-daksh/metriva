"""
Builds the data the API serves for Demo Mode.

Uses incident_transactions.csv (Phase 10's controlled scenarios), not the
plain clean transactions.csv — Section 3 requires Demo Mode to let the user
"inspect anomalies... incidents... root causes... revenue at risk", which
only means something if the served data actually contains findable
incidents. The clean dataset remains at data/processed/transactions.csv
untouched, for anyone who wants a from-scratch example without injected
scenarios; this script's output is what the dashboard/API actually reads.

Run:
    python -m scripts.compute_incidents

Output (overwrites):
    backend/data/processed/daily_metrics.csv
    backend/data/processed/merchant_metrics.csv
Output (new):
    backend/data/processed/anomalies.csv
    backend/data/processed/incidents.csv
"""
from __future__ import annotations

import pandas as pd

from app.config import settings
from app.services.metrics import compute_daily_merchant_metrics, compute_merchant_summary
from app.services.anomaly_detection import detect_anomalies_all_merchants
from app.services.incident_engine import build_incidents_all_merchants


def main() -> None:
    tx_path = settings.PROCESSED_DATA_DIR / "incident_transactions.csv"
    if not tx_path.exists():
        raise SystemExit(
            f"{tx_path} not found — run `python -m scripts.inject_incidents` first."
        )

    transactions = pd.read_csv(tx_path, parse_dates=["timestamp"])

    daily_metrics = compute_daily_merchant_metrics(transactions)
    merchant_metrics = compute_merchant_summary(transactions)

    daily_metrics.to_csv(settings.PROCESSED_DATA_DIR / "daily_metrics.csv", index=False)
    merchant_metrics.to_csv(settings.PROCESSED_DATA_DIR / "merchant_metrics.csv", index=False)

    daily_metrics["date"] = pd.to_datetime(daily_metrics["date"]).dt.date
    anomalies = detect_anomalies_all_merchants(daily_metrics)
    incidents = build_incidents_all_merchants(anomalies, daily_metrics)

    anomalies_path = settings.PROCESSED_DATA_DIR / "anomalies.csv"
    incidents_path = settings.PROCESSED_DATA_DIR / "incidents.csv"
    anomalies.to_csv(anomalies_path, index=False)
    incidents.to_csv(incidents_path, index=False)

    print(f"Recomputed daily_metrics.csv and merchant_metrics.csv from the incident-injected dataset")
    print(f"Wrote {len(anomalies)} anomaly points to {anomalies_path}")
    print(f"Wrote {len(incidents)} incidents to {incidents_path}")
    if not incidents.empty:
        print(incidents["severity"].value_counts().to_string())
        print(incidents["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
