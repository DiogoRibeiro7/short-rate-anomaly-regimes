from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.rates.innovations import (
    ARInnovationConfig,
    RateUnit,
    aggregate_identified_surprises,
    align_market_rate_and_rf,
    build_first_difference_factor,
    build_local_level_factor,
    build_named_ar_factor,
    combine_named_factors,
    compare_article_targets,
    convert_rate_units,
    estimate_ar_innovation,
    factor_correlations,
    factor_descriptive_statistics,
    innovation_diagnostics,
    prepare_rate_columns,
    recursive_ar_coefficients,
    write_factor_outputs,
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


def test_ar1_simulation_recovers_parameters() -> None:
    rng = np.random.default_rng(321)
    dates = pd.date_range("1980-01-31", periods=600, freq="ME")
    values = np.zeros(len(dates), dtype=float)
    shocks = rng.normal(scale=0.05, size=len(dates))
    intercept = 0.2
    phi = 0.65
    for position in range(1, len(values)):
        values[position] = intercept + phi * values[position - 1] + shocks[position]

    result = estimate_ar_innovation(pd.Series(values, index=dates, name="rate"))

    assert float(result.parameters["const"]) == pytest.approx(intercept, abs=0.03)
    assert float(result.parameters["lag_1"]) == pytest.approx(phi, abs=0.05)


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


def test_ar_innovation_rejects_zero_variance_standardization() -> None:
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    rate = pd.Series([2.0, 2.0, 2.0, 2.0, 2.0, 2.0], index=dates)

    with pytest.raises(ValueError, match="zero-variance"):
        estimate_ar_innovation(rate, config=ARInnovationConfig(standardize=True))


def test_prepare_rate_columns_preserves_source_and_converted_units() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-02-29"],
            "fedfunds": [125.0, 150.0],
        }
    )

    prepared = prepare_rate_columns(
        frame,
        date_column="date",
        value_column="fedfunds",
        rate_id="ffr",
        source_unit="basis_points",
        transformed_unit="percent",
    )

    assert list(prepared.columns) == ["ffr_basis_points", "ffr_percent"]
    assert prepared["ffr_percent"].tolist() == [1.25, 1.5]


def test_convert_rate_units_round_trips_percent_decimal_and_basis_points() -> None:
    dates = pd.date_range("2020-01-31", periods=2, freq="ME")
    rate = pd.Series([1.25, 1.50], index=dates, name="rate")

    decimal = convert_rate_units(rate, source_unit="percent", target_unit="decimal")
    basis_points = convert_rate_units(decimal, source_unit="decimal", target_unit="basis_points")

    assert decimal.tolist() == [0.0125, 0.015]
    assert basis_points.tolist() == [125.0, 150.0]


def test_convert_rate_units_handles_same_unit_and_rejects_unknown_units() -> None:
    dates = pd.date_range("2020-01-31", periods=2, freq="ME")
    rate = pd.Series([1.25, 1.50], index=dates, name="rate")

    same = convert_rate_units(rate, source_unit="percent", target_unit="percent")

    assert same.equals(rate)
    with pytest.raises(ValueError, match="Unsupported source unit"):
        convert_rate_units(
            rate,
            source_unit=cast(RateUnit, "unknown"),
            target_unit="percent",
        )
    with pytest.raises(ValueError, match="Unsupported target unit"):
        convert_rate_units(
            rate,
            source_unit="percent",
            target_unit=cast(RateUnit, "unknown"),
        )


def test_prepare_rate_columns_rejects_missing_columns_and_duplicate_dates() -> None:
    with pytest.raises(ValueError, match="Missing date column"):
        prepare_rate_columns(
            pd.DataFrame({"fedfunds": [1.0]}),
            date_column="date",
            value_column="fedfunds",
            rate_id="ffr",
            source_unit="percent",
        )
    with pytest.raises(ValueError, match="Missing value column"):
        prepare_rate_columns(
            pd.DataFrame({"date": ["2020-01-31"]}),
            date_column="date",
            value_column="fedfunds",
            rate_id="ffr",
            source_unit="percent",
        )
    with pytest.raises(ValueError, match="duplicate dates"):
        prepare_rate_columns(
            pd.DataFrame(
                {
                    "date": ["2020-01-31", "2020-01-31"],
                    "fedfunds": [1.0, 2.0],
                }
            ),
            date_column="date",
            value_column="fedfunds",
            rate_id="ffr",
            source_unit="percent",
        )


def test_named_ar_factor_uses_explicit_rate_and_method_namespace() -> None:
    dates = pd.date_range("2020-01-31", periods=24, freq="ME")
    rate = pd.Series(np.linspace(1.0, 2.0, len(dates)), index=dates)

    ar1 = build_named_ar_factor(rate, rate_name="ffr", method="ar1")
    ar2 = build_named_ar_factor(rate, rate_name="ffr", method="ar2")

    assert ar1.result.innovations.name == "ffr_ar1_innovation"
    assert ar2.result.innovations.name == "ffr_ar2_innovation"
    assert "lag_2" in ar2.result.parameters.index


def test_first_difference_and_local_level_factors_use_separate_namespaces() -> None:
    rng = np.random.default_rng(123)
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
    rate = pd.Series(rng.normal(size=len(dates)).cumsum(), index=dates)

    first_difference = build_first_difference_factor(rate, rate_name="tbill")
    local_level = build_local_level_factor(rate, rate_name="tbill")

    assert first_difference.name == "tbill_first_difference_innovation"
    assert local_level.name == "tbill_local_level_innovation"
    assert first_difference.index[0] == dates[1]


def test_alternative_factor_builders_reject_invalid_inputs() -> None:
    bad_index_rate = pd.Series([1.0, 1.1, 1.2], index=[1, 2, 3])
    short_dates = pd.date_range("2020-01-31", periods=4, freq="ME")
    short_rate = pd.Series([1.0, 1.1, 1.2, 1.3], index=short_dates)

    with pytest.raises(TypeError, match="DatetimeIndex"):
        build_first_difference_factor(bad_index_rate, rate_name="ffr")
    with pytest.raises(TypeError, match="DatetimeIndex"):
        build_local_level_factor(bad_index_rate, rate_name="ffr")
    with pytest.raises(ValueError, match="At least 8 observations"):
        build_local_level_factor(short_rate, rate_name="ffr")


def test_aggregate_identified_surprises_sums_events_by_month_without_lookahead() -> None:
    surprises = pd.DataFrame(
        {
            "event_time": ["2020-01-15", "2020-01-31", "2020-02-03"],
            "surprise": [0.1, -0.03, 0.2],
        }
    )

    monthly = aggregate_identified_surprises(
        surprises,
        date_column="event_time",
        value_column="surprise",
        factor_name="policy_surprise",
    )

    assert monthly.name == "policy_surprise"
    assert monthly.iloc[0] == pytest.approx(0.07)
    assert monthly.index[0] == pd.Timestamp("2020-01-31")


def test_aggregate_identified_surprises_rejects_missing_columns() -> None:
    surprises = pd.DataFrame({"event_time": ["2020-01-15"], "surprise": [0.1]})

    with pytest.raises(ValueError, match="Missing date column"):
        aggregate_identified_surprises(
            surprises,
            date_column="missing",
            value_column="surprise",
            factor_name="policy_surprise",
        )
    with pytest.raises(ValueError, match="Missing value column"):
        aggregate_identified_surprises(
            surprises,
            date_column="event_time",
            value_column="missing",
            factor_name="policy_surprise",
        )


def test_combine_named_factors_and_align_market_rate_rf_without_lookahead() -> None:
    dates = pd.date_range("2020-01-31", periods=36, freq="ME")
    ffr = build_named_ar_factor(
        pd.Series(np.linspace(1.0, 2.0, len(dates)), index=dates), rate_name="ffr", method="ar1"
    )
    tbill = build_named_ar_factor(
        pd.Series(np.linspace(0.5, 1.4, len(dates)), index=dates), rate_name="tbill", method="ar1"
    )
    panel = combine_named_factors([ffr, tbill])
    market = pd.Series(np.arange(len(dates), dtype=float), index=dates, name="mkt")
    rf = pd.Series(np.arange(len(dates), dtype=float) / 10.0, index=dates, name="rf")

    aligned = align_market_rate_and_rf(
        market_excess_return=market,
        risk_free_return=rf,
        rate_factors=panel,
    )

    assert aligned.index.equals(panel.index)
    assert aligned["market_excess_return"].iloc[0] == market.loc[panel.index[0]]
    assert aligned["risk_free_return"].iloc[0] == rf.loc[panel.index[0]]


def test_combine_and_align_reject_invalid_inputs() -> None:
    dates = pd.date_range("2020-01-31", periods=3, freq="ME")
    rate_factors = pd.DataFrame({"ffr": [0.1, 0.2]}, index=dates[:2])

    with pytest.raises(ValueError, match="At least one factor"):
        combine_named_factors([])
    with pytest.raises(TypeError, match="DatetimeIndex"):
        align_market_rate_and_rf(
            market_excess_return=pd.Series([1.0], index=[1]),
            risk_free_return=pd.Series([0.1], index=dates[:1]),
            rate_factors=rate_factors,
        )
    with pytest.raises(ValueError, match="No common"):
        align_market_rate_and_rf(
            market_excess_return=pd.Series([1.0], index=dates[:1]),
            risk_free_return=pd.Series([0.1], index=dates[1:2]),
            rate_factors=rate_factors,
        )
    duplicate_index = pd.DatetimeIndex([dates[0], dates[0]])
    with pytest.raises(ValueError, match="duplicate timestamps"):
        align_market_rate_and_rf(
            market_excess_return=pd.Series([1.0, 2.0], index=duplicate_index),
            risk_free_return=pd.Series([0.1, 0.2], index=duplicate_index),
            rate_factors=pd.DataFrame({"ffr": [0.0, 0.1]}, index=duplicate_index),
        )


def test_factor_descriptives_correlations_and_article_target_comparison() -> None:
    dates = pd.date_range("2020-01-31", periods=5, freq="ME")
    factors = pd.DataFrame(
        {
            "ffr_ar1_innovation": [1.0, 2.0, 3.0, 4.0, 5.0],
            "tbill_ar1_innovation": [2.0, 1.0, 2.0, 1.0, 2.0],
        },
        index=dates,
    )

    descriptives = factor_descriptive_statistics(factors)
    correlations = factor_correlations(factors)
    comparison = compare_article_targets(
        descriptives,
        {("ffr_ar1_innovation", "mean"): 3.01},
        tolerance=0.02,
    )

    assert descriptives.loc["ffr_ar1_innovation", "mean"] == pytest.approx(3.0)
    assert correlations.loc["ffr_ar1_innovation", "ffr_ar1_innovation"] == pytest.approx(1.0)
    assert bool(comparison.loc[0, "within_tolerance"]) is True


def test_descriptives_and_correlations_reject_invalid_panels() -> None:
    with pytest.raises(ValueError, match="empty factor panel"):
        factor_descriptive_statistics(pd.DataFrame())
    with pytest.raises(ValueError, match="At least two factors"):
        factor_correlations(pd.DataFrame({"one_factor": [1.0, 2.0]}))


def test_innovation_diagnostics_and_recursive_coefficients() -> None:
    rng = np.random.default_rng(99)
    dates = pd.date_range("1990-01-31", periods=80, freq="ME")
    rate = pd.Series(rng.normal(size=len(dates)).cumsum(), index=dates)
    factor = build_named_ar_factor(rate, rate_name="ffr", method="ar1")

    diagnostics = innovation_diagnostics(
        factor.result.innovations,
        parameter_count=len(factor.result.parameters),
        ljung_box_lags=(4, 8),
    )
    recursive = recursive_ar_coefficients(rate, min_observations=24)

    ljung_box = diagnostics["ljung_box"]
    assert isinstance(ljung_box, dict)
    assert "4" in ljung_box
    assert "arch_lm" in diagnostics
    assert "cusum" in diagnostics
    assert not recursive.empty
    assert "lag_1" in recursive.columns


def test_diagnostics_and_recursive_coefficients_reject_short_inputs() -> None:
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    innovations = pd.Series(np.arange(6, dtype=float), index=dates)

    with pytest.raises(ValueError, match="Not enough observations"):
        innovation_diagnostics(innovations, parameter_count=2, ljung_box_lags=(12,))
    with pytest.raises(ValueError, match="min_observations"):
        recursive_ar_coefficients(innovations, min_observations=2)
    with pytest.raises(ValueError, match="Not enough observations"):
        recursive_ar_coefficients(innovations, min_observations=7)


def test_write_factor_outputs_writes_declared_formats(tmp_path: Path) -> None:
    dates = pd.date_range("2020-01-31", periods=6, freq="ME")
    factor_panel = pd.DataFrame(
        {
            "ffr_ar1_innovation": np.arange(6, dtype=float),
            "tbill_ar1_innovation": np.arange(6, dtype=float) + 1.0,
        },
        index=dates,
    )
    parameters = pd.DataFrame({"ffr": {"const": 0.0, "lag_1": 0.9}})

    paths = write_factor_outputs(
        output_root=tmp_path,
        namespace="baseline_ar1",
        factor_panel=factor_panel,
        parameters=parameters,
        diagnostics={"ffr": {"nobs": 6}},
    )

    assert Path(paths.panel_parquet).is_file()
    assert Path(paths.parameters_json).is_file()
    assert Path(paths.diagnostics_json).is_file()
    assert Path(paths.descriptives_csv).is_file()
    assert Path(paths.descriptives_tex).is_file()
    assert Path(paths.correlations_csv).is_file()
