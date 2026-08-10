"""Run the H4a and H4b weak-factor decision gates on the frozen baseline system.

H4a is the cross-sectional identification-strength hypothesis. It fails when the
beta matrix is numerically rank deficient, when standardized short-rate exposure
dispersion falls below 10 percent of standardized market exposure dispersion, or
when the frozen numerical factor-spanning criterion fails.

H4b is the influence-stability hypothesis. It fails when a leave-one-anomaly-
family refit changes the sign of the rate-attributable fitted-premium spread or
removes its materiality classification, or when the maximum absolute
standardized DFBETA of any single portfolio on ``lambda_rate`` reaches 1.

Every threshold executed here is transcribed from the frozen contract files
``research/inference_contract.md``, ``research/weak_factor_registry.csv``, and
``research/economic_thresholds.md``. This script reports gate outcomes and the
numbers behind them. It states no economic conclusion about the article.

H4c is a separate confirmatory hypothesis and is not executed here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    ArticleSecondPassResult,
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.diagnostics import (
    MAX_SPANNING_R_SQUARED,
    MIN_SPANNING_RESIDUAL_RATIO,
    MIN_STANDARDIZED_RATE_DISPERSION_SHARE,
    REGISTERED_SPANNING_REGRESSORS,
    SPANNING_DECISION_TOLERANCE,
    H4aIdentificationConclusion,
    RateSpanningCriterion,
    WeakFactorReport,
    classify_h4a_identification_strength,
    rate_spanning_criterion,
    weak_factor_report,
)
from short_rate_anomaly_regimes.models.time_series import (
    automatic_newey_west_lags,
    estimate_time_series_betas,
)
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS
from short_rate_anomaly_regimes.provenance import sha256_file

SCRIPT_NAME: Final = "scripts/run_weak_factor_diagnostics.py"

PANEL_PARQUET: Final = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET: Final = Path("data/processed/comparator_factors.parquet")
FIRST_PASS_PARQUET: Final = Path(
    "artifacts/estimates/time_series/baseline_first_pass_betas.parquet"
)
RISK_PRICE_CSV: Final = Path("artifacts/tables/cross_section/baseline_risk_prices.csv")

H4A_JSON: Final = Path("artifacts/diagnostics/weak_factor/h4a_identification_strength.json")
H4B_JSON: Final = Path("artifacts/diagnostics/weak_factor/h4b_influence_stability.json")
LEAVE_ONE_FAMILY_CSV: Final = Path("artifacts/tables/robustness/leave_one_family.csv")
DFBETA_CSV: Final = Path("artifacts/tables/robustness/dfbeta_influence.csv")
PROVENANCE_JSON: Final = Path("artifacts/provenance/weak_factor_diagnostics.json")

#: The tested system for both weak-factor hypotheses.
MODEL: Final = "market_plus_fedfunds_innovation"
BASELINE_PORTFOLIO_SET: Final = "all_seven_families_joint"
MARKET_FACTOR: Final = "RM"
RATE_FACTOR: Final = "FFR_innovation"
RATE_INNOVATION_COLUMN: Final = "short_rate_innovation__fedfunds"
PORTFOLIO_COLUMN_PREFIX: Final = "portfolio_excess_return__"

#: The comparator panel names the market factor ``RM``; the frozen spanning
#: regressor list in ``research/inference_contract.md`` names it ``Mkt-RF``. The
#: rename is a naming map only and changes no value.
COMPARATOR_MARKET_RENAME: Final[dict[str, str]] = {MARKET_FACTOR: "Mkt-RF"}

#: The extreme deciles whose rate-attributable fitted premia define the spread.
#: This matches the article's Table 5 ``DIF`` column.
LOW_DECILE: Final = "decile_01"
HIGH_DECILE: Final = "decile_10"

#: research/economic_thresholds.md: the materiality threshold on a
#: rate-attributable fitted premium, in monthly percentage points. A spread is
#: classified material when its absolute value reaches this bound.
MATERIAL_FITTED_PREMIUM_SPREAD: Final = 0.25

#: research/weak_factor_registry.csv, diagnostic ``dfbeta_influence``: the
#: maximum absolute standardized DFBETA must stay below 1. The gate fails when
#: any absolute standardized DFBETA reaches this bound.
MAX_ABS_STANDARDIZED_DFBETA: Final = 1.0

GATE_RANK: Final = "rank_gate"
GATE_DISPERSION: Final = "standardized_rate_exposure_dispersion"
GATE_SPANNING: Final = "rate_spanning_criterion"
GATE_LEAVE_ONE_FAMILY: Final = "leave_one_family_fitted_premium"
GATE_DFBETA: Final = "dfbeta_influence"

ROLE_CONFIRMATORY: Final = "confirmatory"
ROLE_DESCRIPTIVE: Final = "descriptive"


@dataclass(frozen=True, slots=True)
class SystemEstimate:
    """First-pass and article second-pass estimate of one pricing system.

    Attributes:
        portfolio_set: Identifier of the asset set.
        model: Identifier of the factor model.
        betas: First-pass loadings, assets by factors, with no intercept column.
        mean_excess_returns: Average excess return per test asset.
        residual_covariance: First-pass residual covariance across test assets.
        factor_covariance: Covariance of the priced factors.
        n_months: Months in the first-pass estimation window.
        second_pass: The article second-pass result for the system.
    """

    portfolio_set: str
    model: str
    betas: pd.DataFrame
    mean_excess_returns: pd.Series
    residual_covariance: pd.DataFrame
    factor_covariance: pd.DataFrame
    n_months: int
    second_pass: ArticleSecondPassResult


def short_asset_label(column: str) -> str:
    """Shorten a panel column to ``family__decile`` for readable outputs.

    Args:
        column: Panel column name.

    Returns:
        The column without the portfolio prefix.
    """
    return column.removeprefix(PORTFOLIO_COLUMN_PREFIX)


def split_asset_label(asset: str) -> tuple[str, str]:
    """Split a ``family__decile`` asset label into its two parts.

    Args:
        asset: Asset label such as ``book_to_market__decile_01``.

    Returns:
        The family name and the decile name.

    Raises:
        ValueError: If the label does not carry both parts.
    """
    family, separator, decile = asset.rpartition("__")
    if not separator or not family or not decile:
        raise ValueError(f"Asset label {asset!r} is not of the form family__decile")
    return family, decile


def prepare_spanning_regressors(comparator_factors: pd.DataFrame) -> pd.DataFrame:
    """Rename the comparator market column to its registered spanning name.

    Args:
        comparator_factors: Comparator factor panel as stored on disk.

    Returns:
        The same panel with the market column named as the frozen regressor list
        names it. No value is changed.
    """
    return comparator_factors.rename(columns=COMPARATOR_MARKET_RENAME)


def evaluate_h4a(
    *,
    betas: pd.DataFrame,
    factors: pd.DataFrame,
    spanning: RateSpanningCriterion,
    rate_factor: str = RATE_FACTOR,
    market_factor: str = MARKET_FACTOR,
) -> tuple[WeakFactorReport, H4aIdentificationConclusion]:
    """Evaluate every confirmatory H4a gate for one asset set.

    The rank gate and the standardized rate-exposure dispersion gate are
    computed from the beta matrix and the factor panel. The spanning gate is
    supplied already executed, because the frozen criterion is estimated on the
    intersection months rather than on the asset set.

    Args:
        betas: First-pass loadings, assets by factors, ordered market then rate.
        factors: Factor panel carrying at least the beta columns.
        spanning: Executed result of the frozen factor-spanning criterion.
        rate_factor: Column name of the short-rate factor.
        market_factor: Column name of the market factor.

    Returns:
        The weak-factor report and the aggregated H4a decision.

    Raises:
        ValueError: If the beta matrix or the factor panel is unusable, as
            raised by the underlying diagnostics.
    """
    report = weak_factor_report(betas=betas, factors=factors)
    conclusion = classify_h4a_identification_strength(
        weak_report=report,
        spanning=spanning,
        rate_factor=rate_factor,
        market_factor=market_factor,
    )
    return report, conclusion


def rank_numerical_tolerance(report: WeakFactorReport) -> float:
    """Return the numerical rank tolerance declared for the H4a rank gate.

    The frozen rule counts singular values exceeding
    ``max(n_assets, n_factors) * machine_epsilon * largest_singular_value``.

    Args:
        report: Weak-factor report for the tested beta matrix.

    Returns:
        The tolerance actually implied by the reported singular values.
    """
    largest = max(report.singular_values)
    return float(max(report.n_assets, report.n_factors) * np.finfo(float).eps * largest)


def estimate_system(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    hac_lags: int,
    portfolio_set: str,
    model: str,
) -> SystemEstimate:
    """Estimate the first pass and the article second pass for one asset set.

    Args:
        excess_returns: Months by assets excess-return panel on a DatetimeIndex.
        factors: Months by factors panel on the same index type.
        hac_lags: Newey-West lag length for the first pass.
        portfolio_set: Identifier recorded on the result.
        model: Identifier recorded on the result.

    Returns:
        The complete system estimate.

    Raises:
        ValueError: If the panels share no complete observations, or if the
            second-pass inputs are misaligned or singular.
    """
    first_pass = estimate_time_series_betas(excess_returns, factors, hac_lags=hac_lags)
    assets = [str(column) for column in excess_returns.columns]
    factor_names = [str(column) for column in factors.columns]
    betas = first_pass.coefficients.loc[assets, factor_names]
    mean_returns = excess_returns.mean().rename("mean_excess_return")
    mean_returns.index = pd.Index(assets)
    residual_covariance = residual_covariance_from_first_pass(first_pass.residuals).loc[
        assets, assets
    ]
    factor_covariance = factors.cov()
    n_months = int(first_pass.alignment.common_observations)
    second_pass = estimate_article_second_pass(
        mean_excess_returns=mean_returns,
        betas=betas,
        residual_covariance=residual_covariance,
        factor_covariance=factor_covariance,
        n_months=n_months,
        portfolio_set=portfolio_set,
        model=model,
    )
    return SystemEstimate(
        portfolio_set=portfolio_set,
        model=model,
        betas=betas,
        mean_excess_returns=mean_returns,
        residual_covariance=residual_covariance,
        factor_covariance=factor_covariance,
        n_months=n_months,
        second_pass=second_pass,
    )


def family_fitted_premium_spreads(*, rate_betas: pd.Series, lambda_rate: float) -> pd.Series:
    """Compute the rate-attributable fitted-premium spread of every family.

    The frozen definition is ``spread = pi_rate(decile_10) - pi_rate(decile_01)``
    with ``pi_rate(i) = beta_rate(i) * lambda_rate``, which is the object the
    article tabulates as ``DIF`` across the extreme deciles.

    Args:
        rate_betas: Short-rate loadings indexed by ``family__decile`` labels.
        lambda_rate: Estimated short-rate risk price of the same system.

    Returns:
        The spread per family, indexed by family name and sorted by name.

    Raises:
        ValueError: If no loadings are supplied or if a family is missing one of
            the two extreme deciles.
    """
    if rate_betas.empty:
        raise ValueError("Short-rate loadings cannot be empty")
    premia = rate_betas.astype(float) * float(lambda_rate)
    members: dict[str, dict[str, str]] = {}
    for label in premia.index:
        family, decile = split_asset_label(str(label))
        members.setdefault(family, {})[decile] = str(label)
    spreads: dict[str, float] = {}
    for family in sorted(members):
        deciles = members[family]
        missing = [name for name in (LOW_DECILE, HIGH_DECILE) if name not in deciles]
        if missing:
            raise ValueError(
                f"Family {family!r} is missing extreme deciles: {', '.join(sorted(missing))}"
            )
        spreads[family] = float(premia[deciles[HIGH_DECILE]] - premia[deciles[LOW_DECILE]])
    return pd.Series(spreads, name="fitted_premium_spread", dtype=float)


def compare_family_spreads(*, baseline: pd.Series, refit: pd.Series) -> pd.DataFrame:
    """Compare baseline and refit fitted-premium spreads family by family.

    The registered leave-one-family gate fails when a refit changes the sign of
    the spread or removes its materiality classification. A refit that gains a
    materiality classification is recorded but is not a failure under the frozen
    rule.

    Args:
        baseline: Fitted-premium spread per family in the full system.
        refit: Fitted-premium spread per family in the refitted system.

    Returns:
        One row per family present in the refit, with the sign-reversal and
        materiality-loss flags and the row-level gate outcome.

    Raises:
        ValueError: If the refit carries a family absent from the baseline.
    """
    rows: list[dict[str, float | str | bool]] = []
    for family in refit.index:
        if family not in baseline.index:
            raise ValueError(f"Refit family {family!r} is absent from the baseline spreads")
        baseline_spread = float(baseline[family])
        refit_spread = float(refit[family])
        baseline_material = bool(abs(baseline_spread) >= MATERIAL_FITTED_PREMIUM_SPREAD)
        refit_material = bool(abs(refit_spread) >= MATERIAL_FITTED_PREMIUM_SPREAD)
        sign_reversal = bool(np.sign(baseline_spread) != np.sign(refit_spread))
        materiality_lost = bool(baseline_material and not refit_material)
        rows.append(
            {
                "family": str(family),
                "baseline_spread": baseline_spread,
                "refit_spread": refit_spread,
                "spread_change": refit_spread - baseline_spread,
                "baseline_material": baseline_material,
                "refit_material": refit_material,
                "sign_reversal": sign_reversal,
                "materiality_lost": materiality_lost,
                "passes": not (sign_reversal or materiality_lost),
            }
        )
    return pd.DataFrame(rows)


def leave_one_family_records(
    *,
    baseline: SystemEstimate,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    hac_lags: int,
    rate_factor: str = RATE_FACTOR,
    market_factor: str = MARKET_FACTOR,
) -> pd.DataFrame:
    """Refit the pricing system with each anomaly family removed in turn.

    Each refit re-estimates the first pass and the article second pass on the
    retained portfolios only, and records the short-rate risk price, the
    rate-attributable fitted premium of every retained asset, and whether the
    sign or the materiality classification of the family fitted-premium spread
    changed relative to the full system.

    Args:
        baseline: Estimate of the full system that supplies the comparison.
        excess_returns: Months by assets panel of the full system.
        factors: Months by factors panel used by the first pass.
        hac_lags: Newey-West lag length for the first pass.
        rate_factor: Column name of the short-rate factor.
        market_factor: Column name of the market factor.

    Returns:
        One row per omitted family and retained asset, carrying both the
        asset-level fitted premium and the family-level spread comparison.

    Raises:
        ValueError: If fewer than two anomaly families are present.
    """
    families = sorted({split_asset_label(str(column))[0] for column in excess_returns.columns})
    if len(families) < 2:
        raise ValueError("A leave-one-family refit needs at least two anomaly families")
    baseline_lambda_rate = float(baseline.second_pass.risk_prices[rate_factor])
    baseline_lambda_market = float(baseline.second_pass.risk_prices[market_factor])
    baseline_rate_betas = baseline.betas[rate_factor]
    baseline_spreads = family_fitted_premium_spreads(
        rate_betas=baseline_rate_betas, lambda_rate=baseline_lambda_rate
    )
    baseline_premia = baseline_rate_betas.astype(float) * baseline_lambda_rate
    rows: list[dict[str, float | int | str | bool]] = []
    for omitted in families:
        retained = [
            str(column)
            for column in excess_returns.columns
            if split_asset_label(str(column))[0] != omitted
        ]
        refit = estimate_system(
            excess_returns=excess_returns.loc[:, retained],
            factors=factors,
            hac_lags=hac_lags,
            portfolio_set=f"{baseline.portfolio_set}__minus__{omitted}",
            model=baseline.model,
        )
        lambda_rate = float(refit.second_pass.risk_prices[rate_factor])
        lambda_market = float(refit.second_pass.risk_prices[market_factor])
        shanken_se = float(refit.second_pass.shanken_standard_errors[rate_factor])
        refit_spreads = family_fitted_premium_spreads(
            rate_betas=refit.betas[rate_factor], lambda_rate=lambda_rate
        )
        comparison: dict[Any, dict[Any, Any]] = (
            compare_family_spreads(baseline=baseline_spreads, refit=refit_spreads)
            .set_index("family")
            .to_dict(orient="index")
        )
        refit_rate_betas = refit.betas[rate_factor].astype(float)
        for asset in refit.betas.index:
            family, decile = split_asset_label(str(asset))
            spread = comparison[family]
            beta_rate = float(refit_rate_betas[asset])
            premium = beta_rate * lambda_rate
            rows.append(
                {
                    "omitted_family": omitted,
                    "portfolio_set": refit.portfolio_set,
                    "model": refit.model,
                    "n_assets": int(refit.second_pass.n_assets),
                    "n_months": int(refit.n_months),
                    "lambda_rate": lambda_rate,
                    "lambda_market": lambda_market,
                    "shanken_se_lambda_rate": shanken_se,
                    "baseline_lambda_rate": baseline_lambda_rate,
                    "baseline_lambda_market": baseline_lambda_market,
                    "asset": str(asset),
                    "family": family,
                    "decile": decile,
                    "beta_rate": beta_rate,
                    "baseline_beta_rate": float(baseline_rate_betas[asset]),
                    "pi_rate": premium,
                    "baseline_pi_rate": float(baseline_premia[asset]),
                    "pi_rate_change": premium - float(baseline_premia[asset]),
                    "family_spread_baseline": float(spread["baseline_spread"]),
                    "family_spread_refit": float(spread["refit_spread"]),
                    "family_spread_change": float(spread["spread_change"]),
                    "family_material_baseline": bool(spread["baseline_material"]),
                    "family_material_refit": bool(spread["refit_material"]),
                    "family_sign_reversal": bool(spread["sign_reversal"]),
                    "family_materiality_lost": bool(spread["materiality_lost"]),
                    "family_gate_passes": bool(spread["passes"]),
                }
            )
    return pd.DataFrame(rows)


def leave_one_family_gate_passes(records: pd.DataFrame) -> bool:
    """Return whether no leave-one-family refit broke the fitted-premium spread.

    Args:
        records: Table produced by :func:`leave_one_family_records`.

    Returns:
        True when no retained family shows a sign reversal or a loss of the
        materiality classification.

    Raises:
        ValueError: If the table is empty.
    """
    if records.empty:
        raise ValueError("Leave-one-family records cannot be empty")
    return bool(records["family_gate_passes"].all())


def standardized_dfbeta_influence(
    *,
    mean_excess_returns: pd.Series,
    betas: pd.DataFrame,
    residual_covariance: pd.DataFrame,
    factor_covariance: pd.DataFrame,
    n_months: int,
    portfolio_set: str,
    model: str,
    rate_factor: str = RATE_FACTOR,
) -> pd.DataFrame:
    """Compute each portfolio's standardized DFBETA on the short-rate risk price.

    Only the second pass is refitted: the first-pass betas are held fixed and one
    asset at a time is removed from the average-return vector, the beta matrix,
    and the residual covariance. The change in the risk price is standardized by
    the Shanken standard error of ``lambda_rate`` in the full system, so the
    reported statistic is
    ``(lambda_rate_full - lambda_rate_without_i) / shanken_se(lambda_rate_full)``.
    The leave-one-out Shanken standard error is reported alongside it and is
    descriptive.

    Args:
        mean_excess_returns: Average excess return per test asset.
        betas: First-pass loadings, assets by factors.
        residual_covariance: First-pass residual covariance across test assets.
        factor_covariance: Covariance of the priced factors.
        n_months: Months in the first-pass estimation window.
        portfolio_set: Identifier recorded on every row.
        model: Identifier recorded on every row.
        rate_factor: Column name of the short-rate factor.

    Returns:
        One row per portfolio with the leave-one-out risk price, the parameter
        change, the standardized DFBETA, and the row-level threshold flag.

    Raises:
        ValueError: If the short-rate factor is absent, if removing one asset
            would leave too few assets to identify the risk prices, or if the
            full-system Shanken standard error is not positive.
    """
    if rate_factor not in betas.columns:
        raise ValueError(f"Beta matrix has no {rate_factor!r} column")
    assets = [str(label) for label in mean_excess_returns.index]
    if len(assets) - 1 <= betas.shape[1]:
        raise ValueError(
            "A leave-one-portfolio-out second pass needs more retained assets than factors"
        )
    full = estimate_article_second_pass(
        mean_excess_returns=mean_excess_returns,
        betas=betas,
        residual_covariance=residual_covariance,
        factor_covariance=factor_covariance,
        n_months=n_months,
        portfolio_set=portfolio_set,
        model=model,
    )
    lambda_full = float(full.risk_prices[rate_factor])
    shanken_se_full = float(full.shanken_standard_errors[rate_factor])
    if not shanken_se_full > 0.0:
        raise ValueError(
            "The full-system Shanken standard error of the short-rate risk price is not "
            "positive, so a standardized DFBETA is undefined"
        )
    rate_betas = betas[rate_factor].astype(float)
    rows: list[dict[str, float | int | str | bool]] = []
    for asset in assets:
        retained = [label for label in assets if label != asset]
        leave_one_out = estimate_article_second_pass(
            mean_excess_returns=mean_excess_returns.loc[retained],
            betas=betas.loc[retained],
            residual_covariance=residual_covariance.loc[retained, retained],
            factor_covariance=factor_covariance,
            n_months=n_months,
            portfolio_set=f"{portfolio_set}__minus__{asset}",
            model=model,
        )
        lambda_out = float(leave_one_out.risk_prices[rate_factor])
        change = lambda_full - lambda_out
        standardized = change / shanken_se_full
        family, decile = split_asset_label(asset)
        rows.append(
            {
                "portfolio_set": portfolio_set,
                "model": model,
                "asset": asset,
                "family": family,
                "decile": decile,
                "n_assets": int(full.n_assets),
                "beta_rate": float(rate_betas[asset]),
                "lambda_rate_full": lambda_full,
                "lambda_rate_leave_one_out": lambda_out,
                "delta_lambda_rate": change,
                "shanken_se_lambda_rate_full": shanken_se_full,
                "shanken_se_lambda_rate_leave_one_out": float(
                    leave_one_out.shanken_standard_errors[rate_factor]
                ),
                "standardized_dfbeta": standardized,
                "abs_standardized_dfbeta": abs(standardized),
                "reaches_threshold": bool(abs(standardized) >= MAX_ABS_STANDARDIZED_DFBETA),
            }
        )
    return pd.DataFrame(rows)


def dfbeta_gate_passes(influence: pd.DataFrame) -> bool:
    """Return whether no portfolio reaches the standardized DFBETA bound.

    Args:
        influence: Table produced by :func:`standardized_dfbeta_influence`.

    Returns:
        True when every absolute standardized DFBETA stays below 1.

    Raises:
        ValueError: If the table is empty.
    """
    if influence.empty:
        raise ValueError("Influence table cannot be empty")
    return bool(float(influence["abs_standardized_dfbeta"].max()) < MAX_ABS_STANDARDIZED_DFBETA)


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex([pd.Period(str(value), freq="M") for value in panel["month"]], freq="M")
    panel = panel.drop(columns=["month"]).set_axis(index)

    comparators = pd.read_parquet(COMPARATOR_PARQUET)
    comparator_index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in comparators["month"]], freq="M"
    )
    comparators = comparators.drop(columns=["month"]).set_axis(comparator_index)

    factors = pd.DataFrame(
        {
            MARKET_FACTOR: comparators[MARKET_FACTOR],
            RATE_FACTOR: panel[RATE_INNOVATION_COLUMN],
        }
    )

    asset_sets: dict[str, list[str]] = {}
    for family in FAMILY_MEMBERS:
        asset_sets[family] = sorted(
            column
            for column in panel.columns
            if column.startswith(f"{PORTFOLIO_COLUMN_PREFIX}{family}__")
        )
    asset_sets[BASELINE_PORTFOLIO_SET] = sorted(
        column for column in panel.columns if column.startswith(PORTFOLIO_COLUMN_PREFIX)
    )
    return panel, factors, comparators, asset_sets


def _stored_betas(portfolio_set: str) -> pd.DataFrame:
    stored = pd.read_parquet(FIRST_PASS_PARQUET)
    selected = stored[(stored["model"] == MODEL) & (stored["portfolio_set"] == portfolio_set)]
    if selected.empty:
        raise ValueError(
            f"No stored first-pass betas for model {MODEL!r} and portfolio set {portfolio_set!r}"
        )
    frame = selected.set_index("asset")[[f"beta_{MARKET_FACTOR}", f"beta_{RATE_FACTOR}"]]
    frame.columns = pd.Index([MARKET_FACTOR, RATE_FACTOR])
    return frame.astype(float).sort_index()


def _spanning_payload(spanning: RateSpanningCriterion) -> dict[str, Any]:
    return {
        "executed_regressors": list(spanning.executed_regressors),
        "registered_regressors": list(REGISTERED_SPANNING_REGRESSORS),
        "r2_span": spanning.r2_span,
        "s_span": spanning.s_span,
        "passes": spanning.passes,
        "passes_residual_ratio_form": spanning.passes_residual_ratio_form,
        "market_only_regressors": list(spanning.market_only_regressors),
        "market_only_r2_span": spanning.market_only_r2_span,
        "market_only_s_span": spanning.market_only_s_span,
        "n_months": spanning.n_months,
    }


def _h4a_system_payload(
    *,
    portfolio_set: str,
    role: str,
    report: WeakFactorReport,
    conclusion: H4aIdentificationConclusion,
) -> dict[str, Any]:
    return {
        "portfolio_set": portfolio_set,
        "role": role,
        "n_assets": report.n_assets,
        "n_factors": report.n_factors,
        "rank": report.rank,
        "rank_numerical_tolerance": rank_numerical_tolerance(report),
        "singular_values": list(report.singular_values),
        "condition_number": report.condition_number,
        "beta_dispersion": report.beta_dispersion,
        "standardized_exposure_dispersion": report.standardized_exposure_dispersion,
        "standardized_dispersion_share": conclusion.standardized_dispersion_share,
        "rank_gate_passes": conclusion.rank_gate_passes,
        "standardized_dispersion_passes": conclusion.standardized_dispersion_passes,
        "spanning_passes": conclusion.spanning.passes,
        "passes": conclusion.passes,
        "gate_failures": list(conclusion.gate_failures),
    }


def _leave_one_family_payload(records: pd.DataFrame) -> list[dict[str, Any]]:
    systems: list[dict[str, Any]] = []
    for omitted, group in records.groupby("omitted_family", sort=True):
        families = group.drop_duplicates(subset=["family"])
        systems.append(
            {
                "omitted_family": str(omitted),
                "portfolio_set": str(group["portfolio_set"].iloc[0]),
                "n_assets": int(group["n_assets"].iloc[0]),
                "lambda_rate": float(group["lambda_rate"].iloc[0]),
                "lambda_market": float(group["lambda_market"].iloc[0]),
                "shanken_se_lambda_rate": float(group["shanken_se_lambda_rate"].iloc[0]),
                "max_abs_pi_rate_change": float(group["pi_rate_change"].abs().max()),
                "sign_reversals": int(families["family_sign_reversal"].sum()),
                "materiality_losses": int(families["family_materiality_lost"].sum()),
                "passes": bool(families["family_gate_passes"].all()),
                "evaluated_families": [
                    {
                        "family": str(row["family"]),
                        "baseline_spread": float(row["family_spread_baseline"]),
                        "refit_spread": float(row["family_spread_refit"]),
                        "spread_change": float(row["family_spread_change"]),
                        "baseline_material": bool(row["family_material_baseline"]),
                        "refit_material": bool(row["family_material_refit"]),
                        "sign_reversal": bool(row["family_sign_reversal"]),
                        "materiality_lost": bool(row["family_materiality_lost"]),
                    }
                    for _, row in families.sort_values("family").iterrows()
                ],
            }
        )
    return systems


def _dfbeta_payload(influence: pd.DataFrame) -> dict[str, Any]:
    peak = influence.loc[influence["abs_standardized_dfbeta"].idxmax()]
    return {
        "portfolio_set": str(influence["portfolio_set"].iloc[0]),
        "n_assets": int(influence["n_assets"].iloc[0]),
        "lambda_rate_full": float(influence["lambda_rate_full"].iloc[0]),
        "shanken_se_lambda_rate_full": float(influence["shanken_se_lambda_rate_full"].iloc[0]),
        "max_abs_standardized_dfbeta": float(cast(float, peak["abs_standardized_dfbeta"])),
        "max_abs_standardized_dfbeta_asset": str(peak["asset"]),
        "n_assets_reaching_threshold": int(influence["reaches_threshold"].sum()),
        "passes": dfbeta_gate_passes(influence),
    }


def _thresholds_payload() -> dict[str, Any]:
    return {
        "rank_gate": {
            "rule": "rank must equal the number of priced factors",
            "numerical_tolerance": (
                "max(n_assets, n_factors) * machine_epsilon * largest_singular_value"
            ),
            "source": "research/inference_contract.md, research/weak_factor_registry.csv",
        },
        "standardized_rate_exposure_dispersion": {
            "min_share_of_market_dispersion": MIN_STANDARDIZED_RATE_DISPERSION_SHARE,
            "source": "research/inference_contract.md, research/weak_factor_registry.csv",
        },
        "rate_spanning_criterion": {
            "max_r2_span": MAX_SPANNING_R_SQUARED,
            "min_s_span": MIN_SPANNING_RESIDUAL_RATIO,
            "decision_tolerance": SPANNING_DECISION_TOLERANCE,
            "source": "research/inference_contract.md, research/economic_thresholds.md",
        },
        "leave_one_family_fitted_premium": {
            "material_fitted_premium_spread_monthly_pp": MATERIAL_FITTED_PREMIUM_SPREAD,
            "rule": "no sign reversal and no loss of materiality in any refit",
            "source": "research/economic_thresholds.md, research/inference_contract.md",
        },
        "dfbeta_influence": {
            "max_abs_standardized_dfbeta": MAX_ABS_STANDARDIZED_DFBETA,
            "rule": "the gate fails when any absolute standardized DFBETA reaches the bound",
            "source": "research/inference_contract.md, research/weak_factor_registry.csv",
        },
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def _print_h4a(systems: list[dict[str, Any]], spanning: RateSpanningCriterion) -> None:
    print("H4a cross-sectional identification strength")
    print(
        f"  {GATE_SPANNING:38s} "
        f"{'PASS' if spanning.passes else 'FAIL':4s} "
        f"R2_span={spanning.r2_span:.6f} (max {MAX_SPANNING_R_SQUARED}) "
        f"s_span={spanning.s_span:.6f} (min {MIN_SPANNING_RESIDUAL_RATIO:.6f})"
    )
    print(
        f"  {'rate_spanning_market_only_reference':38s} "
        f"{'----':4s} "
        f"R2_span={spanning.market_only_r2_span:.6f} "
        f"s_span={spanning.market_only_s_span:.6f} (descriptive, no threshold)"
    )
    print(f"  executed regressors: {', '.join(spanning.executed_regressors)}")
    print(f"  n_months: {spanning.n_months}")
    for system in systems:
        print(
            f"  {system['portfolio_set']!s:38s} "
            f"{'PASS' if system['passes'] else 'FAIL':4s} "
            f"[{system['role']}] N={system['n_assets']} "
            f"rank={system['rank']}/{system['n_factors']} "
            f"dispersion_share={float(system['standardized_dispersion_share']):.6f} "
            f"(min {MIN_STANDARDIZED_RATE_DISPERSION_SHARE}) "
            f"failures={','.join(str(name) for name in system['gate_failures']) or 'none'}"
        )


def _print_h4b(
    *,
    leave_one_family: list[dict[str, Any]],
    leave_one_family_passes: bool,
    dfbeta: dict[str, Any],
) -> None:
    print("H4b influence stability")
    print(
        f"  {GATE_LEAVE_ONE_FAMILY:38s} "
        f"{'PASS' if leave_one_family_passes else 'FAIL':4s} "
        f"sign_reversals="
        f"{sum(int(system['sign_reversals']) for system in leave_one_family)} "
        f"materiality_losses="
        f"{sum(int(system['materiality_losses']) for system in leave_one_family)}"
    )
    for system in leave_one_family:
        print(
            f"    omit {system['omitted_family']!s:24s} "
            f"{'PASS' if system['passes'] else 'FAIL':4s} "
            f"N={system['n_assets']} "
            f"lambda_rate={float(system['lambda_rate']): .6f} "
            f"max|d pi_rate|={float(system['max_abs_pi_rate_change']):.6f}"
        )
    print(
        f"  {GATE_DFBETA:38s} "
        f"{'PASS' if dfbeta['passes'] else 'FAIL':4s} "
        f"max|standardized DFBETA|={float(dfbeta['max_abs_standardized_dfbeta']):.6f} "
        f"(bound {MAX_ABS_STANDARDIZED_DFBETA}) "
        f"at {dfbeta['max_abs_standardized_dfbeta_asset']}"
    )


def main() -> None:
    """Execute the H4a and H4b gates and write every diagnostic artifact."""
    panel, factors, comparators, asset_sets = _load_inputs()
    months = len(panel)
    hac_lags = automatic_newey_west_lags(months)
    timestamps = pd.PeriodIndex(panel.index, freq="M").to_timestamp(how="start")
    dated_factors = factors.set_axis(timestamps)

    spanning = rate_spanning_criterion(
        rate_innovation=panel[RATE_INNOVATION_COLUMN],
        comparator_factors=prepare_spanning_regressors(comparators),
    )

    families = sorted(FAMILY_MEMBERS)
    h4a_systems: list[dict[str, Any]] = []
    confirmatory_conclusion: H4aIdentificationConclusion | None = None
    for portfolio_set in (BASELINE_PORTFOLIO_SET, *families):
        stored = _stored_betas(portfolio_set)
        report, conclusion = evaluate_h4a(betas=stored, factors=factors, spanning=spanning)
        role = ROLE_CONFIRMATORY if portfolio_set == BASELINE_PORTFOLIO_SET else ROLE_DESCRIPTIVE
        if portfolio_set == BASELINE_PORTFOLIO_SET:
            confirmatory_conclusion = conclusion
        h4a_systems.append(
            _h4a_system_payload(
                portfolio_set=portfolio_set, role=role, report=report, conclusion=conclusion
            )
        )
    if confirmatory_conclusion is None:  # pragma: no cover - the loop always sets it
        raise ValueError("The confirmatory H4a system was not evaluated")

    joint_columns = asset_sets[BASELINE_PORTFOLIO_SET]
    excess_returns = (
        panel.loc[:, joint_columns]
        .rename(columns={column: short_asset_label(column) for column in joint_columns})
        .set_axis(timestamps)
    )
    baseline = estimate_system(
        excess_returns=excess_returns,
        factors=dated_factors,
        hac_lags=hac_lags,
        portfolio_set=BASELINE_PORTFOLIO_SET,
        model=MODEL,
    )
    stored_joint = _stored_betas(BASELINE_PORTFOLIO_SET)
    beta_difference = float(
        (baseline.betas.sort_index() - stored_joint.loc[:, baseline.betas.columns])
        .abs()
        .to_numpy(dtype=float)
        .max()
    )

    leave_one_family = leave_one_family_records(
        baseline=baseline,
        excess_returns=excess_returns,
        factors=dated_factors,
        hac_lags=hac_lags,
    )
    leave_one_family_passes = leave_one_family_gate_passes(leave_one_family)

    influence_frames: list[pd.DataFrame] = []
    confirmatory_influence = standardized_dfbeta_influence(
        mean_excess_returns=baseline.mean_excess_returns,
        betas=baseline.betas,
        residual_covariance=baseline.residual_covariance,
        factor_covariance=baseline.factor_covariance,
        n_months=baseline.n_months,
        portfolio_set=baseline.portfolio_set,
        model=baseline.model,
    )
    influence_frames.append(confirmatory_influence.assign(role=ROLE_CONFIRMATORY))
    for family in families:
        columns = asset_sets[family]
        family_returns = (
            panel.loc[:, columns]
            .rename(columns={column: short_asset_label(column) for column in columns})
            .set_axis(timestamps)
        )
        family_system = estimate_system(
            excess_returns=family_returns,
            factors=dated_factors,
            hac_lags=hac_lags,
            portfolio_set=family,
            model=MODEL,
        )
        influence_frames.append(
            standardized_dfbeta_influence(
                mean_excess_returns=family_system.mean_excess_returns,
                betas=family_system.betas,
                residual_covariance=family_system.residual_covariance,
                factor_covariance=family_system.factor_covariance,
                n_months=family_system.n_months,
                portfolio_set=family_system.portfolio_set,
                model=family_system.model,
            ).assign(role=ROLE_DESCRIPTIVE)
        )
    influence = pd.concat(influence_frames, ignore_index=True)
    dfbeta_passes = dfbeta_gate_passes(confirmatory_influence)

    h4b_failures = [
        name
        for name, passed in (
            (GATE_LEAVE_ONE_FAMILY, leave_one_family_passes),
            (GATE_DFBETA, dfbeta_passes),
        )
        if not passed
    ]

    leave_one_family_payload = _leave_one_family_payload(leave_one_family)
    dfbeta_summary = _dfbeta_payload(confirmatory_influence)

    for path in (LEAVE_ONE_FAMILY_CSV, DFBETA_CSV):
        path.parent.mkdir(parents=True, exist_ok=True)
    leave_one_family.to_csv(LEAVE_ONE_FAMILY_CSV, index=False, lineterminator="\n")
    influence.to_csv(DFBETA_CSV, index=False, lineterminator="\n")

    _write_json(
        H4A_JSON,
        {
            "script": SCRIPT_NAME,
            "hypothesis": "H4a",
            "family": "weak_factor_diagnostics",
            "model": MODEL,
            "market_factor": MARKET_FACTOR,
            "rate_factor": RATE_FACTOR,
            "confirmatory_portfolio_set": BASELINE_PORTFOLIO_SET,
            "beta_source": FIRST_PASS_PARQUET.as_posix(),
            "n_months": months,
            "thresholds": _thresholds_payload(),
            "rate_spanning_criterion": _spanning_payload(spanning),
            "systems": h4a_systems,
            "passes": confirmatory_conclusion.passes,
            "gate_failures": list(confirmatory_conclusion.gate_failures),
        },
    )
    _write_json(
        H4B_JSON,
        {
            "script": SCRIPT_NAME,
            "hypothesis": "H4b",
            "family": "weak_factor_diagnostics",
            "model": MODEL,
            "market_factor": MARKET_FACTOR,
            "rate_factor": RATE_FACTOR,
            "confirmatory_portfolio_set": BASELINE_PORTFOLIO_SET,
            "n_months": baseline.n_months,
            "thresholds": _thresholds_payload(),
            "fitted_premium_spread_definition": (
                "spread = pi_rate(decile_10) - pi_rate(decile_01) with "
                "pi_rate(i) = beta_rate(i) * lambda_rate"
            ),
            "baseline": {
                "n_assets": baseline.second_pass.n_assets,
                "lambda_rate": float(baseline.second_pass.risk_prices[RATE_FACTOR]),
                "lambda_market": float(baseline.second_pass.risk_prices[MARKET_FACTOR]),
                "shanken_se_lambda_rate": float(
                    baseline.second_pass.shanken_standard_errors[RATE_FACTOR]
                ),
                "shanken_t_lambda_rate": float(
                    baseline.second_pass.shanken_t_statistics[RATE_FACTOR]
                ),
                "family_fitted_premium_spreads": {
                    str(family): float(value)
                    for family, value in family_fitted_premium_spreads(
                        rate_betas=baseline.betas[RATE_FACTOR],
                        lambda_rate=float(baseline.second_pass.risk_prices[RATE_FACTOR]),
                    ).items()
                },
            },
            "leave_one_family_fitted_premium": {
                "passes": leave_one_family_passes,
                "systems": leave_one_family_payload,
            },
            "dfbeta_influence": dfbeta_summary,
            "passes": not h4b_failures,
            "gate_failures": h4b_failures,
        },
    )
    _write_json(
        PROVENANCE_JSON,
        {
            "script": SCRIPT_NAME,
            "hypotheses": ["H4a", "H4b"],
            "multiplicity_family": "weak_factor_diagnostics",
            "model": MODEL,
            "confirmatory_portfolio_set": BASELINE_PORTFOLIO_SET,
            "window": {
                "start": str(panel.index[0]),
                "end": str(panel.index[-1]),
                "months": months,
            },
            "inputs": {
                path.as_posix(): sha256_file(path)
                for path in (
                    PANEL_PARQUET,
                    COMPARATOR_PARQUET,
                    FIRST_PASS_PARQUET,
                    RISK_PRICE_CSV,
                )
            },
            "outputs": {
                path.as_posix(): sha256_file(path)
                for path in (H4A_JSON, H4B_JSON, LEAVE_ONE_FAMILY_CSV, DFBETA_CSV)
            },
            "spanning_regression": {
                "dependent_variable": RATE_INNOVATION_COLUMN,
                "registered_regressors": list(REGISTERED_SPANNING_REGRESSORS),
                "executed_regressors": list(spanning.executed_regressors),
                "market_only_regressors": list(spanning.market_only_regressors),
                "comparator_column_rename": COMPARATOR_MARKET_RENAME,
                "estimator": "ols_with_constant",
                "n_months": spanning.n_months,
            },
            "thresholds": _thresholds_payload(),
            "estimators": {
                "h4a_betas": "loaded from the stored baseline first pass",
                "h4b_first_pass": "ols_with_intercept",
                "h4b_first_pass_covariance": "newey_west",
                "h4b_hac_lags": hac_lags,
                "h4b_second_pass": "no_intercept_ols_article_equation_4",
                "h4b_uncertainty": "shanken_1992",
                "dfbeta_construction": (
                    "leave-one-portfolio-out refit of the second pass only, first-pass betas "
                    "held fixed, standardized by the full-system Shanken standard error of "
                    "lambda_rate"
                ),
                "max_abs_beta_difference_recomputed_vs_stored": beta_difference,
            },
        },
    )

    _print_h4a(h4a_systems, spanning)
    print(
        f"  {'H4a overall (confirmatory system)':38s} "
        f"{'PASS' if confirmatory_conclusion.passes else 'FAIL':4s} "
        f"failures={','.join(confirmatory_conclusion.gate_failures) or 'none'}"
    )
    _print_h4b(
        leave_one_family=leave_one_family_payload,
        leave_one_family_passes=leave_one_family_passes,
        dfbeta=dfbeta_summary,
    )
    print(
        f"  {'H4b overall (confirmatory system)':38s} "
        f"{'PASS' if not h4b_failures else 'FAIL':4s} "
        f"failures={','.join(h4b_failures) or 'none'}"
    )
    print(f"\nRecomputed-versus-stored beta agreement: max abs difference {beta_difference:.3e}")
    print(
        "Wrote "
        + ", ".join(
            path.as_posix()
            for path in (H4A_JSON, H4B_JSON, LEAVE_ONE_FAMILY_CSV, DFBETA_CSV, PROVENANCE_JSON)
        )
    )


if __name__ == "__main__":
    main()
