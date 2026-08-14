"""Tests for the second pass with an unrestricted zero-beta rate."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_article_second_pass,
    estimate_zero_beta_second_pass,
)

RESULTS = Path("artifacts/tables/cross_section/zero_beta_second_pass.csv")

#: The models the article names as misspecified by this test: "the estimates for
#: lambda_0 assume larger values (above 1% per month) and are statistically above
#: the average risk-free rate in most cases (namely for the CAPM, FF3, PS4, and
#: HXZ4 models)".
ARTICLE_MISSPECIFIED = {"capm", "fama_french_3", "liquidity", "q_factor"}
ARTICLE_PASSES = {"market_plus_fedfunds_innovation", "market_plus_tbill_innovation"}


def _system(n_assets: int = 12, seed: int = 3) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    assets = [f"asset_{i:02d}" for i in range(n_assets)]
    factors = ["market", "rate"]
    # Drawn rather than laid out on two grids. Two evenly spaced columns are
    # affine transforms of each other, so with an intercept the design would be
    # rank deficient and the fixture would exercise the guard instead of the
    # estimator.
    betas = pd.DataFrame(
        np.column_stack([rng.normal(1.0, 0.25, n_assets), rng.normal(0.0, 0.6, n_assets)]),
        index=assets,
        columns=factors,
    )
    mean_returns = pd.Series(
        0.5 + betas["market"] * 0.4 - betas["rate"] * 0.3 + rng.normal(0, 0.02, n_assets),
        index=assets,
        name="mean_return",
    )
    residual = rng.normal(0, 1.0, (200, n_assets))
    return {
        "mean_excess_returns": mean_returns,
        "betas": betas,
        "residual_covariance": pd.DataFrame(np.cov(residual, rowvar=False), assets, assets),
        "factor_covariance": pd.DataFrame(np.diag([16.0, 0.36]), factors, factors),
        "n_months": 200,
        "portfolio_set": "demo",
        "model": "market_plus_rate",
    }


def test_the_intercept_is_the_only_thing_the_risk_free_shift_moves() -> None:
    """Regressing total returns equals regressing excess returns with an intercept.

    Total and excess returns differ by a constant common to every asset, which
    the intercept absorbs. If the slopes or pricing errors moved with it, the
    estimator would be reading the level of returns as cross-sectional evidence.
    """
    system = _system()
    plain = estimate_zero_beta_second_pass(**system)  # type: ignore[arg-type]

    shifted = dict(system)
    mean_returns = system["mean_excess_returns"]
    assert isinstance(mean_returns, pd.Series)
    shifted["mean_excess_returns"] = mean_returns + 0.42
    with_level = estimate_zero_beta_second_pass(**shifted)  # type: ignore[arg-type]

    pd.testing.assert_series_equal(plain.risk_prices, with_level.risk_prices)
    pd.testing.assert_series_equal(plain.pricing_errors, with_level.pricing_errors)
    assert with_level.excess_zero_beta_rate == pytest.approx(plain.excess_zero_beta_rate + 0.42)


def test_the_level_reading_adds_the_average_bill_return() -> None:
    system = _system()
    result = estimate_zero_beta_second_pass(mean_risk_free_return=0.4203, **system)  # type: ignore[arg-type]

    assert result.zero_beta_rate_level == pytest.approx(result.excess_zero_beta_rate + 0.4203)
    without = estimate_zero_beta_second_pass(**system)  # type: ignore[arg-type]
    assert without.zero_beta_rate_level is None


def test_the_intercept_costs_one_degree_of_freedom() -> None:
    """The specification test loses a degree of freedom to the estimated intercept."""
    system = _system()
    restricted = estimate_article_second_pass(**system)  # type: ignore[arg-type]
    unrestricted = estimate_zero_beta_second_pass(**system)  # type: ignore[arg-type]

    assert unrestricted.chi_square_degrees_of_freedom == (
        restricted.chi_square_degrees_of_freedom - 1
    )


def test_a_cross_section_too_small_for_the_intercept_is_rejected() -> None:
    """Three assets cannot identify an intercept and two factors."""
    system = _system(n_assets=3)

    with pytest.raises(ValueError, match=re.escape("intercept plus factors")):
        estimate_zero_beta_second_pass(**system)  # type: ignore[arg-type]


def test_collinear_betas_are_rejected_rather_than_silently_pseudo_inverted() -> None:
    """Betas that are an affine function of a constant leave the intercept unidentified.

    Two evenly spaced beta columns are exactly this case, which is why the
    fixture draws them instead. Without the rank check the gram matrix would be
    singular and the intercept would absorb an arbitrary share of the fit.
    """
    system = _system(n_assets=12)
    grid = np.linspace(-1.0, 1.0, 12)
    system["betas"] = pd.DataFrame(
        np.column_stack([1.0 + 0.3 * grid, grid]),
        index=[f"asset_{i:02d}" for i in range(12)],
        columns=["market", "rate"],
    )

    with pytest.raises(ValueError, match=re.escape("rank deficient")):
        estimate_zero_beta_second_pass(**system)  # type: ignore[arg-type]


def test_the_reconstruction_reproduces_the_models_the_article_names() -> None:
    """The article's prose claim, checked against generated estimates.

    The appendix reports, without tabulating them, that the zero-beta test flags
    the CAPM, FF3, PS4 and HXZ4 as misspecified while its own model passes. That
    set is a prediction this reconstruction can either meet or miss, and it is
    the sharper test precisely because no table backs it.
    """
    if not RESULTS.is_file():
        pytest.skip("the zero-beta estimates are not generated in this checkout")
    frame = pd.read_csv(RESULTS)
    joint = frame[frame["portfolio_set"] == "all_seven_families_joint"].set_index("model")
    t_statistics = {
        str(model): abs(float(value))
        for model, value in joint["excess_zero_beta_t_statistic"].items()
    }
    significant = {model for model, value in t_statistics.items() if value > 1.96}

    assert significant >= ARTICLE_MISSPECIFIED, (
        "the article names these models as rejected by the zero-beta test"
    )
    assert not (ARTICLE_PASSES & significant), (
        "both versions of the article's own model must pass the test it uses to defend them"
    )
    # The article's own magnitude for the CAPM: above one percent per month.
    zero_beta_rates = {
        str(model): float(value) for model, value in joint["excess_zero_beta_rate"].items()
    }
    assert zero_beta_rates["capm"] > 1.0
