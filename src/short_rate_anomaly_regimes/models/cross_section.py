"""Second-pass cross-sectional asset-pricing estimators."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm


@dataclass(frozen=True, slots=True)
class CrossSectionResult:
    """Risk prices, pricing errors, and fit statistics."""

    risk_prices: pd.Series
    standard_errors: pd.Series
    t_statistics: pd.Series
    pricing_errors: pd.Series
    fitted_mean_returns: pd.Series
    r_squared: float
    rmse: float
    mae: float


def estimate_ols_two_pass(
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    *,
    include_intercept: bool = True,
) -> CrossSectionResult:
    """Estimate an OLS second-pass cross-sectional regression.

    This base implementation does not yet apply Shanken or weak-factor corrections. Those are
    separate milestone deliverables and must not be implied by the returned standard errors.
    """
    joined = betas.join(mean_excess_returns.rename("mean_return"), how="inner").dropna()
    if joined.empty:
        raise ValueError("No common assets between mean returns and beta estimates")
    factor_names = list(betas.columns)
    design = joined[factor_names]
    if include_intercept:
        design = sm.add_constant(design, has_constant="add")
    fitted_model = sm.OLS(joined["mean_return"], design).fit()
    fitted = fitted_model.fittedvalues.rename("fitted_mean_return")
    errors = (joined["mean_return"] - fitted).rename("pricing_error")
    variance = float(np.square(joined["mean_return"] - joined["mean_return"].mean()).sum())
    residual_sum = float(np.square(errors).sum())
    cross_sectional_r2 = float("nan") if variance == 0.0 else 1.0 - residual_sum / variance
    return CrossSectionResult(
        risk_prices=fitted_model.params,
        standard_errors=fitted_model.bse,
        t_statistics=fitted_model.tvalues,
        pricing_errors=errors,
        fitted_mean_returns=fitted,
        r_squared=cross_sectional_r2,
        rmse=float(np.sqrt(np.mean(np.square(errors)))),
        mae=float(np.mean(np.abs(errors))),
    )


def estimate_gls_two_pass(*args: object, **kwargs: object) -> CrossSectionResult:
    """Estimate the paper's GLS second pass after its weighting matrix is verified."""
    del args, kwargs
    raise NotImplementedError("Implement in Milestone 6 using the verified GLS specification")


def estimate_fama_macbeth(*args: object, **kwargs: object) -> CrossSectionResult:
    """Estimate Fama-MacBeth risk prices with verified windows and corrections."""
    del args, kwargs
    raise NotImplementedError("Implement in Milestone 6 using the verified article procedure")
