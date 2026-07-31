"""Deterministic monthly monetary-regime labels."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

import pandas as pd


@dataclass(frozen=True, slots=True)
class RegimeInterval:
    """Closed monthly interval for a named monetary regime."""

    regime_id: str
    start: pd.Period
    end: pd.Period


@dataclass(frozen=True, slots=True)
class RegimeSource:
    """Evidence source for one frozen monetary-regime boundary."""

    regime_id: str
    boundary_month: str
    policy_action_date: str
    source_url: str
    source_note: str


def label_regimes(index: pd.DatetimeIndex, intervals: tuple[RegimeInterval, ...]) -> pd.Series:
    """Assign exactly one deterministic regime to each monthly observation."""
    labels = pd.Series(pd.NA, index=index, dtype="string", name="regime")
    monthly = index.to_period("M")
    for interval in intervals:
        mask = (monthly >= interval.start) & (monthly <= interval.end)
        if labels.loc[mask].notna().any():
            raise ValueError(f"Overlapping regime interval detected for {interval.regime_id}")
        labels.loc[mask] = interval.regime_id
    if labels.isna().any():
        missing = labels.index[labels.isna()]
        raise ValueError(f"Unlabelled regime observations: {len(missing)}")
    return labels


def build_regime_table(
    intervals: tuple[RegimeInterval, ...],
    sources: tuple[RegimeSource, ...],
) -> pd.DataFrame:
    """Create the frozen regime table with source URLs attached to boundaries."""
    source_by_regime = {source.regime_id: source for source in sources}
    rows: list[dict[str, str | bool]] = []
    for interval in intervals:
        source = source_by_regime.get(interval.regime_id)
        rows.append(
            {
                "regime_id": interval.regime_id,
                "start": str(interval.start),
                "end": str(interval.end),
                "boundary_verified": source is not None,
                "policy_action_date": "" if source is None else source.policy_action_date,
                "source_url": "" if source is None else source.source_url,
                "source_note": "" if source is None else source.source_note,
            }
        )
    return pd.DataFrame(rows)


def interval_from_months(regime_id: str, start: str, end: str) -> RegimeInterval:
    """Build a monthly closed interval from config strings."""
    start_period = pd.Period(start, freq="M")
    end_period = pd.Period(end, freq="M")
    if end_period < start_period:
        raise ValueError(f"Regime {regime_id} ends before it starts")
    return RegimeInterval(regime_id=regime_id, start=start_period, end=end_period)


def shift_regime_boundaries(
    intervals: tuple[RegimeInterval, ...],
    *,
    shift_months: int,
) -> tuple[RegimeInterval, ...]:
    """Shift internal boundaries while preserving a contiguous closed calendar."""
    if len(intervals) < 2:
        return intervals
    ordered = tuple(sorted(intervals, key=lambda interval: interval.start))
    shifted: list[RegimeInterval] = []
    current_start = ordered[0].start
    for left, right in pairwise(ordered):
        shifted_end = left.end + shift_months
        if shifted_end < current_start:
            raise ValueError("Boundary shift creates an empty regime")
        if shifted_end >= right.end:
            raise ValueError("Boundary shift overlaps the next regime")
        shifted.append(RegimeInterval(left.regime_id, current_start, shifted_end))
        current_start = shifted_end + 1
    shifted.append(RegimeInterval(ordered[-1].regime_id, current_start, ordered[-1].end))
    return tuple(shifted)


def regime_observation_counts(labels: pd.Series) -> pd.DataFrame:
    """Count monthly observations in each deterministic regime."""
    counts = labels.value_counts(sort=False).rename_axis("regime_id").rename("observations")
    return counts.reset_index()


def split_sample_eligibility(labels: pd.Series, *, minimum_observations: int) -> pd.DataFrame:
    """Report which regimes satisfy the split-sample estimation minimum."""
    if minimum_observations <= 0:
        raise ValueError("minimum_observations must be positive")
    counts = regime_observation_counts(labels)
    counts["eligible_for_split_sample"] = counts["observations"] >= minimum_observations
    return counts
