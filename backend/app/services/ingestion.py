"""
Phase 2 — Ingestion service.

Responsible for reading a raw CSV (from Demo Mode's fixed file or an
uploaded file) and performing structural validation only: does it parse,
are required columns present, are dtypes sane. It does NOT map columns to
the canonical schema — that's normalization.py (Phase 3/5).

Kept deliberately dumb: ingestion should never guess semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

REQUIRED_MINIMUM_COLUMNS = {"timestamp", "amount", "status"}


@dataclass
class IngestionResult:
    dataframe: pd.DataFrame
    row_count: int
    column_count: int
    columns: list[str]
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def ingest_csv(path: str | Path) -> IngestionResult:
    path = Path(path)
    errors: list[str] = []
    warnings: list[str] = []

    if not path.exists():
        return IngestionResult(pd.DataFrame(), 0, 0, [], errors=[f"File not found: {path}"])

    if path.stat().st_size == 0:
        return IngestionResult(pd.DataFrame(), 0, 0, [], errors=["File is empty."])

    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return IngestionResult(pd.DataFrame(), 0, 0, [], errors=["File has no parseable rows."])
    except pd.errors.ParserError as exc:
        return IngestionResult(pd.DataFrame(), 0, 0, [], errors=[f"Malformed CSV: {exc}"])

    if df.empty:
        errors.append("File parsed but contains zero data rows.")

    missing_required = REQUIRED_MINIMUM_COLUMNS - set(df.columns)
    if missing_required:
        errors.append(f"Missing required columns: {sorted(missing_required)}")

    duplicate_cols = df.columns[df.columns.duplicated()].tolist()
    if duplicate_cols:
        errors.append(f"Duplicate column names: {duplicate_cols}")

    return IngestionResult(
        dataframe=df,
        row_count=len(df),
        column_count=df.shape[1],
        columns=list(df.columns),
        errors=errors,
        warnings=warnings,
    )
