"""Second-pass cross-sectional asset-pricing estimators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm

EstimatorName = Literal["ols_two_pass", "gls_two_pass", "fama_macbeth"]


@dataclass(frozen=True, slots=True)
class WeakFactorWarning:
    """Weak-factor diagnostic warning for a cross-sectional beta matrix."""

    condition_number: float
    min_singular_value: float
    beta_rank: int
    warning: str | None


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
    corrected_standard_errors: pd.Series
    corrected_t_statistics: pd.Series
    confidence_interval_low: pd.Series
    confidence_interval_high: pd.Series
    max_abs_alpha: float
    estimator: EstimatorName
    include_intercept: bool
    beta_source: str
    estimation_window: str
    weighting_matrix: pd.DataFrame | None
    regularization: float
    weak_factor_warning: WeakFactorWarning
    n_assets: int


def estimate_ols_two_pass(
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    *,
    include_intercept: bool = True,
    factor_covariance: pd.DataFrame | None = None,
    beta_source: str = "first_pass_time_series",
    estimation_window: str = "full_sample",
) -> CrossSectionResult:
    """Estimate an OLS second-pass cross-sectional regression."""
    joined, design = _prepare_cross_section_design(
        mean_excess_returns,
        betas,
        include_intercept=include_intercept,
    )
    fitted_model = sm.OLS(joined["mean_return"], design).fit()
    fitted = fitted_model.fittedvalues.rename("fitted_mean_return")
    errors = (joined["mean_return"] - fitted).rename("pricing_error")
    uncorrected_se = fitted_model.bse.rename("standard_error")
    corrected_se = _apply_shanken_style_correction(
        risk_prices=fitted_model.params,
        standard_errors=uncorrected_se,
        factor_covariance=factor_covariance,
        include_intercept=include_intercept,
    )
    return _build_result(
        estimator="ols_two_pass",
        include_intercept=include_intercept,
        beta_source=beta_source,
        estimation_window=estimation_window,
        risk_prices=fitted_model.params,
        standard_errors=uncorrected_se,
        corrected_standard_errors=corrected_se,
        fitted=fitted,
        errors=errors,
        observed=joined["mean_return"],
        betas=joined[list(betas.columns)],
        weighting_matrix=None,
        regularization=0.0,
    )


def estimate_gls_two_pass(
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    *,
    pricing_error_covariance: pd.DataFrame,
    include_intercept: bool = True,
    regularization: float = 0.0,
    factor_covariance: pd.DataFrame | None = None,
    beta_source: str = "first_pass_time_series",
    estimation_window: str = "full_sample",
) -> CrossSectionResult:
    """Estimate a GLS second-pass regression with an explicit weighting matrix."""
    if regularization < 0:
        raise ValueError("regularization must be nonnegative")
    joined, design = _prepare_cross_section_design(
        mean_excess_returns,
        betas,
        include_intercept=include_intercept,
    )
    covariance = pricing_error_covariance.loc[joined.index, joined.index].astype(float)
    covariance = covariance + np.eye(covariance.shape[0]) * regularization
    weights = pd.DataFrame(
        np.linalg.pinv(covariance.to_numpy(dtype=float)),
        index=joined.index,
        columns=joined.index,
    )
    x = design.to_numpy(dtype=float)
    y = joined["mean_return"].to_numpy(dtype=float)
    w = weights.to_numpy(dtype=float)
    xtwx_inv = np.linalg.pinv(x.T @ w @ x)
    params = xtwx_inv @ x.T @ w @ y
    fitted = pd.Series(x @ params, index=joined.index, name="fitted_mean_return")
    errors = (joined["mean_return"] - fitted).rename("pricing_error")
    sigma2 = float(errors.to_numpy(dtype=float).T @ w @ errors.to_numpy(dtype=float))
    denominator = max(1, joined.shape[0] - design.shape[1])
    covariance_params = xtwx_inv * (sigma2 / denominator)
    standard_errors = pd.Series(
        np.sqrt(np.diag(covariance_params)),
        index=design.columns,
        name="standard_error",
    )
    risk_prices = pd.Series(params, index=design.columns, name="risk_price")
    corrected_se = _apply_shanken_style_correction(
        risk_prices=risk_prices,
        standard_errors=standard_errors,
        factor_covariance=factor_covariance,
        include_intercept=include_intercept,
    )
    return _build_result(
        estimator="gls_two_pass",
        include_intercept=include_intercept,
        beta_source=beta_source,
        estimation_window=estimation_window,
        risk_prices=risk_prices,
        standard_errors=standard_errors,
        corrected_standard_errors=corrected_se,
        fitted=fitted,
        errors=errors,
        observed=joined["mean_return"],
        betas=joined[list(betas.columns)],
        weighting_matrix=weights,
        regularization=regularization,
    )


def estimate_fama_macbeth(
    excess_returns: pd.DataFrame,
    betas: pd.DataFrame,
    *,
    include_intercept: bool = True,
    beta_source: str = "first_pass_time_series",
    estimation_window: str = "fixed_beta_panel",
) -> CrossSectionResult:
    """Estimate fixed-beta Fama-MacBeth cross-sectional risk prices."""
    common_assets = [asset for asset in excess_returns.columns if asset in betas.index]
    if not common_assets:
        raise ValueError("No common assets between return panel and beta estimates")
    asset_returns = excess_returns.loc[:, common_assets].dropna(how="all")
    beta_panel = betas.loc[common_assets]
    period_prices: list[pd.Series] = []
    fitted_accumulator = pd.Series(0.0, index=common_assets)
    observed_means = asset_returns.mean(axis=0).rename("mean_return")
    for _date, row in asset_returns.iterrows():
        observed = pd.Series(row, index=common_assets, dtype=float).dropna()
        if observed.shape[0] <= beta_panel.shape[1]:
            continue
        joined, design = _prepare_cross_section_design(
            observed,
            beta_panel.loc[observed.index],
            include_intercept=include_intercept,
        )
        model = sm.OLS(joined["mean_return"], design).fit()
        period_prices.append(model.params)
        fitted_accumulator.loc[joined.index] += model.fittedvalues
    if not period_prices:
        raise ValueError("No Fama-MacBeth cross sections have enough complete assets")
    prices = pd.DataFrame(period_prices)
    risk_prices = prices.mean(axis=0).rename("risk_price")
    standard_errors = (prices.std(axis=0, ddof=1) / np.sqrt(prices.shape[0])).rename(
        "standard_error"
    )
    fitted = (fitted_accumulator / prices.shape[0]).rename("fitted_mean_return")
    errors = (observed_means - fitted).rename("pricing_error")
    return _build_result(
        estimator="fama_macbeth",
        include_intercept=include_intercept,
        beta_source=beta_source,
        estimation_window=estimation_window,
        risk_prices=risk_prices,
        standard_errors=standard_errors,
        corrected_standard_errors=standard_errors.copy(),
        fitted=fitted,
        errors=errors,
        observed=observed_means,
        betas=beta_panel,
        weighting_matrix=None,
        regularization=0.0,
    )


def weak_factor_diagnostic(
    betas: pd.DataFrame,
    *,
    condition_threshold: float = 1_000.0,
    singular_value_threshold: float = 1e-8,
) -> WeakFactorWarning:
    """Compute beta-matrix rank and conditioning warnings."""
    if betas.empty:
        raise ValueError("Beta matrix cannot be empty")
    values = betas.to_numpy(dtype=float)
    singular_values = np.linalg.svd(values, compute_uv=False)
    min_singular = float(singular_values.min())
    max_singular = float(singular_values.max())
    condition_number = float("inf") if min_singular == 0.0 else max_singular / min_singular
    rank = int(np.linalg.matrix_rank(values))
    warning: str | None = None
    if rank < values.shape[1]:
        warning = "beta_matrix_rank_deficient"
    elif condition_number > condition_threshold or min_singular < singular_value_threshold:
        warning = "beta_matrix_ill_conditioned"
    return WeakFactorWarning(
        condition_number=condition_number,
        min_singular_value=min_singular,
        beta_rank=rank,
        warning=warning,
    )


def model_evaluation_table(results: dict[str, CrossSectionResult]) -> pd.DataFrame:
    """Create a stable model-comparison table from cross-sectional results."""
    rows = [
        {
            "model": model_name,
            "estimator": result.estimator,
            "r_squared": result.r_squared,
            "rmse": result.rmse,
            "mae": result.mae,
            "max_abs_alpha": result.max_abs_alpha,
            "n_assets": result.n_assets,
            "weak_factor_warning": result.weak_factor_warning.warning,
        }
        for model_name, result in results.items()
    ]
    return pd.DataFrame(rows)


def leave_one_group_out(
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    groups: pd.Series,
    *,
    include_intercept: bool = True,
) -> dict[str, CrossSectionResult]:
    """Estimate OLS systems leaving each registered asset group out."""
    outputs: dict[str, CrossSectionResult] = {}
    for group in sorted(groups.dropna().unique()):
        kept_assets = groups[groups != group].index
        outputs[str(group)] = estimate_ols_two_pass(
            mean_excess_returns.loc[kept_assets],
            betas.loc[kept_assets],
            include_intercept=include_intercept,
            estimation_window=f"leave_out_{group}",
        )
    return outputs


def simulate_factor_model(
    *,
    n_periods: int,
    betas: pd.DataFrame,
    risk_prices: pd.Series,
    residual_scale: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Simulate returns with known cross-sectional risk prices."""
    rng = np.random.default_rng(seed)
    factor_names = list(betas.columns)
    factors = pd.DataFrame(
        rng.normal(0.0, 0.04, size=(n_periods, len(factor_names))),
        columns=factor_names,
        index=pd.date_range("2000-01-31", periods=n_periods, freq="ME"),
    )
    expected_returns = betas @ risk_prices.loc[factor_names]
    noise = rng.normal(0.0, residual_scale, size=(n_periods, betas.shape[0]))
    returns = pd.DataFrame(
        expected_returns.to_numpy(dtype=float)[None, :] + noise,
        index=factors.index,
        columns=betas.index,
    )
    return returns, factors, expected_returns.rename("mean_return")


def coefficient_table(result: CrossSectionResult) -> pd.DataFrame:
    """Return a stable long-form risk-price table."""
    return pd.DataFrame(
        {
            "parameter": result.risk_prices.index,
            "risk_price": result.risk_prices.to_numpy(dtype=float),
            "standard_error": result.standard_errors.to_numpy(dtype=float),
            "t_statistic": result.t_statistics.to_numpy(dtype=float),
            "corrected_standard_error": result.corrected_standard_errors.to_numpy(dtype=float),
            "corrected_t_statistic": result.corrected_t_statistics.to_numpy(dtype=float),
            "confidence_interval_low": result.confidence_interval_low.to_numpy(dtype=float),
            "confidence_interval_high": result.confidence_interval_high.to_numpy(dtype=float),
            "estimator": result.estimator,
            "include_intercept": result.include_intercept,
            "beta_source": result.beta_source,
            "estimation_window": result.estimation_window,
        }
    )


def write_cross_section_outputs(
    result: CrossSectionResult,
    *,
    coefficients_path: Path,
    pricing_errors_path: Path,
    metrics_path: Path,
    metadata_path: Path,
    metadata: dict[str, str],
) -> None:
    """Write machine-readable cross-sectional result artifacts."""
    for path in (coefficients_path, pricing_errors_path, metrics_path, metadata_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    coefficient_table(result).to_parquet(coefficients_path, index=False)
    result.pricing_errors.rename("pricing_error").to_frame().to_parquet(pricing_errors_path)
    metrics = {
        "r_squared": result.r_squared,
        "rmse": result.rmse,
        "mae": result.mae,
        "max_abs_alpha": result.max_abs_alpha,
        "n_assets": result.n_assets,
        "weak_factor_warning": result.weak_factor_warning.warning,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    payload = {
        **metadata,
        "estimator": result.estimator,
        "include_intercept": result.include_intercept,
        "beta_source": result.beta_source,
        "estimation_window": result.estimation_window,
        "regularization": result.regularization,
    }
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _prepare_cross_section_design(
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    *,
    include_intercept: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    joined = betas.join(mean_excess_returns.rename("mean_return"), how="inner").dropna()
    if joined.empty:
        raise ValueError("No common assets between mean returns and beta estimates")
    factor_names = list(betas.columns)
    design = joined[factor_names]
    if include_intercept:
        design = sm.add_constant(design, has_constant="add")
    return joined, design


def _apply_shanken_style_correction(
    *,
    risk_prices: pd.Series,
    standard_errors: pd.Series,
    factor_covariance: pd.DataFrame | None,
    include_intercept: bool,
) -> pd.Series:
    if factor_covariance is None:
        return standard_errors.rename("corrected_standard_error")
    factor_prices = (
        risk_prices.drop(labels=["const"], errors="ignore") if include_intercept else risk_prices
    )
    covariance = factor_covariance.loc[factor_prices.index, factor_prices.index]
    adjustment = 1.0 + float(
        factor_prices.to_numpy(dtype=float).T
        @ np.linalg.pinv(covariance.to_numpy(dtype=float))
        @ factor_prices.to_numpy(dtype=float)
    )
    corrected_values = standard_errors.to_numpy(dtype=float) * float(np.sqrt(adjustment))
    return pd.Series(
        corrected_values,
        index=standard_errors.index,
        name="corrected_standard_error",
    )


def _fit_statistics(observed: pd.Series, errors: pd.Series) -> tuple[float, float, float, float]:
    variance = float(np.square(observed - observed.mean()).sum())
    residual_sum = float(np.square(errors).sum())
    r_squared = float("nan") if variance == 0.0 else 1.0 - residual_sum / variance
    rmse = float(np.sqrt(np.mean(np.square(errors))))
    mae = float(np.mean(np.abs(errors)))
    max_abs_alpha = float(np.max(np.abs(errors)))
    return r_squared, rmse, mae, max_abs_alpha


def _build_result(
    *,
    estimator: EstimatorName,
    include_intercept: bool,
    beta_source: str,
    estimation_window: str,
    risk_prices: pd.Series,
    standard_errors: pd.Series,
    corrected_standard_errors: pd.Series,
    fitted: pd.Series,
    errors: pd.Series,
    observed: pd.Series,
    betas: pd.DataFrame,
    weighting_matrix: pd.DataFrame | None,
    regularization: float,
) -> CrossSectionResult:
    risk_prices = risk_prices.rename("risk_price")
    standard_errors = standard_errors.reindex(risk_prices.index).rename("standard_error")
    corrected_standard_errors = corrected_standard_errors.reindex(risk_prices.index).rename(
        "corrected_standard_error"
    )
    t_statistics = (risk_prices / standard_errors).rename("t_statistic")
    corrected_t_statistics = (risk_prices / corrected_standard_errors).rename(
        "corrected_t_statistic"
    )
    confidence_low = (risk_prices - 1.96 * corrected_standard_errors).rename(
        "confidence_interval_low"
    )
    confidence_high = (risk_prices + 1.96 * corrected_standard_errors).rename(
        "confidence_interval_high"
    )
    r_squared, rmse, mae, max_abs_alpha = _fit_statistics(observed, errors)
    return CrossSectionResult(
        risk_prices=risk_prices,
        standard_errors=standard_errors,
        t_statistics=t_statistics,
        pricing_errors=errors,
        fitted_mean_returns=fitted,
        r_squared=r_squared,
        rmse=rmse,
        mae=mae,
        corrected_standard_errors=corrected_standard_errors,
        corrected_t_statistics=corrected_t_statistics,
        confidence_interval_low=confidence_low,
        confidence_interval_high=confidence_high,
        max_abs_alpha=max_abs_alpha,
        estimator=estimator,
        include_intercept=include_intercept,
        beta_source=beta_source,
        estimation_window=estimation_window,
        weighting_matrix=weighting_matrix,
        regularization=regularization,
        weak_factor_warning=weak_factor_diagnostic(betas),
        n_assets=int(observed.shape[0]),
    )
