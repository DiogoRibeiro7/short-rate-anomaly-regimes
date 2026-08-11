from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.forecasting.out_of_sample import (
    ForecastWindow,
    OutOfSampleBuild,
    OutOfSampleDesign,
    build_out_of_sample_evaluation,
    forecast_metrics,
    generate_benchmark_forecasts,
    generate_model_forecasts,
    make_refit_schedule,
    model_confidence_set,
    top_minus_bottom_rank_accuracy,
    write_out_of_sample_outputs,
)


def _fixture_returns_factors() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.date_range("1999-01-31", periods=48, freq="ME")
    factors = pd.DataFrame(
        {
            "mkt": np.linspace(-0.03, 0.04, 48),
            "rate": np.sin(np.arange(48)) / 100.0,
        },
        index=dates,
    )
    returns = pd.DataFrame(
        {
            "asset_a": 0.01 + 0.8 * factors["mkt"] - 0.2 * factors["rate"],
            "asset_b": -0.01 + 0.5 * factors["mkt"] + 0.3 * factors["rate"],
            "asset_c": 0.02 - 0.2 * factors["mkt"] + 0.6 * factors["rate"],
        },
        index=dates,
    )
    return returns, factors


def test_make_refit_schedule_freezes_annual_and_rolling_windows() -> None:
    dates = pd.date_range("1999-01-31", periods=48, freq="ME")

    expanding = make_refit_schedule(
        dates,
        initial_train_end="1999-12",
        evaluation_end="2001-12",
        refit_frequency_months=12,
    )
    rolling = make_refit_schedule(
        dates,
        initial_train_end="1999-12",
        evaluation_end="2001-12",
        refit_frequency_months=12,
        rolling_window_months=12,
    )

    assert expanding[0].train_start == "1999-01"
    assert expanding[0].test_start == "2000-01"
    assert expanding[1].train_end == "2000-12"
    assert rolling[1].train_start == "2000-01"
    with pytest.raises(ValueError, match="positive"):
        make_refit_schedule(
            dates,
            initial_train_end="1999-12",
            evaluation_end="2000-12",
            refit_frequency_months=0,
        )
    with pytest.raises(ValueError, match="precede"):
        make_refit_schedule(
            dates,
            initial_train_end="2000-12",
            evaluation_end="2000-12",
            refit_frequency_months=12,
        )
    with pytest.raises(ValueError, match="dates"):
        make_refit_schedule(
            pd.DatetimeIndex([]),
            initial_train_end="1999-12",
            evaluation_end="2000-12",
            refit_frequency_months=12,
        )


def test_generate_model_forecasts_carry_vintage_and_do_not_look_ahead() -> None:
    returns, factors = _fixture_returns_factors()
    windows = make_refit_schedule(
        pd.DatetimeIndex(returns.index),
        initial_train_end="1999-12",
        evaluation_end="2001-12",
        refit_frequency_months=12,
    )

    forecasts = generate_model_forecasts(
        excess_returns=returns,
        factors=factors,
        windows=windows,
        model_name="two_factor_market_rate",
        factor_columns=("mkt", "rate"),
    )

    assert all(
        str(row.model_vintage).endswith(str(row.train_end))
        for row in forecasts.itertuples(index=False)
    )
    assert (
        pd.to_datetime(forecasts["train_end"]).max() < pd.to_datetime(forecasts["test_end"]).max()
    )
    assert {"asset", "forecast", "observed", "forecast_error"} <= set(forecasts.columns)
    with pytest.raises(ValueError, match="Missing factor"):
        generate_model_forecasts(
            excess_returns=returns,
            factors=factors,
            windows=windows,
            model_name="bad",
            factor_columns=("missing",),
        )


def test_benchmark_forecasts_and_validation_guards() -> None:
    returns, factors = _fixture_returns_factors()
    windows = (
        ForecastWindow(
            window_id=1,
            train_start="1999-01",
            train_end="1999-12",
            test_start="2000-01",
            test_end="2000-12",
        ),
    )
    benchmarks = generate_benchmark_forecasts(
        excess_returns=returns,
        windows=windows,
        benchmarks=("historical_mean", "zero_excess_return"),
    )

    assert set(benchmarks["model"]) == {"historical_mean", "zero_excess_return"}
    assert (benchmarks.loc[benchmarks["model"] == "zero_excess_return", "forecast"] == 0.0).all()
    with pytest.raises(ValueError, match="Unsupported benchmark"):
        generate_benchmark_forecasts(
            excess_returns=returns,
            windows=windows,
            benchmarks=("unsupported",),
        )
    with pytest.raises(TypeError, match="DatetimeIndex"):
        generate_model_forecasts(
            excess_returns=returns.reset_index(drop=True),
            factors=factors,
            windows=windows,
            model_name="bad_index",
            factor_columns=("mkt",),
        )


def test_forecast_metrics_rank_accuracy_and_confidence_set() -> None:
    forecasts = pd.DataFrame(
        {
            "window_id": [1, 1, 1, 1, 1, 1],
            "model": [
                "model",
                "model",
                "historical_mean",
                "historical_mean",
                "zero_excess_return",
                "zero_excess_return",
            ],
            "asset": ["a", "b", "a", "b", "a", "b"],
            "forecast": [0.02, 0.01, 0.01, 0.02, 0.0, 0.0],
            "observed": [0.03, 0.00, 0.03, 0.00, 0.03, 0.00],
        }
    )

    metrics = forecast_metrics(forecasts, benchmark_model="historical_mean")
    confidence = model_confidence_set(metrics, tolerance=0.25)

    assert set(metrics["model"]) == {"model", "historical_mean", "zero_excess_return"}
    assert top_minus_bottom_rank_accuracy(forecasts.loc[forecasts["model"] == "model"]) == 1.0
    assert "included_in_confidence_set" in confidence.columns
    with pytest.raises(ValueError, match="Benchmark"):
        forecast_metrics(forecasts, benchmark_model="missing")
    with pytest.raises(ValueError, match="mean_squared_error"):
        model_confidence_set(pd.DataFrame({"model": ["x"]}))
    with pytest.raises(ValueError, match="nonnegative"):
        model_confidence_set(metrics, tolerance=-0.1)


def test_build_out_of_sample_evaluation_and_output_writer(tmp_path: Path) -> None:
    returns, factors = _fixture_returns_factors()
    design = OutOfSampleDesign(
        initial_train_end="1999-12",
        evaluation_end="2001-12",
        refit_frequency_months=12,
        factor_definition="mkt,rate",
        confirmatory_model="two_factor_market_rate",
        benchmarks=("historical_mean", "zero_excess_return"),
    )

    build = build_out_of_sample_evaluation(
        excess_returns=returns,
        factors=factors,
        design=design,
    )

    assert isinstance(build, OutOfSampleBuild)
    assert not build.forecasts.empty
    write_out_of_sample_outputs(
        build=build,
        forecast_path=tmp_path / "forecasts.parquet",
        table_dir=tmp_path / "tables",
        report_path=tmp_path / "report.md",
        design=design,
    )

    assert (tmp_path / "forecasts.parquet").is_file()
    assert (tmp_path / "tables" / "forecast_metrics.csv").is_file()
    assert "Negative out-of-sample performance" in (tmp_path / "report.md").read_text(
        encoding="utf-8"
    )


def test_the_loss_band_does_not_claim_to_be_a_model_confidence_set() -> None:
    """The column name will be read as Hansen, Lunde and Nason; the object is not that.

    A model confidence set eliminates models by a bootstrapped
    equal-predictive-ability test and carries a coverage guarantee at a stated
    level. This is a deterministic band around the lowest observed loss, with no
    resampling and no test statistic, so the rule has to travel in the artifact
    rather than only in a docstring a reader of the CSV never sees.
    """
    metrics = pd.DataFrame(
        {
            "model": ["a", "b", "c"],
            "mean_squared_error": [1.0, 1.05, 2.0],
        }
    )

    table = model_confidence_set(metrics, tolerance=0.10)

    rule = set(table["selection_rule"])
    assert len(rule) == 1
    recorded = rule.pop()
    assert "not_hansen_lunde_nason" in recorded
    assert "no_coverage_guarantee" in recorded
    assert "10%" in recorded
    # The band itself: within ten percent of 1.0 keeps a and b, drops c.
    assert list(table["included_in_confidence_set"]) == [True, True, False]


def test_the_recorded_rule_follows_the_tolerance_it_was_given() -> None:
    """A stale rule string would misdescribe the very screen it labels."""
    metrics = pd.DataFrame({"model": ["a", "b"], "mean_squared_error": [1.0, 1.4]})

    assert "50%" in set(model_confidence_set(metrics, tolerance=0.5)["selection_rule"]).pop()
    assert list(model_confidence_set(metrics, tolerance=0.5)["included_in_confidence_set"]) == [
        True,
        True,
    ]
    assert list(model_confidence_set(metrics, tolerance=0.1)["included_in_confidence_set"]) == [
        True,
        False,
    ]


def test_the_committed_out_of_sample_report_states_what_the_band_is_not() -> None:
    """The shipped report must carry the caveat, not just the source."""
    report = Path("reports/generated/out_of_sample_report.md").read_text(encoding="utf-8")

    assert "Verdict: `generated_from_frozen_design`" in report
    assert "not** the Hansen, Lunde and Nason (2011) model" in report
    assert "no coverage guarantee at any level" in report
    # The benchmark the out-of-sample R2 is measured against reads zero by
    # construction, which a reader comparing columns would otherwise misread.
    assert "reads 0 by construction" in report
