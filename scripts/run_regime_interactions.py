"""Test pooled regime-interaction beta stability, the pooled half of H3.

This script covers exactly one half of the registered H3 workflow: pooled
time-series regime interactions for **beta** stability, plus the exploratory
structural-break battery run on the same system. The regime-specific second
passes, the fitted-premium and pricing-error comparisons, and the TOST
equivalence intervals belong to the other half of the same confirmatory family
and are produced elsewhere.

The pooled design is what carries `pandemic_elb_qe`, `inflation_tightening` and
`post_tightening_easing`. Under the frozen eligibility floors in
`configs/regimes.yaml` those three regimes permit pooled regime-interaction
models only, so no regime-specific estimate of theirs exists anywhere else.

Design follows `research/statistical_protocol.md`, section "Structural Change":
a single omitted baseline category (`conventional_pre_elb`), interactions of the
market factor and the federal-funds innovation with `regime_primary`, joint Wald
tests on the interaction block, Holm adjustment inside the registered
`regime_stability` family, and boundary shifts of -3 and +3 months as declared
in `configs/regimes.yaml`.

The break battery is exploratory hypothesis E1 and is labelled as such in every
artifact it appears in. It neither confirms nor refutes H3.

Nothing in this script interprets a rejection. A significant regime interaction
is evidence of parameter instability and of nothing else; the protocol is
explicit that it does not identify a causal effect of monetary policy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2  # type: ignore[import-untyped]

from short_rate_anomaly_regimes.config import load_regime_config
from short_rate_anomaly_regimes.models.time_series import automatic_newey_west_lags
from short_rate_anomaly_regimes.regimes.calendar import (
    RegimeInterval,
    interval_from_months,
    label_regimes,
    shift_regime_boundaries,
)
from short_rate_anomaly_regimes.regimes.stability import (
    bai_perron_breaks,
    chow_test,
    classify_stability,
    cusum_test,
    estimate_regime_interactions,
    holm_adjust_tests,
    quandt_andrews_test,
    regime_interaction_wald_tests,
)

REGIME_PARQUET = Path("data/processed/regimes/monthly_regimes.parquet")
ELIGIBILITY_CSV = Path("artifacts/tables/regimes/regime_eligibility.csv")
REGIME_CONFIG = Path("configs/regimes.yaml")

WALD_CSV = Path("artifacts/tables/regimes/pooled_interaction_wald.csv")
BREAK_CSV = Path("artifacts/tables/regimes/break_tests.csv")
SENSITIVITY_CSV = Path("artifacts/tables/regimes/boundary_sensitivity.csv")
DIAGNOSTIC_JSON = Path("artifacts/diagnostics/h3_pooled_beta_stability.json")
PROVENANCE_JSON = Path("artifacts/provenance/regime_interactions.json")

RATE = "fedfunds"
MARKET_FACTOR = "RM"
RATE_FACTOR = "FFR_innovation"

#: research/statistical_protocol.md requires a single omitted baseline category.
OMITTED_REGIME = "conventional_pre_elb"

#: Equal-weighted portfolio of the test assets. Because every asset shares the
#: same regressors, its regression coefficients equal the pooled common-slope
#: estimator across the 70 assets, and its HAC covariance absorbs cross-asset
#: correlation. It is the joint counterpart of the per-asset tests.
AGGREGATE_ASSET = "equal_weighted_test_assets"

ALPHA = 0.05

#: The registered boundaries are known, so the Chow minimum only protects the
#: degrees of freedom of the shorter side. The final registered regime is 15
#: months long, which is what binds this constant.
CHOW_MIN_SEGMENT_MONTHS = 12

#: Unknown-break searches use the frozen minimum regime length from
#: configs/regimes.yaml (`minimum_regime_observations`).
UNKNOWN_BREAK_MIN_SEGMENT_MONTHS = 36
BAI_PERRON_MAX_BREAKS = 2

BOUNDARY_SHIFTS = (-3, 0, 3)

EXPLORATORY_NOTE = (
    "exploratory under hypothesis E1; not a member of the confirmatory "
    "regime_stability family and neither confirms nor refutes H3"
)


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file.

    Args:
        path: File to digest.

    Returns:
        Lowercase hexadecimal digest.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(series: pd.Series) -> dict[str, Any]:
    """Convert one result series into a string-keyed record.

    Args:
        series: Result series returned by a stability test.

    Returns:
        The same content keyed by string labels.
    """
    return {str(key): value for key, value in series.items()}


def load_regime_panel(path: Path) -> pd.DataFrame:
    """Load the monthly regime panel onto a month-start DatetimeIndex.

    The stability functions require a DatetimeIndex, while the panel stores
    `YYYY-MM` strings, so the month periods are converted with
    ``to_timestamp(how="start")``.

    Args:
        path: Parquet path of the labelled monthly regime panel.

    Returns:
        The panel indexed by month-start timestamps, without the `month` column.

    Raises:
        ValueError: If the panel has duplicate or non-contiguous months.
    """
    frame = pd.read_parquet(path)
    months = pd.PeriodIndex([pd.Period(str(value), freq="M") for value in frame["month"]], freq="M")
    if months.has_duplicates:
        raise ValueError("The regime panel has duplicate months")
    expected = pd.period_range(months[0], months[-1], freq="M")
    if list(months) != list(expected):
        raise ValueError("The regime panel has month gaps")
    return frame.drop(columns=["month"]).set_axis(months.to_timestamp(how="start"))


def asset_columns(panel: pd.DataFrame) -> list[str]:
    """List the registered test-asset return columns.

    Args:
        panel: Monthly regime panel.

    Returns:
        Sorted portfolio excess-return column names.
    """
    return sorted(
        column for column in panel.columns if str(column).startswith("portfolio_excess_return__")
    )


def build_system(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the response and regressor blocks of the pooled system.

    Args:
        panel: Monthly regime panel on a DatetimeIndex.

    Returns:
        The test-asset returns with the equal-weighted aggregate appended, and
        the two-factor regressor frame.
    """
    columns = asset_columns(panel)
    returns = panel[columns].astype(float).copy()
    returns[AGGREGATE_ASSET] = returns.mean(axis=1)
    factors = pd.DataFrame(
        {
            MARKET_FACTOR: panel["market_excess_return"].astype(float),
            RATE_FACTOR: panel[f"short_rate_innovation__{RATE}"].astype(float),
        },
        index=panel.index,
    )
    return returns, factors


def registered_intervals(config_path: Path, *, last_month: str) -> tuple[RegimeInterval, ...]:
    """Read the frozen primary regime intervals from configuration.

    Args:
        config_path: Path of `configs/regimes.yaml`.
        last_month: Month closing an open-ended final regime, as `YYYY-MM`.

    Returns:
        The registered primary intervals in configured order.
    """
    config = load_regime_config(config_path)
    return tuple(
        interval_from_months(
            regime.id,
            regime.start,
            last_month if regime.end == "latest_available" else regime.end,
        )
        for regime in config.regime_definition.regimes
    )


def shifted_regime_labels(
    index: pd.DatetimeIndex,
    intervals: tuple[RegimeInterval, ...],
    *,
    shift_months: int,
) -> pd.Series:
    """Relabel every month after shifting the internal regime boundaries.

    Args:
        index: Monthly DatetimeIndex to label.
        intervals: Registered primary regime intervals.
        shift_months: Signed month shift applied to internal boundaries.

    Returns:
        One regime label per month under the shifted calendar.
    """
    shifted = shift_regime_boundaries(intervals, shift_months=shift_months)
    return label_regimes(index, shifted)


def interaction_design(
    factors: pd.DataFrame,
    regimes: pd.Series,
    *,
    reference_regime: str,
) -> pd.DataFrame:
    """Rebuild the pooled regime-interaction design matrix.

    This mirrors the design that
    :func:`short_rate_anomaly_regimes.regimes.stability.estimate_regime_interactions`
    builds internally. It is rebuilt here only because a restriction on the rate
    beta alone needs the fitted covariance block, which the public estimator does
    not return. :func:`assert_design_agrees` re-checks the two against each other
    on every run, so the rebuild cannot silently diverge.

    Args:
        factors: Factor regressors on a monthly DatetimeIndex.
        regimes: Regime labels on the same index.
        reference_regime: The single omitted baseline category.

    Returns:
        Constant, factors, regime dummies, and factor-by-regime interactions.

    Raises:
        ValueError: If the reference regime is absent from the labels.
    """
    regime_values = pd.Series(regimes, index=factors.index, dtype="string")
    order = tuple(str(regime) for regime in regime_values.drop_duplicates())
    if reference_regime not in set(regime_values.dropna().astype(str)):
        raise ValueError(f"Unknown reference regime {reference_regime!r}")
    design = sm.add_constant(factors.astype(float), has_constant="add")
    for regime in order:
        if regime == reference_regime:
            continue
        dummy = (regime_values == regime).astype(float)
        design[f"regime_{regime}"] = dummy
        for factor in factors.columns:
            design[f"{factor}_x_regime_{regime}"] = factors[factor].astype(float) * dummy
    frame: pd.DataFrame = design.astype(float)
    return frame


def _align_system(returns: pd.DataFrame, factors: pd.DataFrame, regimes: pd.Series) -> pd.DataFrame:
    """Join returns, factors, and regime labels on complete months.

    Args:
        returns: Test-asset returns on a monthly DatetimeIndex.
        factors: Factor regressors on the same index.
        regimes: Regime labels on the same index.

    Returns:
        The inner-joined complete-case frame with a `regime` column.

    Raises:
        ValueError: If no complete month survives the join.
    """
    joined = returns.join(factors, how="inner").join(regimes.rename("regime"), how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations across returns, factors, and regimes")
    return joined


def _fit_hac(response: pd.Series, design: pd.DataFrame, *, hac_lags: int) -> Any:
    """Fit one OLS regression with a Newey-West covariance.

    Args:
        response: Dependent series.
        design: Design matrix including its own constant.
        hac_lags: Newey-West lag truncation.

    Returns:
        The fitted statsmodels results object.
    """
    return sm.OLS(response.astype(float), design.astype(float)).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": hac_lags, "use_correction": False},
    )


def _restriction_wald(model: Any, columns: list[str]) -> dict[str, float]:
    """Compute a joint Wald statistic for a block of zero restrictions.

    Args:
        model: Fitted regression results.
        columns: Parameter names restricted to zero.

    Returns:
        Statistic, chi-square p-value, degrees of freedom, and observations.
    """
    params = model.params.loc[columns].to_numpy(dtype=float)
    covariance = model.cov_params().loc[columns, columns].to_numpy(dtype=float)
    statistic = float(params.T @ np.linalg.pinv(covariance) @ params)
    return {
        "statistic": statistic,
        "p_value": float(chi2.sf(statistic, len(columns))),
        "df": float(len(columns)),
        "nobs": float(model.nobs),
    }


def interaction_wald_battery(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    regimes: pd.Series,
    *,
    hac_lags: int,
    reference_regime: str,
    rate_factor: str = RATE_FACTOR,
) -> pd.DataFrame:
    """Run the all-factor and rate-beta joint interaction Wald tests per asset.

    Two restrictions are tested on the same fitted model: that every
    factor-by-regime interaction is zero, and that every regime interaction on
    the rate beta alone is zero.

    Args:
        returns: Test-asset returns on a monthly DatetimeIndex.
        factors: Factor regressors on the same index.
        regimes: Regime labels on the same index.
        hac_lags: Newey-West lag truncation.
        reference_regime: The single omitted baseline category.
        rate_factor: Factor whose interactions form the rate-beta restriction.

    Returns:
        Two joint Wald rows per asset.

    Raises:
        ValueError: If the design carries no interaction column for `rate_factor`.
    """
    aligned = _align_system(returns, factors, regimes)
    design = interaction_design(
        aligned[list(factors.columns)],
        aligned["regime"],
        reference_regime=reference_regime,
    )
    all_interactions = [column for column in design.columns if "_x_regime_" in str(column)]
    rate_interactions = [
        column for column in all_interactions if str(column).startswith(f"{rate_factor}_x_regime_")
    ]
    if not rate_interactions:
        raise ValueError(f"No regime interaction columns for factor {rate_factor!r}")
    rows: list[dict[str, float | str]] = []
    for asset in returns.columns:
        model = _fit_hac(aligned[str(asset)], design, hac_lags=hac_lags)
        rows.append(
            {
                "asset": str(asset),
                "test": "joint_regime_factor_interactions",
                "restricted_parameters": float(len(all_interactions)),
                **_restriction_wald(model, all_interactions),
            }
        )
        rows.append(
            {
                "asset": str(asset),
                "test": "joint_rate_beta_regime_interactions",
                "restricted_parameters": float(len(rate_interactions)),
                **_restriction_wald(model, rate_interactions),
            }
        )
    return pd.DataFrame(rows)


def assert_design_agrees(battery: pd.DataFrame, module_tests: pd.DataFrame) -> float:
    """Check the rebuilt design against the published all-interaction Wald tests.

    Args:
        battery: Output of :func:`interaction_wald_battery`.
        module_tests: Output of
            :func:`short_rate_anomaly_regimes.regimes.stability.regime_interaction_wald_tests`.

    Returns:
        The largest absolute statistic deviation observed.

    Raises:
        ValueError: If any asset's statistic deviates by more than 1e-8 relative.
    """
    mine = (
        battery.loc[battery["test"] == "joint_regime_factor_interactions"]
        .set_index("asset")["statistic"]
        .astype(float)
    )
    theirs = module_tests.set_index("asset")["statistic"].astype(float)
    if sorted(mine.index) != sorted(theirs.index):
        raise ValueError("The rebuilt battery and the stability module disagree on the asset set")
    deviation = (mine - theirs.reindex(mine.index)).abs()
    scale = theirs.reindex(mine.index).abs().clip(lower=1.0)
    if float((deviation / scale).max()) > 1e-8:
        raise ValueError("The rebuilt interaction design diverges from the stability module")
    return float(deviation.max())


def rate_interaction_wide(coefficients: pd.DataFrame, *, rate_factor: str) -> pd.DataFrame:
    """Reshape the per-asset rate-beta interaction coefficients to one row per asset.

    Args:
        coefficients: Output of
            :func:`short_rate_anomaly_regimes.regimes.stability.estimate_regime_interactions`.
        rate_factor: Factor whose interaction coefficients are extracted.

    Returns:
        A frame indexed by asset with coefficient and t-statistic columns per regime.
    """
    prefix = f"{rate_factor}_x_regime_"
    rows = coefficients.loc[coefficients["parameter"].astype(str).str.startswith(prefix)].copy()
    rows["regime"] = rows["parameter"].astype(str).str.removeprefix(prefix)
    coefficient = rows.pivot(index="asset", columns="regime", values="coefficient").add_prefix(
        "rate_interaction_coefficient__"
    )
    t_statistic = rows.pivot(index="asset", columns="regime", values="t_statistic").add_prefix(
        "rate_interaction_t__"
    )
    wide: pd.DataFrame = coefficient.join(t_statistic)
    wide.columns.name = None
    return wide


def break_battery(
    response: pd.Series,
    regressors: pd.DataFrame,
    *,
    boundary_months: tuple[str, ...],
) -> pd.DataFrame:
    """Run the exploratory structural-break battery on the pooled system.

    Every row produced here is exploratory hypothesis E1. The battery is run on
    the equal-weighted aggregate of the test assets, which is the pooled system
    the interaction tests describe.

    Args:
        response: Aggregate excess return on a monthly DatetimeIndex.
        regressors: Factor regressors on the same index.
        boundary_months: Registered boundary months, each the closing month of an
            outgoing regime.

    Returns:
        One frame holding Chow, Quandt-Andrews, Bai-Perron, and CUSUM results.
    """
    rows: list[dict[str, Any]] = []
    for month in boundary_months:
        result = chow_test(
            response,
            regressors,
            break_month=month,
            min_segment_observations=CHOW_MIN_SEGMENT_MONTHS,
        )
        rows.append(
            {
                **_record(result),
                "break_type": "registered_boundary",
                "min_segment_observations": float(CHOW_MIN_SEGMENT_MONTHS),
            }
        )
    quandt = quandt_andrews_test(
        response,
        regressors,
        min_segment_observations=UNKNOWN_BREAK_MIN_SEGMENT_MONTHS,
    )
    rows.append(
        {
            **_record(quandt),
            "break_type": "estimated_unknown_break",
            "min_segment_observations": float(UNKNOWN_BREAK_MIN_SEGMENT_MONTHS),
        }
    )
    breaks = bai_perron_breaks(
        response,
        regressors,
        min_segment_observations=UNKNOWN_BREAK_MIN_SEGMENT_MONTHS,
        max_breaks=BAI_PERRON_MAX_BREAKS,
    )
    if breaks.empty:
        rows.append(
            {
                "test": "bai_perron_multiple_breaks",
                "break_type": "estimated_unknown_break",
                "min_segment_observations": float(UNKNOWN_BREAK_MIN_SEGMENT_MONTHS),
                "selected_breaks": 0.0,
            }
        )
    else:
        for row in breaks.to_dict(orient="records"):
            rows.append(
                {
                    "test": "bai_perron_multiple_breaks",
                    "break_month": str(row["break_month"]),
                    "break_number": float(row["break_number"]),
                    "criterion": float(row["criterion"]),
                    "break_type": "estimated_unknown_break",
                    "min_segment_observations": float(UNKNOWN_BREAK_MIN_SEGMENT_MONTHS),
                    "selected_breaks": float(len(breaks)),
                }
            )
    rows.append({**_record(cusum_test(response, regressors)), "break_type": "recursive_residuals"})
    table = pd.DataFrame(rows)
    table.insert(1, "scope", AGGREGATE_ASSET)
    table["evidence_class"] = "exploratory"
    table["hypothesis"] = "E1"
    table["multiplicity_family"] = "not_in_confirmatory_family"
    table["max_breaks_searched"] = float(BAI_PERRON_MAX_BREAKS)
    table["note"] = EXPLORATORY_NOTE
    table["replication_status"] = "documented_reconstruction"
    return table


def boundary_sensitivity(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    intervals: tuple[RegimeInterval, ...],
    *,
    hac_lags: int,
    shifts: tuple[int, ...] = BOUNDARY_SHIFTS,
) -> pd.DataFrame:
    """Repeat the pooled interaction Wald tests under shifted regime boundaries.

    Args:
        returns: Test-asset returns on a monthly DatetimeIndex.
        factors: Factor regressors on the same index.
        intervals: Registered primary regime intervals.
        hac_lags: Newey-West lag truncation.
        shifts: Signed month shifts applied to the internal boundaries.

    Returns:
        Holm-adjusted Wald rows stacked over shifts, each carrying the shift's
        registered stability verdict.
    """
    index = pd.DatetimeIndex(returns.index)
    frames: list[pd.DataFrame] = []
    for shift in shifts:
        labels = shifted_regime_labels(index, intervals, shift_months=shift)
        battery = interaction_wald_battery(
            returns,
            factors,
            labels,
            hac_lags=hac_lags,
            reference_regime=OMITTED_REGIME,
        )
        adjusted = holm_adjust_tests(battery)
        adjusted["significant_holm_5pct"] = adjusted["holm_p_value"].astype(float) <= ALPHA
        adjusted["shift_months"] = shift
        adjusted["boundary_rule"] = (
            "registered" if shift == 0 else f"registered_boundaries_shifted_{shift:+d}_months"
        )
        adjusted["verdict"] = classify_stability(adjusted, alpha=ALPHA).verdict
        frames.append(adjusted)
    table = pd.concat(frames, ignore_index=True)
    table["scope"] = np.where(
        table["asset"] == AGGREGATE_ASSET, "equal_weighted_aggregate", "asset"
    )
    table["evidence_class"] = "confirmatory"
    table["hypothesis"] = "H3"
    table["replication_status"] = "documented_reconstruction"
    return table


def _regime_summary(coefficients: pd.DataFrame, *, rate_factor: str) -> list[dict[str, Any]]:
    """Summarise the rate-beta interaction coefficients across the test assets.

    Args:
        coefficients: Output of
            :func:`short_rate_anomaly_regimes.regimes.stability.estimate_regime_interactions`.
        rate_factor: Factor whose interaction coefficients are summarised.

    Returns:
        One record per non-baseline regime.
    """
    prefix = f"{rate_factor}_x_regime_"
    rows = coefficients.loc[
        coefficients["parameter"].astype(str).str.startswith(prefix)
        & (coefficients["asset"] != AGGREGATE_ASSET)
    ].copy()
    rows["regime"] = rows["parameter"].astype(str).str.removeprefix(prefix)
    records: list[dict[str, Any]] = []
    for regime, frame in rows.groupby("regime"):
        records.append(
            {
                "regime": str(regime),
                "assets": len(frame),
                "mean_interaction_coefficient": float(frame["coefficient"].mean()),
                "median_interaction_coefficient": float(frame["coefficient"].median()),
                "min_interaction_coefficient": float(frame["coefficient"].min()),
                "max_interaction_coefficient": float(frame["coefficient"].max()),
                "assets_unadjusted_p_below_5pct": int((frame["p_value"] <= ALPHA).sum()),
            }
        )
    return records


def main() -> None:
    """Run the pooled interaction tests, the break battery, and the boundary shifts.

    Raises:
        ValueError: If the panel labels disagree with the frozen regime calendar,
            or if the rebuilt interaction design diverges from the stability module.
    """
    panel = load_regime_panel(REGIME_PARQUET)
    eligibility = pd.read_csv(ELIGIBILITY_CSV)
    assets = asset_columns(panel)
    returns, factors = build_system(panel)
    regimes = panel["regime_primary"].astype("string").rename("regime")
    index = pd.DatetimeIndex(panel.index)
    last_month = str(pd.Period(index[-1], freq="M"))
    intervals = registered_intervals(REGIME_CONFIG, last_month=last_month)

    registered_labels = label_regimes(index, intervals)
    if not registered_labels.astype(str).equals(regimes.astype(str)):
        raise ValueError("The panel regime labels disagree with the frozen regime calendar")

    hac_lags = automatic_newey_west_lags(len(panel))

    coefficients = estimate_regime_interactions(
        returns,
        factors,
        regimes,
        hac_lags=hac_lags,
        reference_regime=OMITTED_REGIME,
    )
    module_tests = regime_interaction_wald_tests(
        returns,
        factors,
        regimes,
        hac_lags=hac_lags,
        reference_regime=OMITTED_REGIME,
    )
    battery = interaction_wald_battery(
        returns,
        factors,
        regimes,
        hac_lags=hac_lags,
        reference_regime=OMITTED_REGIME,
    )
    max_deviation = assert_design_agrees(battery, module_tests)

    adjusted = holm_adjust_tests(battery)
    adjusted["significant_holm_5pct"] = adjusted["holm_p_value"].astype(float) <= ALPHA
    adjusted["significant_unadjusted_5pct"] = adjusted["p_value"].astype(float) <= ALPHA
    adjusted["scope"] = np.where(
        adjusted["asset"] == AGGREGATE_ASSET, "equal_weighted_aggregate", "asset"
    )
    adjusted["reference_regime"] = OMITTED_REGIME
    adjusted["hac_lags"] = hac_lags
    adjusted["evidence_class"] = "confirmatory"
    adjusted["hypothesis"] = "H3"
    adjusted["replication_status"] = "documented_reconstruction"
    wald_table = adjusted.merge(
        rate_interaction_wide(coefficients, rate_factor=RATE_FACTOR),
        left_on="asset",
        right_index=True,
        how="left",
    )
    conclusion = classify_stability(wald_table, alpha=ALPHA)

    aggregate_rate = wald_table.loc[
        (wald_table["asset"] == AGGREGATE_ASSET)
        & (wald_table["test"] == "joint_rate_beta_regime_interactions")
    ].iloc[0]
    aggregate_all = wald_table.loc[
        (wald_table["asset"] == AGGREGATE_ASSET)
        & (wald_table["test"] == "joint_regime_factor_interactions")
    ].iloc[0]
    per_asset = wald_table.loc[wald_table["asset"] != AGGREGATE_ASSET]
    rate_rows = per_asset.loc[per_asset["test"] == "joint_rate_beta_regime_interactions"]
    all_rows = per_asset.loc[per_asset["test"] == "joint_regime_factor_interactions"]

    boundary_months = tuple(str(interval.end) for interval in intervals[:-1])
    breaks = break_battery(
        returns[AGGREGATE_ASSET],
        factors,
        boundary_months=boundary_months,
    )
    sensitivity = boundary_sensitivity(returns, factors, intervals, hac_lags=hac_lags)

    registered_verdict = conclusion.verdict
    sensitivity_records: list[dict[str, Any]] = []
    for shift in BOUNDARY_SHIFTS:
        frame = sensitivity.loc[sensitivity["shift_months"] == shift]
        shift_rate = frame.loc[frame["test"] == "joint_rate_beta_regime_interactions"]
        shift_assets = shift_rate.loc[shift_rate["asset"] != AGGREGATE_ASSET]
        aggregate_row = shift_rate.loc[shift_rate["asset"] == AGGREGATE_ASSET].iloc[0]
        verdict = str(frame["verdict"].iloc[0])
        sensitivity_records.append(
            {
                "shift_months": shift,
                "verdict": verdict,
                "verdict_matches_registered_boundaries": verdict == registered_verdict,
                "assets_rate_beta_significant_holm": int(
                    shift_assets["significant_holm_5pct"].sum()
                ),
                "aggregate_rate_beta_statistic": float(aggregate_row["statistic"]),
                "aggregate_rate_beta_holm_p_value": float(aggregate_row["holm_p_value"]),
            }
        )
    conclusion_changed = any(
        not record["verdict_matches_registered_boundaries"] for record in sensitivity_records
    )

    for path in (WALD_CSV, BREAK_CSV, SENSITIVITY_CSV, DIAGNOSTIC_JSON, PROVENANCE_JSON):
        path.parent.mkdir(parents=True, exist_ok=True)
    wald_table.to_csv(WALD_CSV, index=False)
    breaks.to_csv(BREAK_CSV, index=False)
    sensitivity.to_csv(SENSITIVITY_CSV, index=False)

    pooled_only = eligibility.loc[
        ~eligibility["regime_specific_first_pass_permitted"].astype(bool), "regime_id"
    ].tolist()

    DIAGNOSTIC_JSON.write_text(
        json.dumps(
            {
                "hypothesis": "H3",
                "scope": "pooled_regime_interaction_beta_stability",
                "scope_note": (
                    "this artifact covers the pooled beta half of H3 only; the "
                    "regime-specific second passes, pricing-error and fit comparisons, "
                    "and the TOST equivalence intervals are separate members of the "
                    "same confirmatory family"
                ),
                "classification": conclusion.verdict,
                "significant_tests": list(conclusion.significant_tests),
                "interpretation_note": conclusion.interpretation_note,
                "sample": {
                    "months": len(panel),
                    "start": str(pd.Period(index[0], freq="M")),
                    "end": last_month,
                    "test_assets": len(assets),
                    "vintage": "current_throughout",
                },
                "specification": {
                    "response": "test-asset monthly excess return",
                    "regressors": [MARKET_FACTOR, RATE_FACTOR],
                    "interaction_variable": "regime_primary",
                    "omitted_baseline_regime": OMITTED_REGIME,
                    "hac_lags": hac_lags,
                    "alpha": ALPHA,
                    "aggregate_asset_note": (
                        "every asset shares the same regressors, so the equal-weighted "
                        "portfolio regression reproduces the pooled common-slope estimator "
                        "and its HAC covariance absorbs cross-asset correlation"
                    ),
                    "design_cross_check_max_absolute_deviation": max_deviation,
                },
                "per_asset_rate_beta_interactions": {
                    "assets": len(rate_rows),
                    "significant_unadjusted_5pct": int(
                        rate_rows["significant_unadjusted_5pct"].sum()
                    ),
                    "significant_holm_5pct": int(rate_rows["significant_holm_5pct"].sum()),
                    "min_p_value": float(rate_rows["p_value"].min()),
                    "median_p_value": float(rate_rows["p_value"].median()),
                    "min_holm_p_value": float(rate_rows["holm_p_value"].min()),
                    "median_holm_p_value": float(rate_rows["holm_p_value"].median()),
                    "median_statistic": float(rate_rows["statistic"].median()),
                    "restricted_parameters": int(rate_rows["restricted_parameters"].iloc[0]),
                },
                "per_asset_all_factor_interactions": {
                    "assets": len(all_rows),
                    "significant_unadjusted_5pct": int(
                        all_rows["significant_unadjusted_5pct"].sum()
                    ),
                    "significant_holm_5pct": int(all_rows["significant_holm_5pct"].sum()),
                    "min_holm_p_value": float(all_rows["holm_p_value"].min()),
                    "median_holm_p_value": float(all_rows["holm_p_value"].median()),
                    "restricted_parameters": int(all_rows["restricted_parameters"].iloc[0]),
                },
                "joint_equal_weighted_tests": {
                    "rate_beta_interactions": {
                        "statistic": float(aggregate_rate["statistic"]),
                        "df": float(aggregate_rate["df"]),
                        "p_value": float(aggregate_rate["p_value"]),
                        "holm_p_value": float(aggregate_rate["holm_p_value"]),
                    },
                    "all_factor_interactions": {
                        "statistic": float(aggregate_all["statistic"]),
                        "df": float(aggregate_all["df"]),
                        "p_value": float(aggregate_all["p_value"]),
                        "holm_p_value": float(aggregate_all["holm_p_value"]),
                    },
                },
                "rate_beta_interaction_by_regime": _regime_summary(
                    coefficients, rate_factor=RATE_FACTOR
                ),
                "boundary_sensitivity": {
                    "shifts_months": list(BOUNDARY_SHIFTS),
                    "results": sensitivity_records,
                    "any_conclusion_changed": conclusion_changed,
                },
                "exploratory_break_tests": {
                    "hypothesis": "E1",
                    "evidence_class": "exploratory",
                    "note": EXPLORATORY_NOTE,
                    "scope": AGGREGATE_ASSET,
                    "results": json.loads(
                        breaks.drop(columns=["note", "replication_status"]).to_json(
                            orient="records"
                        )
                    ),
                },
                "multiplicity": {
                    "family": "regime_stability",
                    "adjustment": "holm",
                    "tests_adjusted": len(wald_table),
                    "scope_note": (
                        "Holm is applied here across the pooled beta-stability tests. "
                        "The registered family also contains the fitted-premium, "
                        "pricing-error, and fit tests produced by the regime-specific "
                        "workflow; adjusting over the completed family can only raise "
                        "these adjusted p-values"
                    ),
                },
                "pooled_interaction_only_regimes": pooled_only,
                "pooled_interaction_only_note": (
                    "these regimes fall below the frozen floor for regime-specific "
                    "estimation, so the pooled interaction tests in this artifact are "
                    "the only registered evidence available for them"
                ),
                "replication_status": "documented_reconstruction",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_regime_interactions.py",
                "replication_status": "documented_reconstruction",
                "omitted_baseline_category": OMITTED_REGIME,
                "single_omitted_category": True,
                "interaction_variable": "regime_primary",
                "response": "portfolio_excess_return__<family>__decile_NN",
                "regressors": [MARKET_FACTOR, RATE_FACTOR],
                "inputs": {
                    path.as_posix(): _sha256(path)
                    for path in (REGIME_PARQUET, ELIGIBILITY_CSV, REGIME_CONFIG)
                },
                "outputs": {
                    path.as_posix(): _sha256(path)
                    for path in (WALD_CSV, BREAK_CSV, SENSITIVITY_CSV, DIAGNOSTIC_JSON)
                },
                "thresholds": {
                    "alpha": ALPHA,
                    "multiple_testing_adjustment": "holm",
                    "multiplicity_family": "regime_stability",
                    "hac_lags": hac_lags,
                    "chow_min_segment_months": CHOW_MIN_SEGMENT_MONTHS,
                    "unknown_break_min_segment_months": UNKNOWN_BREAK_MIN_SEGMENT_MONTHS,
                    "bai_perron_max_breaks": BAI_PERRON_MAX_BREAKS,
                    "boundary_shift_months": list(BOUNDARY_SHIFTS),
                },
                "registered_boundary_months": list(boundary_months),
                "evidence_classes": {
                    "pooled_interaction_wald": "confirmatory_H3",
                    "boundary_sensitivity": "confirmatory_H3_sensitivity",
                    "break_tests": "exploratory_E1",
                },
                "sources": [
                    "research/statistical_protocol.md#structural-change",
                    "research/inference_contract.md#multiplicity-families",
                    "research/regime_registry.csv",
                    "configs/regimes.yaml",
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(f"pooled regime interactions: {len(panel)} months, {len(assets)} test assets")
    print(f"  omitted baseline category : {OMITTED_REGIME}")
    print(f"  HAC lags                  : {hac_lags}")
    print(
        "  rate-beta interactions    : "
        f"{int(rate_rows['significant_holm_5pct'].sum())}/{len(rate_rows)} assets "
        f"significant after Holm (unadjusted {int(rate_rows['significant_unadjusted_5pct'].sum())})"
    )
    print(
        "  all-factor interactions   : "
        f"{int(all_rows['significant_holm_5pct'].sum())}/{len(all_rows)} assets "
        f"significant after Holm"
    )
    print(
        "  equal-weighted joint rate : "
        f"chi2({aggregate_rate['df']:.0f}) = {float(aggregate_rate['statistic']):.3f}, "
        f"p = {float(aggregate_rate['p_value']):.3e}, "
        f"Holm p = {float(aggregate_rate['holm_p_value']):.3e}"
    )
    print(f"\nH3 pooled beta stability: {conclusion.verdict}")
    print(f"  {conclusion.interpretation_note}")
    print("\nboundary sensitivity")
    for record in sensitivity_records:
        print(
            f"  shift {record['shift_months']:+d} months: verdict {record['verdict']}, "
            f"{record['assets_rate_beta_significant_holm']}/{len(rate_rows)} assets significant, "
            f"matches registered = {record['verdict_matches_registered_boundaries']}"
        )
    print(f"  any conclusion changed: {conclusion_changed}")
    print("\nexploratory break battery (hypothesis E1, not confirmatory)")
    print(
        breaks[["test", "break_month", "statistic", "p_value", "evidence_class"]]
        .fillna("")
        .to_string(index=False)
    )


if __name__ == "__main__":
    main()
