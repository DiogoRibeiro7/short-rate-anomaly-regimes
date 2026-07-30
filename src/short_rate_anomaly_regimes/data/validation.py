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
    continuous_months: bool


def validate_monthly_panel(
    frame: pd.DataFrame,
    *,
    date_column: str = "date",
    expected_columns: tuple[str, ...] = (),
    sample_start: str | None = None,
    sample_end: str | None = None,
    require_continuous_months: bool = False,
    numeric_bounds: tuple[float, float] | None = None,
    units: str | None = None,
    expected_portfolio_count: int | None = None,
    factor_columns: tuple[str, ...] = (),
) -> ValidationSummary:
    """Validate a monthly panel without silently modifying it.

    Args:
        frame: Input data frame.
        date_column: Column containing monthly timestamps.

    Returns:
        Validation summary.

    Raises:
        ValueError: For missing date columns, duplicate dates, non-monthly spacing, or infinities.
    """
    missing_expected_columns = set(expected_columns) - set(frame.columns)
    if missing_expected_columns:
        missing = ", ".join(sorted(missing_expected_columns))
        raise ValueError(f"Missing expected columns: {missing}")
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
    continuous_months = True
    if len(periods):
        expected_periods = pd.period_range(periods.min(), periods.max(), freq="M")
        continuous_months = list(periods) == list(expected_periods)
    if require_continuous_months and not continuous_months:
        raise ValueError("Monthly panel has gaps in month continuity")
    if sample_start is not None and str(periods.min()) != sample_start:
        raise ValueError(f"Expected sample start {sample_start}, found {periods.min()}")
    if sample_end is not None and str(periods.max()) != sample_end:
        raise ValueError(f"Expected sample end {sample_end}, found {periods.max()}")
    if numeric_bounds is not None:
        lower, upper = numeric_bounds
        numeric_values = numeric.to_numpy(dtype=float, copy=False)
        if ((numeric_values < lower) | (numeric_values > upper)).any():
            raise ValueError(f"Numeric values fall outside declared bounds [{lower}, {upper}]")
    if units is not None and numeric.shape[1] > 0:
        max_abs = float(np.nanmax(np.abs(numeric.to_numpy(dtype=float, copy=False))))
        if units == "decimal_return" and max_abs > 2.0:
            raise ValueError(
                "Return units look like percent values but decimal_return was declared"
            )
        if units == "percent_return" and 0 < max_abs < 1.0:
            raise ValueError("Return units look like decimals but percent_return was declared")
    if expected_portfolio_count is not None:
        portfolio_columns = [column for column in frame.columns if column != date_column]
        if len(portfolio_columns) != expected_portfolio_count:
            raise ValueError(
                f"Expected {expected_portfolio_count} portfolio columns, "
                f"found {len(portfolio_columns)}"
            )
    missing_factor_columns = set(factor_columns) - set(frame.columns)
    if missing_factor_columns:
        missing = ", ".join(sorted(missing_factor_columns))
        raise ValueError(f"Missing expected factor columns: {missing}")
    return ValidationSummary(
        rows=len(frame),
        columns=len(frame.columns),
        missing_values=int(frame.isna().sum().sum()),
        duplicate_dates=duplicate_dates,
        monotonic_dates=True,
        continuous_months=continuous_months,
    )
