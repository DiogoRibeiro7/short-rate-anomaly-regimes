"""Parameter-stability tests for factor loadings and risk prices."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, cast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import chi2  # type: ignore[import-untyped]
from scipy.stats import f as f_distribution

from short_rate_anomaly_regimes.reporting.artifact_evidence import (
    artifact_field,
    format_code,
    format_sequence,
    load_json_artifact,
    markdown_table,
    path_bullets,
)

StabilityVerdict = Literal["stable", "unstable", "inconclusive"]


@dataclass(frozen=True, slots=True)
class StabilityConclusion:
    """Concise stability verdict and supporting test failures."""

    verdict: StabilityVerdict
    significant_tests: tuple[str, ...]
    interpretation_note: str


def estimate_regime_interactions(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    regimes: pd.Series,
    *,
    hac_lags: int = 0,
    reference_regime: str | None = None,
) -> pd.DataFrame:
    """Estimate pooled factor models with regime-specific loading interactions."""
    aligned = _align_regime_inputs(returns, factors, regimes)
    factor_names = list(factors.columns)
    regime_order = _regime_order(aligned["regime"])
    reference = reference_regime or regime_order[0]
    rows: list[dict[str, float | str | bool]] = []
    design = _regime_interaction_design(
        aligned[factor_names],
        aligned["regime"],
        reference_regime=reference,
    )
    for asset in returns.columns:
        model = _fit_ols(aligned[str(asset)], design, hac_lags=hac_lags)
        for parameter in model.params.index:
            parameter_name = str(parameter)
            rows.append(
                {
                    "asset": str(asset),
                    "parameter": parameter_name,
                    "coefficient": float(model.params[parameter]),
                    "standard_error": float(model.bse[parameter]),
                    "t_statistic": float(model.tvalues[parameter]),
                    "p_value": float(model.pvalues[parameter]),
                    "reference_regime": reference,
                    "is_regime_interaction": "_x_regime_" in parameter_name,
                    "nobs": float(model.nobs),
                }
            )
    return pd.DataFrame(rows)


def regime_interaction_wald_tests(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    regimes: pd.Series,
    *,
    hac_lags: int = 0,
    reference_regime: str | None = None,
) -> pd.DataFrame:
    """Run joint Wald tests for all factor-loading regime interactions by asset."""
    aligned = _align_regime_inputs(returns, factors, regimes)
    factor_names = list(factors.columns)
    reference = reference_regime or _regime_order(aligned["regime"])[0]
    design = _regime_interaction_design(
        aligned[factor_names],
        aligned["regime"],
        reference_regime=reference,
    )
    prefixes = tuple(f"{factor}_x_regime_" for factor in factor_names)
    interaction_columns = [column for column in design.columns if str(column).startswith(prefixes)]
    if not interaction_columns:
        raise ValueError("No regime interaction columns available for Wald test")
    rows: list[dict[str, float | str]] = []
    for asset in returns.columns:
        model = _fit_ols(aligned[str(asset)], design, hac_lags=hac_lags)
        rows.append(
            {
                "asset": str(asset),
                "test": "joint_regime_factor_interactions",
                **_wald_from_model(model, tuple(interaction_columns)),
            }
        )
    return pd.DataFrame(rows)


def chow_test(
    response: pd.Series,
    regressors: pd.DataFrame,
    *,
    break_month: str,
    min_segment_observations: int,
) -> pd.Series:
    """Run a Chow test at a declared monthly policy boundary."""
    clean = _align_response_regressors(response, regressors)
    break_date = _month_end(break_month)
    before = clean.loc[clean.index <= break_date]
    after = clean.loc[clean.index > break_date]
    if min(before.shape[0], after.shape[0]) < min_segment_observations:
        raise ValueError("Insufficient observations on one side of the known break")
    y_col = "response"
    x_cols = [column for column in clean.columns if column != y_col]
    rss_full, k = _rss_and_k(clean[y_col], clean[x_cols])
    rss_before, _ = _rss_and_k(before[y_col], before[x_cols])
    rss_after, _ = _rss_and_k(after[y_col], after[x_cols])
    numerator = (rss_full - (rss_before + rss_after)) / k
    denominator = (rss_before + rss_after) / (clean.shape[0] - 2 * k)
    statistic = (
        float("inf")
        if denominator <= 1e-30 and numerator > 0.0
        else max(0.0, numerator / denominator)
    )
    p_value = float(f_distribution.sf(statistic, k, clean.shape[0] - 2 * k))
    return pd.Series(
        {
            "test": "chow_known_break",
            "break_month": break_month,
            "statistic": float(statistic),
            "p_value": p_value,
            "df_num": float(k),
            "df_denom": float(clean.shape[0] - 2 * k),
            "nobs": float(clean.shape[0]),
        }
    )


def quandt_andrews_test(
    response: pd.Series,
    regressors: pd.DataFrame,
    *,
    min_segment_observations: int,
) -> pd.Series:
    """Scan admissible unknown break months and report the maximum Chow statistic."""
    clean = _align_response_regressors(response, regressors)
    candidates = clean.index[min_segment_observations:-min_segment_observations]
    if candidates.empty:
        raise ValueError("No admissible break candidates")
    results = [
        chow_test(
            clean["response"],
            clean.drop(columns=["response"]),
            break_month=pd.Timestamp(candidate).strftime("%Y-%m"),
            min_segment_observations=min_segment_observations,
        )
        for candidate in candidates
    ]
    table = pd.DataFrame(results)
    winner = table.sort_values("statistic", ascending=False).iloc[0]
    adjusted_p = min(1.0, float(winner["p_value"]) * len(results))
    return pd.Series(
        {
            "test": "quandt_andrews_unknown_break",
            "break_month": str(winner["break_month"]),
            "statistic": float(winner["statistic"]),
            "p_value": adjusted_p,
            "candidate_count": float(len(results)),
        }
    )


def bai_perron_breaks(
    response: pd.Series,
    regressors: pd.DataFrame,
    *,
    min_segment_observations: int,
    max_breaks: int = 2,
    penalty: float | None = None,
) -> pd.DataFrame:
    """Select multiple structural breaks using a BIC-style penalized RSS rule."""
    if max_breaks < 0:
        raise ValueError("max_breaks must be nonnegative")
    clean = _align_response_regressors(response, regressors)
    nobs = clean.shape[0]
    if nobs < 2 * min_segment_observations:
        raise ValueError("Insufficient observations for multiple-break search")
    y_col = "response"
    x_cols = [column for column in clean.columns if column != y_col]
    base_penalty = penalty if penalty is not None else np.log(nobs)
    candidates = list(range(min_segment_observations, nobs - min_segment_observations + 1))
    best_breaks: tuple[int, ...] = ()
    best_score = _segmented_score(clean[y_col], clean[x_cols], (), base_penalty)
    for n_breaks in range(1, max_breaks + 1):
        for breaks in _valid_break_combinations(
            candidates,
            n_breaks,
            min_segment_observations,
            nobs,
        ):
            score = _segmented_score(clean[y_col], clean[x_cols], breaks, base_penalty)
            if score < best_score:
                best_score = score
                best_breaks = breaks
    rows: list[dict[str, float | str | int]] = []
    for break_number, break_index in enumerate(best_breaks, start=1):
        rows.append(
            {
                "break_number": break_number,
                "break_month": pd.Timestamp(clean.index[break_index - 1]).strftime("%Y-%m"),
                "criterion": float(best_score),
                "min_segment_observations": min_segment_observations,
            }
        )
    return pd.DataFrame(
        rows,
        columns=["break_number", "break_month", "criterion", "min_segment_observations"],
    )


def cusum_test(response: pd.Series, regressors: pd.DataFrame) -> pd.Series:
    """Compute a simple standardized CUSUM instability diagnostic."""
    clean = _align_response_regressors(response, regressors)
    y_col = "response"
    x_cols = [column for column in clean.columns if column != y_col]
    model = _fit_ols(clean[y_col], sm.add_constant(clean[x_cols], has_constant="add"), hac_lags=0)
    residuals = pd.Series(model.resid, index=clean.index)
    sigma = float(residuals.std(ddof=1))
    if sigma == 0.0:
        statistic = 0.0
    else:
        statistic = float((residuals.cumsum() / (sigma * np.sqrt(len(residuals)))).abs().max())
    return pd.Series(
        {
            "test": "cusum_recursive_residuals",
            "statistic": statistic,
            "p_value": float(np.exp(-2.0 * statistic**2)),
            "nobs": float(clean.shape[0]),
        }
    )


def holm_adjust_tests(test_results: pd.DataFrame) -> pd.DataFrame:
    """Apply Holm correction to the registered regime-stability test family."""
    if "p_value" not in test_results.columns:
        raise ValueError("Missing p_value column")
    table = test_results.copy()
    ordered = table["p_value"].astype(float).sort_values()
    adjusted: dict[object, float] = {}
    running = 0.0
    m = ordered.shape[0]
    for rank, (idx, p_value) in enumerate(ordered.items(), start=1):
        running = max(running, min(1.0, float(p_value) * (m - rank + 1)))
        adjusted[idx] = running
    table["holm_p_value"] = pd.Series(adjusted).reindex(table.index).to_numpy(dtype=float)
    table["family"] = "regime_stability"
    return table


def classify_stability(test_results: pd.DataFrame, *, alpha: float = 0.05) -> StabilityConclusion:
    """Classify stability without assigning a causal monetary-policy interpretation."""
    if test_results.empty:
        return StabilityConclusion(
            verdict="inconclusive",
            significant_tests=(),
            interpretation_note="No stability tests were available.",
        )
    p_column = "holm_p_value" if "holm_p_value" in test_results.columns else "p_value"
    significant = test_results.loc[test_results[p_column].astype(float) <= alpha]
    tests = tuple(str(test) for test in significant["test"].drop_duplicates())
    verdict: StabilityVerdict = "unstable" if tests else "stable"
    return StabilityConclusion(
        verdict=verdict,
        significant_tests=tests,
        interpretation_note=(
            "Significant regime interactions indicate parameter instability; they do not by "
            "themselves identify a causal effect of monetary policy."
        ),
    )


def write_regime_outputs(
    *,
    regime_table: pd.DataFrame,
    coefficient_panel: pd.DataFrame,
    test_results: pd.DataFrame,
    conclusion: StabilityConclusion,
    table_dir: Path,
    figure_dir: Path,
    report_path: Path,
) -> None:
    """Write regime tables, figures, and a concise markdown stability report."""
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    regime_table.to_csv(table_dir / "regime_table.csv", index=False)
    coefficient_panel.to_csv(table_dir / "coefficient_panel.csv", index=False)
    test_results.to_csv(table_dir / "stability_tests.csv", index=False)
    (table_dir / "stability_verdict.json").write_text(
        json.dumps(
            {
                "verdict": conclusion.verdict,
                "significant_tests": list(conclusion.significant_tests),
                "interpretation_note": conclusion.interpretation_note,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_break_plot(test_results, output_path=figure_dir / "break_dates.pdf")
    write_rolling_beta_plot(coefficient_panel, output_path=figure_dir / "rolling_betas.pdf")
    report_path.write_text(
        "\n".join(
            [
                "# Regime Stability Report",
                "",
                f"Verdict: `{conclusion.verdict}`",
                "",
                conclusion.interpretation_note,
            ]
        ),
        encoding="utf-8",
    )


def write_break_plot(test_results: pd.DataFrame, *, output_path: Path) -> None:
    """Plot detected break months from known and unknown break tests."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 2.5))
    if "break_month" in test_results.columns and test_results["break_month"].notna().any():
        break_months = pd.to_datetime(test_results["break_month"].dropna()) + pd.offsets.MonthEnd(0)
        ax.eventplot(break_months.map(pd.Timestamp.toordinal), orientation="horizontal")
    ax.set_yticks([])
    ax.set_xlabel("Detected break month")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def write_rolling_beta_plot(coefficient_panel: pd.DataFrame, *, output_path: Path) -> None:
    """Plot available rolling-beta coefficients, or a placeholder axis if absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3))
    if {"window_end", "coefficient", "parameter"} <= set(coefficient_panel.columns):
        for parameter, frame in coefficient_panel.groupby("parameter"):
            if str(parameter) == "const":
                continue
            dates = pd.to_datetime(frame["window_end"]) + pd.offsets.MonthEnd(0)
            ax.plot(dates, frame["coefficient"].to_numpy(dtype=float), label=str(parameter))
        if ax.lines:
            ax.legend()
    ax.set_xlabel("Window end")
    ax.set_ylabel("Coefficient")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def write_blocked_regime_report(*, output_path: Path, missing_inputs: tuple[Path, ...]) -> None:
    """Write a blocked regime report when empirical inputs are absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Regime Stability Report",
                "",
                "Verdict: `blocked_missing_input`",
                "",
                "Regime stability results are blocked until the registered H3 equivalence "
                "and pooled beta-stability artifacts exist. A significant regime interaction "
                "is interpreted as parameter instability, not as monetary-policy causality.",
                "",
                "Missing inputs:",
                *[f"- `{path.as_posix()}`" for path in missing_inputs],
                "",
            ]
        ),
        encoding="utf-8",
    )


def render_regime_evidence_report(*, equivalence_path: Path, pooled_beta_path: Path) -> str:
    """Render the regime report from the frozen H3 diagnostic artifacts.

    Args:
        equivalence_path: Registered H3 regime-equivalence artifact.
        pooled_beta_path: Registered H3 pooled beta-stability artifact.

    Returns:
        The markdown report. Every displayed value is read from the artifacts;
        the registered classification strings are reproduced verbatim.
    """
    equivalence = load_json_artifact(equivalence_path)
    pooled = load_json_artifact(pooled_beta_path)
    lines = [
        "# Regime Stability Report",
        "",
        f"Verdict: {format_code(artifact_field(equivalence, 'classification'))}",
        "",
        f"Hypothesis: {format_code(artifact_field(equivalence, 'hypothesis'))}",
        f"Replication status: {format_code(artifact_field(equivalence, 'replication_status'))}",
        f"Equivalence rule: {format_code(artifact_field(equivalence, 'equivalence_rule'))}",
        f"Bootstrap draws: {format_code(artifact_field(equivalence, 'draws'))}",
        f"Reference regime: {format_code(artifact_field(equivalence, 'reference_regime'))}",
        "Innovation definition: "
        f"{format_code(artifact_field(equivalence, 'innovation_definition'))}",
        "",
        f"Classification basis: {artifact_field(equivalence, 'classification_basis')}",
        "",
        *_regime_equivalence_sections(equivalence),
        *_pooled_beta_sections(pooled),
        "## Artifacts Read",
        "",
        *path_bullets((equivalence_path, pooled_beta_path)),
        "",
    ]
    return "\n".join(lines)


def write_regime_evidence_report(
    *,
    output_path: Path,
    equivalence_path: Path,
    pooled_beta_path: Path,
) -> None:
    """Write the regime report rendered from the frozen H3 artifacts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_regime_evidence_report(
            equivalence_path=equivalence_path,
            pooled_beta_path=pooled_beta_path,
        ),
        encoding="utf-8",
    )


def _regime_equivalence_sections(equivalence: Mapping[str, Any]) -> list[str]:
    gates = artifact_field(equivalence, "gates")
    categories = artifact_field(equivalence, "per_portfolio_decision_categories")
    conditioning = artifact_field(equivalence, "residual_covariance_conditioning")
    sensitivity = artifact_field(equivalence, "global_innovation_sensitivity")
    return [
        "## Registered Equivalence Gates",
        "",
        *markdown_table(
            ["Dimension", "Equivalence Demonstrated"],
            [[dimension, gates[dimension]] for dimension in sorted(gates)],
        ),
        "",
        "Dimensions with a demonstrated exceedance: "
        + format_sequence(artifact_field(equivalence, "dimensions_with_a_demonstrated_exceedance")),
        "",
        "## Per-Portfolio Equivalence Decisions",
        "",
        *markdown_table(
            ["Decision", "Portfolios"],
            [[decision, categories[decision]] for decision in sorted(categories)],
        ),
        "",
        "- Portfolios evaluated: "
        + format_code(artifact_field(equivalence, "portfolios_evaluated")),
        "- Portfolios failing the premium bound: "
        f"{format_code(artifact_field(equivalence, 'portfolios_failing_the_premium_bound'))}",
        "- Maximum absolute point premium change: "
        f"{format_code(artifact_field(equivalence, 'max_absolute_point_premium_change'))}",
        "",
        "## Regime Coverage",
        "",
        "- Standalone second pass: "
        + format_sequence(artifact_field(equivalence, "regimes_with_standalone_second_pass")),
        "- Pooled interactions only: "
        + format_sequence(artifact_field(equivalence, "regimes_limited_to_pooled_interactions")),
        "",
        f"Coverage note: {artifact_field(equivalence, 'coverage_note')}",
        "",
        "## Residual Covariance Conditioning",
        "",
        *markdown_table(
            ["Regime", "Months", "Test Assets", "Excess Months", "Condition Number"],
            [
                [
                    regime,
                    conditioning[regime]["months"],
                    conditioning[regime]["test_assets"],
                    conditioning[regime]["excess_months_over_assets"],
                    conditioning[regime]["residual_covariance_condition_number"],
                ]
                for regime in sorted(conditioning)
            ],
        ),
        "",
        f"Specification caveat: {artifact_field(equivalence, 'specification_test_caveat')}",
        "",
        "## Global Innovation Sensitivity",
        "",
        *markdown_table(
            ["Statistic", "Value"],
            [[statistic, sensitivity[statistic]] for statistic in sorted(sensitivity)],
        ),
        "",
    ]


def _pooled_beta_sections(pooled: Mapping[str, Any]) -> list[str]:
    joint = artifact_field(pooled, "joint_equal_weighted_tests")
    sample = artifact_field(pooled, "sample")
    specification = artifact_field(pooled, "specification")
    return [
        "## Pooled Interaction Beta Stability",
        "",
        f"Classification: {format_code(artifact_field(pooled, 'classification'))}",
        f"Scope: {format_code(artifact_field(pooled, 'scope'))}",
        f"Replication status: {format_code(artifact_field(pooled, 'replication_status'))}",
        "",
        *markdown_table(
            ["Test", "Statistic", "Degrees Of Freedom", "P Value", "Holm P Value"],
            [
                [
                    test,
                    joint[test]["statistic"],
                    joint[test]["df"],
                    joint[test]["p_value"],
                    joint[test]["holm_p_value"],
                ]
                for test in sorted(joint)
            ],
        ),
        "",
        "Significant tests: " + format_sequence(artifact_field(pooled, "significant_tests")),
        "",
        "- Multiplicity adjustment: "
        f"{format_code(artifact_field(pooled, 'multiplicity', 'adjustment'))} across "
        f"{format_code(artifact_field(pooled, 'multiplicity', 'tests_adjusted'))} tests in family "
        f"{format_code(artifact_field(pooled, 'multiplicity', 'family'))}",
        f"- Sample: {format_code(sample['months'])} months, {format_code(sample['start'])} to "
        f"{format_code(sample['end'])}, {format_code(sample['test_assets'])} test assets, vintage "
        f"{format_code(sample['vintage'])}",
        f"- Specification: response {format_code(specification['response'])}, regressors "
        f"{format_sequence(specification['regressors'])}, HAC lags "
        f"{format_code(specification['hac_lags'])}, omitted baseline regime "
        f"{format_code(specification['omitted_baseline_regime'])}",
        "- Boundary sensitivity changed a conclusion: "
        f"{format_code(artifact_field(pooled, 'boundary_sensitivity', 'any_conclusion_changed'))}",
        "- Regimes evidenced only by pooled interactions: "
        + format_sequence(artifact_field(pooled, "pooled_interaction_only_regimes")),
        "",
        f"Interpretation: {artifact_field(pooled, 'interpretation_note')}",
        "",
        f"Scope note: {artifact_field(pooled, 'scope_note')}",
        "",
    ]


def _align_regime_inputs(
    returns: pd.DataFrame,
    factors: pd.DataFrame,
    regimes: pd.Series,
) -> pd.DataFrame:
    _require_datetime_index(returns, "returns")
    _require_datetime_index(factors, "factors")
    if not isinstance(regimes.index, pd.DatetimeIndex):
        raise TypeError("regimes must use a DatetimeIndex")
    if regimes.index.has_duplicates:
        raise ValueError("regimes contain duplicate dates")
    joined = returns.join(factors, how="inner").join(regimes.rename("regime"), how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations across returns, factors, and regimes")
    return joined


def _align_response_regressors(response: pd.Series, regressors: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(response.index, pd.DatetimeIndex):
        raise TypeError("response must use a DatetimeIndex")
    _require_datetime_index(regressors, "regressors")
    joined = regressors.join(response.rename("response"), how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations for stability test")
    return joined


def _require_datetime_index(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex")
    if frame.index.has_duplicates:
        raise ValueError(f"{name} contain duplicate dates")


def _regime_order(regimes: pd.Series) -> tuple[str, ...]:
    return tuple(str(regime) for regime in pd.Series(regimes).drop_duplicates())


def _regime_interaction_design(
    factors: pd.DataFrame,
    regimes: pd.Series,
    *,
    reference_regime: str,
) -> pd.DataFrame:
    regime_values = pd.Series(regimes, index=factors.index, dtype="string")
    if reference_regime not in set(regime_values.dropna().astype(str)):
        raise ValueError(f"Unknown reference regime {reference_regime!r}")
    design = sm.add_constant(factors.astype(float), has_constant="add")
    for regime in _regime_order(regime_values):
        if regime == reference_regime:
            continue
        dummy = (regime_values == regime).astype(float)
        design[f"regime_{regime}"] = dummy
        for factor in factors.columns:
            design[f"{factor}_x_regime_{regime}"] = factors[factor].astype(float) * dummy
    return cast(pd.DataFrame, design.astype(float))


def _fit_ols(response: pd.Series, design: pd.DataFrame, *, hac_lags: int) -> Any:
    if response.shape[0] <= design.shape[1]:
        raise ValueError("Insufficient observations for OLS stability model")
    return sm.OLS(response.astype(float), design.astype(float)).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": hac_lags, "use_correction": False},
    )


def _wald_from_model(model: Any, columns: tuple[str, ...]) -> dict[str, float]:
    params = model.params.loc[list(columns)].to_numpy(dtype=float)
    covariance = model.cov_params().loc[list(columns), list(columns)].to_numpy(dtype=float)
    statistic = float(params.T @ np.linalg.pinv(covariance) @ params)
    df = len(columns)
    return {
        "statistic": statistic,
        "p_value": float(chi2.sf(statistic, df)),
        "df": float(df),
        "nobs": float(model.nobs),
    }


def _rss_and_k(response: pd.Series, regressors: pd.DataFrame) -> tuple[float, int]:
    design = sm.add_constant(regressors.astype(float), has_constant="add")
    if response.shape[0] <= design.shape[1]:
        raise ValueError("Insufficient observations for stability regression")
    model = sm.OLS(response.astype(float), design).fit()
    return float(np.square(model.resid).sum()), int(design.shape[1])


def _segmented_score(
    response: pd.Series,
    regressors: pd.DataFrame,
    breaks: tuple[int, ...],
    penalty: float,
) -> float:
    edges = (0, *breaks, response.shape[0])
    rss = 0.0
    k_total = 0
    for start, end in pairwise(edges):
        segment_y = response.iloc[start:end]
        segment_x = regressors.iloc[start:end]
        segment_rss, k = _rss_and_k(segment_y, segment_x)
        rss += segment_rss
        k_total += k
    return float(
        response.shape[0] * np.log(max(rss, 1e-30) / response.shape[0]) + penalty * k_total
    )


def _valid_break_combinations(
    candidates: list[int],
    n_breaks: int,
    min_segment_observations: int,
    nobs: int,
) -> list[tuple[int, ...]]:
    if n_breaks == 0:
        return [()]
    combinations: list[tuple[int, ...]] = []

    def visit(start_at: int, selected: tuple[int, ...]) -> None:
        if len(selected) == n_breaks:
            edges = (0, *selected, nobs)
            if all(right - left >= min_segment_observations for left, right in pairwise(edges)):
                combinations.append(selected)
            return
        for offset, candidate in enumerate(candidates[start_at:], start=start_at):
            if selected and candidate - selected[-1] < min_segment_observations:
                continue
            visit(offset + 1, (*selected, candidate))

    visit(0, ())
    return combinations


def _month_end(month: str) -> pd.Timestamp:
    return pd.Timestamp(month) + pd.offsets.MonthEnd(0)
