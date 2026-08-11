"""Tests for the article's useless-factor bootstrap, Internet Appendix Section 4."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.time_series import estimate_time_series_betas
from short_rate_anomaly_regimes.models.useless_factor_bootstrap import (
    ARTICLE_REPLICATIONS,
    bootstrap_useless_factor_p_values,
    empirical_risk_price_p_value,
    first_pass_by_matrix_ols,
)


def _panel(
    *,
    n_months: int = 240,
    n_assets: int = 12,
    seed: int = 11,
    rate_loading: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a return-factor panel with a controllable rate exposure."""
    rng = np.random.default_rng(seed)
    index = pd.period_range("1980-01", periods=n_months, freq="M").to_timestamp(how="start")
    market = rng.normal(0.5, 4.0, n_months)
    rate = rng.normal(0.0, 0.6, n_months)
    factors = pd.DataFrame({"market": market, "rate": rate}, index=index)

    market_betas = np.linspace(0.7, 1.3, n_assets)
    rate_betas = np.linspace(-1.0, 1.0, n_assets) * rate_loading
    common = rng.normal(0.0, 1.0, n_months)
    returns = {}
    for position in range(n_assets):
        idiosyncratic = rng.normal(0.0, 2.0, n_months) + common
        returns[f"asset_{position:02d}"] = (
            market_betas[position] * market + rate_betas[position] * rate + idiosyncratic
        )
    return pd.DataFrame(returns, index=index), factors


def test_matrix_first_pass_matches_the_repository_estimator() -> None:
    """The fast path must be the same OLS the rest of the pipeline runs.

    The bootstrap cannot use ``estimate_time_series_betas`` five thousand times,
    because that function also computes HAC standard errors it never reads. It
    may only skip them if the coefficients and residuals are identical, so that
    a bootstrap statistic and a baseline statistic are the same object.
    """
    returns, factors = _panel(rate_loading=0.5)

    betas, residuals = first_pass_by_matrix_ols(returns, factors)
    reference = estimate_time_series_betas(returns, factors, hac_lags=6)

    pd.testing.assert_frame_equal(
        betas,
        reference.coefficients[list(factors.columns)],
        check_names=False,
        atol=1e-10,
    )
    pd.testing.assert_frame_equal(residuals, reference.residuals, check_names=False, atol=1e-10)


def test_the_bootstrap_reproduces_the_sample_statistics_of_the_second_pass() -> None:
    """Reported sample statistics must be the estimator's, not a re-derivation."""
    returns, factors = _panel(rate_loading=0.6)
    betas, residuals = first_pass_by_matrix_ols(returns, factors)
    expected = estimate_article_second_pass(
        mean_excess_returns=returns.mean().rename("mean_return"),
        betas=betas,
        residual_covariance=residual_covariance_from_first_pass(residuals),
        factor_covariance=factors.cov(),
        n_months=len(returns),
        portfolio_set="demo",
        model="market_plus_rate",
    )

    result = bootstrap_useless_factor_p_values(
        excess_returns=returns,
        factors=factors,
        portfolio_set="demo",
        model="market_plus_rate",
        seed=7,
        n_replications=40,
    )

    assert result.sample_chi_square == pytest.approx(expected.chi_square_statistic)
    assert result.sample_article_fit == pytest.approx(expected.article_cross_sectional_fit)
    pd.testing.assert_series_equal(result.sample_risk_prices, expected.risk_prices)


def test_the_p_value_branches_follow_the_published_definition() -> None:
    """Step 6 selects its branch on the sign of the risk price, not the t-ratio."""
    draws = np.array([-3.0, -1.0, 0.0, 1.0, 3.0])

    # Negative estimate: #{t_b <= -2} = 1 and #{t_b > 2} = 1.
    assert empirical_risk_price_p_value(
        sample_risk_price=-0.4, sample_t_statistic=-2.0, bootstrap_t_statistics=draws
    ) == pytest.approx(2 / 5)
    # Positive estimate: #{t_b >= 2} = 1 and #{t_b < -2} = 1.
    assert empirical_risk_price_p_value(
        sample_risk_price=0.4, sample_t_statistic=2.0, bootstrap_t_statistics=draws
    ) == pytest.approx(2 / 5)
    # An estimate no draw matches returns zero rather than failing.
    assert empirical_risk_price_p_value(
        sample_risk_price=-0.4, sample_t_statistic=-99.0, bootstrap_t_statistics=draws
    ) == pytest.approx(0.0)

    # The branch must follow the risk price, not the t-ratio. Pairing a positive
    # price with a negative t-ratio separates the two: the published rule counts
    # #{t_b >= -2} + #{t_b < 2} = 4 + 4, while a rule keyed on the t-ratio's sign
    # would count #{t_b <= -2} + #{t_b > 2} = 1 + 1. Every same-signed case above
    # gives the same answer either way, so none of them can catch a regression
    # that switched the selector.
    assert empirical_risk_price_p_value(
        sample_risk_price=0.4, sample_t_statistic=-2.0, bootstrap_t_statistics=draws
    ) == pytest.approx(8 / 5)


def test_a_useless_factor_is_not_flagged_as_priced() -> None:
    """The calibration check: under the null the p-value must not reject.

    The returns here are generated with a zero rate loading, so the rate factor
    is useless by construction. A procedure that reported a small p-value for it
    would be measuring its own resampling rather than the data.
    """
    returns, factors = _panel(rate_loading=0.0, seed=23)

    result = bootstrap_useless_factor_p_values(
        excess_returns=returns,
        factors=factors,
        portfolio_set="demo",
        model="market_plus_rate",
        seed=101,
        n_replications=400,
    )

    assert result.risk_price_p_values["rate"] > 0.10
    assert result.n_replications_degenerate == 0
    assert result.n_replications_completed == 400


def test_a_genuinely_priced_factor_survives_the_null() -> None:
    """The power check, so the test above cannot pass by always failing to reject.

    A factor whose loadings really do line up with average returns must reach a
    small empirical p-value. Without this, a bootstrap that returned 1.0 for
    everything would satisfy the calibration test.
    """
    returns, factors = _panel(rate_loading=0.0, seed=5)
    # Give average returns a component that only the rate betas explain, so the
    # cross-sectional relation is real rather than an artefact of the residuals.
    rate_betas = np.linspace(-1.5, 1.5, returns.shape[1])
    returns = returns + rate_betas * 3.0 + np.outer(factors["rate"].to_numpy(), rate_betas)

    result = bootstrap_useless_factor_p_values(
        excess_returns=returns,
        factors=factors,
        portfolio_set="demo",
        model="market_plus_rate",
        seed=101,
        n_replications=400,
    )

    assert result.risk_price_p_values["rate"] < 0.05


def test_the_bootstrap_is_deterministic_given_a_seed() -> None:
    """A recorded seed must reproduce a recorded p-value exactly."""
    returns, factors = _panel(rate_loading=0.4)
    kwargs = {
        "excess_returns": returns,
        "factors": factors,
        "portfolio_set": "demo",
        "model": "market_plus_rate",
        "n_replications": 50,
    }

    first = bootstrap_useless_factor_p_values(seed=3, **kwargs)  # type: ignore[arg-type]
    second = bootstrap_useless_factor_p_values(seed=3, **kwargs)  # type: ignore[arg-type]
    different = bootstrap_useless_factor_p_values(seed=4, **kwargs)  # type: ignore[arg-type]

    pd.testing.assert_series_equal(first.risk_price_p_values, second.risk_price_p_values)
    assert first.chi_square_p_value == second.chi_square_p_value
    assert (first.risk_price_p_values != different.risk_price_p_values).any() or (
        first.chi_square_p_value != different.chi_square_p_value
    )


def test_the_null_distribution_is_centred_however_strongly_the_factor_is_priced() -> None:
    """Steps 2 and 3 impose the null by drawing two independent time sequences.

    This is the property that independence buys, and it is testable from the
    output. However strong the real cross-sectional relation is, the bootstrap
    t-ratios must stay centred near zero, because the factors a replication sees
    were drawn on a different time sequence from the residuals. A design that
    resampled both on one sequence would carry the alternative into the null,
    shifting these medians toward the sample t-ratio and destroying the test's
    power. Comparing against the sample t-ratio is what makes the assertion
    meaningful rather than a statement about zero.
    """
    returns, factors = _panel(rate_loading=0.0, seed=5)
    rate_betas = np.linspace(-1.5, 1.5, returns.shape[1])
    returns = returns + rate_betas * 3.0 + np.outer(factors["rate"].to_numpy(), rate_betas)

    result = bootstrap_useless_factor_p_values(
        excess_returns=returns,
        factors=factors,
        portfolio_set="demo",
        model="market_plus_rate",
        seed=17,
        n_replications=400,
    )

    sample_t = abs(float(result.sample_shanken_t_statistics["rate"]))
    null_median = abs(float(result.bootstrap_t_statistic_medians["rate"]))
    assert sample_t > 3.0, "the fixture must price the factor for this test to bite"
    assert null_median < 0.5
    assert null_median < 0.1 * sample_t


def test_the_article_replication_count_is_the_published_one() -> None:
    assert ARTICLE_REPLICATIONS == 5000


def test_a_non_positive_replication_count_is_rejected() -> None:
    returns, factors = _panel()
    with pytest.raises(ValueError, match="n_replications must be positive"):
        bootstrap_useless_factor_p_values(
            excess_returns=returns,
            factors=factors,
            portfolio_set="demo",
            model="market_plus_rate",
            seed=1,
            n_replications=0,
        )


def test_misaligned_inputs_are_rejected() -> None:
    returns, factors = _panel()
    with pytest.raises(ValueError, match="share a time index"):
        first_pass_by_matrix_ols(returns, factors.iloc[1:])


def test_missing_observations_are_rejected_rather_than_imputed() -> None:
    returns, factors = _panel()
    returns.iloc[3, 2] = np.nan
    with pytest.raises(ValueError, match="does not impute"):
        first_pass_by_matrix_ols(returns, factors)


def test_a_window_shorter_than_the_design_is_rejected() -> None:
    returns, factors = _panel(n_months=240)
    with pytest.raises(ValueError, match="more months than design columns"):
        first_pass_by_matrix_ols(returns.iloc[:3], factors.iloc[:3])


def test_an_empty_replication_set_cannot_produce_a_p_value() -> None:
    with pytest.raises(ValueError, match="at least one replication"):
        empirical_risk_price_p_value(
            sample_risk_price=-0.4,
            sample_t_statistic=-2.0,
            bootstrap_t_statistics=np.array([]),
        )


def test_a_degenerate_factor_is_counted_rather_than_resampled_away() -> None:
    """A draw the estimator cannot fit must not be silently redrawn.

    Redrawing until every replication succeeds would condition the null
    distribution on the estimator's success, which is a different null. The
    fixture makes degeneracy common: the rate factor is zero in every month but
    one, so any draw that misses that month resamples a constant factor, whose
    betas leave the risk prices unidentified.
    """
    returns, factors = _panel(rate_loading=0.3)
    spike = np.zeros(len(factors))
    spike[0] = 5.0
    factors["rate"] = spike

    result = bootstrap_useless_factor_p_values(
        excess_returns=returns,
        factors=factors,
        portfolio_set="demo",
        model="market_plus_rate",
        seed=31,
        n_replications=60,
    )

    assert result.n_replications_degenerate > 0
    assert result.n_replications_requested == 60
    # The denominator is the completed count, and both numbers are recorded, so
    # a reader can see that the p-value was not divided by the requested count.
    assert result.n_replications_completed == 60 - result.n_replications_degenerate
    assert result.n_replications_completed > 0
