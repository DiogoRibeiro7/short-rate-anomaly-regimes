"""Construction and validation of the immutable canonical baseline panel.

The panel is an inner join of every frozen input on the calendar month. It is
never forward filled, never reindexed onto a wider calendar, and never extended
past the frozen baseline endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class PanelValidationReport:
    """Outcome of every canonical-panel validation check."""

    rows: int
    columns: int
    sample_start: str
    sample_end: str
    checks: dict[str, bool] = field(default_factory=dict)
    details: dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Report whether every validation check passed."""
        return all(self.checks.values())


def build_baseline_panel(
    *,
    market_excess_return: pd.Series,
    risk_free_return: pd.Series,
    short_rate_levels: dict[str, pd.Series],
    short_rate_innovations: dict[str, pd.Series],
    portfolio_returns: dict[str, pd.DataFrame],
    window_start: str,
    window_end: str,
) -> pd.DataFrame:
    """Assemble the canonical monthly panel by inner join on the calendar month.

    Args:
        market_excess_return: Market excess return in percent per month.
        risk_free_return: Risk-free return in percent per month.
        short_rate_levels: Short-rate levels in annualized percentage points.
        short_rate_innovations: AR(1) innovations in annualized percentage points.
        portfolio_returns: Raw portfolio returns in percent per month, by family.
        window_start: First month of the baseline window.
        window_end: Last month of the baseline window, inclusive and binding.

    Returns:
        The canonical panel indexed by month period.

    Raises:
        ValueError: If any input is not month-period indexed, if any input has a
            duplicate month, or if the intersection is empty.
    """
    components: dict[str, pd.Series] = {
        "market_excess_return": market_excess_return,
        "risk_free_return": risk_free_return,
    }
    for name, series in short_rate_levels.items():
        components[f"short_rate_level__{name}"] = series
    for name, series in short_rate_innovations.items():
        components[f"short_rate_innovation__{name}"] = series
    for family, frame in portfolio_returns.items():
        for column in frame.columns:
            components[f"portfolio_excess_return__{family}__{column}"] = frame[column]

    for name, series in components.items():
        if not isinstance(series.index, pd.PeriodIndex) or series.index.freqstr != "M":
            raise ValueError(f"Input {name!r} must use a monthly PeriodIndex")
        if series.index.has_duplicates:
            raise ValueError(f"Input {name!r} has duplicate months")

    window = pd.period_range(window_start, window_end, freq="M")
    common: pd.PeriodIndex = window
    for series in components.values():
        available = pd.PeriodIndex(series.dropna().index, freq="M")
        common = pd.PeriodIndex(common.intersection(available), freq="M")
    common = pd.PeriodIndex(sorted(common), freq="M")
    if len(common) == 0:
        raise ValueError("Inputs share no common month inside the baseline window")

    panel = pd.DataFrame(index=common)
    panel.index.name = "month"
    risk_free = risk_free_return.reindex(common)
    for name, series in components.items():
        aligned = series.reindex(common)
        if name.startswith("portfolio_excess_return__"):
            aligned = aligned - risk_free
        panel[name] = aligned.to_numpy(dtype=float)
    return panel


def validate_baseline_panel(
    panel: pd.DataFrame,
    *,
    window_start: str,
    window_end: str,
    raw_portfolio_returns: dict[str, pd.DataFrame],
    short_rate_levels: dict[str, pd.Series],
    ar_parameters: dict[str, tuple[float, float]],
    market_excess_return: pd.Series,
) -> PanelValidationReport:
    """Run every declared canonical-panel validation check.

    Args:
        panel: The assembled canonical panel.
        window_start: First month of the baseline window.
        window_end: Frozen baseline endpoint.
        raw_portfolio_returns: Raw portfolio returns, used to verify the excess-return step.
        short_rate_levels: Short-rate levels, used to verify the innovation timing.
        ar_parameters: Intercept and slope per short-rate series.
        market_excess_return: Source market factor, used to verify no timing shift.

    Returns:
        The validation report.
    """
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}
    index = panel.index

    checks["unique_monthly_keys"] = not index.has_duplicates
    checks["monotonically_increasing_dates"] = bool(index.is_monotonic_increasing)

    expected = pd.period_range(index.min(), index.max(), freq="M")
    checks["no_internal_month_gaps"] = list(index) == list(expected)

    endpoint = pd.Period(window_end, freq="M")
    start = pd.Period(window_start, freq="M")
    checks["no_observation_after_frozen_endpoint"] = bool(index.max() <= endpoint)
    checks["no_observation_before_window_start"] = bool(index.min() >= start)

    checks["no_missing_values"] = not bool(panel.isna().to_numpy().any())
    checks["no_infinite_values"] = not bool(np.isinf(panel.to_numpy(dtype=float)).any())

    # A forward fill would create runs of exactly repeated float values across
    # consecutive months in return columns. Genuine returns never do this.
    return_columns = [
        column
        for column in panel.columns
        if column.startswith(("portfolio_excess_return__", "market_excess_return"))
    ]
    repeated = {
        column: int((panel[column].diff() == 0).sum())
        for column in return_columns
        if int((panel[column].diff() == 0).sum()) > 0
    }
    checks["no_implicit_forward_filling"] = not repeated
    details["repeated_consecutive_return_values"] = str(repeated)

    # Unit consistency. Monthly percent returns and annualized percentage-point
    # rates occupy different but overlapping ranges, so each is checked against
    # its own declared band rather than a single global band.
    return_values = panel[return_columns].to_numpy(dtype=float)
    checks["return_units_are_percent_per_month"] = bool(
        np.nanmax(np.abs(return_values)) > 1.0 and np.nanmax(np.abs(return_values)) < 200.0
    )
    level_columns = [c for c in panel.columns if c.startswith("short_rate_level__")]
    if level_columns:
        level_values = panel[level_columns].to_numpy(dtype=float)
        checks["rate_units_are_annualized_percentage_points"] = bool(
            np.nanmin(level_values) >= 0.0 and np.nanmax(level_values) < 100.0
        )
    else:
        details["rate_units_are_annualized_percentage_points"] = (
            "no short-rate level column present"
        )
    checks["risk_free_return_is_percent_per_month"] = bool(
        panel["risk_free_return"].max() < 5.0 and panel["risk_free_return"].min() >= 0.0
    )

    # No accidental timing shift in the rate innovation.
    innovation_ok = True
    for name, (intercept, slope) in ar_parameters.items():
        column = f"short_rate_innovation__{name}"
        if column not in panel.columns:
            continue
        levels = short_rate_levels[name]
        current = levels.reindex(index).to_numpy(dtype=float)
        lagged = levels.reindex(index - 1).to_numpy(dtype=float)
        manual = current - intercept - slope * lagged
        innovation_ok &= bool(np.allclose(panel[column].to_numpy(dtype=float), manual, atol=1e-9))
    checks["innovation_has_no_timing_shift"] = innovation_ok

    # No accidental timing shift in the market factor.
    checks["market_factor_has_no_timing_shift"] = bool(
        np.allclose(
            panel["market_excess_return"].to_numpy(dtype=float),
            market_excess_return.reindex(index).to_numpy(dtype=float),
            atol=1e-12,
        )
    )

    # The excess-return step is exactly the raw return minus the same-month
    # risk-free return.
    excess_ok = True
    risk_free = panel["risk_free_return"].to_numpy(dtype=float)
    for family, frame in raw_portfolio_returns.items():
        for column in frame.columns:
            panel_column = f"portfolio_excess_return__{family}__{column}"
            if panel_column not in panel.columns:
                continue
            expected_values = frame[column].reindex(index).to_numpy(dtype=float) - risk_free
            excess_ok &= bool(
                np.allclose(panel[panel_column].to_numpy(dtype=float), expected_values, atol=1e-9)
            )
    checks["excess_returns_use_same_month_risk_free"] = excess_ok

    return PanelValidationReport(
        rows=len(panel),
        columns=int(panel.shape[1]),
        sample_start=str(index.min()),
        sample_end=str(index.max()),
        checks=checks,
        details=details,
    )
