"""Acquire publication-era and current Kenneth French factor archives."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.french_freeze import (
    FRENCH_BASE_URL,
    compare_vintages,
    freeze_french_archive,
    load_normalized_french,
)

RAW_ROOT = Path("data/raw/kenneth_french")
NORMALIZED_ROOT = Path("data/interim/kenneth_french")
MANIFEST_ROOT = Path("artifacts/provenance/kenneth_french")
SUMMARY_CSV = Path("artifacts/provenance/french_freeze_summary.csv")
VINTAGE_SUMMARY_CSV = Path("artifacts/data_quality/french_vintage_summary.csv")
VINTAGE_DIFFERENCES_CSV = Path("artifacts/data_quality/french_vintage_differences.csv")
SHARED_FACTOR_CONSISTENCY_CSV = Path("artifacts/data_quality/french_shared_factor_consistency.csv")

HISTORICAL_LABEL = "publication_era_20170709"
CURRENT_LABEL = "current_20260801"

#: Internet Archive snapshots closest to the article's June 2017 publication.
HISTORICAL_SNAPSHOTS = {
    "F-F_Research_Data_Factors": (
        "https://web.archive.org/web/20170709190420id_/"
        f"http://{FRENCH_BASE_URL.split('//')[1]}/F-F_Research_Data_Factors_CSV.zip"
    ),
    "F-F_Momentum_Factor": (
        "https://web.archive.org/web/20170709210520id_/"
        f"http://{FRENCH_BASE_URL.split('//')[1]}/F-F_Momentum_Factor_CSV.zip"
    ),
    "F-F_Research_Data_5_Factors_2x3": (
        "https://web.archive.org/web/20170709190513id_/"
        f"http://{FRENCH_BASE_URL.split('//')[1]}/F-F_Research_Data_5_Factors_2x3_CSV.zip"
    ),
}

ARCHIVE_DATES = {
    "F-F_Research_Data_Factors": "2017-07-09",
    "F-F_Momentum_Factor": "2017-07-09",
    "F-F_Research_Data_5_Factors_2x3": "2017-07-09",
}


def main() -> None:
    """Freeze both vintages of every registered archive and compare them."""
    records = []
    for dataset, historical_url in HISTORICAL_SNAPSHOTS.items():
        for label, url, archive_date in (
            (HISTORICAL_LABEL, historical_url, ARCHIVE_DATES[dataset]),
            (CURRENT_LABEL, f"{FRENCH_BASE_URL}/{dataset}_CSV.zip", "2026-08-01"),
        ):
            record = freeze_french_archive(
                dataset=dataset,
                url=url,
                vintage_label=label,
                archive_date=archive_date,
                raw_root=RAW_ROOT,
                normalized_root=NORMALIZED_ROOT,
                manifest_root=MANIFEST_ROOT,
            )
            records.append(record)
            print(
                f"{dataset:34s} {label:26s} {record.monthly_start}..{record.monthly_end} "
                f"n={record.monthly_observations} cols={list(record.columns)} "
                f"missing={record.missing_value_count} sha={record.raw_sha256[:12]}"
            )

    rows = []
    for record in records:
        row = {
            key: value
            for key, value in asdict(record).items()
            if not isinstance(value, dict | tuple | list)
        }
        row["columns"] = ";".join(record.columns)
        row["missing_value_codes"] = ";".join(str(code) for code in record.missing_value_codes)
        row["source_metadata_lines"] = " | ".join(record.source_metadata_lines)
        row["value_minimum"] = record.value_range["minimum"]
        row["value_maximum"] = record.value_range["maximum"]
        rows.append(row)
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    baseline_window = pd.period_range("1972-01", "2013-12", freq="M")
    summaries = []
    differences = []
    for dataset in HISTORICAL_SNAPSHOTS:
        historical = load_normalized_french(NORMALIZED_ROOT / f"{dataset}_{HISTORICAL_LABEL}.csv")
        current = load_normalized_french(NORMALIZED_ROOT / f"{dataset}_{CURRENT_LABEL}.csv")
        for scope, left, right in (
            ("full_common_sample", historical, current),
            (
                "baseline_window_1972_01_to_2013_12",
                historical.reindex(historical.index.intersection(baseline_window)),
                current.reindex(current.index.intersection(baseline_window)),
            ),
        ):
            summary, difference = compare_vintages(
                historical=left,
                current=right,
                dataset=dataset,
                historical_label=HISTORICAL_LABEL,
                current_label=CURRENT_LABEL,
            )
            summary.insert(1, "scope", scope)
            if not difference.empty:
                difference.insert(1, "scope", scope)
            summaries.append(summary)
            differences.append(difference)

    VINTAGE_SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    summary_frame = pd.concat(summaries, ignore_index=True)
    summary_frame.to_csv(VINTAGE_SUMMARY_CSV, index=False, lineterminator="\n")
    pd.concat(differences, ignore_index=True).to_csv(
        VINTAGE_DIFFERENCES_CSV, index=False, lineterminator="\n"
    )

    consistency = _shared_factor_consistency(baseline_window)
    consistency.to_csv(SHARED_FACTOR_CONSISTENCY_CSV, index=False, lineterminator="\n")

    print()
    print(summary_frame.to_string(index=False))
    print()
    print(consistency.to_string(index=False))
    print()
    print(json.dumps({"summary": str(VINTAGE_SUMMARY_CSV)}, indent=2))


def _shared_factor_consistency(window: pd.PeriodIndex) -> pd.DataFrame:
    """Check whether factors shared by two archives agree within each vintage.

    ``Mkt-RF``, ``SMB``, ``HML``, and ``RF`` appear in both the three-factor and
    the five-factor archive. A factor that is the same series by definition must
    agree between the two files at a given vintage; where it does not, the
    revision counts reported against that vintage are not comparable across the
    two archives. ``SMB`` is expected to differ because the five-factor file
    builds it from the three 2x3 sorts rather than from the three-factor
    construction.

    Args:
        window: Baseline months over which the comparison is made.

    Returns:
        One row per vintage and shared factor.
    """
    rows = []
    for vintage in (HISTORICAL_LABEL, CURRENT_LABEL):
        three = load_normalized_french(NORMALIZED_ROOT / f"F-F_Research_Data_Factors_{vintage}.csv")
        five = load_normalized_french(
            NORMALIZED_ROOT / f"F-F_Research_Data_5_Factors_2x3_{vintage}.csv"
        )
        common = three.index.intersection(five.index).intersection(window)
        for column in ("Mkt-RF", "SMB", "HML", "RF"):
            difference = (three.loc[common, column] - five.loc[common, column]).abs()
            differing = int((difference > 0).sum())
            rows.append(
                {
                    "vintage": vintage,
                    "factor": column,
                    "months_compared": len(common),
                    "months_differing_between_archives": differing,
                    "max_absolute_difference": float(difference.max()),
                    "expected_to_differ": column == "SMB",
                    "verdict": (
                        "identical_between_archives"
                        if differing == 0
                        else (
                            "differs_by_construction_as_expected"
                            if column == "SMB"
                            else "UNEXPECTED_divergence_between_archives"
                        )
                    ),
                }
            )
    return pd.DataFrame.from_records(rows)


if __name__ == "__main__":
    main()
