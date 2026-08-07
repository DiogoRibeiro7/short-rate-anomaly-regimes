"""Reconstruct the baseline AR(1) short-rate innovations and audit R1a.

The derived innovation panel is written together with a companion provenance
record so that the panel bytes, the frozen inputs they were built from, the
timing variants, the estimation window, and the AR specification can never be
separated from one another.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from short_rate_anomaly_regimes.data.aggregation_audit import aggregate_daily_to_monthly
from short_rate_anomaly_regimes.data.short_rate_freeze import load_normalized_series
from short_rate_anomaly_regimes.exceptions import DataValidationError
from short_rate_anomaly_regimes.provenance import sha256_file
from short_rate_anomaly_regimes.rates.baseline_reconstruction import (
    ARReconstruction,
    TimingVariant,
    classify_replication_target,
    compare_with_published,
    estimate_ar1_reconstruction,
    monthly_rate_from_freeze,
)

SCRIPT_NAME = "scripts/reconstruct_rate_innovations.py"

RETRIEVAL_DATE = "2026-08-01"
NORMALIZED_ROOT = Path("data/interim/fred")
FREEZE_MANIFEST_ROOT = Path("artifacts/provenance/short_rate")
WINDOW_START = "1972-01"
WINDOW_END = "2013-12"

DIAGNOSTIC_ROOT = Path("artifacts/diagnostics/rates")
TABLE_ROOT = Path("artifacts/tables/factors")
FACTOR_ROOT = Path("data/processed/factors")
INNOVATION_PARQUET = FACTOR_ROOT / "short_rate_innovations_baseline.parquet"
INNOVATION_PROVENANCE_JSON = Path("artifacts/provenance/short_rate_innovations_baseline.json")

#: Frozen normalized inputs, in the order the level series are derived from them.
INPUT_SERIES_IDS: tuple[str, ...] = ("FEDFUNDS", "TB3MS", "DTB3")

#: Timing variants estimated for every eligible level series.
TIMING_VARIANTS: tuple[TimingVariant, ...] = ("within_window_lag", "pre_window_lag")

#: The estimated specification, stated once and recorded with the panel.
AR_MODEL = {
    "specification": "r_t = a + rho * r_{t-1} + u_t",
    "order": 1,
    "estimator": "ordinary_least_squares",
    "innovation_definition": "u_t, the residual of the fitted AR(1) level equation",
    "level_units": "percent_per_annum",
    "daily_aggregation_rule_for_DTB3": "available_observation_mean",
}

#: Article page 935 AR equations and article page 936 Table 1 Panel A.
PUBLISHED_TARGETS: dict[str, dict[str, float]] = {
    "FEDFUNDS": {
        "intercept": 0.000,
        "slope": 0.991,
        "t_intercept": 0.99,
        "t_slope": 147.26,
        "r_squared": 0.98,
        "mean": 0.00,
        "standard_deviation": 0.59,
        "minimum": -6.51,
        "maximum": 3.15,
        "autocorrelation_1": 0.40,
    },
    "TB3MS": {
        "intercept": 0.000,
        "slope": 0.992,
        "t_intercept": 0.89,
        "t_slope": 153.18,
        "r_squared": 0.98,
        "mean": 0.00,
        "standard_deviation": 0.49,
        "minimum": -4.54,
        "maximum": 2.69,
        "autocorrelation_1": 0.33,
    },
}

REPLICATION_MODE = {
    "FEDFUNDS": "documented_reconstruction",
    "TB3MS": "documented_reconstruction",
    "DTB3_MONTHLY_MEAN": "sensitivity_only",
}


def _verified_input(series_id: str) -> dict[str, str]:
    """Verify one frozen normalized input against its freeze manifest.

    Args:
        series_id: FRED series identifier of the frozen input.

    Returns:
        The normalized path, its verified SHA-256 digest, the vintage label, and
        the manifest path the digest was checked against.

    Raises:
        DataValidationError: If the manifest or the file is missing, the manifest
            names a different normalized path, or the checksums disagree.
    """
    normalized_path = NORMALIZED_ROOT / f"{series_id}_{RETRIEVAL_DATE}.csv"
    manifest_path = FREEZE_MANIFEST_ROOT / f"{series_id}_{RETRIEVAL_DATE}.json"
    if not manifest_path.is_file():
        raise DataValidationError(f"Frozen manifest is missing: {manifest_path}")
    if not normalized_path.is_file():
        raise DataValidationError(f"Frozen input is missing: {normalized_path}")
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded_path = str(manifest.get("normalized_path", ""))
    if recorded_path != normalized_path.as_posix():
        raise DataValidationError(
            f"Manifest {manifest_path} records normalized_path={recorded_path!r} "
            f"but this reconstruction reads {normalized_path.as_posix()!r}"
        )
    expected = str(manifest.get("normalized_sha256", ""))
    observed = sha256_file(normalized_path)
    if not expected or observed != expected:
        raise DataValidationError(
            f"Checksum mismatch for {normalized_path}: manifest {manifest_path} records "
            f"{expected!r} but the file on disk hashes to {observed}. The frozen input has "
            f"been altered or replaced; refusing to derive an innovation panel from it."
        )
    return {
        "series_id": series_id,
        "normalized_path": normalized_path.as_posix(),
        "normalized_sha256": observed,
        "vintage_label": str(manifest.get("vintage_label", "")),
        "manifest": manifest_path.as_posix(),
    }


def _load_rate_levels() -> dict[str, pd.Series]:
    fedfunds = monthly_rate_from_freeze(
        load_normalized_series(NORMALIZED_ROOT / f"FEDFUNDS_{RETRIEVAL_DATE}.csv")
    )
    tb3ms = monthly_rate_from_freeze(
        load_normalized_series(NORMALIZED_ROOT / f"TB3MS_{RETRIEVAL_DATE}.csv")
    )
    dtb3_daily = load_normalized_series(NORMALIZED_ROOT / f"DTB3_{RETRIEVAL_DATE}.csv")
    dtb3_monthly = monthly_rate_from_freeze(
        aggregate_daily_to_monthly(dtb3_daily, rule="available_observation_mean")
    )
    return {
        "FEDFUNDS": fedfunds,
        "TB3MS": tb3ms,
        "DTB3_MONTHLY_MEAN": dtb3_monthly,
    }


def _record_row(reconstruction: ARReconstruction) -> dict[str, object]:
    row = {
        key: value
        for key, value in asdict(reconstruction).items()
        if key not in {"innovations", "descriptives", "diagnostics", "unit_scale_audit"}
    }
    for prefix, payload in (
        ("descriptive", reconstruction.descriptives),
        ("diagnostic", reconstruction.diagnostics),
        ("unit_audit", reconstruction.unit_scale_audit),
    ):
        for key, value in payload.items():
            row[f"{prefix}_{key}"] = value
    return row


def _write_innovation_provenance(
    *,
    panel: pd.DataFrame,
    verified_inputs: list[dict[str, str]],
) -> None:
    record = {
        "script": SCRIPT_NAME,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "output_path": INNOVATION_PARQUET.as_posix(),
        "output_sha256": sha256_file(INNOVATION_PARQUET),
        "output_format": "parquet",
        "columns": [str(column) for column in panel.columns],
        "index_name": str(panel.index.name),
        "index_convention": "month-start timestamp",
        "rows": len(panel),
        "index_start": str(panel.index.min().date()),
        "index_end": str(panel.index.max().date()),
        "non_null_by_column": {
            str(column): int(panel[column].notna().sum()) for column in panel.columns
        },
        "estimation_window": {
            "start": WINDOW_START,
            "end": WINDOW_END,
            "frequency": "M",
            "months": len(pd.period_range(WINDOW_START, WINDOW_END, freq="M")),
        },
        "timing_variants": list(TIMING_VARIANTS),
        "ar_model": AR_MODEL,
        "replication_mode_by_series": dict(REPLICATION_MODE),
        "inputs": verified_inputs,
    }
    INNOVATION_PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    INNOVATION_PROVENANCE_JSON.write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )


def main() -> None:
    """Estimate every eligible reconstruction and write the R1a audit artifacts.

    Raises:
        DataValidationError: If any frozen normalized input fails its manifest
            checksum.
    """
    verified_inputs = [_verified_input(series_id) for series_id in INPUT_SERIES_IDS]
    levels = _load_rate_levels()
    reconstructions: list[ARReconstruction] = []
    comparisons: list[pd.DataFrame] = []
    classifications: list[dict[str, object]] = []

    for series_id, rate in levels.items():
        for variant in TIMING_VARIANTS:
            reconstruction = estimate_ar1_reconstruction(
                rate,
                series_id=series_id,
                replication_mode=REPLICATION_MODE[series_id],
                timing_variant=variant,
                window_start=WINDOW_START,
                window_end=WINDOW_END,
            )
            reconstructions.append(reconstruction)
            print(
                f"{series_id:20s} {variant:17s} n={reconstruction.regression_observations} "
                f"a={reconstruction.intercept: .6f} (t={reconstruction.intercept_t_ratio: .2f}) "
                f"rho={reconstruction.slope:.6f} (t={reconstruction.slope_t_ratio:.2f}) "
                f"R2={reconstruction.r_squared:.4f} "
                f"sd(u)={reconstruction.descriptives['standard_deviation']:.4f}"
            )
            published = PUBLISHED_TARGETS.get(series_id)
            if published is None:
                classifications.append(
                    {
                        "series_id": series_id,
                        "timing_variant": variant,
                        "replication_mode": REPLICATION_MODE[series_id],
                        "exact_input_available": False,
                        "r1a_classification": "not_attempted_no_published_target_for_this_series",
                        "note": (
                            "The article never reports an AR(1) for a daily-aggregated "
                            "Treasury-bill series, so there is no published target to audit."
                        ),
                    }
                )
                continue
            comparison = compare_with_published(reconstruction, published)
            comparisons.append(comparison)
            classification = classify_replication_target(
                comparison,
                replication_mode=REPLICATION_MODE[series_id],
                exact_input_available=False,
            )
            classifications.append(
                {
                    "series_id": series_id,
                    "timing_variant": variant,
                    "replication_mode": REPLICATION_MODE[series_id],
                    "exact_input_available": False,
                    "r1a_classification": classification,
                    "note": (
                        "The article names a provider without a series code or vintage, "
                        "so no rate reconstruction is eligible for an exact-replication label."
                    ),
                }
            )

    for path in (DIAGNOSTIC_ROOT, TABLE_ROOT, FACTOR_ROOT):
        path.mkdir(parents=True, exist_ok=True)

    pd.DataFrame.from_records([_record_row(item) for item in reconstructions]).to_csv(
        DIAGNOSTIC_ROOT / "ar1_reconstruction_estimates.csv", index=False, lineterminator="\n"
    )
    comparison_frame = pd.concat(comparisons, ignore_index=True)
    comparison_frame.to_csv(
        TABLE_ROOT / "ar1_published_target_comparison.csv", index=False, lineterminator="\n"
    )
    pd.DataFrame.from_records(classifications).to_csv(
        DIAGNOSTIC_ROOT / "r1a_classification.csv", index=False, lineterminator="\n"
    )

    innovation_panel = pd.concat(
        {f"{item.series_id}__{item.timing_variant}": item.innovations for item in reconstructions},
        axis=1,
    ).sort_index()
    innovation_panel.index = pd.PeriodIndex(innovation_panel.index, freq="M").to_timestamp(
        how="start"
    )
    innovation_panel.index.name = "month"
    innovation_panel.to_parquet(INNOVATION_PARQUET)
    _write_innovation_provenance(panel=innovation_panel, verified_inputs=verified_inputs)

    (DIAGNOSTIC_ROOT / "ar1_reconstruction_diagnostics.json").write_text(
        json.dumps(
            {
                f"{item.series_id}__{item.timing_variant}": {
                    "descriptives": item.descriptives,
                    "diagnostics": item.diagnostics,
                    "unit_scale_audit": item.unit_scale_audit,
                }
                for item in reconstructions
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print()
    print(comparison_frame.to_string(index=False))
    print()
    print(pd.DataFrame.from_records(classifications).to_string(index=False))
    print()
    print(f"Wrote {INNOVATION_PARQUET} and {INNOVATION_PROVENANCE_JSON}")


if __name__ == "__main__":
    main()
