"""
Phase 3 — Canonical schema.

Both Demo Mode and uploaded CSVs must converge to this shape before hitting
any analytics. Fields legitimately unavailable in a given source are left
as None rather than fabricated (Section 6).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CanonicalTransaction(BaseModel):
    transaction_id: str
    merchant_id: str
    timestamp: datetime
    amount: float
    status: str  # normalized to "SUCCESS" | "FAILED"
    payment_method: Optional[str] = None
    payment_processor_or_bank: Optional[str] = None
    sender_bank: Optional[str] = None
    receiver_bank: Optional[str] = None
    device_type: Optional[str] = None
    network_type: Optional[str] = None
    state: Optional[str] = None
    merchant_category: Optional[str] = None
    customer_id: Optional[str] = None


CANONICAL_COLUMNS = list(CanonicalTransaction.model_fields.keys())

# Fields that MUST be non-null for any analytics to run.
REQUIRED_CANONICAL_FIELDS = {"transaction_id", "merchant_id", "timestamp", "amount", "status"}

VALID_STATUSES = {"SUCCESS", "FAILED"}
