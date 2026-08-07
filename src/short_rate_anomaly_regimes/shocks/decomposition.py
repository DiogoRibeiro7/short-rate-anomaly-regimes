"""Policy and central-bank information shock decomposition."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

AggregationRule = Literal["monthly_sum", "monthly_mean", "monthly_abs_sum"]


@dataclass(frozen=True, slots=True)
class ShockIdentificationRule:
    """Frozen high-frequency shock identification settings."""

    dataset_id: str
    method: str
    event_window_minutes: int
    rate_surprise_column: str
    equity_surprise_column: str
    policy_component_name: str = "policy_shock"
    information_component_name: str = "central_bank_information"
    ambiguous_component_name: str = "ambiguous_rate_surprise"


@dataclass(frozen=True, slots=True)
class ShockDecompositionBuild:
    """Event and monthly shock outputs plus audit tables."""

    event_shocks: pd.DataFrame
    monthly_shocks: pd.DataFrame
    summary_statistics: pd.DataFrame
    asset_pricing_design: pd.DataFrame


def decompose_high_frequency_surprises(
    event_data: pd.DataFrame,
    *,
    rate_surprise_column: str,
    equity_surprise_column: str,
    event_time_column: str = "event_time",
    identification: str = "poor_mans_sign_restriction",
    event_window_minutes: int = 30,
) -> pd.DataFrame:
    """Separate high-frequency surprises into policy and information components.

    The implemented production contract is the documented Jarocinski-Karadi poor-man's
    sign decomposition: rate and equity surprises with opposite signs are assigned to the
    policy component; same-sign surprises are assigned to the central-bank-information
    component. Events with a zero or missing sign are preserved as ambiguous instead of
    forcing an identifying label.
    """
    if identification != "poor_mans_sign_restriction":
        raise ValueError(f"Unsupported shock identification method: {identification}")
    if event_window_minutes <= 0:
        raise ValueError("event_window_minutes must be positive")
    required = {event_time_column, rate_surprise_column, equity_surprise_column}
    missing = required - set(event_data.columns)
    if missing:
        raise ValueError(f"Event data are missing columns: {', '.join(sorted(missing))}")
    if event_data.empty:
        raise ValueError("event_data cannot be empty")

    events = event_data.copy()
    events[event_time_column] = pd.to_datetime(events[event_time_column], errors="raise")
    events = events.sort_values(event_time_column).reset_index(drop=True)
    rate = pd.to_numeric(events[rate_surprise_column], errors="raise").astype(float)
    equity = pd.to_numeric(events[equity_surprise_column], errors="raise").astype(float)
    product = rate * equity
    policy_mask = product < 0.0
    information_mask = product > 0.0
    ambiguous_mask = ~(policy_mask | information_mask)
    output = pd.DataFrame(
        {
            "event_time": events[event_time_column],
            "event_date": events[event_time_column].dt.strftime("%Y-%m-%d"),
            "month": events[event_time_column].dt.to_period("M").astype(str),
            "total_rate_surprise": rate,
            "equity_surprise": equity,
            "policy_shock": rate.where(policy_mask, 0.0),
            "central_bank_information": rate.where(information_mask, 0.0),
            "ambiguous_rate_surprise": rate.where(ambiguous_mask, 0.0),
            "ambiguous_event": ambiguous_mask.astype(bool),
            "identification": identification,
            "event_window_minutes": event_window_minutes,
        }
    )
    output["component_identity_error"] = output["total_rate_surprise"] - (
        output["policy_shock"]
        + output["central_bank_information"]
        + output["ambiguous_rate_surprise"]
    )
    return output


def aggregate_monthly_shocks(
    event_shocks: pd.DataFrame,
    *,
    start_month: str,
    end_month: str,
    aggregation: AggregationRule = "monthly_sum",
) -> pd.DataFrame:
    """Aggregate event shocks to monthly factors, explicitly representing no-meeting months."""
    required = {
        "month",
        "total_rate_surprise",
        "policy_shock",
        "central_bank_information",
        "ambiguous_rate_surprise",
        "ambiguous_event",
    }
    missing = required - set(event_shocks.columns)
    if missing:
        raise ValueError(f"Event shock table is missing columns: {', '.join(sorted(missing))}")
    months = pd.period_range(start_month, end_month, freq="M")
    if months.empty:
        raise ValueError("Monthly aggregation window cannot be empty")
    events = event_shocks.copy()
    events["month_period"] = pd.PeriodIndex(events["month"], freq="M")
    if aggregation not in {"monthly_sum", "monthly_mean", "monthly_abs_sum"}:
        raise ValueError(f"Unsupported aggregation rule: {aggregation}")
    component_columns = [
        "total_rate_surprise",
        "policy_shock",
        "central_bank_information",
        "ambiguous_rate_surprise",
    ]
    grouped_by_month = events.groupby("month_period")[component_columns]
    if aggregation == "monthly_sum":
        grouped = grouped_by_month.sum()
    elif aggregation == "monthly_mean":
        grouped = grouped_by_month.mean()
    else:
        grouped = grouped_by_month.apply(_absolute_sum)
    counts = events.groupby("month_period").agg(
        meeting_count=("month_period", "size"),
        ambiguous_events=("ambiguous_event", "sum"),
    )
    monthly = pd.DataFrame(index=months).join(grouped, how="left").join(counts, how="left")
    monthly[component_columns] = monthly[component_columns].fillna(0.0)
    monthly[["meeting_count", "ambiguous_events"]] = monthly[
        ["meeting_count", "ambiguous_events"]
    ].fillna(0)
    monthly["multiple_meetings"] = monthly["meeting_count"].astype(int) > 1
    monthly["aggregation"] = aggregation
    monthly.index = pd.PeriodIndex(monthly.index, freq="M").to_timestamp("M")
    monthly.index.name = "month_end"
    return monthly


def source_study_summary_statistics(event_shocks: pd.DataFrame) -> pd.DataFrame:
    """Compute reproduction statistics for the selected shock source."""
    required = {"total_rate_surprise", "policy_shock", "central_bank_information"}
    missing = required - set(event_shocks.columns)
    if missing:
        raise ValueError(f"Shock table is missing columns: {', '.join(sorted(missing))}")
    rows: list[dict[str, float | str]] = []
    for column in sorted(required):
        series = pd.to_numeric(event_shocks[column], errors="raise").astype(float)
        rows.extend(
            [
                {"statistic": f"{column}_mean", "value": float(series.mean())},
                {"statistic": f"{column}_std", "value": float(series.std(ddof=1))},
                {"statistic": f"{column}_nonzero_count", "value": float((series != 0.0).sum())},
            ]
        )
    correlation = (
        event_shocks["policy_shock"]
        .astype(float)
        .corr(event_shocks["central_bank_information"].astype(float))
    )
    rows.append({"statistic": "policy_information_correlation", "value": float(correlation)})
    rows.append({"statistic": "event_count", "value": float(event_shocks.shape[0])})
    return pd.DataFrame(rows)


def reproduction_audit(
    generated_statistics: pd.DataFrame,
    target_statistics: pd.DataFrame,
) -> pd.DataFrame:
    """Compare generated source-study statistics against frozen targets."""
    required_generated = {"statistic", "value"}
    required_target = {"statistic", "target_value", "tolerance"}
    missing_generated = required_generated - set(generated_statistics.columns)
    missing_target = required_target - set(target_statistics.columns)
    if missing_generated:
        raise ValueError(f"Generated statistics missing columns: {', '.join(missing_generated)}")
    if missing_target:
        raise ValueError(f"Target statistics missing columns: {', '.join(missing_target)}")
    joined = target_statistics.merge(generated_statistics, on="statistic", how="left")
    joined["absolute_error"] = (joined["value"] - joined["target_value"]).abs()
    joined["status"] = np.where(
        joined["value"].isna(),
        "missing_generated_statistic",
        np.where(
            joined["absolute_error"] <= joined["tolerance"],
            "reproduced",
            "outside_tolerance",
        ),
    )
    return joined


def asset_pricing_factor_design() -> pd.DataFrame:
    """Register asset-pricing specifications for aggregate and decomposed shocks."""
    rows = [
        {
            "model": "aggregate_ar_rate_innovation",
            "factor_columns": "short_rate_innovation",
            "language_label": "rate innovation",
        },
        {
            "model": "high_frequency_total_rate_surprise",
            "factor_columns": "total_rate_surprise",
            "language_label": "high-frequency rate surprise",
        },
        {
            "model": "high_frequency_policy_component",
            "factor_columns": "policy_shock",
            "language_label": "policy shock",
        },
        {
            "model": "high_frequency_information_component",
            "factor_columns": "central_bank_information",
            "language_label": "central-bank information shock",
        },
        {
            "model": "joint_policy_information_components",
            "factor_columns": "policy_shock,central_bank_information",
            "language_label": "policy and information shocks",
        },
    ]
    return pd.DataFrame(rows)


def compare_shock_spanning(monthly_shocks: pd.DataFrame) -> pd.DataFrame:
    """Compare correlations among total, policy, and information monthly factors."""
    columns = ["total_rate_surprise", "policy_shock", "central_bank_information"]
    missing = set(columns) - set(monthly_shocks.columns)
    if missing:
        raise ValueError(f"Monthly shocks missing columns: {', '.join(sorted(missing))}")
    correlations = monthly_shocks[columns].astype(float).corr()
    return correlations.rename_axis("factor").reset_index()


def enforce_policy_language_rule(labels: pd.Series) -> None:
    """Reject labels that call an AR residual a policy shock."""
    lowered = labels.astype(str).str.lower()
    invalid = lowered.str.contains("ar") & lowered.str.contains("policy shock")
    if invalid.any():
        bad = labels.loc[invalid].tolist()
        raise ValueError(
            "Only identified high-frequency components may be called policy shocks: "
            f"{', '.join(str(item) for item in bad)}"
        )


def build_shock_decomposition(
    event_data: pd.DataFrame,
    *,
    rule: ShockIdentificationRule,
    start_month: str,
    end_month: str,
    aggregation: AggregationRule,
) -> ShockDecompositionBuild:
    """Build event-level and monthly shocks using a frozen identification rule."""
    event_shocks = decompose_high_frequency_surprises(
        event_data,
        rate_surprise_column=rule.rate_surprise_column,
        equity_surprise_column=rule.equity_surprise_column,
        identification=rule.method,
        event_window_minutes=rule.event_window_minutes,
    )
    monthly_shocks = aggregate_monthly_shocks(
        event_shocks,
        start_month=start_month,
        end_month=end_month,
        aggregation=aggregation,
    )
    summary = source_study_summary_statistics(event_shocks)
    design = asset_pricing_factor_design()
    enforce_policy_language_rule(design["model"] + " " + design["language_label"])
    return ShockDecompositionBuild(
        event_shocks=event_shocks,
        monthly_shocks=monthly_shocks,
        summary_statistics=summary,
        asset_pricing_design=design,
    )


def write_shock_outputs(
    *,
    build: ShockDecompositionBuild,
    diagnostics_dir: Path,
    table_dir: Path,
    monthly_path: Path,
    report_path: Path,
    rule: ShockIdentificationRule,
) -> None:
    """Write shock decomposition outputs and a concise markdown report."""
    for path in (diagnostics_dir, table_dir, monthly_path.parent, report_path.parent):
        path.mkdir(parents=True, exist_ok=True)
    build.monthly_shocks.to_parquet(monthly_path)
    build.event_shocks.to_csv(table_dir / "event_shocks.csv", index=False)
    build.summary_statistics.to_csv(table_dir / "source_study_summary.csv", index=False)
    build.asset_pricing_design.to_csv(table_dir / "asset_pricing_design.csv", index=False)
    compare_shock_spanning(build.monthly_shocks).to_csv(
        table_dir / "shock_spanning.csv",
        index=False,
    )
    (diagnostics_dir / "identification_rule.json").write_text(
        json.dumps(asdict(rule), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path.write_text(
        "\n".join(
            [
                "# Shock Decomposition Report",
                "",
                "Verdict: `generated_from_frozen_event_data`",
                "",
                f"Dataset: `{rule.dataset_id}`",
                f"Identification: `{rule.method}`",
                "",
                "Only the identified high-frequency component is labelled a policy shock. "
                "The AR residual remains a rate innovation.",
            ]
        ),
        encoding="utf-8",
    )


def write_blocked_shock_report(
    *,
    output_path: Path,
    missing_inputs: tuple[Path, ...],
    selected_dataset: str,
) -> None:
    """Write a blocked report when selected event-level shock inputs are absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Shock Decomposition Report",
                "",
                "Verdict: `blocked_missing_input`",
                "",
                f"Selected dataset: `{selected_dataset}`",
                "",
                "Shock decomposition is blocked until event-level high-frequency surprise "
                "data are acquired with redistribution terms recorded. The AR residual must "
                "remain labelled a rate innovation, not a policy shock.",
                "",
                "Missing inputs:",
                *[f"- `{path.as_posix()}`" for path in missing_inputs],
                "",
            ]
        ),
        encoding="utf-8",
    )


def _absolute_sum(values: pd.DataFrame) -> pd.Series:
    return values.abs().sum()
