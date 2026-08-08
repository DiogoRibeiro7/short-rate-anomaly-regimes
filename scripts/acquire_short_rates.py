"""Acquire and freeze the short-rate source series for the baseline milestone."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from short_rate_anomaly_regimes.data.short_rate_freeze import (
    FRED_INTERIM_ROOT,
    FROZEN_FRED_VINTAGE,
    freeze_fred_series,
)

SERIES = ("FEDFUNDS", "TB3MS", "DTB3", "DFF")

RAW_ROOT = Path("data/raw/fred")
MANIFEST_ROOT = Path("artifacts/provenance/short_rate")
SUMMARY_CSV = Path("artifacts/provenance/short_rate_freeze_summary.csv")


def main() -> None:
    """Download each registered short-rate series and write its freeze manifest."""
    records = []
    for series_id in SERIES:
        record = freeze_fred_series(
            series_id=series_id,
            retrieval_date=FROZEN_FRED_VINTAGE,
            raw_root=RAW_ROOT,
            normalized_root=FRED_INTERIM_ROOT,
            manifest_root=MANIFEST_ROOT,
        )
        records.append(record)
        print(
            f"{record.series_id}: {record.observation_count} obs "
            f"{record.observation_start}..{record.observation_end} "
            f"freq_observed={record.frequency_observed} "
            f"missing={record.missing_value_count} raw_sha={record.raw_sha256[:12]}"
        )

    rows = []
    for record in records:
        row = {key: value for key, value in asdict(record).items() if not isinstance(value, dict)}
        row["unit_magnitude_audit"] = json.dumps(record.unit_magnitude_audit, sort_keys=True)
        row["declared_metadata_audit"] = json.dumps(record.declared_metadata_audit, sort_keys=True)
        rows.append(row)
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
