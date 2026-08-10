"""First-pass time-series asset-pricing regressions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
import numpy.typing as npt
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch

CovarianceMethod = Literal["newey_west"]

#: Explicit array alias. Newer numpy stubs reject a bare ``np.ndarray``.
FloatArray = npt.NDArray[np.floating[Any]]


@dataclass(frozen=True, slots=True)
class AlignmentSummary:
    """Observation accounting for first-pass sample construction."""

    return_observations: int
    factor_observations: int
    common_observations: int
    dropped_return_dates: int
    dropped_factor_dates: int
    dropped_incomplete_rows: int


@dataclass(frozen=True, slots=True)
class MatrixOLSResult:
    """Direct matrix-algebra OLS result with HAC covariance."""

    parameters: pd.Series
    covariance: pd.DataFrame
    standard_errors: pd.Series
    t_statistics: pd.Series


@dataclass(frozen=True, slots=True)
class TimeSeriesResult:
    """First-pass coefficients and diagnostics for all test assets."""

    coefficients: pd.DataFrame
    standard_errors: pd.DataFrame
    t_statistics: pd.DataFrame
    p_values: pd.DataFrame
    confidence_interval_low: pd.DataFrame
    confidence_interval_high: pd.DataFrame
    residuals: pd.DataFrame
    r_squared: pd.Series
    adjusted_r_squared: pd.Series
    nobs: pd.Series
    diagnostics: pd.DataFrame
    alignment: AlignmentSummary
    factor_order: tuple[str, ...]
    covariance: CovarianceMethod
    hac_lags: int


def estimate_time_series_betas(
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    *,
    hac_lags: int,
) -> TimeSeriesResult:
    """Estimate asset-specific factor loadings using OLS with HAC inference."""
    aligned_returns, aligned_factors, alignment = align_first_pass_inputs(
        excess_returns=excess_returns,
        factors=factors,
    )
    joined = aligned_returns.join(aligned_factors, how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations between returns and factors")
    factor_names = list(aligned_factors.columns)
    design = sm.add_constant(joined[factor_names], has_constant="add")
    coefficients: dict[str, pd.Series] = {}
    standard_errors: dict[str, pd.Series] = {}
    t_statistics: dict[str, pd.Series] = {}
    p_values: dict[str, pd.Series] = {}
    confidence_interval_low: dict[str, pd.Series] = {}
    confidence_interval_high: dict[str, pd.Series] = {}
    residuals: dict[str, pd.Series] = {}
    r_squared: dict[str, float] = {}
    adjusted_r_squared: dict[str, float] = {}
    nobs: dict[str, int] = {}
    diagnostics: dict[str, pd.Series] = {}
    for asset in aligned_returns.columns:
        model = sm.OLS(joined[asset], design).fit(
            cov_type="HAC",
            cov_kwds={"maxlags": hac_lags, "use_correction": False},
        )
        coefficients[asset] = model.params
        standard_errors[asset] = model.bse
        t_statistics[asset] = model.tvalues
        p_values[asset] = model.pvalues
        confidence = model.conf_int(alpha=0.05)
        confidence_interval_low[asset] = confidence[0]
        confidence_interval_high[asset] = confidence[1]
        residuals[asset] = model.resid
        r_squared[asset] = float(model.rsquared)
        adjusted_r_squared[asset] = float(model.rsquared_adj)
        nobs[asset] = int(model.nobs)
        diagnostics[asset] = first_pass_diagnostics(model, asset=asset)
    return TimeSeriesResult(
        coefficients=pd.DataFrame(coefficients).T,
        standard_errors=pd.DataFrame(standard_errors).T,
        t_statistics=pd.DataFrame(t_statistics).T,
        p_values=pd.DataFrame(p_values).T,
        confidence_interval_low=pd.DataFrame(confidence_interval_low).T,
        confidence_interval_high=pd.DataFrame(confidence_interval_high).T,
        residuals=pd.DataFrame(residuals),
        diagnostics=pd.DataFrame(diagnostics).T,
        r_squared=pd.Series(r_squared, name="r_squared"),
        adjusted_r_squared=pd.Series(adjusted_r_squared, name="adjusted_r_squared"),
        nobs=pd.Series(nobs, name="nobs", dtype="int64"),
        alignment=alignment,
        factor_order=tuple(factor_names),
        covariance="newey_west",
        hac_lags=hac_lags,
    )


def construct_excess_returns(
    portfolio_returns: pd.DataFrame,
    risk_free: pd.Series,
) -> pd.DataFrame:
    """Subtract the frozen risk-free return from each portfolio-return column."""
    if not isinstance(portfolio_returns.index, pd.DatetimeIndex):
        raise TypeError("Portfolio returns must use a DatetimeIndex")
    if not isinstance(risk_free.index, pd.DatetimeIndex):
        raise TypeError("Risk-free returns must use a DatetimeIndex")
    if portfolio_returns.columns.duplicated().any():
        raise ValueError("Portfolio return columns must be unique")
    joined = portfolio_returns.join(risk_free.rename("risk_free"), how="inner")
    if joined.empty:
        raise ValueError("No common observations between portfolios and risk-free returns")
    excess = joined.loc[:, list(portfolio_returns.columns)].subtract(joined["risk_free"], axis=0)
    excess.columns = [str(column) for column in portfolio_returns.columns]
    return excess.sort_index()


def align_first_pass_inputs(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, AlignmentSummary]:
    """Intersect return and factor dates explicitly and record observation losses."""
    if not isinstance(excess_returns.index, pd.DatetimeIndex):
        raise TypeError("Excess returns must use a DatetimeIndex")
    if not isinstance(factors.index, pd.DatetimeIndex):
        raise TypeError("Factors must use a DatetimeIndex")
    if excess_returns.index.has_duplicates:
        raise ValueError("Excess returns contain duplicate dates")
    if factors.index.has_duplicates:
        raise ValueError("Factors contain duplicate dates")
    sorted_returns = excess_returns.sort_index()
    sorted_factors = factors.sort_index()
    common_index = sorted_returns.index.intersection(sorted_factors.index).sort_values()
    if common_index.empty:
        raise ValueError("No common dates between returns and factors")
    pre_drop = sorted_returns.loc[common_index].join(sorted_factors.loc[common_index], how="inner")
    complete = pre_drop.dropna()
    aligned_returns = complete.loc[:, list(sorted_returns.columns)]
    aligned_factors = complete.loc[:, list(sorted_factors.columns)]
    summary = AlignmentSummary(
        return_observations=int(sorted_returns.shape[0]),
        factor_observations=int(sorted_factors.shape[0]),
        common_observations=int(complete.shape[0]),
        dropped_return_dates=int(sorted_returns.shape[0] - len(common_index)),
        dropped_factor_dates=int(sorted_factors.shape[0] - len(common_index)),
        dropped_incomplete_rows=int(pre_drop.shape[0] - complete.shape[0]),
    )
    return aligned_returns, aligned_factors, summary


def automatic_newey_west_lags(nobs: int) -> int:
    """Return the common monthly Newey-West automatic lag length."""
    if nobs <= 0:
        raise ValueError("nobs must be positive")
    return int(np.floor(4.0 * (nobs / 100.0) ** (2.0 / 9.0)))


def estimate_matrix_ols_hac(
    response: pd.Series,
    regressors: pd.DataFrame,
    *,
    hac_lags: int,
    include_intercept: bool = True,
) -> MatrixOLSResult:
    """Estimate OLS and Newey-West covariance directly through matrix algebra."""
    joined = regressors.join(response.rename("response"), how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations for matrix OLS")
    factor_names = list(regressors.columns)
    design = joined[factor_names]
    if include_intercept:
        design = sm.add_constant(design, has_constant="add")
    y = joined["response"].to_numpy(dtype=float)
    x = design.to_numpy(dtype=float)
    xtx_inv = np.linalg.inv(x.T @ x)
    beta = xtx_inv @ x.T @ y
    residuals = y - x @ beta
    meat = _newey_west_meat(x, residuals, hac_lags=hac_lags)
    covariance = xtx_inv @ meat @ xtx_inv
    parameters = pd.Series(beta, index=design.columns, name="parameter")
    covariance_frame = pd.DataFrame(covariance, index=design.columns, columns=design.columns)
    standard_errors = pd.Series(
        np.sqrt(np.diag(covariance)),
        index=design.columns,
        name="standard_error",
    )
    t_statistics = (parameters / standard_errors).rename("t_statistic")
    return MatrixOLSResult(
        parameters=parameters,
        covariance=covariance_frame,
        standard_errors=standard_errors,
        t_statistics=t_statistics,
    )


def first_pass_diagnostics(
    fitted_model: Any,
    *,
    asset: str,
    crisis_months: tuple[pd.Timestamp, ...] = (),
) -> pd.Series:
    """Compute residual and influence diagnostics without changing the fitted model."""
    model = fitted_model
    residuals = pd.Series(
        np.asarray(model.resid, dtype=np.float64),
        index=model.model.data.row_labels,
    )
    ljung_box = acorr_ljungbox(residuals, lags=[min(6, max(1, len(residuals) // 2))])
    arch_lags = min(6, max(1, len(residuals) // 3))
    _arch_stat, arch_pvalue, _, _ = het_arch(residuals, nlags=arch_lags)
    _jarque_bera_stat, jarque_bera_pvalue, _, _ = sm.stats.stattools.jarque_bera(residuals)
    influence = model.get_influence()
    leverage = pd.Series(influence.hat_matrix_diag, index=residuals.index)
    cooks = pd.Series(influence.cooks_distance[0], index=residuals.index)
    dfbeta = pd.DataFrame(influence.dfbetas, index=residuals.index)
    crisis_overlap = residuals.index.intersection(pd.DatetimeIndex(crisis_months))
    crisis_abs_residual = (
        float(residuals.loc[crisis_overlap].abs().max()) if len(crisis_overlap) else np.nan
    )
    return pd.Series(
        {
            "asset": asset,
            "durbin_watson": float(sm.stats.stattools.durbin_watson(residuals)),
            "ljung_box_pvalue": float(ljung_box["lb_pvalue"].iloc[0]),
            "arch_lm_pvalue": float(arch_pvalue),
            "jarque_bera_pvalue": float(jarque_bera_pvalue),
            "max_abs_residual": float(residuals.abs().max()),
            "max_leverage": float(leverage.max()),
            "max_cooks_distance": float(cooks.max()),
            "max_abs_dfbeta": float(np.abs(dfbeta.to_numpy(dtype=float)).max()),
            "crisis_month_count": len(crisis_overlap),
            "crisis_max_abs_residual": crisis_abs_residual,
        }
    )


def coefficient_table(result: TimeSeriesResult) -> pd.DataFrame:
    """Return a stable long-form coefficient table for storage and reporting."""
    rows: list[dict[str, float | int | str]] = []
    for asset in result.coefficients.index:
        for parameter in result.coefficients.columns:
            rows.append(
                {
                    "asset": str(asset),
                    "parameter": str(parameter),
                    "coefficient": float(result.coefficients.loc[asset, parameter]),
                    "standard_error": float(result.standard_errors.loc[asset, parameter]),
                    "t_statistic": float(result.t_statistics.loc[asset, parameter]),
                    "p_value": float(result.p_values.loc[asset, parameter]),
                    "confidence_interval_low": float(
                        result.confidence_interval_low.loc[asset, parameter]
                    ),
                    "confidence_interval_high": float(
                        result.confidence_interval_high.loc[asset, parameter]
                    ),
                    "r_squared": float(result.r_squared.loc[asset]),
                    "adjusted_r_squared": float(result.adjusted_r_squared.loc[asset]),
                    "nobs": int(result.nobs.loc[asset]),
                }
            )
    return pd.DataFrame(rows)


def write_time_series_outputs(
    result: TimeSeriesResult,
    *,
    coefficients_path: Path,
    residuals_path: Path,
    diagnostics_path: Path,
    table_path: Path,
    metadata_path: Path,
    metadata: dict[str, str],
) -> None:
    """Write machine-readable first-pass artifacts and table metadata."""
    for path in (coefficients_path, residuals_path, diagnostics_path, table_path, metadata_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    table = coefficient_table(result)
    table.to_parquet(coefficients_path, index=False)
    result.residuals.to_parquet(residuals_path)
    result.diagnostics.to_json(diagnostics_path, orient="index", indent=2)
    table.to_csv(table_path, index=False, lineterminator="\n")
    payload = {
        **metadata,
        "covariance": result.covariance,
        "hac_lags": result.hac_lags,
        "factor_order": list(result.factor_order),
        "alignment": {
            "return_observations": result.alignment.return_observations,
            "factor_observations": result.alignment.factor_observations,
            "common_observations": result.alignment.common_observations,
            "dropped_return_dates": result.alignment.dropped_return_dates,
            "dropped_factor_dates": result.alignment.dropped_factor_dates,
            "dropped_incomplete_rows": result.alignment.dropped_incomplete_rows,
        },
    }
    metadata_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )


def _newey_west_meat(x: FloatArray, residuals: FloatArray, *, hac_lags: int) -> FloatArray:
    if hac_lags < 0:
        raise ValueError("hac_lags must be nonnegative")
    score = x * residuals[:, None]
    meat = score.T @ score
    for lag in range(1, hac_lags + 1):
        if lag >= score.shape[0]:
            break
        weight = 1.0 - lag / (hac_lags + 1.0)
        gamma = score[lag:].T @ score[:-lag]
        meat += weight * (gamma + gamma.T)
    return cast(FloatArray, meat)
