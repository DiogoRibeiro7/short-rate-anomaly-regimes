"""Reconstruct the baseline AR(1) short-rate innovations and audit R1a."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.aggregation_audit import aggregate_daily_to_monthly
from short_rate_anomaly_regimes.data.short_rate_freeze import load_normalized_series
from short_rate_anomaly_regimes.rates.baseline_reconstruction import (
    ARReconstruction,
    classify_replication_target,
    compare_with_published,
    estimate_ar1_reconstruction,
    monthly_rate_from_freeze,
)

RETRIEVAL_DATE = "2026-08-01"
NORMALIZED_ROOT = Path("data/interim/fred")
WINDOW_START = "1972-01"
WINDOW_END = "2013-12"

DIAGNOSTIC_ROOT = Path("artifacts/diagnostics/rates")
TABLE_ROOT = Path("artifacts/tables/factors")
FACTOR_ROOT = Path("data/processed/factors")

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


def main() -> None:
    """Estimate every eligible reconstruction and write the R1a audit artifacts."""
    levels = _load_rate_levels()
    reconstructions: list[ARReconstruction] = []
    comparisons: list[pd.DataFrame] = []
    classifications: list[dict[str, object]] = []

    for series_id, rate in levels.items():
        for variant in ("within_window_lag", "pre_window_lag"):
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
        DIAGNOSTIC_ROOT / "ar1_reconstruction_estimates.csv", index=False
    )
    comparison_frame = pd.concat(comparisons, ignore_index=True)
    comparison_frame.to_csv(TABLE_ROOT / "ar1_published_target_comparison.csv", index=False)
    pd.DataFrame.from_records(classifications).to_csv(
        DIAGNOSTIC_ROOT / "r1a_classification.csv", index=False
    )

    innovation_panel = pd.concat(
        {f"{item.series_id}__{item.timing_variant}": item.innovations for item in reconstructions},
        axis=1,
    ).sort_index()
    innovation_panel.index = pd.PeriodIndex(innovation_panel.index, freq="M").to_timestamp(
        how="start"
    )
    innovation_panel.index.name = "month"
    innovation_panel.to_parquet(FACTOR_ROOT / "short_rate_innovations_baseline.parquet")

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
    )

    print()
    print(comparison_frame.to_string(index=False))
    print()
    print(pd.DataFrame.from_records(classifications).to_string(index=False))


if __name__ == "__main__":
    main()
