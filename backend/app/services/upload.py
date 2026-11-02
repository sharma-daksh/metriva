"""
Phase 20 — Upload processing.

Turns a raw uploaded DataFrame + a confirmed column mapping into canonical
transactions, then hands off to normalization.validate_canonical (already
generic, built in Phase 5) for the data quality report.

Never fabricates a field that wasn't mapped (Section 6) — an unmapped
canonical column is left null, not guessed. The one exception is
transaction_id: if genuinely absent, we generate a row-sequence ID purely
as an internal join key. That's a synthetic identifier, not a fabricated
business fact (no amount, status, bank, etc. is ever invented), so it's
labeled as generated in the response rather than silently faked.
"""
from __future__ import annotations

import pandas as pd

from app.models.schemas import CANONICAL_COLUMNS

# These must be mappable to proceed at all — everything else may be null.
HARD_REQUIRED_FIELDS = ["merchant_id", "timestamp", "amount", "status"]

_STATUS_ALIASES = {
    "success": "SUCCESS", "successful": "SUCCESS", "completed": "SUCCESS", "paid": "SUCCESS",
    "failed": "FAILED", "failure": "FAILED", "declined": "FAILED", "error": "FAILED",
}


def check_mapping_sufficient(mapping: dict[str, str | None]) -> list[str]:
    """Returns the list of hard-required fields that are still unmapped."""
    return [f for f in HARD_REQUIRED_FIELDS if not mapping.get(f)]


def apply_mapping(raw_df: pd.DataFrame, mapping: dict[str, str | None]) -> pd.DataFrame:
    """
    Builds a canonical-schema DataFrame by selecting/renaming the uploaded
    columns per `mapping`. Canonical fields with no mapped source column
    become an explicit null column (Section 6), not a guess.
    """
    canonical = {}
    for field in CANONICAL_COLUMNS:
        source_col = mapping.get(field)
        if source_col and source_col in raw_df.columns:
            canonical[field] = raw_df[source_col]
        else:
            canonical[field] = pd.Series([None] * len(raw_df))

    df = pd.DataFrame(canonical)

    generated_transaction_id = False
    if df["transaction_id"].isna().all():
        df["transaction_id"] = [f"ROW_{i}" for i in range(len(df))]
        generated_transaction_id = True

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

    # Normalize whatever status vocabulary the source uses onto SUCCESS/FAILED
    # where we recognize it; anything unrecognized is left as-is so the
    # quality report's "unknown_statuses" count reflects it honestly rather
    # than silently coercing it to one bucket or the other.
    raw_status = df["status"].astype(str).str.strip().str.lower()
    df["status"] = raw_status.map(_STATUS_ALIASES).fillna(df["status"].astype(str).str.strip().str.upper())

    df["merchant_id"] = df["merchant_id"].astype(str)

    return df[CANONICAL_COLUMNS], generated_transaction_id
