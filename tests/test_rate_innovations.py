import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.rates.innovations import (
    ARInnovationConfig,
    estimate_ar_innovation,
)


def test_ar1_innovation_preserves_monthly_index() -> None:
    rng = np.random.default_rng(123)
    dates = pd.date_range("2000-01-31", periods=180, freq="ME")
    values = np.zeros(len(dates), dtype=float)
    shocks = rng.normal(scale=0.2, size=len(dates))
    for position in range(1, len(values)):
        values[position] = 0.1 + 0.8 * values[position - 1] + shocks[position]
    result = estimate_ar_innovation(
        pd.Series(values, index=dates, name="rate"),
        config=ARInnovationConfig(lags=1),
    )
    assert result.innovations.index.equals(dates[1:])
    assert abs(float(result.innovations.mean())) < 1e-10
    assert 0.6 < float(result.parameters["lag_1"]) < 1.0


def test_ar_innovation_requires_datetime_index() -> None:
    rate = pd.Series([1.0, 1.1, 1.2, 1.3], index=[1, 2, 3, 4])

    with pytest.raises(TypeError, match="DatetimeIndex"):
        estimate_ar_innovation(rate)


def test_ar_innovation_rejects_short_series() -> None:
    dates = pd.date_range("2020-01-31", periods=3, freq="ME")
    rate = pd.Series([1.0, 1.1, 1.2], index=dates)

    with pytest.raises(ValueError, match="Insufficient observations"):
        estimate_ar_innovation(rate, config=ARInnovationConfig(lags=1))


def test_ar_innovation_standardizes_residuals() -> None:
    dates = pd.date_range("2020-01-31", periods=12, freq="ME")
    rate = pd.Series(
        [1.00, 1.10, 1.18, 1.28, 1.35, 1.46, 1.55, 1.61, 1.73, 1.80, 1.95, 2.02],
        index=dates,
    )

    result = estimate_ar_innovation(rate, config=ARInnovationConfig(standardize=True))

    assert float(result.innovations.std(ddof=1)) == pytest.approx(1.0)
