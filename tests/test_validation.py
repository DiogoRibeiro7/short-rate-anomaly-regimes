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
