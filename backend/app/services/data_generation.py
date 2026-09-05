"""
Phase 2 — Dataset ingestion: raw data generation.

We do not have network access to a data portal (Kaggle etc. are not on the
allowed domain list for this environment), so the "current development data"
described in the build spec (Section 5: 250,000 UPI transactions, 17 columns,
2024 timestamps) is generated synthetically here with a fixed random seed.

This is intentionally the ONLY place randomness is introduced for the base
dataset. Nothing downstream should regenerate or mutate this file — see
`RAW_DATA_DIR` in config.py, which is treated as immutable everywhere else
in the codebase (Section 5: "Keep the raw dataset immutable").

Columns (17), matching the spec:
    transaction_id, timestamp, sender_upi_id, receiver_upi_id, amount,
    transaction_type, merchant_category, status, sender_bank, receiver_bank,
    device_type, network_type, state, fraud_flag, hour, day_of_week,
    is_weekend
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import settings

SEED = 42
N_TRANSACTIONS = 250_000

TRANSACTION_TYPES = ["P2P", "P2M", "bill_payment", "recharge"]
TRANSACTION_TYPE_WEIGHTS = [0.45, 0.35, 0.13, 0.07]

MERCHANT_CATEGORIES = [
    "grocery", "food_delivery", "electronics", "fashion", "utilities",
    "travel", "entertainment", "pharmacy", "fuel", "education",
]

BANKS = [
    "SBI", "HDFC", "ICICI", "Axis", "Kotak", "PNB", "BankOfBaroda",
    "Yes", "IndusInd", "Canara",
]

DEVICE_TYPES = ["Android", "iOS"]
DEVICE_WEIGHTS = [0.78, 0.22]

NETWORK_TYPES = ["4G", "5G", "WiFi", "3G"]
NETWORK_WEIGHTS = [0.55, 0.20, 0.22, 0.03]

STATES = [
    "Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Uttar Pradesh",
    "Gujarat", "West Bengal", "Rajasthan", "Telangana", "Kerala",
]

# Baseline per-bank failure propensity (used only to generate realistic,
# non-uniform base rates — not visible to the detector, which must discover
# patterns from data, not from this generator).
BANK_BASE_FAILURE_RATE = {
    "SBI": 0.052, "HDFC": 0.041, "ICICI": 0.045, "Axis": 0.048,
    "Kotak": 0.043, "PNB": 0.058, "BankOfBaroda": 0.055, "Yes": 0.061,
    "IndusInd": 0.047, "Canara": 0.054,
}


def generate_raw_dataset(n: int = N_TRANSACTIONS, seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)

    timestamps = pd.to_datetime("2024-01-01") + pd.to_timedelta(
        rng.integers(0, 366 * 24 * 3600, size=n), unit="s"
    )

    transaction_type = rng.choice(TRANSACTION_TYPES, size=n, p=TRANSACTION_TYPE_WEIGHTS)
    sender_bank = rng.choice(BANKS, size=n)
    receiver_bank = rng.choice(BANKS, size=n)
    device_type = rng.choice(DEVICE_TYPES, size=n, p=DEVICE_WEIGHTS)
    network_type = rng.choice(NETWORK_TYPES, size=n, p=NETWORK_WEIGHTS)
    state = rng.choice(STATES, size=n)
    merchant_category = rng.choice(MERCHANT_CATEGORIES, size=n)

    # Amount: log-normal, realistic long tail for P2M vs small P2P transfers
    base_amount = rng.lognormal(mean=6.2, sigma=1.1, size=n)
    is_p2m_or_bill = np.isin(transaction_type, ["P2M", "bill_payment"])
    amount = np.where(is_p2m_or_bill, base_amount, base_amount * 0.4).round(2)
    amount = np.clip(amount, 10, 250_000)

    # Failure probability driven by bank + a mild network penalty for 3G/4G,
    # so the base dataset has *some* realistic texture without any injected
    # incidents (those come later, in Phase 10, on a separate copy).
    bank_rate = np.array([BANK_BASE_FAILURE_RATE[b] for b in sender_bank])
    network_penalty = np.where(network_type == "3G", 0.02, 0.0)
    fail_prob = np.clip(bank_rate + network_penalty, 0.01, 0.35)
    status = np.where(
        rng.random(n) < fail_prob, "FAILED", "SUCCESS"
    )

    fraud_flag = (rng.random(n) < 0.003).astype(int)

    transaction_id = np.array([f"TXN{i:08d}" for i in range(n)])

    df = pd.DataFrame({
        "transaction_id": transaction_id,
        "timestamp": timestamps,
        "sender_upi_id": [f"user{u}@upi" for u in rng.integers(0, 60_000, size=n)],
        "receiver_upi_id": [f"merchant{u}@upi" for u in rng.integers(0, 5_000, size=n)],
        "amount": amount,
        "transaction_type": transaction_type,
        "merchant_category": merchant_category,
        "status": status,
        "sender_bank": sender_bank,
        "receiver_bank": receiver_bank,
        "device_type": device_type,
        "network_type": network_type,
        "state": state,
        "fraud_flag": fraud_flag,
        "hour": timestamps.hour,
        "day_of_week": timestamps.dayofweek,
        "is_weekend": (timestamps.dayofweek >= 5).astype(int),
    })

    return df.sort_values("timestamp").reset_index(drop=True)


def ensure_raw_dataset_exists(force: bool = False) -> str:
    """Writes the raw dataset to disk if it doesn't already exist."""
    settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = settings.RAW_DATA_DIR / "upi_transactions_raw.csv"

    if out_path.exists() and not force:
        return str(out_path)

    df = generate_raw_dataset()
    df.to_csv(out_path, index=False)
    return str(out_path)


if __name__ == "__main__":
    path = ensure_raw_dataset_exists(force=True)
    print(f"Wrote raw dataset to {path}")
