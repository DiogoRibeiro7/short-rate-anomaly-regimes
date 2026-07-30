"""Short-rate innovation estimators."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm

from short_rate_anomaly_regimes.types import RateInnovationResult


@dataclass(frozen=True, slots=True)
class ARInnovationConfig:
    """Configuration for a univariate autoregressive innovation model."""

    lags: int = 1
    include_intercept: bool = True
    standardize: bool = False


DEFAULT_AR_INNOVATION_CONFIG = ARInnovationConfig()


def estimate_ar_innovation(
    rate: pd.Series,
    *,
    config: ARInnovationConfig = DEFAULT_AR_INNOVATION_CONFIG,
) -> RateInnovationResult:
    """Estimate innovations from a finite-order autoregression.

    The function preserves the original index and does not extrapolate missing observations.
    It is suitable for the baseline AR(1) construction once the paper's exact rate units and
    timing convention have been verified.
    """
    if not isinstance(rate.index, pd.DatetimeIndex):
        raise TypeError("Rate series must use a DatetimeIndex")
    clean = rate.astype(float).dropna().sort_index()
    if len(clean) <= config.lags + 2:
        raise ValueError("Insufficient observations for autoregressive innovation estimation")

    lagged = pd.concat(
        {f"lag_{lag}": clean.shift(lag) for lag in range(1, config.lags + 1)}, axis=1
    ).dropna()
    target = clean.loc[lagged.index]
    design = sm.add_constant(lagged, has_constant="add") if config.include_intercept else lagged
    fitted_model = sm.OLS(target, design).fit()
    innovations = fitted_model.resid.rename("rate_innovation")
    if config.standardize:
        standard_deviation = float(innovations.std(ddof=1))
        if standard_deviation == 0.0:
            raise ValueError("Cannot standardize zero-variance innovations")
        innovations = innovations / standard_deviation
    diagnostics = pd.Series(
        {
            "nobs": float(fitted_model.nobs),
            "r_squared": float(fitted_model.rsquared),
            "durbin_watson": float(sm.stats.stattools.durbin_watson(fitted_model.resid)),
        },
        dtype=float,
    )
    return RateInnovationResult(
        innovations=innovations,
        fitted_values=fitted_model.fittedvalues.rename("fitted_rate"),
        parameters=fitted_model.params,
        diagnostics=diagnostics,
    )
