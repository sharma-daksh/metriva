"""
Phase 8 — Anomaly detector.

Core idea (Section 8): a failure rate deviation is only meaningful if it's
both statistically unlikely under the merchant's baseline AND backed by
enough transactions to trust. We never treat "1 failure / 4 transactions"
as equally strong evidence as "100 failures / 400 transactions" just
because both are 25% — the binomial test below is volume-aware by
construction (it takes n, not just the rate).

Algorithm, per (merchant, day):
    1. Try the smallest window (1 day). If it doesn't have enough
       transactions to trust (MIN_TRANSACTIONS_FOR_EVIDENCE), widen to the
       next window (3, 7, 14 days) — Section 10's "use aggregated windows
       ... choose the most statistically defensible window automatically."
    2. Compute the baseline (Phase 7) using only data strictly before the
       window start — never contaminated by the window itself.
    3. Run a one-sided exact binomial test: "if the true failure rate were
       the baseline rate, how likely is it we'd see this many failures (or
       more) out of this many transactions?" A low p-value means the
       deviation is unlikely to be chance.
    4. Require BOTH statistical significance (p-value) AND a minimum
       practical effect size (excess percentage points) — a huge sample can
       make a trivial 0.3pp deviation "significant"; we don't want that
       flagged as an incident.

This module produces day-level anomaly POINTS only. Grouping consecutive
points into incidents (with severity, revenue-at-risk, states) is Phase 9.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
from scipy import stats

from app.services.baseline import Baseline, compute_baseline

# Windows tried in order, smallest (most responsive) first. A day-level
# window is preferred when it has enough evidence; we only widen when it
# doesn't, per Section 10.
CANDIDATE_WINDOWS_DAYS = (1, 3, 7, 14)

MIN_TRANSACTIONS_FOR_EVIDENCE = 10  # below this, a window is never trusted
MIN_EXCESS_RATE_PP = 0.03  # minimum practically-meaningful effect size (3 percentage points)
P_VALUE_THRESHOLD = 0.01  # strict — avoid false alarms from noise
BASELINE_LOOKBACK_DAYS = 60


@dataclass
class AnomalyPoint:
    merchant_id: str
    date: date
    window_days: int
    observed_transactions: int
    observed_failures: int
    observed_failure_rate: float
    baseline_failure_rate: float | None
    baseline_method: str
    excess_rate_pp: float | None
    p_value: float | None
    evidence_sufficient: bool
    is_anomaly: bool
    reason: str


def _binomial_test(observed_failures: int, observed_n: int, baseline_rate: float) -> float:
    """
    One-sided exact binomial test: P(X >= observed_failures | n=observed_n,
    p=baseline_rate). Low p-value = failures are higher than baseline would
    predict, more than chance can explain.
    """
    result = stats.binomtest(observed_failures, observed_n, baseline_rate, alternative="greater")
    return result.pvalue


def detect_anomaly_for_day(
    merchant_days: pd.DataFrame,
    merchant_id: str,
    as_of_date: date,
    windows: tuple[int, ...] = CANDIDATE_WINDOWS_DAYS,
    baseline_lookback_days: int = BASELINE_LOOKBACK_DAYS,
) -> AnomalyPoint:
    """
    merchant_days: daily_metrics filtered to ONE merchant, sorted by date,
    with a contiguous positional index (0..N-1) matching chronological order
    of that merchant's observed days (gap days with zero transactions are
    simply absent — see module docstring in the caller for that limitation).
    """
    merchant_days = merchant_days.reset_index(drop=True)
    merchant_days["date"] = pd.to_datetime(merchant_days["date"]).dt.date
    idx_matches = merchant_days.index[merchant_days["date"] == as_of_date]

    if len(idx_matches) == 0:
        return AnomalyPoint(
            merchant_id, as_of_date, 0, 0, 0, 0.0, None, "insufficient", None, None,
            False, False, "No transactions recorded for this merchant on this date.",
        )

    end_idx = idx_matches[0]

    for w in windows:
        start_idx = end_idx - w + 1
        if start_idx < 0:
            continue  # not enough prior days in the dataset for this window size

        window = merchant_days.iloc[start_idx:end_idx + 1]
        observed_n = int(window["transaction_count"].sum())
        observed_failures = int(window["failure_count"].sum())

        if observed_n < MIN_TRANSACTIONS_FOR_EVIDENCE:
            continue  # widen to the next window

        window_start_date = window.iloc[0]["date"]
        baseline = compute_baseline(
            merchant_days, merchant_id, as_of=window_start_date, lookback_days=baseline_lookback_days
        )

        if baseline.method == "insufficient":
            continue  # can't test without a baseline — try a wider window in case more history helps

        observed_rate = observed_failures / observed_n
        p_value = _binomial_test(observed_failures, observed_n, baseline.baseline_failure_rate)
        excess_pp = (observed_rate - baseline.baseline_failure_rate) * 100

        is_anomaly = (
            p_value < P_VALUE_THRESHOLD
            and (excess_pp / 100) >= MIN_EXCESS_RATE_PP
        )

        reason = (
            f"{w}-day window: {observed_failures}/{observed_n} failed "
            f"({observed_rate:.1%}) vs baseline {baseline.baseline_failure_rate:.1%} "
            f"({baseline.method}, p={p_value:.4g})."
        )

        return AnomalyPoint(
            merchant_id=merchant_id,
            date=as_of_date,
            window_days=w,
            observed_transactions=observed_n,
            observed_failures=observed_failures,
            observed_failure_rate=observed_rate,
            baseline_failure_rate=baseline.baseline_failure_rate,
            baseline_method=baseline.method,
            excess_rate_pp=excess_pp,
            p_value=p_value,
            evidence_sufficient=True,
            is_anomaly=is_anomaly,
            reason=reason,
        )

    # No window (up to the largest tried) produced sufficient evidence or baseline.
    return AnomalyPoint(
        merchant_id, as_of_date, 0, 0, 0, 0.0, None, "insufficient", None, None,
        False, False,
        f"No window up to {max(windows)} days had enough transactions or history "
        "to evaluate — insufficient evidence.",
    )


def detect_anomalies_for_merchant(
    daily_metrics: pd.DataFrame,
    merchant_id: str,
    windows: tuple[int, ...] = CANDIDATE_WINDOWS_DAYS,
    baseline_lookback_days: int = BASELINE_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Runs detect_anomaly_for_day across every observed day for one merchant."""
    merchant_days = daily_metrics[daily_metrics["merchant_id"] == merchant_id].copy()
    merchant_days["date"] = pd.to_datetime(merchant_days["date"]).dt.date
    merchant_days = merchant_days.sort_values("date").reset_index(drop=True)

    points = [
        detect_anomaly_for_day(merchant_days, merchant_id, d, windows, baseline_lookback_days)
        for d in merchant_days["date"]
    ]
    return pd.DataFrame([p.__dict__ for p in points])


def detect_anomalies_all_merchants(
    daily_metrics: pd.DataFrame,
    windows: tuple[int, ...] = CANDIDATE_WINDOWS_DAYS,
    baseline_lookback_days: int = BASELINE_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Batch version across every merchant in daily_metrics."""
    frames = [
        detect_anomalies_for_merchant(daily_metrics, merchant_id, windows, baseline_lookback_days)
        for merchant_id in sorted(daily_metrics["merchant_id"].unique())
    ]
    return pd.concat(frames, ignore_index=True)
