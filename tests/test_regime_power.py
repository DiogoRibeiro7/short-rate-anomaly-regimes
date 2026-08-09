"""Property tests for the regime-eligibility power simulator.

The simulator is a decision-support tool, so the properties that matter are the
ones a reader would rely on when looking at the curve: the calibration must be an
identity when there is no noise, precision must improve with window length, and
the probability of getting the sign of ``lambda_rate`` wrong must fall as windows
grow. Nothing here asserts anything about a frozen threshold.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest
import yaml
from scripts.analyse_regime_power import (
    DECILE_LABELS,
    ECONOMIC_BOUND,
    FROZEN_FIRST_PASS_FLOOR_MONTHS,
    FROZEN_MINIMUM_TEST_ASSETS,
    FROZEN_SECOND_PASS_FLOOR_MONTHS,
    MARKET_FACTOR,
    POST_HOC_DISCLOSURE,
    RATE_FACTOR,
    REGISTERED_REGIME_MONTHS,
    WINDOW_LENGTHS,
    PowerDgp,
    available_families,
    calibrate_power_dgp,
    covariance_factor,
    cross_sectional_residual_dispersion,
    first_pass_beta_reliability,
    first_window_meeting,
    portfolio_column,
    simulate_panel,
    simulate_window,
    summarise_estimates,
    true_fitted_premium_spreads,
)

FloatArray = npt.NDArray[np.floating[Any]]

TEST_FAMILY = "book_to_market"
TRUE_LAMBDA = np.array([0.60, -0.50])

#: Market loadings alternate about one so that the two beta columns are close to
#: orthogonal, which keeps the second pass well conditioned in the noiseless
#: calibration test.
MARKET_BETAS = 1.0 + 0.1 * np.array([1.0, -1.0] * 5)


def _make_panel(
    *,
    months: int,
    seed: int,
    residual_sd: float,
    rate_beta_span: float = 0.5,
    residual_correlation: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame, FloatArray]:
    """Build a synthetic ten-decile panel with known betas and risk prices.

    Args:
        months: Number of monthly observations.
        seed: Random seed.
        residual_sd: Standard deviation of the asset disturbances.
        rate_beta_span: Half-width of the true rate loadings across deciles.
        residual_correlation: Equicorrelation imposed on the disturbances across
            assets. Zero leaves the independent draw untouched.

    Returns:
        The excess-return panel, the factor panel, and the true beta matrix.
    """
    rng = np.random.default_rng(seed)
    index = pd.date_range("1970-01-01", periods=months, freq="MS")
    factors = pd.DataFrame(
        {
            MARKET_FACTOR: rng.normal(0.6, 4.5, months),
            RATE_FACTOR: rng.normal(0.0, 0.5, months),
        },
        index=index,
    )
    rate_betas = np.linspace(-rate_beta_span, rate_beta_span, len(DECILE_LABELS))
    betas = np.column_stack([MARKET_BETAS, rate_betas])
    intercepts = betas @ (TRUE_LAMBDA - factors.to_numpy(dtype=float).mean(axis=0))
    disturbances: FloatArray
    if residual_sd == 0.0:
        disturbances = np.zeros((months, len(DECILE_LABELS)))
    elif residual_correlation == 0.0:
        disturbances = rng.normal(0.0, residual_sd, (months, len(DECILE_LABELS)))
    else:
        correlation = np.full((len(DECILE_LABELS), len(DECILE_LABELS)), residual_correlation)
        np.fill_diagonal(correlation, 1.0)
        disturbances = residual_sd * (
            rng.standard_normal((months, len(DECILE_LABELS))) @ np.linalg.cholesky(correlation).T
        )
    returns = pd.DataFrame(
        intercepts + factors.to_numpy(dtype=float) @ betas.T + disturbances,
        index=index,
        columns=[portfolio_column(TEST_FAMILY, decile) for decile in DECILE_LABELS],
    )
    return returns, factors, betas


@pytest.fixture(scope="module")
def noisy_dgp() -> PowerDgp:
    """Calibrate a moderately noisy ten-decile system once for the sweep tests."""
    returns, factors, _ = _make_panel(months=480, seed=11, residual_sd=1.5)
    return calibrate_power_dgp(returns, factors, portfolio_set="test_system")


@pytest.fixture(scope="module")
def correlated_dgp() -> PowerDgp:
    """Calibrate a system whose first-pass residuals share a large common component.

    The reliability decomposition only differs from the naive diagonal-only
    calculation when residuals are cross-sectionally correlated, so the tests that
    pin the corrected formula need a system where they are.
    """
    returns, factors, _ = _make_panel(
        months=600, seed=71, residual_sd=1.5, residual_correlation=0.5
    )
    return calibrate_power_dgp(returns, factors, portfolio_set="test_system")


def test_calibration_is_an_identity_when_the_noise_is_zero() -> None:
    """The calibration must return exactly the parameters that generated the panel."""
    returns, factors, betas = _make_panel(months=180, seed=3, residual_sd=0.0)

    dgp = calibrate_power_dgp(returns, factors, portfolio_set="test_system")

    np.testing.assert_allclose(dgp.betas.to_numpy(dtype=float), betas, atol=1e-10)
    np.testing.assert_allclose(dgp.true_risk_prices.to_numpy(dtype=float), TRUE_LAMBDA, atol=1e-10)
    np.testing.assert_allclose(
        dgp.residual_covariance.to_numpy(dtype=float),
        np.zeros((len(DECILE_LABELS), len(DECILE_LABELS))),
        atol=1e-20,
    )
    expected_intercepts = betas @ (TRUE_LAMBDA - factors.to_numpy(dtype=float).mean(axis=0))
    np.testing.assert_allclose(
        dgp.intercepts.to_numpy(dtype=float), expected_intercepts, atol=1e-10
    )
    np.testing.assert_allclose(
        dgp.factor_covariance.to_numpy(dtype=float),
        factors.cov().to_numpy(dtype=float),
        atol=1e-12,
    )
    assert dgp.calibration_months == 180
    assert dgp.factors == (MARKET_FACTOR, RATE_FACTOR)


def test_zero_noise_simulation_leaves_only_the_factor_mean_error() -> None:
    """With no disturbances the simulator must reproduce its own input parameters.

    The residual covariance is exactly zero, so a simulated window is the
    calibrated pricing relation evaluated at the drawn factors. The first pass
    then recovers the calibrated betas exactly and the second pass recovers the
    calibrated risk prices up to the deviation of the drawn factor mean from the
    calibrated one, which is the only remaining source of error.
    """
    returns, factors, betas = _make_panel(months=180, seed=4, residual_sd=0.0)
    dgp = calibrate_power_dgp(returns, factors, portfolio_set="test_system")
    window = 120

    drawn_factors, drawn_returns = simulate_panel(
        dgp,
        window_months=window,
        rng=np.random.default_rng(5),
        factor_factor=covariance_factor(dgp.factor_covariance.to_numpy(dtype=float)),
        residual_factor=covariance_factor(dgp.residual_covariance.to_numpy(dtype=float)),
    )
    np.testing.assert_allclose(
        drawn_returns,
        dgp.intercepts.to_numpy(dtype=float) + drawn_factors @ betas.T,
        atol=1e-12,
    )

    design = np.column_stack([np.ones(window), drawn_factors])
    coefficients = np.linalg.lstsq(design, drawn_returns, rcond=None)[0]
    np.testing.assert_allclose(coefficients[1:, :].T, betas, atol=1e-9)

    estimated = np.linalg.lstsq(betas, drawn_returns.mean(axis=0), rcond=None)[0]
    factor_mean_error = drawn_factors.mean(axis=0) - dgp.factor_means.to_numpy(dtype=float)
    np.testing.assert_allclose(estimated, TRUE_LAMBDA + factor_mean_error, atol=1e-9)


def test_true_fitted_premium_spread_is_the_extreme_decile_difference() -> None:
    """The reported estimand must be ``pi(decile_10) - pi(decile_01)``."""
    returns, factors, betas = _make_panel(months=180, seed=4, residual_sd=0.0)
    dgp = calibrate_power_dgp(returns, factors, portfolio_set="test_system")

    spreads = true_fitted_premium_spreads(dgp)

    expected = float((betas[-1, 1] - betas[0, 1]) * TRUE_LAMBDA[1])
    assert list(spreads.index) == [TEST_FAMILY]
    assert spreads[TEST_FAMILY] == pytest.approx(expected, abs=1e-10)


def test_precision_improves_with_window_length(noisy_dgp: PowerDgp) -> None:
    """The dispersion of every reported estimand must fall as windows lengthen."""
    short = simulate_window(noisy_dgp, window_months=24, replications=250, seed=101)
    long = simulate_window(noisy_dgp, window_months=240, replications=250, seed=101)

    rate_position = noisy_dgp.factors.index(RATE_FACTOR)
    short_rate_sd = float(np.std(short.joint_risk_prices[:, rate_position], ddof=1))
    long_rate_sd = float(np.std(long.joint_risk_prices[:, rate_position], ddof=1))
    assert long_rate_sd < short_rate_sd

    short_spread_sd = float(np.std(short.joint_spreads[:, 0], ddof=1))
    long_spread_sd = float(np.std(long.joint_spreads[:, 0], ddof=1))
    assert long_spread_sd < short_spread_sd

    market_position = noisy_dgp.factors.index(MARKET_FACTOR)
    short_market_sd = float(np.std(short.joint_risk_prices[:, market_position], ddof=1))
    long_market_sd = float(np.std(long.joint_risk_prices[:, market_position], ddof=1))
    # The market risk price is dominated by the sampling error of the factor mean,
    # so its dispersion should fall at roughly the parametric root-T rate.
    assert long_market_sd < short_market_sd / 2.0


def test_sign_error_probability_falls_with_window_length(noisy_dgp: PowerDgp) -> None:
    """Short windows must get the sign of lambda_rate wrong far more often."""
    true_rate = float(noisy_dgp.true_risk_prices[RATE_FACTOR])
    rate_position = noisy_dgp.factors.index(RATE_FACTOR)

    probabilities = []
    for window in (24, 120, 480):
        draws = simulate_window(noisy_dgp, window_months=window, replications=250, seed=202)
        estimates = draws.joint_risk_prices[:, rate_position]
        probabilities.append(float(np.mean(np.sign(estimates) != np.sign(true_rate))))

    assert probabilities[0] > probabilities[1] > probabilities[2]
    assert probabilities[0] > 0.20
    assert probabilities[-1] < 0.05


def test_attenuation_towards_zero_weakens_as_windows_lengthen(noisy_dgp: PowerDgp) -> None:
    """The errors-in-variables attenuation of lambda_rate must shrink with the window."""
    true_rate = float(noisy_dgp.true_risk_prices[RATE_FACTOR])
    rate_position = noisy_dgp.factors.index(RATE_FACTOR)

    ratios = [
        float(
            np.mean(
                simulate_window(
                    noisy_dgp, window_months=window, replications=200, seed=303
                ).joint_risk_prices[:, rate_position]
            )
            / true_rate
        )
        for window in (24, 120, 480)
    ]
    assert ratios[0] < ratios[1] < ratios[2]
    assert ratios[0] < 0.5


def test_simulated_windows_are_reproducible(noisy_dgp: PowerDgp) -> None:
    """Two runs on the same seed must produce identical draws."""
    first = simulate_window(noisy_dgp, window_months=36, replications=20, seed=909)
    second = simulate_window(noisy_dgp, window_months=36, replications=20, seed=909)
    np.testing.assert_array_equal(first.joint_risk_prices, second.joint_risk_prices)
    np.testing.assert_array_equal(first.joint_spreads, second.joint_spreads)


def test_feasible_shanken_covariance_tracks_the_month_to_asset_ratio(
    noisy_dgp: PowerDgp,
) -> None:
    """Full rank of the sample residual covariance must gate the feasible interval.

    The gate is a reporting choice, not a limit of the estimator: a window with
    no more months than assets yields a rank-deficient covariance that the second
    pass accepts. This sweep reports the feasible interval only above that point.
    """
    withheld = simulate_window(noisy_dgp, window_months=len(DECILE_LABELS), replications=5, seed=7)
    reported = simulate_window(
        noisy_dgp, window_months=len(DECILE_LABELS) + 2, replications=5, seed=7
    )

    assert withheld.joint_feasible_full_rank is False
    assert bool(np.all(np.isnan(withheld.joint_feasible_standard_errors)))
    # The oracle interval, which does not depend on the sample covariance, is
    # still produced at the withheld length, so nothing failed to estimate.
    assert bool(np.all(np.isfinite(withheld.joint_oracle_standard_errors)))
    assert reported.joint_feasible_full_rank is True
    assert bool(np.all(np.isfinite(reported.joint_feasible_standard_errors)))


def test_simulated_mean_returns_track_the_calibrated_pricing_relation(
    noisy_dgp: PowerDgp,
) -> None:
    """Long simulated panels must price close to ``B lambda`` by construction."""
    rng = np.random.default_rng(19)
    factors, returns = simulate_panel(
        noisy_dgp,
        window_months=60_000,
        rng=rng,
        factor_factor=covariance_factor(noisy_dgp.factor_covariance.to_numpy(dtype=float)),
        residual_factor=covariance_factor(noisy_dgp.residual_covariance.to_numpy(dtype=float)),
    )
    assert factors.shape == (60_000, 2)
    implied = noisy_dgp.betas.to_numpy(dtype=float) @ noisy_dgp.true_risk_prices.to_numpy(
        dtype=float
    )
    np.testing.assert_allclose(returns.mean(axis=0), implied, atol=0.05)


def test_cross_sectional_residual_dispersion_is_the_centred_trace() -> None:
    """``tr(M_N Sigma) / (N - 1)`` must equal mean diagonal minus mean off-diagonal."""
    rng = np.random.default_rng(4242)
    factor = rng.standard_normal((8, 8))
    covariance = factor @ factor.T

    n_assets = covariance.shape[0]
    centring = np.eye(n_assets) - np.ones((n_assets, n_assets)) / n_assets
    expected = float(np.trace(centring @ covariance)) / (n_assets - 1)

    assert cross_sectional_residual_dispersion(covariance) == pytest.approx(expected, rel=1e-12)

    # An equicorrelated system is the closed form the docstring quotes: with unit
    # variances and correlation rho the centred dispersion is exactly ``1 - rho``.
    rho = 0.4
    equicorrelated = np.full((6, 6), rho)
    np.fill_diagonal(equicorrelated, 1.0)
    assert cross_sectional_residual_dispersion(equicorrelated) == pytest.approx(
        1.0 - rho, rel=1e-12
    )


def test_cross_sectional_residual_dispersion_rejects_degenerate_input() -> None:
    """A dispersion across fewer than two assets, or a non-square matrix, is refused."""
    with pytest.raises(ValueError, match="square matrix"):
        cross_sectional_residual_dispersion(np.ones((3, 4)))
    with pytest.raises(ValueError, match="at least two assets"):
        cross_sectional_residual_dispersion(np.ones((1, 1)))


def test_beta_noise_variance_matches_an_independent_monte_carlo(
    correlated_dgp: PowerDgp,
) -> None:
    """The corrected formula must reproduce a simulated cross-sectional error variance.

    The analytic claim is that the estimation-error contribution to the
    cross-sectional variance of factor ``k``'s estimated loadings is
    ``[Sigma_f^-1]_kk / (T (N - 1)) * tr(M_N Sigma_eps)``. This test never uses
    that expression to build its own benchmark: it draws windows from the
    calibrated process, runs the first pass, and measures the cross-sectional
    variance of ``beta_hat - beta`` directly.
    """
    window = 480
    replications = 3_000
    rate_position = correlated_dgp.factors.index(RATE_FACTOR)
    true_betas = correlated_dgp.betas.to_numpy(dtype=float)
    factor_factor = covariance_factor(correlated_dgp.factor_covariance.to_numpy(dtype=float))
    residual_factor = covariance_factor(correlated_dgp.residual_covariance.to_numpy(dtype=float))

    rng = np.random.default_rng(8_675_309)
    realised = np.empty(replications)
    for replication in range(replications):
        factors, returns = simulate_panel(
            correlated_dgp,
            window_months=window,
            rng=rng,
            factor_factor=factor_factor,
            residual_factor=residual_factor,
        )
        design = np.column_stack([np.ones(window), factors])
        coefficients = np.linalg.lstsq(design, returns, rcond=None)[0]
        errors = coefficients[1:, :].T - true_betas
        realised[replication] = float(np.var(errors[:, rate_position], ddof=1))
    monte_carlo = float(np.mean(realised))

    decomposition = first_pass_beta_reliability(correlated_dgp, window_months=window)
    analytic = float(decomposition["noise_cross_sectional_variance"][RATE_FACTOR])
    diagonal_only = float(decomposition["mean_individual_beta_sampling_variance"][RATE_FACTOR])

    # The remaining gap is the O(1/T) difference between conditioning on the
    # population factor covariance and on the drawn one, plus Monte Carlo error.
    assert analytic == pytest.approx(monte_carlo, rel=0.05)

    # The superseded diagonal-only quantity is not merely less precise; with
    # positively correlated residuals it is biased upward by a wide margin, and
    # the Monte Carlo rules it out.
    assert diagonal_only > 1.5 * monte_carlo


def test_reliability_and_noise_share_are_exact_complements(correlated_dgp: PowerDgp) -> None:
    """The two reported shares must sum to one and split the observed variance."""
    decomposition = first_pass_beta_reliability(correlated_dgp, window_months=240)

    total = (
        decomposition["reliability_ratio"]
        + decomposition["noise_share_of_cross_sectional_variance"]
    )
    np.testing.assert_allclose(total.to_numpy(dtype=float), 1.0, atol=1e-12)
    np.testing.assert_allclose(
        (
            decomposition["signal_cross_sectional_variance"]
            + decomposition["noise_cross_sectional_variance"]
        ).to_numpy(dtype=float),
        decomposition["observed_cross_sectional_variance"].to_numpy(dtype=float),
        atol=1e-12,
    )
    assert list(decomposition.index) == list(correlated_dgp.factors)


def test_diagonal_only_calculation_overstates_the_noise_when_residuals_correlate(
    correlated_dgp: PowerDgp,
) -> None:
    """Positive average residual correlation must make the naive figure the larger one."""
    residual_covariance = correlated_dgp.residual_covariance.to_numpy(dtype=float)
    n_assets = residual_covariance.shape[0]
    mean_off_diagonal = float(
        (residual_covariance.sum() - np.trace(residual_covariance)) / (n_assets * (n_assets - 1))
    )
    assert mean_off_diagonal > 0.0

    decomposition = first_pass_beta_reliability(correlated_dgp, window_months=120)
    individual = decomposition["mean_individual_beta_sampling_variance"]
    cross_sectional = decomposition["noise_cross_sectional_variance"]
    for factor in correlated_dgp.factors:
        assert float(individual[factor]) > float(cross_sectional[factor])


def test_first_pass_beta_noise_falls_like_one_over_the_window(noisy_dgp: PowerDgp) -> None:
    """The estimation-error share of beta dispersion must scale like 1/T."""
    long_window = first_pass_beta_reliability(noisy_dgp, window_months=480)
    short_window = first_pass_beta_reliability(noisy_dgp, window_months=48)

    column = "noise_share_of_cross_sectional_variance"
    long_share = float(long_window[column][RATE_FACTOR])
    short_share = float(short_window[column][RATE_FACTOR])
    assert short_share > long_share
    assert short_share == pytest.approx(10.0 * long_share, rel=1e-9)
    assert float(short_window["reliability_ratio"][RATE_FACTOR]) < float(
        long_window["reliability_ratio"][RATE_FACTOR]
    )


def test_first_pass_beta_reliability_rejects_a_non_positive_window(noisy_dgp: PowerDgp) -> None:
    """A window of zero months has no sampling variance to report."""
    with pytest.raises(ValueError, match="window_months must be positive"):
        first_pass_beta_reliability(noisy_dgp, window_months=0)


def test_summarise_estimates_reports_bias_dispersion_and_coverage() -> None:
    """The summary must reproduce hand-computable bias, dispersion, and coverage."""
    draws = np.array([-1.0, -0.5, 0.5, 1.0])
    summary = summarise_estimates(
        draws,
        true_value=-1.0,
        oracle_standard_errors=np.full(4, 1.0),
    )
    assert summary["mean_estimate"] == pytest.approx(0.0)
    assert summary["bias"] == pytest.approx(1.0)
    assert summary["attenuation_ratio"] == pytest.approx(0.0)
    assert summary["sign_error_probability"] == pytest.approx(0.5)
    assert summary["standard_deviation"] == pytest.approx(float(np.std(draws, ddof=1)))
    # The 95 percent interval is +/- 1.96, so only the draw at 1.0 excludes -1.0.
    assert summary["oracle_coverage_95"] == pytest.approx(0.75)
    assert summary["feasible_coverage_95"] is None


def test_summarise_estimates_rejects_a_single_replication() -> None:
    """A one-replication window carries no dispersion and must be refused."""
    with pytest.raises(ValueError, match="At least two replications"):
        summarise_estimates(np.array([0.1]), true_value=0.1)


def test_first_window_meeting_requires_the_criterion_to_stay_met() -> None:
    """A single lucky crossing must not be reported as a crossing."""
    windows = (12, 24, 36, 48)
    lucky = {12: 0.9, 24: 0.1, 36: 0.9, 48: 0.9}
    assert first_window_meeting(lucky, lambda value: value > 0.5, windows) == 36
    never = {12: 0.1, 24: 0.1, 36: 0.1, 48: 0.1}
    assert first_window_meeting(never, lambda value: value > 0.5, windows) is None
    missing = {12: 0.9, 24: None, 36: 0.9, 48: 0.9}
    assert first_window_meeting(missing, lambda value: value > 0.5, windows) == 36


def test_covariance_factor_reconstructs_the_covariance() -> None:
    """The square-root factor must reproduce both full-rank and singular inputs."""
    rng = np.random.default_rng(5)
    raw = rng.standard_normal((6, 6))
    positive_definite = raw @ raw.T + np.eye(6)
    factor = covariance_factor(positive_definite)
    np.testing.assert_allclose(factor @ factor.T, positive_definite, atol=1e-10)

    singular = np.outer(np.arange(1.0, 5.0), np.arange(1.0, 5.0))
    singular_factor = covariance_factor(singular)
    np.testing.assert_allclose(singular_factor @ singular_factor.T, singular, atol=1e-8)

    with pytest.raises(ValueError, match="square matrix"):
        covariance_factor(np.ones((2, 3)))


def test_available_families_requires_a_complete_decile_set() -> None:
    """A family missing one decile must not be simulated as a ten-asset system."""
    complete = [portfolio_column(TEST_FAMILY, decile) for decile in DECILE_LABELS]
    assert available_families(complete) == (TEST_FAMILY,)
    assert available_families(complete[:-1]) == ()


def test_simulate_window_rejects_degenerate_inputs(noisy_dgp: PowerDgp) -> None:
    """Non-positive replications and unusable windows must raise."""
    with pytest.raises(ValueError, match="replications must be positive"):
        simulate_window(noisy_dgp, window_months=24, replications=0, seed=1)
    with pytest.raises(ValueError, match="must exceed the number of first-pass parameters"):
        simulate_panel(
            noisy_dgp,
            window_months=2,
            rng=np.random.default_rng(0),
            factor_factor=covariance_factor(noisy_dgp.factor_covariance.to_numpy(dtype=float)),
            residual_factor=covariance_factor(noisy_dgp.residual_covariance.to_numpy(dtype=float)),
        )


def test_calibration_rejects_misaligned_or_short_panels() -> None:
    """Calibration must refuse inputs it cannot estimate on."""
    returns, factors, _ = _make_panel(months=60, seed=8, residual_sd=1.0)
    with pytest.raises(ValueError, match="share an index"):
        calibrate_power_dgp(returns, factors.iloc[1:])
    with pytest.raises(ValueError, match="more months than test assets"):
        calibrate_power_dgp(returns.iloc[:8], factors.iloc[:8])


def test_frozen_reference_marks_match_the_configuration() -> None:
    """The reference marks must be the frozen values, so the curve cannot mislabel them."""
    config = yaml.safe_load(Path("configs/regimes.yaml").read_text(encoding="utf-8"))
    eligibility = config["regime_estimation_eligibility"]
    assert (
        eligibility["minimum_months_for_regime_specific_estimation"]
        == FROZEN_FIRST_PASS_FLOOR_MONTHS
    )
    assert (
        eligibility["minimum_months_for_standalone_second_pass"] == FROZEN_SECOND_PASS_FLOOR_MONTHS
    )
    assert (
        eligibility["minimum_test_assets_for_standalone_second_pass"] == FROZEN_MINIMUM_TEST_ASSETS
    )


def test_post_hoc_disclosure_names_the_floors_that_are_actually_frozen() -> None:
    """The disclosure must be derived from the reference marks, not written out.

    The disclosure is copied verbatim into the diagnostic and provenance
    artifacts, so a hand-written floor month in it would keep disclosing a
    superseded value after `configs/regimes.yaml` moved. Deriving it from the
    constants ties it to the configuration, which
    `test_frozen_reference_marks_match_the_configuration` pins.
    """
    named = [int(month) for month in re.findall(r"(\d+)-month", POST_HOC_DISCLOSURE)]

    assert named == [FROZEN_FIRST_PASS_FLOOR_MONTHS, FROZEN_SECOND_PASS_FLOOR_MONTHS]


def test_registered_regime_lengths_are_points_on_the_sweep() -> None:
    """Every registered regime length must be readable straight off the curve."""
    registry = pd.read_csv(Path("research/regime_registry.csv"))
    primary = registry[registry["primary_or_sensitivity"] != "declared_combination_sensitivity"]
    observed = {
        str(regime): int(str(months))
        for regime, months in zip(
            primary["regime_id"], primary["number_of_observations"], strict=True
        )
    }
    assert observed == REGISTERED_REGIME_MONTHS
    assert set(REGISTERED_REGIME_MONTHS.values()) <= set(WINDOW_LENGTHS)


def test_economic_bound_matches_the_threshold_contract() -> None:
    """The fitted-premium bound must be the one the threshold contract fixes."""
    text = Path("research/economic_thresholds.md").read_text(encoding="utf-8")
    assert "0.25 monthly percentage points" in text
    assert ECONOMIC_BOUND == 0.25
