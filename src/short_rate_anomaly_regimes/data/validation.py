"""Validation rules for monthly financial panels."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    """Compact data-quality result."""

    rows: int
    columns: int
    missing_values: int
    duplicate_dates: int
    monotonic_dates: bool


def validate_monthly_panel(frame: pd.DataFrame, *, date_column: str = "date") -> ValidationSummary:
    """Validate a monthly panel without silently modifying it.

    Args:
        frame: Input data frame.
        date_column: Column containing monthly timestamps.

    Returns:
        Validation summary.

    Raises:
        ValueError: For missing date columns, duplicate dates, non-monthly spacing, or infinities.
    """
    if date_column not in frame.columns:
        raise ValueError(f"Missing date column {date_column!r}")
    dates = pd.to_datetime(frame[date_column], errors="raise")
    duplicate_dates = int(dates.duplicated().sum())
    if duplicate_dates:
        raise ValueError(f"Found {duplicate_dates} duplicate monthly dates")
    if not dates.is_monotonic_increasing:
        raise ValueError("Dates must be sorted in ascending order")
    numeric = frame.select_dtypes(include=["number"])
    if np.isinf(numeric.to_numpy(dtype=float, copy=False)).any():
        raise ValueError("Numeric panel contains infinite values")
    periods = dates.dt.to_period("M")
    if periods.duplicated().any():
        raise ValueError("More than one observation exists in at least one calendar month")
    return ValidationSummary(
        rows=len(frame),
        columns=len(frame.columns),
        missing_values=int(frame.isna().sum().sum()),
        duplicate_dates=duplicate_dates,
        monotonic_dates=True,
    )
