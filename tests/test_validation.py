import pandas as pd
import pytest

from short_rate_anomaly_regimes.data.validation import validate_monthly_panel


def test_valid_monthly_panel_returns_summary() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-02-29", "2020-03-31"],
            "asset": [1.0, None, 3.0],
        }
    )

    summary = validate_monthly_panel(frame)

    assert summary.rows == 3
    assert summary.columns == 2
    assert summary.missing_values == 1
    assert summary.duplicate_dates == 0
    assert summary.monotonic_dates is True
    assert summary.continuous_months is True


def test_duplicate_month_is_rejected() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-01", "2020-01-31"],
            "asset": [1.0, 2.0],
        }
    )
    with pytest.raises(ValueError, match="calendar month"):
        validate_monthly_panel(frame)


def test_missing_date_column_is_rejected() -> None:
    frame = pd.DataFrame({"asset": [1.0]})

    with pytest.raises(ValueError, match="Missing date column"):
        validate_monthly_panel(frame)


def test_duplicate_exact_date_is_rejected() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-01-31"],
            "asset": [1.0, 2.0],
        }
    )

    with pytest.raises(ValueError, match="duplicate monthly dates"):
        validate_monthly_panel(frame)


def test_unsorted_dates_are_rejected() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-02-29", "2020-01-31"],
            "asset": [1.0, 2.0],
        }
    )

    with pytest.raises(ValueError, match="ascending order"):
        validate_monthly_panel(frame)


def test_infinite_numeric_values_are_rejected() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-02-29"],
            "asset": [1.0, float("inf")],
        }
    )

    with pytest.raises(ValueError, match="infinite values"):
        validate_monthly_panel(frame)


def test_month_continuity_and_sample_endpoints_are_checked() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-03-31"],
            "asset": [1.0, 2.0],
        }
    )

    with pytest.raises(ValueError, match="month continuity"):
        validate_monthly_panel(frame, require_continuous_months=True)
    with pytest.raises(ValueError, match="Expected sample end"):
        validate_monthly_panel(frame, sample_end="2020-04")


def test_units_bounds_portfolio_count_and_factor_names_are_checked() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-02-29"],
            "P1": [0.5, 0.6],
            "Mkt-RF": [0.1, 0.2],
        }
    )

    with pytest.raises(ValueError, match="percent_return"):
        validate_monthly_panel(frame, units="percent_return")
    with pytest.raises(ValueError, match="outside declared bounds"):
        validate_monthly_panel(frame, numeric_bounds=(-0.1, 0.1))
    with pytest.raises(ValueError, match="Expected 25 portfolio columns"):
        validate_monthly_panel(frame, expected_portfolio_count=25)
    with pytest.raises(ValueError, match="Missing expected factor columns"):
        validate_monthly_panel(frame, factor_columns=("RF",))


def test_expected_columns_sample_start_and_decimal_units_are_checked() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-02-29"],
            "asset": [10.0, 20.0],
        }
    )

    with pytest.raises(ValueError, match="Missing expected columns"):
        validate_monthly_panel(frame, expected_columns=("missing",))
    with pytest.raises(ValueError, match="Expected sample start"):
        validate_monthly_panel(frame, sample_start="2020-02")
    with pytest.raises(ValueError, match="decimal_return"):
        validate_monthly_panel(frame, units="decimal_return")
