"""Re-price the cross-section on the article's restricted sample, 1972-01 to 2006-12.

Internet Appendix Section 2.2 reports the results on a sample ending in December
2006. The endpoint matters for this paper in a way it did not for the article:
the excluded eight years contain the financial crisis and the first effective
lower bound, and this reconstruction's own extension work finds the pricing
relation deteriorating after 2013. If the baseline result were an artefact of the
crisis years it should weaken when they are removed.

One convention the appendix leaves open, and which the evidence freeze already
records as an ambiguity: it does not say whether the AR(1) short-rate innovation
is re-estimated on the restricted window or carried over from the full sample.
Both are admissible, so both are run and reported. Choosing one silently would
manufacture a precision the source does not have; running both turns an
undetermined convention into a measured question about whether it matters.

Recovering the re-estimated variant needs the level of the month before the
window, which the canonical panel does not carry, so it is recovered from the
stored level and residual by the same routine the block bootstrap uses.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.block_bootstrap import recover_lagged_level
from short_rate_anomaly_regimes.models.useless_factor_bootstrap import first_pass_by_matrix_ols

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")
OUTPUT_CSV = Path("artifacts/tables/cross_section/restricted_sample.csv")
PROVENANCE_JSON = Path("artifacts/provenance/restricted_sample.json")

#: Internet Appendix Section 2.2.
RESTRICTED_END = "2006-12"

RATES = {
    "fedfunds": ("short_rate_level__fedfunds", "short_rate_innovation__fedfunds"),
    "tb3ms": ("short_rate_level__tb3ms", "short_rate_innovation__tb3ms"),
}

FAMILY_MEMBERS = (
    "book_to_market",
    "earnings_to_price",
    "equity_duration",
    "inventory_growth",
    "investment_to_assets",
    "long_term_reversal",
    "ppe_investment",
)

REPLICATION_STATUS = "documented_reconstruction"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _short_label(column: str) -> str:
    return column.removeprefix("portfolio_excess_return__")


def reestimated_innovation(level: pd.Series, innovation: pd.Series) -> pd.Series:
    """Re-fit the AR(1) on the restricted window under the frozen timing convention.

    The convention regresses each window month on the level of the preceding
    month, including a month before the window for the first observation. That
    lag is recovered from the full-sample level and residual, which identify the
    autoregression exactly, and the AR(1) is then re-fitted using only the
    restricted months.
    """
    lagged = pd.Series(
        recover_lagged_level(level.to_numpy(dtype=float), innovation.to_numpy(dtype=float)),
        index=level.index,
    )
    design = np.column_stack([np.ones(len(level)), lagged.to_numpy(dtype=float)])
    coefficients, *_ = np.linalg.lstsq(design, level.to_numpy(dtype=float), rcond=None)
    return pd.Series(level.to_numpy(dtype=float) - design @ coefficients, index=level.index)


def load_inputs() -> tuple[pd.DataFrame, pd.Series, dict[str, list[str]]]:
    """Load the baseline panel, the market factor, and the registered asset sets."""
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    ).to_timestamp(how="start")
    panel = panel.drop(columns=["month"]).set_axis(index)

    comparators = pd.read_parquet(COMPARATOR_PARQUET)
    comparator_index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in comparators["month"]], freq="M"
    ).to_timestamp(how="start")
    market = comparators.drop(columns=["month"]).set_axis(comparator_index)["RM"]

    asset_sets: dict[str, list[str]] = {
        family: sorted(
            column
            for column in panel.columns
            if column.startswith(f"portfolio_excess_return__{family}__")
        )
        for family in FAMILY_MEMBERS
    }
    asset_sets["all_seven_families_joint"] = sorted(
        column for column in panel.columns if column.startswith("portfolio_excess_return__")
    )
    return panel, market, asset_sets


def main() -> None:
    """Estimate the two-factor system on the restricted sample under both conventions."""
    panel, market, asset_sets = load_inputs()
    cutoff = pd.Period(RESTRICTED_END, freq="M").to_timestamp(how="start")
    restricted = panel.index <= cutoff

    rows: list[dict[str, Any]] = []
    for rate, (level_column, innovation_column) in RATES.items():
        level = panel[level_column].astype(float)
        innovation = panel[innovation_column].astype(float)
        conventions = {
            "carried_over_from_full_sample": innovation[restricted],
            "reestimated_on_restricted_window": reestimated_innovation(
                level[restricted], innovation[restricted]
            ),
        }
        for convention, rate_factor in conventions.items():
            factors = pd.DataFrame({"RM": market[restricted], "rate": rate_factor})
            for asset_set, columns in asset_sets.items():
                excess_returns = panel.loc[restricted, columns].rename(
                    columns={c: _short_label(c) for c in columns}
                )
                betas, residuals = first_pass_by_matrix_ols(excess_returns, factors)
                result = estimate_article_second_pass(
                    mean_excess_returns=excess_returns.mean().rename("mean_return"),
                    betas=betas,
                    residual_covariance=residual_covariance_from_first_pass(residuals),
                    factor_covariance=factors.cov(),
                    n_months=int(restricted.sum()),
                    portfolio_set=asset_set,
                    model=f"market_plus_{rate}",
                )
                rows.append(
                    {
                        "rate": rate,
                        "ar1_convention": convention,
                        "portfolio_set": asset_set,
                        "sample_end": RESTRICTED_END,
                        "n_months": int(restricted.sum()),
                        "lambda_rate": float(result.risk_prices["rate"]),
                        "shanken_t_rate": float(result.shanken_t_statistics["rate"]),
                        "article_cross_sectional_fit": result.article_cross_sectional_fit,
                        "root_mean_squared_pricing_error": (result.root_mean_squared_pricing_error),
                        "replication_status": REPLICATION_STATUS,
                    }
                )

    frame = pd.DataFrame.from_records(rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    print(f"restricted sample: {int(restricted.sum())} months to {RESTRICTED_END}")
    joint = frame.loc[frame["portfolio_set"] == "all_seven_families_joint"]
    for entry in joint.to_dict("records"):
        record = {str(key): value for key, value in entry.items()}
        print(
            f"  {record['rate']:<9} {record['ar1_convention']:<34} "
            f"lambda={float(record['lambda_rate']):+.4f} "
            f"t={float(record['shanken_t_rate']):+.2f} "
            f"fit={float(record['article_cross_sectional_fit']):+.4f}"
        )
    priced = frame.loc[(frame["lambda_rate"] < 0.0) & (frame["shanken_t_rate"] < -1.96)]
    print(f"negative and significant rate price in {len(priced)} of {len(frame)} systems")

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_restricted_sample.py",
                "replication_status": REPLICATION_STATUS,
                "specification": "internet_appendix_section_2_2_restricted_sample",
                "sample_end": RESTRICTED_END,
                "recorded_ambiguity": (
                    "the appendix does not say whether the restricted-sample AR(1) is "
                    "re-estimated on 1972:01-2006:12 or carried over from the full sample, "
                    "which research/publication_evidence_freeze.md already records; both "
                    "are admissible and both are run rather than one being chosen silently"
                ),
                "pre_window_lag": (
                    "the re-estimated variant needs the level of the month before the window, "
                    "which the panel does not carry; it is recovered from the stored level "
                    "and residual, which identify the autoregression exactly"
                ),
                "inputs": {
                    path.as_posix(): _sha256(path) for path in (PANEL_PARQUET, COMPARATOR_PARQUET)
                },
                "outputs": {OUTPUT_CSV.as_posix(): _sha256(OUTPUT_CSV)},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUTPUT_CSV.as_posix()}")


if __name__ == "__main__":
    main()
