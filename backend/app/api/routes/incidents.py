from __future__ import annotations

import math
from functools import lru_cache

import joblib
import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.storage.repositories import load_incidents, load_transactions
from app.services.root_cause import analyze_incident_root_cause, generate_summary_sentences, DIMENSION_LABELS as _DIMENSION_LABELS
from app.services.recovery_policy import recommend_action
from app.services.recovery_simulation import simulate_recovery
from app.services.audit import AuditEvent, append_audit_events
from app.ml.models import TrainedModel
from app.ml.explainers import build_explainer, explain_instance

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


@lru_cache(maxsize=1)
def _load_model_and_explainer():
    model_path = settings.BASE_DIR / "data" / "models" / "anomaly_classifier.joblib"
    if not model_path.exists():
        return None, None
    data = joblib.load(model_path)
    trained = TrainedModel(model=data["model"], feature_columns=data["feature_columns"], metrics={})
    explainer = build_explainer(trained)
    return trained, explainer


@lru_cache(maxsize=1)
def _load_model_features() -> pd.DataFrame:
    path = settings.PROCESSED_DATA_DIR / "model_features.csv"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, parse_dates=["date"])
    df["date"] = df["date"].dt.date
    return df


def _serialize(row) -> dict:
    return {
        "incident_id": row["incident_id"],
        "merchant_id": row["merchant_id"],
        "start_date": row["start_date"].strftime("%Y-%m-%d"),
        "detection_date": row["detection_date"].strftime("%Y-%m-%d"),
        "end_date": row["end_date"].strftime("%Y-%m-%d"),
        "duration_days": int(row["duration_days"]),
        "baseline_failure_rate": _clean(round(float(row["baseline_failure_rate"]), 4)),
        "incident_failure_rate": _clean(round(float(row["incident_failure_rate"]), 4)),
        "peak_failure_rate": _clean(round(float(row["peak_failure_rate"]), 4)),
        "failed_transactions": int(row["failed_transactions"]),
        "excess_failures": _clean(round(float(row["excess_failures"]), 1)),
        "revenue_at_risk_low": _clean(round(float(row["revenue_at_risk_low"]), 2)),
        "revenue_at_risk_high": _clean(round(float(row["revenue_at_risk_high"]), 2)),
        "severity": row["severity"],
        "confidence": _clean(round(float(row["confidence"]), 4)),
        "detection_delay_days": int(row["detection_delay_days"]),
        "status": row["status"],
    }


@router.get("")
def list_incidents(
    merchant_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
):
    incidents = load_incidents()
    if incidents.empty:
        return []

    if merchant_id:
        incidents = incidents[incidents["merchant_id"] == merchant_id]
    if status:
        incidents = incidents[incidents["status"] == status.upper()]

    incidents = incidents.sort_values("start_date", ascending=False)
    return [_serialize(row) for _, row in incidents.iterrows()]


@router.get("/summary")
def incidents_summary():
    """Portfolio-wide KPIs for the overview page (Section 22)."""
    incidents = load_incidents()
    if incidents.empty:
        return {
            "total_revenue_at_risk": 0, "open_incidents": 0,
            "critical_incidents": 0, "resolved_incidents": 0,
        }

    open_mask = incidents["status"].isin(["WATCH", "ACTIVE"])
    return {
        "total_revenue_at_risk_low": _clean(round(float(incidents["revenue_at_risk_low"].sum()), 2)),
        "total_revenue_at_risk_high": _clean(round(float(incidents["revenue_at_risk_high"].sum()), 2)),
        "open_incidents": int(open_mask.sum()),
        "critical_incidents": int((incidents["severity"] == "CRITICAL").sum()),
        "resolved_incidents": int((incidents["status"] == "RESOLVED").sum()),
        "total_incidents": int(len(incidents)),
    }


@router.get("/{incident_id}")
def get_incident(incident_id: str):
    incidents = load_incidents()
    row = incidents[incidents["incident_id"] == incident_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return _serialize(row.iloc[0])


def _get_incident_row(incident_id: str):
    incidents = load_incidents()
    row = incidents[incidents["incident_id"] == incident_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    return row.iloc[0]


@router.get("/{incident_id}/root-cause")
def get_incident_root_cause(incident_id: str):
    """
    Phase 12: which factors (network, bank, device, state, category) show
    the biggest failure-rate jump for this incident, computed live.

    dimensions ranks DIMENSIONS against each other by absolute excess
    failures (apples-to-apples). all_factors is every individually-flagged
    value, kept for anyone who wants the full breakdown, but values across
    different dimensions are NOT comparable to each other on contribution_pct
    (see root_cause.py's module docstring) — the frontend should lead with
    `dimensions`, not `all_factors`.
    """
    incident = _get_incident_row(incident_id)
    transactions = load_transactions()

    result = analyze_incident_root_cause(
        transactions,
        incident_id=incident["incident_id"],
        merchant_id=incident["merchant_id"],
        start_date=incident["start_date"].date(),
        end_date=incident["end_date"].date(),
    )

    if result.note:  # insufficient data to attribute anything
        return {"incident_id": incident_id, "dimensions": [], "all_factors": [], "summary": [], "note": result.note}

    top_dims = result.top_dimensions(3)
    summary = generate_summary_sentences(top_dims)

    for d in top_dims:
        d["baseline_failure_rate"] = _clean(round(d["baseline_failure_rate"], 4)) if d["baseline_failure_rate"] is not None else None
        d["incident_failure_rate"] = _clean(round(d["incident_failure_rate"], 4))

    all_factors = result.top(8)
    return {
        "incident_id": incident_id,
        "dimensions": top_dims,
        "summary": summary,
        "all_factors": [
            {
                "dimension": c.dimension,
                "dimension_label": _DIMENSION_LABELS.get(c.dimension, c.dimension),
                "value": c.value,
                "baseline_failure_rate": _clean(round(c.baseline_failure_rate, 4)) if c.baseline_failure_rate is not None else None,
                "incident_failure_rate": _clean(round(c.incident_failure_rate, 4)),
                "incident_transactions": c.incident_transactions,
                "contribution_pct_within_dimension": _clean(c.contribution_pct),
            }
            for c in all_factors
        ],
        "note": None if top_dims else "No dimension had enough transactions in the incident window to attribute a cause.",
    }


@router.get("/{incident_id}/recovery")
def get_incident_recovery(incident_id: str):
    """Phase 14 recommendation + Phase 15 simulation for this incident. SIMULATION only — no live/test-mode execution exists yet."""
    incident = _get_incident_row(incident_id)
    recommendation = recommend_action(incident)

    payload = {
        "incident_id": incident_id,
        "action": recommendation.action,
        "reason": recommendation.reason,
        "policy": None,
        "simulation": None,
    }

    if recommendation.policy is not None:
        payload["policy"] = {
            "max_retries": recommendation.policy.max_retries,
            "cooldown_minutes": recommendation.policy.cooldown_minutes,
            "eligibility_rules": recommendation.policy.eligibility_rules,
        }

    if recommendation.action == "retry_eligible_failed_payments":
        transactions = load_transactions()
        incident_for_sim = incident.copy()
        incident_for_sim["start_date"] = incident["start_date"].date()
        incident_for_sim["end_date"] = incident["end_date"].date()

        sim = simulate_recovery(transactions, incident_for_sim, recommendation.policy)
        payload["simulation"] = {
            "mode": sim.mode,
            "eligible_count": sim.eligible_count,
            "proposed_retries": sim.proposed_retries,
            "projected_recoverable_amount": _clean(round(sim.projected_recoverable_amount, 2)),
            "successful_recoveries": sim.successful_recoveries,
            "recovered_amount": _clean(round(sim.recovered_amount, 2)),
            "failed_retries": sim.failed_retries,
            "skipped": sim.skipped,
            "retry_success_probability_assumed": sim.retry_success_probability_assumed,
        }

    return payload


@router.post("/{incident_id}/recovery/execute")
def execute_incident_recovery(incident_id: str):
    """
    Actually runs the (simulated) recovery and writes an audit record per
    transaction attempted — this is the step that makes GET /recovery's
    preview a real, recorded action instead of a fresh guess every time
    someone loads the page.
    """
    incident = _get_incident_row(incident_id)
    recommendation = recommend_action(incident)

    if recommendation.action != "retry_eligible_failed_payments":
        raise HTTPException(
            status_code=400,
            detail=f"Nothing to execute — recommended action is '{recommendation.action}', not a retry.",
        )

    transactions = load_transactions()
    incident_for_sim = incident.copy()
    incident_for_sim["start_date"] = incident["start_date"].date()
    incident_for_sim["end_date"] = incident["end_date"].date()

    sim = simulate_recovery(transactions, incident_for_sim, recommendation.policy)

    events = [
        AuditEvent(
            merchant_id=incident["merchant_id"],
            incident_id=incident_id,
            action="retry_eligible_failed_payments",
            reason=recommendation.reason,
            eligibility="eligible",
            decision="approved",
            result=txn["result"],
            amount=float(txn["amount"]),
            mode=sim.mode,
        )
        for txn in sim.per_transaction_results
    ]
    append_audit_events(events)

    return {
        "executed": True,
        "audit_events_written": len(events),
        "mode": sim.mode,
        "successful_recoveries": sim.successful_recoveries,
        "recovered_amount": _clean(round(sim.recovered_amount, 2)),
        "failed_retries": sim.failed_retries,
        "message": f"Executed and recorded {len(events)} recovery attempts in the audit trail.",
    }


@router.get("/{incident_id}/explanation")
def get_incident_explanation(incident_id: str):
    """
    Phase 16 — SHAP-based explanation, a SECOND signal alongside Phase 12's
    statistical root cause. This model was trained to predict the same
    is_anomaly label the statistical detector already produces (Section
    14's "root-cause ranking" layer sits on top of detection, it doesn't
    replace it) — SHAP explains what the MODEL learned to associate with
    an anomaly, in feature terms, which is a different lens than comparing
    raw failure rates across dimensions.
    """
    incidents = load_incidents()
    row = incidents[incidents["incident_id"] == incident_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found.")
    incident = row.iloc[0]

    trained, explainer = _load_model_and_explainer()
    if trained is None:
        return {
            "incident_id": incident_id, "available": False,
            "note": "No trained model found — run `python -m scripts.train_anomaly_model` first.",
        }

    features = _load_model_features()
    if features.empty:
        return {
            "incident_id": incident_id, "available": False,
            "note": "No feature data found — run `python -m scripts.train_anomaly_model` first.",
        }

    detection_date = pd.to_datetime(incident["detection_date"]).date()
    match = features[
        (features["merchant_id"] == incident["merchant_id"]) & (features["date"] == detection_date)
    ]
    if match.empty:
        return {
            "incident_id": incident_id, "available": False,
            "note": f"No feature row for {incident['merchant_id']} on {detection_date} — "
                    "likely too early in that merchant's history for a rolling window to exist.",
        }

    explanation = explain_instance(trained, explainer, match.iloc[0])

    return {
        "incident_id": incident_id,
        "available": True,
        "explained_date": str(detection_date),
        "model_predicted_probability": _clean(round(explanation.predicted_probability, 4)),
        "contributions": [
            {
                "feature": c["feature"],
                "display_name": c["display_name"],
                "value": _clean(round(c["value"], 4)),
                "shap_value": _clean(round(c["shap_value"], 4)),
                "direction": "increases_anomaly_score" if c["shap_value"] > 0 else "decreases_anomaly_score",
            }
            for c in explanation.contributions
        ],
        "note": "SHAP values from a gradient-boosted classifier trained on this dataset's own "
                "anomaly labels — a model-based complement to the statistical root-cause panel "
                "above, not a replacement for it.",
    }