"""
Phase 9 — Incident engine.

Turns Phase 8's day-level anomaly points into incidents (Section 11): a
single burst of overlapping/adjacent anomalous days should be ONE incident,
not one alert per day. This also assigns lifecycle states and computes
revenue-at-risk using the excess-failures methodology from Section 12 (not
"all failed transaction value").

Grouping rule: anomalous days for the same merchant within
MAX_GAP_DAYS_TO_MERGE of each other are merged into a single incident.

States (Section 11):
    WATCH      — a single anomalous window, not yet persistent
    ACTIVE     — persisted for >= MIN_PERSISTENCE_DAYS anomalous days
    RECOVERING — was ACTIVE, but the most recent observed day(s) returned
                 toward baseline
    RESOLVED   — the merchant's failure rate has been back at/below
                 baseline for >= RESOLUTION_QUIET_DAYS since the incident
    (NORMAL is the absence of an incident, not a state ever stored here.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from app.services.baseline import compute_baseline
from app.services.revenue import compute_revenue_at_risk

MAX_GAP_DAYS_TO_MERGE = 2  # anomalous days this close together are one incident
MIN_PERSISTENCE_DAYS = 2  # anomalous days needed to escalate WATCH -> ACTIVE
RESOLUTION_QUIET_DAYS = 3  # consecutive non-anomalous days needed to call it RESOLVED
MIN_TRANSACTIONS_FOR_RESOLUTION_CHECK = 10  # pooled evidence floor for the quiet-period check

# Revenue-at-risk uncertainty band lives in app.services.revenue now.


@dataclass
class Incident:
    incident_id: str
    merchant_id: str
    start_date: date
    detection_date: date  # first date the anomaly was statistically confirmed
    end_date: date  # last anomalous date seen so far
    duration_days: int
    baseline_failure_rate: float
    incident_failure_rate: float
    peak_failure_rate: float
    failed_transactions: int
    expected_failures: float
    excess_failures: float
    revenue_at_risk_low: float
    revenue_at_risk_high: float
    severity: str  # "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
    confidence: float  # 1 - min(p_value) across constituent anomaly points
    detection_delay_days: int  # start_date -> detection_date
    status: str  # WATCH | ACTIVE | RECOVERING | RESOLVED
    anomalous_days: list = field(default_factory=list)


def _severity_from_excess(excess_pp: float) -> str:
    if excess_pp >= 15:
        return "CRITICAL"
    if excess_pp >= 8:
        return "HIGH"
    if excess_pp >= 4:
        return "MEDIUM"
    return "LOW"


def _group_anomalous_dates(dates: list[date], max_gap_days: int) -> list[list[date]]:
    """Groups a sorted list of dates into clusters where consecutive dates
    are at most `max_gap_days` apart."""
    if not dates:
        return []

    groups: list[list[date]] = [[dates[0]]]
    for d in dates[1:]:
        if (d - groups[-1][-1]).days <= max_gap_days:
            groups[-1].append(d)
        else:
            groups.append([d])
    return groups


def _group_by_window_overlap(
    points: pd.DataFrame, max_gap_days: int
) -> list[pd.DataFrame]:
    """
    Groups anomaly points by the overlap of their DETECTION WINDOWS, not
    just their flagged calendar date. A point flagged on day D using a
    7-day window actually carries evidence from [D - 6, D]; if that span
    overlaps (or nearly touches) another point's span, they're evidence of
    the same underlying event and must be merged into one incident —
    otherwise a wide window can "re-detect" the tail of an incident already
    captured under an earlier point and produce a second, spurious incident
    (exactly what Section 11 warns against).
    """
    points = points.copy().sort_values("date").reset_index(drop=True)
    points["window_start"] = points.apply(
        lambda r: r["date"] - timedelta(days=int(r["window_days"]) - 1), axis=1
    )

    groups: list[list[int]] = [[0]]
    group_end = points.loc[0, "date"]

    for i in range(1, len(points)):
        row_start = points.loc[i, "window_start"]
        if (row_start - group_end).days <= max_gap_days:
            groups[-1].append(i)
            group_end = max(group_end, points.loc[i, "date"])
        else:
            groups.append([i])
            group_end = points.loc[i, "date"]

    return [points.loc[idxs] for idxs in groups]


def build_incidents_for_merchant(
    anomaly_points: pd.DataFrame,
    daily_metrics: pd.DataFrame,
    merchant_id: str,
    avg_transaction_value: float | None = None,
) -> list[Incident]:
    """
    anomaly_points: output of anomaly_detection.detect_anomalies_for_merchant
    (or the 'all_merchants' variant, pre-filtered to this merchant).
    """
    merchant_anomalies = anomaly_points[
        (anomaly_points["merchant_id"] == merchant_id) & (anomaly_points["is_anomaly"])
    ].copy()
    if merchant_anomalies.empty:
        return []

    merchant_anomalies["date"] = pd.to_datetime(merchant_anomalies["date"]).dt.date
    merchant_anomalies = merchant_anomalies.sort_values("date")

    point_groups = _group_by_window_overlap(merchant_anomalies, MAX_GAP_DAYS_TO_MERGE)

    merchant_daily = daily_metrics[daily_metrics["merchant_id"] == merchant_id].copy()
    merchant_daily["date"] = pd.to_datetime(merchant_daily["date"]).dt.date

    if avg_transaction_value is None:
        avg_transaction_value = float(merchant_daily["average_transaction_value"].mean())

    incidents: list[Incident] = []
    for i, group_points in enumerate(point_groups):
        group_dates = group_points["date"].tolist()

        # The incident spans from the EARLIEST evidence window's start (not
        # just the earliest flagged date) through the last flagged date —
        # this is what actually distinguishes a merged, window-overlapping
        # group from a set of independent single-day flags.
        start_date = group_points["window_start"].min()
        end_date = max(group_dates)
        duration_days = (end_date - start_date).days + 1

        # Actual observed behavior across the full incident span (not just
        # the flagged days) — this is what "incident_failure_rate" means.
        span_rows = merchant_daily[
            (merchant_daily["date"] >= start_date) & (merchant_daily["date"] <= end_date)
        ]
        failed_transactions = int(span_rows["failure_count"].sum())
        total_transactions = int(span_rows["transaction_count"].sum())
        incident_failure_rate = failed_transactions / total_transactions if total_transactions else 0.0
        peak_failure_rate = float(span_rows["failure_rate"].max()) if not span_rows.empty else 0.0

        baseline_rate = float(group_points["baseline_failure_rate"].mean())
        expected_failures = baseline_rate * total_transactions
        excess_failures = max(0.0, failed_transactions - expected_failures)

        rar = compute_revenue_at_risk(excess_failures, avg_transaction_value)
        revenue_at_risk_low, revenue_at_risk_high = rar.low_estimate, rar.high_estimate

        excess_pp = (incident_failure_rate - baseline_rate) * 100
        severity = _severity_from_excess(excess_pp)

        confidence = 1 - float(group_points["p_value"].min())
        detection_date = start_date if len(group_dates) < MIN_PERSISTENCE_DAYS else group_dates[MIN_PERSISTENCE_DAYS - 1]
        detection_delay = (detection_date - start_date).days

        status = "ACTIVE" if len(group_dates) >= MIN_PERSISTENCE_DAYS else "WATCH"

        # Check for recovery/resolution using data AFTER the last anomalous
        # day. Pooled (not day-by-day) so a single failure on a near-empty
        # day can't look "still elevated" purely from a tiny denominator —
        # the same volume-awareness principle as the detector itself.
        post_incident = merchant_daily[merchant_daily["date"] > end_date].sort_values("date")
        if not post_incident.empty:
            quiet_days = post_incident.head(RESOLUTION_QUIET_DAYS)
            quiet_n = int(quiet_days["transaction_count"].sum())
            quiet_failures = int(quiet_days["failure_count"].sum())
            quiet_rate = quiet_failures / quiet_n if quiet_n >= MIN_TRANSACTIONS_FOR_RESOLUTION_CHECK else None

            if quiet_rate is None:
                pass  # not enough post-incident evidence yet — leave status as ACTIVE/WATCH
            elif len(quiet_days) >= RESOLUTION_QUIET_DAYS and quiet_rate <= baseline_rate * 1.5:
                status = "RESOLVED"
            elif quiet_rate <= baseline_rate * 1.5:
                status = "RECOVERING"

        incidents.append(Incident(
            incident_id=f"INC-{merchant_id}-{i + 1:03d}",
            merchant_id=merchant_id,
            start_date=start_date,
            detection_date=detection_date,
            end_date=end_date,
            duration_days=duration_days,
            baseline_failure_rate=baseline_rate,
            incident_failure_rate=incident_failure_rate,
            peak_failure_rate=peak_failure_rate,
            failed_transactions=failed_transactions,
            expected_failures=expected_failures,
            excess_failures=excess_failures,
            revenue_at_risk_low=revenue_at_risk_low,
            revenue_at_risk_high=revenue_at_risk_high,
            severity=severity,
            confidence=confidence,
            detection_delay_days=detection_delay,
            status=status,
            anomalous_days=group_dates,
        ))

    return incidents


_INCIDENT_COLUMNS = [
    "incident_id", "merchant_id", "start_date", "detection_date", "end_date",
    "duration_days", "baseline_failure_rate", "incident_failure_rate",
    "peak_failure_rate", "failed_transactions", "expected_failures",
    "excess_failures", "revenue_at_risk_low", "revenue_at_risk_high",
    "severity", "confidence", "detection_delay_days", "status", "anomalous_days",
]


def build_incidents_all_merchants(
    anomaly_points: pd.DataFrame, daily_metrics: pd.DataFrame
) -> pd.DataFrame:
    all_incidents: list[Incident] = []
    for merchant_id in sorted(anomaly_points["merchant_id"].unique()):
        all_incidents.extend(
            build_incidents_for_merchant(anomaly_points, daily_metrics, merchant_id)
        )

    if not all_incidents:
        # A columnless empty DataFrame writes an unparseable CSV (pandas
        # raises EmptyDataError trying to read it back) — genuinely
        # possible on real uploaded data with no detectable incidents, not
        # just a theoretical edge case (caught via a live upload test).
        # Keep the schema even when there's nothing to report.
        return pd.DataFrame(columns=_INCIDENT_COLUMNS)

    rows = [
        {**vars(inc), "anomalous_days": ",".join(str(d) for d in inc.anomalous_days)}
        for inc in all_incidents
    ]
    return pd.DataFrame(rows)
