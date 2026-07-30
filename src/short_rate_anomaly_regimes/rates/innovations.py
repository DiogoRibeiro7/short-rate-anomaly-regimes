"""Short-rate innovation estimators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, SupportsFloat, cast

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox, breaks_cusumolsresid, het_arch

from short_rate_anomaly_regimes.types import RateInnovationResult


@dataclass(frozen=True, slots=True)
class ARInnovationConfig:
    """Configuration for a univariate autoregressive innovation model."""

    lags: int = 1
    include_intercept: bool = True
    standardize: bool = False


DEFAULT_AR_INNOVATION_CONFIG = ARInnovationConfig()

RateUnit = Literal["percent", "decimal", "basis_points"]


@dataclass(frozen=True, slots=True)
class NamedRateFactor:
    """A named short-rate factor and its model output."""

    name: str
    method: str
    result: RateInnovationResult


@dataclass(frozen=True, slots=True)
class FactorOutputPaths:
    """Paths written by the short-rate output writer."""

    panel_parquet: str
    parameters_json: str
    diagnostics_json: str
    descriptives_csv: str
    descriptives_tex: str
    correlations_csv: str


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


def convert_rate_units(
    rate: pd.Series, *, source_unit: RateUnit, target_unit: RateUnit
) -> pd.Series:
    """Convert rate levels while preserving the original index and name."""
    if source_unit == target_unit:
        return rate.astype(float).copy()
    decimal = rate.astype(float)
    if source_unit == "percent":
        decimal = decimal / 100.0
    elif source_unit == "basis_points":
        decimal = decimal / 10_000.0
    elif source_unit != "decimal":
        raise ValueError(f"Unsupported source unit: {source_unit}")

    if target_unit == "decimal":
        converted = decimal
    elif target_unit == "percent":
        converted = decimal * 100.0
    elif target_unit == "basis_points":
        converted = decimal * 10_000.0
    else:
        raise ValueError(f"Unsupported target unit: {target_unit}")
    converted.name = rate.name
    return converted


def prepare_rate_columns(
    frame: pd.DataFrame,
    *,
    date_column: str,
    value_column: str,
    rate_id: str,
    source_unit: RateUnit,
    transformed_unit: RateUnit = "percent",
) -> pd.DataFrame:
    """Create explicit source and transformed monthly-rate columns."""
    if date_column not in frame.columns:
        raise ValueError(f"Missing date column {date_column!r}")
    if value_column not in frame.columns:
        raise ValueError(f"Missing value column {value_column!r}")
    dates = pd.to_datetime(frame[date_column], errors="raise")
    if dates.duplicated().any():
        raise ValueError("Rate series contains duplicate dates")
    source = pd.Series(frame[value_column].to_numpy(dtype=float), index=dates, name=value_column)
    source = source.sort_index()
    transformed = convert_rate_units(
        source,
        source_unit=source_unit,
        target_unit=transformed_unit,
    )
    return pd.DataFrame(
        {
            f"{rate_id}_{source_unit}": source,
            f"{rate_id}_{transformed_unit}": transformed,
        }
    )


def build_named_ar_factor(
    rate: pd.Series,
    *,
    rate_name: str,
    method: Literal["ar1", "ar2"],
    standardize: bool = False,
) -> NamedRateFactor:
    """Estimate a named AR short-rate innovation factor."""
    lags = {"ar1": 1, "ar2": 2}[method]
    result = estimate_ar_innovation(
        rate,
        config=ARInnovationConfig(lags=lags, include_intercept=True, standardize=standardize),
    )
    innovation_name = f"{rate_name}_{method}_innovation"
    fitted_name = f"{rate_name}_{method}_fitted"
    return NamedRateFactor(
        name=innovation_name,
        method=method,
        result=RateInnovationResult(
            innovations=result.innovations.rename(innovation_name),
            fitted_values=result.fitted_values.rename(fitted_name),
            parameters=result.parameters,
            diagnostics=result.diagnostics,
        ),
    )


def build_first_difference_factor(rate: pd.Series, *, rate_name: str) -> pd.Series:
    """Construct the first-difference robustness factor from Appendix Table A.2."""
    if not isinstance(rate.index, pd.DatetimeIndex):
        raise TypeError("Rate series must use a DatetimeIndex")
    factor = rate.astype(float).sort_index().diff().dropna()
    return factor.rename(f"{rate_name}_first_difference_innovation")


def build_local_level_factor(rate: pd.Series, *, rate_name: str) -> pd.Series:
    """Construct a separate local-level state-space innovation factor."""
    if not isinstance(rate.index, pd.DatetimeIndex):
        raise TypeError("Rate series must use a DatetimeIndex")
    clean = rate.astype(float).dropna().sort_index()
    if len(clean) < 8:
        raise ValueError("At least 8 observations are required for a local-level factor")
    model = sm.tsa.UnobservedComponents(clean, level="local level").fit(disp=False)
    errors = pd.Series(
        np.asarray(model.filter_results.forecasts_error[0], dtype=float),
        index=clean.index,
        name=f"{rate_name}_local_level_innovation",
    )
    return errors.dropna()


def aggregate_identified_surprises(
    surprises: pd.DataFrame,
    *,
    date_column: str,
    value_column: str,
    factor_name: str,
) -> pd.Series:
    """Aggregate event-level identified surprises to monthly factors without look-ahead."""
    if date_column not in surprises.columns:
        raise ValueError(f"Missing date column {date_column!r}")
    if value_column not in surprises.columns:
        raise ValueError(f"Missing value column {value_column!r}")
    frame = surprises.copy()
    frame[date_column] = pd.to_datetime(frame[date_column], errors="raise")
    periods = frame[date_column].dt.to_period("M")
    monthly = frame.groupby(periods, sort=True)[value_column].sum()
    monthly.index = pd.PeriodIndex(monthly.index).to_timestamp(how="end").normalize()
    return monthly.astype(float).rename(factor_name)


def combine_named_factors(factors: list[NamedRateFactor]) -> pd.DataFrame:
    """Combine named factor innovations into one monthly panel."""
    if not factors:
        raise ValueError("At least one factor is required")
    return pd.concat([factor.result.innovations for factor in factors], axis=1).dropna()


def align_market_rate_and_rf(
    *,
    market_excess_return: pd.Series,
    risk_free_return: pd.Series,
    rate_factors: pd.DataFrame,
) -> pd.DataFrame:
    """Align market, risk-free, and rate factors by same-month timestamps."""
    inputs = [market_excess_return, risk_free_return, *[rate_factors[col] for col in rate_factors]]
    if any(not isinstance(item.index, pd.DatetimeIndex) for item in inputs):
        raise TypeError("All aligned factor inputs must use a DatetimeIndex")
    if any(item.index.has_duplicates for item in inputs):
        raise ValueError("Aligned factor panel contains duplicate timestamps")
    aligned = pd.concat(
        [
            market_excess_return.rename("market_excess_return"),
            risk_free_return.rename("risk_free_return"),
            rate_factors,
        ],
        axis=1,
        join="inner",
    ).sort_index()
    if aligned.empty:
        raise ValueError("No common same-month factor observations")
    return aligned.dropna()


def factor_descriptive_statistics(factors: pd.DataFrame) -> pd.DataFrame:
    """Compute article-style factor descriptive statistics."""
    if factors.empty:
        raise ValueError("Cannot describe an empty factor panel")
    return pd.DataFrame(
        {
            "mean": factors.mean(),
            "standard_deviation": factors.std(ddof=1),
            "minimum": factors.min(),
            "maximum": factors.max(),
            "autocorrelation_1": factors.apply(lambda series: series.autocorr(lag=1)),
            "observations": factors.count().astype(float),
        }
    )


def factor_correlations(factors: pd.DataFrame) -> pd.DataFrame:
    """Compute pairwise factor correlations."""
    if factors.shape[1] < 2:
        raise ValueError("At least two factors are required for correlations")
    return factors.corr()


def innovation_diagnostics(
    innovations: pd.Series,
    *,
    parameter_count: int,
    ljung_box_lags: tuple[int, ...] = (6, 12),
    largest_residuals: int = 5,
) -> dict[str, object]:
    """Compute residual diagnostics for a short-rate innovation series."""
    clean = innovations.astype(float).dropna()
    if len(clean) <= max(ljung_box_lags):
        raise ValueError("Not enough observations for requested diagnostics")
    ljung_box = acorr_ljungbox(clean, lags=list(ljung_box_lags), return_df=True)
    arch_lm = het_arch(clean, nlags=min(12, len(clean) // 4))
    cusum = breaks_cusumolsresid(clean, ddof=parameter_count)
    residual_std = float(clean.std(ddof=1))
    largest = clean.abs().sort_values(ascending=False).head(largest_residuals)
    return {
        "ljung_box": {
            str(int(lag)): {
                "statistic": float(ljung_box.loc[lag, "lb_stat"]),
                "p_value": float(ljung_box.loc[lag, "lb_pvalue"]),
            }
            for lag in ljung_box.index
        },
        "arch_lm": {
            "statistic": float(arch_lm[0]),
            "p_value": float(arch_lm[1]),
        },
        "cusum": {
            "statistic": float(cusum[0]),
            "p_value": float(cusum[1]),
        },
        "largest_absolute_residual_months": {
            timestamp.strftime("%Y-%m"): float(clean.loc[timestamp]) for timestamp in largest.index
        },
        "maximum_absolute_standardized_residual": float(largest.iloc[0] / residual_std),
    }


def recursive_ar_coefficients(
    rate: pd.Series,
    *,
    min_observations: int,
    config: ARInnovationConfig = DEFAULT_AR_INNOVATION_CONFIG,
) -> pd.DataFrame:
    """Estimate expanding-window AR coefficients for recursive diagnostic plots."""
    clean = rate.astype(float).dropna().sort_index()
    if min_observations <= config.lags + 2:
        raise ValueError("min_observations must exceed lag count plus two observations")
    if len(clean) < min_observations:
        raise ValueError("Not enough observations for recursive coefficients")
    rows: list[pd.Series] = []
    for end in range(min_observations, len(clean) + 1):
        result = estimate_ar_innovation(clean.iloc[:end], config=config)
        row = result.parameters.copy()
        row.name = clean.index[end - 1]
        rows.append(row)
    return pd.DataFrame(rows)


def compare_article_targets(
    statistics: pd.DataFrame,
    targets: dict[tuple[str, str], float],
    *,
    tolerance: float,
) -> pd.DataFrame:
    """Compare computed factor statistics with frozen article targets."""
    records: list[dict[str, object]] = []
    for (factor_name, statistic_name), published_value in targets.items():
        replicated_value = float(cast(SupportsFloat, statistics.loc[factor_name, statistic_name]))
        absolute_difference = abs(replicated_value - published_value)
        records.append(
            {
                "factor": factor_name,
                "statistic": statistic_name,
                "published_value": published_value,
                "replicated_value": replicated_value,
                "absolute_difference": absolute_difference,
                "within_tolerance": absolute_difference <= tolerance,
            }
        )
    return pd.DataFrame.from_records(records)


def write_factor_outputs(
    *,
    output_root: Path,
    namespace: str,
    factor_panel: pd.DataFrame,
    parameters: pd.DataFrame,
    diagnostics: dict[str, object],
) -> FactorOutputPaths:
    """Write short-rate factor outputs in the declared artifact formats."""
    panel_path = output_root / "data" / "processed" / "factors" / f"{namespace}.parquet"
    parameter_path = (
        output_root / "artifacts" / "diagnostics" / "rates" / f"{namespace}_parameters.json"
    )
    diagnostic_path = output_root / "artifacts" / "diagnostics" / "rates" / f"{namespace}.json"
    descriptive_path = output_root / "artifacts" / "tables" / "factors" / f"{namespace}.csv"
    latex_path = output_root / "artifacts" / "tables" / "factors" / f"{namespace}.tex"
    correlation_path = (
        output_root / "artifacts" / "tables" / "factors" / f"{namespace}_correlations.csv"
    )
    descriptives = factor_descriptive_statistics(factor_panel)
    correlations = factor_correlations(factor_panel)
    for path in [
        panel_path,
        parameter_path,
        diagnostic_path,
        descriptive_path,
        latex_path,
        correlation_path,
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
    factor_panel.to_parquet(panel_path)
    parameter_path.write_text(parameters.to_json(indent=2), encoding="utf-8")
    diagnostic_path.write_text(json.dumps(diagnostics, indent=2, sort_keys=True), encoding="utf-8")
    descriptives.to_csv(descriptive_path)
    latex_path.write_text(descriptives.to_latex(float_format="%.6f"), encoding="utf-8")
    correlations.to_csv(correlation_path)
    return FactorOutputPaths(
        panel_parquet=str(panel_path),
        parameters_json=str(parameter_path),
        diagnostics_json=str(diagnostic_path),
        descriptives_csv=str(descriptive_path),
        descriptives_tex=str(latex_path),
        correlations_csv=str(correlation_path),
    )
