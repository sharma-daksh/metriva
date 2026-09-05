"""
Phase 3 (canonical mapping for Demo Mode) + Phase 5 (normalization/validation).

`map_demo_dataset_to_canonical` is specific to our synthetic UPI raw format.
A generic column-mapping UI for arbitrary uploaded CSVs (Section 39) is
deferred to Phase 20 — it's a different problem (inferring an unknown
schema) from normalizing a known one, and the build order in the spec
places CSV upload after the analytics pipeline exists.

`validate_canonical` and `assess_data_quality` are format-agnostic and will
be reused by the upload path once it exists.
"""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from app.models.schemas import CANONICAL_COLUMNS, REQUIRED_CANONICAL_FIELDS, VALID_STATUSES

N_MERCHANTS = 50
MERCHANT_ID_PREFIX = "GRM"


def _assign_merchant_id(receiver_upi_id: str) -> str:
    """
    Deterministically assigns a merchant to a P2M transaction based on the
    receiver's UPI handle, so the same receiver always maps to the same
    merchant (Section 5: "50 simulated merchants assigned deterministically").
    """
    digest = hashlib.md5(str(receiver_upi_id).encode()).hexdigest()
    bucket = int(digest, 16) % N_MERCHANTS
    return f"{MERCHANT_ID_PREFIX}{bucket + 1:03d}"


def map_demo_dataset_to_canonical(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters the raw UPI dataset to P2M transactions and maps it onto the
    canonical schema. Returns a DataFrame with exactly CANONICAL_COLUMNS.
    """
    p2m = raw_df[raw_df["transaction_type"] == "P2M"].copy()

    p2m["merchant_id"] = p2m["receiver_upi_id"].apply(_assign_merchant_id)
    p2m["status"] = p2m["status"].str.upper().str.strip()

    canonical = pd.DataFrame({
        "transaction_id": p2m["transaction_id"],
        "merchant_id": p2m["merchant_id"],
        "timestamp": pd.to_datetime(p2m["timestamp"]),
        "amount": pd.to_numeric(p2m["amount"], errors="coerce"),
        "status": p2m["status"],
        "payment_method": "UPI",
        "payment_processor_or_bank": p2m["receiver_bank"],
        "sender_bank": p2m["sender_bank"],
        "receiver_bank": p2m["receiver_bank"],
        "device_type": p2m["device_type"],
        "network_type": p2m["network_type"],
        "state": p2m["state"],
        "merchant_category": p2m["merchant_category"],
        "customer_id": p2m["sender_upi_id"].astype(str),
    })

    return canonical[CANONICAL_COLUMNS].reset_index(drop=True)


def assess_data_quality(canonical_df: pd.DataFrame) -> dict:
    """
    Produces the Data Quality Report described in Section 40. Never silently
    discards rows here — this only measures and reports; filtering happens
    in validate_canonical, which returns both the clean rows AND what was
    dropped, so nothing disappears without a trace.
    """
    total_rows = len(canonical_df)
    duplicate_rows = int(canonical_df.duplicated(subset=["transaction_id"]).sum())
    missing_timestamps = int(canonical_df["timestamp"].isna().sum())
    invalid_amounts = int(
        (canonical_df["amount"].isna() | (canonical_df["amount"] <= 0)).sum()
    )
    unknown_statuses = int((~canonical_df["status"].isin(VALID_STATUSES)).sum())
    missing_required = {
        field: int(canonical_df[field].isna().sum())
        for field in REQUIRED_CANONICAL_FIELDS
        if field in canonical_df.columns
    }

    valid_rows = total_rows - len(set(
        list(canonical_df[canonical_df.duplicated(subset=["transaction_id"])].index)
        + list(canonical_df[canonical_df["timestamp"].isna()].index)
        + list(canonical_df[canonical_df["amount"].isna() | (canonical_df["amount"] <= 0)].index)
        + list(canonical_df[~canonical_df["status"].isin(VALID_STATUSES)].index)
    ))

    return {
        "rows": total_rows,
        "valid_rows": valid_rows,
        "duplicate_rows": duplicate_rows,
        "missing_timestamps": missing_timestamps,
        "invalid_amounts": invalid_amounts,
        "unknown_statuses": unknown_statuses,
        "missing_required_fields": missing_required,
        "can_proceed": valid_rows > 0,
    }


def validate_canonical(canonical_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Splits canonical_df into (clean_rows, dropped_rows, quality_report).
    Dropped rows are never silently discarded — callers should persist them
    if they need to show the user what was excluded and why.
    """
    report = assess_data_quality(canonical_df)

    is_duplicate = canonical_df.duplicated(subset=["transaction_id"])
    is_bad_timestamp = canonical_df["timestamp"].isna()
    is_bad_amount = canonical_df["amount"].isna() | (canonical_df["amount"] <= 0)
    is_bad_status = ~canonical_df["status"].isin(VALID_STATUSES)

    drop_mask = is_duplicate | is_bad_timestamp | is_bad_amount | is_bad_status

    clean = canonical_df[~drop_mask].reset_index(drop=True)
    dropped = canonical_df[drop_mask].reset_index(drop=True)

    return clean, dropped, report
