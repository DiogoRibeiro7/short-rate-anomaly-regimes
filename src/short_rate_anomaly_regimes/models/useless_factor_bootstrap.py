r"""The article's useless-factor bootstrap, Internet Appendix Section 4.

Every empirical p-value the article prints comes from this procedure, and until
it existed here those cells were recorded as
``not_attempted_bootstrap_not_implemented`` rather than compared against an
asymptotic value, which would have been a different object. This module
implements the published algorithm literally so those cells become auditable.

The algorithm, as the Internet Appendix states it in six steps:

1. On the real data, run the first-pass time-series regression and the
   no-intercept second pass, and save ``t(lambda_k)``, the ``chi2`` statistic,
   both on Shanken (1992) standard errors, and the cross-sectional
   ``R2_OLS``. Also run the auxiliary regression of each asset's excess return
   on its own mean, which yields the mean excess returns and the residuals
   ``xi``.
2. In replication ``b``, resample ``xi`` over time with replacement, drawing one
   index sequence ``s_b`` that is **shared by every asset**. Sharing the sequence
   is what preserves the contemporaneous cross-correlation of returns.
3. Independently resample the factors with a second sequence ``r_b``, shared by
   every factor so their mutual correlations survive, and independent of
   ``s_b``. This independence is the whole design: it severs any relation
   between factors and returns.
4. Build pseudo returns by imposing the null that the factors do not explain
   returns, ``R_b = mean(R) + xi_b``. The mean is the original one, so only the
   factor-return relation is destroyed, not the cross-section of average returns.
5. Re-estimate both passes on the artificial data and save the same four
   statistics.
6. Read the empirical p-value off the resulting distribution.

What the resulting p-value is, and is not, is worth stating plainly. The null is
that the factor is *useless*: independent of returns, so its estimated betas are
noise. The p-value therefore answers "how often does a factor known to be
useless produce a t-ratio this extreme in a cross-section of this shape", which
is the Kan and Zhang (1999) concern the article is guarding against. It is not
the p-value of ``lambda = 0`` in a correctly specified model, and the two must
not be read as the same quantity.

This bootstrap is an **audit instrument**, not a confirmatory one. The
repository's own inference remains the moving-block bootstrap frozen in
``research/bootstrap_contract.md``, whose resampling unit, block length and
replication count are all different. Nothing here enters a registered gate; it
exists to compare a generated cell with a published one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    PSEUDO_INVERSE_RCOND,
    ArticleSecondPassResult,
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)

#: The article states 5,000 replications (Internet Appendix Section 4, step 2).
ARTICLE_REPLICATIONS = 5000

#: Label recorded on every artifact this module produces. The algorithm is the
#: published one, but the inputs are reconstructions, so the result is a
#: reconstruction of the article's bootstrap rather than the article's own.
REPLICATION_STATUS = "documented_reconstruction"


@dataclass(frozen=True, slots=True)
class UselessFactorBootstrapResult:
    """Empirical p-values for one system under the article's useless-factor null."""

    portfolio_set: str
    model: str
    n_assets: int
    n_months: int
    n_factors: int
    n_replications_requested: int
    n_replications_completed: int
    n_replications_degenerate: int
    seed: int
    sample_risk_prices: pd.Series
    sample_shanken_t_statistics: pd.Series
    sample_chi_square: float
    sample_article_fit: float
    risk_price_p_values: pd.Series
    bootstrap_t_statistic_medians: pd.Series
    chi_square_p_value: float
    article_fit_p_value: float
    replication_status: str = REPLICATION_STATUS
    diagnostics: dict[str, float] = field(default_factory=dict)


def first_pass_by_matrix_ols(
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the first pass for every asset at once, returning betas and residuals.

    The article's first pass is an OLS time-series regression with an intercept.
    Every asset shares one design matrix, so all ``N`` regressions are one least
    squares solve. This is the same estimator as
    :func:`~short_rate_anomaly_regimes.models.time_series.estimate_time_series_betas`
    produces coefficients for; that function additionally computes HAC standard
    errors, which the bootstrap never reads and which would dominate its cost
    across five thousand replications.

    Args:
        excess_returns: Months by test assets.
        factors: Months by priced factors, sharing the return index.

    Returns:
        The asset-by-factor betas and the months-by-asset residuals.

    Raises:
        ValueError: If the inputs are misaligned or hold missing values.
    """
    if not excess_returns.index.equals(factors.index):
        raise ValueError("Returns and factors must share a time index")
    if excess_returns.isna().to_numpy().any() or factors.isna().to_numpy().any():
        raise ValueError("The first pass does not impute missing observations")
    n_months = len(excess_returns)
    if n_months <= factors.shape[1] + 1:
        raise ValueError("The first pass needs more months than design columns")

    factor_matrix = factors.to_numpy(dtype=float)
    design = np.column_stack([np.ones(n_months), factor_matrix])
    targets = excess_returns.to_numpy(dtype=float)
    coefficients, *_ = np.linalg.lstsq(design, targets, rcond=None)
    residuals = targets - design @ coefficients
    betas = pd.DataFrame(
        coefficients[1:].T,
        index=excess_returns.columns,
        columns=factors.columns,
    )
    return betas, pd.DataFrame(
        residuals, index=excess_returns.index, columns=excess_returns.columns
    )


def _estimate_system(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    portfolio_set: str,
    model: str,
    pseudo_inverse_rcond: float,
) -> ArticleSecondPassResult:
    """Run both passes and return the article's second-pass result."""
    betas, residuals = first_pass_by_matrix_ols(excess_returns, factors)
    return estimate_article_second_pass(
        mean_excess_returns=excess_returns.mean().rename("mean_return"),
        betas=betas,
        residual_covariance=residual_covariance_from_first_pass(residuals),
        factor_covariance=factors.cov(),
        n_months=len(excess_returns),
        portfolio_set=portfolio_set,
        model=model,
        pseudo_inverse_rcond=pseudo_inverse_rcond,
    )


def empirical_risk_price_p_value(
    *,
    sample_risk_price: float,
    sample_t_statistic: float,
    bootstrap_t_statistics: np.ndarray,
) -> float:
    """Compute the article's two-sided empirical p-value for one risk price.

    Internet Appendix Section 4, step 6, defines it by the sign of the estimate::

        lambda >= 0:  [ #{t_b >= t} + #{t_b <  -t} ] / B
        lambda <  0:  [ #{t_b <= t} + #{t_b >  -t} ] / B

    The two branches are transcribed exactly as printed, including the mixed
    strict and non-strict comparisons. They are not tidied into a symmetric
    ``|t_b| >= |t|`` rule: that would be a different statistic on ties, and the
    point of this module is that a generated cell and a published one are the
    same object.

    Args:
        sample_risk_price: The risk-price point estimate, which selects the branch.
        sample_t_statistic: The Shanken t-ratio from the real data.
        bootstrap_t_statistics: Shanken t-ratios across replications.

    Returns:
        The empirical p-value.

    Raises:
        ValueError: If no replications were supplied.
    """
    draws = np.asarray(bootstrap_t_statistics, dtype=float)
    if draws.size == 0:
        raise ValueError("An empirical p-value needs at least one replication")
    if sample_risk_price >= 0.0:
        exceedances = np.count_nonzero(draws >= sample_t_statistic) + np.count_nonzero(
            draws < -sample_t_statistic
        )
    else:
        exceedances = np.count_nonzero(draws <= sample_t_statistic) + np.count_nonzero(
            draws > -sample_t_statistic
        )
    return float(exceedances) / float(draws.size)


def bootstrap_useless_factor_p_values(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    portfolio_set: str,
    model: str,
    seed: int,
    n_replications: int = ARTICLE_REPLICATIONS,
    pseudo_inverse_rcond: float = PSEUDO_INVERSE_RCOND,
) -> UselessFactorBootstrapResult:
    """Run the article's useless-factor bootstrap for one system.

    Args:
        excess_returns: Months by test assets.
        factors: Months by priced factors, sharing the return index.
        portfolio_set: Identifier recorded on the result.
        model: Identifier recorded on the result.
        seed: Seed for the replication draws, recorded on the result.
        n_replications: Replication count. The article uses 5,000.
        pseudo_inverse_rcond: Passed through to the second-pass estimator.

    Returns:
        The sample statistics and their empirical p-values.

    Raises:
        ValueError: If the inputs are misaligned or ``n_replications`` is not positive.
    """
    if n_replications <= 0:
        raise ValueError("n_replications must be positive")

    sample = _estimate_system(
        excess_returns=excess_returns,
        factors=factors,
        portfolio_set=portfolio_set,
        model=model,
        pseudo_inverse_rcond=pseudo_inverse_rcond,
    )

    # Step 1's auxiliary regression. Regressing each asset on a constant makes
    # the fitted value the sample mean and the residual the demeaned return, so
    # the regression is written out here rather than solved.
    mean_returns = excess_returns.mean()
    centred_returns = (excess_returns - mean_returns).to_numpy(dtype=float)
    factor_matrix = factors.to_numpy(dtype=float)
    n_months = len(excess_returns)

    rng = np.random.default_rng(seed)
    factor_names = list(factors.columns)
    t_draws: list[np.ndarray] = []
    chi_square_draws: list[float] = []
    fit_draws: list[float] = []
    degenerate = 0

    for _ in range(n_replications):
        # Step 2: one index sequence for every asset, so the cross-sectional
        # correlation of returns survives the resampling.
        residual_index = rng.integers(0, n_months, size=n_months)
        # Step 3: a second sequence, independent of the first and shared across
        # factors. The independence is what imposes the useless-factor null.
        factor_index = rng.integers(0, n_months, size=n_months)

        # Step 4: the null is imposed by construction, not tested for.
        pseudo_returns = pd.DataFrame(
            mean_returns.to_numpy(dtype=float) + centred_returns[residual_index],
            index=excess_returns.index,
            columns=excess_returns.columns,
        )
        pseudo_factors = pd.DataFrame(
            factor_matrix[factor_index],
            index=excess_returns.index,
            columns=factor_names,
        )

        try:
            replication = _estimate_system(
                excess_returns=pseudo_returns,
                factors=pseudo_factors,
                portfolio_set=portfolio_set,
                model=model,
                pseudo_inverse_rcond=pseudo_inverse_rcond,
            )
        except ValueError:
            # A draw whose pseudo betas are collinear, or whose resampled
            # factors have no variation, leaves the risk prices unidentified.
            # It is counted rather than resampled away, because silently
            # redrawing until every replication succeeds would condition the
            # null distribution on the estimator's success.
            degenerate += 1
            continue

        t_draws.append(replication.shanken_t_statistics.to_numpy(dtype=float))
        chi_square_draws.append(replication.chi_square_statistic)
        fit_draws.append(replication.article_cross_sectional_fit)

    completed = len(chi_square_draws)
    if completed == 0:
        raise ValueError("Every bootstrap replication was degenerate")

    t_matrix = np.vstack(t_draws)
    p_values = pd.Series(
        [
            empirical_risk_price_p_value(
                sample_risk_price=float(sample.risk_prices.iloc[position]),
                sample_t_statistic=float(sample.shanken_t_statistics.iloc[position]),
                bootstrap_t_statistics=t_matrix[:, position],
            )
            for position in range(len(factor_names))
        ],
        index=factor_names,
        name="empirical_p_value",
    )

    chi_square_array = np.asarray(chi_square_draws, dtype=float)
    fit_array = np.asarray(fit_draws, dtype=float)
    return UselessFactorBootstrapResult(
        portfolio_set=portfolio_set,
        model=model,
        n_assets=sample.n_assets,
        n_months=n_months,
        n_factors=sample.n_factors,
        n_replications_requested=n_replications,
        n_replications_completed=completed,
        n_replications_degenerate=degenerate,
        seed=seed,
        sample_risk_prices=sample.risk_prices,
        sample_shanken_t_statistics=sample.shanken_t_statistics,
        sample_chi_square=sample.chi_square_statistic,
        sample_article_fit=sample.article_cross_sectional_fit,
        risk_price_p_values=p_values,
        # The null distribution's location. Because steps 2 and 3 draw
        # independent time sequences, these medians sit near zero however
        # strongly the factor is priced in the real sample. A design that shared
        # one sequence would carry the alternative into the null and pull them
        # toward the sample t-ratios, so this is the number that shows the null
        # was actually imposed.
        bootstrap_t_statistic_medians=pd.Series(
            np.median(t_matrix, axis=0),
            index=factor_names,
            name="bootstrap_t_statistic_median",
        ),
        # Steps 6's remaining two definitions are one-sided upper-tail counts.
        chi_square_p_value=float(
            np.count_nonzero(chi_square_array >= sample.chi_square_statistic) / completed
        ),
        article_fit_p_value=float(
            np.count_nonzero(fit_array >= sample.article_cross_sectional_fit) / completed
        ),
        diagnostics={
            "median_bootstrap_chi_square": float(np.median(chi_square_array)),
            "median_bootstrap_article_fit": float(np.median(fit_array)),
            # Under a useless factor the cross-sectional fit is still positive on
            # average, because two noise regressors explain some of any
            # cross-section. This is the number that makes a large sample fit
            # readable rather than impressive on its own.
            "mean_bootstrap_article_fit": float(np.mean(fit_array)),
            "bootstrap_article_fit_95th_percentile": float(np.percentile(fit_array, 95.0)),
        },
    )
