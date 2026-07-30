import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.time_series import estimate_time_series_betas


def test_time_series_betas_recover_deterministic_loadings() -> None:
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    factors = pd.DataFrame(
        {
            "mkt": [-0.03, -0.01, 0.0, 0.02, 0.04, 0.01, -0.02, 0.03],
            "rate": [0.01, 0.02, -0.01, 0.0, 0.03, -0.02, 0.01, 0.02],
        },
        index=dates,
    )
    excess_returns = pd.DataFrame(
        {
            "asset_a": 0.01 + 1.2 * factors["mkt"] - 0.4 * factors["rate"],
            "asset_b": -0.02 + 0.7 * factors["mkt"] + 0.3 * factors["rate"],
        },
        index=dates,
    )

    result = estimate_time_series_betas(excess_returns, factors, hac_lags=1)

    assert result.coefficients.loc["asset_a", "const"] == pytest.approx(0.01)
    assert result.coefficients.loc["asset_a", "mkt"] == pytest.approx(1.2)
    assert result.coefficients.loc["asset_a", "rate"] == pytest.approx(-0.4)
    assert result.coefficients.loc["asset_b", "const"] == pytest.approx(-0.02)
    assert result.coefficients.loc["asset_b", "mkt"] == pytest.approx(0.7)
    assert result.coefficients.loc["asset_b", "rate"] == pytest.approx(0.3)
    assert result.residuals.index.equals(dates)
    assert result.r_squared.loc["asset_a"] == pytest.approx(1.0)


def test_time_series_betas_reject_no_complete_common_observations() -> None:
    returns = pd.DataFrame(
        {"asset": [0.01, None]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29"]),
    )
    factors = pd.DataFrame(
        {"mkt": [None, 0.02]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29"]),
    )

    with pytest.raises(ValueError, match="No common complete observations"):
        estimate_time_series_betas(returns, factors, hac_lags=1)
