"""
Data access for the API layer. Reads processed CSVs fresh on every call
(dataset sizes here are small enough that this is cheap) — no caching, so
switching the active dataset (see below) takes effect immediately with no
server restart needed.

ACTIVE DATASET: the app supports two data sources — the built-in Demo
dataset and a person's uploaded CSV (Section 2: "Both modes must converge
into the same canonical transaction schema and analytics engine"). Rather
than overwrite the demo files when someone uploads data (destructive, and
loses the demo permanently), an "active_dataset.txt" pointer selects which
file set every load_* function reads from. This means every existing route
(merchants, incidents, root-cause, recovery, analytics) works unmodified on
uploaded data — only this file needed to change.

This is a GLOBAL pointer, not per-user/session — there's no auth or
multi-tenancy in this app yet, so one active dataset is shared by everyone
hitting the API. Fine for a single-demo-at-a-time hackathon deployment;
would need per-session or per-account scoping for real multi-tenant use.
"""
from __future__ import annotations

import pandas as pd

from app.config import settings

_ACTIVE_DATASET_FILE = "active_dataset.txt"
_FILENAME_PREFIX = {"demo": "", "uploaded": "uploaded_"}


def _read_csv(name: str, parse_dates: list[str] | None = None) -> pd.DataFrame:
    path = settings.PROCESSED_DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, parse_dates=parse_dates)
    except pd.errors.EmptyDataError:
        # A genuinely empty/headerless CSV (e.g. zero incidents ever
        # written for a dataset) should behave like "no data", not crash
        # every endpoint that reads it.
        return pd.DataFrame()


def get_active_dataset() -> str:
    path = settings.PROCESSED_DATA_DIR / _ACTIVE_DATASET_FILE
    if not path.exists():
        return "demo"
    value = path.read_text().strip()
    return value if value in _FILENAME_PREFIX else "demo"


def set_active_dataset(name: str) -> None:
    if name not in _FILENAME_PREFIX:
        raise ValueError(f"Unknown dataset '{name}' — must be one of {list(_FILENAME_PREFIX)}.")
    path = settings.PROCESSED_DATA_DIR / _ACTIVE_DATASET_FILE
    path.write_text(name)


def _prefixed(name: str) -> str:
    return _FILENAME_PREFIX[get_active_dataset()] + name


def load_merchant_metrics() -> pd.DataFrame:
    return _read_csv(_prefixed("merchant_metrics.csv"))


def load_daily_metrics() -> pd.DataFrame:
    return _read_csv(_prefixed("daily_metrics.csv"), parse_dates=["date"])


def load_incidents() -> pd.DataFrame:
    return _read_csv(
        _prefixed("incidents.csv"), parse_dates=["start_date", "detection_date", "end_date"]
    )


def load_transactions() -> pd.DataFrame:
    # The demo dataset's canonical transactions file is historically named
    # incident_transactions.csv (Phase 10's controlled scenarios baked in),
    # not transactions.csv (the pre-injection clean version) — everything
    # else follows the uniform _prefixed() naming.
    if get_active_dataset() == "demo":
        return _read_csv("incident_transactions.csv", parse_dates=["timestamp"])
    return _read_csv("uploaded_transactions.csv", parse_dates=["timestamp"])
