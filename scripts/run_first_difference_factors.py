"""Re-price the cross-section with first-difference short-rate factors.

Internet Appendix Section 2.1 replaces the AR(1) innovation with the first
difference of the short rate and reports that the results survive. It needs no
new econometrics, only a different factor, and it probes the construction choice
this reconstruction had the most trouble with: the article does not state its
AR(1) timing convention, and recovering it required testing two admissible
variants against the published slopes.

A first difference has no timing convention to recover. It is the change in the
rate over the month, full stop. If the pricing result holds under it as well as
under the AR(1) residual, then the recovered convention is not carrying the
finding, which is worth establishing rather than assuming given how much of the
audit rests on that reconstruction.

Nothing upstream is re-estimated. The rate levels are already in the panel, and
only the factor and the two passes that read it are recomputed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.useless_factor_bootstrap import first_pass_by_matrix_ols

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")
OUTPUT_CSV = Path("artifacts/tables/cross_section/first_difference_factors.csv")
PROVENANCE_JSON = Path("artifacts/provenance/first_difference_factors.json")

#: Each short rate, with the level column the difference is taken from and the
#: AR(1) innovation column the result is compared against.
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
    """Estimate the two-factor system under each short-rate factor definition."""
    panel, market, asset_sets = load_inputs()

    rows: list[dict[str, Any]] = []
    for rate, (level_column, innovation_column) in RATES.items():
        # The first month has no preceding level, so the difference is undefined
        # there. Both definitions are estimated on the same shortened window, so
        # the comparison is not confounded by a one-month sample difference.
        difference = panel[level_column].astype(float).diff()
        window = difference.notna()
        definitions = {
            "first_difference": difference[window],
            "ar1_innovation": panel[innovation_column].astype(float)[window],
        }
        for definition, rate_factor in definitions.items():
            factors = pd.DataFrame({"RM": market[window], "rate": rate_factor})
            for asset_set, columns in asset_sets.items():
                excess_returns = panel.loc[window, columns].rename(
                    columns={c: _short_label(c) for c in columns}
                )
                betas, residuals = first_pass_by_matrix_ols(excess_returns, factors)
                result = estimate_article_second_pass(
                    mean_excess_returns=excess_returns.mean().rename("mean_return"),
                    betas=betas,
                    residual_covariance=residual_covariance_from_first_pass(residuals),
                    factor_covariance=factors.cov(),
                    n_months=int(window.sum()),
                    portfolio_set=asset_set,
                    model=f"market_plus_{rate}_{definition}",
                )
                rows.append(
                    {
                        "rate": rate,
                        "factor_definition": definition,
                        "portfolio_set": asset_set,
                        "n_months": int(window.sum()),
                        "lambda_rate": float(result.risk_prices["rate"]),
                        "shanken_t_rate": float(result.shanken_t_statistics["rate"]),
                        "lambda_market": float(result.risk_prices["RM"]),
                        "article_cross_sectional_fit": result.article_cross_sectional_fit,
                        "root_mean_squared_pricing_error": (result.root_mean_squared_pricing_error),
                        "replication_status": REPLICATION_STATUS,
                    }
                )

    frame = pd.DataFrame.from_records(rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    print("joint seventy portfolios, rate price of risk by factor definition:")
    joint = frame.loc[frame["portfolio_set"] == "all_seven_families_joint"]
    for entry in joint.to_dict("records"):
        record = {str(key): value for key, value in entry.items()}
        print(
            f"  {record['rate']:<9} {record['factor_definition']:<17} "
            f"lambda={float(record['lambda_rate']):+.4f} "
            f"t={float(record['shanken_t_rate']):+.2f} "
            f"fit={float(record['article_cross_sectional_fit']):+.4f}"
        )
    negative_and_significant = frame.loc[
        (frame["lambda_rate"] < 0.0) & (frame["shanken_t_rate"] < -1.96)
    ]
    print(
        f"systems with a negative and significant rate price: "
        f"{len(negative_and_significant)} of {len(frame)}"
    )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_first_difference_factors.py",
                "replication_status": REPLICATION_STATUS,
                "specification": "internet_appendix_section_2_1_first_difference_factor",
                "comparison_rule": (
                    "both factor definitions are estimated on the same window, which drops "
                    "the first month because a first difference is undefined there, so the "
                    "comparison is not confounded by a one-month sample difference"
                ),
                "why": (
                    "the article does not state its AR(1) timing convention and it had to be "
                    "recovered; a first difference has no convention to recover, so agreement "
                    "shows the recovered one is not carrying the result"
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
