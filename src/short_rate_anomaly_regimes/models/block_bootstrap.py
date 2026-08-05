"""Politis-White block-length selection and the joint moving-block bootstrap.

The bootstrap contract in ``research/bootstrap_contract.md`` fixes a moving-block
bootstrap with an automatic Politis-White block length, a declared fallback, and
joint monthly resampling of the stochastic variables. The selector is
implemented here rather than taken from a library so that the exact formula used
by every generated interval is auditable in the repository.

The estimator recomputation is deliberately written in plain array algebra. A
draw re-estimates the short-rate innovation, every first-pass beta, the
no-intercept second pass, and the fitted premia, so it runs tens of thousands of
times; routing that through a general regression package would make the declared
10,000 repetitions impractical and would not change any number.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

#: Array aliases. The bare ``np.ndarray`` used elsewhere in this package is
#: rejected by newer numpy stubs, so new code parameterises it explicitly.
FloatArray = npt.NDArray[np.floating[Any]]
IndexArray = npt.NDArray[np.integer[Any]]

#: Declared fallback when the selector cannot be trusted, from the bootstrap
#: contract. One year preserves seasonal accounting and portfolio-formation
#: dependence while avoiding a result-dependent block choice.
FALLBACK_BLOCK_LENGTH = 12

#: The selector is rejected outside this closed interval, per the contract.
MINIMUM_BLOCK_LENGTH = 2
MAXIMUM_BLOCK_LENGTH = 24

#: The contract requires at least this many complete factor months.
MINIMUM_MONTHS_FOR_SELECTOR = 60


@dataclass(frozen=True, slots=True)
class BlockLengthSelection:
    """Outcome of the Politis-White block-length selection."""

    block_length: int
    selected_by: str
    raw_optimal_lengths: tuple[float, ...]
    failure_reasons: tuple[str, ...]
    months: int


@dataclass(frozen=True, slots=True)
class FittedPremiumBootstrap:
    """Bootstrap distribution of the rate-attributable fitted-premium spreads."""

    estimand: str
    point_estimates: pd.Series
    lower_95: pd.Series
    upper_95: pd.Series
    lower_90: pd.Series
    upper_90: pd.Series
    draws: int
    successful_draws: int
    block_length: int
    block_length_selected_by: str
    seed: int
    resampled_variables: tuple[str, ...]
    diagnostics: dict[str, float] = field(default_factory=dict)


def _flat_top_kernel(fractions: FloatArray) -> FloatArray:
    """Evaluate the Politis-White flat-top trapezoidal lag window."""
    absolute = np.abs(fractions)
    weights = np.zeros_like(absolute, dtype=float)
    weights[absolute <= 0.5] = 1.0
    middle = (absolute > 0.5) & (absolute <= 1.0)
    weights[middle] = 2.0 * (1.0 - absolute[middle])
    return weights


def _optimal_block_length_single(values: FloatArray) -> float:
    """Compute the Politis-White moving-block optimal length for one series.

    Implements Politis and White (2004) with the Patton, Politis and White (2009)
    correction, specialised to the circular or moving block bootstrap, for which
    the denominator constant is ``4/3`` rather than the stationary bootstrap's
    ``2``.

    Args:
        values: One demeanable series.

    Returns:
        The optimal block length before the contract's bounds are applied.

    Raises:
        ValueError: If the series has no variation.
    """
    series = np.asarray(values, dtype=float)
    n = series.size
    centred = series - series.mean()
    variance = float(np.dot(centred, centred) / n)
    if variance <= 0.0:
        raise ValueError("Series has zero sample variance")

    # Correlogram-based bandwidth. The flat-top rule takes the smallest lag
    # beyond which the next K_N autocorrelations are all insignificant.
    max_lag = int(min(np.ceil(8.0 * (np.log10(n) ** 2)), n - 1))
    max_lag = max(max_lag, 1)
    autocovariance = np.array(
        [float(np.dot(centred[: n - k], centred[k:]) / n) for k in range(max_lag + 1)]
    )
    if not np.all(np.isfinite(autocovariance)):
        raise ValueError("Series has non-finite autocovariances")
    autocorrelation = autocovariance / autocovariance[0]

    threshold = 2.0 * np.sqrt(np.log10(n) / n)
    window = int(max(5, np.sqrt(np.log10(n))))
    chosen_lag = max_lag
    for lag in range(1, max_lag + 1):
        upper = min(lag + window, max_lag)
        if upper <= lag:
            break
        if np.all(np.abs(autocorrelation[lag : upper + 1]) < threshold):
            chosen_lag = lag - 1
            break
    bandwidth = max(1, min(2 * max(chosen_lag, 1), max_lag))

    lags = np.arange(-bandwidth, bandwidth + 1)
    weights = _flat_top_kernel(lags / bandwidth)
    symmetric = np.array([autocovariance[abs(int(lag))] for lag in lags])
    g_hat = float(np.sum(weights * np.abs(lags) * symmetric))
    spectrum_at_zero = float(np.sum(weights * symmetric))
    denominator = (4.0 / 3.0) * spectrum_at_zero**2
    if denominator <= 0.0 or not np.isfinite(denominator) or not np.isfinite(g_hat):
        raise ValueError("Non-finite Politis-White intermediate quantities")
    return float((2.0 * g_hat**2 / denominator) ** (1.0 / 3.0) * n ** (1.0 / 3.0))


def select_block_length(factors: pd.DataFrame) -> BlockLengthSelection:
    """Select the moving-block length under the frozen contract.

    The selector runs on each supplied factor and the maximum is taken, so that
    the block is long enough for the most persistent series in the system. Every
    declared failure condition falls back to the fixed 12-month block and is
    recorded rather than silently absorbed.

    Args:
        factors: Complete factor months, one column per series.

    Returns:
        The selection outcome, including why the value was chosen.
    """
    reasons: list[str] = []
    months = len(factors)
    if months < MINIMUM_MONTHS_FOR_SELECTOR:
        reasons.append(f"fewer than {MINIMUM_MONTHS_FOR_SELECTOR} complete factor months")
    if factors.isna().to_numpy().any():
        reasons.append("factor panel contains missing months")

    raw: list[float] = []
    if not reasons:
        for column in factors.columns:
            try:
                raw.append(_optimal_block_length_single(factors[column].to_numpy(dtype=float)))
            except ValueError as error:
                reasons.append(f"{column}: {error}")

    if reasons or not raw:
        return BlockLengthSelection(
            block_length=FALLBACK_BLOCK_LENGTH,
            selected_by="declared_fallback",
            raw_optimal_lengths=tuple(raw),
            failure_reasons=tuple(reasons),
            months=months,
        )

    candidate = float(np.max(raw))
    if not np.isfinite(candidate):
        return BlockLengthSelection(
            block_length=FALLBACK_BLOCK_LENGTH,
            selected_by="declared_fallback",
            raw_optimal_lengths=tuple(raw),
            failure_reasons=("selector returned a non-finite block length",),
            months=months,
        )
    rounded = int(np.ceil(candidate))
    if rounded < MINIMUM_BLOCK_LENGTH or rounded > MAXIMUM_BLOCK_LENGTH:
        return BlockLengthSelection(
            block_length=FALLBACK_BLOCK_LENGTH,
            selected_by="declared_fallback",
            raw_optimal_lengths=tuple(raw),
            failure_reasons=(
                f"selected block length {rounded} lies outside "
                f"[{MINIMUM_BLOCK_LENGTH}, {MAXIMUM_BLOCK_LENGTH}]",
            ),
            months=months,
        )
    return BlockLengthSelection(
        block_length=rounded,
        selected_by="politis_white",
        raw_optimal_lengths=tuple(raw),
        failure_reasons=(),
        months=months,
    )


def moving_block_indices(
    n_months: int,
    *,
    block_length: int,
    rng: np.random.Generator,
) -> IndexArray:
    """Draw one moving-block resample of month positions.

    Blocks overlap and are drawn with replacement from every admissible start,
    then concatenated and truncated to the original length.

    Args:
        n_months: Length of the original monthly sample.
        block_length: Block length in months.
        rng: Random generator.

    Returns:
        An array of ``n_months`` positions into the original sample.

    Raises:
        ValueError: If the block length does not fit the sample.
    """
    if block_length < 1 or block_length > n_months:
        raise ValueError("Block length must lie between one month and the sample length")
    n_blocks = int(np.ceil(n_months / block_length))
    starts = rng.integers(0, n_months - block_length + 1, size=n_blocks)
    offsets = np.arange(block_length)
    positions: IndexArray = (starts[:, None] + offsets[None, :]).reshape(-1)[:n_months]
    return positions


def _ols(design: FloatArray, targets: FloatArray) -> FloatArray:
    """Solve a least-squares system, returning coefficients as columns per target."""
    coefficients: FloatArray = np.linalg.lstsq(design, targets, rcond=None)[0]
    return coefficients


def recover_lagged_level(level: FloatArray, innovation: FloatArray) -> FloatArray:
    """Recover the lagged short-rate level implied by a level and its AR residual.

    Under the frozen pre-window-lag timing convention the first window month is
    regressed on the level of the month *before* the window, which the canonical
    panel does not carry. The panel does carry both the level and the AR
    residual, and those identify the fitted value ``a + rho * lagged``. Fitting
    ``a`` and ``rho`` on the interior months, where the lag is observed, and
    inverting recovers the lag for every month including the first.

    The inversion is exact rather than approximate: the same two parameters
    generated the residual, so the recovered interior lags reproduce the observed
    previous-month levels to machine precision.

    Args:
        level: Short-rate level over the estimation window.
        innovation: The AR(1) residual over the same months.

    Returns:
        The lagged level for every month in the window.

    Raises:
        ValueError: If the inputs disagree in length, are too short, or imply a
            degenerate autoregression.
    """
    if level.size != innovation.size:
        raise ValueError("Level and innovation must cover the same months")
    if level.size < 3:
        raise ValueError("At least three months are needed to recover the lag")
    fitted = level - innovation
    design = np.column_stack([np.ones(level.size - 1), level[:-1]])
    intercept, slope = _ols(design, fitted[1:])
    if not np.isfinite(slope) or abs(slope) < 1e-12:
        raise ValueError("Recovered autoregressive slope is degenerate")
    recovered: FloatArray = (fitted - intercept) / slope
    return recovered


def bootstrap_fitted_premium_spreads(
    *,
    rate_level: FloatArray,
    lagged_rate_level: FloatArray,
    market: FloatArray,
    excess_returns: FloatArray,
    spread_pairs: dict[str, tuple[int, int]],
    block_length: int,
    draws: int,
    seed: int,
    selected_by: str = "politis_white",
) -> FittedPremiumBootstrap:
    """Bootstrap the rate-attributable fitted-premium spread for each family.

    Each draw resamples calendar months jointly across every stochastic variable
    and then recomputes the whole chain: the AR(1) short-rate innovation, the
    first-pass betas, the no-intercept second pass, and the fitted premia
    ``pi_i = beta_i_rate * lambda_rate``. The reported estimand per family is the
    spread between the extreme deciles, ``pi(decile_10) - pi(decile_01)``, which
    is the object the article tabulates as ``DIF`` in Table 5.

    The AR(1) is re-estimated on resampled ``(r_t, r_{t-1})`` pairs, so the lag
    relation travels with the month rather than being broken at block joins.

    Regime labels are not among the resampled variables. Nothing here resamples
    an asset or a label; only calendar months are drawn.

    Args:
        rate_level: Short-rate level aligned to the estimation months.
        lagged_rate_level: The one-month lag of the same level.
        market: Market excess return per month.
        excess_returns: Months by assets excess-return matrix.
        spread_pairs: Family name mapped to the (low, high) asset column indices.
        block_length: Moving-block length in months.
        draws: Number of bootstrap repetitions.
        seed: Project random seed.
        selected_by: How the block length was chosen, recorded on the result.

    Returns:
        The bootstrap result with percentile intervals per family.

    Raises:
        ValueError: If the inputs disagree on the number of months.
    """
    n_months, n_assets = excess_returns.shape
    if not (rate_level.size == lagged_rate_level.size == market.size == n_months):
        raise ValueError("All bootstrap inputs must cover the same months")
    if draws < 1:
        raise ValueError("draws must be positive")

    families = list(spread_pairs)
    rng = np.random.default_rng(seed)

    def _one(positions: IndexArray) -> FloatArray:
        current = rate_level[positions]
        lagged = lagged_rate_level[positions]
        ar_design = np.column_stack([np.ones(n_months), lagged])
        ar_coefficients = _ols(ar_design, current)
        innovation = current - ar_design @ ar_coefficients

        factors = np.column_stack([np.ones(n_months), market[positions], innovation])
        betas = _ols(factors, excess_returns[positions, :])[1:, :].T  # assets by 2

        mean_returns = excess_returns[positions, :].mean(axis=0)
        risk_prices = _ols(betas, mean_returns)
        premia = betas[:, 1] * risk_prices[1]
        return np.array([premia[high] - premia[low] for low, high in spread_pairs.values()])

    point = _one(np.arange(n_months))

    collected = np.empty((draws, len(families)), dtype=float)
    successes = 0
    for _ in range(draws):
        positions = moving_block_indices(n_months, block_length=block_length, rng=rng)
        try:
            collected[successes, :] = _one(positions)
        except np.linalg.LinAlgError:
            continue
        successes += 1
    if successes == 0:
        raise ValueError("Every bootstrap draw failed to solve")
    realised = collected[:successes, :]

    def _quantile(level: float) -> pd.Series:
        return pd.Series(np.quantile(realised, level, axis=0), index=families)

    return FittedPremiumBootstrap(
        estimand="rate_attributable_fitted_premium_spread_decile_10_minus_decile_01",
        point_estimates=pd.Series(point, index=families),
        lower_95=_quantile(0.025),
        upper_95=_quantile(0.975),
        lower_90=_quantile(0.05),
        upper_90=_quantile(0.95),
        draws=draws,
        successful_draws=successes,
        block_length=block_length,
        block_length_selected_by=selected_by,
        seed=seed,
        resampled_variables=(
            "market_excess_return",
            "portfolio_excess_returns",
            "short_rate_level",
        ),
        diagnostics={
            "bootstrap_mean_bias": float(np.mean(realised.mean(axis=0) - point)),
            "max_interval_width_95": float(
                np.max(np.quantile(realised, 0.975, axis=0) - np.quantile(realised, 0.025, axis=0))
            ),
        },
    )
