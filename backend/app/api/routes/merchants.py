from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.storage.repositories import load_daily_metrics, load_incidents, load_merchant_metrics

router = APIRouter(prefix="/merchants", tags=["merchants"])


def _clean(value):
    """Replace NaN/inf with None so FastAPI's JSON encoder doesn't choke."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _merchant_health_score(failure_rate: float, active_incidents: int) -> int:
    """
    Simple, documented health score (Section 29): starts at 100, loses
    points for elevated failure rate and for currently-open incidents.
    Not a trained model — a transparent, explainable formula, which is the
    right choice for something a merchant will see and needs to trust.
    """
    score = 100
    score -= min(60, failure_rate * 100 * 6)  # each 1pp of failure costs 6 points, capped at 60
    score -= min(25, active_incidents * 12.5)  # each open incident costs 12.5 points, capped at 25
    return max(0, round(score))


@router.get("")
def list_merchants():
    summary = load_merchant_metrics()
    incidents = load_incidents()

    if summary.empty:
        raise HTTPException(status_code=503, detail="Merchant data not available yet.")

    open_counts = (
        incidents[incidents["status"].isin(["WATCH", "ACTIVE"])]
        .groupby("merchant_id")
        .size()
        if not incidents.empty else pd.Series(dtype=int)
    )

    rows = []
    for _, r in summary.iterrows():
        open_incidents = int(open_counts.get(r["merchant_id"], 0))
        rows.append({
            "merchant_id": r["merchant_id"],
            "transaction_count": int(r["transaction_count"]),
            "failure_rate": _clean(round(float(r["failure_rate"]), 4)),
            "transaction_volume": _clean(round(float(r["transaction_volume"]), 2)),
            "average_transaction_value": _clean(round(float(r["average_transaction_value"]), 2)),
            "open_incidents": open_incidents,
            "health_score": _merchant_health_score(float(r["failure_rate"]), open_incidents),
        })

    return sorted(rows, key=lambda r: r["merchant_id"])


@router.get("/{merchant_id}")
def get_merchant(merchant_id: str):
    summary = load_merchant_metrics()
    row = summary[summary["merchant_id"] == merchant_id]
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Merchant {merchant_id} not found.")

    incidents = load_incidents()
    open_incidents = 0
    if not incidents.empty:
        open_incidents = int(
            (
                (incidents["merchant_id"] == merchant_id)
                & incidents["status"].isin(["WATCH", "ACTIVE"])
            ).sum()
        )

    r = row.iloc[0]
    return {
        "merchant_id": merchant_id,
        "transaction_count": int(r["transaction_count"]),
        "failure_rate": round(float(r["failure_rate"]), 4),
        "transaction_volume": round(float(r["transaction_volume"]), 2),
        "average_transaction_value": round(float(r["average_transaction_value"]), 2),
        "open_incidents": open_incidents,
        "health_score": _merchant_health_score(float(r["failure_rate"]), open_incidents),
    }


@router.get("/{merchant_id}/daily-metrics")
def get_merchant_daily_metrics(merchant_id: str):
    daily = load_daily_metrics()
    merchant_daily = daily[daily["merchant_id"] == merchant_id].sort_values("date")
    if merchant_daily.empty:
        raise HTTPException(status_code=404, detail=f"No daily metrics for {merchant_id}.")

    return [
        {
            "date": row["date"].strftime("%Y-%m-%d"),
            "transaction_count": int(row["transaction_count"]),
            "failure_count": int(row["failure_count"]),
            "failure_rate": _clean(round(float(row["failure_rate"]), 4)),
            "transaction_volume": _clean(round(float(row["transaction_volume"]), 2)),
        }
        for _, row in merchant_daily.iterrows()
    ]
