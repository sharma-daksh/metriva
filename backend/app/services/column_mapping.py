"""
Phase 20 — Upload column mapping.

Guesses which uploaded column corresponds to each canonical field (Section
39: "show the mapping to the user"), using common naming aliases. This is
a SUGGESTION only — the user confirms or corrects it before anything is
processed. Fields with no confident match are left unmapped rather than
guessed, per Section 6: "Do not fabricate customer identity or payment
fields just to fill the schema."
"""
from __future__ import annotations

from app.models.schemas import CANONICAL_COLUMNS

# Canonical field -> lowercase aliases we'll recognize in an uploaded header.
FIELD_ALIASES: dict[str, list[str]] = {
    "transaction_id": ["transaction_id", "txn_id", "payment_id", "id", "order_id"],
    "merchant_id": ["merchant_id", "merchant", "merchant_name", "store_id", "seller_id"],
    "timestamp": ["timestamp", "created_at", "date", "datetime", "txn_date", "transaction_date"],
    "amount": ["amount", "amt", "value", "txn_amount", "payment_amount"],
    "status": ["status", "payment_state", "txn_status", "state", "result"],
    "payment_method": ["payment_method", "method", "payment_type", "mode"],
    "payment_processor_or_bank": ["processor", "payment_processor", "gateway", "acquirer"],
    "sender_bank": ["sender_bank", "payer_bank", "from_bank"],
    "receiver_bank": ["receiver_bank", "payee_bank", "to_bank", "bank"],
    "device_type": ["device_type", "device", "platform"],
    "network_type": ["network_type", "network", "connection_type"],
    "state": ["state", "region", "customer_state"],
    "merchant_category": ["merchant_category", "category", "mcc"],
    "customer_id": ["customer_id", "user_id", "payer_id", "sender_id"],
}


def suggest_mapping(uploaded_columns: list[str]) -> dict[str, str | None]:
    """
    Returns {canonical_field: uploaded_column_name | None}. Matching is
    case-insensitive, exact-alias only (no fuzzy distance) — a wrong-but-
    confident-looking guess is worse than leaving a field unmapped for the
    user to fill in by hand.
    """
    normalized = {col.strip().lower(): col for col in uploaded_columns}
    mapping: dict[str, str | None] = {}

    for canonical_field in CANONICAL_COLUMNS:
        aliases = FIELD_ALIASES.get(canonical_field, [canonical_field])
        match = None
        for alias in aliases:
            if alias in normalized:
                match = normalized[alias]
                break
        mapping[canonical_field] = match

    return mapping