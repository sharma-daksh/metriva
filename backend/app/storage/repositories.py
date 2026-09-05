"""
Lightweight in-memory data access for the API layer. Loads processed CSVs
once at import time and re-serves them from memory. Fine for a demo-scale
dataset (tens of thousands of rows); would move to a real DB-backed
repository (per storage/repositories.py in the architecture doc) once
uploads and multi-tenant data enter the picture.
"""
from __future__ import annotations

import pandas as pd

from app.config import settings


def _read_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = settings.PROCESSED_DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=parse_dates)


def load_merchant_metrics() -> pd.DataFrame:
    return _read_csv("merchant_metrics.csv")


def load_daily_metrics() -> pd.DataFrame:
    return _read_csv("daily_metrics.csv", parse_dates=["date"])


def load_incidents() -> pd.DataFrame:
    return _read_csv(
        "incidents.csv", parse_dates=["start_date", "detection_date", "end_date"]
    )
