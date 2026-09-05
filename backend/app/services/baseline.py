"""
Phase 7 — Historical baseline engine.

Establishes what "normal" looks like for a merchant BEFORE a monitoring
window begins, so an ongoing incident can never leak into its own baseline
(Section 9: "historical baseline -> monitoring period -> current
observations", and "avoid contamination of the baseline by the current
incident").

Baseline strategy depends on how much pre-window history is available:
  - >= MIN_DAYS_FOR_ROLLING_BASELINE days AND enough transactions
        -> rolling baseline over that history
  - Some history, but below that threshold
        -> conservative pooled baseline, flagged with wider uncertainty
  - No usable history at all
        -> explicitly "insufficient" — callers must not invent a number
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

MIN_DAYS_FOR_ROLLING_BASELINE = 14
MIN_DAYS_FOR_POOLED_BASELINE = 3
MIN_TRANSACTIONS_FOR_BASELINE = 30
DEFAULT_LOOKBACK_DAYS = 60


@dataclass
class Baseline:
    merchant_id: str
    method: str  # "rolling" | "pooled" | "insufficient"
    baseline_failure_rate: float | None
    baseline_transaction_count: int
    baseline_days: int
    window_start: date | None
    window_end: date | None
    note: str


def compute_baseline(
    daily_metrics: pd.DataFrame,
    merchant_id: str,
    as_of: date,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> Baseline:
    """
    Computes the baseline for `merchant_id` using only days strictly before
    `as_of` (the first day of the monitoring window), within `lookback_days`
    of history. Never touches days >= as_of.
    """
    merchant_days = daily_metrics[daily_metrics["merchant_id"] == merchant_id].copy()
    merchant_days["date"] = pd.to_datetime(merchant_days["date"]).dt.date

    as_of = pd.Timestamp(as_of).date()
    window_start = as_of - pd.Timedelta(days=lookback_days)
    window_start = window_start if isinstance(window_start, date) else window_start.date()

    history = merchant_days[
        (merchant_days["date"] >= window_start) & (merchant_days["date"] < as_of)
    ]

    n_days = history["date"].nunique()
    n_txns = int(history["transaction_count"].sum())

    if n_days == 0 or n_txns == 0:
        return Baseline(
            merchant_id, "insufficient", None, 0, 0, None, None,
            "No historical data available before the monitoring window — "
            "cannot establish a baseline.",
        )

    total_failures = int(history["failure_count"].sum())
    pooled_rate = total_failures / n_txns

    if n_days >= MIN_DAYS_FOR_ROLLING_BASELINE and n_txns >= MIN_TRANSACTIONS_FOR_BASELINE:
        method = "rolling"
        note = f"Rolling baseline over {n_days} days ({n_txns} transactions)."
    elif n_days >= MIN_DAYS_FOR_POOLED_BASELINE:
        method = "pooled"
        note = (
            f"Limited history ({n_days} days, {n_txns} transactions) — "
            "using a conservative pooled baseline; treat with wider uncertainty."
        )
    else:
        return Baseline(
            merchant_id, "insufficient", None, n_txns, n_days,
            history["date"].min(), history["date"].max(),
            f"Only {n_days} day(s) of history — insufficient for a defensible baseline.",
        )

    return Baseline(
        merchant_id=merchant_id,
        method=method,
        baseline_failure_rate=pooled_rate,
        baseline_transaction_count=n_txns,
        baseline_days=n_days,
        window_start=history["date"].min(),
        window_end=history["date"].max(),
        note=note,
    )


def compute_baselines_for_all_merchants(
    daily_metrics: pd.DataFrame, as_of: date, lookback_days: int = DEFAULT_LOOKBACK_DAYS
) -> pd.DataFrame:
    """Convenience batch wrapper — one baseline row per merchant, as of a given date."""
    rows = []
    for merchant_id in sorted(daily_metrics["merchant_id"].unique()):
        b = compute_baseline(daily_metrics, merchant_id, as_of, lookback_days)
        rows.append({
            "merchant_id": b.merchant_id,
            "method": b.method,
            "baseline_failure_rate": b.baseline_failure_rate,
            "baseline_transaction_count": b.baseline_transaction_count,
            "baseline_days": b.baseline_days,
            "window_start": b.window_start,
            "window_end": b.window_end,
            "note": b.note,
        })
    return pd.DataFrame(rows)
