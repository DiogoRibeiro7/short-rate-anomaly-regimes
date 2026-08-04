"""Tests for the article's exact second pass, fit metric, and specification test."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.article_second_pass import (
    ArticleSecondPassResult,
    article_cross_sectional_fit,
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)


@dataclass(frozen=True)
class System:
    """A cross-section whose risk prices are known by construction."""

    mean_returns: pd.Series
    betas: pd.DataFrame
    residual_covariance: pd.DataFrame
    factor_covariance: pd.DataFrame
    n_months: int
    residuals: pd.DataFrame


def _system(
    *,
    n_assets: int = 25,
    n_months: int = 504,
    true_prices: tuple[float, ...] = (0.55, -0.30),
    seed: int = 20260804,
    residual_sd: float = 0.0,
) -> System:
    """Build a cross-section whose risk prices are known by construction."""
    rng = np.random.default_rng(seed)
    assets = [f"asset_{index:02d}" for index in range(n_assets)]
    factors = ["mkt", "rate"]
    betas = pd.DataFrame(
        np.column_stack(
            [
                rng.uniform(0.6, 1.5, n_assets),
                rng.uniform(-1.2, 1.2, n_assets),
            ]
        ),
        index=assets,
        columns=factors,
    )
    mean_returns = pd.Series(
        betas.to_numpy(dtype=float) @ np.array(true_prices)
        + rng.normal(0.0, residual_sd, n_assets),
        index=assets,
        name="mean_return",
    )
    residuals = pd.DataFrame(
        rng.normal(0.0, 4.0, (n_months, n_assets)),
        index=pd.period_range("1972-01", periods=n_months, freq="M"),
        columns=assets,
    )
    factor_covariance = pd.DataFrame([[21.0, -0.4], [-0.4, 0.35]], index=factors, columns=factors)
    return System(
        mean_returns=mean_returns,
        betas=betas,
        residual_covariance=residuals.cov(),
        factor_covariance=factor_covariance,
        n_months=n_months,
        residuals=residuals,
    )


def _estimate(parts: System, **overrides: object) -> ArticleSecondPassResult:
    kwargs: dict[str, object] = {
        "mean_excess_returns": parts.mean_returns,
        "betas": parts.betas,
        "residual_covariance": parts.residual_covariance,
        "factor_covariance": parts.factor_covariance,
        "n_months": parts.n_months,
        "portfolio_set": "test_set",
        "model": "market_plus_rate",
    }
    kwargs.update(overrides)
    return estimate_article_second_pass(**kwargs)  # type: ignore[arg-type]


class TestRiskPriceRecovery:
    """The estimator must recover risk prices it was given by construction."""

    def test_exact_recovery_without_cross_sectional_noise(self) -> None:
        parts = _system(residual_sd=0.0)
        result = _estimate(parts)
        np.testing.assert_allclose(
            result.risk_prices.to_numpy(dtype=float), [0.55, -0.30], atol=1e-10
        )
        assert result.max_absolute_pricing_error == pytest.approx(0.0, abs=1e-10)

    def test_a_perfect_fit_gives_unit_cross_sectional_fit(self) -> None:
        result = _estimate(_system(residual_sd=0.0))
        assert result.article_cross_sectional_fit == pytest.approx(1.0, abs=1e-10)

    def test_noise_degrades_the_fit_but_keeps_the_signs(self) -> None:
        result = _estimate(_system(residual_sd=0.15))
        assert result.article_cross_sectional_fit < 1.0
        assert result.risk_prices["mkt"] > 0.0
        assert result.risk_prices["rate"] < 0.0

    def test_the_second_pass_has_no_intercept(self) -> None:
        """A no-intercept fit leaves a generally non-zero mean pricing error."""
        result = _estimate(_system(residual_sd=0.20, seed=7))
        assert "const" not in result.risk_prices.index
        assert list(result.risk_prices.index) == ["mkt", "rate"]
        assert abs(result.diagnostics["mean_pricing_error"]) > 0.0


class TestArticleFitMetric:
    """The article metric is centred and differs from the uncentred fallback."""

    def test_it_is_the_centred_variance_ratio(self) -> None:
        returns = pd.Series([1.0, 2.0, 3.0, 4.0], index=list("abcd"))
        errors = pd.Series([0.5, -0.5, 0.5, -0.5], index=list("abcd"))
        expected = 1.0 - float(np.var(errors.to_numpy())) / float(np.var(returns.to_numpy()))
        assert article_cross_sectional_fit(returns, errors) == pytest.approx(expected)

    def test_it_differs_from_the_uncentred_pseudo_fit_when_errors_are_biased(self) -> None:
        returns = pd.Series([1.0, 2.0, 3.0, 4.0], index=list("abcd"))
        errors = pd.Series([0.6, 0.6, 0.6, 0.6], index=list("abcd"))
        centred = article_cross_sectional_fit(returns, errors)
        uncentred = 1.0 - float(np.sum(errors**2)) / float(np.sum(returns**2))
        # Constant errors have zero cross-sectional variance, so the article
        # metric is 1 while the uncentred fallback is not.
        assert centred == pytest.approx(1.0)
        assert uncentred != pytest.approx(centred)

    def test_it_is_invariant_to_the_degrees_of_freedom_convention(self) -> None:
        returns = pd.Series([1.0, 2.5, 0.4, 3.1, 2.2], index=list("abcde"))
        errors = pd.Series([0.2, -0.4, 0.1, 0.3, -0.2], index=list("abcde"))
        population = 1.0 - float(np.var(errors, ddof=0)) / float(np.var(returns, ddof=0))
        sample = 1.0 - float(np.var(errors, ddof=1)) / float(np.var(returns, ddof=1))
        assert population == pytest.approx(sample)
        assert article_cross_sectional_fit(returns, errors) == pytest.approx(population)

    def test_it_can_be_negative(self) -> None:
        returns = pd.Series([0.4, 0.5, 0.45, 0.55], index=list("abcd"))
        errors = pd.Series([2.0, -2.0, 1.5, -1.5], index=list("abcd"))
        assert article_cross_sectional_fit(returns, errors) < 0.0

    def test_misaligned_inputs_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="share an index"):
            article_cross_sectional_fit(
                pd.Series([1.0, 2.0], index=["a", "b"]),
                pd.Series([0.1, 0.2], index=["a", "c"]),
            )

    def test_a_degenerate_cross_section_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="variance of average returns is zero"):
            article_cross_sectional_fit(
                pd.Series([1.0, 1.0, 1.0], index=list("abc")),
                pd.Series([0.1, 0.2, 0.3], index=list("abc")),
            )


class TestShankenInference:
    """Shanken inference must inflate ordinary errors and scale with the sample."""

    def test_the_multiplier_exceeds_one_and_widens_the_standard_errors(self) -> None:
        result = _estimate(_system(residual_sd=0.1))
        assert result.shanken_multiplier > 1.0
        assert bool((result.shanken_standard_errors > result.ordinary_standard_errors).all())

    def test_standard_errors_shrink_with_the_root_of_the_sample(self) -> None:
        short = _estimate(_system(residual_sd=0.1, n_months=504))
        long = _estimate(_system(residual_sd=0.1, n_months=2016))
        ratio = short.shanken_standard_errors["mkt"] / long.shanken_standard_errors["mkt"]
        # Only the residual term carries 1/T here because the same residual
        # covariance is reused, so the ratio sits at the two-fold root bound.
        assert 1.9 < ratio < 2.1

    def test_the_specification_test_has_n_minus_k_degrees_of_freedom(self) -> None:
        result = _estimate(_system(n_assets=25, residual_sd=0.1))
        assert result.chi_square_degrees_of_freedom == 23
        assert result.n_factors == 2

    def test_a_perfect_fit_produces_a_negligible_statistic(self) -> None:
        result = _estimate(_system(residual_sd=0.0))
        assert result.chi_square_statistic == pytest.approx(0.0, abs=1e-6)
        assert result.chi_square_asymptotic_p_value == pytest.approx(1.0, abs=1e-6)

    def test_larger_pricing_errors_raise_the_statistic(self) -> None:
        small = _estimate(_system(residual_sd=0.05, seed=3))
        large = _estimate(_system(residual_sd=0.50, seed=3))
        assert large.chi_square_statistic > small.chi_square_statistic

    def test_the_pseudo_inverse_tolerance_is_recorded(self) -> None:
        result = _estimate(_system(residual_sd=0.1))
        assert result.pseudo_inverse_rcond == 1e-15


class TestGuards:
    """Misuse must fail loudly rather than produce a plausible number."""

    def test_misaligned_betas_are_rejected(self) -> None:
        parts = _system()
        betas = parts.betas.copy()
        betas.index = [f"other_{index}" for index in range(len(betas))]
        with pytest.raises(ValueError, match="same assets as the mean returns"):
            _estimate(parts, betas=betas)

    def test_misaligned_factor_covariance_is_rejected(self) -> None:
        parts = _system()
        bad = pd.DataFrame([[1.0, 0.0], [0.0, 1.0]], index=["a", "b"], columns=["a", "b"])
        with pytest.raises(ValueError, match="indexed by the beta columns"):
            _estimate(parts, factor_covariance=bad)

    def test_too_few_assets_are_rejected(self) -> None:
        parts = _system(n_assets=2)
        with pytest.raises(ValueError, match="more assets than priced factors"):
            _estimate(parts)

    def test_a_rank_deficient_beta_matrix_is_rejected(self) -> None:
        parts = _system()
        betas = parts.betas.copy()
        betas["rate"] = betas["mkt"] * 2.0
        with pytest.raises(ValueError, match="rank deficient"):
            _estimate(parts, betas=betas)

    def test_a_nonpositive_month_count_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="n_months must be positive"):
            _estimate(_system(), n_months=0)


class TestResidualCovariance:
    """The residual covariance feeding Shanken must be complete and well posed."""

    def test_it_is_the_asset_covariance_of_the_residual_panel(self) -> None:
        parts = _system()
        residuals = parts.residuals
        covariance = residual_covariance_from_first_pass(residuals)
        assert list(covariance.index) == list(residuals.columns)
        pd.testing.assert_frame_equal(covariance, residuals.cov())

    def test_missing_residuals_are_rejected(self) -> None:
        parts = _system()
        residuals = parts.residuals.copy()
        residuals.iloc[0, 0] = np.nan
        with pytest.raises(ValueError, match="must be complete"):
            residual_covariance_from_first_pass(residuals)

    def test_a_singular_short_panel_is_rejected(self) -> None:
        parts = _system(n_assets=25, n_months=20)
        with pytest.raises(ValueError, match="more months than assets"):
            residual_covariance_from_first_pass(parts.residuals)
