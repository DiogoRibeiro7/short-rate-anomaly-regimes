"""Audit whether provider monthly rate series reproduce aggregations of daily data.

The audit never assumes that a provider monthly series equals an arithmetic
aggregation of the corresponding daily series. It computes each candidate rule
explicitly, compares it with the published monthly series, and reports the
outcome against a declared tolerance.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

#: Half of the smallest published increment. FRED publishes both the monthly and
#: the daily rate series rounded to two decimal places, so an aggregation that
#: agrees to within half a reporting increment is indistinguishable from the
#: provider computation given the published inputs.
PRIMARY_TOLERANCE_PERCENTAGE_POINTS = 0.005

#: One full reporting increment. Used as a declared secondary band so that a
#: near-miss is reported as such rather than silently classified as a match.
SECONDARY_TOLERANCE_PERCENTAGE_POINTS = 0.01

#: Guard against a floating-point subtraction of two two-decimal quantities
#: landing marginally outside an exactly-equal tolerance boundary.
NUMERICAL_EPSILON = 1e-9

AggregationRule = Literal[
    "calendar_day_mean",
    "business_day_mean",
    "available_observation_mean",
    "month_end_last_observation",
]


@dataclass(frozen=True, slots=True)
class AggregationComparison:
    """Result of comparing one aggregation rule with a published monthly series."""

    monthly_series_id: str
    daily_series_id: str
    rule: str
    complete_months_compared: int
    exact_match_months: int
    max_absolute_difference: float
    mean_absolute_difference: float
    root_mean_squared_difference: float
    months_within_primary_tolerance: int
    months_within_secondary_tolerance: int
    share_within_primary_tolerance: float
    verdict: str


def _month_period(index: pd.DatetimeIndex) -> pd.PeriodIndex:
    return index.to_period("M")


def aggregate_daily_to_monthly(
    daily: pd.Series,
    *,
    rule: AggregationRule,
) -> pd.Series:
    """Aggregate a daily rate series to monthly under one explicit rule.

    Args:
        daily: Daily rate series indexed by observation date.
        rule: Aggregation rule to apply.

    Returns:
        Monthly series indexed by period start timestamps.

    Raises:
        ValueError: If the rule is not recognised.
    """
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("Daily rate series must use a DatetimeIndex")
    clean = daily.sort_index()
    if rule == "business_day_mean":
        weekdays = pd.DatetimeIndex(clean.index).weekday
        clean = clean[weekdays < 5]
    present = clean.dropna()
    months = _month_period(pd.DatetimeIndex(present.index))
    if rule in {"calendar_day_mean", "business_day_mean", "available_observation_mean"}:
        grouped = present.groupby(months).mean()
    elif rule == "month_end_last_observation":
        grouped = present.groupby(months).last()
    else:
        raise ValueError(f"Unsupported aggregation rule {rule!r}")
    grouped.index = pd.PeriodIndex(grouped.index, freq="M").to_timestamp(how="start")
    return grouped.astype(float)


def daily_month_coverage(daily: pd.Series) -> pd.DataFrame:
    """Summarise how completely a daily series covers each calendar month."""
    clean = daily.sort_index()
    periods = _month_period(pd.DatetimeIndex(clean.index))
    present = clean.dropna()
    frame = pd.DataFrame(
        {
            "observations": clean.groupby(periods).size(),
            "non_missing_observations": present.groupby(
                _month_period(pd.DatetimeIndex(present.index))
            ).size(),
            "first_day": clean.groupby(periods).apply(lambda block: block.index.min().day),
            "last_day": clean.groupby(periods).apply(lambda block: block.index.max().day),
        }
    )
    frame["days_in_month"] = [period.days_in_month for period in frame.index]
    frame["covers_month_start"] = frame["first_day"] <= 3
    frame["covers_month_end"] = frame["days_in_month"] - frame["last_day"] <= 3
    frame["complete_month"] = frame["covers_month_start"] & frame["covers_month_end"]
    frame.index = pd.PeriodIndex(frame.index, freq="M").to_timestamp(how="start")
    return frame


def build_aggregation_difference_frame(
    *,
    monthly: pd.Series,
    daily: pd.Series,
    monthly_series_id: str,
    daily_series_id: str,
    rule: AggregationRule,
) -> pd.DataFrame:
    """Build the month-by-month difference table for one aggregation rule."""
    aggregated = aggregate_daily_to_monthly(daily, rule=rule)
    coverage = daily_month_coverage(daily)
    joined = pd.concat(
        {
            "published_monthly": monthly,
            "aggregated_monthly": aggregated,
        },
        axis=1,
        join="inner",
    ).sort_index()
    joined["difference"] = joined["published_monthly"] - joined["aggregated_monthly"]
    joined["absolute_difference"] = joined["difference"].abs()
    joined["complete_month"] = coverage["complete_month"].reindex(joined.index).fillna(False)
    joined["daily_observations_used"] = (
        coverage["non_missing_observations"].reindex(joined.index).astype("Int64")
    )
    joined["within_primary_tolerance"] = (
        joined["absolute_difference"] <= PRIMARY_TOLERANCE_PERCENTAGE_POINTS + NUMERICAL_EPSILON
    )
    joined["within_secondary_tolerance"] = (
        joined["absolute_difference"] <= SECONDARY_TOLERANCE_PERCENTAGE_POINTS + NUMERICAL_EPSILON
    )
    joined["exact_to_published_precision"] = joined["absolute_difference"] < 5e-9
    joined.insert(0, "rule", rule)
    joined.insert(0, "daily_series_id", daily_series_id)
    joined.insert(0, "monthly_series_id", monthly_series_id)
    joined.index.name = "month"
    return joined.reset_index()


@dataclass(frozen=True, slots=True)
class DecimalRoundingCheck:
    """Exact-decimal test of the hypothesis that the monthly series is a rounded mean."""

    monthly_series_id: str
    daily_series_id: str
    rule: str
    decimal_places: int
    rounding_mode: str
    complete_months_compared: int
    exact_decimal_matches: int
    mismatched_months: tuple[str, ...]
    verdict: str


def exact_decimal_rounding_check(
    *,
    monthly_raw_path: Path,
    daily_raw_path: Path,
    monthly_series_id: str,
    daily_series_id: str,
    rule: AggregationRule,
    decimal_places: int = 2,
) -> DecimalRoundingCheck:
    """Test whether the published monthly value equals the rounded daily mean exactly.

    The test parses the provider payloads as decimal strings rather than binary
    floats, so a value lying exactly on a rounding tie is resolved the way the
    provider would resolve it rather than the way binary representation happens
    to fall.

    Args:
        monthly_raw_path: Immutable raw provider CSV for the monthly series.
        daily_raw_path: Immutable raw provider CSV for the daily series.
        monthly_series_id: Identifier recorded in the result.
        daily_series_id: Identifier recorded in the result.
        rule: Aggregation rule under test.
        decimal_places: Published precision of the monthly series.

    Returns:
        The exact-decimal comparison record.

    Raises:
        ValueError: If the rule is not a mean rule or no complete month exists.
    """
    if rule not in {"calendar_day_mean", "business_day_mean", "available_observation_mean"}:
        raise ValueError(f"Rule {rule!r} is not a mean rule")
    quantum = Decimal(1).scaleb(-decimal_places)

    daily = pd.read_csv(daily_raw_path, dtype=str)
    daily.columns = ["date", "value"]
    daily["date"] = pd.to_datetime(daily["date"], errors="raise")
    daily = daily[daily["value"].str.strip() != "."]
    if rule == "business_day_mean":
        daily = daily[daily["date"].dt.weekday < 5]
    daily["decimal_value"] = daily["value"].str.strip().map(Decimal)

    periods = daily["date"].dt.to_period("M")
    totals = daily.groupby(periods)["decimal_value"].sum()
    counts = daily.groupby(periods)["decimal_value"].count()
    rounded = (totals / counts.map(Decimal)).map(
        lambda value: value.quantize(quantum, rounding=ROUND_HALF_UP)
    )
    coverage = daily.groupby(periods)["date"].agg(["min", "max"])

    monthly = pd.read_csv(monthly_raw_path, dtype=str)
    monthly.columns = ["date", "value"]
    monthly = monthly[monthly["value"].str.strip() != "."]
    monthly["date"] = pd.to_datetime(monthly["date"], errors="raise")
    published = (
        monthly.set_index(monthly["date"].dt.to_period("M"))["value"]
        .str.strip()
        .map(lambda value: Decimal(value).quantize(quantum))
    )

    matches = 0
    mismatches: list[str] = []
    for period in rounded.index.intersection(published.index):
        days_in_month = period.days_in_month
        if coverage.loc[period, "min"].day > 3:
            continue
        if days_in_month - coverage.loc[period, "max"].day > 3:
            continue
        if rounded[period] == published[period]:
            matches += 1
        else:
            mismatches.append(str(period))
    compared = matches + len(mismatches)
    if compared == 0:
        raise ValueError("No complete months available for the exact-decimal check")
    return DecimalRoundingCheck(
        monthly_series_id=monthly_series_id,
        daily_series_id=daily_series_id,
        rule=rule,
        decimal_places=decimal_places,
        rounding_mode="ROUND_HALF_UP",
        complete_months_compared=compared,
        exact_decimal_matches=matches,
        mismatched_months=tuple(mismatches),
        verdict=(
            "monthly_series_is_the_rounded_daily_mean_for_every_complete_month"
            if not mismatches
            else "monthly_series_is_not_the_rounded_daily_mean_for_every_complete_month"
        ),
    )


def summarise_aggregation(frame: pd.DataFrame) -> AggregationComparison:
    """Reduce a month-by-month difference table to one comparison record."""
    complete = frame[frame["complete_month"]].copy()
    if complete.empty:
        raise ValueError("No complete months available for comparison")
    absolute = complete["absolute_difference"].to_numpy(dtype=float)
    within_primary = int(complete["within_primary_tolerance"].sum())
    share_primary = float(within_primary / len(complete))
    max_absolute = float(np.max(absolute))
    exact_matches = int(complete["exact_to_published_precision"].sum())
    if max_absolute <= PRIMARY_TOLERANCE_PERCENTAGE_POINTS + NUMERICAL_EPSILON:
        verdict = "reproduced_within_primary_tolerance"
    elif share_primary >= 0.99:
        verdict = "reproduced_for_at_least_99_percent_of_months_with_isolated_exceptions"
    elif max_absolute <= SECONDARY_TOLERANCE_PERCENTAGE_POINTS:
        verdict = "reproduced_within_secondary_tolerance_only"
    else:
        verdict = "not_reproduced_within_declared_tolerance"
    return AggregationComparison(
        monthly_series_id=str(complete["monthly_series_id"].iloc[0]),
        daily_series_id=str(complete["daily_series_id"].iloc[0]),
        rule=str(complete["rule"].iloc[0]),
        complete_months_compared=len(complete),
        exact_match_months=exact_matches,
        max_absolute_difference=max_absolute,
        mean_absolute_difference=float(np.mean(absolute)),
        root_mean_squared_difference=float(np.sqrt(np.mean(absolute**2))),
        months_within_primary_tolerance=within_primary,
        months_within_secondary_tolerance=int(complete["within_secondary_tolerance"].sum()),
        share_within_primary_tolerance=share_primary,
        verdict=verdict,
    )
