"""Estimate the second pass with an unrestricted zero-beta rate.

Internet Appendix Section 2.5 re-runs the cross-sectional regression with an
intercept and asks whether the zero-beta rate differs from the average risk-free
rate. The article uses the answer as a misspecification check, and reports that
its own model passes while the alternative factor models do not: "the estimates
for lambda_0 assume larger values (above 1% per month) and are statistically
above the average risk-free rate in most cases (namely for the CAPM, FF3, PS4,
and HXZ4 models). This suggests a misspecification of those factor models."

That claim matters here more than it does in the article. This reconstruction
finds that every registered traded comparator attains a lower in-sample pricing
error than the short-rate model, and the zero-beta test is the article's own
counterweight to exactly that comparison. Reconstructing it establishes whether
the counterweight survives in this reconstruction rather than assuming it does.

Nothing is re-estimated. The first-pass betas, the residual covariance inputs and
the mean returns are already stored; only the second pass is re-run, with an
intercept.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_zero_beta_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.useless_factor_bootstrap import first_pass_by_matrix_ols

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")
OUTPUT_CSV = Path("artifacts/tables/cross_section/zero_beta_second_pass.csv")
PROVENANCE_JSON = Path("artifacts/provenance/zero_beta_second_pass.json")

MODELS: dict[str, tuple[str, ...]] = {
    "capm": ("RM",),
    "market_plus_fedfunds_innovation": ("RM", "FFR_innovation"),
    "market_plus_tbill_innovation": ("RM", "TB_innovation"),
    "fama_french_3": ("RM", "SMB", "HML"),
    "carhart_4": ("RM", "SMB", "HML", "UMD"),
    "fama_french_5": ("RM", "SMB", "HML", "RMW", "CMA"),
    "q_factor": ("RM", "ME", "IA", "ROE"),
    "liquidity": ("RM", "SMB", "HML", "LIQ"),
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


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]], float]:
    """Load the panel, the factors, the asset sets, and the average bill return."""
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    ).to_timestamp(how="start")
    panel = panel.drop(columns=["month"]).set_axis(index)

    comparators = pd.read_parquet(COMPARATOR_PARQUET)
    comparator_index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in comparators["month"]], freq="M"
    ).to_timestamp(how="start")
    comparators = comparators.drop(columns=["month"]).set_axis(comparator_index)

    factors = comparators.copy()
    factors["FFR_innovation"] = panel["short_rate_innovation__fedfunds"]
    factors["TB_innovation"] = panel["short_rate_innovation__tb3ms"]

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
    mean_risk_free = float(panel["risk_free_return"].astype(float).mean())
    return panel, factors, asset_sets, mean_risk_free


def main() -> None:
    """Estimate the zero-beta second pass for every registered system."""
    panel, factors, asset_sets, mean_risk_free = load_inputs()
    months = len(panel)

    rows: list[dict[str, Any]] = []
    for model, factor_names in MODELS.items():
        model_factors = factors[list(factor_names)]
        for asset_set, columns in asset_sets.items():
            excess_returns = panel[columns].rename(columns={c: _short_label(c) for c in columns})
            betas, residuals = first_pass_by_matrix_ols(excess_returns, model_factors)
            result = estimate_zero_beta_second_pass(
                mean_excess_returns=excess_returns.mean().rename("mean_return"),
                betas=betas,
                residual_covariance=residual_covariance_from_first_pass(residuals),
                factor_covariance=model_factors.cov(),
                n_months=months,
                portfolio_set=asset_set,
                model=model,
                mean_risk_free_return=mean_risk_free,
            )
            record: dict[str, Any] = {
                "model": model,
                "portfolio_set": asset_set,
                "n_assets": result.n_assets,
                "excess_zero_beta_rate": result.excess_zero_beta_rate,
                "excess_zero_beta_t_statistic": result.excess_zero_beta_t_statistic,
                "zero_beta_rate_level": result.zero_beta_rate_level,
                "article_cross_sectional_fit": result.article_cross_sectional_fit,
                "chi_square_statistic": result.chi_square_statistic,
                "chi_square_asymptotic_p_value": result.chi_square_asymptotic_p_value,
                "replication_status": REPLICATION_STATUS,
            }
            for factor in factor_names:
                record[f"lambda_{factor}"] = float(result.risk_prices[factor])
                record[f"shanken_t_{factor}"] = float(result.shanken_t_statistics[factor])
            rows.append(record)

    frame = pd.DataFrame.from_records(rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    joint = frame.loc[frame["portfolio_set"] == "all_seven_families_joint"]
    print(f"average risk-free return: {mean_risk_free:.4f} per month")
    print("joint seventy-portfolio systems, excess zero-beta rate:")
    for entry in joint.to_dict("records"):
        record = {str(key): value for key, value in entry.items()}
        significant = abs(float(record["excess_zero_beta_t_statistic"])) > 1.96
        print(
            f"  {record['model']!s:<32} "
            f"lambda_0={float(record['excess_zero_beta_rate']):+.4f} "
            f"t={float(record['excess_zero_beta_t_statistic']):+.2f} "
            f"{'significant' if significant else 'not significant'}"
        )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_zero_beta_second_pass.py",
                "replication_status": REPLICATION_STATUS,
                "specification": "internet_appendix_equation_1_unrestricted_intercept",
                "tested_null": (
                    "the zero-beta rate in excess of the average one-month bill return is "
                    "zero, which is the intercept of the excess-return regression"
                ),
                "level_convention": (
                    "the article regresses total returns; total and excess returns differ by "
                    "the average bill return, which is common to every asset and absorbed by "
                    "the intercept, so slopes, pricing errors and fit are identical and only "
                    "the intercept shifts. Both readings are reported."
                ),
                "mean_risk_free_return": mean_risk_free,
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
