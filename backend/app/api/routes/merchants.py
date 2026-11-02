from __future__ import annotations

import math

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.storage.repositories import load_daily_metrics, load_incidents, load_merchant_metrics, load_transactions
from app.services.metrics import compute_dimension_failure_rates, compute_daily_merchant_metrics

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


_BREAKDOWN_DIMENSIONS = {
    "receiver_bank": "Receiving Bank",
    "network_type": "Network",
    "device_type": "Device",
    "state": "Customer State",
    "merchant_category": "Merchant Category",
}
_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@router.get("/{merchant_id}/analytics")
def get_merchant_analytics(
    merchant_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Phase 30 — Payment Analytics page data. Everything needed for the
    charts: the daily time series (reused from daily-metrics) plus
    breakdowns by bank/network/device/state/category/hour/day-of-week,
    each with a real failure_rate so a bar chart can show "which slice is
    worse than average", not just raw counts.

    start_date/end_date (YYYY-MM-DD, inclusive) filter BOTH the time series
    and the breakdowns to that range — a date filter that only truncated
    the chart while leaving "which bank is worst" computed over the whole
    year would be misleading (Section 30: "Provide date filters").
    """
    transactions = load_transactions()
    merchant_tx = transactions[transactions["merchant_id"] == merchant_id].copy()
    if merchant_tx.empty:
        raise HTTPException(status_code=404, detail=f"No transactions for {merchant_id}.")

    merchant_tx["timestamp"] = pd.to_datetime(merchant_tx["timestamp"])

    if start_date:
        merchant_tx = merchant_tx[merchant_tx["timestamp"].dt.date >= pd.Timestamp(start_date).date()]
    if end_date:
        merchant_tx = merchant_tx[merchant_tx["timestamp"].dt.date <= pd.Timestamp(end_date).date()]
    if merchant_tx.empty:
        raise HTTPException(status_code=404, detail=f"No transactions for {merchant_id} in that date range.")

    merchant_tx["hour"] = merchant_tx["timestamp"].dt.hour
    merchant_tx["day_of_week"] = merchant_tx["timestamp"].dt.dayofweek

    breakdowns = {}
    for dim, label in _BREAKDOWN_DIMENSIONS.items():
        rates = compute_dimension_failure_rates(merchant_tx, dim)
        breakdowns[dim] = {
            "label": label,
            "values": [
                {
                    "value": str(row[dim]),
                    "transaction_count": int(row["transaction_count"]),
                    "failure_count": int(row["failure_count"]),
                    "failure_rate": _clean(round(float(row["failure_rate"]), 4)),
                }
                for _, row in rates.iterrows()
            ],
        }

    hour_rates = compute_dimension_failure_rates(merchant_tx, "hour").sort_values("hour")
    breakdowns["hour"] = {
        "label": "Hour of Day",
        "values": [
            {
                "value": f"{int(row['hour']):02d}:00",
                "transaction_count": int(row["transaction_count"]),
                "failure_count": int(row["failure_count"]),
                "failure_rate": _clean(round(float(row["failure_rate"]), 4)),
            }
            for _, row in hour_rates.iterrows()
        ],
    }

    dow_rates = compute_dimension_failure_rates(merchant_tx, "day_of_week").sort_values("day_of_week")
    breakdowns["day_of_week"] = {
        "label": "Day of Week",
        "values": [
            {
                "value": _DAY_NAMES[int(row["day_of_week"])],
                "transaction_count": int(row["transaction_count"]),
                "failure_count": int(row["failure_count"]),
                "failure_rate": _clean(round(float(row["failure_rate"]), 4)),
            }
            for _, row in dow_rates.iterrows()
        ],
    }

    daily_metrics = compute_daily_merchant_metrics(merchant_tx)

    return {
        "merchant_id": merchant_id,
        "date_range_applied": {"start_date": start_date, "end_date": end_date},
        "daily": [
            {
                "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
                "transaction_count": int(row["transaction_count"]),
                "failure_count": int(row["failure_count"]),
                "failure_rate": _clean(round(float(row["failure_rate"]), 4)),
                "transaction_volume": _clean(round(float(row["transaction_volume"]), 2)),
                "average_transaction_value": _clean(round(float(row["average_transaction_value"]), 2)),
                "failed_amount": _clean(round(float(row["failed_amount"]), 2)),
            }
            for _, row in daily_metrics.sort_values("date").iterrows()
        ],
        "breakdowns": breakdowns,
    }