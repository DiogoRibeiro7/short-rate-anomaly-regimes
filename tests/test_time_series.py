import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from short_rate_anomaly_regimes.models.time_series import (
    align_first_pass_inputs,
    automatic_newey_west_lags,
    coefficient_table,
    construct_excess_returns,
    estimate_matrix_ols_hac,
    estimate_time_series_betas,
    first_pass_diagnostics,
    write_time_series_outputs,
)


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
    assert result.standard_errors.columns.tolist() == ["const", "mkt", "rate"]
    assert result.p_values.index.tolist() == ["asset_a", "asset_b"]
    assert result.factor_order == ("mkt", "rate")
    assert result.covariance == "newey_west"
    assert result.nobs.loc["asset_a"] == 8


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


def test_construct_excess_returns_subtracts_risk_free_rate() -> None:
    dates = pd.date_range("2020-01-31", periods=3, freq="ME")
    portfolios = pd.DataFrame({"asset_a": [0.03, 0.04, 0.01]}, index=dates)
    risk_free = pd.Series([0.01, 0.02, 0.005], index=dates, name="rf")

    excess = construct_excess_returns(portfolios, risk_free)

    assert excess["asset_a"].tolist() == pytest.approx([0.02, 0.02, 0.005])


def test_construct_excess_returns_rejects_non_datetime_index() -> None:
    with pytest.raises(TypeError, match="DatetimeIndex"):
        construct_excess_returns(
            pd.DataFrame({"asset": [0.01]}, index=[1]),
            pd.Series([0.001], index=[1]),
        )


def test_align_first_pass_inputs_records_observation_losses() -> None:
    returns = pd.DataFrame(
        {"asset": [0.01, None, 0.03]},
        index=pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"]),
    )
    factors = pd.DataFrame(
        {"mkt": [0.02, 0.03, 0.04]},
        index=pd.to_datetime(["2020-02-29", "2020-03-31", "2020-04-30"]),
    )

    aligned_returns, aligned_factors, summary = align_first_pass_inputs(
        excess_returns=returns,
        factors=factors,
    )

    assert aligned_returns.index.tolist() == [pd.Timestamp("2020-03-31")]
    assert aligned_factors.index.tolist() == [pd.Timestamp("2020-03-31")]
    assert summary.dropped_return_dates == 1
    assert summary.dropped_factor_dates == 1
    assert summary.dropped_incomplete_rows == 1


def test_align_first_pass_inputs_rejects_duplicate_dates() -> None:
    duplicate_index = pd.to_datetime(["2020-01-31", "2020-01-31"])
    with pytest.raises(ValueError, match="duplicate dates"):
        align_first_pass_inputs(
            excess_returns=pd.DataFrame({"asset": [0.01, 0.02]}, index=duplicate_index),
            factors=pd.DataFrame(
                {"mkt": [0.01, 0.02]},
                index=pd.date_range("2020-01-31", periods=2, freq="ME"),
            ),
        )


def test_automatic_newey_west_lag_rule_matches_formula() -> None:
    assert automatic_newey_west_lags(100) == 4
    assert automatic_newey_west_lags(12) >= 0
    with pytest.raises(ValueError, match="positive"):
        automatic_newey_west_lags(0)


def test_matrix_ols_hac_matches_statsmodels_coefficients_and_covariance() -> None:
    dates = pd.date_range("2020-01-31", periods=12, freq="ME")
    factors = pd.DataFrame(
        {
            "mkt": np.linspace(-0.04, 0.05, 12),
            "rate": np.sin(np.arange(12)) / 100.0,
        },
        index=dates,
    )
    response = 0.01 + 0.8 * factors["mkt"] - 0.3 * factors["rate"]
    response = response + pd.Series(np.linspace(-0.003, 0.004, 12), index=dates)

    matrix = estimate_matrix_ols_hac(response, factors, hac_lags=2)
    design = sm.add_constant(factors, has_constant="add")
    statsmodels_result = sm.OLS(response, design).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": 2, "use_correction": False},
    )

    assert matrix.parameters.to_numpy() == pytest.approx(statsmodels_result.params.to_numpy())
    assert matrix.covariance.to_numpy() == pytest.approx(statsmodels_result.cov_params().to_numpy())


def test_first_pass_diagnostics_reports_influence_statistics() -> None:
    dates = pd.date_range("2020-01-31", periods=12, freq="ME")
    factors = pd.DataFrame({"mkt": np.linspace(-0.03, 0.04, 12)}, index=dates)
    response = pd.Series(0.01 + 1.5 * factors["mkt"].to_numpy(), index=dates)
    model = sm.OLS(response, sm.add_constant(factors, has_constant="add")).fit()

    diagnostics = first_pass_diagnostics(
        model,
        asset="asset_a",
        crisis_months=(pd.Timestamp("2020-03-31"),),
    )

    assert diagnostics["asset"] == "asset_a"
    assert diagnostics["max_leverage"] > 0
    assert diagnostics["crisis_month_count"] == 1


def test_coefficient_table_and_output_writer(tmp_path: Path) -> None:
    dates = pd.date_range("2020-01-31", periods=10, freq="ME")
    factors = pd.DataFrame({"mkt": np.linspace(-0.02, 0.03, 10)}, index=dates)
    returns = pd.DataFrame({"asset": 0.01 + 0.5 * factors["mkt"]}, index=dates)
    result = estimate_time_series_betas(returns, factors, hac_lags=1)

    table = coefficient_table(result)
    assert {"asset", "parameter", "coefficient", "standard_error"} <= set(table.columns)

    metadata_path = tmp_path / "metadata.json"
    write_time_series_outputs(
        result,
        coefficients_path=tmp_path / "coefficients.parquet",
        residuals_path=tmp_path / "residuals.parquet",
        diagnostics_path=tmp_path / "diagnostics.json",
        table_path=tmp_path / "table.csv",
        metadata_path=metadata_path,
        metadata={
            "model": "capm",
            "sample": "fixture",
            "rate_factor": "none",
            "portfolio_set": "fixture",
            "units": "decimal_return",
            "code_commit": "test",
        },
    )

    payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert payload["covariance"] == "newey_west"
    assert payload["factor_order"] == ["mkt"]
    assert (tmp_path / "coefficients.parquet").is_file()
