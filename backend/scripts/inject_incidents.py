"""
Phase 10 — runner: builds the controlled incident test dataset.

Run:
    python -m scripts.inject_incidents
"""
from __future__ import annotations

import pandas as pd

from app.config import settings
from app.services.incident_simulation import build_incident_test_dataset


def main() -> None:
    transactions = pd.read_csv(
        settings.PROCESSED_DATA_DIR / "transactions.csv", parse_dates=["timestamp"]
    )
    incident_tx, ground_truth = build_incident_test_dataset(transactions)

    out_tx = settings.PROCESSED_DATA_DIR / "incident_transactions.csv"
    out_gt = settings.PROCESSED_DATA_DIR / "ground_truth_incidents.csv"

    incident_tx.to_csv(out_tx, index=False)
    ground_truth.to_csv(out_gt, index=False)

    print(f"Wrote {len(incident_tx):,} transactions ({len(transactions) - len(incident_tx)} "
          f"fewer than clean set, due to Scenario D volume drop) to {out_tx}")
    print(f"Wrote {len(ground_truth)} ground-truth incidents to {out_gt}")
    print(ground_truth.to_string(index=False))


if __name__ == "__main__":
    main()
