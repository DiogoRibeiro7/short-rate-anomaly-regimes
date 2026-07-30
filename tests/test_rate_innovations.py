import numpy as np
import pandas as pd

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
