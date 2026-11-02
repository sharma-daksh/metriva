"""
Phase 15 — Recovery simulation.

This is a SIMULATION, not a live payment execution (Section 21/56) — no
real or test-mode Razorpay API is called. That distinction is load-bearing:
every result this module produces must be labeled "simulation" wherever
it's surfaced, and Section 22 requires the three quantities below to never
be conflated:

    estimated at risk       -> from incident_engine / revenue.py
    projected recoverable   -> this module's pre-run estimate
    actually recovered      -> this module's post-run (simulated) result

ASSUMPTION (stated explicitly, not hidden): since there is no real retry
channel to observe, we simulate each eligible retry succeeding
independently with probability RETRY_SUCCESS_PROBABILITY. This number is a
documented assumption for demo purposes — Section 21's own example (71/96
≈ 74%) is the basis for the default — not a measured system property. A
fixed seed makes the simulation reproducible (Section 48).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.services.recovery_policy import RecoveryPolicy, determine_eligible_transactions

RETRY_SUCCESS_PROBABILITY = 0.74  # documented assumption — see module docstring
SIMULATION_SEED = 123


@dataclass
class RecoverySimulationResult:
    incident_id: str
    mode: str = "SIMULATION"  # never anything else in this module
    eligible_count: int = 0
    proposed_retries: int = 0
    projected_recoverable_amount: float = 0.0
    projected_recovery_rate: float | None = None
    successful_recoveries: int = 0
    recovered_amount: float = 0.0
    failed_retries: int = 0
    skipped: int = 0
    retry_success_probability_assumed: float = RETRY_SUCCESS_PROBABILITY
    per_transaction_results: list = field(default_factory=list)  # kept for the audit trail (Phase 23)


def simulate_recovery(
    transactions: pd.DataFrame,
    incident: pd.Series,
    policy: RecoveryPolicy | None = None,
    retry_success_probability: float = RETRY_SUCCESS_PROBABILITY,
    seed: int = SIMULATION_SEED,
) -> RecoverySimulationResult:
    policy = policy or RecoveryPolicy()
    eligible = determine_eligible_transactions(transactions, incident, policy)

    eligible_count = len(eligible)
    if eligible_count == 0:
        return RecoverySimulationResult(incident_id=incident["incident_id"], eligible_count=0)

    # Bounded: even though every eligible transaction gets exactly one retry
    # attempt in this simplified simulation (policy.max_retries caps retries
    # PER transaction, not how many transactions are attempted), we cap the
    # total batch size defensively so a single incident can never trigger an
    # unbounded retry sweep (Section 20: "never an unrestricted autonomous
    # payment loop").
    MAX_BATCH_SIZE = 5000
    proposed = eligible.head(MAX_BATCH_SIZE)
    proposed_retries = len(proposed)
    skipped = eligible_count - proposed_retries

    projected_recoverable_amount = float(proposed["amount"].sum() * retry_success_probability)

    rng = np.random.default_rng(seed)
    outcomes = rng.random(proposed_retries) < retry_success_probability

    successful_amount = float(proposed.loc[outcomes, "amount"].sum())
    successful_count = int(outcomes.sum())
    failed_count = proposed_retries - successful_count

    per_txn = [
        {
            "transaction_id": row["transaction_id"],
            "amount": row["amount"],
            "result": "SUCCESS" if success else "FAILED",
        }
        for (_, row), success in zip(proposed.iterrows(), outcomes)
    ]

    return RecoverySimulationResult(
        incident_id=incident["incident_id"],
        eligible_count=eligible_count,
        proposed_retries=proposed_retries,
        projected_recoverable_amount=projected_recoverable_amount,
        projected_recovery_rate=retry_success_probability,
        successful_recoveries=successful_count,
        recovered_amount=successful_amount,
        failed_retries=failed_count,
        skipped=skipped,
        retry_success_probability_assumed=retry_success_probability,
        per_transaction_results=per_txn,
    )
