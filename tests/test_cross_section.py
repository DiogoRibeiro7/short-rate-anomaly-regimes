import math

import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.cross_section import (
    estimate_fama_macbeth,
    estimate_gls_two_pass,
    estimate_ols_two_pass,
)


def test_ols_two_pass_recovers_linear_risk_prices() -> None:
    betas = pd.DataFrame(
        {
            "mkt": [0.8, 1.0, 1.2, 1.4],
            "rate": [-0.5, -0.1, 0.2, 0.6],
        },
        index=["asset_a", "asset_b", "asset_c", "asset_d"],
    )
    mean_returns = 0.01 + 0.05 * betas["mkt"] - 0.02 * betas["rate"]

    result = estimate_ols_two_pass(mean_returns, betas)

    assert result.risk_prices["const"] == pytest.approx(0.01)
    assert result.risk_prices["mkt"] == pytest.approx(0.05)
    assert result.risk_prices["rate"] == pytest.approx(-0.02)
    assert result.rmse == pytest.approx(0.0, abs=1e-14)
    assert result.mae == pytest.approx(0.0, abs=1e-14)
    assert result.r_squared == pytest.approx(1.0)


def test_ols_two_pass_returns_nan_r_squared_for_constant_returns() -> None:
    betas = pd.DataFrame({"mkt": [0.8, 1.0, 1.2]}, index=["a", "b", "c"])
    mean_returns = pd.Series([0.02, 0.02, 0.02], index=["a", "b", "c"])

    result = estimate_ols_two_pass(mean_returns, betas)

    assert math.isnan(result.r_squared)


def test_ols_two_pass_can_omit_intercept() -> None:
    betas = pd.DataFrame({"mkt": [0.8, 1.0, 1.2]}, index=["a", "b", "c"])
    mean_returns = 0.04 * betas["mkt"]

    result = estimate_ols_two_pass(mean_returns, betas, include_intercept=False)

    assert "const" not in result.risk_prices.index
    assert result.risk_prices["mkt"] == pytest.approx(0.04)


def test_ols_two_pass_rejects_disjoint_assets() -> None:
    betas = pd.DataFrame({"mkt": [1.0]}, index=["asset_a"])
    mean_returns = pd.Series([0.02], index=["asset_b"])

    with pytest.raises(ValueError, match="No common assets"):
        estimate_ols_two_pass(mean_returns, betas)


def test_unverified_second_pass_estimators_are_milestone_gated() -> None:
    with pytest.raises(NotImplementedError, match="Milestone 6"):
        estimate_gls_two_pass()

    with pytest.raises(NotImplementedError, match="Milestone 6"):
        estimate_fama_macbeth()
