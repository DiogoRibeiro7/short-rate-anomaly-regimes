"""The article's exact second-pass estimator, fit metric, and specification test.

The repository's general cross-sectional estimators in
:mod:`short_rate_anomaly_regimes.models.cross_section` are deliberately broader
than the published design. This module implements the three objects the article
defines literally, so that a generated cell can be compared with a published one
without a definitional gap:

- the no-intercept OLS second pass of article equation (4);
- the Shanken (1992) covariance of the risk prices and of the pricing errors,
  which the article uses for every reported t-ratio and for the specification
  test;
- the joint pricing-error statistic of article equation (5) and the
  cross-sectional fit of article equation (6).

Nothing here is a reconstruction fallback. Every formula is the published one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import chi2 as chi2_distribution  # type: ignore[import-untyped]

#: Article page 933, equation (5) uses a pseudo-inverse whose numerical
#: tolerance the article does not state. This is the declared project value and
#: is recorded with every generated artifact.
PSEUDO_INVERSE_RCOND = 1e-15


@dataclass(frozen=True, slots=True)
class ArticleSecondPassResult:
    """Risk prices, pricing errors, fit, and specification test for one system."""

    portfolio_set: str
    model: str
    n_assets: int
    n_months: int
    n_factors: int
    risk_prices: pd.Series
    shanken_standard_errors: pd.Series
    shanken_t_statistics: pd.Series
    ordinary_standard_errors: pd.Series
    pricing_errors: pd.Series
    fitted_mean_returns: pd.Series
    article_cross_sectional_fit: float
    chi_square_statistic: float
    chi_square_degrees_of_freedom: int
    chi_square_asymptotic_p_value: float
    root_mean_squared_pricing_error: float
    mean_absolute_pricing_error: float
    max_absolute_pricing_error: float
    shanken_multiplier: float
    pseudo_inverse_rcond: float
    beta_matrix_rank: int
    diagnostics: dict[str, float] = field(default_factory=dict)


def article_cross_sectional_fit(
    mean_excess_returns: pd.Series,
    pricing_errors: pd.Series,
) -> float:
    """Compute the article's cross-sectional fit, equation (6) on page 933.

    The definition is ``1 - var_N(alpha_i) / var_N(mean_excess_return_i)`` where
    ``var_N`` is the cross-sectional variance across test assets. Both terms are
    centred. This is *not* the uncentred pricing-error pseudo-fit used as the
    contract fallback, and the two must never share a label. Because the second
    pass has no intercept the mean pricing error is generally non-zero, so the
    two statistics genuinely differ. The article notes at page 933 footnote 13
    that this metric can be negative.

    Args:
        mean_excess_returns: Average excess return per test asset.
        pricing_errors: Cross-sectional pricing error per test asset.

    Returns:
        The cross-sectional fit, which may be negative.

    Raises:
        ValueError: If the inputs are misaligned or the denominator vanishes.
    """
    if not mean_excess_returns.index.equals(pricing_errors.index):
        raise ValueError("Mean returns and pricing errors must share an index")
    if len(mean_excess_returns) < 2:
        raise ValueError("Cross-sectional fit needs at least two test assets")
    # The ratio is invariant to the degrees-of-freedom convention because the
    # same convention and the same N appear in both terms.
    denominator = float(np.var(mean_excess_returns.to_numpy(dtype=float)))
    if denominator == 0.0:
        raise ValueError("Cross-sectional variance of average returns is zero")
    numerator = float(np.var(pricing_errors.to_numpy(dtype=float)))
    return 1.0 - numerator / denominator


def article_constrained_fit(
    *,
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    factor_means: pd.Series,
) -> float:
    """Compute the article's constrained cross-sectional fit, equations (7) and (8).

    The constrained pricing errors restrict every risk price to the sample mean
    of the corresponding factor, so ``alpha_C = mean_return - B factor_mean``.
    The article states at page 934 that this restriction applies only to models
    whose factors are traded excess returns, and explicitly **not** to the
    ICAPM, whose hedging factors are not holding-period returns. Callers must
    enforce that restriction; this function does not know which factors are
    traded.

    Args:
        mean_excess_returns: Average excess return per test asset.
        betas: First-pass factor loadings, assets by factors.
        factor_means: Sample mean of each factor, indexed like the beta columns.

    Returns:
        The constrained cross-sectional fit, which may be negative.

    Raises:
        ValueError: If the inputs are misaligned.
    """
    if list(betas.columns) != list(factor_means.index):
        raise ValueError("Factor means must be indexed by the beta columns")
    if list(betas.index) != list(mean_excess_returns.index):
        raise ValueError("Betas must be indexed by the same assets as the mean returns")
    constrained_fitted = betas.to_numpy(dtype=float) @ factor_means.to_numpy(dtype=float)
    constrained_errors = pd.Series(
        mean_excess_returns.to_numpy(dtype=float) - constrained_fitted,
        index=mean_excess_returns.index,
        name="constrained_pricing_error",
    )
    return article_cross_sectional_fit(mean_excess_returns, constrained_errors)


def estimate_article_second_pass(
    *,
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    residual_covariance: pd.DataFrame,
    factor_covariance: pd.DataFrame,
    n_months: int,
    portfolio_set: str,
    model: str,
    pseudo_inverse_rcond: float = PSEUDO_INVERSE_RCOND,
) -> ArticleSecondPassResult:
    """Estimate the article's no-intercept second pass with Shanken inference.

    Implements article equations (4), (5), and (6). With ``B`` the ``N x K`` beta
    matrix, ``Sigma`` the first-pass residual covariance, ``Sigma_f`` the factor
    covariance, and ``T`` the number of months:

    ``lambda_hat = (B'B)^-1 B' mean_return``

    ``alpha_hat = mean_return - B lambda_hat``

    ``c = lambda_hat' Sigma_f^-1 lambda_hat``

    ``var(lambda_hat) = (1/T) [ (B'B)^-1 B' Sigma B (B'B)^-1 (1 + c) + Sigma_f ]``

    ``var(alpha_hat) = (1/T) M Sigma M' (1 + c)``  with  ``M = I - B(B'B)^-1 B'``

    ``chi2 = alpha_hat' var(alpha_hat)^+ alpha_hat  ~  chi2(N - K)``

    Args:
        mean_excess_returns: Average excess return per test asset.
        betas: First-pass factor loadings, assets by factors, no intercept column.
        residual_covariance: First-pass residual covariance across test assets.
        factor_covariance: Covariance of the priced factors.
        n_months: Number of months in the first-pass estimation window.
        portfolio_set: Identifier recorded on the result.
        model: Identifier recorded on the result.
        pseudo_inverse_rcond: Cutoff for the pricing-error pseudo-inverse.

    Returns:
        The complete second-pass result.

    Raises:
        ValueError: If the inputs are misaligned, too small, or singular.
    """
    assets = list(mean_excess_returns.index)
    if list(betas.index) != assets:
        raise ValueError("Betas must be indexed by the same assets as the mean returns")
    if list(residual_covariance.index) != assets or list(residual_covariance.columns) != assets:
        raise ValueError("Residual covariance must be indexed by the same assets")
    factors = list(betas.columns)
    if list(factor_covariance.index) != factors or list(factor_covariance.columns) != factors:
        raise ValueError("Factor covariance must be indexed by the beta columns")
    n_assets, n_factors = len(assets), len(factors)
    if n_assets <= n_factors:
        raise ValueError("The cross-section needs more assets than priced factors")
    if n_months <= 0:
        raise ValueError("n_months must be positive")

    returns = mean_excess_returns.to_numpy(dtype=float)
    beta_matrix = betas.to_numpy(dtype=float)
    residual_matrix = residual_covariance.to_numpy(dtype=float)
    factor_matrix = factor_covariance.to_numpy(dtype=float)

    gram = beta_matrix.T @ beta_matrix
    if np.linalg.matrix_rank(beta_matrix) < n_factors:
        raise ValueError("The beta matrix is rank deficient; risk prices are unidentified")
    gram_inverse = np.linalg.inv(gram)
    risk_prices = gram_inverse @ beta_matrix.T @ returns
    fitted = beta_matrix @ risk_prices
    errors = returns - fitted

    shanken_multiplier = 1.0 + float(risk_prices.T @ np.linalg.pinv(factor_matrix) @ risk_prices)

    bread = gram_inverse @ beta_matrix.T
    price_covariance = (
        bread @ residual_matrix @ bread.T * shanken_multiplier + factor_matrix
    ) / n_months
    price_standard_errors = np.sqrt(np.diag(price_covariance))

    ordinary_price_covariance = (bread @ residual_matrix @ bread.T) / n_months
    ordinary_standard_errors = np.sqrt(np.diag(ordinary_price_covariance))

    annihilator = np.eye(n_assets) - beta_matrix @ gram_inverse @ beta_matrix.T
    error_covariance = (
        annihilator @ residual_matrix @ annihilator.T * shanken_multiplier
    ) / n_months
    chi_square = float(
        errors.T @ np.linalg.pinv(error_covariance, rcond=pseudo_inverse_rcond) @ errors
    )
    degrees_of_freedom = n_assets - n_factors
    asymptotic_p_value = float(chi2_distribution.sf(chi_square, degrees_of_freedom))

    price_series = pd.Series(risk_prices, index=factors, name="risk_price")
    error_series = pd.Series(errors, index=assets, name="pricing_error")
    shanken_se = pd.Series(price_standard_errors, index=factors, name="shanken_standard_error")
    return ArticleSecondPassResult(
        portfolio_set=portfolio_set,
        model=model,
        n_assets=n_assets,
        n_months=n_months,
        n_factors=n_factors,
        risk_prices=price_series,
        shanken_standard_errors=shanken_se,
        shanken_t_statistics=(price_series / shanken_se).rename("shanken_t_statistic"),
        ordinary_standard_errors=pd.Series(
            ordinary_standard_errors, index=factors, name="ordinary_standard_error"
        ),
        pricing_errors=error_series,
        fitted_mean_returns=pd.Series(fitted, index=assets, name="fitted_mean_return"),
        article_cross_sectional_fit=article_cross_sectional_fit(mean_excess_returns, error_series),
        chi_square_statistic=chi_square,
        chi_square_degrees_of_freedom=degrees_of_freedom,
        chi_square_asymptotic_p_value=asymptotic_p_value,
        root_mean_squared_pricing_error=float(np.sqrt(np.mean(np.square(errors)))),
        mean_absolute_pricing_error=float(np.mean(np.abs(errors))),
        max_absolute_pricing_error=float(np.max(np.abs(errors))),
        shanken_multiplier=shanken_multiplier,
        pseudo_inverse_rcond=pseudo_inverse_rcond,
        beta_matrix_rank=int(np.linalg.matrix_rank(beta_matrix)),
        diagnostics={
            "mean_pricing_error": float(np.mean(errors)),
            "beta_matrix_condition_number": float(np.linalg.cond(beta_matrix)),
            "residual_covariance_condition_number": float(np.linalg.cond(residual_matrix)),
        },
    )


def residual_covariance_from_first_pass(residuals: pd.DataFrame) -> pd.DataFrame:
    """Build the first-pass residual covariance used by the Shanken formulas.

    Args:
        residuals: First-pass residuals, months by test assets.

    Returns:
        The asset-by-asset residual covariance.

    Raises:
        ValueError: If the residual panel has missing values or too few months.
    """
    if residuals.isna().to_numpy().any():
        raise ValueError("First-pass residuals must be complete before forming a covariance")
    if len(residuals) <= residuals.shape[1]:
        # A covariance estimated from fewer months than assets is singular. The
        # article's 70-portfolio system has 504 months, so this is a guard
        # against a mis-specified call rather than an expected condition.
        raise ValueError(
            "Residual covariance needs more months than assets; "
            f"got {len(residuals)} months and {residuals.shape[1]} assets"
        )
    return residuals.cov()
