import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.cross_section import (
    coefficient_table,
    estimate_fama_macbeth,
    estimate_gls_two_pass,
    estimate_ols_two_pass,
    leave_one_group_out,
    model_evaluation_table,
    simulate_factor_model,
    weak_factor_diagnostic,
    write_cross_section_outputs,
)
from short_rate_anomaly_regimes.models.diagnostics import grs_test


def _beta_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mkt": [0.8, 1.0, 1.2, 1.4, 0.7, 1.5],
            "rate": [-0.5, -0.1, 0.2, 0.6, -0.8, 0.9],
        },
        index=["asset_a", "asset_b", "asset_c", "asset_d", "asset_e", "asset_f"],
    )


def test_ols_two_pass_recovers_linear_risk_prices() -> None:
    betas = _beta_fixture()
    mean_returns = 0.01 + 0.05 * betas["mkt"] - 0.02 * betas["rate"]

    result = estimate_ols_two_pass(mean_returns, betas)

    assert result.risk_prices["const"] == pytest.approx(0.01)
    assert result.risk_prices["mkt"] == pytest.approx(0.05)
    assert result.risk_prices["rate"] == pytest.approx(-0.02)
    assert result.rmse == pytest.approx(0.0, abs=1e-14)
    assert result.mae == pytest.approx(0.0, abs=1e-14)
    assert result.max_abs_alpha == pytest.approx(0.0, abs=1e-14)
    assert result.r_squared == pytest.approx(1.0)
    assert result.estimator == "ols_two_pass"
    assert result.beta_source == "first_pass_time_series"


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


def test_ols_two_pass_applies_separate_corrected_uncertainty() -> None:
    betas = _beta_fixture()
    mean_returns = 0.01 + 0.05 * betas["mkt"] - 0.02 * betas["rate"]
    factor_covariance = pd.DataFrame(
        [[0.04, 0.0], [0.0, 0.02]],
        index=["mkt", "rate"],
        columns=["mkt", "rate"],
    )

    result = estimate_ols_two_pass(
        mean_returns,
        betas,
        factor_covariance=factor_covariance,
    )

    assert (result.corrected_standard_errors >= result.standard_errors).all()
    assert result.confidence_interval_low.name == "confidence_interval_low"


def test_ols_two_pass_rejects_disjoint_assets() -> None:
    betas = pd.DataFrame({"mkt": [1.0]}, index=["asset_a"])
    mean_returns = pd.Series([0.02], index=["asset_b"])

    with pytest.raises(ValueError, match="No common assets"):
        estimate_ols_two_pass(mean_returns, betas)


def test_gls_two_pass_uses_explicit_weighting_matrix() -> None:
    betas = _beta_fixture()
    mean_returns = 0.01 + 0.05 * betas["mkt"] - 0.02 * betas["rate"]
    covariance = pd.DataFrame(
        np.eye(len(betas)) * 0.02,
        index=betas.index,
        columns=betas.index,
    )

    result = estimate_gls_two_pass(
        mean_returns,
        betas,
        pricing_error_covariance=covariance,
        regularization=1e-8,
    )

    assert result.estimator == "gls_two_pass"
    assert result.weighting_matrix is not None
    assert result.risk_prices["mkt"] == pytest.approx(0.05)


def test_gls_two_pass_rejects_negative_regularization() -> None:
    with pytest.raises(ValueError, match="nonnegative"):
        estimate_gls_two_pass(
            pd.Series([0.01], index=["a"]),
            pd.DataFrame({"mkt": [1.0]}, index=["a"]),
            pricing_error_covariance=pd.DataFrame([[1.0]], index=["a"], columns=["a"]),
            regularization=-1.0,
        )


def test_fama_macbeth_fixed_beta_panel_estimates_average_prices() -> None:
    betas = _beta_fixture()
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    returns = pd.DataFrame(
        {
            asset: 0.01 + 0.04 * beta["mkt"] - 0.01 * beta["rate"]
            for asset, beta in betas.iterrows()
        },
        index=dates,
    )

    result = estimate_fama_macbeth(returns, betas)

    assert result.estimator == "fama_macbeth"
    assert result.risk_prices["mkt"] == pytest.approx(0.04)
    assert result.risk_prices["rate"] == pytest.approx(-0.01)


def test_fama_macbeth_rejects_insufficient_complete_cross_sections() -> None:
    with pytest.raises(ValueError, match="No common assets"):
        estimate_fama_macbeth(
            pd.DataFrame({"asset": [0.01]}),
            pd.DataFrame({"mkt": [1.0]}, index=["other"]),
        )


def test_fama_macbeth_rejects_cross_sections_with_too_few_assets() -> None:
    returns = pd.DataFrame(
        {"asset_a": [0.01, 0.02], "asset_b": [0.02, 0.03]},
        index=pd.date_range("2020-01-31", periods=2, freq="ME"),
    )
    betas = pd.DataFrame(
        {"mkt": [1.0, 1.1], "rate": [0.1, 0.2]},
        index=["asset_a", "asset_b"],
    )

    with pytest.raises(ValueError, match="enough complete assets"):
        estimate_fama_macbeth(returns, betas)


def test_weak_factor_diagnostic_rejects_empty_beta_matrix() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        weak_factor_diagnostic(pd.DataFrame())


def test_weak_factor_diagnostic_flags_ill_conditioned_matrix() -> None:
    warning = weak_factor_diagnostic(
        pd.DataFrame({"a": [1.0, 1.0, 1.0], "b": [1.0, 1.0, 1.0 + 1e-9]}),
        condition_threshold=10.0,
    )

    assert warning.warning == "beta_matrix_ill_conditioned"


def test_weak_factor_diagnostic_flags_rank_deficiency() -> None:
    warning = weak_factor_diagnostic(pd.DataFrame({"a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0]}))

    assert warning.warning == "beta_matrix_rank_deficient"


def test_model_evaluation_and_leave_one_group_out_tables() -> None:
    betas = _beta_fixture()
    mean_returns = 0.01 + 0.05 * betas["mkt"] - 0.02 * betas["rate"]
    groups = pd.Series(
        ["value", "value", "investment", "investment", "duration", "duration"],
        index=betas.index,
    )
    results = leave_one_group_out(mean_returns, betas, groups)
    table = model_evaluation_table(results)

    assert set(results) == {"duration", "investment", "value"}
    assert {"model", "estimator", "rmse", "max_abs_alpha"} <= set(table.columns)


def test_simulated_factor_model_recovers_known_prices() -> None:
    betas = _beta_fixture()
    prices = pd.Series({"mkt": 0.04, "rate": -0.02})
    returns, _factors, expected = simulate_factor_model(
        n_periods=120,
        betas=betas,
        risk_prices=prices,
        residual_scale=0.0,
        seed=123,
    )

    result = estimate_ols_two_pass(returns.mean(axis=0), betas, include_intercept=False)

    assert expected.loc["asset_a"] == pytest.approx(returns.mean(axis=0).loc["asset_a"])
    assert result.risk_prices["mkt"] == pytest.approx(0.04)
    assert result.risk_prices["rate"] == pytest.approx(-0.02)


def test_coefficient_table_and_output_writer(tmp_path: Path) -> None:
    betas = _beta_fixture()
    mean_returns = 0.01 + 0.05 * betas["mkt"] - 0.02 * betas["rate"]
    result = estimate_ols_two_pass(mean_returns, betas)

    table = coefficient_table(result)
    assert {"risk_price", "corrected_standard_error", "estimator"} <= set(table.columns)

    metrics_path = tmp_path / "metrics.json"
    write_cross_section_outputs(
        result,
        coefficients_path=tmp_path / "coefficients.parquet",
        pricing_errors_path=tmp_path / "pricing_errors.parquet",
        metrics_path=metrics_path,
        metadata_path=tmp_path / "metadata.json",
        metadata={"model": "fixture", "portfolio_set": "fixture", "code_commit": "test"},
    )

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["n_assets"] == 6
    assert (tmp_path / "coefficients.parquet").is_file()


def test_grs_test_accepts_zero_alpha_fixture() -> None:
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
    factors = pd.DataFrame(
        {
            "mkt": np.linspace(-0.04, 0.05, 36),
            "rate": np.sin(np.arange(36)) / 100.0,
        },
        index=dates,
    )
    returns = pd.DataFrame(
        {
            "asset_a": 1.1 * factors["mkt"] - 0.2 * factors["rate"],
            "asset_b": 0.8 * factors["mkt"] + 0.4 * factors["rate"],
            "asset_c": 1.4 * factors["mkt"] - 0.1 * factors["rate"],
        },
        index=dates,
    )

    result = grs_test(returns=returns, factors=factors)

    assert result["statistic"] == pytest.approx(0.0, abs=1e-10)
    assert 0.0 <= result["p_value"] <= 1.0


def test_grs_test_reports_nonzero_alpha_statistic() -> None:
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
    factor = pd.Series(np.linspace(-0.04, 0.05, 36), index=dates, name="mkt")
    factors = factor.to_frame()
    noise_a = pd.Series(np.sin(np.arange(36)) / 1_000.0, index=dates)
    noise_b = pd.Series(np.cos(np.arange(36)) / 1_000.0, index=dates)
    noise_c = pd.Series(np.sin(np.arange(36) * 0.5) / 1_000.0, index=dates)
    returns = pd.DataFrame(
        {
            "asset_a": 0.01 + 1.1 * factor + noise_a,
            "asset_b": -0.005 + 0.8 * factor + noise_b,
            "asset_c": 0.004 + 1.4 * factor + noise_c,
        },
        index=dates,
    )

    result = grs_test(returns=returns, factors=factors)

    assert result["statistic"] > 0
    assert 0.0 <= result["p_value"] <= 1.0


def test_grs_test_rejects_disjoint_panels() -> None:
    with pytest.raises(ValueError, match="No common complete observations"):
        grs_test(
            returns=pd.DataFrame({"asset": [0.01]}, index=[pd.Timestamp("2020-01-31")]),
            factors=pd.DataFrame({"mkt": [0.01]}, index=[pd.Timestamp("2020-02-29")]),
        )


def test_grs_test_rejects_insufficient_observations() -> None:
    dates = pd.date_range("2020-01-31", periods=3, freq="ME")
    with pytest.raises(ValueError, match="Insufficient observations"):
        grs_test(
            returns=pd.DataFrame({"asset_a": [0.01, 0.02, 0.03]}, index=dates),
            factors=pd.DataFrame({"mkt": [0.01, 0.02, 0.03]}, index=dates),
        )
