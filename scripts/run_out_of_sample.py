"""Run the registered out-of-sample falsification under the frozen design.

Evidence gate 4, and Milestone 12. The estimator, the refit schedule, the
benchmarks and the loss functions have been frozen in ``configs/extensions.yaml``
since before any of these forecasts existed, and the machinery to run them has
been in ``short_rate_anomaly_regimes.forecasting.out_of_sample`` for as long.
What was missing was a driver: nothing ever called it, so the evaluation
artifacts never existed and the generated report reported
``blocked_missing_input`` against inputs the repository was always able to
produce. That is a different situation from the shock decomposition, which is
blocked on event data this repository does not hold.

The panel is the vintage-consistent 648-month regime panel rather than the
baseline or extension panel, because the evaluation window crosses the 2013-12
vintage boundary. Using a spliced panel would let a data revision enter as an
apparent forecasting result.

The design is read from the frozen config and never inferred from the data,
with one exception recorded in the design artifact: ``evaluation_end`` is the
last month the panel carries, because the config fixes when evaluation starts
and not when the data run out.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from short_rate_anomaly_regimes.forecasting.out_of_sample import (
    OutOfSampleDesign,
    build_out_of_sample_evaluation,
    write_out_of_sample_outputs,
)

PANEL_PARQUET = Path("data/processed/regimes/monthly_regimes.parquet")
EXTENSIONS_CONFIG = Path("configs/extensions.yaml")

FORECAST_PARQUET = Path("artifacts/estimates/out_of_sample/forecasts.parquet")
TABLE_DIR = Path("artifacts/tables/out_of_sample")
REPORT_PATH = Path("reports/generated/out_of_sample_report.md")
PROVENANCE_JSON = Path("artifacts/provenance/out_of_sample.json")

#: The frozen design names its factors ``mkt`` and ``rate``. The panel names
#: them for their sources, so the mapping is written down here rather than left
#: to a column-order coincidence.
FACTOR_COLUMNS = {
    "mkt": "market_excess_return",
    "rate": "short_rate_innovation__fedfunds",
}

REPLICATION_STATUS = "documented_reconstruction"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the test-asset excess returns and the priced factors."""
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    ).to_timestamp(how="start")
    panel = panel.drop(columns=["month"]).set_axis(index)

    columns = sorted(c for c in panel.columns if c.startswith("portfolio_excess_return__"))
    excess_returns = panel[columns].rename(
        columns={c: c.removeprefix("portfolio_excess_return__") for c in columns}
    )
    factors = pd.DataFrame(
        {name: panel[source] for name, source in FACTOR_COLUMNS.items()},
        index=panel.index,
    )
    missing = excess_returns.isna().to_numpy().any() or factors.isna().to_numpy().any()
    if missing:
        raise ValueError("The out-of-sample panel must not carry missing observations")
    return excess_returns, factors


def load_design(evaluation_end: str) -> OutOfSampleDesign:
    """Build the frozen design from the configuration."""
    config = yaml.safe_load(EXTENSIONS_CONFIG.read_text(encoding="utf-8"))["out_of_sample"]
    return OutOfSampleDesign(
        initial_train_end=str(config["initial_train_end"]),
        evaluation_end=evaluation_end,
        refit_frequency_months=int(config["refit_frequency_months"]),
        factor_definition=str(config["factor_definition"]),
        confirmatory_model=str(config["confirmatory_model"]),
        benchmarks=tuple(str(name) for name in config["benchmarks"]),
    )


def main() -> None:
    """Run the frozen falsification and write its artifacts."""
    excess_returns, factors = load_panel()
    evaluation_end = str(pd.Period(excess_returns.index[-1], freq="M"))
    design = load_design(evaluation_end)

    build = build_out_of_sample_evaluation(
        excess_returns=excess_returns,
        factors=factors,
        design=design,
    )
    write_out_of_sample_outputs(
        build=build,
        forecast_path=FORECAST_PARQUET,
        table_dir=TABLE_DIR,
        report_path=REPORT_PATH,
        design=design,
    )

    ranked = build.metrics.sort_values("mean_squared_error")
    print(f"windows evaluated: {build.forecasts['window_id'].nunique()}")
    print(f"test assets:       {build.forecasts['asset'].nunique()}")
    print(f"evaluated through: {build.forecasts['test_end'].max()}")
    for row in ranked.itertuples():
        print(f"  {row.model:<28} mse={row.mean_squared_error:.6f}")

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_out_of_sample.py",
                "replication_status": REPLICATION_STATUS,
                "design_source": EXTENSIONS_CONFIG.as_posix(),
                "evaluation_end_rule": (
                    "the last month the panel carries. The frozen config fixes when "
                    "evaluation starts, not when the data run out"
                ),
                "panel_rationale": (
                    "the vintage-consistent 648-month regime panel, because the evaluation "
                    "window crosses the 2013-12 vintage boundary and a spliced panel would "
                    "let a data revision enter as an apparent forecasting result"
                ),
                "factor_columns": FACTOR_COLUMNS,
                "window": {
                    "start": str(pd.Period(excess_returns.index[0], freq="M")),
                    "end": evaluation_end,
                    "months": len(excess_returns),
                    "test_assets": int(excess_returns.shape[1]),
                },
                "inputs": {
                    PANEL_PARQUET.as_posix(): _sha256(PANEL_PARQUET),
                    EXTENSIONS_CONFIG.as_posix(): _sha256(EXTENSIONS_CONFIG),
                },
                "outputs": {
                    path.as_posix(): _sha256(path)
                    for path in (
                        TABLE_DIR / "forecast_metrics.csv",
                        TABLE_DIR / "model_confidence_set.csv",
                        TABLE_DIR / "design.json",
                    )
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {REPORT_PATH.as_posix()}")


if __name__ == "__main__":
    main()
