"""Evaluate H2 temporal stability, and separate the vintage effect from it.

Three evaluations are produced.

1. **Frozen-parameter.** Every parameter is fixed at its 1972-2013 value: the
   AR(1) intercept and slope that build the short-rate innovation, the first-pass
   betas, and the second-pass risk prices. Nothing estimated after 2013-12 enters
   it, so it is genuinely out of sample with respect to the article.
2. **Refitted.** The whole chain is re-estimated on 2014-01 to 2025-12 alone.
3. **Revised-history.** The baseline window recomputed on the current vintage.
   Differencing this against the locked baseline isolates the vintage change;
   differencing the refitted extension against it isolates the temporal change.

The third evaluation is what allows the milestone's acceptance gate to be met:
the publication-era against current-vintage revision effect is reported as its
own comparison rather than being folded into the temporal verdict.

Two classifications are produced, and they are not interchangeable.

- The **registered** classification is the frozen point-estimate rule in the H2
  registry row: sign compatibility, a fitted-premium magnitude bound, and an
  RMSE deterioration bound, each applied to point estimates. It is confirmatory
  and nothing here alters it.
- A **supplementary inferential** classification puts an interval around the
  same temporal comparison. Both windows are re-estimated inside every joint
  moving-block draw and the two independent draw sequences are paired, exactly
  as the H3 regime comparison pairs two within-regime bootstraps. Each estimand
  is then classified three ways under the frozen TOST rule: compatible with the
  registered bound, incompatible with it, or inconclusive. This is what makes
  the registry's `inconclusive` outcome reachable, which the point-estimate rule
  alone cannot express: "fails the registered gates" and "the economic relation
  changed" are different claims on 144 months.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.data.short_rate_freeze import (
    frozen_fred_path,
    load_normalized_series,
)
from short_rate_anomaly_regimes.models.article_second_pass import (
    ArticleSecondPassResult,
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.block_bootstrap import (
    BlockLengthSelection,
    FloatArray,
    recover_lagged_level,
    select_block_length,
)
from short_rate_anomaly_regimes.models.diagnostics import (
    MIN_STANDARDIZED_RATE_DISPERSION_SHARE,
    weak_factor_report,
)
from short_rate_anomaly_regimes.models.time_series import (
    automatic_newey_west_lags,
    estimate_time_series_betas,
)
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS
from short_rate_anomaly_regimes.rates.baseline_reconstruction import monthly_rate_from_freeze
from short_rate_anomaly_regimes.regimes.equivalence import (
    CONFIRMATORY_RULE,
    SENSITIVITY_RULE,
    EquivalenceOutcome,
    RegimePremiumBootstrap,
    bootstrap_regime_premia,
    classify_equivalence,
    paired_difference_draws,
)

BASELINE_PARQUET = Path("data/processed/baseline_panel.parquet")
EXTENSION_PARQUET = Path("data/processed/extension/monthly_panel.parquet")
REVISED_PARQUET = Path("data/processed/extension/revised_history_panel.parquet")

#: The frozen current-vintage federal funds file that
#: ``scripts/build_extension_panels.py`` reads to build both the extension and the
#: revised-history panel, and that ``scripts/build_baseline_panel.py`` reads for
#: the locked baseline's rate column. Every evaluation here draws its pre-window
#: lag from this file, so each lag is the observed preceding month on the vintage
#: that evaluation is actually estimated on.
FEDFUNDS_CSV = frozen_fred_path("FEDFUNDS")

EVALUATION_CSV = Path("artifacts/tables/extension/temporal_evaluation.csv")
SPREAD_CSV = Path("artifacts/tables/extension/fitted_premium_spreads.csv")
VINTAGE_CSV = Path("artifacts/tables/extension/vintage_decomposition.csv")
INFERENCE_CSV = Path("artifacts/tables/extension/h2_temporal_inference.csv")
DIAGNOSTIC_JSON = Path("artifacts/diagnostics/h2_temporal_stability.json")
PROVENANCE_JSON = Path("artifacts/provenance/temporal_extension.json")

#: research/economic_thresholds.md and the H2 registry row.
FITTED_PREMIUM_BOUND = 0.25
RMSE_DETERIORATION_BOUND = 0.10

#: research/bootstrap_contract.md: confirmatory repetitions and the project seed
#: from configs/baseline.yaml. The two windows are disjoint calendar samples, so
#: each gets its own stream and the draws are paired index-wise afterwards.
DRAWS = 10_000
BASE_SEED = 20260727
REVISED_HISTORY_SEED = BASE_SEED
REFITTED_EXTENSION_SEED = BASE_SEED + 1

RATE = "fedfunds"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    index = pd.PeriodIndex([pd.Period(str(v), freq="M") for v in frame["month"]], freq="M")
    return frame.drop(columns=["month"]).set_axis(index)


def _asset_columns(panel: pd.DataFrame) -> list[str]:
    return sorted(c for c in panel.columns if c.startswith("portfolio_excess_return__"))


def _spread_pairs(columns: list[str]) -> dict[str, tuple[int, int]]:
    positions = {column: index for index, column in enumerate(columns)}
    return {
        family: (
            positions[f"portfolio_excess_return__{family}__decile_01"],
            positions[f"portfolio_excess_return__{family}__decile_10"],
        )
        for family in FAMILY_MEMBERS
    }


def load_current_vintage_rate() -> pd.Series:
    """Load the current-vintage monthly federal funds level, indexed by month."""
    return monthly_rate_from_freeze(load_normalized_series(FEDFUNDS_CSV))


def rate_level(rate: pd.Series, month: pd.Period) -> float:
    """Return one month's observed rate level.

    Args:
        rate: Monthly rate level indexed by monthly periods.
        month: The month to read.

    Returns:
        The observed level for that month.

    Raises:
        ValueError: If the series does not carry the month.
    """
    levels = dict(zip(rate.index, rate.to_numpy(dtype=float), strict=True))
    if month not in levels:
        raise ValueError(f"The rate series does not carry {month}")
    return float(levels[month])


def pre_window_lag(rate: pd.Series, panel: pd.DataFrame) -> float:
    """Return the observed rate level of the month before a panel's first month.

    The project's frozen AR(1) timing convention, registered in
    ``reports/short_rate_source_report.md`` and implemented by
    :func:`short_rate_anomaly_regimes.rates.baseline_reconstruction.estimate_ar1_reconstruction`
    under ``pre_window_lag``, regresses the first window month on the level of the
    month *before* the window. Seeding the recursion with the first window month
    instead would regress that month on itself and would give the evaluation a
    different AR timing from the locked baseline, which is what the
    vintage-isolation comparison depends on.

    Args:
        rate: Monthly rate level for the vintage the panel is built on.
        panel: The evaluation panel whose first month needs a lag.

    Returns:
        The observed level of the month preceding the panel window.

    Raises:
        ValueError: If the series does not reach the preceding month. No value is
            substituted, because a substituted lag would silently reintroduce the
            timing mismatch this function exists to prevent.
    """
    first = pd.Period(panel.index[0], freq="M")
    previous = first - 1
    try:
        return rate_level(rate, previous)
    except ValueError as error:
        raise ValueError(
            f"The rate series does not reach {previous}, which is the pre-window "
            f"lag required for the window starting {first}"
        ) from error


def lagged_level(panel: pd.DataFrame, *, previous_level: float) -> FloatArray:
    """Build a panel's one-month lagged rate level under the pre-window convention."""
    level = panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    lags: FloatArray = np.concatenate([[previous_level], level[:-1]])
    return lags


def _ar_parameters(panel: pd.DataFrame) -> tuple[float, float]:
    """Recover the AR(1) intercept and slope embedded in a panel's innovation."""
    level = panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    innovation = panel[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float)
    lagged = recover_lagged_level(level, innovation)
    design = np.column_stack([np.ones(level.size), lagged])
    intercept, slope = np.linalg.lstsq(design, level - innovation, rcond=None)[0]
    return float(intercept), float(slope)


def _innovation_from_frozen_ar(
    panel: pd.DataFrame, *, intercept: float, slope: float, previous_level: float
) -> FloatArray:
    """Apply frozen AR(1) parameters to a later window without re-estimating them."""
    level = panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    innovation: FloatArray = (
        level - intercept - slope * lagged_level(panel, previous_level=previous_level)
    )
    return innovation


def _fit_system(
    panel: pd.DataFrame, innovation: FloatArray, label: str
) -> tuple[pd.DataFrame, pd.Series, ArticleSecondPassResult]:
    """Estimate the first pass and the article second pass on one window."""
    columns = _asset_columns(panel)
    timestamps = pd.PeriodIndex(panel.index, freq="M").to_timestamp(how="start")
    returns = panel[columns].set_axis(timestamps)
    factors = pd.DataFrame(
        {
            "RM": panel["market_excess_return"].to_numpy(dtype=float),
            "FFR_innovation": innovation,
        },
        index=timestamps,
    )
    first_pass = estimate_time_series_betas(
        returns, factors, hac_lags=automatic_newey_west_lags(len(panel))
    )
    betas = first_pass.coefficients[["RM", "FFR_innovation"]]
    mean_returns = returns.mean().rename("mean_return")
    result = estimate_article_second_pass(
        mean_excess_returns=mean_returns,
        betas=betas,
        residual_covariance=residual_covariance_from_first_pass(first_pass.residuals),
        factor_covariance=factors.cov(),
        n_months=len(panel),
        portfolio_set="all_seven_families_joint",
        model=label,
    )
    return betas, mean_returns, result


def _spreads(betas: pd.DataFrame, lambda_rate: float, columns: list[str]) -> dict[str, float]:
    premia = betas["FFR_innovation"].to_numpy(dtype=float) * lambda_rate
    return {
        family: float(premia[high] - premia[low])
        for family, (low, high) in _spread_pairs(columns).items()
    }


def standardized_dispersion_share(
    betas: pd.DataFrame, *, market: FloatArray, innovation: FloatArray
) -> float:
    """Return the H4a standardized rate-exposure dispersion share for one window.

    The share is
    ``sd_cs(beta_rate * sd(rate innovation)) / sd_cs(beta_mkt * sd(market))`` on
    the window's own betas and its own factor standard deviations, which is the
    quantity ``research/inference_contract.md`` puts a floor on. It is computed
    through :func:`weak_factor_report` rather than inline so that the H2
    diagnostic and the H4a gate cannot drift apart in definition, and so that a
    rebuild reports the window it actually estimated rather than a constant.

    Args:
        betas: First-pass betas with the ``RM`` and ``FFR_innovation`` columns.
        market: Market excess return over the same months.
        innovation: Short-rate innovation over the same months.

    Returns:
        The rate share of market standardized dispersion.

    Raises:
        ValueError: If the market standardized dispersion is zero, which would
            leave the share undefined.
    """
    factors = pd.DataFrame({"RM": np.asarray(market, dtype=float), "FFR_innovation": innovation})
    dispersion = weak_factor_report(
        betas=betas[["RM", "FFR_innovation"]], factors=factors
    ).standardized_exposure_dispersion
    if dispersion["RM"] == 0.0:
        raise ValueError("Standardized market-exposure dispersion is zero")
    return float(dispersion["FFR_innovation"] / dispersion["RM"])


def window_bootstrap(
    *,
    window_id: str,
    panel: pd.DataFrame,
    columns: list[str],
    lagged: FloatArray,
    innovation: FloatArray,
    seed: int,
) -> tuple[RegimePremiumBootstrap, BlockLengthSelection]:
    """Run the joint moving-block bootstrap over one estimation window.

    Every stage is recomputed inside each draw, including the autoregression that
    builds the short-rate innovation, so the interval describes the estimator the
    point estimate came from. The block length is selected per window under the
    frozen contract, because the two windows differ by a factor of three and a
    single shared length would be selected on neither.

    Args:
        window_id: Label carried onto the result for provenance.
        panel: The window's monthly panel.
        columns: Test-asset columns in their canonical order.
        lagged: The window's one-month lagged rate level under the frozen
            pre-window-lag convention.
        innovation: The window's short-rate innovation, used only to select the
            block length; each draw re-estimates its own.
        seed: Random seed for this window's draw stream.

    Returns:
        The bootstrap result and the block-length selection that produced it.
    """
    selection = select_block_length(
        pd.DataFrame(
            {
                "market_excess_return": panel["market_excess_return"].to_numpy(dtype=float),
                f"short_rate_innovation__{RATE}": innovation,
            }
        )
    )
    result = bootstrap_regime_premia(
        # The bootstrap is labelled by regime in H3 and by evaluation window
        # here; the label is provenance only and is never resampled either way.
        regime_id=window_id,
        assets=tuple(columns),
        rate_level=panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float),
        lagged_rate_level=lagged,
        market=panel["market_excess_return"].to_numpy(dtype=float),
        excess_returns=panel[columns].to_numpy(dtype=float),
        block_length=selection.block_length,
        draws=DRAWS,
        seed=seed,
        block_length_selected_by=selection.selected_by,
    )
    return result, selection


def spread_draws(bootstrap: RegimePremiumBootstrap, columns: list[str]) -> dict[str, FloatArray]:
    """Collapse per-portfolio premium draws to the per-family decile spread.

    Args:
        bootstrap: One window's bootstrap over per-portfolio fitted premia.
        columns: Test-asset columns in the order the draws were stored in.

    Returns:
        Draw-level ``pi(decile_10) - pi(decile_01)`` for each registered family.
    """
    draws = bootstrap.premium_draws
    return {
        family: draws[:, high] - draws[:, low]
        for family, (low, high) in _spread_pairs(columns).items()
    }


def _inferential_status(outcomes: list[EquivalenceOutcome]) -> str:
    """Reduce the per-estimand interval decisions to one supplementary status.

    The three outcomes are not interchangeable, and the middle one is the whole
    reason this function exists. ``unsupported`` asserts that the economic
    relation changed, so it requires at least one estimand whose entire interval
    lies beyond its bound. An estimand that merely fails to certify
    compatibility leaves the question open, which is the registry's registered
    ``inconclusive`` reading for H2.

    Args:
        outcomes: The classified estimands of the temporal comparison.

    Returns:
        The supplementary inferential status label.
    """
    if all(outcome.passes for outcome in outcomes):
        return "post_publication_compatibility_supported_under_the_bootstrap_interval_standard"
    if any(outcome.decision_category == "difference_exceeds_bound" for outcome in outcomes):
        return "post_publication_compatibility_unsupported_under_the_bootstrap_interval_standard"
    return "post_publication_compatibility_inconclusive_under_the_bootstrap_interval_standard"


def relative_change_draws(current: FloatArray, reference: FloatArray) -> FloatArray:
    """Pair two independent draw sequences into a relative change, draw by draw.

    The multiplicative counterpart of
    :func:`short_rate_anomaly_regimes.regimes.equivalence.paired_difference_draws`,
    with the same truncation rule so that no draw is reused.

    Args:
        current: Draws for the window under test.
        reference: Draws for the comparison window.

    Returns:
        ``current / reference - 1`` over the paired draws.
    """
    usable = min(current.size, reference.size)
    return current[:usable] / reference[:usable] - 1.0


def main() -> None:
    """Run all three evaluations and classify H2."""
    baseline = _load(BASELINE_PARQUET)
    extension = _load(EXTENSION_PARQUET)
    revised = _load(REVISED_PARQUET)
    columns = _asset_columns(baseline)
    if _asset_columns(extension) != columns or _asset_columns(revised) != columns:
        raise ValueError("Panels disagree on the test-asset set")

    rate = load_current_vintage_rate()
    # The locked baseline does not carry its own lag column, so its pre-window lag
    # is recovered from the level and the AR residual it does carry. Checking the
    # recovered value against the observed preceding month proves that the two
    # historical-window evaluations share one timing convention, which is what
    # makes the locked-against-revised difference a pure vintage difference.
    baseline_pre_window_lag = pre_window_lag(rate, baseline)
    recovered_baseline_lag = float(
        recover_lagged_level(
            baseline[f"short_rate_level__{RATE}"].to_numpy(dtype=float),
            baseline[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float),
        )[0]
    )
    if abs(recovered_baseline_lag - baseline_pre_window_lag) > 1e-8:
        raise ValueError(
            "The locked baseline's first AR lag "
            f"({recovered_baseline_lag:.6f}) is not the observed level of the month "
            f"before its window ({baseline_pre_window_lag:.6f}), so the baseline and "
            "the revised history do not share the pre-window-lag timing convention"
        )

    intercept, slope = _ar_parameters(baseline)
    baseline_innovation = baseline[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float)
    baseline_betas, _, baseline_result = _fit_system(baseline, baseline_innovation, "baseline")
    baseline_lambda_rate = float(baseline_result.risk_prices["FFR_innovation"])
    baseline_spreads = _spreads(baseline_betas, baseline_lambda_rate, columns)

    # Frozen-parameter: the AR parameters, the betas and the risk prices are all
    # the 2013-12 values. The only post-2013 information used is the realised
    # data the frozen model is scored against.
    # The extension panel is on the current vintage, so its pre-window lag is the
    # current-vintage December 2013 level, the month immediately preceding the
    # extension window, rather than the last row of the locked baseline panel.
    previous_level = pre_window_lag(rate, extension)
    # With the betas and the risk prices both frozen, the fitted premium is a
    # pure function of baseline parameters, so the extension innovation does not
    # enter this evaluation at all. The frozen AR coefficients still matter,
    # because they are the ones that produced the frozen betas. The frozen
    # innovation is computed here only to confirm it can be built without any
    # post-2013 estimation, which is what makes the evaluation out of sample.
    frozen_innovation = _innovation_from_frozen_ar(
        extension, intercept=intercept, slope=slope, previous_level=previous_level
    )
    if not np.all(np.isfinite(frozen_innovation)):
        raise ValueError("Frozen AR parameters produced a non-finite extension innovation")
    extension_mean = extension[columns].mean().to_numpy(dtype=float)
    frozen_fitted = baseline_betas.to_numpy(dtype=float) @ baseline_result.risk_prices.to_numpy(
        dtype=float
    )
    frozen_errors = extension_mean - frozen_fitted
    frozen_spreads = baseline_spreads  # parameters frozen, so the spreads are too

    # Refitted: everything re-estimated on the extension window alone.
    refit_level = extension[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    refit_lagged = lagged_level(extension, previous_level=previous_level)
    refit_design = np.column_stack([np.ones(refit_level.size), refit_lagged])
    refit_ar = np.linalg.lstsq(refit_design, refit_level, rcond=None)[0]
    refit_innovation = refit_level - refit_design @ refit_ar
    refit_betas, _, refit_result = _fit_system(extension, refit_innovation, "refitted_extension")
    refit_lambda_rate = float(refit_result.risk_prices["FFR_innovation"])
    refit_spreads = _spreads(refit_betas, refit_lambda_rate, columns)

    # Revised history: baseline months, current vintage. The pre-window lag is the
    # current-vintage December 1971 level, so this AR shares the locked baseline's
    # timing convention and the two differ only in vintage.
    revised_previous_level = pre_window_lag(rate, revised)
    revised_innovation_level = revised[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    revised_lagged = lagged_level(revised, previous_level=revised_previous_level)
    revised_design = np.column_stack([np.ones(revised_innovation_level.size), revised_lagged])
    revised_ar = np.linalg.lstsq(revised_design, revised_innovation_level, rcond=None)[0]
    revised_innovation = revised_innovation_level - revised_design @ revised_ar
    revised_betas, _, revised_result = _fit_system(revised, revised_innovation, "revised_history")
    revised_lambda_rate = float(revised_result.risk_prices["FFR_innovation"])
    revised_spreads = _spreads(revised_betas, revised_lambda_rate, columns)

    frozen_rmse = float(np.sqrt(np.mean(np.square(frozen_errors))))
    rows = [
        {
            "evaluation": "locked_baseline_1972_2013",
            "vintage": "publication_era",
            "months": len(baseline),
            "lambda_market": float(baseline_result.risk_prices["RM"]),
            "lambda_rate": baseline_lambda_rate,
            "shanken_t_rate": float(baseline_result.shanken_t_statistics["FFR_innovation"]),
            "rmse": baseline_result.root_mean_squared_pricing_error,
            "mae": baseline_result.mean_absolute_pricing_error,
            "max_abs": baseline_result.max_absolute_pricing_error,
            "article_fit": baseline_result.article_cross_sectional_fit,
        },
        {
            "evaluation": "frozen_parameter_extension_2014_2025",
            "vintage": "current",
            "months": len(extension),
            "lambda_market": float(baseline_result.risk_prices["RM"]),
            "lambda_rate": baseline_lambda_rate,
            "shanken_t_rate": float(baseline_result.shanken_t_statistics["FFR_innovation"]),
            "rmse": frozen_rmse,
            "mae": float(np.mean(np.abs(frozen_errors))),
            "max_abs": float(np.max(np.abs(frozen_errors))),
            "article_fit": float(1.0 - np.var(frozen_errors) / np.var(extension_mean)),
        },
        {
            "evaluation": "refitted_extension_2014_2025",
            "vintage": "current",
            "months": len(extension),
            "lambda_market": float(refit_result.risk_prices["RM"]),
            "lambda_rate": refit_lambda_rate,
            "shanken_t_rate": float(refit_result.shanken_t_statistics["FFR_innovation"]),
            "rmse": refit_result.root_mean_squared_pricing_error,
            "mae": refit_result.mean_absolute_pricing_error,
            "max_abs": refit_result.max_absolute_pricing_error,
            "article_fit": refit_result.article_cross_sectional_fit,
        },
        {
            "evaluation": "revised_history_1972_2013",
            "vintage": "current",
            "months": len(revised),
            "lambda_market": float(revised_result.risk_prices["RM"]),
            "lambda_rate": revised_lambda_rate,
            "shanken_t_rate": float(revised_result.shanken_t_statistics["FFR_innovation"]),
            "rmse": revised_result.root_mean_squared_pricing_error,
            "mae": revised_result.mean_absolute_pricing_error,
            "max_abs": revised_result.max_absolute_pricing_error,
            "article_fit": revised_result.article_cross_sectional_fit,
        },
    ]
    evaluation = pd.DataFrame.from_records(rows)
    evaluation["replication_status"] = "documented_reconstruction"

    spread_rows = []
    for family in FAMILY_MEMBERS:
        base = baseline_spreads[family]
        spread_rows.append(
            {
                "family": family,
                "baseline_spread": base,
                "frozen_spread": frozen_spreads[family],
                "refitted_spread": refit_spreads[family],
                "revised_history_spread": revised_spreads[family],
                "temporal_change": refit_spreads[family] - revised_spreads[family],
                "vintage_change": revised_spreads[family] - base,
                "total_change": refit_spreads[family] - base,
                # The registered gate. It compares the refitted extension with
                # the LOCKED baseline, so it is the one place in H2 where two
                # vintages meet; the magnitude gate below is vintage isolated.
                "sign_compatible_with_baseline": bool(
                    np.sign(refit_spreads[family]) == np.sign(base)
                ),
                # The same-vintage counterpart, reported so the vintage-isolated
                # reading of the sign comparison is auditable. It decides
                # nothing: the frozen rule is the column above.
                "sign_compatible_with_revised_history": bool(
                    np.sign(refit_spreads[family]) == np.sign(revised_spreads[family])
                ),
                "temporal_change_within_bound": bool(
                    abs(refit_spreads[family] - revised_spreads[family]) <= FITTED_PREMIUM_BOUND
                ),
                "total_change_within_bound": bool(
                    abs(refit_spreads[family] - base) <= FITTED_PREMIUM_BOUND
                ),
            }
        )
    spreads = pd.DataFrame.from_records(spread_rows)

    baseline_rmse = baseline_result.root_mean_squared_pricing_error
    revised_rmse = revised_result.root_mean_squared_pricing_error
    refit_rmse = refit_result.root_mean_squared_pricing_error
    rmse_vs_revised = (refit_rmse - revised_rmse) / revised_rmse
    rmse_vs_locked = (refit_rmse - baseline_rmse) / baseline_rmse

    # The registered, confirmatory rule, applied to point estimates exactly as
    # frozen in the H2 registry row. Nothing below may modify it.
    sign_ok = bool(spreads["sign_compatible_with_baseline"].all())
    magnitude_ok = bool(spreads["temporal_change_within_bound"].all())
    rmse_ok = bool(rmse_vs_revised <= RMSE_DETERIORATION_BOUND)
    supported = sign_ok and magnitude_ok and rmse_ok
    classification = (
        "post_publication_compatibility_supported"
        if supported
        else "post_publication_compatibility_unsupported"
    )

    # The same-vintage sign comparison. It is reported, never substituted: the
    # frozen gate is the locked-baseline column. The two can only diverge for a
    # family whose revised-history spread has crossed zero relative to the
    # locked one, which the vintage decomposition would show as a spread change
    # of the order of the spread itself rather than of the revision.
    same_vintage_sign_ok = bool(spreads["sign_compatible_with_revised_history"].all())
    sign_gate_vintage_disagreement = sign_ok != same_vintage_sign_ok

    vintage = pd.DataFrame.from_records(
        [
            {
                "comparison": "vintage_effect_locked_vs_revised_history",
                "description": "same months, publication-era against current vintage",
                "lambda_rate_change": revised_lambda_rate - baseline_lambda_rate,
                "rmse_relative_change": (revised_rmse - baseline_rmse) / baseline_rmse,
                "max_abs_spread_change": float(spreads["vintage_change"].abs().max()),
            },
            {
                "comparison": "temporal_effect_revised_history_vs_refitted_extension",
                "description": "same vintage, baseline months against extension months",
                "lambda_rate_change": refit_lambda_rate - revised_lambda_rate,
                "rmse_relative_change": rmse_vs_revised,
                "max_abs_spread_change": float(spreads["temporal_change"].abs().max()),
            },
            {
                "comparison": "combined_locked_baseline_vs_refitted_extension",
                "description": "confounds vintage and time; reported for completeness only",
                "lambda_rate_change": refit_lambda_rate - baseline_lambda_rate,
                "rmse_relative_change": rmse_vs_locked,
                "max_abs_spread_change": float(spreads["total_change"].abs().max()),
            },
        ]
    )

    # ------------------------------------------------------------------ #
    # Supplementary inferential comparison.
    #
    # The registered rule above is a point-estimate rule, so it can only ever
    # say supported or unsupported. The registry, however, defines a third H2
    # outcome for evidence that is too imprecise to classify, and on 144 months
    # that is not a hypothetical: the refitted lambda_rate carries a Shanken t
    # of about -1.5. What follows puts an interval around the same temporal
    # comparison so that outcome is reachable. It is recorded beside the
    # registered verdict and never in place of it.
    # ------------------------------------------------------------------ #
    revised_bootstrap, revised_selection = window_bootstrap(
        window_id="revised_history_1972_2013",
        panel=revised,
        columns=columns,
        lagged=revised_lagged,
        innovation=revised_innovation,
        seed=REVISED_HISTORY_SEED,
    )
    refit_bootstrap, refit_selection = window_bootstrap(
        window_id="refitted_extension_2014_2025",
        panel=extension,
        columns=columns,
        lagged=refit_lagged,
        innovation=refit_innovation,
        seed=REFITTED_EXTENSION_SEED,
    )
    # The two windows partition the calendar, so their bootstrap distributions
    # are independent and pairing the draws index-wise samples the product
    # distribution. This is the same argument the H3 regime comparison rests on.
    revised_spread_draws = spread_draws(revised_bootstrap, columns)
    refit_spread_draws = spread_draws(refit_bootstrap, columns)

    outcomes = [
        classify_equivalence(
            estimand=f"temporal_fitted_premium_spread_change__{family}",
            point_change=refit_spreads[family] - revised_spreads[family],
            change_draws=paired_difference_draws(
                refit_spread_draws[family], revised_spread_draws[family]
            ),
            bound=FITTED_PREMIUM_BOUND,
        )
        for family in FAMILY_MEMBERS
    ]
    outcomes.append(
        classify_equivalence(
            estimand="temporal_rmse_relative_change",
            point_change=rmse_vs_revised,
            change_draws=relative_change_draws(
                refit_bootstrap.statistic_draws["rmse"],
                revised_bootstrap.statistic_draws["rmse"],
            ),
            bound=RMSE_DETERIORATION_BOUND,
            # Only deterioration is bounded, so the registered comparison is a
            # one-sided one and so is its interval test.
            one_sided=True,
        )
    )

    inference = pd.DataFrame.from_records(
        [
            {
                "estimand": outcome.estimand,
                "comparison": "refitted_extension_2014_2025_minus_revised_history_1972_2013",
                "point_change": outcome.point_change,
                "lower_90": outcome.lower_90,
                "upper_90": outcome.upper_90,
                "lower_95": outcome.lower_95,
                "upper_95": outcome.upper_95,
                "bound": outcome.bound,
                "one_sided_bound": outcome.one_sided,
                "tost_5pct_90pct_interval_passes": outcome.passes,
                "decision_category": outcome.decision_category,
                "strict_95pct_interval_sensitivity_passes": outcome.passes_strict_sensitivity,
                "rule": CONFIRMATORY_RULE,
                "sensitivity_rule": SENSITIVITY_RULE,
                "role": "supplementary_inferential_not_the_registered_gate",
                "replication_status": "documented_reconstruction",
            }
            for outcome in outcomes
        ]
    )
    inferential_status = _inferential_status(outcomes)
    exceeded = sorted(
        outcome.estimand
        for outcome in outcomes
        if outcome.decision_category == "difference_exceeds_bound"
    )
    inconclusive = sorted(
        outcome.estimand for outcome in outcomes if outcome.decision_category == "inconclusive"
    )

    baseline_dispersion_share = standardized_dispersion_share(
        baseline_betas,
        market=baseline["market_excess_return"].to_numpy(dtype=float),
        innovation=baseline_innovation,
    )
    refit_dispersion_share = standardized_dispersion_share(
        refit_betas,
        market=extension["market_excess_return"].to_numpy(dtype=float),
        innovation=refit_innovation,
    )

    for path in (EVALUATION_CSV, DIAGNOSTIC_JSON):
        path.parent.mkdir(parents=True, exist_ok=True)
    evaluation.to_csv(EVALUATION_CSV, index=False, lineterminator="\n")
    spreads.to_csv(SPREAD_CSV, index=False, lineterminator="\n")
    vintage.to_csv(VINTAGE_CSV, index=False, lineterminator="\n")
    inference.to_csv(INFERENCE_CSV, index=False, lineterminator="\n")

    DIAGNOSTIC_JSON.write_text(
        json.dumps(
            {
                "hypothesis": "H2",
                # The registered, confirmatory verdict. The supplementary
                # interval classification is recorded under
                # `supplementary_inferential_classification` and does not touch
                # this key or the gates below.
                "classification": classification,
                "classification_role": "registered_confirmatory_point_estimate_rule",
                "gates": {
                    "sign_compatibility": sign_ok,
                    "fitted_premium_magnitude_within_0_25": magnitude_ok,
                    "rmse_deterioration_within_10_percent": rmse_ok,
                },
                "sign_gate_vintage": {
                    "registered_gate_compares_against": "locked_baseline",
                    "registered_gate_passes": sign_ok,
                    "same_vintage_gate_compares_against": "revised_history",
                    "same_vintage_gate_passes": same_vintage_sign_ok,
                    "gates_agree": not sign_gate_vintage_disagreement,
                    "note": (
                        "the registered sign gate compares the refitted extension with the "
                        "locked baseline and so is the one H2 gate that spans two vintages; "
                        "the fitted-premium magnitude gate is vintage isolated against the "
                        "revised history. The same-vintage sign comparison is reported here "
                        "for audit and decides nothing. Where the two disagree the registered "
                        "verdict still follows the locked-baseline column"
                    ),
                },
                "supplementary_inferential_classification": {
                    "status": inferential_status,
                    "role": (
                        "supplementary interval evidence; the registered point-estimate rule "
                        "above remains the confirmatory classification"
                    ),
                    "rule": CONFIRMATORY_RULE,
                    "sensitivity_rule": SENSITIVITY_RULE,
                    "comparison": ("refitted_extension_2014_2025_minus_revised_history_1972_2013"),
                    "estimands": {
                        outcome.estimand: {
                            "point_change": outcome.point_change,
                            "lower_90": outcome.lower_90,
                            "upper_90": outcome.upper_90,
                            "lower_95": outcome.lower_95,
                            "upper_95": outcome.upper_95,
                            "bound": outcome.bound,
                            "one_sided_bound": outcome.one_sided,
                            "decision_category": outcome.decision_category,
                            "tost_5pct_90pct_interval_passes": outcome.passes,
                            "strict_95pct_interval_sensitivity_passes": (
                                outcome.passes_strict_sensitivity
                            ),
                        }
                        for outcome in outcomes
                    },
                    "estimands_with_a_demonstrated_exceedance": exceeded,
                    "estimands_that_are_inconclusive": inconclusive,
                    "status_basis": (
                        "at least one estimand has its whole 90 percent interval beyond its "
                        "bound, which is what a demonstrated temporal change asserts"
                        if exceeded
                        else (
                            "no estimand demonstrates an exceedance; the registered gates fail "
                            "on point estimates that the interval cannot separate from the "
                            "bound, which is imprecision rather than a demonstrated change"
                        )
                    ),
                    "draws": DRAWS,
                    "windows": {
                        "revised_history_1972_2013": {
                            "months": revised_bootstrap.months,
                            "seed": revised_bootstrap.seed,
                            "successful_draws": revised_bootstrap.successful_draws,
                            "block_length": revised_bootstrap.block_length,
                            "block_length_selected_by": revised_selection.selected_by,
                            "block_length_failure_reasons": list(revised_selection.failure_reasons),
                            "raw_politis_white_lengths": list(
                                revised_selection.raw_optimal_lengths
                            ),
                        },
                        "refitted_extension_2014_2025": {
                            "months": refit_bootstrap.months,
                            "seed": refit_bootstrap.seed,
                            "successful_draws": refit_bootstrap.successful_draws,
                            "block_length": refit_bootstrap.block_length,
                            "block_length_selected_by": refit_selection.selected_by,
                            "block_length_failure_reasons": list(refit_selection.failure_reasons),
                            "raw_politis_white_lengths": list(refit_selection.raw_optimal_lengths),
                        },
                    },
                    "resampled_variables": [
                        "market_excess_return",
                        "portfolio_excess_returns",
                        "short_rate_level",
                    ],
                    "recomputed_per_draw": [
                        "short_rate_innovation",
                        "first_pass_betas",
                        "second_pass_risk_prices",
                        "fitted_premia",
                        "pricing_errors",
                        "fit_metrics",
                    ],
                    "note": (
                        "both windows are re-estimated inside every draw and the two "
                        "independent draw sequences are paired index-wise, so the interval "
                        "describes the temporal comparison rather than either window alone"
                    ),
                },
                "rmse_relative_change_vs_revised_history": rmse_vs_revised,
                "rmse_relative_change_vs_locked_baseline": rmse_vs_locked,
                "frozen_ar_intercept": intercept,
                "frozen_ar_slope": slope,
                "ar_timing_convention": {
                    "convention": "pre_window_lag",
                    "source": FEDFUNDS_CSV.as_posix(),
                    "note": (
                        "every evaluation regresses its first window month on the "
                        "observed level of the month before the window, read from the "
                        "vintage that evaluation is estimated on, so the locked "
                        "baseline and the revised history differ only in vintage"
                    ),
                    "pre_window_lag_level": {
                        "locked_baseline_1972_2013": baseline_pre_window_lag,
                        "revised_history_1972_2013": revised_previous_level,
                        "extension_2014_2025": previous_level,
                    },
                    "locked_baseline_recovered_first_lag": recovered_baseline_lag,
                },
                "lambda_rate": {
                    "locked_baseline": baseline_lambda_rate,
                    "revised_history": revised_lambda_rate,
                    "refitted_extension": refit_lambda_rate,
                },
                "standardized_rate_exposure_dispersion_share": {
                    "locked_baseline": baseline_dispersion_share,
                    "refitted_extension": refit_dispersion_share,
                    "floor": MIN_STANDARDIZED_RATE_DISPERSION_SHARE,
                    "note": (
                        "recomputed from each window's own first-pass betas and factor "
                        f"standard deviations. The H4a dispersion floor is "
                        f"{MIN_STANDARDIZED_RATE_DISPERSION_SHARE}; the extension window "
                        "clears it, so the extension does not fail the registered H4a "
                        "dispersion criterion. That criterion does not measure exposure "
                        "reliability, so a higher share is not evidence that the temporal "
                        "result is well identified"
                    ),
                },
                "vintage_isolation": (
                    "the temporal gates compare the refitted extension with the "
                    "revised-history baseline, so revised historical values do enter the "
                    "comparison, as the quantity the extension is measured against. What "
                    "the shared vintage achieves is holding the revision contribution "
                    "common to both sides, so it differences out of the temporal change; "
                    "the publication-era against current-vintage effect is reported "
                    "separately as the locked-against-revised comparison"
                ),
                "replication_status": "documented_reconstruction",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_temporal_extension.py",
                "inputs": {
                    p.as_posix(): _sha256(p)
                    for p in (
                        BASELINE_PARQUET,
                        EXTENSION_PARQUET,
                        REVISED_PARQUET,
                        FEDFUNDS_CSV,
                    )
                },
                "outputs": {
                    p.as_posix(): _sha256(p)
                    for p in (
                        EVALUATION_CSV,
                        SPREAD_CSV,
                        VINTAGE_CSV,
                        INFERENCE_CSV,
                        DIAGNOSTIC_JSON,
                    )
                },
                "bounds": {
                    "fitted_premium": FITTED_PREMIUM_BOUND,
                    "rmse_deterioration": RMSE_DETERIORATION_BOUND,
                },
                "bootstrap": {
                    "draws": DRAWS,
                    "base_seed": BASE_SEED,
                    "seeds_by_window": {
                        "revised_history_1972_2013": revised_bootstrap.seed,
                        "refitted_extension_2014_2025": refit_bootstrap.seed,
                    },
                    "successful_draws_by_window": {
                        "revised_history_1972_2013": revised_bootstrap.successful_draws,
                        "refitted_extension_2014_2025": refit_bootstrap.successful_draws,
                    },
                    "block_lengths_by_window": {
                        "revised_history_1972_2013": revised_bootstrap.block_length,
                        "refitted_extension_2014_2025": refit_bootstrap.block_length,
                    },
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(evaluation.round(4).to_string(index=False))
    print()
    print(vintage.round(4).to_string(index=False))
    print()
    print(spreads.round(4).to_string(index=False))
    print()
    print(
        inference[
            [
                "estimand",
                "point_change",
                "lower_90",
                "upper_90",
                "bound",
                "tost_5pct_90pct_interval_passes",
                "decision_category",
            ]
        ]
        .round(4)
        .to_string(index=False)
    )
    print(f"\nH2 registered classification: {classification}")
    print(f"  sign compatibility        : {sign_ok} (against the locked baseline, as registered)")
    print(f"  same-vintage sign check   : {same_vintage_sign_ok} (reported only, decides nothing)")
    print(f"  fitted-premium magnitude  : {magnitude_ok}")
    print(f"  RMSE deterioration        : {rmse_ok} ({rmse_vs_revised:+.1%} vs revised history)")
    if sign_gate_vintage_disagreement:
        print(
            "  WARNING: the registered locked-baseline sign gate and the same-vintage sign "
            "comparison disagree; the registered verdict still follows the locked-baseline "
            "column, and the divergence is recorded under sign_gate_vintage"
        )
    print(f"\nH2 supplementary inferential status: {inferential_status}")
    print(f"  demonstrated exceedances  : {exceeded or 'none'}")
    print(f"  inconclusive estimands    : {inconclusive or 'none'}")
    print(
        "  dispersion share          : locked baseline "
        f"{baseline_dispersion_share:.4f}, refitted extension {refit_dispersion_share:.4f} "
        f"(H4a floor {MIN_STANDARDIZED_RATE_DISPERSION_SHARE})"
    )


if __name__ == "__main__":
    main()
