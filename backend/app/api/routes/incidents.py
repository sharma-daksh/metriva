from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException, Query

from app.storage.repositories import load_incidents

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


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
