"""Temporal-extension utilities with explicit vintage separation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import cast

import matplotlib
import numpy as np
import pandas as pd
from matplotlib.dates import date2num
from scipy.stats import spearmanr  # type: ignore[import-untyped]

from short_rate_anomaly_regimes.reporting.artifact_evidence import (
    artifact_field,
    dataframe_table,
    format_code,
    load_json_artifact,
    markdown_table,
    path_bullets,
)

matplotlib.use("Agg")


@dataclass(frozen=True, slots=True)
class TemporalFreeze:
    """Frozen date and vintage metadata for the post-2013 extension."""

    baseline_start: str
    baseline_end: str
    extension_start: str
    latest_common_month: str
    retrieval_date: str
    baseline_vintage_label: str
    extension_vintage_label: str
    revision_policy: str = "audit_separately"


@dataclass(frozen=True, slots=True)
class TemporalPanelBuild:
    """Vintage-labelled extension panel and its audit tables."""

    monthly_panel: pd.DataFrame
    revision_audit: pd.DataFrame
    universe: pd.DataFrame
    observation_summary: pd.DataFrame


def build_temporal_panel(
    *,
    locked_baseline: pd.DataFrame,
    extension_vintage: pd.DataFrame,
    freeze: TemporalFreeze,
    allow_revisions: bool = False,
    revision_tolerance: float = 1e-12,
) -> TemporalPanelBuild:
    """Append post-2013 rows while keeping revised historical values separate."""
    _require_datetime_index(locked_baseline, "locked_baseline")
    _require_datetime_index(extension_vintage, "extension_vintage")
    if freeze.revision_policy != "audit_separately":
        raise ValueError("Temporal extension requires revision_policy='audit_separately'")

    baseline_end = _month_end(freeze.baseline_end)
    extension_start = _month_end(freeze.extension_start)
    latest_common = _month_end(freeze.latest_common_month)
    if extension_start <= baseline_end:
        raise ValueError("extension_start must be after baseline_end")
    if latest_common < extension_start:
        raise ValueError("latest_common_month must be on or after extension_start")

    baseline_window = locked_baseline.sort_index().loc[:baseline_end]
    if baseline_window.empty:
        raise ValueError("Locked baseline contains no observations through baseline_end")
    extension_sorted = extension_vintage.sort_index()
    compatible_series = [
        str(column) for column in baseline_window.columns if column in extension_sorted.columns
    ]
    if not compatible_series:
        raise ValueError("No compatible series between locked baseline and extension vintage")

    audit = revision_audit_table(
        locked_baseline=baseline_window.loc[:, compatible_series],
        revised_history=extension_sorted.loc[:baseline_end, compatible_series],
        tolerance=revision_tolerance,
    )
    if not audit.empty and not allow_revisions:
        raise ValueError(
            "Revised baseline-period data detected; store them separately and review "
            "revision_audit before enabling allow_revisions"
        )

    extension_window = extension_sorted.loc[extension_start:latest_common, compatible_series]
    if extension_window.empty:
        raise ValueError("Extension vintage contains no post-baseline observations")

    monthly_panel = pd.concat(
        [
            _to_long_panel(
                baseline_window.loc[:, compatible_series],
                vintage=freeze.baseline_vintage_label,
                sample_period="locked_baseline",
            ),
            _to_long_panel(
                extension_window,
                vintage=freeze.extension_vintage_label,
                sample_period="post_publication_extension",
            ),
        ],
        ignore_index=True,
    )
    universe = extension_universe_table(
        locked_baseline=locked_baseline,
        extension_vintage=extension_vintage,
        included_series=tuple(compatible_series),
    )
    observations = observation_summary_table(monthly_panel)
    return TemporalPanelBuild(
        monthly_panel=monthly_panel,
        revision_audit=audit,
        universe=universe,
        observation_summary=observations,
    )


def revision_audit_table(
    *,
    locked_baseline: pd.DataFrame,
    revised_history: pd.DataFrame,
    tolerance: float = 1e-12,
) -> pd.DataFrame:
    """Quantify overlap revisions without mutating the locked baseline panel."""
    _require_datetime_index(locked_baseline, "locked_baseline")
    _require_datetime_index(revised_history, "revised_history")
    common_dates = locked_baseline.index.intersection(revised_history.index).sort_values()
    common_columns = [
        str(column) for column in locked_baseline.columns if column in revised_history
    ]
    rows: list[dict[str, float | str]] = []
    for date in common_dates:
        for series_id in common_columns:
            baseline_value = locked_baseline.loc[date, series_id]
            revised_value = revised_history.loc[date, series_id]
            if pd.isna(baseline_value) and pd.isna(revised_value):
                continue
            difference = float(revised_value) - float(baseline_value)
            if abs(difference) <= tolerance:
                continue
            denominator = abs(float(baseline_value))
            rows.append(
                {
                    "month": pd.Timestamp(date).strftime("%Y-%m"),
                    "series_id": series_id,
                    "baseline_value": float(baseline_value),
                    "revised_value": float(revised_value),
                    "absolute_revision": difference,
                    "relative_revision": np.inf if denominator == 0.0 else difference / denominator,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "month",
            "series_id",
            "baseline_value",
            "revised_value",
            "absolute_revision",
            "relative_revision",
        ],
    )


def extension_universe_table(
    *,
    locked_baseline: pd.DataFrame,
    extension_vintage: pd.DataFrame,
    included_series: tuple[str, ...],
) -> pd.DataFrame:
    """Report compatible and reduced-universe series without rewriting the baseline."""
    baseline_series = {str(column) for column in locked_baseline.columns}
    extension_series = {str(column) for column in extension_vintage.columns}
    included = set(included_series)
    rows: list[dict[str, bool | str]] = []
    for series_id in sorted(baseline_series | extension_series):
        in_baseline = series_id in baseline_series
        in_extension = series_id in extension_series
        if series_id in included:
            status = "included_compatible_definition"
        elif in_baseline and not in_extension:
            status = "baseline_only_not_extended"
        else:
            status = "extension_only_not_in_baseline"
        rows.append(
            {
                "series_id": series_id,
                "in_locked_baseline": in_baseline,
                "in_extension_vintage": in_extension,
                "included_in_extension": series_id in included,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def observation_summary_table(monthly_panel: pd.DataFrame) -> pd.DataFrame:
    """Count observations by sample period and vintage label."""
    required = {"sample_period", "vintage", "value"}
    missing = required - set(monthly_panel.columns)
    if missing:
        raise ValueError(f"Monthly panel is missing columns: {', '.join(sorted(missing))}")
    return (
        monthly_panel.dropna(subset=["value"])
        .groupby(["sample_period", "vintage"], as_index=False)
        .agg(
            observations=("value", "size"),
            first_month=("month", "min"),
            last_month=("month", "max"),
            n_series=("series_id", "nunique"),
        )
    )


def evaluate_frozen_pricing(
    *,
    post_returns: pd.DataFrame,
    frozen_betas: pd.DataFrame,
    frozen_risk_prices: pd.Series,
) -> tuple[pd.DataFrame, pd.Series]:
    """Apply December 2013 frozen betas and risk prices to post-2013 mean returns."""
    if post_returns.empty:
        raise ValueError("post_returns cannot be empty")
    if frozen_betas.empty:
        raise ValueError("frozen_betas cannot be empty")
    common_assets = [asset for asset in post_returns.columns if asset in frozen_betas.index]
    if not common_assets:
        raise ValueError("No common assets between post returns and frozen betas")
    factor_prices = frozen_risk_prices.drop(labels=["const"], errors="ignore")
    missing_factors = set(factor_prices.index) - set(frozen_betas.columns)
    if missing_factors:
        raise ValueError(f"Frozen betas missing factors: {', '.join(sorted(missing_factors))}")

    intercept = float(frozen_risk_prices.get("const", 0.0))
    betas = frozen_betas.loc[common_assets, list(factor_prices.index)].astype(float)
    expected = pd.Series(
        intercept + betas.to_numpy(dtype=float) @ factor_prices.to_numpy(dtype=float),
        index=common_assets,
        name="frozen_expected_mean_return",
    )
    observed = (
        post_returns.loc[:, common_assets].astype(float).mean(axis=0).rename("post_mean_return")
    )
    errors = (observed - expected).rename("frozen_pricing_error")
    table = pd.DataFrame(
        {
            "asset": common_assets,
            "post_mean_return": observed.to_numpy(dtype=float),
            "frozen_expected_mean_return": expected.to_numpy(dtype=float),
            "frozen_pricing_error": errors.to_numpy(dtype=float),
        }
    )
    summary = pricing_error_summary(errors=errors, observed=observed)
    return table, summary


def pricing_error_summary(*, errors: pd.Series, observed: pd.Series) -> pd.Series:
    """Summarize cross-sectional pricing errors for extension periods."""
    benchmark_errors = observed - float(observed.mean())
    benchmark_sse = float(np.square(benchmark_errors.to_numpy(dtype=float)).sum())
    model_sse = float(np.square(errors.to_numpy(dtype=float)).sum())
    return pd.Series(
        {
            "rmse": float(np.sqrt(np.mean(np.square(errors.to_numpy(dtype=float))))),
            "mae": float(np.mean(np.abs(errors.to_numpy(dtype=float)))),
            "max_abs_alpha": float(np.max(np.abs(errors.to_numpy(dtype=float)))),
            "out_of_sample_r2": np.nan if benchmark_sse == 0.0 else 1.0 - model_sse / benchmark_sse,
            "n_assets": float(errors.shape[0]),
        }
    )


def compare_pre_post_patterns(
    *,
    pre_returns: pd.DataFrame,
    post_returns: pd.DataFrame,
    pre_betas: pd.DataFrame,
    post_betas: pd.DataFrame,
) -> pd.DataFrame:
    """Compare anomaly means and beta ordering before and after publication."""
    common_assets = [
        asset
        for asset in pre_returns.columns
        if asset in post_returns.columns and asset in pre_betas.index and asset in post_betas.index
    ]
    common_factors = [factor for factor in pre_betas.columns if factor in post_betas.columns]
    if not common_assets:
        raise ValueError("No common assets across pre/post returns and beta estimates")
    if not common_factors:
        raise ValueError("No common factors across pre/post beta estimates")
    pre_means = pre_returns.loc[:, common_assets].mean(axis=0)
    post_means = post_returns.loc[:, common_assets].mean(axis=0)
    rows: list[dict[str, float | str]] = []
    for asset in common_assets:
        row: dict[str, float | str] = {
            "asset": str(asset),
            "pre_mean_return": float(pre_means.loc[asset]),
            "post_mean_return": float(post_means.loc[asset]),
            "mean_return_change": float(post_means.loc[asset] - pre_means.loc[asset]),
        }
        for factor in common_factors:
            pre_rank = float(pre_betas.loc[common_assets, factor].rank().loc[asset])
            post_rank = float(post_betas.loc[common_assets, factor].rank().loc[asset])
            row[f"pre_{factor}_beta"] = float(cast(float, pre_betas.at[asset, factor]))
            row[f"post_{factor}_beta"] = float(cast(float, post_betas.at[asset, factor]))
            row[f"{factor}_beta_rank_change"] = post_rank - pre_rank
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate_pattern_change(
    pattern_table: pd.DataFrame, *, factor_names: tuple[str, ...]
) -> pd.Series:
    """Create publication-decay diagnostics from the asset-level pattern table."""
    if pattern_table.empty:
        raise ValueError("pattern_table cannot be empty")
    payload: dict[str, float] = {
        "mean_abs_return_change": float(pattern_table["mean_return_change"].abs().mean()),
        "pre_high_minus_low_spread": _high_minus_low(pattern_table["pre_mean_return"]),
        "post_high_minus_low_spread": _high_minus_low(pattern_table["post_mean_return"]),
    }
    payload["spread_change"] = (
        payload["post_high_minus_low_spread"] - payload["pre_high_minus_low_spread"]
    )
    for factor in factor_names:
        pre_column = f"pre_{factor}_beta"
        post_column = f"post_{factor}_beta"
        if pre_column not in pattern_table or post_column not in pattern_table:
            continue
        statistic, p_value = spearmanr(pattern_table[pre_column], pattern_table[post_column])
        payload[f"{factor}_beta_rank_correlation"] = float(statistic)
        payload[f"{factor}_beta_rank_correlation_p_value"] = float(p_value)
    return pd.Series(payload)


def refit_windows(
    dates: pd.DatetimeIndex,
    *,
    initial_train_end: str,
    evaluation_end: str,
    refit_frequency_months: int,
    rolling_window_months: int | None = None,
) -> pd.DataFrame:
    """Return explicit expanding or rolling training windows for secondary analyses."""
    if refit_frequency_months <= 0:
        raise ValueError("refit_frequency_months must be positive")
    if rolling_window_months is not None and rolling_window_months <= 0:
        raise ValueError("rolling_window_months must be positive")
    if dates.empty:
        raise ValueError("dates cannot be empty")
    sorted_dates = pd.DatetimeIndex(dates).sort_values()
    train_end = _month_end(initial_train_end)
    final_end = _month_end(evaluation_end)
    rows: list[dict[str, str | int]] = []
    train_start = sorted_dates.min()
    window_id = 1
    while train_end < final_end:
        test_start = train_end + pd.offsets.MonthEnd(1)
        test_end = min(train_end + pd.offsets.MonthEnd(refit_frequency_months), final_end)
        if rolling_window_months is not None:
            train_start = train_end - pd.offsets.MonthEnd(rolling_window_months - 1)
        rows.append(
            {
                "window_id": window_id,
                "window_type": "rolling" if rolling_window_months is not None else "expanding",
                "train_start": pd.Timestamp(train_start).strftime("%Y-%m"),
                "train_end": pd.Timestamp(train_end).strftime("%Y-%m"),
                "test_start": pd.Timestamp(test_start).strftime("%Y-%m"),
                "test_end": pd.Timestamp(test_end).strftime("%Y-%m"),
            }
        )
        train_end = test_end
        window_id += 1
    return pd.DataFrame(rows)


def write_temporal_extension_outputs(
    *,
    panel_build: TemporalPanelBuild,
    frozen_pricing: pd.DataFrame,
    pattern_comparison: pd.DataFrame,
    pattern_summary: pd.Series,
    table_dir: Path,
    figure_dir: Path,
    report_path: Path,
    freeze: TemporalFreeze,
) -> None:
    """Write extension tables, a boundary figure, and a concise markdown report."""
    table_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    panel_build.monthly_panel.to_csv(
        table_dir / "monthly_panel_audit.csv", index=False, lineterminator="\n"
    )
    panel_build.revision_audit.to_csv(
        table_dir / "revision_audit.csv", index=False, lineterminator="\n"
    )
    panel_build.universe.to_csv(
        table_dir / "extension_universe.csv", index=False, lineterminator="\n"
    )
    panel_build.observation_summary.to_csv(
        table_dir / "observation_summary.csv", index=False, lineterminator="\n"
    )
    frozen_pricing.to_csv(
        table_dir / "frozen_2013_pricing_errors.csv", index=False, lineterminator="\n"
    )
    pattern_comparison.to_csv(
        table_dir / "pre_post_pattern_comparison.csv", index=False, lineterminator="\n"
    )
    pattern_summary.to_frame("value").to_csv(
        table_dir / "publication_decay_summary.csv", lineterminator="\n"
    )
    (table_dir / "freeze_metadata.json").write_text(
        json.dumps(asdict(freeze), indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    write_boundary_figure(
        panel_build.monthly_panel,
        output_path=figure_dir / "december_2013_boundary.pdf",
        boundary_month=freeze.baseline_end,
    )
    report_path.write_text(
        "\n".join(
            [
                "# Temporal Extension Report",
                "",
                f"Latest common month: `{freeze.latest_common_month}`",
                f"Retrieval date: `{freeze.retrieval_date}`",
                f"Locked baseline vintage: `{freeze.baseline_vintage_label}`",
                f"Extension vintage: `{freeze.extension_vintage_label}`",
                "",
                "The baseline and extension vintages are labelled separately. Revised "
                "historical values are reported only in the revision audit.",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def write_boundary_figure(
    monthly_panel: pd.DataFrame,
    *,
    output_path: Path,
    boundary_month: str,
) -> None:
    """Plot mean series values with a vertical December 2013 boundary."""
    import matplotlib.pyplot as plt

    required = {"month", "value", "sample_period"}
    missing = required - set(monthly_panel.columns)
    if missing:
        raise ValueError(f"Monthly panel is missing columns: {', '.join(sorted(missing))}")
    frame = monthly_panel.copy()
    frame["date"] = pd.to_datetime(frame["month"]) + pd.offsets.MonthEnd(0)
    mean_by_month = frame.groupby("date")["value"].mean()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(
        mean_by_month.index, mean_by_month.to_numpy(dtype=float), color="#255c99", linewidth=1.4
    )
    ax.axvline(
        date2num(_month_end(boundary_month).to_pydatetime()),  # type: ignore[no-untyped-call]
        color="#c43c35",
        linestyle="--",
        linewidth=1.2,
    )
    ax.set_xlabel("Month")
    ax.set_ylabel("Cross-sectional mean")
    ax.set_title("Temporal Extension Boundary")
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def write_blocked_temporal_report(
    *,
    output_path: Path,
    freeze: TemporalFreeze,
    missing_inputs: tuple[Path, ...],
) -> None:
    """Write a blocked extension report when empirical inputs are absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Temporal Extension Report",
                "",
                "Verdict: `blocked_missing_input`",
                "",
                f"Latest common month: `{freeze.latest_common_month}`",
                f"Retrieval date: `{freeze.retrieval_date}`",
                "",
                "The temporal extension report cannot be rendered until the registered H2 "
                "temporal-stability artifacts exist. No revised historical data have been "
                "merged into the locked 1972-2013 baseline.",
                "",
                "Missing inputs:",
                *[f"- `{path.as_posix()}`" for path in missing_inputs],
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def render_temporal_evidence_report(
    *,
    freeze: TemporalFreeze,
    stability_path: Path,
    evaluation_table_path: Path,
) -> str:
    """Render the temporal-extension report from the frozen H2 artifacts.

    Two classifications are rendered and they are kept apart. The verdict at the
    top is the registered point-estimate rule; the supplementary section carries
    the interval classification, which distinguishes a demonstrated change from
    evidence too imprecise to classify and never replaces the verdict.

    Args:
        freeze: Frozen vintage metadata for the post-2013 extension.
        stability_path: Registered H2 temporal-stability artifact.
        evaluation_table_path: Registered per-window evaluation table.

    Returns:
        The markdown report. Every displayed value is read from the artifacts or
        from the frozen extension configuration.
    """
    stability = load_json_artifact(stability_path)
    evaluation = pd.read_csv(evaluation_table_path)
    gates = artifact_field(stability, "gates")
    lambda_rate = artifact_field(stability, "lambda_rate")
    dispersion = artifact_field(stability, "standardized_rate_exposure_dispersion_share")
    sign_gate = artifact_field(stability, "sign_gate_vintage")
    inferential = artifact_field(stability, "supplementary_inferential_classification")
    estimands = artifact_field(inferential, "estimands")
    lines = [
        "# Temporal Extension Report",
        "",
        f"Verdict: {format_code(artifact_field(stability, 'classification'))}",
        "",
        f"Hypothesis: {format_code(artifact_field(stability, 'hypothesis'))}",
        f"Replication status: {format_code(artifact_field(stability, 'replication_status'))}",
        f"Latest common month: `{freeze.latest_common_month}`",
        f"Retrieval date: `{freeze.retrieval_date}`",
        f"Locked baseline vintage: `{freeze.baseline_vintage_label}`",
        f"Extension vintage: `{freeze.extension_vintage_label}`",
        f"Revision policy: `{freeze.revision_policy}`",
        "",
        "## Registered Compatibility Gates",
        "",
        "These are the frozen point-estimate gates of the H2 registry row, and they decide "
        "the verdict above.",
        "",
        *markdown_table(
            ["Gate", "Passed"],
            [[gate, gates[gate]] for gate in sorted(gates)],
        ),
        "",
        "- Registered sign gate compares against: "
        f"{format_code(sign_gate['registered_gate_compares_against'])}, passed "
        f"{format_code(sign_gate['registered_gate_passes'])}",
        "- Same-vintage sign comparison against: "
        f"{format_code(sign_gate['same_vintage_gate_compares_against'])}, passed "
        f"{format_code(sign_gate['same_vintage_gate_passes'])}",
        f"- The two sign comparisons agree: {format_code(sign_gate['gates_agree'])}",
        "",
        f"Sign-gate vintage note: {sign_gate['note']}",
        "",
        "## Supplementary Inferential Classification",
        "",
        f"Status: {format_code(artifact_field(inferential, 'status'))}",
        f"Role: {artifact_field(inferential, 'role')}",
        f"Rule: {format_code(artifact_field(inferential, 'rule'))}, sensitivity rule "
        f"{format_code(artifact_field(inferential, 'sensitivity_rule'))}",
        f"Comparison: {format_code(artifact_field(inferential, 'comparison'))}",
        f"Draws: {format_code(artifact_field(inferential, 'draws'))}",
        "",
        *markdown_table(
            ["Estimand", "Point Change", "Lower 90", "Upper 90", "Bound", "Decision"],
            [
                [
                    name,
                    estimands[name]["point_change"],
                    estimands[name]["lower_90"],
                    estimands[name]["upper_90"],
                    estimands[name]["bound"],
                    estimands[name]["decision_category"],
                ]
                for name in sorted(estimands)
            ],
        ),
        "",
        f"Status basis: {artifact_field(inferential, 'status_basis')}",
        "",
        f"Interval note: {artifact_field(inferential, 'note')}",
        "",
        "## Rate Risk Price By Evaluation Window",
        "",
        *markdown_table(
            ["Window", "Rate Risk Price"],
            [[window, lambda_rate[window]] for window in sorted(lambda_rate)],
        ),
        "",
        "- RMSE relative change against the locked baseline: "
        f"{format_code(artifact_field(stability, 'rmse_relative_change_vs_locked_baseline'))}",
        "- RMSE relative change against the revised history: "
        f"{format_code(artifact_field(stability, 'rmse_relative_change_vs_revised_history'))}",
        "- Frozen autoregression intercept: "
        f"{format_code(artifact_field(stability, 'frozen_ar_intercept'))}, slope "
        f"{format_code(artifact_field(stability, 'frozen_ar_slope'))}",
        "- Standardized rate-exposure dispersion share: locked baseline "
        f"{format_code(dispersion['locked_baseline'])}, refitted extension "
        f"{format_code(dispersion['refitted_extension'])}, against a floor of "
        f"{format_code(dispersion['floor'])}",
        "",
        f"Dispersion note: {dispersion['note']}",
        "",
        f"Vintage isolation: {artifact_field(stability, 'vintage_isolation')}",
        "",
        "## Evaluation Windows",
        "",
        *dataframe_table(evaluation),
        "",
        "The baseline and extension vintages are labelled separately. The revised-history "
        "evaluation is the current-vintage comparator for the registered temporal gates, so "
        "revised historical values do enter the temporal verdict, as the quantity the refitted "
        "extension is measured against. What the shared vintage removes is the publication-era "
        "against current-vintage revision effect, which the locked-baseline comparison reports "
        "separately.",
        "",
        "## Artifacts Read",
        "",
        *path_bullets((stability_path, evaluation_table_path)),
        "",
    ]
    return "\n".join(lines)


def write_temporal_evidence_report(
    *,
    output_path: Path,
    freeze: TemporalFreeze,
    stability_path: Path,
    evaluation_table_path: Path,
) -> None:
    """Write the temporal-extension report rendered from the frozen H2 artifacts."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_temporal_evidence_report(
            freeze=freeze,
            stability_path=stability_path,
            evaluation_table_path=evaluation_table_path,
        ),
        encoding="utf-8",
        newline="\n",
    )


def _to_long_panel(panel: pd.DataFrame, *, vintage: str, sample_period: str) -> pd.DataFrame:
    long = (
        panel.rename_axis("date")
        .reset_index()
        .melt(id_vars="date", var_name="series_id", value_name="value")
    )
    long["month"] = pd.to_datetime(long["date"]).dt.strftime("%Y-%m")
    long["vintage"] = vintage
    long["sample_period"] = sample_period
    return long.loc[:, ["month", "series_id", "value", "vintage", "sample_period"]]


def _require_datetime_index(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex")
    if frame.index.has_duplicates:
        raise ValueError(f"{name} contains duplicate dates")


def _month_end(month: str) -> pd.Timestamp:
    return pd.Timestamp(month) + pd.offsets.MonthEnd(0)


def _high_minus_low(values: pd.Series) -> float:
    ordered = values.sort_values()
    return float(ordered.iloc[-1] - ordered.iloc[0])
