"""
Phase 13 — Revenue-at-risk calculation.

Methodology (Section 12): revenue at risk is the INCREMENTAL loss
attributable to deterioration relative to baseline — never "all failed
transaction value". We estimate:

    excess_failures = observed_failures - expected_failures_under_baseline
    revenue_at_risk (point) = excess_failures x average_transaction_value

Because both the excess-failure count and the "right" average transaction
value are themselves estimates, we report a range (±UNCERTAINTY_PCT)
rather than a single unjustified figure, per Section 12's explicit
instruction to avoid "pretending to know an exact amount".
"""
from __future__ import annotations

from dataclasses import dataclass

UNCERTAINTY_PCT = 0.15  # ±15% band around the point estimate


@dataclass
class RevenueAtRisk:
    excess_failures: float
    average_transaction_value: float
    point_estimate: float
    low_estimate: float
    high_estimate: float


def compute_revenue_at_risk(
    excess_failures: float,
    average_transaction_value: float,
    uncertainty_pct: float = UNCERTAINTY_PCT,
) -> RevenueAtRisk:
    excess_failures = max(0.0, excess_failures)
    point = excess_failures * average_transaction_value
    return RevenueAtRisk(
        excess_failures=excess_failures,
        average_transaction_value=average_transaction_value,
        point_estimate=point,
        low_estimate=point * (1 - uncertainty_pct),
        high_estimate=point * (1 + uncertainty_pct),
    )
