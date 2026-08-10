"""Simulate the sampling precision of this design's regime-specific estimates.

This is a decision-support artifact, not a design change. It answers one
question: at a given number of months, how reliably does *this* design recover a
regime-specific short-rate risk price and the rate-attributable fitted-premium
spread? Nothing here evaluates, proposes, or alters a threshold. The frozen
floors in ``configs/regimes.yaml`` appear only as reference marks on a curve.

The data-generating process is calibrated to the actual estimated system on the
current 648-month regime panel: real first-pass betas, the real factor
covariance, the real first-pass residual covariance, and the risk prices the
design's own second pass produces on that panel. Simulated windows are drawn from
that calibrated system and re-estimated with the design's own second pass,
:func:`estimate_article_second_pass`, so the reported precision is a property of
this estimator rather than of a textbook one.

Three implementation choices are declared rather than hidden.

- The first pass inside the replication loop is plain least squares, following
  the pattern in :mod:`short_rate_anomaly_regimes.models.block_bootstrap`. The
  first-pass HAC covariance never enters the second pass, so this changes no
  simulated number; it only makes the loop feasible. The *calibration* first pass
  is the full project estimator, :func:`estimate_time_series_betas`.
- The Shanken covariance is reported twice. The **feasible** version uses the
  simulated sample residual covariance built by
  :func:`residual_covariance_from_first_pass`. That covariance exists at every
  window length, but below ``T = N + 1`` months it is rank deficient, so on the
  confirmatory 70-portfolio system it is of full rank only from 71 months. This
  sweep reports the feasible interval only where the covariance is of full rank,
  which is a declared reporting choice, not a statement that it cannot be
  computed below that point: the estimator never inverts the residual covariance
  and tolerates rank deficiency throughout. The **oracle** version substitutes
  the calibrated population residual covariance, is available at every window
  length, and is infeasible in practice; it isolates how much of the short-window
  problem is the risk price itself rather than the covariance estimate.
- The calibration treats the full-sample estimated betas as the true betas, which
  is what a calibration to the actual estimated system means. It follows that the
  simulated data-generating process is **not a fixed point** of the two-pass
  estimator: a first pass run on a simulated window produces noisier betas than
  the noiseless ones the process was built from, and the no-intercept second pass
  therefore attenuates the risk price toward zero at every window length,
  including the calibration length itself. The calibration-length row is carried
  in the sweep so that attenuation can be read off directly, and
  :func:`first_pass_beta_reliability` records what fraction of the observed
  cross-sectional beta dispersion is genuine exposure dispersion rather than
  first-pass sampling noise. Because the real betas are themselves noisy
  estimates, the simulated cross-section is better identified than the real one,
  so every precision number reported here is, if anything, optimistic.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.time_series import (
    automatic_newey_west_lags,
    estimate_time_series_betas,
)
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS

#: Array alias. Newer numpy stubs reject a bare ``np.ndarray``, so new code
#: parameterises it exactly as ``models/block_bootstrap.py`` does.
FloatArray = npt.NDArray[np.floating[Any]]

PANEL_PARQUET = Path("data/processed/regimes/monthly_regimes.parquet")
CURVE_CSV = Path("artifacts/tables/regimes/eligibility_power_curve.csv")
DIAGNOSTIC_JSON = Path("artifacts/diagnostics/regime_eligibility_power.json")
PROVENANCE_JSON = Path("artifacts/provenance/regime_power_analysis.json")

RATE = "fedfunds"
MODEL = "market_plus_fedfunds_innovation"
MARKET_FACTOR = "market_excess_return"
RATE_FACTOR = f"short_rate_innovation__{RATE}"
FACTOR_COLUMNS: tuple[str, str] = (MARKET_FACTOR, RATE_FACTOR)

JOINT_SYSTEM = "joint_70_portfolio"
FAMILY_SYSTEM = "family_10_decile"
FAMILIES: tuple[str, ...] = tuple(FAMILY_MEMBERS)
DECILE_LABELS: tuple[str, ...] = tuple(f"decile_{index:02d}" for index in range(1, 11))
LOW_DECILE = DECILE_LABELS[0]
HIGH_DECILE = DECILE_LABELS[-1]

#: Window sweep. The required grid {12, 18, 24, 30, 36, 48, 60, 84, 120, 240} is
#: extended with the observed length of every registered regime (15, 51, 444),
#: with 72 months, the shortest window on the grid at which the sample residual
#: covariance of the 70-portfolio system is of full rank, and with 648 months,
#: the calibration length, which serves as the reference row.
WINDOW_LENGTHS: tuple[int, ...] = (
    12,
    15,
    18,
    24,
    30,
    36,
    48,
    51,
    60,
    72,
    84,
    120,
    180,
    240,
    444,
    648,
)

#: Replications per window length. 2,000 puts the Monte Carlo standard error of a
#: coverage probability near 0.90 at about 0.007 and the relative Monte Carlo
#: error of a reported standard deviation at about 1.6 percent, finer than any
#: distinction this report draws. Every reported statistic carries its own Monte
#: Carlo standard error in the curve file.
REPLICATIONS = 2_000

#: The project seed from ``configs/baseline.yaml``, reused so this study is not
#: seeded on a value chosen after seeing a result. Each window length runs on the
#: derived stream ``SEED + window_months`` so windows are independent and any one
#: of them can be reproduced on its own.
SEED = 20260727

#: Two-sided 95 percent normal quantile. The design's Shanken inference is
#: asymptotic, so the interval is ``lambda_hat +/- z * shanken_standard_error``.
NORMAL_95_QUANTILE = 1.959963984540054

#: ``research/economic_thresholds.md``: the economic bound on a rate-attributable
#: fitted premium, in monthly percentage points.
ECONOMIC_BOUND = 0.25

#: ``configs/regimes.yaml``, ``regime_estimation_eligibility``. Reference marks
#: only. This script never evaluates, proposes, or writes a threshold.
FROZEN_FIRST_PASS_FLOOR_MONTHS = 36
FROZEN_SECOND_PASS_FLOOR_MONTHS = 72
FROZEN_MINIMUM_TEST_ASSETS = 10

#: ``research/regime_registry.csv``, primary transition rule, current vintage.
#: Every one of these lengths is a point on ``WINDOW_LENGTHS`` by construction.
REGISTERED_REGIME_MONTHS: dict[str, int] = {
    "conventional_pre_elb": 444,
    "elb_qe": 84,
    "normalisation": 51,
    "inflation_tightening": 30,
    "pandemic_elb_qe": 24,
    "post_tightening_easing": 15,
}

#: Reporting conventions used to read the curve. These are *not* thresholds, are
#: not registered anywhere, and are not proposed as replacements for anything.
#: They exist so the curve can be summarised as "criterion met from month X".
SIGN_ERROR_READING_LEVEL = 0.05
COVERAGE_READING_LOW = 0.90
COVERAGE_READING_HIGH = 0.99
ATTENUATION_READING_LEVELS: tuple[float, ...] = (0.50, 0.90)

#: Text repeated into every generated artifact so no consumer can read the curve
#: without the disclosure attached. The floor months are interpolated from the
#: reference-mark constants rather than written out, so the disclosure cannot
#: keep naming a superseded floor after ``configs/regimes.yaml`` moves.
POST_HOC_DISCLOSURE = (
    f"This power analysis was produced AFTER the frozen "
    f"{FROZEN_FIRST_PASS_FLOOR_MONTHS}-month and {FROZEN_SECOND_PASS_FLOOR_MONTHS}-month "
    "eligibility floors were observed to bind. No threshold, config, contract, or "
    "registry entry has been changed by it. Acting on this evidence would be a "
    "post-hoc design change and would require its own justification and its own "
    "disclosure."
)


@dataclass(frozen=True, slots=True)
class PowerDgp:
    """Data-generating process calibrated to the estimated system.

    Returns are generated as ``R_t = a + B f_t + e_t`` with
    ``a = B (lambda - mean(f))``, so the population mean excess return is exactly
    ``B lambda`` and ``lambda`` is the true risk-price vector the second pass is
    trying to recover.
    """

    assets: tuple[str, ...]
    factors: tuple[str, ...]
    betas: pd.DataFrame
    intercepts: pd.Series
    factor_means: pd.Series
    factor_covariance: pd.DataFrame
    residual_covariance: pd.DataFrame
    true_risk_prices: pd.Series
    calibration_months: int
    hac_lags: int


@dataclass(frozen=True, slots=True)
class WindowDraws:
    """Per-replication estimates for one window length.

    Every array carries a leading replication axis of length
    ``replications_used``. ``*_feasible_*`` arrays are all-``nan`` when the
    window has no more months than the system has test assets, so that the
    simulated sample residual covariance would be rank deficient. This sweep
    declines to report a feasible interval there; it is not a case the estimator
    refuses.
    """

    window_months: int
    replications_requested: int
    replications_used: int
    factor_order: tuple[str, ...]
    families: tuple[str, ...]
    joint_risk_prices: FloatArray
    joint_oracle_standard_errors: FloatArray
    joint_feasible_standard_errors: FloatArray
    joint_feasible_full_rank: bool
    joint_spreads: FloatArray
    family_risk_prices: FloatArray
    family_oracle_standard_errors: FloatArray
    family_feasible_standard_errors: FloatArray
    family_feasible_full_rank: bool
    family_spreads: FloatArray


def portfolio_column(family: str, decile: str) -> str:
    """Build the panel column name for one decile of one anomaly family.

    Args:
        family: Registered anomaly family identifier.
        decile: Decile label such as ``decile_01``.

    Returns:
        The excess-return column name used by the regime panel.
    """
    return f"portfolio_excess_return__{family}__{decile}"


def load_regime_panel(path: Path = PANEL_PARQUET) -> pd.DataFrame:
    """Load the monthly regime panel with a month-start DatetimeIndex.

    ``estimate_time_series_betas`` requires a DatetimeIndex and the panel stores
    months as ``YYYY-MM`` strings, so the string column is converted explicitly
    rather than parsed loosely.

    Args:
        path: Location of the regime panel parquet file.

    Returns:
        The panel indexed by month start, with the ``month`` column removed.

    Raises:
        ValueError: If the panel has a duplicated month or a missing value.
    """
    panel = pd.read_parquet(path)
    periods = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    )
    indexed = panel.drop(columns=["month"]).set_axis(periods.to_timestamp())
    if indexed.index.has_duplicates:
        raise ValueError("The regime panel contains duplicate months")
    if indexed.select_dtypes(include=[np.number]).isna().to_numpy().any():
        raise ValueError("The regime panel must be complete before calibration")
    return indexed


def calibrate_power_dgp(
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    *,
    hac_lags: int | None = None,
    portfolio_set: str = JOINT_SYSTEM,
    model: str = MODEL,
) -> PowerDgp:
    """Calibrate the simulation's data-generating process to an estimated system.

    The first pass is the project estimator :func:`estimate_time_series_betas`;
    the residual covariance is built by
    :func:`residual_covariance_from_first_pass`; the true risk prices are the ones
    the design's own no-intercept second pass produces on the supplied sample. The
    intercepts are then chosen so the population mean excess return equals
    ``B lambda`` exactly. With the residuals set to zero the whole construction is
    an identity, which is what the accompanying test checks.

    Args:
        excess_returns: Months by test assets excess-return panel.
        factors: Months by priced factors panel, aligned to the returns.
        hac_lags: First-pass Newey-West lag length; the project's automatic rule
            is used when omitted. It affects no simulated quantity.
        portfolio_set: Identifier recorded on the calibration second pass.
        model: Identifier recorded on the calibration second pass.

    Returns:
        The calibrated data-generating process.

    Raises:
        ValueError: If the panels are misaligned or too short to calibrate.
    """
    if not excess_returns.index.equals(factors.index):
        raise ValueError("Calibration returns and factors must share an index")
    if len(excess_returns) <= excess_returns.shape[1]:
        raise ValueError("Calibration needs more months than test assets")
    months = len(excess_returns)
    lags = automatic_newey_west_lags(months) if hac_lags is None else hac_lags

    first_pass = estimate_time_series_betas(excess_returns, factors, hac_lags=lags)
    asset_order = [str(asset) for asset in excess_returns.columns]
    factor_order = [str(name) for name in factors.columns]
    betas = first_pass.coefficients.loc[asset_order, factor_order]
    residual_covariance = residual_covariance_from_first_pass(first_pass.residuals).loc[
        asset_order, asset_order
    ]
    factor_covariance = factors.cov()
    factor_means = factors.mean()

    second_pass = estimate_article_second_pass(
        mean_excess_returns=excess_returns.mean(),
        betas=betas,
        residual_covariance=residual_covariance,
        factor_covariance=factor_covariance,
        n_months=months,
        portfolio_set=portfolio_set,
        model=model,
    )
    true_risk_prices = second_pass.risk_prices
    intercepts = pd.Series(
        betas.to_numpy(dtype=float)
        @ (true_risk_prices.to_numpy(dtype=float) - factor_means.to_numpy(dtype=float)),
        index=betas.index,
        name="intercept",
    )
    return PowerDgp(
        assets=tuple(asset_order),
        factors=tuple(factor_order),
        betas=betas,
        intercepts=intercepts,
        factor_means=factor_means,
        factor_covariance=factor_covariance,
        residual_covariance=residual_covariance,
        true_risk_prices=true_risk_prices,
        calibration_months=months,
        hac_lags=lags,
    )


def cross_sectional_residual_dispersion(residual_covariance: FloatArray) -> float:
    """Return ``tr(M_N Sigma_eps) / (N - 1)`` for a first-pass residual covariance.

    ``M_N = I_N - 11'/N`` is the cross-sectional centring projector, so this is
    the expected cross-sectional variance of a mean-zero disturbance vector whose
    covariance is ``Sigma_eps``. Expanding the trace gives the form that makes the
    correlation correction legible::

        tr(M_N Sigma_eps) / (N - 1)
            = sum_i sigma_ii / N - sum_{i != j} sigma_ij / (N (N - 1))
            = mean(diagonal) - mean(off-diagonal)

    A cross-section whose residuals are on average positively correlated
    therefore disperses *less* than its individual variances suggest, because the
    common component shifts the whole cross-section together and ``M_N`` removes
    exactly that shift.

    Args:
        residual_covariance: Symmetric ``N`` by ``N`` first-pass residual
            covariance matrix.

    Returns:
        The expected cross-sectional variance, with the ``ddof=1`` convention.

    Raises:
        ValueError: If the matrix is not square or has fewer than two assets.
    """
    if (
        residual_covariance.ndim != 2
        or residual_covariance.shape[0] != residual_covariance.shape[1]
    ):
        raise ValueError("The residual covariance must be a square matrix")
    n_assets = residual_covariance.shape[0]
    if n_assets < 2:
        raise ValueError("A cross-sectional dispersion needs at least two assets")
    mean_diagonal = float(np.mean(np.diag(residual_covariance)))
    off_diagonal_total = float(residual_covariance.sum() - np.trace(residual_covariance))
    mean_off_diagonal = off_diagonal_total / (n_assets * (n_assets - 1))
    return mean_diagonal - mean_off_diagonal


def first_pass_beta_reliability(dgp: PowerDgp, *, window_months: int | None = None) -> pd.DataFrame:
    """Decompose the observed cross-sectional beta dispersion into signal and noise.

    **Derivation.** The first pass regresses asset ``i`` on a constant and the
    factors, ``r_it = a_i + beta_i' f_t + e_it``, so its slope error is

    .. code-block:: text

        beta_hat_i - beta_i = Sigma_f^-1 (1/T) sum_t (f_t - fbar) e_it

    Conditioning on the factors, the errors of two assets covary through their
    contemporaneous residual covariance ``sigma_ij = Cov(e_it, e_jt)``:

    .. code-block:: text

        Cov(beta_hat_i - beta_i, beta_hat_j - beta_j) = sigma_ij Sigma_f^-1 / T

    Fix factor ``k`` and collect the ``N`` loading errors into the vector ``u``
    with ``u_i = (beta_hat_i - beta_i)_k``. Taking the ``(k, k)`` element of the
    display above gives the *full* error covariance of that vector,

    .. code-block:: text

        Cov(u) = [Sigma_f^-1]_kk / T * Sigma_eps

    which is emphatically not diagonal. The quantity of interest is how much
    ``u`` contributes to the **cross-sectional** variance of the estimated
    loadings. With the ``ddof=1`` convention that variance is the quadratic form
    ``u' M_N u / (N - 1)`` in the centring projector ``M_N = I_N - 11'/N``, and
    because ``E[u] = 0``,

    .. code-block:: text

        E[u' M_N u / (N - 1)] = tr(M_N Cov(u)) / (N - 1)
                              = [Sigma_f^-1]_kk / (T (N - 1)) * tr(M_N Sigma_eps)

    That is the ``noise_cross_sectional_variance`` reported here, evaluated by
    :func:`cross_sectional_residual_dispersion`.

    The one approximation in that chain is substituting the population factor
    covariance for the drawn one, which leaves an ``O(1/T)`` discrepancy of order
    ``T / (T - K - 2)``. It is under one percent at the calibration length and is
    the residual gap the accompanying Monte Carlo test tolerates; it is far
    smaller than the correction made here.

    **Why the diagonal-only version overstates the share.** Replacing
    ``tr(M_N Sigma_eps) / (N - 1)`` with the average individual residual variance
    ``mean_i sigma_ii`` drops every off-diagonal term. Since

    .. code-block:: text

        tr(M_N Sigma_eps) / (N - 1) = mean_i sigma_ii - mean_{i != j} sigma_ij

    the two agree only when residuals are cross-sectionally uncorrelated on
    average. Whenever the average off-diagonal residual covariance is positive --
    as it is for these seventy anomaly portfolios, which share a large common
    component -- estimation error moves many loadings in the same direction. A
    common shift changes the cross-sectional *mean* of the estimated loadings,
    not their *spread*, and ``M_N`` annihilates it. The diagonal-only figure
    therefore attributes to dispersion an error that never reached dispersion,
    and overstates the noise share.

    **Reporting.** The headline is the ``reliability_ratio``, signal over
    observed, in the sense of classical test theory: the fraction of the observed
    cross-sectional variance of the estimated loadings that is genuine exposure
    dispersion. ``noise_share_of_cross_sectional_variance`` is its complement and
    is reported alongside so neither can be mistaken for the other. Both are
    unclipped: at short windows the noise term can exceed the observed variance,
    which drives the reliability ratio below zero and is itself the finding.

    ``mean_individual_beta_sampling_variance`` is retained because it is
    independently informative -- it is the precision of a *single* portfolio's
    loading, which is what a reader asking "how well is one beta estimated"
    wants -- but it is a variance in squared-loading units, not a share of any
    dispersion, and is named so it cannot be read as one.

    Args:
        dgp: Calibrated data-generating process.
        window_months: Window length to evaluate; the calibration length is used
            when omitted.

    Returns:
        One row per factor, indexed in factor order, with the observed, noise,
        and signal cross-sectional variances, the reliability ratio, its
        complementary noise share, and the mean individual sampling variance.

    Raises:
        ValueError: If the window length is not positive.
    """
    months = dgp.calibration_months if window_months is None else window_months
    if months <= 0:
        raise ValueError("window_months must be positive")

    residual_covariance = dgp.residual_covariance.to_numpy(dtype=float)
    inverse_factor_covariance = np.diag(np.linalg.pinv(dgp.factor_covariance.to_numpy(dtype=float)))
    dispersion = cross_sectional_residual_dispersion(residual_covariance)
    mean_residual_variance = float(np.mean(np.diag(residual_covariance)))

    noise_variances = inverse_factor_covariance * dispersion / months
    individual_variances = inverse_factor_covariance * mean_residual_variance / months
    observed_variances = dgp.betas.var(ddof=1).to_numpy(dtype=float)
    return pd.DataFrame(
        {
            "observed_cross_sectional_variance": observed_variances,
            "signal_cross_sectional_variance": observed_variances - noise_variances,
            "noise_cross_sectional_variance": noise_variances,
            "reliability_ratio": 1.0 - noise_variances / observed_variances,
            "noise_share_of_cross_sectional_variance": noise_variances / observed_variances,
            "mean_individual_beta_sampling_variance": individual_variances,
        },
        index=pd.Index(list(dgp.factors), name="factor"),
    )


def covariance_factor(covariance: FloatArray) -> FloatArray:
    """Return a square-root factor of a symmetric positive-semidefinite matrix.

    Args:
        covariance: Symmetric covariance matrix.

    Returns:
        A matrix ``L`` with ``L L' = covariance``, up to the clipping applied to
        any numerically negative eigenvalue.

    Raises:
        ValueError: If the input is not a square matrix.
    """
    if covariance.ndim != 2 or covariance.shape[0] != covariance.shape[1]:
        raise ValueError("Covariance must be a square matrix")
    symmetric = 0.5 * (covariance + covariance.T)
    try:
        chol: FloatArray = np.linalg.cholesky(symmetric)
    except np.linalg.LinAlgError:
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        chol = eigenvectors @ np.diag(np.sqrt(np.clip(eigenvalues, 0.0, None)))
    return chol


def simulate_panel(
    dgp: PowerDgp,
    *,
    window_months: int,
    rng: np.random.Generator,
    factor_factor: FloatArray,
    residual_factor: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    """Draw one simulated estimation window from the calibrated system.

    Args:
        dgp: Calibrated data-generating process.
        window_months: Number of months in the simulated window.
        rng: Random generator.
        factor_factor: Square-root factor of the factor covariance.
        residual_factor: Square-root factor of the residual covariance.

    Returns:
        The simulated factor matrix and the simulated excess-return matrix.

    Raises:
        ValueError: If the window cannot support a first-pass regression.
    """
    n_factors = len(dgp.factors)
    if window_months <= n_factors + 1:
        raise ValueError("The window must exceed the number of first-pass parameters")
    n_assets = len(dgp.assets)
    factors: FloatArray = (
        dgp.factor_means.to_numpy(dtype=float)
        + rng.standard_normal((window_months, n_factors)) @ factor_factor.T
    )
    disturbances = rng.standard_normal((window_months, n_assets)) @ residual_factor.T
    returns: FloatArray = (
        dgp.intercepts.to_numpy(dtype=float)
        + factors @ dgp.betas.to_numpy(dtype=float).T
        + disturbances
    )
    return factors, returns


def available_families(assets: Sequence[str]) -> tuple[str, ...]:
    """Return the registered families whose full decile set is present.

    Args:
        assets: Test-asset column names of the system.

    Returns:
        The registered families, in frozen registry order, that are complete.
    """
    present = set(assets)
    return tuple(
        family
        for family in FAMILIES
        if all(portfolio_column(family, decile) in present for decile in DECILE_LABELS)
    )


def true_fitted_premium_spreads(dgp: PowerDgp) -> pd.Series:
    """Compute the population rate-attributable fitted-premium spread per family.

    The estimand is ``pi(decile_10) - pi(decile_01)`` with
    ``pi_i = beta_i_rate * lambda_rate``, the object the article tabulates as
    ``DIF`` in Table 5 and the one the bootstrap contract already bounds.

    Args:
        dgp: Calibrated data-generating process.

    Returns:
        The true spread per family, in monthly percentage points.
    """
    rate_betas = dgp.betas[RATE_FACTOR]
    lambda_rate = float(dgp.true_risk_prices[RATE_FACTOR])
    return pd.Series(
        {
            family: (
                float(rate_betas[portfolio_column(family, HIGH_DECILE)])
                - float(rate_betas[portfolio_column(family, LOW_DECILE)])
            )
            * lambda_rate
            for family in available_families(dgp.assets)
        },
        dtype=float,
        name="true_fitted_premium_spread",
    )


def simulate_window(
    dgp: PowerDgp,
    *,
    window_months: int,
    replications: int,
    seed: int,
) -> WindowDraws:
    """Run the replication loop for one window length.

    Each replication draws a window from the calibrated system, refits the first
    pass by plain least squares, then refits the design's own no-intercept second
    pass on the joint system and on each complete ten-decile family system. The
    feasible Shanken covariance is computed only where the simulated sample
    residual covariance is of full rank, which requires more months than test
    assets. The estimator itself accepts a rank-deficient covariance; declining
    to report one is this sweep's choice.

    Args:
        dgp: Calibrated data-generating process.
        window_months: Number of months in each simulated window.
        replications: Number of replications requested.
        seed: Seed for this window's generator stream.

    Returns:
        The per-replication draws for this window length.

    Raises:
        ValueError: If ``replications`` is not positive or no family is complete.
    """
    if replications < 1:
        raise ValueError("replications must be positive")

    rng = np.random.default_rng(seed)
    factor_factor = covariance_factor(dgp.factor_covariance.to_numpy(dtype=float))
    residual_factor = covariance_factor(dgp.residual_covariance.to_numpy(dtype=float))

    assets = list(dgp.assets)
    factor_order = list(dgp.factors)
    n_assets = len(assets)
    n_factors = len(factor_order)
    rate_position = factor_order.index(RATE_FACTOR)
    families = available_families(assets)
    if not families:
        raise ValueError("No registered family has a complete decile set in this system")
    n_families = len(families)

    family_columns = {
        family: [portfolio_column(family, decile) for decile in DECILE_LABELS]
        for family in families
    }
    family_rows = {
        family: [assets.index(column) for column in columns]
        for family, columns in family_columns.items()
    }
    family_oracle_covariances = {
        family: dgp.residual_covariance.iloc[rows, rows] for family, rows in family_rows.items()
    }
    family_asset_count = len(DECILE_LABELS)

    joint_feasible_full_rank = window_months > n_assets
    family_feasible_full_rank = window_months > family_asset_count

    joint_prices = np.full((replications, n_factors), np.nan)
    joint_oracle = np.full((replications, n_factors), np.nan)
    joint_feasible = np.full((replications, n_factors), np.nan)
    joint_spreads = np.full((replications, n_families), np.nan)
    family_prices = np.full((replications, n_families, n_factors), np.nan)
    family_oracle = np.full((replications, n_families, n_factors), np.nan)
    family_feasible = np.full((replications, n_families, n_factors), np.nan)
    family_spreads = np.full((replications, n_families), np.nan)

    month_labels = list(range(window_months))
    used = 0
    for _ in range(replications):
        factors, returns = simulate_panel(
            dgp,
            window_months=window_months,
            rng=rng,
            factor_factor=factor_factor,
            residual_factor=residual_factor,
        )
        design = np.column_stack([np.ones(window_months), factors])
        coefficients = np.linalg.lstsq(design, returns, rcond=None)[0]
        estimated_betas = coefficients[1:, :].T
        residuals = returns - design @ coefficients

        beta_frame = pd.DataFrame(estimated_betas, index=assets, columns=factor_order)
        mean_frame = pd.Series(returns.mean(axis=0), index=assets, dtype=float)
        residual_frame = pd.DataFrame(residuals, index=month_labels, columns=assets)
        sample_factor_covariance = pd.DataFrame(
            np.cov(factors, rowvar=False), index=factor_order, columns=factor_order
        )

        try:
            joint_oracle_result = estimate_article_second_pass(
                mean_excess_returns=mean_frame,
                betas=beta_frame,
                residual_covariance=dgp.residual_covariance,
                factor_covariance=dgp.factor_covariance,
                n_months=window_months,
                portfolio_set=JOINT_SYSTEM,
                model=MODEL,
            )
            joint_feasible_errors: FloatArray | None = None
            if joint_feasible_full_rank:
                joint_feasible_errors = (
                    estimate_article_second_pass(
                        mean_excess_returns=mean_frame,
                        betas=beta_frame,
                        residual_covariance=residual_covariance_from_first_pass(residual_frame),
                        factor_covariance=sample_factor_covariance,
                        n_months=window_months,
                        portfolio_set=JOINT_SYSTEM,
                        model=MODEL,
                    )
                    .shanken_standard_errors.to_numpy(dtype=float)
                    .copy()
                )

            family_prices_draw = np.empty((n_families, n_factors))
            family_oracle_draw = np.empty((n_families, n_factors))
            family_feasible_draw = np.full((n_families, n_factors), np.nan)
            for family_index, family in enumerate(families):
                columns = family_columns[family]
                sub_mean = mean_frame.loc[columns]
                sub_betas = beta_frame.loc[columns]
                sub_oracle = estimate_article_second_pass(
                    mean_excess_returns=sub_mean,
                    betas=sub_betas,
                    residual_covariance=family_oracle_covariances[family],
                    factor_covariance=dgp.factor_covariance,
                    n_months=window_months,
                    portfolio_set=f"{FAMILY_SYSTEM}__{family}",
                    model=MODEL,
                )
                family_prices_draw[family_index, :] = sub_oracle.risk_prices.to_numpy(dtype=float)
                family_oracle_draw[family_index, :] = sub_oracle.shanken_standard_errors.to_numpy(
                    dtype=float
                )
                if family_feasible_full_rank:
                    sub_feasible = estimate_article_second_pass(
                        mean_excess_returns=sub_mean,
                        betas=sub_betas,
                        residual_covariance=residual_covariance_from_first_pass(
                            residual_frame.loc[:, columns]
                        ),
                        factor_covariance=sample_factor_covariance,
                        n_months=window_months,
                        portfolio_set=f"{FAMILY_SYSTEM}__{family}",
                        model=MODEL,
                    )
                    family_feasible_draw[family_index, :] = (
                        sub_feasible.shanken_standard_errors.to_numpy(dtype=float)
                    )
        except (ValueError, np.linalg.LinAlgError):
            continue

        joint_prices[used, :] = joint_oracle_result.risk_prices.to_numpy(dtype=float)
        joint_oracle[used, :] = joint_oracle_result.shanken_standard_errors.to_numpy(dtype=float)
        if joint_feasible_errors is not None:
            joint_feasible[used, :] = joint_feasible_errors
        family_prices[used, :, :] = family_prices_draw
        family_oracle[used, :, :] = family_oracle_draw
        family_feasible[used, :, :] = family_feasible_draw

        joint_rate_price = float(joint_prices[used, rate_position])
        for family_index, family in enumerate(families):
            low, high = family_rows[family][0], family_rows[family][-1]
            beta_difference = float(
                estimated_betas[high, rate_position] - estimated_betas[low, rate_position]
            )
            joint_spreads[used, family_index] = beta_difference * joint_rate_price
            family_spreads[used, family_index] = beta_difference * float(
                family_prices_draw[family_index, rate_position]
            )
        used += 1

    return WindowDraws(
        window_months=window_months,
        replications_requested=replications,
        replications_used=used,
        factor_order=tuple(factor_order),
        families=families,
        joint_risk_prices=joint_prices[:used],
        joint_oracle_standard_errors=joint_oracle[:used],
        joint_feasible_standard_errors=joint_feasible[:used],
        joint_feasible_full_rank=joint_feasible_full_rank,
        joint_spreads=joint_spreads[:used],
        family_risk_prices=family_prices[:used],
        family_oracle_standard_errors=family_oracle[:used],
        family_feasible_standard_errors=family_feasible[:used],
        family_feasible_full_rank=family_feasible_full_rank,
        family_spreads=family_spreads[:used],
    )


def summarise_estimates(
    draws: FloatArray,
    *,
    true_value: float,
    oracle_standard_errors: FloatArray | None = None,
    feasible_standard_errors: FloatArray | None = None,
) -> dict[str, float | None]:
    """Summarise one estimand's replication draws.

    Args:
        draws: One estimate per replication.
        true_value: The population value the data-generating process imposes.
        oracle_standard_errors: Shanken standard errors computed with the
            population residual covariance, or ``None`` when not applicable.
        feasible_standard_errors: Shanken standard errors computed with the
            simulated sample residual covariance, or ``None`` at window lengths
            where that covariance would be rank deficient and this sweep declines
            to report it.

    Returns:
        A mapping of summary statistic names to values, with ``None`` wherever a
        statistic is not available for this estimand and window.

    Raises:
        ValueError: If fewer than two replications are supplied.
    """
    if draws.size < 2:
        raise ValueError("At least two replications are needed to summarise a window")
    count = int(draws.size)
    mean_estimate = float(np.mean(draws))
    standard_deviation = float(np.std(draws, ddof=1))
    sign_error = float(np.mean(np.sign(draws) != np.sign(true_value)))
    summary: dict[str, float | None] = {
        "true_value": float(true_value),
        "mean_estimate": mean_estimate,
        "bias": mean_estimate - float(true_value),
        "attenuation_ratio": mean_estimate / float(true_value),
        "standard_deviation": standard_deviation,
        "standard_deviation_mcse": standard_deviation / float(np.sqrt(2.0 * (count - 1))),
        "standard_deviation_relative_to_true_value": standard_deviation / abs(float(true_value)),
        "root_mean_squared_error": float(np.sqrt(np.mean(np.square(draws - true_value)))),
        "sign_error_probability": sign_error,
        "sign_error_probability_mcse": float(np.sqrt(sign_error * (1.0 - sign_error) / count)),
    }
    for label, errors in (
        ("oracle", oracle_standard_errors),
        ("feasible", feasible_standard_errors),
    ):
        if errors is None or errors.size == 0 or not np.all(np.isfinite(errors)):
            summary[f"{label}_mean_shanken_standard_error"] = None
            summary[f"{label}_coverage_95"] = None
            summary[f"{label}_coverage_95_mcse"] = None
            summary[f"{label}_detection_probability"] = None
            continue
        half_width = NORMAL_95_QUANTILE * errors
        covered = float(
            np.mean((draws - half_width <= true_value) & (true_value <= draws + half_width))
        )
        detected = float(
            np.mean((np.abs(draws) >= half_width) & (np.sign(draws) == np.sign(true_value)))
        )
        summary[f"{label}_mean_shanken_standard_error"] = float(np.mean(errors))
        summary[f"{label}_coverage_95"] = covered
        summary[f"{label}_coverage_95_mcse"] = float(np.sqrt(covered * (1.0 - covered) / count))
        summary[f"{label}_detection_probability"] = detected
    return summary


def _below_economic_bound(summary: Mapping[str, float | None]) -> bool:
    """Report whether a summarised dispersion sits inside the economic bound.

    Args:
        summary: One estimand's summary, as returned by :func:`summarise_estimates`.

    Returns:
        ``True`` when the sampling standard deviation is strictly below the
        threshold contract's fitted-premium bound.
    """
    dispersion = summary["standard_deviation"]
    return dispersion is not None and float(dispersion) < ECONOMIC_BOUND


def build_curve_rows(
    draws: WindowDraws,
    *,
    dgp: PowerDgp,
    true_spreads: pd.Series,
) -> list[dict[str, Any]]:
    """Turn one window's replication draws into long-form curve rows.

    Args:
        draws: The window's replication draws.
        dgp: Calibrated data-generating process, for the true risk prices.
        true_spreads: True fitted-premium spread per family.

    Returns:
        One row per system, cross-section, and estimand for this window length.
    """
    rows: list[dict[str, Any]] = []
    factor_order = list(draws.factor_order)
    common = {
        "window_months": draws.window_months,
        "replications_requested": draws.replications_requested,
        "replications_used": draws.replications_used,
    }

    for estimand, factor_name in (("lambda_rate", RATE_FACTOR), ("lambda_market", MARKET_FACTOR)):
        position = factor_order.index(factor_name)
        rows.append(
            {
                **common,
                "system": JOINT_SYSTEM,
                "cross_section": JOINT_SYSTEM,
                "n_test_assets": len(dgp.assets),
                "estimand": estimand,
                "economic_bound": None,
                "standard_deviation_below_economic_bound": None,
                "feasible_shanken_full_rank": draws.joint_feasible_full_rank,
                **summarise_estimates(
                    draws.joint_risk_prices[:, position],
                    true_value=float(dgp.true_risk_prices[factor_name]),
                    oracle_standard_errors=draws.joint_oracle_standard_errors[:, position],
                    feasible_standard_errors=(
                        draws.joint_feasible_standard_errors[:, position]
                        if draws.joint_feasible_full_rank
                        else None
                    ),
                ),
            }
        )

    rate_position = factor_order.index(RATE_FACTOR)
    for family_index, family in enumerate(draws.families):
        true_spread = float(true_spreads[family])
        spread_summary = summarise_estimates(
            draws.joint_spreads[:, family_index], true_value=true_spread
        )
        rows.append(
            {
                **common,
                "system": JOINT_SYSTEM,
                "cross_section": family,
                "n_test_assets": len(dgp.assets),
                "estimand": "fitted_premium_spread",
                "economic_bound": ECONOMIC_BOUND,
                "standard_deviation_below_economic_bound": _below_economic_bound(spread_summary),
                "feasible_shanken_full_rank": None,
                **spread_summary,
            }
        )

        rows.append(
            {
                **common,
                "system": FAMILY_SYSTEM,
                "cross_section": family,
                "n_test_assets": len(DECILE_LABELS),
                "estimand": "lambda_rate",
                "economic_bound": None,
                "standard_deviation_below_economic_bound": None,
                "feasible_shanken_full_rank": draws.family_feasible_full_rank,
                **summarise_estimates(
                    draws.family_risk_prices[:, family_index, rate_position],
                    true_value=float(dgp.true_risk_prices[RATE_FACTOR]),
                    oracle_standard_errors=draws.family_oracle_standard_errors[
                        :, family_index, rate_position
                    ],
                    feasible_standard_errors=(
                        draws.family_feasible_standard_errors[:, family_index, rate_position]
                        if draws.family_feasible_full_rank
                        else None
                    ),
                ),
            }
        )

        family_spread_summary = summarise_estimates(
            draws.family_spreads[:, family_index], true_value=true_spread
        )
        rows.append(
            {
                **common,
                "system": FAMILY_SYSTEM,
                "cross_section": family,
                "n_test_assets": len(DECILE_LABELS),
                "estimand": "fitted_premium_spread",
                "economic_bound": ECONOMIC_BOUND,
                "standard_deviation_below_economic_bound": _below_economic_bound(
                    family_spread_summary
                ),
                "feasible_shanken_full_rank": None,
                **family_spread_summary,
            }
        )
    return rows


def first_window_meeting(
    values: Mapping[int, float | None],
    predicate: Callable[[float], bool],
    windows: Sequence[int],
) -> int | None:
    """Find the shortest window from which a reading criterion holds and stays held.

    A single lucky crossing is not a crossing: the criterion must hold at the
    returned window and at every longer window on the grid.

    Args:
        values: Statistic by window length.
        predicate: Test applied to a finite statistic.
        windows: Window grid in ascending order.

    Returns:
        The shortest qualifying window, or ``None`` if no window qualifies.
    """

    def holds(window: int) -> bool:
        value = values.get(window)
        return value is not None and bool(np.isfinite(value)) and predicate(float(value))

    return next(
        (
            window
            for index, window in enumerate(windows)
            if all(holds(later) for later in windows[index:])
        ),
        None,
    )


def _at_least(bound: float) -> Callable[[float], bool]:
    """Build a predicate that tests whether a statistic reaches a level.

    Args:
        bound: The level the statistic must reach.

    Returns:
        A predicate suitable for :func:`first_window_meeting`.
    """

    def predicate(value: float) -> bool:
        return value >= bound

    return predicate


def reading_criteria(curve: pd.DataFrame, windows: Sequence[int]) -> dict[str, Any]:
    """Report where each reading criterion first holds, per system and family.

    The criteria are reporting conventions for summarising a curve. They are not
    registered thresholds and are not proposed as replacements for any frozen
    value.

    Args:
        curve: The long-form power curve.
        windows: Window grid in ascending order.

    Returns:
        A nested mapping of criterion name to crossing windows.
    """

    def series(
        system: str, cross_section: str, estimand: str, column: str
    ) -> dict[int, float | None]:
        subset = curve[
            (curve["system"] == system)
            & (curve["cross_section"] == cross_section)
            & (curve["estimand"] == estimand)
        ]
        return {
            int(str(window)): (None if pd.isna(value) else float(value))
            for window, value in zip(subset["window_months"], subset[column], strict=True)
        }

    families = sorted(set(curve.loc[curve["estimand"] == "fitted_premium_spread", "cross_section"]))

    spread_crossings = {
        system: {
            family: first_window_meeting(
                series(system, family, "fitted_premium_spread", "standard_deviation"),
                lambda value: value < ECONOMIC_BOUND,
                windows,
            )
            for family in families
        }
        for system in (JOINT_SYSTEM, FAMILY_SYSTEM)
    }
    spread_error_crossings = {
        system: {
            family: first_window_meeting(
                series(system, family, "fitted_premium_spread", "root_mean_squared_error"),
                lambda value: value < ECONOMIC_BOUND,
                windows,
            )
            for family in families
        }
        for system in (JOINT_SYSTEM, FAMILY_SYSTEM)
    }

    def slowest(crossings: Mapping[str, int | None]) -> int | None:
        values = list(crossings.values())
        if any(value is None for value in values):
            return None
        return max(int(value) for value in values if value is not None)

    all_family_spread = {
        system: slowest(crossings) for system, crossings in spread_crossings.items()
    }
    all_family_spread_error = {
        system: slowest(crossings) for system, crossings in spread_error_crossings.items()
    }

    sign_error = {
        JOINT_SYSTEM: first_window_meeting(
            series(JOINT_SYSTEM, JOINT_SYSTEM, "lambda_rate", "sign_error_probability"),
            lambda value: value <= SIGN_ERROR_READING_LEVEL,
            windows,
        ),
        FAMILY_SYSTEM: {
            family: first_window_meeting(
                series(FAMILY_SYSTEM, family, "lambda_rate", "sign_error_probability"),
                lambda value: value <= SIGN_ERROR_READING_LEVEL,
                windows,
            )
            for family in families
        },
    }

    attenuation = series(JOINT_SYSTEM, JOINT_SYSTEM, "lambda_rate", "attenuation_ratio")

    def coverage_ok(value: float) -> bool:
        return COVERAGE_READING_LOW <= value <= COVERAGE_READING_HIGH

    coverage = {
        f"{JOINT_SYSTEM}__oracle": first_window_meeting(
            series(JOINT_SYSTEM, JOINT_SYSTEM, "lambda_rate", "oracle_coverage_95"),
            coverage_ok,
            windows,
        ),
        f"{JOINT_SYSTEM}__feasible": first_window_meeting(
            series(JOINT_SYSTEM, JOINT_SYSTEM, "lambda_rate", "feasible_coverage_95"),
            coverage_ok,
            windows,
        ),
        FAMILY_SYSTEM: {
            family: first_window_meeting(
                series(FAMILY_SYSTEM, family, "lambda_rate", "feasible_coverage_95"),
                coverage_ok,
                windows,
            )
            for family in families
        },
    }

    full_rank_windows = curve.loc[
        (curve["system"] == JOINT_SYSTEM)
        & (curve["estimand"] == "lambda_rate")
        & (curve["feasible_shanken_full_rank"]),
        "window_months",
    ]
    return {
        "status": "reporting_conventions_not_registered_thresholds",
        "fitted_premium_spread_sd_below_economic_bound": {
            "description": (
                "Sampling standard deviation of pi(decile_10) - pi(decile_01) falls "
                f"below the {ECONOMIC_BOUND} monthly percentage-point bound in "
                "research/economic_thresholds.md and stays below it."
            ),
            "per_family": spread_crossings,
            "all_families": all_family_spread,
        },
        "fitted_premium_spread_rmse_below_economic_bound": {
            "description": (
                "Root mean squared error of pi(decile_10) - pi(decile_01) about its true "
                f"value falls below the {ECONOMIC_BOUND} monthly percentage-point bound "
                "and stays below it. Unlike the standard-deviation reading this one "
                "counts the attenuation bias, so a window cannot satisfy it merely by "
                "shrinking the estimate toward zero."
            ),
            "per_family": spread_error_crossings,
            "all_families": all_family_spread_error,
        },
        "sign_error_probability_at_or_below_level": {
            "description": (
                "Probability that the estimated lambda_rate has the wrong sign is at "
                f"or below {SIGN_ERROR_READING_LEVEL} and stays there."
            ),
            "crossings": sign_error,
        },
        "shanken_coverage_within_band": {
            "description": (
                "Coverage of the nominal 95 percent Shanken interval for lambda_rate "
                f"lies in [{COVERAGE_READING_LOW}, {COVERAGE_READING_HIGH}] and stays there."
            ),
            "crossings": coverage,
        },
        "attenuation_ratio_at_or_above_level": {
            "description": (
                "Mean estimated lambda_rate on the joint system, divided by the true "
                "value, reaches the level and stays there. A ratio of 0.90 is the same "
                "statement as an absolute bias of at most 10 percent of the truth."
            ),
            "crossings": {
                f"{level:.2f}": first_window_meeting(attenuation, _at_least(level), windows)
                for level in ATTENUATION_READING_LEVELS
            },
        },
        "feasible_shanken_covariance_full_rank": {
            "description": (
                "The simulated sample residual covariance is of full rank, which requires "
                "more months than test assets. Below this the covariance still exists and "
                "the estimator still runs: it is rank deficient, and no step of the second "
                "pass inverts it. This sweep declines to report a feasible interval there, "
                "which is a reporting choice and not a statement that the covariance, the "
                "Shanken standard errors, or the chi-square cannot be computed."
            ),
            JOINT_SYSTEM: (None if full_rank_windows.empty else int(full_rank_windows.min())),
            "joint_exact_minimum_months": len(FAMILIES) * len(DECILE_LABELS) + 1,
            FAMILY_SYSTEM: len(DECILE_LABELS) + 1,
        },
    }


def _sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _print_headline(curve: pd.DataFrame) -> None:
    """Print the joint-system headline curve to standard output."""
    headline = curve[
        (curve["system"] == JOINT_SYSTEM) & (curve["estimand"] == "lambda_rate")
    ].copy()
    columns = [
        "window_months",
        "mean_estimate",
        "attenuation_ratio",
        "standard_deviation",
        "sign_error_probability",
        "oracle_coverage_95",
        "feasible_coverage_95",
        "oracle_detection_probability",
    ]
    print("\nJoint 70-portfolio system, lambda_rate")
    print(headline[columns].round(4).to_string(index=False))

    spread = curve[
        (curve["system"] == JOINT_SYSTEM) & (curve["estimand"] == "fitted_premium_spread")
    ]
    pivot = spread.pivot(
        index="window_months", columns="cross_section", values="standard_deviation"
    )
    print("\nJoint 70-portfolio system, sd of pi(decile_10) - pi(decile_01)")
    print(pivot.round(4).to_string())


def main() -> None:
    """Calibrate the system, sweep window lengths, and write every artifact."""
    started = time.perf_counter()
    panel = load_regime_panel()
    asset_columns = sorted(
        column for column in panel.columns if column.startswith("portfolio_excess_return__")
    )
    excess_returns = panel[asset_columns]
    factors = panel[list(FACTOR_COLUMNS)]

    dgp = calibrate_power_dgp(excess_returns, factors)
    true_spreads = true_fitted_premium_spreads(dgp)
    reliability = first_pass_beta_reliability(dgp)
    print(f"calibrated on {dgp.calibration_months} months, {len(dgp.assets)} test assets")
    print(f"true risk prices: {dgp.true_risk_prices.round(4).to_dict()}")
    print(f"true fitted-premium spreads: {true_spreads.round(4).to_dict()}")
    print("first-pass beta reliability (signal / observed cross-sectional variance):")
    print(reliability.round(6).to_string())
    print(f"replications per window: {REPLICATIONS}, seed: {SEED}")

    rows: list[dict[str, Any]] = []
    for window in WINDOW_LENGTHS:
        window_started = time.perf_counter()
        draws = simulate_window(
            dgp, window_months=window, replications=REPLICATIONS, seed=SEED + window
        )
        rows.extend(build_curve_rows(draws, dgp=dgp, true_spreads=true_spreads))
        print(
            f"  window {window:>4} months: {draws.replications_used}/{REPLICATIONS} replications "
            f"in {time.perf_counter() - window_started:.1f}s"
        )

    ordered_columns = [
        "system",
        "cross_section",
        "n_test_assets",
        "window_months",
        "estimand",
        "replications_requested",
        "replications_used",
        "true_value",
        "mean_estimate",
        "bias",
        "attenuation_ratio",
        "standard_deviation",
        "standard_deviation_mcse",
        "standard_deviation_relative_to_true_value",
        "root_mean_squared_error",
        "sign_error_probability",
        "sign_error_probability_mcse",
        "oracle_mean_shanken_standard_error",
        "oracle_coverage_95",
        "oracle_coverage_95_mcse",
        "oracle_detection_probability",
        "feasible_shanken_full_rank",
        "feasible_mean_shanken_standard_error",
        "feasible_coverage_95",
        "feasible_coverage_95_mcse",
        "feasible_detection_probability",
        "economic_bound",
        "standard_deviation_below_economic_bound",
    ]
    curve = pd.DataFrame.from_records(rows)[ordered_columns].sort_values(
        ["system", "estimand", "cross_section", "window_months"], ignore_index=True
    )
    CURVE_CSV.parent.mkdir(parents=True, exist_ok=True)
    curve.to_csv(CURVE_CSV, index=False, lineterminator="\n")

    criteria = reading_criteria(curve, WINDOW_LENGTHS)
    diagnostics = {
        "analysis": "regime_eligibility_power_analysis",
        "post_hoc_disclosure": POST_HOC_DISCLOSURE,
        "thresholds_changed": [],
        "frozen_reference_marks": {
            "minimum_months_for_regime_specific_estimation": FROZEN_FIRST_PASS_FLOOR_MONTHS,
            "minimum_months_for_standalone_second_pass": FROZEN_SECOND_PASS_FLOOR_MONTHS,
            "minimum_test_assets_for_standalone_second_pass": FROZEN_MINIMUM_TEST_ASSETS,
            "source": "configs/regimes.yaml regime_estimation_eligibility",
            "role": "reference_marks_only_not_evaluated_and_not_changed",
        },
        "design": {
            "model": MODEL,
            "rate_series": RATE,
            "factor_order": list(dgp.factors),
            "calibration_months": dgp.calibration_months,
            "calibration_first_pass": "estimate_time_series_betas",
            "calibration_hac_lags": dgp.hac_lags,
            "simulation_first_pass": "plain_least_squares_as_in_block_bootstrap",
            "second_pass": "estimate_article_second_pass",
            "residual_covariance": "residual_covariance_from_first_pass",
            "disturbances": "gaussian_iid_calibrated_to_first_pass_residual_covariance",
            "factors": "gaussian_iid_calibrated_to_sample_factor_mean_and_covariance",
            "replications": REPLICATIONS,
            "seed": SEED,
            "seed_rule": "SEED + window_months",
            "window_lengths": list(WINDOW_LENGTHS),
            "interval": "lambda_hat +/- 1.959963984540054 * shanken_standard_error",
        },
        "calibrated_truth": {
            "risk_prices": {str(key): float(value) for key, value in dgp.true_risk_prices.items()},
            "fitted_premium_spreads": {
                str(key): float(value) for key, value in true_spreads.items()
            },
            "factor_means": {str(key): float(value) for key, value in dgp.factor_means.items()},
            "rate_beta_dispersion": float(dgp.betas[RATE_FACTOR].std(ddof=1)),
            "first_pass_beta_reliability_at_calibration_length": {
                "description": (
                    "Decomposition of the observed cross-sectional variance of the "
                    "calibration first-pass loadings into genuine exposure dispersion "
                    "and first-pass estimation error, per factor. The error term is "
                    "[Sigma_f^-1]_kk / (T (N - 1)) * tr(M_N Sigma_eps) with "
                    "M_N = I - 11'/N, which uses the full residual covariance and so "
                    "credits the common component of the estimation error to the "
                    "cross-sectional mean rather than to the spread. reliability_ratio "
                    "is signal over observed; noise_share_of_cross_sectional_variance "
                    "is its complement. mean_individual_beta_sampling_variance is the "
                    "sampling variance of a single portfolio's loading, in squared "
                    "loading units, and is not a share of anything."
                ),
                "per_factor": {
                    str(factor): {str(field): float(value) for field, value in row.items()}
                    for factor, row in reliability.iterrows()
                },
            },
            "fixed_point_caveat": (
                "The calibration treats the full-sample estimated betas as true, so the "
                "process is not a fixed point of the two-pass estimator. Simulated first "
                "passes produce noisier betas than the process was built from, and the "
                "no-intercept second pass attenuates lambda_rate toward zero at every "
                "window length including the calibration length. Read bias, "
                "attenuation_ratio, and coverage as comparisons across window lengths, "
                "not as absolute statements. Because the real betas are themselves "
                "estimates, the simulated cross-section is better identified than the "
                "real one, so the reported precision is if anything optimistic."
            ),
        },
        "registered_regime_months": REGISTERED_REGIME_MONTHS,
        "reading_criteria": criteria,
        "replication_status": "documented_reconstruction",
    }
    DIAGNOSTIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_JSON.write_text(
        json.dumps(diagnostics, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/analyse_regime_power.py",
                "post_hoc_disclosure": POST_HOC_DISCLOSURE,
                "inputs": {PANEL_PARQUET.as_posix(): _sha256(PANEL_PARQUET)},
                "outputs": {
                    CURVE_CSV.as_posix(): _sha256(CURVE_CSV),
                    DIAGNOSTIC_JSON.as_posix(): _sha256(DIAGNOSTIC_JSON),
                },
                "replications": REPLICATIONS,
                "seed": SEED,
                "window_lengths": list(WINDOW_LENGTHS),
                "model": MODEL,
                "rate_series": RATE,
                "thresholds_changed": [],
                "runtime_seconds": round(time.perf_counter() - started, 1),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    _print_headline(curve)
    print(f"\n{POST_HOC_DISCLOSURE}")
    print(f"\nwrote {CURVE_CSV}, {DIAGNOSTIC_JSON}, {PROVENANCE_JSON}")


if __name__ == "__main__":
    main()
