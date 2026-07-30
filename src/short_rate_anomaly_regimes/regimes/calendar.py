"""Deterministic monthly monetary-regime labels."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class RegimeInterval:
    """Closed monthly interval for a named monetary regime."""

    regime_id: str
    start: pd.Period
    end: pd.Period


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
