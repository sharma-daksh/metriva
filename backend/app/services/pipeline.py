"""
Orchestrates Phases 2-7 for Demo Mode and writes the processed output files
listed in Section 63 (transactions.csv, merchants.csv, merchant_metrics.csv,
daily_metrics.csv). Run this whenever the raw dataset changes.

Usage:
    python -m app.services.pipeline
"""
from __future__ import annotations

from app.config import settings
from app.services.data_generation import ensure_raw_dataset_exists
from app.services.ingestion import ingest_csv
from app.services.normalization import map_demo_dataset_to_canonical, validate_canonical
from app.services.metrics import compute_daily_merchant_metrics, compute_merchant_summary


def run_demo_pipeline() -> dict:
    raw_path = ensure_raw_dataset_exists()
    ingestion_result = ingest_csv(raw_path)
    if not ingestion_result.ok:
        raise RuntimeError(f"Raw dataset failed ingestion checks: {ingestion_result.errors}")

    canonical = map_demo_dataset_to_canonical(ingestion_result.dataframe)
    clean, dropped, quality_report = validate_canonical(canonical)

    daily_metrics = compute_daily_merchant_metrics(clean)
    merchant_summary = compute_merchant_summary(clean)

    settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(settings.PROCESSED_DATA_DIR / "transactions.csv", index=False)
    merchant_summary.to_csv(settings.PROCESSED_DATA_DIR / "merchants.csv", index=False)
    daily_metrics.to_csv(settings.PROCESSED_DATA_DIR / "daily_metrics.csv", index=False)
    merchant_summary.to_csv(settings.PROCESSED_DATA_DIR / "merchant_metrics.csv", index=False)

    if not dropped.empty:
        dropped.to_csv(settings.PROCESSED_DATA_DIR / "dropped_rows.csv", index=False)

    return {
        "raw_path": raw_path,
        "quality_report": quality_report,
        "n_transactions": len(clean),
        "n_merchants": merchant_summary.shape[0],
        "n_dropped": len(dropped),
    }


if __name__ == "__main__":
    result = run_demo_pipeline()
    print("Demo pipeline complete:")
    for k, v in result.items():
        print(f"  {k}: {v}")
