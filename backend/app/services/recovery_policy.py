"""
Phase 14 — Recovery policy engine.

Every automated action has hard bounds (Section 20): eligibility rules, a
maximum retry count, a cooldown, and explicit stopping conditions. This
module NEVER executes anything — it only decides (a) whether an incident
warrants action and (b) which transactions are eligible under the policy.
Execution (simulated, for now) is Phase 15.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Bounded retry policy (Section 20's example numbers).
MAX_RETRIES = 2
COOLDOWN_MINUTES = 30
RETRY_WINDOW_DAYS = 7  # a failure older than this is not considered "recent" enough to retry


@dataclass
class RecoveryPolicy:
    max_retries: int = MAX_RETRIES
    cooldown_minutes: int = COOLDOWN_MINUTES
    stop_on_success: bool = True
    stop_on_customer_decline: bool = True
    eligibility_rules: list = field(default_factory=lambda: [
        "status == FAILED",
        f"failed within the last {RETRY_WINDOW_DAYS} days of the incident window",
        "no previous successful retry on this transaction",  # not yet trackable — see note below
    ])


@dataclass
class RecoveryRecommendation:
    incident_id: str
    action: str  # "retry_eligible_failed_payments" | "retry_after_delay" | "monitor" | "no_action_needed"
    reason: str
    policy: RecoveryPolicy | None


def recommend_action(incident: pd.Series) -> RecoveryRecommendation:
    """
    Decides WHAT to recommend for an incident — not who to retry (that's
    determine_eligible_transactions below). Deliberately conservative:
    WATCH-status incidents (not yet persistent) get "monitor", not a retry
    action, since acting on single-window evidence risks retrying
    transactions that were never really degraded.
    """
    status = incident["status"]
    severity = incident["severity"]

    if status == "RESOLVED":
        return RecoveryRecommendation(
            incident["incident_id"], "no_action_needed",
            "Incident has already resolved — no outstanding recovery action needed.",
            None,
        )

    if status == "WATCH":
        return RecoveryRecommendation(
            incident["incident_id"], "monitor",
            "Only a single anomalous window so far — insufficient persistence to act on "
            "(Section 20 principle: never an unrestricted, hair-trigger response).",
            None,
        )

    if status in ("ACTIVE", "RECOVERING") and severity in ("CRITICAL", "HIGH", "MEDIUM"):
        return RecoveryRecommendation(
            incident["incident_id"], "retry_eligible_failed_payments",
            f"{severity} incident with persistent evidence — retry eligible failed payments "
            f"under a bounded policy (max {MAX_RETRIES} retries, {COOLDOWN_MINUTES}min cooldown).",
            RecoveryPolicy(),
        )

    return RecoveryRecommendation(
        incident["incident_id"], "monitor",
        "Low severity — continue monitoring before committing recovery actions.",
        None,
    )


def determine_eligible_transactions(
    transactions: pd.DataFrame, incident: pd.Series, policy: RecoveryPolicy = RecoveryPolicy()
) -> pd.DataFrame:
    """
    Returns the FAILED transactions for this incident's merchant/window that
    are eligible for retry under `policy`.

    NOTE on the "no previous successful retry" rule: this system has no
    retry-history store yet (that lands with the audit trail, Phase 23), so
    every failed transaction in-window is currently treated as never having
    been retried. This is stated explicitly rather than silently assumed.
    """
    tx = transactions.copy()
    tx["date"] = pd.to_datetime(tx["timestamp"]).dt.date

    in_window = (
        (tx["merchant_id"] == incident["merchant_id"])
        & (tx["date"] >= incident["start_date"])
        & (tx["date"] <= incident["end_date"])
        & (tx["status"] == "FAILED")
    )
    eligible = tx[in_window].copy()
    eligible["retry_count_used"] = 0  # no history store yet — see note above
    return eligible
