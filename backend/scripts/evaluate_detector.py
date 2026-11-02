"""
Phase 11 — Automated detector evaluation.

Scores incidents.csv (produced by scripts/compute_incidents.py, which had
zero knowledge of ground_truth_incidents.csv — see Section 17: "the
detector must discover the incident rather than being hardcoded") against
the 6 injected scenarios from Phase 10.

SCOPE LIMITATION (read before the numbers): the anomaly detector (Phase 8)
only evaluates FAILURE RATE. Scenario D is a transaction-VOLUME drop, not a
failure-rate change, and is structurally outside what this detector can
find — a volume-anomaly detector is a distinct, not-yet-built capability
(Section 8 lists "rolling volume" as a feature to add later). Its recall is
reported as 0 by design, not measured as a failure of this detector.

MATCHING RULE:
  - Merchant-specific ground truth (merchant_id != "*"): detected if any
    row in incidents.csv for that merchant overlaps the ground-truth date
    range.
  - Dataset-wide ground truth (merchant_id == "*" — a bank or network
    degrading across every merchant): our detector only operates
    per-merchant, so a shared cause has to show up as several merchants
    independently flagging incidents around the same time. Detected if at
    least MIN_MERCHANTS_FOR_DATASET_WIDE_MATCH merchants have an
    overlapping incident.

WHY NO PORTFOLIO-WIDE PRECISION: precision would require knowing, for
EVERY detected incident, whether it's a true or false alarm. We only have
ground truth for the 6 injected windows — the other ~100 detected
incidents are real statistical anomalies in data that intentionally has
per-bank/network baseline variance (see data_generation.py); we have no
label for whether each one is "real" degradation or noise. Reporting a
precision number built on treating all of them as false positives would be
fabricated confidence (Section 16), so this script reports scenario-level
recall and detection delay only, and separately shows how many incidents
fell outside every ground-truth window without calling them false
positives.

Run:
    python -m scripts.evaluate_detector
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.config import settings

MIN_MERCHANTS_FOR_DATASET_WIDE_MATCH = 3


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start <= b_end and b_start <= a_end


def _to_date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.date


def evaluate_merchant_specific(gt_row: pd.Series, incidents: pd.DataFrame) -> dict:
    merchant_incidents = incidents[incidents["merchant_id"] == gt_row["merchant_id"]]
    matches = merchant_incidents[
        merchant_incidents.apply(
            lambda r: _overlaps(r["start_date"], r["end_date"], gt_row["start_date"], gt_row["end_date"]),
            axis=1,
        )
    ]

    if matches.empty:
        return {
            "incident_id": gt_row["incident_id"],
            "incident_type": gt_row["incident_type"],
            "detected": False,
            "matched_incident_ids": "",
            "detection_delay_days": None,
            "note": f"No incident found for {gt_row['merchant_id']} overlapping "
                    f"{gt_row['start_date']}..{gt_row['end_date']}.",
        }

    earliest = matches.loc[matches["start_date"].idxmin()]
    delay = (earliest["start_date"] - gt_row["start_date"]).days
    return {
        "incident_id": gt_row["incident_id"],
        "incident_type": gt_row["incident_type"],
        "detected": True,
        "matched_incident_ids": ",".join(matches["incident_id"]),
        "detection_delay_days": delay,
        "note": f"Matched {len(matches)} incident(s) for {gt_row['merchant_id']}.",
    }


def evaluate_dataset_wide(gt_row: pd.Series, incidents: pd.DataFrame) -> dict:
    matched_per_merchant = []
    for merchant_id, group in incidents.groupby("merchant_id"):
        overlap = group[
            group.apply(
                lambda r: _overlaps(r["start_date"], r["end_date"], gt_row["start_date"], gt_row["end_date"]),
                axis=1,
            )
        ]
        if not overlap.empty:
            matched_per_merchant.append((merchant_id, overlap["start_date"].min(), overlap["incident_id"].tolist()))

    n_matched = len(matched_per_merchant)
    detected = n_matched >= MIN_MERCHANTS_FOR_DATASET_WIDE_MATCH

    if n_matched == 0:
        delay = None
    else:
        delays = [(start - gt_row["start_date"]).days for _, start, _ in matched_per_merchant]
        delay = sum(delays) / len(delays)

    return {
        "incident_id": gt_row["incident_id"],
        "incident_type": gt_row["incident_type"],
        "detected": detected,
        "matched_incident_ids": ",".join(mid for _, _, ids in matched_per_merchant for mid in ids),
        "detection_delay_days": delay,
        "note": f"{n_matched} merchant(s) showed an overlapping incident "
                f"(threshold: {MIN_MERCHANTS_FOR_DATASET_WIDE_MATCH}).",
    }


def evaluate_volume_scenario(gt_row: pd.Series) -> dict:
    return {
        "incident_id": gt_row["incident_id"],
        "incident_type": gt_row["incident_type"],
        "detected": False,
        "matched_incident_ids": "",
        "detection_delay_days": None,
        "note": "Out of scope for the current failure-rate detector — a transaction-volume "
                "drop needs a separate volume-anomaly check (not yet built). Not counted as a miss.",
    }


def main() -> None:
    ground_truth = pd.read_csv(
        settings.PROCESSED_DATA_DIR / "ground_truth_incidents.csv",
        parse_dates=["start_date", "end_date"],
    )
    ground_truth["start_date"] = _to_date(ground_truth["start_date"])
    ground_truth["end_date"] = _to_date(ground_truth["end_date"])

    incidents = pd.read_csv(
        settings.PROCESSED_DATA_DIR / "incidents.csv",
        parse_dates=["start_date", "end_date"],
    )
    incidents["start_date"] = _to_date(incidents["start_date"])
    incidents["end_date"] = _to_date(incidents["end_date"])

    results = []
    for _, gt_row in ground_truth.iterrows():
        if gt_row["incident_type"] == "volume_anomaly":
            results.append(evaluate_volume_scenario(gt_row))
        elif gt_row["merchant_id"] == "*":
            results.append(evaluate_dataset_wide(gt_row, incidents))
        else:
            results.append(evaluate_merchant_specific(gt_row, incidents))

    results_df = pd.DataFrame(results)

    in_scope = results_df[results_df["note"].str.contains("Out of scope") == False]
    n_in_scope = len(in_scope)
    n_detected = int(in_scope["detected"].sum())
    recall_in_scope = n_detected / n_in_scope if n_in_scope else float("nan")

    detected_delays = in_scope.loc[in_scope["detected"], "detection_delay_days"].dropna()
    mean_delay = detected_delays.mean() if not detected_delays.empty else None

    matched_ids = set()
    for ids in results_df["matched_incident_ids"]:
        matched_ids.update(i for i in ids.split(",") if i)
    n_unmatched_incidents = len(incidents) - len(matched_ids)

    print("=" * 60)
    print("METRIVA DETECTOR EVALUATION (Phase 11)")
    print("=" * 60)
    print(f"Ground-truth scenarios: {len(ground_truth)}")
    print(f"In scope for the current (failure-rate) detector: {n_in_scope}")
    print(f"Detected: {n_detected}/{n_in_scope}  (recall, in-scope only: {recall_in_scope:.1%})")
    print(f"Mean detection delay (detected scenarios): "
          f"{f'{mean_delay:.1f} days' if mean_delay is not None else 'n/a'}")
    print()
    print(results_df.to_string(index=False))
    print()
    print(f"Total incidents detected across the dataset: {len(incidents)}")
    print(f"  - matched to a ground-truth scenario: {len(matched_ids)}")
    print(f"  - not matched to any injected scenario: {n_unmatched_incidents} "
          f"(background statistical variance intentionally present in the synthetic "
          f"data's per-bank/network baselines — NOT reported as false positives, since "
          f"we have no day-level ground truth for the rest of the dataset to score them against)")

    out_path = settings.PROCESSED_DATA_DIR / "evaluation_report.csv"
    results_df.to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
