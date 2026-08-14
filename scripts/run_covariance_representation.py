"""Estimate the ICAPM in expected return-covariance form, Internet Appendix 2.8.

Equation (3) prices the cross-section on factor *covariances* rather than on
multiple-regression betas, and equation (4) gives the GMM system that estimates
it. The appendix states that first-stage GMM with equally weighted moments "is
conceptually equivalent to running an OLS cross-sectional regression of average
excess returns on factor covariances", and that the pricing errors and fit are
"defined analogously to the formulas presented in Section 3 of the paper".

Unlike the Kan-Robotti-Shanken statistics of Table A.8, none of this rests on
code the appendix cites without publishing: the moment conditions are printed and
the two derived statistics are defined by reference to equations this project
already implements.

The appendix also makes a prediction worth testing rather than assuming: "As
expected, the R2 estimates are the same as in the benchmark test of the beta
pricing equation." That is an identity, not a coincidence. Multiple-regression
betas satisfy ``C = B Sigma_f`` with ``Sigma_f`` invertible, so the covariance
design and the beta design span the same column space; the no-intercept OLS
projection is therefore the same, the pricing errors are the same, and the fit is
the same. Only the coefficients differ, by ``gamma = Sigma_f^-1 lambda``.

Both routes are computed here and required to agree, which turns the appendix's
"as expected" into a check on this reconstruction rather than a claim inherited
from it.

What is deliberately not produced: t-ratios. The appendix obtains them from the
GMM covariance matrix, which accounts for estimation error in the factor means
through the last two moment conditions. That is a different standard error from
the Shanken one this project implements, and reporting the latter under a GMM
heading would be a substitution rather than a reconstruction.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import article_cross_sectional_fit
from short_rate_anomaly_regimes.models.useless_factor_bootstrap import first_pass_by_matrix_ols

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")
OUTPUT_CSV = Path("artifacts/tables/cross_section/covariance_representation.csv")
PROVENANCE_JSON = Path("artifacts/provenance/covariance_representation.json")

MODELS: dict[str, tuple[str, ...]] = {
    "market_plus_fedfunds_innovation": ("RM", "FFR_innovation"),
    "market_plus_tbill_innovation": ("RM", "TB_innovation"),
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


def covariance_risk_prices(
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
) -> tuple[pd.Series, pd.Series, float]:
    """Price the cross-section on factor covariances, returning prices, errors and fit."""
    returns = excess_returns.to_numpy(dtype=float)
    factor_matrix = factors.to_numpy(dtype=float)
    centred_factors = factor_matrix - factor_matrix.mean(axis=0)
    centred_returns = returns - returns.mean(axis=0)
    # Cov(R_i, f_k) with the same divisor pandas uses, so the design matches the
    # factor covariance the beta route divides by.
    covariances = centred_returns.T @ centred_factors / (len(excess_returns) - 1)

    mean_returns = excess_returns.mean().to_numpy(dtype=float)
    gram = covariances.T @ covariances
    prices = np.linalg.solve(gram, covariances.T @ mean_returns)
    errors = mean_returns - covariances @ prices

    error_series = pd.Series(errors, index=excess_returns.columns, name="pricing_error")
    return (
        pd.Series(prices, index=factors.columns, name="covariance_risk_price"),
        error_series,
        article_cross_sectional_fit(excess_returns.mean().rename("mean_return"), error_series),
    )


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    """Load the panel, the factor panel and the registered asset sets."""
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    ).to_timestamp(how="start")
    panel = panel.drop(columns=["month"]).set_axis(index)

    comparators = pd.read_parquet(COMPARATOR_PARQUET)
    comparator_index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in comparators["month"]], freq="M"
    ).to_timestamp(how="start")
    factors = comparators.drop(columns=["month"]).set_axis(comparator_index)
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
    return panel, factors, asset_sets


def main() -> None:
    """Estimate the covariance representation and check it against the beta one."""
    panel, factors, asset_sets = load_inputs()

    rows: list[dict[str, Any]] = []
    for model, factor_names in MODELS.items():
        model_factors = factors[list(factor_names)]
        factor_covariance = model_factors.cov().to_numpy(dtype=float)
        for asset_set, columns in asset_sets.items():
            excess_returns = panel[columns].rename(columns={c: _short_label(c) for c in columns})
            prices, errors, fit = covariance_risk_prices(excess_returns, model_factors)

            # The beta route, for the identity the appendix predicts.
            betas, _ = first_pass_by_matrix_ols(excess_returns, model_factors)
            beta_matrix = betas.to_numpy(dtype=float)
            mean_returns = excess_returns.mean().to_numpy(dtype=float)
            beta_prices = np.linalg.solve(beta_matrix.T @ beta_matrix, beta_matrix.T @ mean_returns)
            implied = np.linalg.solve(factor_covariance, beta_prices)
            beta_errors = mean_returns - beta_matrix @ beta_prices

            record: dict[str, Any] = {
                "model": model,
                "portfolio_set": asset_set,
                "n_assets": len(columns),
                "article_cross_sectional_fit": fit,
                # Both are recorded so the identity is auditable from the artifact
                # rather than only from the test suite.
                "max_abs_price_gap_against_transform": float(
                    np.max(np.abs(prices.to_numpy(dtype=float) - implied))
                ),
                "max_abs_pricing_error_gap_against_beta_route": float(
                    np.max(np.abs(errors.to_numpy(dtype=float) - beta_errors))
                ),
                "replication_status": REPLICATION_STATUS,
            }
            for factor in factor_names:
                record[f"gamma_{factor}"] = float(prices[factor])
            rows.append(record)

    frame = pd.DataFrame.from_records(rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    print("covariance risk prices, joint seventy portfolios:")
    joint = frame.loc[frame["portfolio_set"] == "all_seven_families_joint"]
    for entry in joint.to_dict("records"):
        record = {str(key): value for key, value in entry.items()}
        # The frame unions the gamma columns across models, so a row carries a
        # NaN for the rate it does not price. Selecting the first gamma column
        # printed that NaN; the populated one is the model's own.
        rate = next(
            key
            for key, value in record.items()
            if key.startswith("gamma_") and key != "gamma_RM" and pd.notna(value)
        )
        fit = float(record["article_cross_sectional_fit"])
        print(
            f"  {record['model']:<32} gamma_market={float(record['gamma_RM']):+.5f} "
            f"{rate}={float(record[rate]):+.5f} fit={fit:+.4f}"
        )
    print(
        "largest gap against the beta route: "
        f"prices {frame['max_abs_price_gap_against_transform'].max():.3e}, "
        f"pricing errors {frame['max_abs_pricing_error_gap_against_beta_route'].max():.3e}"
    )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_covariance_representation.py",
                "replication_status": REPLICATION_STATUS,
                "specification": "internet_appendix_equation_3_and_4_covariance_representation",
                "estimator": (
                    "first-stage GMM with equally weighted moments, which the appendix states "
                    "is equivalent to the OLS cross-sectional regression of average excess "
                    "returns on factor covariances, and which is computed as that regression"
                ),
                "identity_checked": (
                    "the covariance and beta designs span the same column space because "
                    "C = B Sigma_f, so pricing errors and fit are identical and the prices "
                    "satisfy gamma = Sigma_f^-1 lambda; both routes are computed and the "
                    "artifact records the gap between them"
                ),
                "not_produced": (
                    "t-ratios. The appendix takes them from the GMM covariance, which accounts "
                    "for estimation error in the factor means through the last two moment "
                    "conditions; the Shanken standard errors implemented here are a different "
                    "object and are not substituted for them"
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
