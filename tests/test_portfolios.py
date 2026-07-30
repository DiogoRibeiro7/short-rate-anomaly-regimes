from pathlib import Path

import pandas as pd
import pytest

from short_rate_anomaly_regimes.portfolios.loaders import load_monthly_portfolios


def test_load_monthly_portfolios_reads_csv_with_datetime_index(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "portfolios.csv"
    portfolio_path.write_text(
        "date,asset_a,asset_b\n2020-01-31,0.01,0.04\n2020-02-29,0.02,0.03\n",
        encoding="utf-8",
    )

    frame = load_monthly_portfolios(portfolio_path)

    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.tolist() == [
        pd.Timestamp("2020-01-31"),
        pd.Timestamp("2020-02-29"),
    ]
    assert frame.loc[pd.Timestamp("2020-01-31"), "asset_a"] == pytest.approx(0.01)


def test_load_monthly_portfolios_rejects_unsupported_extension(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "portfolios.txt"
    portfolio_path.write_text("date,asset\n2020-01-31,0.01\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported portfolio file extension"):
        load_monthly_portfolios(portfolio_path)


def test_load_monthly_portfolios_runs_monthly_validation(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "invalid.csv"
    portfolio_path.write_text(
        "date,asset\n2020-01-01,0.01\n2020-01-31,0.02\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="calendar month"):
        load_monthly_portfolios(portfolio_path)
