"""Regime-specific fitted premia and the H3 equivalence decision.

The equivalence estimand fixed in ``research/economic_thresholds.md`` is the
rate-attributable fitted premium of *every* registered portfolio,

``pi_rate[i, s] = beta_rate[i, s] * lambda_rate[s]``,

not the extreme-decile spread that Milestone 9 bootstraps for the temporal
comparison. The two share an estimation chain but not an estimand, so the
per-portfolio version is implemented here rather than folded into
``models.block_bootstrap``: the gate binds on the maximum across all portfolios,
and collapsing to seven spreads would silently exempt the interior deciles.

Two contract clauses shape the resampling.

- ``research/inference_contract.md`` requires that the short-rate innovation be
  recomputed in every draw, and that blocks be resampled *within* regime for
  regime-specific inference. The autoregression is therefore re-estimated on the
  resampled months of the regime being evaluated, and the regime's point
  estimate uses the same within-regime innovation, so the point estimate and its
  interval describe one estimator rather than two.
- ``pi_rate`` is invariant to rescaling the innovation, which is what makes a
  within-regime innovation admissible for a cross-regime comparison at all. It
  is not invariant to an arbitrary redefinition of the factor, so the caller is
  expected to report the global-innovation point estimates as a labelled
  sensitivity.

Regime labels are never resampled. Only calendar months within a fixed labelled
window are drawn.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from short_rate_anomaly_regimes.models.block_bootstrap import (
    FloatArray,
    moving_block_indices,
)

#: Statistics recomputed in every draw alongside the per-portfolio premia.
STATISTIC_NAMES = ("lambda_rate", "rmse", "max_abs_error", "article_fit", "dispersion")

#: The confirmatory rule name, fixed in ``research/inference_contract.md``.
CONFIRMATORY_RULE = "tost_5pct_90pct_interval"

#: The stricter variant, which may never decide a classification.
SENSITIVITY_RULE = "strict_95pct_interval_sensitivity"


@dataclass(frozen=True, slots=True)
class RegimePremiumBootstrap:
    """Bootstrap distribution of one regime's per-portfolio fitted premia."""

    regime_id: str
    months: int
    assets: tuple[str, ...]
    point_premia: FloatArray
    premium_draws: FloatArray
    point_statistics: dict[str, float]
    statistic_draws: dict[str, FloatArray]
    block_length: int
    block_length_selected_by: str
    seed: int
    draws: int
    successful_draws: int


@dataclass(frozen=True, slots=True)
class EquivalenceOutcome:
    """One equivalence estimand evaluated against its predeclared bound."""

    estimand: str
    point_change: float
    lower_90: float
    upper_90: float
    lower_95: float
    upper_95: float
    bound: float
    one_sided: bool
    passes: bool
    passes_strict_sensitivity: bool
    decision_category: str
    rule: str = CONFIRMATORY_RULE


def evaluate_regime_sample(
    *,
    rate_level: FloatArray,
    lagged_rate_level: FloatArray,
    market: FloatArray,
    excess_returns: FloatArray,
) -> tuple[FloatArray, dict[str, float]]:
    """Run the whole estimation chain once on one regime sample.

    Recomputes the AR(1) short-rate innovation, the first-pass betas, the
    no-intercept second pass, the fitted premia, and every cross-sectional
    statistic the equivalence gates need.

    Args:
        rate_level: Short-rate level for each month of the regime window.
        lagged_rate_level: The one-month lag of the same level.
        market: Market excess return per month.
        excess_returns: Months by assets excess-return matrix.

    Returns:
        The per-portfolio fitted premia and the scalar statistics.

    Raises:
        ValueError: If the inputs disagree on the number of months.
    """
    n_months = excess_returns.shape[0]
    if not (rate_level.size == lagged_rate_level.size == market.size == n_months):
        raise ValueError("All regime inputs must cover the same months")

    ar_design = np.column_stack([np.ones(n_months), lagged_rate_level])
    ar_coefficients = np.linalg.lstsq(ar_design, rate_level, rcond=None)[0]
    innovation = rate_level - ar_design @ ar_coefficients

    factors = np.column_stack([np.ones(n_months), market, innovation])
    betas = np.linalg.lstsq(factors, excess_returns, rcond=None)[0][1:, :].T

    mean_returns = excess_returns.mean(axis=0)
    risk_prices = np.linalg.lstsq(betas, mean_returns, rcond=None)[0]
    pricing_errors = mean_returns - betas @ risk_prices
    premia = betas[:, 1] * risk_prices[1]

    denominator = float(np.var(mean_returns))
    if denominator == 0.0:
        raise ValueError("Cross-sectional variance of average returns is zero")
    statistics = {
        "lambda_rate": float(risk_prices[1]),
        "rmse": float(np.sqrt(np.mean(pricing_errors**2))),
        "max_abs_error": float(np.max(np.abs(pricing_errors))),
        "article_fit": 1.0 - float(np.var(pricing_errors)) / denominator,
        # Population dispersion. The gate is a ratio between regimes over the
        # same N, so the degrees-of-freedom convention cancels.
        "dispersion": float(np.std(premia)),
    }
    return premia, statistics


def bootstrap_regime_premia(
    *,
    regime_id: str,
    assets: tuple[str, ...],
    rate_level: FloatArray,
    lagged_rate_level: FloatArray,
    market: FloatArray,
    excess_returns: FloatArray,
    block_length: int,
    draws: int,
    seed: int,
    block_length_selected_by: str = "politis_white",
) -> RegimePremiumBootstrap:
    """Bootstrap one regime's per-portfolio fitted premia within its own window.

    Args:
        regime_id: Frozen regime label, carried through for provenance.
        assets: Portfolio names in the column order of ``excess_returns``.
        rate_level: Short-rate level aligned to the regime months.
        lagged_rate_level: The one-month lag of the same level.
        market: Market excess return per month.
        excess_returns: Months by assets excess-return matrix.
        block_length: Moving-block length in months.
        draws: Number of bootstrap repetitions.
        seed: Random seed for this regime.
        block_length_selected_by: How the block length was chosen.

    Returns:
        The point estimates and the retained draw-level distribution.

    Raises:
        ValueError: If the asset labels do not match the return matrix, or if
            every draw fails to solve.
    """
    if len(assets) != excess_returns.shape[1]:
        raise ValueError("Asset labels and return columns disagree")
    point_premia, point_statistics = evaluate_regime_sample(
        rate_level=rate_level,
        lagged_rate_level=lagged_rate_level,
        market=market,
        excess_returns=excess_returns,
    )

    n_months = excess_returns.shape[0]
    rng = np.random.default_rng(seed)
    premium_draws = np.empty((draws, len(assets)), dtype=float)
    statistic_draws = {name: np.empty(draws, dtype=float) for name in STATISTIC_NAMES}
    successes = 0
    for _ in range(draws):
        positions = moving_block_indices(n_months, block_length=block_length, rng=rng)
        try:
            premia, statistics = evaluate_regime_sample(
                rate_level=rate_level[positions],
                lagged_rate_level=lagged_rate_level[positions],
                market=market[positions],
                excess_returns=excess_returns[positions, :],
            )
        except (np.linalg.LinAlgError, ValueError):
            continue
        premium_draws[successes, :] = premia
        for name in STATISTIC_NAMES:
            statistic_draws[name][successes] = statistics[name]
        successes += 1
    if successes == 0:
        raise ValueError(f"Every bootstrap draw failed for regime {regime_id}")

    return RegimePremiumBootstrap(
        regime_id=regime_id,
        months=n_months,
        assets=assets,
        point_premia=point_premia,
        premium_draws=premium_draws[:successes, :],
        point_statistics=point_statistics,
        statistic_draws={name: values[:successes] for name, values in statistic_draws.items()},
        block_length=block_length,
        block_length_selected_by=block_length_selected_by,
        seed=seed,
        draws=draws,
        successful_draws=successes,
    )


def paired_difference_draws(first: FloatArray, second: FloatArray) -> FloatArray:
    """Difference two independent bootstrap samples draw by draw.

    The two regimes partition the calendar, so their bootstrap distributions are
    independent. Pairing the draws index-wise therefore samples the product
    distribution, and the differences are a valid bootstrap sample for the
    change. Unequal success counts are truncated to the shorter run so that no
    draw is reused.

    Args:
        first: Draws for the regime under test.
        second: Draws for the reference regime.

    Returns:
        The draw-level differences, ``first - second``.
    """
    usable = min(first.shape[0], second.shape[0])
    return first[:usable] - second[:usable]


def classify_equivalence(
    *,
    estimand: str,
    point_change: float,
    change_draws: FloatArray,
    bound: float,
    one_sided: bool = False,
) -> EquivalenceOutcome:
    """Apply the frozen TOST rule to one estimand.

    Equivalence is supported only when the entire two-sided 90 percent
    percentile interval lies inside the declared bound, which is the standard
    5 percent two one-sided tests procedure. For a one-sided deterioration bound
    only the upper end is compared, which is the corresponding 5 percent
    one-sided test. The 95 percent interval is evaluated in parallel and
    reported under the sensitivity label; it never decides anything.

    Failing this test does not establish a difference. The returned
    ``decision_category`` therefore separates the two ways a failure arises:
    ``inconclusive`` when the interval merely straddles the bound, which is a
    statement about precision, and ``difference_exceeds_bound`` when the whole
    interval lies beyond it, which is evidence of a real change. Only the latter
    may be described as a detected difference.

    Args:
        estimand: Name of the quantity being compared.
        point_change: The observed change.
        change_draws: Bootstrap draws of the change.
        bound: The predeclared equivalence bound.
        one_sided: Whether the bound constrains deterioration only.

    Returns:
        The classified outcome.
    """
    lower_90, upper_90 = (float(v) for v in np.quantile(change_draws, [0.05, 0.95]))
    lower_95, upper_95 = (float(v) for v in np.quantile(change_draws, [0.025, 0.975]))
    if one_sided:
        passes = upper_90 <= bound
        strict = upper_95 <= bound
        beyond = lower_90 > bound
    else:
        passes = lower_90 >= -bound and upper_90 <= bound
        strict = lower_95 >= -bound and upper_95 <= bound
        beyond = lower_90 > bound or upper_90 < -bound
    if passes:
        category = "equivalent_within_bound"
    elif beyond:
        category = "difference_exceeds_bound"
    else:
        category = "inconclusive"
    return EquivalenceOutcome(
        estimand=estimand,
        point_change=point_change,
        lower_90=lower_90,
        upper_90=upper_90,
        lower_95=lower_95,
        upper_95=upper_95,
        bound=bound,
        one_sided=one_sided,
        passes=bool(passes),
        passes_strict_sensitivity=bool(strict),
        decision_category=category,
    )
