"""Build and validate the immutable canonical baseline panel."""

from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.aggregation_audit import aggregate_daily_to_monthly
from short_rate_anomaly_regimes.data.baseline_panel import (
    build_baseline_panel,
    validate_baseline_panel,
)
from short_rate_anomaly_regimes.data.french_freeze import load_normalized_french
from short_rate_anomaly_regimes.data.short_rate_freeze import load_normalized_series
from short_rate_anomaly_regimes.exceptions import DataValidationError
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS, load_family_panel
from short_rate_anomaly_regimes.rates.baseline_reconstruction import (
    TimingVariant,
    estimate_ar1_reconstruction,
    monthly_rate_from_freeze,
)

WINDOW_START = "1972-01"
WINDOW_END = "2013-12"

FRED_DATE = "2026-08-01"
FRENCH_VINTAGE = "publication_era_20170709"
PORTFOLIO_VINTAGE = "global_q_2025_retrieved_20260802"
TIMING_VARIANT: TimingVariant = "pre_window_lag"

FRED_ROOT = Path("data/interim/fred")
FRENCH_ROOT = Path("data/interim/kenneth_french")
PORTFOLIO_ROOT = Path("data/interim/portfolios")

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
PANEL_CSV = Path("data/processed/baseline_panel.csv")
COLUMN_METADATA_CSV = Path("artifacts/provenance/baseline_panel_column_metadata.csv")
VALIDATION_JSON = Path("artifacts/data_quality/baseline_panel_validation.json")

SOURCE_VINTAGE_ID = (
    f"fred_{FRED_DATE}|french_{FRENCH_VINTAGE}|globalq_{PORTFOLIO_VINTAGE}|ar1_{TIMING_VARIANT}"
)
REPLICATION_STATUS = "documented_reconstruction"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Assemble the canonical panel, validate it, and write its metadata."""
    factors = load_normalized_french(
        FRENCH_ROOT / f"F-F_Research_Data_Factors_{FRENCH_VINTAGE}.csv"
    )
    market = factors["Mkt-RF"]
    risk_free = factors["RF"]

    levels = {
        "fedfunds": monthly_rate_from_freeze(
            load_normalized_series(FRED_ROOT / f"FEDFUNDS_{FRED_DATE}.csv")
        ),
        "tb3ms": monthly_rate_from_freeze(
            load_normalized_series(FRED_ROOT / f"TB3MS_{FRED_DATE}.csv")
        ),
        "dtb3_monthly_mean": monthly_rate_from_freeze(
            aggregate_daily_to_monthly(
                load_normalized_series(FRED_ROOT / f"DTB3_{FRED_DATE}.csv"),
                rule="available_observation_mean",
            )
        ),
    }

    innovations: dict[str, pd.Series] = {}
    ar_parameters: dict[str, tuple[float, float]] = {}
    for name, series in levels.items():
        reconstruction = estimate_ar1_reconstruction(
            series,
            series_id=name,
            replication_mode=REPLICATION_STATUS,
            timing_variant=TIMING_VARIANT,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
        innovations[name] = reconstruction.innovations
        ar_parameters[name] = (reconstruction.intercept, reconstruction.slope)

    portfolios = {
        family: load_family_panel(PORTFOLIO_ROOT / f"{family}_{PORTFOLIO_VINTAGE}.csv")
        for family in FAMILY_MEMBERS
    }

    panel = build_baseline_panel(
        market_excess_return=market,
        risk_free_return=risk_free,
        short_rate_levels=levels,
        short_rate_innovations=innovations,
        portfolio_returns=portfolios,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )

    report = validate_baseline_panel(
        panel,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        raw_portfolio_returns=portfolios,
        short_rate_levels=levels,
        ar_parameters=ar_parameters,
        market_excess_return=market,
    )

    # Abort before touching any output. Publishing a panel that failed
    # validation, and publishing checksums for it, would put invalid data in
    # front of every downstream analysis. The previous outputs are left in place
    # rather than being replaced by an unvalidated build.
    if not report.passed:
        failed = sorted(name for name, value in report.checks.items() if not value)
        VALIDATION_JSON.parent.mkdir(parents=True, exist_ok=True)
        VALIDATION_JSON.write_text(
            json.dumps(
                {
                    **asdict(report),
                    "passed": False,
                    "source_vintage_id": SOURCE_VINTAGE_ID,
                    "panel_written": False,
                    "failed_checks": failed,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
            newline="\n",
        )
        raise DataValidationError(
            "Canonical panel validation failed; no panel was written. "
            f"Failed checks: {', '.join(failed)}"
        )

    output = panel.copy()
    output.insert(0, "source_vintage_id", SOURCE_VINTAGE_ID)
    output.insert(1, "replication_status", REPLICATION_STATUS)
    output = output.reset_index()
    output["month"] = output["month"].astype(str)

    PANEL_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    for path in (PANEL_PARQUET, PANEL_CSV):
        if path.exists():
            path.unlink()
    output.to_parquet(PANEL_PARQUET, index=False)
    output.to_csv(PANEL_CSV, index=False, lineterminator="\n")

    rows = []
    for column in panel.columns:
        if column == "market_excess_return":
            source, vintage, units, status = (
                "Kenneth French F-F_Research_Data_Factors",
                FRENCH_VINTAGE,
                "percent_per_month",
                "documented_reconstruction; the article names the library without a "
                "file or vintage",
            )
        elif column == "risk_free_return":
            source, vintage, units, status = (
                "Kenneth French F-F_Research_Data_Factors, RF column",
                FRENCH_VINTAGE,
                "percent_per_month",
                "closest to an exact input; the article names the one-month Treasury-bill "
                "return from this library, which maps to a single public series",
            )
        elif column.startswith("short_rate_level__"):
            name = column.split("__")[1]
            source, vintage, units, status = (
                f"FRED {name.upper()}",
                f"fred_current_retrieved_{FRED_DATE}",
                "annualized_percentage_points",
                "documented_reconstruction" if name != "dtb3_monthly_mean" else "sensitivity_only",
            )
        elif column.startswith("short_rate_innovation__"):
            name = column.split("__")[1]
            source, vintage, units, status = (
                f"AR(1) residual of FRED {name.upper()} under {TIMING_VARIANT}",
                f"fred_current_retrieved_{FRED_DATE}",
                "annualized_percentage_points",
                "documented_reconstruction" if name != "dtb3_monthly_mean" else "sensitivity_only",
            )
        else:
            family = column.split("__")[1]
            source, vintage, units, status = (
                f"global-q.org {FAMILY_MEMBERS[family]['member']}",
                PORTFOLIO_VINTAGE,
                "percent_per_month",
                "documented_reconstruction; original author source, current vintage",
            )
        rows.append(
            {
                "column": column,
                "source": source,
                "source_vintage": vintage,
                "units": units,
                "exact_or_reconstructed": status,
            }
        )
    COLUMN_METADATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with COLUMN_METADATA_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    payload = asdict(report)
    payload["passed"] = report.passed
    payload["source_vintage_id"] = SOURCE_VINTAGE_ID
    payload["panel_parquet_sha256"] = _sha256(PANEL_PARQUET)
    payload["panel_csv_sha256"] = _sha256(PANEL_CSV)
    VALIDATION_JSON.parent.mkdir(parents=True, exist_ok=True)
    VALIDATION_JSON.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )

    print(f"Panel: {report.rows} months x {report.columns} columns")
    print(f"Sample: {report.sample_start} .. {report.sample_end}")
    for name, value in sorted(report.checks.items()):
        print(f"  {'PASS' if value else 'FAIL'}  {name}")
    print(f"Overall: {'PASS' if report.passed else 'FAIL'}")
    if report.details.get("repeated_consecutive_return_values") not in {"{}", None}:
        print("  detail:", report.details["repeated_consecutive_return_values"])


if __name__ == "__main__":
    main()
