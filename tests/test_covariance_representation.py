"""Tests for the expected return-covariance representation, Internet Appendix 2.8."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.run_covariance_representation import covariance_risk_prices

from short_rate_anomaly_regimes.models.useless_factor_bootstrap import first_pass_by_matrix_ols

RESULTS = Path("artifacts/tables/cross_section/covariance_representation.csv")


def _panel(
    n_assets: int = 15, n_months: int = 300, seed: int = 5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    index = pd.period_range("1980-01", periods=n_months, freq="M").to_timestamp(how="start")
    factors = pd.DataFrame(
        {
            "market": rng.normal(0.5, 4.0, n_months),
            "rate": rng.normal(0.0, 0.6, n_months),
        },
        index=index,
    )
    loadings = rng.normal(1.0, 0.3, n_assets)
    rate_loadings = rng.normal(0.0, 0.8, n_assets)
    returns = {
        f"asset_{i:02d}": loadings[i] * factors["market"]
        + rate_loadings[i] * factors["rate"]
        + rng.normal(0.4, 2.0, n_months)
        for i in range(n_assets)
    }
    return pd.DataFrame(returns, index=index), factors


def test_the_two_representations_price_identically() -> None:
    """The appendix predicts identical fit; it is an identity, and is checked as one.

    Multiple-regression betas satisfy C = B Sigma_f, so the covariance design and
    the beta design span the same column space. The no-intercept projection is
    therefore the same and the pricing errors are the same. If this failed, one
    of the two designs would not be what it claims to be.
    """
    returns, factors = _panel()
    prices, errors, _fit = covariance_risk_prices(returns, factors)

    betas, _ = first_pass_by_matrix_ols(returns, factors)
    beta_matrix = betas.to_numpy(dtype=float)
    mean_returns = returns.mean().to_numpy(dtype=float)
    beta_prices = np.linalg.solve(beta_matrix.T @ beta_matrix, beta_matrix.T @ mean_returns)
    beta_errors = mean_returns - beta_matrix @ beta_prices

    np.testing.assert_allclose(errors.to_numpy(dtype=float), beta_errors, atol=1e-10)
    implied = np.linalg.solve(factors.cov().to_numpy(dtype=float), beta_prices)
    np.testing.assert_allclose(prices.to_numpy(dtype=float), implied, rtol=1e-8)


def test_the_covariance_price_is_the_beta_price_scaled_by_the_factor_covariance() -> None:
    """gamma = Sigma_f^-1 lambda, so the two differ by a known transform and nothing else."""
    returns, factors = _panel(seed=9)
    prices, _, _ = covariance_risk_prices(returns, factors)

    betas, _ = first_pass_by_matrix_ols(returns, factors)
    beta_matrix = betas.to_numpy(dtype=float)
    mean_returns = returns.mean().to_numpy(dtype=float)
    beta_prices = np.linalg.solve(beta_matrix.T @ beta_matrix, beta_matrix.T @ mean_returns)

    recovered = factors.cov().to_numpy(dtype=float) @ prices.to_numpy(dtype=float)
    np.testing.assert_allclose(recovered, beta_prices, rtol=1e-8)


def test_the_generated_artifact_records_the_identity_holding() -> None:
    """The artifact carries the gap, so the identity is auditable without the tests."""
    if not RESULTS.is_file():
        pytest.skip("the covariance representation is not generated in this checkout")
    frame = pd.read_csv(RESULTS)

    assert (frame["max_abs_price_gap_against_transform"] < 1e-8).all()
    assert (frame["max_abs_pricing_error_gap_against_beta_route"] < 1e-8).all()


def test_the_sign_pattern_matches_the_appendix_description() -> None:
    """The appendix reports a near-zero market price and a strongly negative rate price.

    Its words are that "the covariance risk price estimates for the market factor
    are largely insignificant" while "the covariance risk prices for the hedging
    factors are negative". The magnitudes differ by orders of magnitude here,
    which is what that description implies.
    """
    if not RESULTS.is_file():
        pytest.skip("the covariance representation is not generated in this checkout")
    frame = pd.read_csv(RESULTS)
    joint = frame[frame["portfolio_set"] == "all_seven_families_joint"]

    rate_columns = [
        column for column in joint.columns if column.startswith("gamma_") and column != "gamma_RM"
    ]
    for record in joint.to_dict("records"):
        entry = {str(key): value for key, value in record.items()}
        rate_price = next(
            float(entry[column]) for column in rate_columns if not pd.isna(entry[column])
        )
        market_price = float(entry["gamma_RM"])
        assert rate_price < 0.0, entry["model"]
        assert abs(market_price) < abs(rate_price) / 10.0, entry["model"]
