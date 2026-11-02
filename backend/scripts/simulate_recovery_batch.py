"""
Phase 14+15 — batch runner.

Applies the recovery policy engine and simulation to every incident, and
aggregates the portfolio-level KPIs from Section 22:
    Revenue at Risk | Recovered | Recovery Rate | Still at Risk
keeping "estimated at risk", "projected recoverable", and "actually
recovered" distinct throughout (Section 22's explicit requirement).

Run:
    python -m scripts.simulate_recovery_batch

Output:
    backend/data/processed/recovery_results.csv   (per-incident detail)
"""
from __future__ import annotations

import pandas as pd

from app.config import settings
from app.services.recovery_policy import recommend_action
from app.services.recovery_simulation import simulate_recovery


def main() -> None:
    incidents = pd.read_csv(
        settings.PROCESSED_DATA_DIR / "incidents.csv", parse_dates=["start_date", "end_date"]
    )
    incidents["start_date"] = incidents["start_date"].dt.date
    incidents["end_date"] = incidents["end_date"].dt.date

    transactions = pd.read_csv(
        settings.PROCESSED_DATA_DIR / "incident_transactions.csv", parse_dates=["timestamp"]
    )

    rows = []
    for _, incident in incidents.iterrows():
        recommendation = recommend_action(incident)
        row = {
            "incident_id": incident["incident_id"],
            "merchant_id": incident["merchant_id"],
            "status": incident["status"],
            "severity": incident["severity"],
            "revenue_at_risk_low": incident["revenue_at_risk_low"],
            "revenue_at_risk_high": incident["revenue_at_risk_high"],
            "recommended_action": recommendation.action,
        }

        if recommendation.action == "retry_eligible_failed_payments":
            result = simulate_recovery(transactions, incident, recommendation.policy)
            row.update({
                "mode": result.mode,
                "eligible": result.eligible_count,
                "proposed_retries": result.proposed_retries,
                "projected_recoverable_amount": result.projected_recoverable_amount,
                "successful_recoveries": result.successful_recoveries,
                "recovered_amount": result.recovered_amount,
                "failed_retries": result.failed_retries,
                "skipped": result.skipped,
            })
        else:
            row.update({
                "mode": None, "eligible": 0, "proposed_retries": 0,
                "projected_recoverable_amount": 0.0, "successful_recoveries": 0,
                "recovered_amount": 0.0, "failed_retries": 0, "skipped": 0,
            })

        rows.append(row)

    results = pd.DataFrame(rows)
    out_path = settings.PROCESSED_DATA_DIR / "recovery_results.csv"
    results.to_csv(out_path, index=False)

    total_at_risk_low = results["revenue_at_risk_low"].sum()
    total_at_risk_high = results["revenue_at_risk_high"].sum()
    total_recovered = results["recovered_amount"].sum()
    acted_on = results[results["recommended_action"] == "retry_eligible_failed_payments"]
    still_at_risk_high = total_at_risk_high - total_recovered
    recovery_rate = (
        total_recovered / acted_on["revenue_at_risk_high"].sum()
        if acted_on["revenue_at_risk_high"].sum() > 0 else 0.0
    )

    print("=" * 50)
    print("REVENUE RECOVERY (SIMULATION) — Section 22 KPIs")
    print("=" * 50)
    print(f"Revenue at Risk        ₹{total_at_risk_low:,.0f} – ₹{total_at_risk_high:,.0f}")
    print(f"Incidents acted on     {len(acted_on)} of {len(incidents)}")
    print(f"Recovered (SIMULATED)  ₹{total_recovered:,.0f}")
    print(f"Recovery Rate          {recovery_rate:.1%}  (of the acted-on incidents' upper RaR estimate)")
    print(f"Still at Risk          ₹{still_at_risk_high:,.0f}")
    print()
    print(f"Wrote {len(results)} rows to {out_path}")


if __name__ == "__main__":
    main()
