"""First-pass time-series asset-pricing regressions."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import statsmodels.api as sm


@dataclass(frozen=True, slots=True)
class TimeSeriesResult:
    """First-pass coefficients and diagnostics for all test assets."""

    coefficients: pd.DataFrame
    t_statistics: pd.DataFrame
    residuals: pd.DataFrame
    r_squared: pd.Series


def estimate_time_series_betas(
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    *,
    hac_lags: int,
) -> TimeSeriesResult:
    """Estimate asset-specific factor loadings using OLS with HAC inference."""
    joined = excess_returns.join(factors, how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations between returns and factors")
    factor_names = list(factors.columns)
    design = sm.add_constant(joined[factor_names], has_constant="add")
    coefficients: dict[str, pd.Series] = {}
    t_statistics: dict[str, pd.Series] = {}
    residuals: dict[str, pd.Series] = {}
    r_squared: dict[str, float] = {}
    for asset in excess_returns.columns:
        model = sm.OLS(joined[asset], design).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
        coefficients[asset] = model.params
        t_statistics[asset] = model.tvalues
        residuals[asset] = model.resid
        r_squared[asset] = float(model.rsquared)
    return TimeSeriesResult(
        coefficients=pd.DataFrame(coefficients).T,
        t_statistics=pd.DataFrame(t_statistics).T,
        residuals=pd.DataFrame(residuals),
        r_squared=pd.Series(r_squared, name="r_squared"),
    )
