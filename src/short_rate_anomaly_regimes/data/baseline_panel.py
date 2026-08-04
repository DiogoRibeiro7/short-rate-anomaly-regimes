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

    # Bounds alone allow a panel truncated at either end to pass. The frozen
    # window is exact, so the first and last keys must equal it; otherwise a
    # source missing its earliest or latest month would silently shorten the
    # baseline without any check firing.
    checks["panel_starts_exactly_at_window_start"] = bool(index.min() == start)
    checks["panel_ends_exactly_at_window_end"] = bool(index.max() == endpoint)
    expected_window = pd.period_range(start, endpoint, freq="M")
    checks["panel_covers_the_whole_frozen_window"] = list(index) == list(expected_window)
    details["expected_window_months"] = str(len(expected_window))
    details["observed_window_months"] = str(len(index))

    checks["no_missing_values"] = not bool(panel.isna().to_numpy().any())
    checks["no_infinite_values"] = not bool(np.isinf(panel.to_numpy(dtype=float)).any())

    return_columns = [
        column
        for column in panel.columns
        if column.startswith(("portfolio_excess_return__", "market_excess_return"))
    ]

    # Two adjacent months carrying the same value is not evidence of forward
    # filling. Provider returns are published to two decimals, so equal
    # neighbours occur naturally. The reliable test is whether every panel value
    # still equals its frozen source at the same month, which is established by
    # the source-equality checks below; a carried-forward value would differ from
    # its source. The repeated-value count is retained as a descriptive detail
    # only, with no pass or fail attached.
    details["repeated_consecutive_return_values"] = str(
        {
            column: int((panel[column].diff() == 0).sum())
            for column in return_columns
            if int((panel[column].diff() == 0).sum()) > 0
        }
    )

    # Unit consistency, evaluated per column. A panel-wide maximum lets a
    # decimal-scale column hide behind any other column that exceeds one percent,
    # so each return column is checked against the declared band on its own.
    off_scale_return_columns = [
        column
        for column in return_columns
        if not (1.0 < float(np.nanmax(np.abs(panel[column].to_numpy(dtype=float)))) < 200.0)
    ]
    checks["return_units_are_percent_per_month"] = not off_scale_return_columns
    details["return_columns_outside_declared_units"] = str(off_scale_return_columns)
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

    # No accidental timing shift in the rate innovation. Every innovation column
    # present in the panel must be verifiable: an unverifiable column is a
    # failure, not something to skip, because skipping would let a
    # timing-shifted or arbitrary innovation ride through unchecked. The reverse
    # direction, a declared parameter whose column is absent, is harmless.
    innovation_columns = [
        column for column in panel.columns if column.startswith("short_rate_innovation__")
    ]
    unverifiable_innovations = [
        column
        for column in innovation_columns
        if column.removeprefix("short_rate_innovation__") not in ar_parameters
        or column.removeprefix("short_rate_innovation__") not in short_rate_levels
    ]
    innovation_ok = not unverifiable_innovations
    for column in innovation_columns:
        name = column.removeprefix("short_rate_innovation__")
        if name not in ar_parameters or name not in short_rate_levels:
            continue
        intercept, slope = ar_parameters[name]
        levels = short_rate_levels[name]
        current = levels.reindex(index).to_numpy(dtype=float)
        lagged = levels.reindex(index - 1).to_numpy(dtype=float)
        manual = current - intercept - slope * lagged
        innovation_ok &= bool(np.allclose(panel[column].to_numpy(dtype=float), manual, atol=1e-9))
    checks["innovation_has_no_timing_shift"] = innovation_ok
    details["unverifiable_innovation_columns"] = str(unverifiable_innovations)

    # No accidental timing shift in the market factor.
    checks["market_factor_has_no_timing_shift"] = bool(
        np.allclose(
            panel["market_excess_return"].to_numpy(dtype=float),
            market_excess_return.reindex(index).to_numpy(dtype=float),
            atol=1e-12,
        )
    )

    # The excess-return step is exactly the raw return minus the same-month
    # risk-free return. As with the innovations, a portfolio column that cannot
    # be traced back to a frozen source is a failure rather than a skip.
    risk_free = panel["risk_free_return"].to_numpy(dtype=float)
    available_sources = {
        f"portfolio_excess_return__{family}__{column}": frame[column]
        for family, frame in raw_portfolio_returns.items()
        for column in frame.columns
    }
    portfolio_columns = [
        column for column in panel.columns if column.startswith("portfolio_excess_return__")
    ]
    untraceable_portfolios = [
        column for column in portfolio_columns if column not in available_sources
    ]
    excess_ok = not untraceable_portfolios
    for column in portfolio_columns:
        source = available_sources.get(column)
        if source is None:
            continue
        expected_values = source.reindex(index).to_numpy(dtype=float) - risk_free
        excess_ok &= bool(
            np.allclose(panel[column].to_numpy(dtype=float), expected_values, atol=1e-9)
        )
    checks["excess_returns_use_same_month_risk_free"] = excess_ok
    details["untraceable_portfolio_columns"] = str(untraceable_portfolios)

    # Forward filling is detectable precisely because a carried-forward value
    # would no longer equal its frozen source. The gate is therefore the
    # conjunction of the source-equality checks rather than a value heuristic.
    checks["no_implicit_forward_filling"] = bool(
        checks["market_factor_has_no_timing_shift"]
        and checks["excess_returns_use_same_month_risk_free"]
        and checks["innovation_has_no_timing_shift"]
    )

    return PanelValidationReport(
        rows=len(panel),
        columns=int(panel.shape[1]),
        sample_start=str(index.min()),
        sample_end=str(index.max()),
        checks=checks,
        details=details,
    )
