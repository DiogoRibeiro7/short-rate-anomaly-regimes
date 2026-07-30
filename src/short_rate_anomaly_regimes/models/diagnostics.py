"""Specification, weak-factor, and influence diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f as f_distribution  # type: ignore[import-untyped]


def weak_factor_diagnostics(*, betas: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Return diagnostics for weak or irrelevant factors.

    The final implementation must include rank, dispersion, first-stage strength, and
    misspecification-robust inference appropriate to the selected two-pass estimator.
    """
    del betas, factors
    raise NotImplementedError("Implement under Milestone 8")


def grs_test(*, returns: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Compute the Gibbons-Ross-Shanken joint alpha test."""
    joined = returns.join(factors, how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations between returns and factors")
    asset_names = list(returns.columns)
    factor_names = list(factors.columns)
    excess_returns = joined[asset_names]
    factor_panel = joined[factor_names]
    nobs = int(joined.shape[0])
    n_assets = len(asset_names)
    n_factors = len(factor_names)
    if nobs <= n_assets + n_factors + 1:
        raise ValueError("Insufficient observations for GRS test")
    design = sm.add_constant(factor_panel, has_constant="add")
    alphas: list[float] = []
    residuals: list[pd.Series] = []
    for asset in asset_names:
        model = sm.OLS(excess_returns[asset], design).fit()
        alphas.append(float(model.params["const"]))
        residuals.append(model.resid.rename(asset))
    alpha = np.asarray(alphas, dtype=float)
    if np.allclose(alpha, 0.0, atol=1e-12):
        return pd.Series(
            {
                "statistic": 0.0,
                "p_value": 1.0,
                "df_num": float(n_assets),
                "df_denom": float(nobs - n_assets - n_factors),
                "nobs": float(nobs),
                "n_assets": float(n_assets),
                "n_factors": float(n_factors),
            }
        )
    residual_matrix = pd.concat(residuals, axis=1).to_numpy(dtype=float)
    residual_covariance = residual_matrix.T @ residual_matrix / float(nobs - n_factors - 1)
    factor_mean = factor_panel.mean(axis=0).to_numpy(dtype=float)
    factor_covariance = factor_panel.cov().to_numpy(dtype=float)
    denominator = 1.0 + float(factor_mean.T @ np.linalg.pinv(factor_covariance) @ factor_mean)
    statistic = (
        (nobs - n_assets - n_factors)
        / n_assets
        / denominator
        * float(alpha.T @ np.linalg.pinv(residual_covariance) @ alpha)
    )
    p_value = float(f_distribution.sf(statistic, n_assets, nobs - n_assets - n_factors))
    return pd.Series(
        {
            "statistic": float(statistic),
            "p_value": p_value,
            "df_num": float(n_assets),
            "df_denom": float(nobs - n_assets - n_factors),
            "nobs": float(nobs),
            "n_assets": float(n_assets),
            "n_factors": float(n_factors),
        }
    )
