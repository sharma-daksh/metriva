"""
Phase 10 — Controlled incident simulation.

Injects known, reproducible incidents (Section 17, scenarios A-F) onto a
COPY of the clean processed transactions. Neither data/raw/ nor
data/processed/transactions.csv is ever touched by this module.

For every scenario we flip a subset of SUCCESS transactions matching the
affected dimension + date range to FAILED, targeting (not exactly hitting —
real degradations aren't clean) a target failure rate, using a fixed seed
per scenario for reproducibility (Section 48).

Each scenario also gets a ground-truth record (Section 18) so Phase 11 can
score the detector objectively. The detector (Phases 8-9) is never told
which merchant/bank/network/date was injected — it has to find it (Section
17: "must discover the incident rather than being hardcoded").

Run:
    python -m scripts.inject_incidents

Output:
    backend/data/processed/incident_transactions.csv
    backend/data/processed/ground_truth_incidents.csv
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.config import settings

SEED = 7  # separate from the raw-data seed (42), so scenario placement is independent


@dataclass
class GroundTruthIncident:
    incident_id: str
    merchant_id: str  # "*" when the incident is not merchant-specific (e.g. bank-wide)
    start_date: date
    end_date: date
    incident_type: str
    affected_dimension: str
    affected_value: str
    severity: str
    target_failure_rate: float
    scenario_rows: list = field(default_factory=list, repr=False)


def _flip_to_failed(
    df: pd.DataFrame, mask: pd.Series, target_rate: float, rng: np.random.Generator
) -> pd.DataFrame:
    """
    Among rows selected by `mask`, flips a random subset of SUCCESS rows to
    FAILED so the resulting failure rate within that mask is approximately
    `target_rate`. Already-failed rows count toward the rate as-is.
    """
    subset_idx = df.index[mask]
    n = len(subset_idx)
    if n == 0:
        return df

    current_failures = (df.loc[subset_idx, "status"] == "FAILED").sum()
    target_failures = int(round(target_rate * n))
    n_to_flip = max(0, target_failures - current_failures)

    success_idx = df.index[mask & (df["status"] == "SUCCESS")]
    n_to_flip = min(n_to_flip, len(success_idx))

    if n_to_flip > 0:
        flip_idx = rng.choice(success_idx, size=n_to_flip, replace=False)
        df.loc[flip_idx, "status"] = "FAILED"

    return df


def inject_scenario_a_merchant_degradation(
    df: pd.DataFrame, rng: np.random.Generator,
    merchant_id: str, start: date, end: date, target_rate: float = 0.18,
) -> GroundTruthIncident:
    """Scenario A: one merchant's failure rate spikes for a period."""
    mask = (
        (df["merchant_id"] == merchant_id)
        & (df["timestamp"].dt.date >= start)
        & (df["timestamp"].dt.date <= end)
    )
    _flip_to_failed(df, mask, target_rate, rng)
    return GroundTruthIncident(
        incident_id="INC_TEST_A001", merchant_id=merchant_id, start_date=start, end_date=end,
        incident_type="merchant_degradation", affected_dimension="merchant",
        affected_value=merchant_id, severity="CRITICAL", target_failure_rate=target_rate,
    )


def inject_scenario_b_bank_degradation(
    df: pd.DataFrame, rng: np.random.Generator,
    bank: str, start: date, end: date, target_rate: float = 0.22,
) -> GroundTruthIncident:
    """Scenario B: one receiving bank degrades across all merchants."""
    mask = (
        (df["receiver_bank"] == bank)
        & (df["timestamp"].dt.date >= start)
        & (df["timestamp"].dt.date <= end)
    )
    _flip_to_failed(df, mask, target_rate, rng)
    return GroundTruthIncident(
        incident_id="INC_TEST_B001", merchant_id="*", start_date=start, end_date=end,
        incident_type="bank_degradation", affected_dimension="receiver_bank",
        affected_value=bank, severity="CRITICAL", target_failure_rate=target_rate,
    )


def inject_scenario_c_network_degradation(
    df: pd.DataFrame, rng: np.random.Generator,
    network: str, start: date, end: date, target_rate: float = 0.20,
) -> GroundTruthIncident:
    """Scenario C: one network type degrades across all merchants."""
    mask = (
        (df["network_type"] == network)
        & (df["timestamp"].dt.date >= start)
        & (df["timestamp"].dt.date <= end)
    )
    _flip_to_failed(df, mask, target_rate, rng)
    return GroundTruthIncident(
        incident_id="INC_TEST_C001", merchant_id="*", start_date=start, end_date=end,
        incident_type="network_degradation", affected_dimension="network_type",
        affected_value=network, severity="HIGH", target_failure_rate=target_rate,
    )


def inject_scenario_d_volume_anomaly(
    df: pd.DataFrame, rng: np.random.Generator,
    merchant_id: str, start: date, end: date, drop_fraction: float = 0.75,
) -> tuple[pd.DataFrame, GroundTruthIncident]:
    """
    Scenario D: a merchant's transaction VOLUME drops sharply (not failure
    rate) — e.g. an outage upstream of Metriva that stops requests from
    arriving at all. Implemented by removing rows, since volume anomalies
    are about absence of transactions, not failed ones.
    """
    mask = (
        (df["merchant_id"] == merchant_id)
        & (df["timestamp"].dt.date >= start)
        & (df["timestamp"].dt.date <= end)
    )
    candidates = df.index[mask]
    n_to_drop = int(round(len(candidates) * drop_fraction))
    if n_to_drop > 0:
        drop_idx = rng.choice(candidates, size=n_to_drop, replace=False)
        df = df.drop(index=drop_idx)

    gt = GroundTruthIncident(
        incident_id="INC_TEST_D001", merchant_id=merchant_id, start_date=start, end_date=end,
        incident_type="volume_anomaly", affected_dimension="transaction_count",
        affected_value=f"-{drop_fraction:.0%}", severity="HIGH", target_failure_rate=0.0,
    )
    return df, gt


def inject_scenario_e_high_value_failure(
    df: pd.DataFrame, rng: np.random.Generator,
    start: date, end: date, amount_threshold: float = 5000.0, target_rate: float = 0.30,
) -> GroundTruthIncident:
    """Scenario E: large-value transactions become disproportionately unsuccessful."""
    mask = (
        (df["amount"] >= amount_threshold)
        & (df["timestamp"].dt.date >= start)
        & (df["timestamp"].dt.date <= end)
    )
    _flip_to_failed(df, mask, target_rate, rng)
    return GroundTruthIncident(
        incident_id="INC_TEST_E001", merchant_id="*", start_date=start, end_date=end,
        incident_type="high_value_failure", affected_dimension="amount_bucket",
        affected_value=f">={amount_threshold:.0f}", severity="MEDIUM", target_failure_rate=target_rate,
    )


def inject_scenario_f_multi_factor(
    df: pd.DataFrame, rng: np.random.Generator,
    bank: str, network: str, start: date, end: date, target_rate: float = 0.35,
) -> GroundTruthIncident:
    """
    Scenario F: a bank + network combination degrades together.

    NOTE on scope: the spec's example narrows this to one merchant + one
    bank + one network. With this dataset's per-merchant volume (~5
    transactions/day), a single merchant's slice of one specific
    bank-network pair over a realistic incident window has only ~1-2
    transactions — nowhere near enough to be a detectable, honest incident
    (or even to reliably hit a target rate). Rather than inject a "35%
    failure rate" over 2 transactions, this scenario is applied
    dataset-wide across all merchants, which is the smallest scope that
    gives ~50+ transactions in the window — enough to actually test
    whether root-cause analysis (Phase 12+) can identify two contributing
    dimensions at once.
    """
    mask = (
        (df["receiver_bank"] == bank)
        & (df["network_type"] == network)
        & (df["timestamp"].dt.date >= start)
        & (df["timestamp"].dt.date <= end)
    )
    _flip_to_failed(df, mask, target_rate, rng)
    return GroundTruthIncident(
        incident_id="INC_TEST_F001", merchant_id="*", start_date=start, end_date=end,
        incident_type="multi_factor", affected_dimension="receiver_bank+network_type",
        affected_value=f"{bank}+{network}", severity="CRITICAL",
        target_failure_rate=target_rate,
    )


def build_incident_test_dataset(transactions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Applies all six scenarios (independent dates so they don't interfere
    with each other's ground truth) to a COPY of `transactions`, returning
    (incident_transactions, ground_truth_incidents).
    """
    df = transactions.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    rng = np.random.default_rng(SEED)

    merchants = sorted(df["merchant_id"].unique())
    ground_truths: list[GroundTruthIncident] = []

    gt_a = inject_scenario_a_merchant_degradation(
        df, rng, merchant_id=merchants[1], start=date(2024, 3, 10), end=date(2024, 3, 17),
    )
    ground_truths.append(gt_a)

    gt_b = inject_scenario_b_bank_degradation(
        df, rng, bank="SBI", start=date(2024, 5, 5), end=date(2024, 5, 9),
    )
    ground_truths.append(gt_b)

    gt_c = inject_scenario_c_network_degradation(
        df, rng, network="4G", start=date(2024, 7, 1), end=date(2024, 7, 6),
    )
    ground_truths.append(gt_c)

    df, gt_d = inject_scenario_d_volume_anomaly(
        df, rng, merchant_id=merchants[5], start=date(2024, 8, 12), end=date(2024, 8, 16),
    )
    ground_truths.append(gt_d)

    gt_e = inject_scenario_e_high_value_failure(
        df, rng, start=date(2024, 9, 15), end=date(2024, 9, 20),
    )
    ground_truths.append(gt_e)

    gt_f = inject_scenario_f_multi_factor(
        df, rng, bank="HDFC", network="WiFi",
        start=date(2024, 11, 3), end=date(2024, 11, 12),
    )
    ground_truths.append(gt_f)

    ground_truth_df = pd.DataFrame([
        {
            "incident_id": g.incident_id,
            "merchant_id": g.merchant_id,
            "start_date": g.start_date,
            "end_date": g.end_date,
            "incident_type": g.incident_type,
            "affected_dimension": g.affected_dimension,
            "affected_value": g.affected_value,
            "severity": g.severity,
            "target_failure_rate": g.target_failure_rate,
        }
        for g in ground_truths
    ])

    return df.reset_index(drop=True), ground_truth_df
