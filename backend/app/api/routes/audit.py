"""
Phase 21 — Audit trail route (Section 38: Recovery Audit page).
"""
from __future__ import annotations

import math

from fastapi import APIRouter, Query

from app.services.audit import load_audit_log

router = APIRouter(prefix="/audit", tags=["audit"])


def _clean(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


@router.get("")
def list_audit_events(
    incident_id: str | None = None,
    merchant_id: str | None = None,
    limit: int = Query(default=200, le=2000),
):
    log = load_audit_log()
    if incident_id:
        log = log[log["incident_id"] == incident_id]
    if merchant_id:
        log = log[log["merchant_id"] == merchant_id]

    log = log.sort_values("timestamp", ascending=False).head(limit)

    return [
        {
            "timestamp": row["timestamp"],
            "merchant_id": row["merchant_id"],
            "incident_id": row["incident_id"],
            "action": row["action"],
            "reason": row["reason"],
            "eligibility": row["eligibility"],
            "decision": row["decision"],
            "result": row["result"],
            "amount": _clean(round(float(row["amount"]), 2)),
            "actor": row["actor"],
            "mode": row["mode"],
        }
        for _, row in log.iterrows()
    ]