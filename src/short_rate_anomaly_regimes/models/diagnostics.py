"""Specification, weak-factor, and influence diagnostics."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f as f_distribution  # type: ignore[import-untyped]

from short_rate_anomaly_regimes.reporting.artifact_evidence import (
    artifact_field,
    format_code,
    format_sequence,
    load_json_artifact,
    markdown_table,
    path_bullets,
)

RobustnessVerdict = Literal["robust", "conditionally_robust", "fragile", "unidentified"]
RobustnessFamily = Literal[
    "rate_definition",
    "covariance_bootstrap",
    "portfolio_weighting",
    "test_asset_composition",
    "crisis_influence",
    "sample_endpoints",
    "comparator_factor_models",
]

REGISTERED_SPANNING_REGRESSORS: tuple[str, ...] = (
    "Mkt-RF",
    "SMB",
    "HML",
    "UMD",
    "RMW",
    "CMA",
    "LIQ",
    "ME",
    "IA",
    "ROE",
)
"""Registered non-short-rate comparator factors in the frozen regressor order."""

MARKET_REFERENCE_REGRESSOR = "Mkt-RF"
"""Minimal regressor set used for the descriptive market-only spanning reference."""

MAX_SPANNING_R_SQUARED = 0.90
"""Confirmatory upper bound on `R2_span` for the H4a factor-spanning gate."""

MIN_SPANNING_RESIDUAL_RATIO = math.sqrt(0.10)
"""Equivalent lower bound on `s_span`, computed at full double precision.

The declared cutoff is the exact value `sqrt(0.10)`, never a decimal rounded
below it such as `0.3162`, which would let a factor whose residual ratio lies
between the rounded literal and the true bound fail the `R2_span` form of the
rule while passing the `s_span` form.
"""

SPANNING_DECISION_TOLERANCE = 1e-12
"""Declared numerical tolerance applied to both forms of the spanning rule.

`s_span` is computed from residual and target standard deviations, so it agrees
with `sqrt(1 - R2_span)` only to within floating-point rounding. Without a
declared tolerance the two algebraically equivalent forms of the frozen rule can
disagree by one unit in the last place exactly at `R2_span = 0.90`. The
tolerance is applied in the lenient direction for both forms, which matches the
closed pass region `R2_span <= 0.90`, and mirrors the numerical tolerance the
rank gate already declares. It is far below any estimation resolution.
"""

MIN_STANDARDIZED_RATE_DISPERSION_SHARE = 0.10
"""Minimum standardized rate-exposure dispersion as a share of the market value."""

_RATE_INNOVATION_COLUMN = "rate_innovation"


@dataclass(frozen=True, slots=True)
class WeakFactorReport:
    """Weak-factor diagnostics for a beta matrix and factor panel."""

    rank: int
    n_assets: int
    n_factors: int
    singular_values: tuple[float, ...]
    condition_number: float
    beta_dispersion: dict[str, float]
    standardized_exposure_dispersion: dict[str, float]
    factor_redundancy: pd.DataFrame
    irrelevant_factors: tuple[str, ...]
    unidentified: bool


@dataclass(frozen=True, slots=True)
class RateSpanningCriterion:
    """Result of the frozen numerical factor-spanning criterion for H4a.

    Attributes:
        executed_regressors: Registered comparator factors actually used, in the
            frozen order, after dropping factors absent from the intersection.
        r2_span: OLS coefficient of determination of the short-rate innovation on
            a constant plus `executed_regressors`.
        s_span: Residual standard-deviation ratio
            `sd(residual) / sd(rate_innovation)`, equal to `sqrt(1 - r2_span)`.
        passes: Confirmatory decision, `r2_span <= MAX_SPANNING_R_SQUARED` up to
            `SPANNING_DECISION_TOLERANCE`.
        passes_residual_ratio_form: The same decision expressed as
            `s_span >= MIN_SPANNING_RESIDUAL_RATIO` up to the same tolerance.
            It is always equal to `passes`.
        market_only_regressors: Regressors used for the descriptive reference.
        market_only_r2_span: Descriptive `R2_span` against `Mkt-RF` alone.
        market_only_s_span: Descriptive `s_span` against `Mkt-RF` alone.
        n_months: Number of intersection months used by both regressions.
    """

    executed_regressors: tuple[str, ...]
    r2_span: float
    s_span: float
    passes: bool
    passes_residual_ratio_form: bool
    market_only_regressors: tuple[str, ...]
    market_only_r2_span: float
    market_only_s_span: float
    n_months: int


@dataclass(frozen=True, slots=True)
class H4aIdentificationConclusion:
    """Aggregated confirmatory decision for H4a cross-sectional identification.

    Attributes:
        passes: True only when every confirmatory H4a gate passes.
        gate_failures: Registry identifiers of the gates that failed, in
            registry order.
        rank_gate_passes: Result of the `rank_gate` diagnostic.
        standardized_dispersion_passes: Result of the
            `standardized_rate_exposure_dispersion` diagnostic.
        standardized_dispersion_share: Standardized rate-exposure dispersion
            divided by standardized market-exposure dispersion.
        spanning: Full result of the `rate_spanning_criterion` diagnostic.
    """

    passes: bool
    gate_failures: tuple[str, ...]
    rank_gate_passes: bool
    standardized_dispersion_passes: bool
    standardized_dispersion_share: float
    spanning: RateSpanningCriterion


@dataclass(frozen=True, slots=True)
class RobustnessDecisionRules:
    """Predeclared robustness classification thresholds."""

    max_material_risk_price_change: float = 0.25
    max_material_rmse_change: float = 0.25
    max_material_mae_change: float = 0.25
    max_material_alpha_change: float = 0.25
    require_no_sign_reversal: bool = True


@dataclass(frozen=True, slots=True)
class RobustnessConclusion:
    """Robustness verdict and supporting rule failures."""

    verdict: RobustnessVerdict
    rule_failures: tuple[str, ...]


DEFAULT_ROBUSTNESS_DECISION_RULES = RobustnessDecisionRules()


def weak_factor_diagnostics(*, betas: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Return compact diagnostics for weak or irrelevant factors."""
    report = weak_factor_report(betas=betas, factors=factors)
    payload: dict[str, float | int | bool | str] = {
        "rank": report.rank,
        "n_assets": report.n_assets,
        "n_factors": report.n_factors,
        "condition_number": report.condition_number,
        "min_singular_value": min(report.singular_values),
        "max_singular_value": max(report.singular_values),
        "unidentified": report.unidentified,
        "irrelevant_factors": ",".join(report.irrelevant_factors),
    }
    for factor_name, dispersion in report.beta_dispersion.items():
        payload[f"beta_dispersion_{factor_name}"] = dispersion
    for factor_name, dispersion in report.standardized_exposure_dispersion.items():
        payload[f"standardized_exposure_dispersion_{factor_name}"] = dispersion
    return pd.Series(payload)


def weak_factor_report(
    *,
    betas: pd.DataFrame,
    factors: pd.DataFrame,
    irrelevant_dispersion_threshold: float = 1e-8,
) -> WeakFactorReport:
    """Compute rank, singular values, dispersion, and spanning diagnostics."""
    if betas.empty:
        raise ValueError("Beta matrix cannot be empty")
    if factors.empty:
        raise ValueError("Factor panel cannot be empty")
    missing_factors = set(betas.columns) - set(factors.columns)
    if missing_factors:
        raise ValueError(
            f"Factor panel is missing beta columns: {', '.join(sorted(missing_factors))}"
        )
    beta_values = betas.to_numpy(dtype=float)
    singular_values = np.linalg.svd(beta_values, compute_uv=False)
    min_singular = float(singular_values.min())
    max_singular = float(singular_values.max())
    rank = int(np.linalg.matrix_rank(beta_values))
    condition_number = float("inf") if min_singular == 0.0 else max_singular / min_singular
    beta_dispersion = {
        str(column): float(pd.to_numeric(betas[column], errors="raise").std(ddof=1))
        for column in betas.columns
    }
    factor_std = {
        str(column): float(pd.to_numeric(factors[column], errors="raise").dropna().std(ddof=1))
        for column in betas.columns
    }
    standardized_exposures = betas.astype(float).copy()
    for column in standardized_exposures.columns:
        standardized_exposures[column] = standardized_exposures[column] * factor_std[str(column)]
    standardized_exposure_dispersion = {
        str(column): float(standardized_exposures[column].std(ddof=1))
        for column in standardized_exposures.columns
    }
    irrelevant_factors = tuple(
        factor
        for factor, dispersion in standardized_exposure_dispersion.items()
        if dispersion <= irrelevant_dispersion_threshold
    )
    redundancy = factor_redundancy_diagnostics(factors.loc[:, list(betas.columns)])
    unidentified = rank < len(betas.columns) or bool(irrelevant_factors)
    return WeakFactorReport(
        rank=rank,
        n_assets=int(betas.shape[0]),
        n_factors=int(betas.shape[1]),
        singular_values=tuple(float(value) for value in singular_values),
        condition_number=condition_number,
        beta_dispersion=beta_dispersion,
        standardized_exposure_dispersion=standardized_exposure_dispersion,
        factor_redundancy=redundancy,
        irrelevant_factors=irrelevant_factors,
        unidentified=unidentified,
    )


def factor_redundancy_diagnostics(factors: pd.DataFrame) -> pd.DataFrame:
    """Regress each factor on the others to describe numerical redundancy.

    This is a DESCRIPTIVE collinearity screen only. It is not the H4a
    factor-spanning gate and must never be reported as confirmatory: it uses a
    near-degeneracy bound (`r_squared >= 0.99`) that supports the rank and
    conditioning narrative, and it regresses every column on every other column
    rather than the short-rate innovation on the registered comparator set. The
    single confirmatory spanning rule is `rate_spanning_criterion`.

    Args:
        factors: Factor panel whose columns are diagnosed against one another.

    Returns:
        One row per factor with `factor`, `r_squared`, `residual_std`, and the
        descriptive `numerically_redundant` flag. An empty table with those
        columns is returned when fewer than two factors are supplied.

    Raises:
        ValueError: If the factor panel has no complete observations.
    """
    if factors.shape[1] < 2:
        return pd.DataFrame(
            columns=["factor", "r_squared", "residual_std", "numerically_redundant"]
        )
    clean = factors.astype(float).dropna()
    if clean.empty:
        raise ValueError("Factor panel has no complete observations")
    rows: list[dict[str, float | str | bool]] = []
    for factor_name in clean.columns:
        target_std = float(clean[factor_name].std(ddof=1))
        if target_std <= 1e-12:
            rows.append(
                {
                    "factor": str(factor_name),
                    "r_squared": 1.0,
                    "residual_std": 0.0,
                    "numerically_redundant": True,
                }
            )
            continue
        others = clean.drop(columns=[factor_name])
        design = sm.add_constant(others, has_constant="add")
        model = sm.OLS(clean[factor_name], design).fit()
        residual_std = float(model.resid.std(ddof=1))
        rows.append(
            {
                "factor": str(factor_name),
                "r_squared": float(model.rsquared),
                "residual_std": residual_std,
                "numerically_redundant": bool(
                    float(model.rsquared) >= 0.99 or residual_std <= 1e-8
                ),
            }
        )
    return pd.DataFrame(rows)


def rate_spanning_criterion(
    *,
    rate_innovation: pd.Series,
    comparator_factors: pd.DataFrame,
) -> RateSpanningCriterion:
    """Execute the frozen numerical factor-spanning criterion for H4a.

    The criterion is fixed in `research/inference_contract.md` and registered as
    `rate_spanning_criterion` in `research/weak_factor_registry.csv`. The
    short-rate innovation entering the tested model is regressed by OLS on a
    constant plus every registered non-short-rate comparator factor available on
    the common intersection, in the frozen order `Mkt-RF, SMB, HML, UMD, RMW,
    CMA, LIQ, ME, IA, ROE`. Registered factors absent from the intersection are
    dropped and the executed list is returned so it can be stored with the
    artifact. The gate passes when `R2_span <= 0.90`, equivalently when
    `s_span >= sqrt(0.10)`. Both statistics are scale free, so the decision is
    invariant to rescaling the short-rate innovation.

    The descriptive market-only reference against `Mkt-RF` alone is computed on
    the same intersection and carries no threshold.

    Args:
        rate_innovation: Short-rate innovation entering the tested model,
            indexed by the frozen intersection months.
        comparator_factors: Comparator factor panel indexed by month. Only
            columns named in `REGISTERED_SPANNING_REGRESSORS` are used.

    Returns:
        The executed regressor list, `r2_span`, `s_span`, the confirmatory
        decision in both equivalent forms, the descriptive market-only
        reference statistics, and the number of intersection months used.

    Raises:
        ValueError: If either input is empty, if no registered comparator factor
            is available, if `Mkt-RF` is absent so the required descriptive
            reference cannot be reported, if the intersection has too few months
            to estimate the regression, if the short-rate innovation has no
            variation on the intersection, or if the `R2_span` and `s_span`
            forms of the frozen decision rule disagree.
    """
    if rate_innovation.empty:
        raise ValueError("Short-rate innovation cannot be empty")
    if comparator_factors.empty:
        raise ValueError("Comparator factor panel cannot be empty")
    executed = tuple(
        name for name in REGISTERED_SPANNING_REGRESSORS if name in comparator_factors.columns
    )
    if not executed:
        raise ValueError(
            "Comparator panel contains no registered spanning regressor; expected any of: "
            + ", ".join(REGISTERED_SPANNING_REGRESSORS)
        )
    if MARKET_REFERENCE_REGRESSOR not in executed:
        raise ValueError(
            f"Comparator panel is missing {MARKET_REFERENCE_REGRESSOR!r}, so the required "
            "descriptive market-only spanning reference cannot be reported"
        )
    target = pd.to_numeric(rate_innovation, errors="raise").astype(float)
    aligned = pd.concat(
        [
            target.rename(_RATE_INNOVATION_COLUMN),
            comparator_factors.loc[:, list(executed)].astype(float),
        ],
        axis=1,
        join="inner",
    )
    clean = aligned.dropna()
    n_months = int(clean.shape[0])
    if n_months <= len(executed) + 1:
        raise ValueError(
            f"Intersection has {n_months} complete months, which is insufficient for a "
            f"spanning regression on {len(executed)} regressors and a constant"
        )
    rate_std = float(clean[_RATE_INNOVATION_COLUMN].std(ddof=1))
    if rate_std <= 0.0:
        raise ValueError("Short-rate innovation has no variation on the intersection")
    r2_span, s_span = _spanning_statistics(clean, list(executed), rate_std)
    market_r2_span, market_s_span = _spanning_statistics(
        clean, [MARKET_REFERENCE_REGRESSOR], rate_std
    )
    passes = bool(r2_span <= MAX_SPANNING_R_SQUARED + SPANNING_DECISION_TOLERANCE)
    passes_residual_ratio_form = bool(
        s_span >= MIN_SPANNING_RESIDUAL_RATIO - SPANNING_DECISION_TOLERANCE
    )
    if passes != passes_residual_ratio_form:
        raise ValueError(
            "Frozen spanning rule is inconsistent between its equivalent forms: "
            f"R2_span={r2_span!r} against {MAX_SPANNING_R_SQUARED!r} gives {passes}, "
            f"s_span={s_span!r} against {MIN_SPANNING_RESIDUAL_RATIO!r} gives "
            f"{passes_residual_ratio_form}"
        )
    return RateSpanningCriterion(
        executed_regressors=executed,
        r2_span=r2_span,
        s_span=s_span,
        passes=passes,
        passes_residual_ratio_form=passes_residual_ratio_form,
        market_only_regressors=(MARKET_REFERENCE_REGRESSOR,),
        market_only_r2_span=market_r2_span,
        market_only_s_span=market_s_span,
        n_months=n_months,
    )


def classify_h4a_identification_strength(
    *,
    weak_report: WeakFactorReport,
    spanning: RateSpanningCriterion,
    rate_factor: str,
    market_factor: str,
) -> H4aIdentificationConclusion:
    """Aggregate every confirmatory H4a gate into one identification decision.

    H4a fails when the beta matrix is rank deficient, when standardized
    short-rate exposure dispersion falls below 10 percent of standardized market
    exposure dispersion, or when the frozen factor-spanning criterion fails. The
    spanning result is a required argument, so an H4a classification cannot be
    produced, and therefore cannot pass, without the spanning gate being
    executed.

    Args:
        weak_report: Weak-factor report for the same asset and factor set.
        spanning: Executed result of `rate_spanning_criterion`.
        rate_factor: Column name of the short-rate factor in `weak_report`.
        market_factor: Column name of the market factor in `weak_report`.

    Returns:
        The aggregated H4a decision with the registry identifier of every gate
        that failed.

    Raises:
        ValueError: If either factor name is absent from the standardized
            exposure dispersion mapping, or if standardized market exposure
            dispersion is zero so the declared share is undefined.
    """
    dispersion = weak_report.standardized_exposure_dispersion
    missing = [name for name in (rate_factor, market_factor) if name not in dispersion]
    if missing:
        raise ValueError(
            "Standardized exposure dispersion is missing factors: " + ", ".join(sorted(missing))
        )
    market_dispersion = float(dispersion[market_factor])
    if market_dispersion <= 0.0:
        raise ValueError(
            f"Standardized market exposure dispersion for {market_factor!r} is zero, so the "
            "standardized rate-exposure dispersion share is undefined"
        )
    share = float(dispersion[rate_factor]) / market_dispersion
    rank_gate_passes = bool(weak_report.rank >= weak_report.n_factors)
    dispersion_passes = bool(share >= MIN_STANDARDIZED_RATE_DISPERSION_SHARE)
    failures: list[str] = []
    if not rank_gate_passes:
        failures.append("rank_gate")
    if not dispersion_passes:
        failures.append("standardized_rate_exposure_dispersion")
    if not spanning.passes:
        failures.append("rate_spanning_criterion")
    return H4aIdentificationConclusion(
        passes=not failures,
        gate_failures=tuple(failures),
        rank_gate_passes=rank_gate_passes,
        standardized_dispersion_passes=dispersion_passes,
        standardized_dispersion_share=share,
        spanning=spanning,
    )


def _spanning_statistics(
    clean: pd.DataFrame, regressors: list[str], rate_std: float
) -> tuple[float, float]:
    design = sm.add_constant(clean.loc[:, regressors], has_constant="add")
    model = sm.OLS(clean[_RATE_INNOVATION_COLUMN], design).fit()
    return float(model.rsquared), float(model.resid.std(ddof=1)) / rate_std


def holm_correction(p_values: pd.Series) -> pd.DataFrame:
    """Apply Holm correction within one registered robustness family."""
    if p_values.empty:
        raise ValueError("p_values cannot be empty")
    clean = pd.to_numeric(p_values, errors="raise").sort_values()
    m = clean.shape[0]
    adjusted_values: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, p_value) in enumerate(clean.items(), start=1):
        adjusted = min(1.0, float(p_value) * (m - rank + 1))
        running_max = max(running_max, adjusted)
        adjusted_values[str(name)] = running_max
    return pd.DataFrame(
        {
            "p_value": p_values.astype(float),
            "holm_p_value": pd.Series(adjusted_values).reindex(p_values.index),
            "family": p_values.name or "unregistered_family",
        }
    )


def specification_table(
    specifications: pd.DataFrame,
    *,
    family_column: str = "family",
    p_value_column: str = "p_value",
) -> pd.DataFrame:
    """Return all registered robustness specifications with within-family Holm p-values."""
    if family_column not in specifications.columns:
        raise ValueError(f"Missing family column {family_column!r}")
    if p_value_column not in specifications.columns:
        raise ValueError(f"Missing p-value column {p_value_column!r}")
    frames: list[pd.DataFrame] = []
    for family, family_frame in specifications.groupby(family_column, sort=True):
        correction = holm_correction(family_frame[p_value_column].rename(str(family)))
        joined = family_frame.copy()
        joined["holm_p_value"] = correction["holm_p_value"].to_numpy(dtype=float)
        frames.append(joined)
    return pd.concat(frames, ignore_index=True)


def economic_diagnostics(
    baseline: pd.Series,
    alternatives: pd.DataFrame,
    *,
    material_change_threshold: float = 0.25,
) -> pd.DataFrame:
    """Compute economic changes across robustness specifications."""
    required = {"risk_price", "rmse", "mae", "max_alpha", "explained_spread"}
    missing_baseline = required - set(baseline.index)
    missing_alternatives = required - set(alternatives.columns)
    if missing_baseline:
        raise ValueError(f"Baseline is missing metrics: {', '.join(sorted(missing_baseline))}")
    if missing_alternatives:
        raise ValueError(
            f"Alternatives are missing metrics: {', '.join(sorted(missing_alternatives))}"
        )
    rows: list[dict[str, float | str | bool]] = []
    for name, row in alternatives.iterrows():
        risk_price_change = _relative_change(
            float(baseline["risk_price"]), float(row["risk_price"])
        )
        rmse_change = _relative_change(float(baseline["rmse"]), float(row["rmse"]))
        mae_change = _relative_change(float(baseline["mae"]), float(row["mae"]))
        alpha_change = _relative_change(float(baseline["max_alpha"]), float(row["max_alpha"]))
        sign_reversal = np.sign(float(baseline["risk_price"])) != np.sign(float(row["risk_price"]))
        material_change = any(
            abs(value) >= material_change_threshold
            for value in (risk_price_change, rmse_change, mae_change, alpha_change)
        )
        rows.append(
            {
                "specification": str(name),
                "risk_price_change": risk_price_change,
                "rmse_change": rmse_change,
                "mae_change": mae_change,
                "max_alpha_change": alpha_change,
                "explained_spread_change": float(row["explained_spread"])
                - float(baseline["explained_spread"]),
                "sign_reversal": bool(sign_reversal),
                "material_change": bool(material_change),
            }
        )
    return pd.DataFrame(rows)


def classify_robustness(
    weak_report: WeakFactorReport,
    economic_table: pd.DataFrame,
    *,
    rules: RobustnessDecisionRules = DEFAULT_ROBUSTNESS_DECISION_RULES,
    h4a: H4aIdentificationConclusion | None = None,
) -> RobustnessConclusion:
    """Classify robustness using predeclared decision rules.

    Args:
        weak_report: Weak-factor report for the tested system.
        economic_table: Economic-change table across registered specifications.
        rules: Predeclared robustness thresholds.
        h4a: Aggregated H4a identification decision. When supplied, any failed
            H4a gate, including the frozen factor-spanning criterion, forces the
            `unidentified` verdict before any economic rule is consulted.

    Returns:
        The robustness verdict together with the rule failures that produced it.
    """
    failures: list[str] = []
    if h4a is not None and not h4a.passes:
        return RobustnessConclusion(verdict="unidentified", rule_failures=h4a.gate_failures)
    if weak_report.unidentified:
        return RobustnessConclusion(verdict="unidentified", rule_failures=("weak_identification",))
    if rules.require_no_sign_reversal and economic_table["sign_reversal"].any():
        failures.append("risk_price_sign_reversal")
    if (economic_table["risk_price_change"].abs() > rules.max_material_risk_price_change).any():
        failures.append("material_risk_price_change")
    if (economic_table["rmse_change"].abs() > rules.max_material_rmse_change).any():
        failures.append("material_rmse_change")
    if (economic_table["mae_change"].abs() > rules.max_material_mae_change).any():
        failures.append("material_mae_change")
    if (economic_table["max_alpha_change"].abs() > rules.max_material_alpha_change).any():
        failures.append("material_alpha_change")
    if not failures:
        verdict: RobustnessVerdict = "robust"
    elif len(failures) <= 2:
        verdict = "conditionally_robust"
    else:
        verdict = "fragile"
    return RobustnessConclusion(verdict=verdict, rule_failures=tuple(failures))


def write_robustness_outputs(
    *,
    weak_report: WeakFactorReport,
    specification_results: pd.DataFrame,
    economic_results: pd.DataFrame,
    conclusion: RobustnessConclusion,
    diagnostics_path: Path,
    table_path: Path,
    report_path: Path,
    h4a: H4aIdentificationConclusion | None = None,
) -> None:
    """Write robustness diagnostics, tables, and a concise markdown report.

    Args:
        weak_report: Weak-factor report for the tested system.
        specification_results: Registered specifications with Holm p-values.
        economic_results: Economic-change table across those specifications.
        conclusion: Robustness verdict to record.
        diagnostics_path: Destination for the JSON diagnostics payload.
        table_path: Destination for the specification table.
        report_path: Destination for the markdown report.
        h4a: Aggregated H4a decision. When supplied, the executed spanning
            regressor list and both spanning statistics are stored with the
            artifact as the frozen criterion requires.
    """
    for path in (diagnostics_path, table_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_payload: dict[str, object] = {
        "weak_factor": {
            "rank": weak_report.rank,
            "n_assets": weak_report.n_assets,
            "n_factors": weak_report.n_factors,
            "singular_values": list(weak_report.singular_values),
            "condition_number": weak_report.condition_number,
            "beta_dispersion": weak_report.beta_dispersion,
            "standardized_exposure_dispersion": weak_report.standardized_exposure_dispersion,
            "irrelevant_factors": list(weak_report.irrelevant_factors),
            "unidentified": weak_report.unidentified,
        },
        "classification": asdict(conclusion),
    }
    if h4a is not None:
        diagnostics_payload["h4a_identification_strength"] = {
            "passes": h4a.passes,
            "gate_failures": list(h4a.gate_failures),
            "rank_gate_passes": h4a.rank_gate_passes,
            "standardized_dispersion_passes": h4a.standardized_dispersion_passes,
            "standardized_dispersion_share": h4a.standardized_dispersion_share,
            "rate_spanning_criterion": {
                "executed_regressors": list(h4a.spanning.executed_regressors),
                "r2_span": h4a.spanning.r2_span,
                "s_span": h4a.spanning.s_span,
                "passes": h4a.spanning.passes,
                "max_r2_span": MAX_SPANNING_R_SQUARED,
                "min_s_span": MIN_SPANNING_RESIDUAL_RATIO,
                "market_only_regressors": list(h4a.spanning.market_only_regressors),
                "market_only_r2_span": h4a.spanning.market_only_r2_span,
                "market_only_s_span": h4a.spanning.market_only_s_span,
                "n_months": h4a.spanning.n_months,
            },
        }
    diagnostics_path.write_text(
        json.dumps(diagnostics_payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    specification_results.to_csv(table_path, index=False, lineterminator="\n")
    report_path.write_text(
        "\n".join(
            [
                "# Robustness Report",
                "",
                f"Verdict: `{conclusion.verdict}`",
                "",
                "Rule failures: "
                + (", ".join(conclusion.rule_failures) if conclusion.rule_failures else "none"),
                "",
                "All registered specifications must be shown; significant-only reporting "
                "is prohibited.",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def render_robustness_evidence_report(
    *,
    materiality_path: Path,
    identification_path: Path,
    influence_path: Path,
    precision_path: Path,
) -> str:
    """Render the robustness report from the frozen H1 and weak-factor artifacts.

    Args:
        materiality_path: Registered H1 incremental-pricing materiality artifact.
        identification_path: Registered H4a identification-strength artifact.
        influence_path: Registered H4b influence-stability artifact.
        precision_path: Registered H4c fitted-premium precision artifact.

    Returns:
        The markdown report. Every displayed value is read from the artifacts and
        every registered gate is reported, whether it passed or failed.
    """
    materiality = load_json_artifact(materiality_path)
    identification = load_json_artifact(identification_path)
    influence = load_json_artifact(influence_path)
    precision = load_json_artifact(precision_path)
    headline = str(artifact_field(materiality, "headline_asset_set"))
    classification = artifact_field(
        materiality, "asset_sets", headline, "h1_primary_classification"
    )
    lines = [
        "# Robustness Report",
        "",
        f"Verdict: {format_code(classification)}",
        "",
        f"Verdict source: `asset_sets.{headline}.h1_primary_classification` in "
        f"`{materiality_path.as_posix()}`",
        f"Hypothesis: {format_code(artifact_field(materiality, 'hypothesis'))}",
        f"Replication status: {format_code(artifact_field(materiality, 'replication_status'))}",
        "Primary comparator: "
        f"{format_code(artifact_field(materiality, 'primary_comparator', 'model'))}, selected "
        "after observing RMSE: "
        + format_code(
            artifact_field(materiality, "primary_comparator", "selected_after_observing_rmse")
        ),
        "",
        f"Decision rule: {artifact_field(materiality, 'decision_rule')}",
        "",
        f"Multiplicity: {artifact_field(materiality, 'multiplicity', 'status')}",
        "",
        *_h1_sections(materiality, headline=headline),
        *_weak_factor_sections(
            identification=identification,
            influence=influence,
            precision=precision,
        ),
        "All registered gates are reported above, whether they passed or failed; "
        "significant-only robustness reporting is prohibited.",
        "",
        "## Artifacts Read",
        "",
        *path_bullets((materiality_path, identification_path, influence_path, precision_path)),
        "",
    ]
    return "\n".join(lines)


def write_robustness_evidence_report(
    *,
    output_path: Path,
    materiality_path: Path,
    identification_path: Path,
    influence_path: Path,
    precision_path: Path,
) -> None:
    """Write the robustness report rendered from the frozen registered artifacts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_robustness_evidence_report(
            materiality_path=materiality_path,
            identification_path=identification_path,
            influence_path=influence_path,
            precision_path=precision_path,
        ),
        encoding="utf-8",
        newline="\n",
    )


def write_blocked_robustness_report(*, output_path: Path, missing_inputs: tuple[Path, ...]) -> None:
    """Write a blocked robustness report when the registered artifacts are absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Robustness Report",
                "",
                "Verdict: `unidentified`",
                "",
                "Robustness diagnostics are blocked until the registered H1 materiality and "
                "weak-factor artifacts exist.",
                "",
                "Missing inputs:",
                *path_bullets(missing_inputs),
                "",
                "No significant-only robustness reporting has been performed.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def _h1_sections(materiality: Mapping[str, Any], *, headline: str) -> list[str]:
    gates = sorted(artifact_field(materiality, "thresholds"))
    asset_sets = artifact_field(materiality, "asset_sets")
    headline_primary = artifact_field(materiality, "asset_sets", headline, "primary_comparison")
    lines = [
        f"## H1 Primary Gates On The Headline Asset Set `{headline}`",
        "",
    ]
    for model in sorted(headline_primary):
        comparison = headline_primary[model]
        lines.extend(
            [
                f"Treatment model {format_code(model)}, comparator "
                f"{format_code(comparison['comparator_model'])}, "
                f"{format_code(comparison['n_assets'])} assets, "
                f"{format_code(comparison['n_months'])} months, "
                f"{format_code(comparison['n_gates_passed'])} of "
                f"{format_code(comparison['n_gates_total'])} gates passed, classification "
                f"{format_code(comparison['classification'])}",
                "",
                *markdown_table(
                    [
                        "Gate",
                        "Comparison",
                        "Threshold",
                        "Comparator",
                        "Treatment",
                        "Observed",
                        "Passed",
                    ],
                    _h1_gate_rows(comparison, gates),
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## H1 Classification By Asset Set",
            "",
            *markdown_table(
                [
                    "Asset Set",
                    "Treatment Model",
                    "Primary Comparator",
                    "Primary Classification",
                    "Secondary Comparator",
                    "Secondary Classification",
                ],
                _h1_asset_set_rows(asset_sets),
            ),
            "",
            "## H1 Gate Values By Asset Set And Comparison",
            "",
            "Every classification in the table above is derived from the gate values below; "
            "no asset set is classified from evidence that is not displayed.",
            "",
            *markdown_table(
                [
                    "Asset Set",
                    "Treatment Model",
                    "Comparison Role",
                    "Comparator Model",
                    "Gate",
                    "Comparison",
                    "Threshold",
                    "Comparator Value",
                    "Treatment Value",
                    "Observed",
                    "Passed",
                ],
                _h1_all_gate_rows(asset_sets, gates),
            ),
            "",
        ]
    )
    return lines


def _h1_gate_rows(comparison: Mapping[str, Any], gates: Sequence[str]) -> list[list[Any]]:
    return [
        [
            gate,
            comparison[f"{gate}__comparison"],
            comparison[f"{gate}__threshold"],
            comparison[f"{gate}__comparator_value"],
            comparison[f"{gate}__treatment_value"],
            comparison[f"{gate}__observed"],
            comparison[f"{gate}__passed"],
        ]
        for gate in gates
    ]


#: Registered comparison slots stored under every H1 asset-set record. Both are
#: rendered so the report displays a gate value for every classification it lists.
H1_COMPARISON_SLOTS: tuple[str, ...] = ("primary_comparison", "secondary_adversarial_comparison")


def _h1_all_gate_rows(asset_sets: Mapping[str, Any], gates: Sequence[str]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for asset_set in sorted(asset_sets):
        record = asset_sets[asset_set]
        for slot in H1_COMPARISON_SLOTS:
            comparisons = record[slot]
            for model in sorted(comparisons):
                comparison = comparisons[model]
                rows.extend(
                    [
                        asset_set,
                        model,
                        comparison["comparison_role"],
                        comparison["comparator_model"],
                        *gate_row,
                    ]
                    for gate_row in _h1_gate_rows(comparison, gates)
                )
    return rows


def _h1_asset_set_rows(asset_sets: Mapping[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for asset_set in sorted(asset_sets):
        primary = asset_sets[asset_set]["primary_comparison"]
        secondary = asset_sets[asset_set]["secondary_adversarial_comparison"]
        for model in sorted(primary):
            rows.append(
                [
                    asset_set,
                    model,
                    primary[model]["comparator_model"],
                    primary[model]["classification"],
                    secondary[model]["comparator_model"],
                    secondary[model]["classification"],
                ]
            )
    return rows


def _weak_factor_sections(
    *,
    identification: Mapping[str, Any],
    influence: Mapping[str, Any],
    precision: Mapping[str, Any],
) -> list[str]:
    confirmatory = _confirmatory_system(identification)
    spanning = artifact_field(identification, "rate_spanning_criterion")
    thresholds = artifact_field(identification, "thresholds")
    dfbeta = artifact_field(influence, "dfbeta_influence")
    leave_one_family = artifact_field(influence, "leave_one_family_fitted_premium")
    baseline = artifact_field(influence, "baseline")
    dispersion_floor = thresholds["standardized_rate_exposure_dispersion"][
        "min_share_of_market_dispersion"
    ]
    spanning_thresholds = thresholds["rate_spanning_criterion"]
    dfbeta_bound = thresholds["dfbeta_influence"]["max_abs_standardized_dfbeta"]
    return [
        "## Weak-Factor Gate Outcomes",
        "",
        *markdown_table(
            ["Hypothesis", "Outcome", "Gate Failures"],
            [
                [
                    artifact_field(identification, "hypothesis"),
                    artifact_field(identification, "passes"),
                    format_sequence(artifact_field(identification, "gate_failures")),
                ],
                [
                    artifact_field(influence, "hypothesis"),
                    artifact_field(influence, "passes"),
                    format_sequence(artifact_field(influence, "gate_failures")),
                ],
                [
                    artifact_field(precision, "hypothesis"),
                    artifact_field(precision, "classification"),
                    format_sequence(artifact_field(precision, "failing_families")),
                ],
            ],
        ),
        "",
        "### H4a Identification Strength",
        "",
        f"- Confirmatory system: {format_code(confirmatory['portfolio_set'])}, rank "
        f"{format_code(confirmatory['rank'])} of {format_code(confirmatory['n_factors'])} priced "
        f"factors, condition number {format_code(confirmatory['condition_number'])}",
        "- Standardized rate-exposure dispersion share: "
        f"{format_code(confirmatory['standardized_dispersion_share'])} against a floor of "
        f"{format_code(dispersion_floor)}",
        f"- Spanning R squared: {format_code(spanning['r2_span'])} against a ceiling of "
        f"{format_code(spanning_thresholds['max_r2_span'])}; residual ratio "
        f"{format_code(spanning['s_span'])} against a floor of "
        f"{format_code(spanning_thresholds['min_s_span'])}",
        "- Spanning regressors: "
        + format_sequence(spanning["executed_regressors"])
        + f", over {format_code(spanning['n_months'])} months",
        "",
        "### H4b Influence Stability",
        "",
        "- Maximum absolute standardized DFBETA: "
        f"{format_code(dfbeta['max_abs_standardized_dfbeta'])} at "
        f"{format_code(dfbeta['max_abs_standardized_dfbeta_asset'])}, against a bound of "
        f"{format_code(dfbeta_bound)}",
        f"- Assets reaching the bound: {format_code(dfbeta['n_assets_reaching_threshold'])} of "
        f"{format_code(dfbeta['n_assets'])}",
        f"- Leave-one-family refits pass: {format_code(leave_one_family['passes'])} across "
        f"{format_code(len(leave_one_family['systems']))} refits",
        f"- Baseline rate risk price: {format_code(baseline['lambda_rate'])}, Shanken standard "
        f"error {format_code(baseline['shanken_se_lambda_rate'])}, t "
        f"{format_code(baseline['shanken_t_lambda_rate'])}",
        "",
        "### H4c Fitted-Premium Precision",
        "",
        f"- Estimand: {format_code(artifact_field(precision, 'estimand'))}",
        f"- Economic direction bound: "
        f"{format_code(artifact_field(precision, 'economic_direction_bound'))}, "
        f"{format_code(artifact_field(precision, 'draws'))} draws, block length "
        f"{format_code(artifact_field(precision, 'block_length'))} selected by "
        f"{format_code(artifact_field(precision, 'block_length_selected_by'))}",
        "",
        "The registered H4c gate is evaluated on the 95 percent bootstrap interval, so the "
        "interval displayed here is the one the gate reads.",
        "",
        *markdown_table(
            ["Family", "Point Estimate", "Lower 95", "Upper 95", "Spans Both Directions", "Gate"],
            [
                [
                    family["family"],
                    family["point_estimate"],
                    family["lower_95"],
                    family["upper_95"],
                    family["interval_spans_both_directions"],
                    family["h4c_gate"],
                ]
                for family in artifact_field(precision, "per_family")
            ],
        ),
        "",
    ]


def _confirmatory_system(identification: Mapping[str, Any]) -> Mapping[str, Any]:
    systems: list[Mapping[str, Any]] = list(artifact_field(identification, "systems"))
    confirmatory = [system for system in systems if system["role"] == "confirmatory"]
    if not confirmatory:
        raise ValueError("H4a artifact contains no confirmatory system")
    return confirmatory[0]


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


def _relative_change(baseline: float, alternative: float) -> float:
    if baseline == 0.0:
        return float("inf") if alternative != 0.0 else 0.0
    return (alternative - baseline) / abs(baseline)
