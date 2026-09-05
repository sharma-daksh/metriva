"""
Phase 6 — Metrics engine.

Computes the base metrics every later phase (baseline, anomaly detection,
root cause) is built on top of. Pure functions over a canonical transactions
DataFrame — no I/O here, so these are easy to unit test and reuse for both
Demo Mode and uploaded data.
"""
from __future__ import annotations

import pandas as pd


def compute_daily_merchant_metrics(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (merchant_id, date): transaction_count, failure_count,
    failure_rate, success_rate, transaction_volume (₹), average_transaction_value,
    failed_amount.
    """
    df = transactions.copy()
    df["date"] = pd.to_datetime(df["timestamp"]).dt.date
    df["is_failed"] = df["status"] == "FAILED"

    grouped = df.groupby(["merchant_id", "date"])
    metrics = grouped.agg(
        transaction_count=("transaction_id", "count"),
        failure_count=("is_failed", "sum"),
        transaction_volume=("amount", "sum"),
        average_transaction_value=("amount", "mean"),
        failed_amount=("amount", lambda s: s[df.loc[s.index, "is_failed"]].sum()),
    ).reset_index()

    metrics["failure_rate"] = metrics["failure_count"] / metrics["transaction_count"]
    metrics["success_rate"] = 1 - metrics["failure_rate"]

    return metrics.sort_values(["merchant_id", "date"]).reset_index(drop=True)


def compute_dimension_failure_rates(
    transactions: pd.DataFrame, dimension: str
) -> pd.DataFrame:
    """
    Failure rate broken down by a categorical dimension (bank, network,
    device, state, hour, day_of_week, etc.) — used by root-cause analysis
    in Phase 12, but is a metrics-layer primitive.
    """
    df = transactions.copy()
    df["is_failed"] = df["status"] == "FAILED"

    grouped = df.groupby(dimension)
    result = grouped.agg(
        transaction_count=("transaction_id", "count"),
        failure_count=("is_failed", "sum"),
    ).reset_index()
    result["failure_rate"] = result["failure_count"] / result["transaction_count"]
    return result.sort_values("failure_rate", ascending=False).reset_index(drop=True)


def compute_merchant_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """
    One row per merchant across the whole period: overall failure rate,
    volume, avg transaction value. Used for the merchant list / overview page.
    """
    df = transactions.copy()
    df["is_failed"] = df["status"] == "FAILED"

    summary = df.groupby("merchant_id").agg(
        transaction_count=("transaction_id", "count"),
        failure_count=("is_failed", "sum"),
        transaction_volume=("amount", "sum"),
        average_transaction_value=("amount", "mean"),
    ).reset_index()
    summary["failure_rate"] = summary["failure_count"] / summary["transaction_count"]
    return summary.sort_values("merchant_id").reset_index(drop=True)
