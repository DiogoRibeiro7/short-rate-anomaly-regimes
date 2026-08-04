"""Baseline AR(1) short-rate innovation reconstruction and published-target audit.

The reconstruction estimates ``r_t = a + rho * r_{t-1} + u_t`` on the frozen
baseline window under both admissible timing conventions, because the article
does not state which month supplies the first lagged rate. Every output is
labelled with its timing variant and its replication mode.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch
from statsmodels.stats.stattools import durbin_watson, jarque_bera

TimingVariant = Literal["within_window_lag", "pre_window_lag"]

#: A published statistic counts as recovered when it agrees with the article to
#: the number of decimals the article prints, that is within half of the last
#: printed increment. This is the ``published_rounding`` rule already registered
#: in ``research/table_target_manifest.csv``.
PUBLISHED_ROUNDING_TOLERANCE = {
    "intercept": 0.0005,
    "intercept_decimal_rate_units": 0.0005,
    "slope": 0.0005,
    "r_squared": 0.005,
    "t_intercept": 0.005,
    "t_slope": 0.005,
    "mean": 0.005,
    "standard_deviation": 0.005,
    "minimum": 0.005,
    "maximum": 0.005,
    "autocorrelation_1": 0.005,
}

#: Secondary relative band for t-ratios, which depend on the exact number of
#: regression observations and therefore on the unresolved timing convention.
T_RATIO_RELATIVE_TOLERANCE = 0.05


@dataclass(frozen=True, slots=True)
class ARReconstruction:
    """One AR(1) short-rate innovation reconstruction."""

    series_id: str
    replication_mode: str
    timing_variant: str
    window_start: str
    window_end: str
    regression_observations: int
    innovation_start: str
    innovation_end: str
    innovation_observations: int
    intercept: float
    intercept_decimal_rate_units: float
    intercept_standard_error: float
    intercept_t_ratio: float
    slope: float
    slope_standard_error: float
    slope_t_ratio: float
    r_squared: float
    residual_standard_error: float
    innovations: pd.Series = field(repr=False)
    descriptives: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, float] = field(default_factory=dict)
    unit_scale_audit: dict[str, float | str] = field(default_factory=dict)


def monthly_rate_from_freeze(series: pd.Series) -> pd.Series:
    """Convert a first-of-month stamped frozen series to a month-period series."""
    if not isinstance(series.index, pd.DatetimeIndex):
        raise TypeError("Frozen rate series must use a DatetimeIndex")
    periods = series.index.to_period("M")
    if periods.duplicated().any():
        raise ValueError("Monthly rate series has more than one observation in a month")
    reindexed = pd.Series(series.to_numpy(dtype=float), index=periods, name=series.name)
    return reindexed.sort_index()


def estimate_ar1_reconstruction(
    rate: pd.Series,
    *,
    series_id: str,
    replication_mode: str,
    timing_variant: TimingVariant,
    window_start: str,
    window_end: str,
) -> ARReconstruction:
    """Estimate the baseline AR(1) innovation equation under one timing convention.

    Args:
        rate: Monthly rate level indexed by ``pandas`` monthly periods.
        series_id: Identifier of the rate series.
        replication_mode: Replication label carried into every output.
        timing_variant: ``within_window_lag`` estimates on regressand months
            inside the window only, so the innovation starts one month after the
            window start. ``pre_window_lag`` draws the first lagged level from
            the month before the window, so the innovation covers the whole
            window.
        window_start: First month of the baseline window, ``YYYY-MM``.
        window_end: Last month of the baseline window, ``YYYY-MM``.

    Returns:
        The reconstruction record, including the residual series.

    Raises:
        ValueError: If the required months are unavailable or the window is empty.
    """
    start = pd.Period(window_start, freq="M")
    end = pd.Period(window_end, freq="M")
    levels = rate.dropna().sort_index()

    if timing_variant == "within_window_lag":
        regressand_start = start + 1
    elif timing_variant == "pre_window_lag":
        regressand_start = start
        if (start - 1) not in levels.index:
            raise ValueError(
                f"Pre-window lag requires the level for {start - 1}, which is unavailable"
            )
    else:
        raise ValueError(f"Unsupported timing variant {timing_variant!r}")

    target_index = pd.period_range(regressand_start, end, freq="M")
    missing = [str(period) for period in target_index if period not in levels.index]
    if missing:
        raise ValueError(f"Missing rate levels for {len(missing)} months, first {missing[0]}")
    lag_index = target_index - 1
    if any(period not in levels.index for period in lag_index):
        raise ValueError("Missing lagged rate levels inside the estimation window")

    target = levels.reindex(target_index)
    lagged = pd.Series(levels.reindex(lag_index).to_numpy(dtype=float), index=target_index)
    design = sm.add_constant(lagged.rename("lagged_rate").to_frame(), has_constant="add")
    fitted = sm.OLS(target.to_numpy(dtype=float), design.to_numpy(dtype=float)).fit()

    residuals = pd.Series(
        np.asarray(fitted.resid, dtype=float), index=target_index, name=f"{series_id}_innovation"
    )
    return ARReconstruction(
        series_id=series_id,
        replication_mode=replication_mode,
        timing_variant=timing_variant,
        window_start=window_start,
        window_end=window_end,
        regression_observations=int(fitted.nobs),
        innovation_start=str(target_index[0]),
        innovation_end=str(target_index[-1]),
        innovation_observations=len(residuals),
        intercept=float(fitted.params[0]),
        intercept_decimal_rate_units=float(fitted.params[0]) / 100.0,
        intercept_standard_error=float(fitted.bse[0]),
        intercept_t_ratio=float(fitted.tvalues[0]),
        slope=float(fitted.params[1]),
        slope_standard_error=float(fitted.bse[1]),
        slope_t_ratio=float(fitted.tvalues[1]),
        r_squared=float(fitted.rsquared),
        residual_standard_error=float(np.sqrt(fitted.mse_resid)),
        innovations=residuals,
        descriptives=innovation_descriptives(residuals),
        diagnostics=innovation_diagnostics(residuals, parameter_count=2),
        unit_scale_audit=unit_scale_audit(levels.reindex(target_index), residuals),
    )


def innovation_descriptives(innovations: pd.Series) -> dict[str, float]:
    """Compute the article Table 1 descriptive statistics for an innovation series."""
    clean = innovations.dropna().astype(float)
    return {
        "mean": float(clean.mean()),
        "standard_deviation": float(clean.std(ddof=1)),
        "minimum": float(clean.min()),
        "maximum": float(clean.max()),
        "autocorrelation_1": float(clean.autocorr(lag=1)),
        "observations": float(len(clean)),
    }


def innovation_diagnostics(innovations: pd.Series, *, parameter_count: int) -> dict[str, float]:
    """Compute residual and autocorrelation diagnostics for an innovation series."""
    clean = innovations.dropna().astype(float)
    values = clean.to_numpy(dtype=float)
    ljung = acorr_ljungbox(values, lags=[1, 6, 12, 24], return_df=True)
    arch = het_arch(values, nlags=12)
    normality = jarque_bera(values)
    diagnostics: dict[str, float] = {
        "durbin_watson": float(durbin_watson(values)),
        "arch_lm_statistic": float(arch[0]),
        "arch_lm_p_value": float(arch[1]),
        "jarque_bera_statistic": float(normality[0]),
        "jarque_bera_p_value": float(normality[1]),
        "skewness": float(normality[2]),
        "kurtosis": float(normality[3]),
        "residual_mean_absolute": float(np.abs(values).mean()),
        "residual_degrees_of_freedom": float(len(values) - parameter_count),
    }
    for lag in (1, 6, 12, 24):
        diagnostics[f"ljung_box_{lag}_statistic"] = float(ljung.loc[lag, "lb_stat"])
        diagnostics[f"ljung_box_{lag}_p_value"] = float(ljung.loc[lag, "lb_pvalue"])
    for lag in (1, 2, 3, 6, 12):
        diagnostics[f"autocorrelation_{lag}"] = float(clean.autocorr(lag=lag))
    return diagnostics


def unit_scale_audit(levels: pd.Series, innovations: pd.Series) -> dict[str, float | str]:
    """Audit the measurement scale of the rate level and its innovation.

    The article prints every Table 1 column under a percent heading while mixing
    monthly percent returns with rate-factor values, so the scale of the rate
    factor has to be established from the data rather than from the heading.
    """
    level_values = levels.dropna().astype(float)
    innovation_values = innovations.dropna().astype(float)
    maximum_level = float(level_values.max())
    if 1.0 < maximum_level <= 100.0:
        scale = "percent_per_annum"
    elif maximum_level <= 1.0:
        scale = "decimal_per_annum"
    else:
        scale = "unrecognised"
    return {
        "level_minimum": float(level_values.min()),
        "level_maximum": maximum_level,
        "level_mean": float(level_values.mean()),
        "inferred_level_scale": scale,
        "innovation_standard_deviation": float(innovation_values.std(ddof=1)),
        "innovation_standard_deviation_if_divided_by_twelve": float(
            innovation_values.std(ddof=1) / 12.0
        ),
        "innovation_standard_deviation_if_divided_by_hundred": float(
            innovation_values.std(ddof=1) / 100.0
        ),
        "innovation_units": (
            "annualized percentage points of the rate level; identical to the "
            "level units because the AR(1) residual is a difference of levels"
        ),
        "article_intercept_display_units": (
            "decimal rate units; the article prints the AR intercept as 0.000 while "
            "printing Table 1 innovation statistics in percent, so the intercept must "
            "be divided by 100 before it is compared with the published value. The "
            "slope, both t-ratios, and R-squared are scale invariant and require no "
            "conversion."
        ),
    }


#: Published statistic name mapped to the reconstructed attribute it must be
#: compared against, together with the units of that comparison.
#:
#: The article prints the AR intercept in decimal rate units while printing the
#: Table 1 innovation statistics in percent, so a published ``intercept`` target
#: must be compared against the reconstructed intercept expressed in decimal rate
#: units. Comparing it against the percentage-point estimate would fail for every
#: variant purely because of the unit convention. Every other statistic is
#: compared in its own native units, and the slope, both t-ratios, and R-squared
#: are scale invariant.
PUBLISHED_STATISTIC_COMPARISON: dict[str, tuple[str, str]] = {
    "intercept": ("intercept_decimal_rate_units", "decimal_rate_units"),
    "intercept_decimal_rate_units": ("intercept_decimal_rate_units", "decimal_rate_units"),
    "slope": ("slope", "dimensionless"),
    "t_intercept": ("t_intercept", "dimensionless"),
    "t_slope": ("t_slope", "dimensionless"),
    "r_squared": ("r_squared", "dimensionless"),
    "mean": ("mean", "annualized_percentage_points"),
    "standard_deviation": ("standard_deviation", "annualized_percentage_points"),
    "minimum": ("minimum", "annualized_percentage_points"),
    "maximum": ("maximum", "annualized_percentage_points"),
    "autocorrelation_1": ("autocorrelation_1", "dimensionless"),
}

#: Statistics that decide the coefficient layer of an R1a classification.
COEFFICIENT_STATISTICS = frozenset(
    {"intercept", "intercept_decimal_rate_units", "slope", "r_squared"}
)

#: Statistics that decide the descriptive layer of an R1a classification.
DESCRIPTIVE_STATISTICS = frozenset(
    {"mean", "standard_deviation", "minimum", "maximum", "autocorrelation_1"}
)


def compare_with_published(
    reconstruction: ARReconstruction,
    published: dict[str, float],
) -> pd.DataFrame:
    """Compare reconstructed statistics with the article's published values.

    Each published statistic is compared against the reconstructed quantity named
    in :data:`PUBLISHED_STATISTIC_COMPARISON`, in the units recorded there. The
    emitted frame records both the value actually compared and, where the two
    differ, the same estimate in annualized percentage points, so the unit
    conversion is visible rather than implicit.

    Args:
        reconstruction: The estimated AR(1) reconstruction.
        published: Published statistic names mapped to their printed values.

    Returns:
        One row per published statistic that the reconstruction can supply.

    Raises:
        KeyError: If a published statistic has no registered comparison rule.
    """
    computed: dict[str, float] = {
        "intercept": reconstruction.intercept,
        "intercept_decimal_rate_units": reconstruction.intercept_decimal_rate_units,
        "slope": reconstruction.slope,
        "t_intercept": reconstruction.intercept_t_ratio,
        "t_slope": reconstruction.slope_t_ratio,
        "r_squared": reconstruction.r_squared,
        **{
            key: float(value)
            for key, value in reconstruction.descriptives.items()
            if key in PUBLISHED_STATISTIC_COMPARISON
        },
    }
    records = []
    for statistic, published_value in published.items():
        if statistic not in PUBLISHED_STATISTIC_COMPARISON:
            continue
        computed_key, comparison_units = PUBLISHED_STATISTIC_COMPARISON[statistic]
        if computed_key not in computed:
            continue
        value = float(computed[computed_key])
        difference = value - published_value
        tolerance = PUBLISHED_ROUNDING_TOLERANCE[statistic]
        relative_ok = (
            abs(difference) <= T_RATIO_RELATIVE_TOLERANCE * abs(published_value)
            if statistic in {"t_intercept", "t_slope"} and published_value != 0.0
            else None
        )
        records.append(
            {
                "series_id": reconstruction.series_id,
                "replication_mode": reconstruction.replication_mode,
                "timing_variant": reconstruction.timing_variant,
                "statistic": statistic,
                "compared_attribute": computed_key,
                "comparison_units": comparison_units,
                "published_value": published_value,
                "reconstructed_value": value,
                "reconstructed_value_percentage_points": (
                    reconstruction.intercept if computed_key.startswith("intercept") else value
                ),
                "difference": difference,
                "absolute_difference": abs(difference),
                "published_rounding_tolerance": tolerance,
                "within_published_rounding": bool(abs(difference) <= tolerance),
                "within_relative_t_ratio_band": relative_ok,
            }
        )
    return pd.DataFrame.from_records(records)


def classify_replication_target(
    comparison: pd.DataFrame,
    *,
    replication_mode: str,
    exact_input_available: bool,
) -> str:
    """Classify one R1a rate-series target from its published-target comparison.

    A documented reconstruction can never be classified as exact replication, no
    matter how closely it matches, because the article does not identify the
    source file it used.

    An empty layer never counts as a match. A frame carrying no coefficient rows
    is treated as unmatched rather than vacuously true, so a comparison that
    silently dropped its coefficients cannot earn a reproduction label.

    Args:
        comparison: Output of :func:`compare_with_published`.
        replication_mode: Replication label carried by the reconstruction.
        exact_input_available: Whether the article identifies the source file.

    Returns:
        The classification string for this rate-series target.
    """
    if comparison.empty:
        return "not_attempted"
    coefficient_rows = comparison[comparison["statistic"].isin(COEFFICIENT_STATISTICS)]
    coefficients_match = (
        bool(coefficient_rows["within_published_rounding"].all())
        if not coefficient_rows.empty
        else False
    )
    descriptive_rows = comparison[comparison["statistic"].isin(DESCRIPTIVE_STATISTICS)]
    descriptives_match = (
        bool(descriptive_rows["within_published_rounding"].all())
        if not descriptive_rows.empty
        else False
    )
    t_ratio_rows = comparison[comparison["statistic"].isin({"t_intercept", "t_slope"})]
    t_ratios_match = (
        bool(t_ratio_rows["within_relative_t_ratio_band"].astype("boolean").fillna(False).all())
        if not t_ratio_rows.empty
        else False
    )
    coefficients_match = coefficients_match and t_ratios_match
    if not exact_input_available:
        if coefficients_match and descriptives_match:
            return "approximately_reproduced_under_documented_reconstruction"
        if coefficients_match:
            return "approximately_reproduced_coefficients_only_under_documented_reconstruction"
        return "not_reproduced_under_documented_reconstruction_exact_input_missing"
    if coefficients_match and descriptives_match:
        return "reproduced"
    if coefficients_match:
        return "approximately_reproduced"
    return "contradicted"
