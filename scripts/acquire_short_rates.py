"""Acquire and verify the short-rate source series for the baseline milestone.

By default this is a verification run: each series is downloaded, hashed, and
compared against the ``raw_sha256`` recorded in
``artifacts/provenance/short_rate``. A mismatch aborts the run and leaves the
recorded hash untouched. Passing ``--update-vintage`` is the only way to record a
different vintage, and it rewrites those manifests.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from short_rate_anomaly_regimes.data.short_rate_freeze import (
    FRED_INTERIM_ROOT,
    FROZEN_FRED_VINTAGE,
    freeze_fred_series,
)
from short_rate_anomaly_regimes.data.vintage import (
    VintageMode,
    announce_mode,
    parse_vintage_mode,
)

SERIES = ("FEDFUNDS", "TB3MS", "DTB3", "DFF")

RAW_ROOT = Path("data/raw/fred")
MANIFEST_ROOT = Path("artifacts/provenance/short_rate")
SUMMARY_CSV = Path("artifacts/provenance/short_rate_freeze_summary.csv")


def main(argv: Sequence[str] | None = None) -> None:
    """Verify each registered short-rate series against its frozen vintage."""
    mode = parse_vintage_mode(argv, description=__doc__)
    print(announce_mode(mode))
    records = []
    for series_id in SERIES:
        record = freeze_fred_series(
            series_id=series_id,
            retrieval_date=FROZEN_FRED_VINTAGE,
            raw_root=RAW_ROOT,
            normalized_root=FRED_INTERIM_ROOT,
            manifest_root=MANIFEST_ROOT,
            mode=mode,
        )
        records.append(record)
        print(
            f"{record.series_id}: {record.observation_count} obs "
            f"{record.observation_start}..{record.observation_end} "
            f"freq_observed={record.frequency_observed} "
            f"missing={record.missing_value_count} raw_sha={record.raw_sha256[:12]}"
        )

    if mode is not VintageMode.UPDATE:
        print(
            f"Verified {len(records)} series against the frozen vintage; "
            f"{MANIFEST_ROOT.as_posix()} and {SUMMARY_CSV.as_posix()} were not rewritten"
        )
        return

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
