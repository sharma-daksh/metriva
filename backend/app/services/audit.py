"""
Phase 21 — Recovery audit trail (Section 23).

Every recovery action (currently: simulated retries) writes an
append-only, timestamped record here — who/what decided, what was
attempted, what happened. This is what makes "the system recommended and
executed X" a checkable claim rather than a black box.

Append-only by design: audit_log.csv is never rewritten or filtered in
place, only appended to.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone

import pandas as pd

from app.config import settings

AUDIT_LOG_COLUMNS = [
    "timestamp", "merchant_id", "incident_id", "action", "reason",
    "eligibility", "decision", "result", "amount", "actor", "mode",
]


@dataclass
class AuditEvent:
    merchant_id: str
    incident_id: str
    action: str
    reason: str
    eligibility: str
    decision: str
    result: str
    amount: float
    actor: str = "system"
    mode: str = "SIMULATION"
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


def append_audit_events(events: list[AuditEvent]) -> None:
    if not events:
        return
    path = settings.PROCESSED_DATA_DIR / "audit_log.csv"
    new_rows = pd.DataFrame([asdict(e) for e in events])[AUDIT_LOG_COLUMNS]

    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, new_rows], ignore_index=True)
    else:
        combined = new_rows

    settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(path, index=False)


def load_audit_log() -> pd.DataFrame:
    path = settings.PROCESSED_DATA_DIR / "audit_log.csv"
    if not path.exists():
        return pd.DataFrame(columns=AUDIT_LOG_COLUMNS)
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=AUDIT_LOG_COLUMNS)