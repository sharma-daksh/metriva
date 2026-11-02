"""
Phase 12 — Root-cause analysis.

For an incident, compares each candidate dimension's failure rate in the
BASELINE window (Phase 7's lookback, ending the day the incident starts)
against the INCIDENT window, then ranks dimension values by their share of
EXCESS failures (not raw percentage-point gap, which would let a
20-transaction category outrank a 2,000-transaction one on a fluke).

IMPORTANT — reading contribution_pct correctly: it is normalized WITHIN
each dimension (e.g. "of the excess failures attributable to network
type, 4G accounts for 100%"). It is NOT comparable across dimensions —
network, bank, device, state, and category are five independent lenses on
the same incident, and several can each show "100%" of their own slice
without meaning the incident has five separate full causes. To identify
which dimension matters MOST overall, use top_dimensions() below, which
ranks dimensions against each other by absolute excess failure count —
the one actual apples-to-apples comparison available here.

Language rule: this never claims causality. Results are phrased as
"contributor" / "strongest observed driver", never "caused by".
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from app.services.metrics import compute_dimension_failure_rates

CANDIDATE_DIMENSIONS = [
    "receiver_bank", "network_type", "device_type", "state", "merchant_category",
]
DIMENSION_LABELS = {
    "receiver_bank": "Receiving Bank",
    "network_type": "Network",
    "device_type": "Device",
    "state": "Customer State",
    "merchant_category": "Merchant Category",
}
MIN_TRANSACTIONS_FOR_CONTRIBUTION = 5  # per dimension value, in the incident window
BASELINE_LOOKBACK_DAYS = 60


@dataclass
class DimensionContribution:
    dimension: str
    value: str
    baseline_failure_rate: float | None
    incident_failure_rate: float
    incident_transactions: int
    incident_failures: int
    excess_failures: float
    contribution_pct: float | None
    evidence_sufficient: bool


@dataclass
class RootCauseResult:
    incident_id: str
    merchant_id: str
    contributions: list = field(default_factory=list)  # sorted, strongest first
    note: str = ""

    def top(self, n: int = 3) -> list:
        """Top VALUES within their own dimension — see the module docstring
        warning before comparing contribution_pct across different dimensions."""
        ranked = [c for c in self.contributions if c.evidence_sufficient and c.contribution_pct is not None]
        return sorted(ranked, key=lambda c: c.contribution_pct, reverse=True)[:n]

    def top_dimensions(self, n: int = 3) -> list[dict]:
        """
        Ranks DIMENSIONS against each other (network vs. bank vs. device,
        etc.) by the absolute excess-failure count of each dimension's
        single strongest value. This is the one comparison on this page
        that's actually apples-to-apples, and is what "primary" /
        "secondary" contributor should be based on.
        """
        by_dimension: dict[str, list] = {}
        for c in self.contributions:
            if c.evidence_sufficient:
                by_dimension.setdefault(c.dimension, []).append(c)

        top_per_dimension = []
        for dim, contributions in by_dimension.items():
            best = max(contributions, key=lambda c: c.excess_failures)
            if best.excess_failures > 0:
                top_per_dimension.append(best)

        top_per_dimension.sort(key=lambda c: c.excess_failures, reverse=True)

        return [
            {
                "rank": i + 1,
                "dimension": c.dimension,
                "dimension_label": DIMENSION_LABELS.get(c.dimension, c.dimension),
                "value": c.value,
                "baseline_failure_rate": c.baseline_failure_rate,
                "incident_failure_rate": c.incident_failure_rate,
                "incident_transactions": c.incident_transactions,
                "excess_failures": round(c.excess_failures, 1),
            }
            for i, c in enumerate(top_per_dimension[:n])
        ]


def analyze_incident_root_cause(
    transactions: pd.DataFrame,
    incident_id: str,
    merchant_id: str,
    start_date: date,
    end_date: date,
    dimensions: list[str] = CANDIDATE_DIMENSIONS,
    baseline_lookback_days: int = BASELINE_LOOKBACK_DAYS,
) -> RootCauseResult:
    tx = transactions.copy()
    tx["date"] = pd.to_datetime(tx["timestamp"]).dt.date
    merchant_tx = tx[tx["merchant_id"] == merchant_id]

    baseline_start = start_date - timedelta(days=baseline_lookback_days)
    baseline_tx = merchant_tx[(merchant_tx["date"] >= baseline_start) & (merchant_tx["date"] < start_date)]
    incident_tx = merchant_tx[(merchant_tx["date"] >= start_date) & (merchant_tx["date"] <= end_date)]

    if baseline_tx.empty:
        return RootCauseResult(
            incident_id, merchant_id, [],
            "No baseline-window transactions available — cannot attribute root cause.",
        )
    if incident_tx.empty:
        return RootCauseResult(
            incident_id, merchant_id, [],
            "No incident-window transactions available — cannot attribute root cause.",
        )

    all_contributions: list[DimensionContribution] = []

    for dim in dimensions:
        if dim not in tx.columns:
            continue

        baseline_rates = compute_dimension_failure_rates(baseline_tx, dim).set_index(dim)
        incident_rates = compute_dimension_failure_rates(incident_tx, dim)

        dim_contributions = []
        for _, row in incident_rates.iterrows():
            value = row[dim]
            incident_n = int(row["transaction_count"])
            incident_failures = int(row["failure_count"])
            incident_rate = row["failure_rate"]

            evidence_sufficient = incident_n >= MIN_TRANSACTIONS_FOR_CONTRIBUTION

            if value in baseline_rates.index:
                baseline_rate = float(baseline_rates.loc[value, "failure_rate"])
            else:
                baseline_rate = None  # this value never appeared in the merchant's baseline history

            expected = (baseline_rate * incident_n) if baseline_rate is not None else incident_failures
            excess = max(0.0, incident_failures - expected)

            dim_contributions.append(DimensionContribution(
                dimension=dim, value=str(value), baseline_failure_rate=baseline_rate,
                incident_failure_rate=incident_rate, incident_transactions=incident_n,
                incident_failures=incident_failures, excess_failures=excess,
                contribution_pct=None, evidence_sufficient=evidence_sufficient,
            ))

        dim_total_excess = sum(c.excess_failures for c in dim_contributions if c.evidence_sufficient)
        for c in dim_contributions:
            if c.evidence_sufficient and dim_total_excess > 0:
                c.contribution_pct = round(100 * c.excess_failures / dim_total_excess, 1)

        all_contributions.extend(dim_contributions)

    return RootCauseResult(incident_id=incident_id, merchant_id=merchant_id, contributions=all_contributions)


_RANK_WORDS = {1: "Primary", 2: "Secondary", 3: "Additional"}


def generate_summary_sentences(top_dimensions: list[dict]) -> list[str]:
    """
    Turns the ranked dimension list into plain-English sentences (Section
    34: "Provide plain-English explanation"), e.g.:
        "Primary factor: Network (4G) — failure rate rose from 3.5% to
         18.2% across 11 transactions."

    This is template-based, not an LLM call. Reasoning: this explanation
    feeds directly into a revenue-risk and recovery-action decision, and
    Phase 17 (Explanation Evaluator) is designed to test this explanation
    for fidelity, stability under randomization, and counterfactual
    validity — all of which assume the explanation is a deterministic
    function of the underlying numbers. A live LLM call would make the
    same incident produce different wording (or even different emphasis)
    on different runs, which undermines exactly the auditability this
    product is supposed to provide. If more natural phrasing is wanted
    later, the right place for an LLM is REWORDING these already-computed,
    already-verified sentences for tone — never generating the underlying
    numbers or ranking itself.
    """
    sentences = []
    for d in top_dimensions:
        rank_word = _RANK_WORDS.get(d["rank"], f"Rank {d['rank']}")
        baseline_pct = f"{d['baseline_failure_rate']:.1%}" if d["baseline_failure_rate"] is not None else "no prior history"
        incident_pct = f"{d['incident_failure_rate']:.1%}"
        sentences.append(
            f"{rank_word} factor: {d['dimension_label']} ({d['value']}) — failure rate rose from "
            f"{baseline_pct} to {incident_pct} across {d['incident_transactions']} transactions "
            f"in this window."
        )
    return sentences