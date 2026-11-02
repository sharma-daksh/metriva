"""
Phase 16 — Feature engineering for the anomaly classifier.

Builds one row per (merchant_id, date) of rolling, leakage-safe features
from Phase 6's daily_metrics — leakage-safe because every rolling window
here is computed with pandas' `closed="left"` semantics (i.e. it looks at
the days *before* the current one), the same "never let the window
contaminate itself" rule Phase 7's baseline engine follows.

These features are deliberately built from the same daily_metrics table
the statistical detector (Phase 8) and baseline engine (Phase 7) already
use, so the model is learning from the same signal the rest of the system
trusts, not a parallel, untested one.
"""
from __future__ import annotations

import pandas as pd

# Every column here must exist on the DataFrame `build_features` returns,
# and in this order — this is the exact column set the model is trained
# and scored on (see app.ml.models.train_anomaly_classifier).
FEATURE_COLUMNS = [
    "transaction_count",
    "failure_rate",
    "failure_count_7d",
    "transaction_count_7d",
    "failure_rate_7d",
    "failure_rate_mean_14d",
    "failure_rate_std_14d",
    "failure_rate_zscore_14d",
    "volume_change_pct_7d",
    "avg_transaction_value_change_pct_7d",
]

# Human-readable labels for the frontend (Phase 16's SHAP panel).
FEATURE_DISPLAY_NAMES = {
    "transaction_count": "Transactions that day",
    "failure_rate": "Failure rate that day",
    "failure_count_7d": "Failures, trailing 7 days",
    "transaction_count_7d": "Transactions, trailing 7 days",
    "failure_rate_7d": "Failure rate, trailing 7 days",
    "failure_rate_mean_14d": "Typical failure rate, trailing 14 days",
    "failure_rate_std_14d": "Failure rate volatility, trailing 14 days",
    "failure_rate_zscore_14d": "How unusual today's failure rate is (z-score)",
    "volume_change_pct_7d": "Transaction volume change vs prior 7 days",
    "avg_transaction_value_change_pct_7d": "Avg transaction value change vs prior 7 days",
}

MIN_STD_FLOOR = 1e-6  # avoids divide-by-zero when a merchant's rate hasn't moved


def _rolling_prior(series: pd.Series, window: int, stat: str) -> pd.Series:
    """Rolling stat over the `window` days strictly BEFORE the current row."""
    shifted = series.shift(1)
    roll = shifted.rolling(window=window, min_periods=window)
    if stat == "mean":
        return roll.mean()
    if stat == "sum":
        return roll.sum()
    if stat == "std":
        return roll.std()
    raise ValueError(f"Unknown stat: {stat}")


def build_features_for_merchant(merchant_days: pd.DataFrame) -> pd.DataFrame:
    """
    merchant_days: daily_metrics filtered to ONE merchant, with one row per
    date it had transactions (gap days are simply absent, same limitation
    Phase 8 documents). Must be sorted by date before calling.
    """
    df = merchant_days.sort_values("date").reset_index(drop=True).copy()

    df["failure_count_7d"] = _rolling_prior(df["failure_count"], 7, "sum")
    df["transaction_count_7d"] = _rolling_prior(df["transaction_count"], 7, "sum")
    df["failure_rate_7d"] = df["failure_count_7d"] / df["transaction_count_7d"]

    df["failure_rate_mean_14d"] = _rolling_prior(df["failure_rate"], 14, "mean")
    df["failure_rate_std_14d"] = _rolling_prior(df["failure_rate"], 14, "std").clip(lower=MIN_STD_FLOOR)
    df["failure_rate_zscore_14d"] = (
        df["failure_rate"] - df["failure_rate_mean_14d"]
    ) / df["failure_rate_std_14d"]

    volume_prior_7d = _rolling_prior(df["transaction_volume"], 7, "mean")
    df["volume_change_pct_7d"] = (df["transaction_volume"] - volume_prior_7d) / volume_prior_7d

    avg_value_prior_7d = _rolling_prior(df["average_transaction_value"], 7, "mean")
    df["avg_transaction_value_change_pct_7d"] = (
        df["average_transaction_value"] - avg_value_prior_7d
    ) / avg_value_prior_7d

    return df


def build_features(daily_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Batch version across every merchant. Returns merchant_id, date, every
    column in FEATURE_COLUMNS, plus the underlying daily_metrics columns
    (kept for convenience/debugging). Rows without enough prior history for
    the 14-day window are dropped — same "don't fabricate on insufficient
    data" stance as Phase 7/8.
    """
    df = daily_metrics.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    frames = [
        build_features_for_merchant(df[df["merchant_id"] == merchant_id])
        for merchant_id in sorted(df["merchant_id"].unique())
    ]
    features = pd.concat(frames, ignore_index=True)
    return features.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)


def attach_labels(features: pd.DataFrame, anomalies: pd.DataFrame) -> pd.DataFrame:
    """Joins Phase 8's is_anomaly label onto the feature rows, by (merchant_id, date)."""
    labels = anomalies[["merchant_id", "date", "is_anomaly"]].copy()
    labels["date"] = pd.to_datetime(labels["date"]).dt.date
    merged = features.merge(labels, on=["merchant_id", "date"], how="inner")
    merged["is_anomaly"] = merged["is_anomaly"].astype(bool)
    return merged