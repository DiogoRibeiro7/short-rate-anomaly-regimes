"""Out-of-sample asset-pricing falsification utilities."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr  # type: ignore[import-untyped]

from short_rate_anomaly_regimes.models.cross_section import estimate_ols_two_pass
from short_rate_anomaly_regimes.models.time_series import (
    automatic_newey_west_lags,
    estimate_time_series_betas,
)


@dataclass(frozen=True, slots=True)
class ForecastWindow:
    """One precommitted refit and evaluation block."""

    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    window_type: str = "expanding"


@dataclass(frozen=True, slots=True)
class OutOfSampleDesign:
    """Frozen out-of-sample design metadata."""

    initial_train_end: str
    evaluation_end: str
    refit_frequency_months: int
    factor_definition: str
    confirmatory_model: str
    benchmarks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OutOfSampleBuild:
    """Forecast, metric, and model-confidence-set outputs."""

    forecasts: pd.DataFrame
    metrics: pd.DataFrame
    confidence_set: pd.DataFrame


def make_refit_schedule(
    dates: pd.DatetimeIndex,
    *,
    initial_train_end: str,
    evaluation_end: str,
    refit_frequency_months: int,
    rolling_window_months: int | None = None,
) -> tuple[ForecastWindow, ...]:
    """Create precommitted annual or rolling forecast windows."""
    if refit_frequency_months <= 0:
        raise ValueError("refit_frequency_months must be positive")
    if rolling_window_months is not None and rolling_window_months <= 0:
        raise ValueError("rolling_window_months must be positive")
    if dates.empty:
        raise ValueError("dates cannot be empty")
    available = pd.DatetimeIndex(dates).sort_values()
    first_available = available.min()
    train_end = _month_end(initial_train_end)
    final_end = _month_end(evaluation_end)
    if train_end >= final_end:
        raise ValueError("initial_train_end must precede evaluation_end")
    rows: list[ForecastWindow] = []
    window_id = 1
    while train_end < final_end:
        train_start = (
            train_end - pd.offsets.MonthEnd(rolling_window_months - 1)
            if rolling_window_months is not None
            else first_available
        )
        test_start = train_end + pd.offsets.MonthEnd(1)
        test_end = min(train_end + pd.offsets.MonthEnd(refit_frequency_months), final_end)
        rows.append(
            ForecastWindow(
                window_id=window_id,
                train_start=pd.Timestamp(train_start).strftime("%Y-%m"),
                train_end=pd.Timestamp(train_end).strftime("%Y-%m"),
                test_start=pd.Timestamp(test_start).strftime("%Y-%m"),
                test_end=pd.Timestamp(test_end).strftime("%Y-%m"),
                window_type="rolling" if rolling_window_months is not None else "expanding",
            )
        )
        train_end = test_end
        window_id += 1
    return tuple(rows)


def generate_model_forecasts(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    windows: tuple[ForecastWindow, ...],
    model_name: str,
    factor_columns: tuple[str, ...],
    hac_lags: int | None = None,
) -> pd.DataFrame:
    """Estimate betas and risk prices from history only, then forecast next blocks."""
    _require_datetime_index(excess_returns, "excess_returns")
    _require_datetime_index(factors, "factors")
    if not windows:
        raise ValueError("windows cannot be empty")
    missing_factors = set(factor_columns) - set(factors.columns)
    if missing_factors:
        raise ValueError(f"Missing factor columns: {', '.join(sorted(missing_factors))}")
    rows: list[dict[str, float | str | int]] = []
    for window in windows:
        train_returns, train_factors, test_returns = _window_panels(
            excess_returns=excess_returns,
            factors=factors.loc[:, list(factor_columns)],
            window=window,
        )
        lags = (
            hac_lags if hac_lags is not None else automatic_newey_west_lags(train_returns.shape[0])
        )
        betas = estimate_time_series_betas(train_returns, train_factors, hac_lags=lags)
        beta_matrix = betas.coefficients.drop(columns=["const"], errors="ignore")
        cross_section = estimate_ols_two_pass(
            train_returns.mean(axis=0),
            beta_matrix,
            include_intercept=True,
            beta_source="training_window_first_pass",
            estimation_window=f"{window.train_start}_{window.train_end}",
        )
        factor_prices = cross_section.risk_prices.drop(labels=["const"], errors="ignore")
        intercept = float(cross_section.risk_prices.get("const", 0.0))
        common_assets = [asset for asset in test_returns.columns if asset in beta_matrix.index]
        forecasts = pd.Series(
            intercept
            + beta_matrix.loc[common_assets, list(factor_prices.index)].to_numpy(dtype=float)
            @ factor_prices.to_numpy(dtype=float),
            index=common_assets,
        )
        observed = test_returns.loc[:, common_assets].mean(axis=0)
        for asset in common_assets:
            rows.append(
                _forecast_row(
                    window=window,
                    model=model_name,
                    factor_definition=",".join(factor_columns),
                    asset=str(asset),
                    forecast=float(forecasts.loc[asset]),
                    observed=float(observed.loc[asset]),
                    benchmark="confirmatory_model",
                )
            )
    return pd.DataFrame(rows)


def generate_benchmark_forecasts(
    *,
    excess_returns: pd.DataFrame,
    windows: tuple[ForecastWindow, ...],
    benchmarks: tuple[str, ...] = ("historical_mean", "zero_excess_return"),
) -> pd.DataFrame:
    """Generate declared benchmark forecasts using training history only."""
    _require_datetime_index(excess_returns, "excess_returns")
    rows: list[dict[str, float | str | int]] = []
    for window in windows:
        train_start = _month_end(window.train_start)
        train_end = _month_end(window.train_end)
        test_start = _month_end(window.test_start)
        test_end = _month_end(window.test_end)
        train = excess_returns.loc[train_start:train_end].dropna(how="all")
        test = excess_returns.loc[test_start:test_end].dropna(how="all")
        if train.empty or test.empty:
            raise ValueError("Benchmark window has no train or test observations")
        for benchmark in benchmarks:
            for asset in test.columns:
                if asset not in train.columns:
                    continue
                forecast = _benchmark_value(train[asset], benchmark)
                rows.append(
                    _forecast_row(
                        window=window,
                        model=benchmark,
                        factor_definition="benchmark",
                        asset=str(asset),
                        forecast=forecast,
                        observed=float(test[asset].mean()),
                        benchmark=benchmark,
                    )
                )
    return pd.DataFrame(rows)


def forecast_metrics(
    forecasts: pd.DataFrame,
    *,
    benchmark_model: str = "historical_mean",
) -> pd.DataFrame:
    """Compute cross-sectional OOS metrics for each model over all forecast records."""
    required = {"model", "asset", "forecast", "observed", "window_id"}
    missing = required - set(forecasts.columns)
    if missing:
        raise ValueError(f"Forecast table is missing columns: {', '.join(sorted(missing))}")
    rows: list[dict[str, float | str]] = []
    benchmark = forecasts.loc[forecasts["model"] == benchmark_model]
    if benchmark.empty:
        raise ValueError(f"Benchmark model {benchmark_model!r} is missing")
    benchmark_errors = _aligned_errors(benchmark)
    benchmark_sse = float(np.square(benchmark_errors.to_numpy(dtype=float)).sum())
    for model, frame in forecasts.groupby("model", sort=True):
        errors = _aligned_errors(frame)
        observed = _aligned_observed(frame)
        row: dict[str, float | str] = {
            "model": str(model),
            "rmse": float(np.sqrt(np.mean(np.square(errors.to_numpy(dtype=float))))),
            "mae": float(np.mean(np.abs(errors.to_numpy(dtype=float)))),
            "max_error": float(np.max(np.abs(errors.to_numpy(dtype=float)))),
            "mean_squared_error": float(np.mean(np.square(errors.to_numpy(dtype=float)))),
            "out_of_sample_r2": np.nan
            if benchmark_sse == 0.0
            else 1.0 - float(np.square(errors.to_numpy(dtype=float)).sum()) / benchmark_sse,
            "rank_correlation": _rank_correlation(frame),
            "top_minus_bottom_rank_accuracy": top_minus_bottom_rank_accuracy(frame),
            "forecast_count": float(frame.shape[0]),
            "asset_count": float(frame["asset"].nunique()),
            "observed_mean": float(observed.mean()),
        }
        rows.append(row)
    return pd.DataFrame(rows)


def top_minus_bottom_rank_accuracy(frame: pd.DataFrame) -> float:
    """Return share of windows where forecast and realized top-minus-bottom signs match."""
    outcomes: list[float] = []
    for _window_id, window in frame.groupby("window_id", sort=True):
        if window.shape[0] < 2:
            continue
        forecast_order = window.sort_values("forecast")
        observed_order = window.sort_values("observed")
        forecast_spread = float(
            forecast_order.iloc[-1]["forecast"] - forecast_order.iloc[0]["forecast"]
        )
        observed_spread = float(
            observed_order.iloc[-1]["observed"] - observed_order.iloc[0]["observed"]
        )
        outcomes.append(float(np.sign(forecast_spread) == np.sign(observed_spread)))
    return float(np.mean(outcomes)) if outcomes else float("nan")


def model_confidence_set(
    metrics: pd.DataFrame,
    *,
    tolerance: float = 0.10,
) -> pd.DataFrame:
    """Create a transparent loss-based model confidence set."""
    if "mean_squared_error" not in metrics.columns:
        raise ValueError("Metrics table is missing mean_squared_error")
    if tolerance < 0:
        raise ValueError("tolerance must be nonnegative")
    best_loss = float(metrics["mean_squared_error"].min())
    table = metrics.copy()
    threshold = best_loss * (1.0 + tolerance)
    table["loss_gap_to_best"] = table["mean_squared_error"].astype(float) - best_loss
    table["included_in_confidence_set"] = table["mean_squared_error"].astype(float) <= threshold
    return table


def build_out_of_sample_evaluation(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    design: OutOfSampleDesign,
) -> OutOfSampleBuild:
    """Build confirmatory model and benchmark forecasts under the frozen design."""
    windows = make_refit_schedule(
        pd.DatetimeIndex(excess_returns.index),
        initial_train_end=design.initial_train_end,
        evaluation_end=design.evaluation_end,
        refit_frequency_months=design.refit_frequency_months,
    )
    factor_columns = tuple(
        part.strip() for part in design.factor_definition.split(",") if part.strip()
    )
    model = generate_model_forecasts(
        excess_returns=excess_returns,
        factors=factors,
        windows=windows,
        model_name=design.confirmatory_model,
        factor_columns=factor_columns,
    )
    benchmarks = generate_benchmark_forecasts(
        excess_returns=excess_returns,
        windows=windows,
        benchmarks=design.benchmarks,
    )
    forecasts = pd.concat([model, benchmarks], ignore_index=True)
    metrics = forecast_metrics(forecasts, benchmark_model=design.benchmarks[0])
    confidence = model_confidence_set(metrics)
    return OutOfSampleBuild(forecasts=forecasts, metrics=metrics, confidence_set=confidence)


def write_out_of_sample_outputs(
    *,
    build: OutOfSampleBuild,
    forecast_path: Path,
    table_dir: Path,
    report_path: Path,
    design: OutOfSampleDesign,
) -> None:
    """Write forecasts, metrics, model confidence set, and report metadata."""
    forecast_path.parent.mkdir(parents=True, exist_ok=True)
    table_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    build.forecasts.to_parquet(forecast_path, index=False)
    build.metrics.to_csv(table_dir / "forecast_metrics.csv", index=False, lineterminator="\n")
    build.confidence_set.to_csv(
        table_dir / "model_confidence_set.csv", index=False, lineterminator="\n"
    )
    (table_dir / "design.json").write_text(
        json.dumps(asdict(design), indent=2, sort_keys=True),
        encoding="utf-8",
        newline="\n",
    )
    best = build.metrics.sort_values("mean_squared_error").iloc[0]
    report_path.write_text(
        "\n".join(
            [
                "# Out-of-Sample Falsification Report",
                "",
                "Verdict: `generated_from_frozen_design`",
                "",
                f"Initial training endpoint: `{design.initial_train_end}`",
                f"Refit frequency months: `{design.refit_frequency_months}`",
                f"Lowest-loss model: `{best['model']}`",
                "",
                "Negative out-of-sample performance must be preserved and investigated "
                "without changing the confirmatory specification.",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def write_blocked_oos_report(*, output_path: Path, missing_inputs: tuple[Path, ...]) -> None:
    """Write a blocked report when OOS empirical inputs are absent."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(
            [
                "# Out-of-Sample Falsification Report",
                "",
                "Verdict: `blocked_missing_input`",
                "",
                "The registered out-of-sample falsification has not been executed, so no "
                "forecast, metric, or model-confidence-set artifacts exist to report. The "
                "refit schedule is frozen before evaluation and must not be tuned after "
                "test errors are seen.",
                "",
                "Missing inputs:",
                *[f"- `{path.as_posix()}`" for path in missing_inputs],
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def _window_panels(
    *,
    excess_returns: pd.DataFrame,
    factors: pd.DataFrame,
    window: ForecastWindow,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train_start = _month_end(window.train_start)
    train_end = _month_end(window.train_end)
    test_start = _month_end(window.test_start)
    test_end = _month_end(window.test_end)
    if train_end >= test_start:
        raise ValueError("Training window must end before test window starts")
    train_returns = excess_returns.loc[train_start:train_end].dropna(how="all")
    train_factors = factors.loc[train_start:train_end].dropna(how="all")
    test_returns = excess_returns.loc[test_start:test_end].dropna(how="all")
    if train_returns.empty or train_factors.empty or test_returns.empty:
        raise ValueError("Forecast window has no train or test observations")
    return train_returns, train_factors, test_returns


def _forecast_row(
    *,
    window: ForecastWindow,
    model: str,
    factor_definition: str,
    asset: str,
    forecast: float,
    observed: float,
    benchmark: str,
) -> dict[str, float | str | int]:
    return {
        "window_id": window.window_id,
        "model_vintage": f"{model}_{window.train_end}",
        "model": model,
        "factor_definition": factor_definition,
        "asset_universe": "common_assets_in_window",
        "asset": asset,
        "train_start": window.train_start,
        "train_end": window.train_end,
        "test_start": window.test_start,
        "test_end": window.test_end,
        "window_type": window.window_type,
        "forecast": forecast,
        "observed": observed,
        "forecast_error": observed - forecast,
        "benchmark": benchmark,
    }


def _benchmark_value(train_asset_returns: pd.Series, benchmark: str) -> float:
    if benchmark == "historical_mean":
        return float(train_asset_returns.dropna().mean())
    if benchmark == "zero_excess_return":
        return 0.0
    raise ValueError(f"Unsupported benchmark: {benchmark}")


def _aligned_errors(frame: pd.DataFrame) -> pd.Series:
    return (frame["observed"].astype(float) - frame["forecast"].astype(float)).rename("error")


def _aligned_observed(frame: pd.DataFrame) -> pd.Series:
    return frame["observed"].astype(float).rename("observed")


def _rank_correlation(frame: pd.DataFrame) -> float:
    values: list[float] = []
    for _window_id, window in frame.groupby("window_id", sort=True):
        if window.shape[0] < 2:
            continue
        if window["forecast"].nunique() < 2 or window["observed"].nunique() < 2:
            continue
        statistic, _p_value = spearmanr(window["forecast"], window["observed"])
        values.append(float(statistic))
    clean = [value for value in values if not np.isnan(value)]
    return float(np.mean(clean)) if clean else float("nan")


def _require_datetime_index(frame: pd.DataFrame, name: str) -> None:
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError(f"{name} must use a DatetimeIndex")
    if frame.index.has_duplicates:
        raise ValueError(f"{name} contains duplicate dates")


def _month_end(month: str) -> pd.Timestamp:
    return pd.Timestamp(month) + pd.offsets.MonthEnd(0)
