"""Tests for Politis-White selection and the joint moving-block bootstrap."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.block_bootstrap import (
    FALLBACK_BLOCK_LENGTH,
    MAXIMUM_BLOCK_LENGTH,
    MINIMUM_BLOCK_LENGTH,
    FittedPremiumBootstrap,
    FloatArray,
    _optimal_block_length_single,
    bootstrap_fitted_premium_spreads,
    moving_block_indices,
    recover_lagged_level,
    select_block_length,
)


def _white_noise(n: int = 504, seed: int = 1) -> FloatArray:
    return np.random.default_rng(seed).normal(0.0, 1.0, n)


def _autoregressive(n: int = 504, rho: float = 0.9, seed: int = 2) -> FloatArray:
    rng = np.random.default_rng(seed)
    values = np.zeros(n)
    for index in range(1, n):
        values[index] = rho * values[index - 1] + rng.normal()
    return values


class TestPolitisWhiteSelector:
    """The selector must respond to dependence and honour its declared bounds."""

    def test_persistent_series_need_longer_blocks_than_white_noise(self) -> None:
        noise = _optimal_block_length_single(_white_noise())
        persistent = _optimal_block_length_single(_autoregressive(rho=0.9))
        assert persistent > noise
        assert noise > 0.0

    def test_more_persistence_gives_a_longer_block(self) -> None:
        mild = _optimal_block_length_single(_autoregressive(rho=0.3, seed=5))
        strong = _optimal_block_length_single(_autoregressive(rho=0.95, seed=5))
        assert strong > mild

    def test_a_constant_series_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="zero sample variance"):
            _optimal_block_length_single(np.ones(200))

    def test_the_selector_takes_the_maximum_across_factors(self) -> None:
        frame = pd.DataFrame({"noise": _white_noise(), "persistent": _autoregressive(rho=0.9)})
        selection = select_block_length(frame)
        assert selection.selected_by in {"politis_white", "declared_fallback"}
        assert len(selection.raw_optimal_lengths) == 2
        if selection.selected_by == "politis_white":
            assert selection.block_length >= int(np.ceil(max(selection.raw_optimal_lengths)))

    def test_a_short_panel_falls_back(self) -> None:
        frame = pd.DataFrame({"x": _white_noise(40)})
        selection = select_block_length(frame)
        assert selection.block_length == FALLBACK_BLOCK_LENGTH
        assert selection.selected_by == "declared_fallback"
        assert any("complete factor months" in reason for reason in selection.failure_reasons)

    def test_a_missing_month_falls_back(self) -> None:
        values = _white_noise()
        values[10] = np.nan
        selection = select_block_length(pd.DataFrame({"x": values}))
        assert selection.block_length == FALLBACK_BLOCK_LENGTH
        assert any("missing months" in reason for reason in selection.failure_reasons)

    def test_a_zero_variance_factor_falls_back(self) -> None:
        selection = select_block_length(pd.DataFrame({"x": np.ones(504)}))
        assert selection.block_length == FALLBACK_BLOCK_LENGTH
        assert selection.selected_by == "declared_fallback"

    def test_a_selection_outside_the_declared_bounds_falls_back(self) -> None:
        """A near-unit-root series pushes the raw selector past the upper bound."""
        selection = select_block_length(
            pd.DataFrame({"x": _autoregressive(n=504, rho=0.995, seed=11)})
        )
        if selection.selected_by == "declared_fallback":
            assert selection.block_length == FALLBACK_BLOCK_LENGTH
        else:
            assert MINIMUM_BLOCK_LENGTH <= selection.block_length <= MAXIMUM_BLOCK_LENGTH

    def test_a_kept_selection_always_lies_inside_the_bounds(self) -> None:
        for seed in range(8):
            selection = select_block_length(
                pd.DataFrame({"x": _autoregressive(rho=0.5, seed=seed)})
            )
            if selection.selected_by == "politis_white":
                assert MINIMUM_BLOCK_LENGTH <= selection.block_length <= MAXIMUM_BLOCK_LENGTH


class TestMovingBlockIndices:
    """Blocks must overlap, stay in range, and preserve within-block order."""

    def test_the_resample_has_the_original_length_and_valid_positions(self) -> None:
        rng = np.random.default_rng(0)
        positions = moving_block_indices(504, block_length=12, rng=rng)
        assert positions.size == 504
        assert positions.min() >= 0
        assert positions.max() < 504

    def test_within_block_order_is_preserved(self) -> None:
        rng = np.random.default_rng(0)
        positions = moving_block_indices(60, block_length=6, rng=rng)
        first_block = positions[:6]
        assert list(first_block) == list(range(first_block[0], first_block[0] + 6))

    def test_a_block_longer_than_the_sample_is_rejected(self) -> None:
        rng = np.random.default_rng(0)
        with pytest.raises(ValueError, match="between one month and the sample length"):
            moving_block_indices(10, block_length=11, rng=rng)

    def test_a_full_length_block_reproduces_the_sample(self) -> None:
        rng = np.random.default_rng(0)
        positions = moving_block_indices(20, block_length=20, rng=rng)
        assert list(positions) == list(range(20))

    def test_the_draw_is_reproducible_from_the_seed(self) -> None:
        first = moving_block_indices(100, block_length=8, rng=np.random.default_rng(42))
        second = moving_block_indices(100, block_length=8, rng=np.random.default_rng(42))
        assert list(first) == list(second)


def _premium_system(
    *, n_months: int = 504, lambda_rate: float = -0.7, seed: int = 3
) -> dict[str, object]:
    """Build a system whose fitted-premium spread is known by construction."""
    rng = np.random.default_rng(seed)
    lagged = np.zeros(n_months)
    for index in range(1, n_months):
        lagged[index] = 0.99 * lagged[index - 1] + rng.normal(0.0, 0.5)
    rate = 0.02 + 0.99 * lagged + rng.normal(0.0, 0.5, n_months)
    innovation = rate - (0.02 + 0.99 * lagged)
    market = rng.normal(0.5, 4.5, n_months)

    beta_market = np.array([1.1, 1.0, 0.9, 1.2, 0.95, 1.05])
    beta_rate = np.array([0.8, 0.4, 0.0, -0.4, -0.8, 0.2])
    mean_target = beta_market * 0.55 + beta_rate * lambda_rate
    returns = (
        np.outer(market, beta_market)
        + np.outer(innovation, beta_rate)
        + rng.normal(0.0, 3.0, (n_months, beta_rate.size))
    )
    returns += mean_target - returns.mean(axis=0)
    return {
        "rate_level": rate,
        "lagged_rate_level": lagged,
        "market": market,
        "excess_returns": returns,
        "spread_pairs": {"famA": (0, 4), "famB": (1, 3)},
    }


class TestFittedPremiumBootstrap:
    """The bootstrap must recompute the whole chain and bracket its own estimate."""

    def _run(self, draws: int = 300, **overrides: object) -> FittedPremiumBootstrap:
        parts = _premium_system()
        parts.update(overrides)
        return bootstrap_fitted_premium_spreads(
            rate_level=parts["rate_level"],  # type: ignore[arg-type]
            lagged_rate_level=parts["lagged_rate_level"],  # type: ignore[arg-type]
            market=parts["market"],  # type: ignore[arg-type]
            excess_returns=parts["excess_returns"],  # type: ignore[arg-type]
            spread_pairs=parts["spread_pairs"],  # type: ignore[arg-type]
            block_length=12,
            draws=draws,
            seed=20260727,
        )

    def test_the_point_estimate_recovers_the_constructed_sign(self) -> None:
        result = self._run()
        # famA spans beta_rate 0.8 down to -0.8 with a negative lambda, so the
        # high-minus-low spread is positive.
        assert result.point_estimates["famA"] > 0.0
        assert result.point_estimates["famB"] > 0.0

    def test_the_interval_brackets_the_point_estimate(self) -> None:
        result = self._run()
        for family in result.point_estimates.index:
            assert result.lower_95[family] <= result.point_estimates[family]
            assert result.point_estimates[family] <= result.upper_95[family]

    def test_the_ninety_interval_is_inside_the_ninety_five_interval(self) -> None:
        result = self._run()
        for family in result.point_estimates.index:
            assert result.lower_90[family] >= result.lower_95[family]
            assert result.upper_90[family] <= result.upper_95[family]

    def test_more_draws_do_not_move_the_point_estimate(self) -> None:
        few = self._run(draws=100)
        many = self._run(draws=400)
        pd.testing.assert_series_equal(few.point_estimates, many.point_estimates)

    def test_the_result_is_reproducible_from_the_seed(self) -> None:
        first = self._run(draws=120)
        second = self._run(draws=120)
        pd.testing.assert_series_equal(first.lower_95, second.lower_95)

    def test_every_draw_is_recorded(self) -> None:
        result = self._run(draws=150)
        assert result.draws == 150
        assert result.successful_draws <= 150
        assert result.successful_draws > 0

    def test_regime_labels_are_not_among_the_resampled_variables(self) -> None:
        result = self._run(draws=50)
        assert "regime" not in " ".join(result.resampled_variables)
        assert set(result.resampled_variables) == {
            "market_excess_return",
            "portfolio_excess_returns",
            "short_rate_level",
        }

    def test_mismatched_month_counts_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="same months"):
            self._run(market=np.zeros(10))

    def test_a_nonpositive_draw_count_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="draws must be positive"):
            self._run(draws=0)


class TestLaggedLevelRecovery:
    """The pre-window lag must be recoverable exactly from level and residual."""

    def _series(self, n: int = 200, seed: int = 9) -> tuple[FloatArray, FloatArray, FloatArray]:
        rng = np.random.default_rng(seed)
        full = np.zeros(n + 1)
        full[0] = 4.14
        for index in range(1, n + 1):
            full[index] = 0.05 + 0.99 * full[index - 1] + rng.normal(0.0, 0.4)
        level = full[1:]
        lagged = full[:-1]
        innovation = level - (0.05 + 0.99 * lagged)
        return level, lagged, innovation

    def test_it_recovers_the_interior_lags_to_machine_precision(self) -> None:
        level, _lagged, innovation = self._series()
        recovered = recover_lagged_level(level, innovation)
        np.testing.assert_allclose(recovered[1:], level[:-1], atol=1e-10)

    def test_it_recovers_the_pre_window_lag(self) -> None:
        """The first entry is the month before the window, absent from the panel."""
        level, lagged, innovation = self._series()
        recovered = recover_lagged_level(level, innovation)
        assert recovered[0] == pytest.approx(lagged[0], abs=1e-9)

    def test_mismatched_lengths_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="same months"):
            recover_lagged_level(np.zeros(10), np.zeros(9))

    def test_too_few_months_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="At least three months"):
            recover_lagged_level(np.zeros(2), np.zeros(2))

    def test_a_degenerate_autoregression_is_rejected(self) -> None:
        """A zero residual everywhere leaves the slope unidentified."""
        level = np.linspace(1.0, 2.0, 50)
        with pytest.raises(ValueError, match="degenerate"):
            recover_lagged_level(level, level.copy())
