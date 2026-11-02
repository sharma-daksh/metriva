"""
Phase 20 — CSV upload routes.

Two-step flow matching Section 39's UX:
  1. POST /upload/preview  — structural check + suggested column mapping +
     a data preview. Nothing is saved yet.
  2. POST /upload/commit   — re-sends the file with a (possibly
     user-edited) mapping. Applies it, validates, and — if there's at
     least one valid row — recomputes the ENTIRE analytics pipeline
     (metrics -> anomaly detection -> incidents) on the uploaded data and
     makes it the active dataset (Section 2: same pipeline as Demo Mode).

Also:
  GET  /upload/status         — which dataset is currently active
  POST /upload/reset-to-demo  — switch back to the built-in demo dataset

SCOPE NOTE: this is a single, global active dataset (see repositories.py's
docstring) — there's no per-user session here, so uploading replaces what
EVERY visitor sees. Fine for a single-demo-at-a-time setting, not for real
multi-tenant use.

LIMITS (Section 54): file type and size are checked before anything else
touches the upload.
"""
from __future__ import annotations

import io
import json
import math

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import settings
from app.services.column_mapping import suggest_mapping
from app.services.upload import apply_mapping, check_mapping_sufficient
from app.services.normalization import validate_canonical
from app.services.metrics import compute_daily_merchant_metrics, compute_merchant_summary
from app.services.anomaly_detection import detect_anomalies_all_merchants
from app.services.incident_engine import build_incidents_all_merchants
from app.storage.repositories import get_active_dataset, set_active_dataset

router = APIRouter(prefix="/upload", tags=["upload"])

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB
MAX_ROWS = 200_000  # keeps synchronous anomaly detection (~seconds per 1000 merchant-days) tractable


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


async def _read_csv_upload(file: UploadFile) -> pd.DataFrame:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds the {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB limit.",
        )

    try:
        df = pd.read_csv(io.BytesIO(contents))
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="File has no parseable rows.")
    except pd.errors.ParserError as exc:
        raise HTTPException(status_code=400, detail=f"Malformed CSV: {exc}")

    if df.empty:
        raise HTTPException(status_code=400, detail="File parsed but contains zero data rows.")
    if len(df) > MAX_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"File has {len(df):,} rows, which exceeds the {MAX_ROWS:,}-row limit for this demo.",
        )

    duplicate_cols = df.columns[df.columns.duplicated()].tolist()
    if duplicate_cols:
        raise HTTPException(status_code=400, detail=f"Duplicate column names: {duplicate_cols}")

    return df


@router.post("/preview")
async def preview_upload(file: UploadFile = File(...)):
    df = await _read_csv_upload(file)
    mapping = suggest_mapping(list(df.columns))
    missing_required = check_mapping_sufficient(mapping)

    preview_df = df.head(5).where(pd.notna(df.head(5)), None)

    return {
        "filename": file.filename,
        "row_count": len(df),
        "columns_found": list(df.columns),
        "suggested_mapping": mapping,
        "missing_required_fields": missing_required,
        "preview_rows": preview_df.to_dict(orient="records"),
    }


@router.post("/commit")
async def commit_upload(file: UploadFile = File(...), mapping: str = Form(...)):
    df = await _read_csv_upload(file)

    try:
        mapping_dict = json.loads(mapping)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="`mapping` must be valid JSON.")

    missing_required = check_mapping_sufficient(mapping_dict)
    if missing_required:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot proceed — these required fields are unmapped: {missing_required}",
        )

    canonical, generated_transaction_id = apply_mapping(df, mapping_dict)
    clean, dropped, quality_report = validate_canonical(canonical)

    if clean.empty:
        return {
            "success": False,
            "quality_report": quality_report,
            "message": "No valid rows remained after validation — nothing was activated. "
                       "Your previous active dataset is unchanged.",
        }

    settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean.to_csv(settings.PROCESSED_DATA_DIR / "uploaded_transactions.csv", index=False)

    daily_metrics = compute_daily_merchant_metrics(clean)
    merchant_metrics = compute_merchant_summary(clean)
    daily_metrics.to_csv(settings.PROCESSED_DATA_DIR / "uploaded_daily_metrics.csv", index=False)
    merchant_metrics.to_csv(settings.PROCESSED_DATA_DIR / "uploaded_merchant_metrics.csv", index=False)

    daily_metrics["date"] = pd.to_datetime(daily_metrics["date"]).dt.date
    anomalies = detect_anomalies_all_merchants(daily_metrics)
    incidents = build_incidents_all_merchants(anomalies, daily_metrics)
    incidents.to_csv(settings.PROCESSED_DATA_DIR / "uploaded_incidents.csv", index=False)

    set_active_dataset("uploaded")

    return {
        "success": True,
        "quality_report": quality_report,
        "generated_transaction_id": generated_transaction_id,
        "summary": {
            "merchants": int(clean["merchant_id"].nunique()),
            "transactions": len(clean),
            "date_range": {
                "start": clean["timestamp"].min().strftime("%Y-%m-%d"),
                "end": clean["timestamp"].max().strftime("%Y-%m-%d"),
            },
            "incidents_detected": len(incidents),
        },
        "message": "Your data is now active — the dashboard is showing your uploaded dataset.",
    }


@router.get("/status")
def upload_status():
    active = get_active_dataset()
    return {"active_dataset": active}


@router.post("/reset-to-demo")
def reset_to_demo():
    set_active_dataset("demo")
    return {"active_dataset": "demo", "message": "Switched back to the built-in demo dataset."}
