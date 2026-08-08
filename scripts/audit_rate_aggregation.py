"""Verify the monthly aggregation of the frozen short-rate series."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.aggregation_audit import (
    AggregationRule,
    build_aggregation_difference_frame,
    exact_decimal_rounding_check,
    summarise_aggregation,
)
from short_rate_anomaly_regimes.data.short_rate_freeze import (
    FRED_INTERIM_ROOT,
    FROZEN_FRED_VINTAGE,
    load_normalized_series,
)

RAW_ROOT = Path("data/raw/fred")
AUDIT_CSV = Path("artifacts/data_quality/aggregation_audit.csv")
DIFFERENCES_CSV = Path("artifacts/data_quality/aggregation_differences.csv")
DECIMAL_CSV = Path("artifacts/data_quality/aggregation_decimal_check.csv")

COMPARISONS: tuple[tuple[str, str, AggregationRule], ...] = (
    ("FEDFUNDS", "DFF", "calendar_day_mean"),
    ("FEDFUNDS", "DFF", "business_day_mean"),
    ("TB3MS", "DTB3", "available_observation_mean"),
    ("TB3MS", "DTB3", "month_end_last_observation"),
)


def _load(series_id: str) -> pd.Series:
    return load_normalized_series(FRED_INTERIM_ROOT / f"{series_id}_{FROZEN_FRED_VINTAGE}.csv")


def main() -> None:
    """Compute every declared aggregation rule and write the audit artifacts."""
    series = {name: _load(name) for name in {"FEDFUNDS", "TB3MS", "DFF", "DTB3"}}
    difference_frames = []
    summaries = []
    for monthly_id, daily_id, rule in COMPARISONS:
        frame = build_aggregation_difference_frame(
            monthly=series[monthly_id],
            daily=series[daily_id],
            monthly_series_id=monthly_id,
            daily_series_id=daily_id,
            rule=rule,
        )
        difference_frames.append(frame)
        summary = summarise_aggregation(frame)
        summaries.append(asdict(summary))
        print(
            f"{monthly_id} vs {daily_id} [{rule}]: n={summary.complete_months_compared} "
            f"max|d|={summary.max_absolute_difference:.6f} "
            f"share_primary={summary.share_within_primary_tolerance:.4f} "
            f"-> {summary.verdict}"
        )

    decimal_records = []
    for monthly_id, daily_id, rule in COMPARISONS:
        if rule == "month_end_last_observation":
            continue
        check = exact_decimal_rounding_check(
            monthly_raw_path=RAW_ROOT / monthly_id / f"{monthly_id}_{FROZEN_FRED_VINTAGE}.csv",
            daily_raw_path=RAW_ROOT / daily_id / f"{daily_id}_{FROZEN_FRED_VINTAGE}.csv",
            monthly_series_id=monthly_id,
            daily_series_id=daily_id,
            rule=rule,
        )
        row = asdict(check)
        row["mismatched_months"] = ";".join(check.mismatched_months)
        decimal_records.append(row)
        print(
            f"{monthly_id} vs {daily_id} [{rule}] exact decimal: "
            f"{check.exact_decimal_matches}/{check.complete_months_compared} -> {check.verdict}"
        )

    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(summaries).to_csv(AUDIT_CSV, index=False, lineterminator="\n")
    pd.concat(difference_frames, ignore_index=True).to_csv(
        DIFFERENCES_CSV, index=False, lineterminator="\n"
    )
    pd.DataFrame.from_records(decimal_records).to_csv(DECIMAL_CSV, index=False, lineterminator="\n")
    print(f"Wrote {AUDIT_CSV}, {DIFFERENCES_CSV}, and {DECIMAL_CSV}")


if __name__ == "__main__":
    main()
