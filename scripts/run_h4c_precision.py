"""Run the H4c fitted-premium precision gate on the frozen baseline panel.

H4c fails when the 95 percent joint-bootstrap interval for the rate-attributable
fitted-premium spread contains both plus and minus 0.25 monthly percentage
points, that is when the interval spans both economically positive and
economically negative effects under the threshold contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.models.block_bootstrap import (
    bootstrap_fitted_premium_spreads,
    recover_lagged_level,
    select_block_length,
)
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
DIAGNOSTIC_JSON = Path("artifacts/diagnostics/weak_factor/h4c_fitted_premium_precision.json")
INTERVAL_CSV = Path("artifacts/tables/robustness/h4c_fitted_premium_intervals.csv")
PROVENANCE_JSON = Path("artifacts/provenance/h4c_precision.json")

#: research/economic_thresholds.md: the economic direction bound on a
#: rate-attributable fitted premium, in monthly percentage points.
ECONOMIC_DIRECTION_BOUND = 0.25

#: research/bootstrap_contract.md: confirmatory repetitions and the project seed
#: from configs/baseline.yaml.
DRAWS = 10_000
SEED = 20260727

RATE = "fedfunds"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Bootstrap the fitted-premium spread per family and classify H4c."""
    panel = pd.read_parquet(PANEL_PARQUET)
    months = pd.PeriodIndex([pd.Period(str(v), freq="M") for v in panel["month"]], freq="M")
    panel = panel.drop(columns=["month"]).set_axis(months)

    level = panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    # The pre-window lag is the frozen timing convention, so the lagged level for
    # the first window month comes from the month before the window. It is not in
    # the panel, so it is reconstructed from the AR relation the panel already
    # embeds: level and innovation together identify the fitted value.
    innovation = panel[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float)
    lagged = recover_lagged_level(level, innovation)

    market = panel["market_excess_return"].to_numpy(dtype=float)

    # The second pass runs on the full 70-portfolio system; the spread pairs only
    # select which columns the reported estimand differences.
    all_columns = sorted(c for c in panel.columns if c.startswith("portfolio_excess_return__"))
    positions = {column: index for index, column in enumerate(all_columns)}
    spread_pairs = {
        family: (
            positions[f"portfolio_excess_return__{family}__decile_01"],
            positions[f"portfolio_excess_return__{family}__decile_10"],
        )
        for family in FAMILY_MEMBERS
    }
    returns = panel[all_columns].to_numpy(dtype=float)

    selection = select_block_length(
        pd.DataFrame(
            {
                "market_excess_return": market,
                f"short_rate_innovation__{RATE}": innovation,
            }
        )
    )
    print(f"block length {selection.block_length} via {selection.selected_by}")
    if selection.failure_reasons:
        print(f"  fallback reasons: {'; '.join(selection.failure_reasons)}")
    print(f"raw Politis-White lengths: {[round(v, 3) for v in selection.raw_optimal_lengths]}")

    result = bootstrap_fitted_premium_spreads(
        rate_level=level,
        lagged_rate_level=lagged,
        market=market,
        excess_returns=returns,
        spread_pairs=spread_pairs,
        block_length=selection.block_length,
        draws=DRAWS,
        seed=SEED,
        selected_by=selection.selected_by,
    )

    rows = []
    for family in result.point_estimates.index:
        low95 = float(result.lower_95[family])
        high95 = float(result.upper_95[family])
        spans_both = low95 < -ECONOMIC_DIRECTION_BOUND and high95 > ECONOMIC_DIRECTION_BOUND
        rows.append(
            {
                "family": family,
                "estimand": result.estimand,
                "point_estimate": float(result.point_estimates[family]),
                "lower_95": low95,
                "upper_95": high95,
                "lower_90": float(result.lower_90[family]),
                "upper_90": float(result.upper_90[family]),
                "economic_direction_bound": ECONOMIC_DIRECTION_BOUND,
                "interval_spans_both_directions": spans_both,
                "h4c_gate": "fail" if spans_both else "pass",
                "replication_status": "documented_reconstruction",
            }
        )
    frame = pd.DataFrame.from_records(rows)
    INTERVAL_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(INTERVAL_CSV, index=False, lineterminator="\n")

    failures = frame.loc[frame["h4c_gate"] == "fail", "family"].tolist()
    classification = (
        "h4c_failed_interval_spans_both_economic_directions"
        if failures
        else "h4c_passed_interval_excludes_at_least_one_economic_direction"
    )

    DIAGNOSTIC_JSON.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_JSON.write_text(
        json.dumps(
            {
                "hypothesis": "H4c",
                "classification": classification,
                "failing_families": failures,
                "estimand": result.estimand,
                "economic_direction_bound": ECONOMIC_DIRECTION_BOUND,
                "draws": result.draws,
                "successful_draws": result.successful_draws,
                "block_length": result.block_length,
                "block_length_selected_by": result.block_length_selected_by,
                "block_length_failure_reasons": list(selection.failure_reasons),
                "raw_politis_white_lengths": list(selection.raw_optimal_lengths),
                "seed": result.seed,
                "resampled_variables": list(result.resampled_variables),
                "regime_labels_resampled": False,
                "diagnostics": result.diagnostics,
                "replication_status": "documented_reconstruction",
                "per_family": rows,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_h4c_precision.py",
                "inputs": {PANEL_PARQUET.as_posix(): _sha256(PANEL_PARQUET)},
                "outputs": {
                    DIAGNOSTIC_JSON.as_posix(): _sha256(DIAGNOSTIC_JSON),
                    INTERVAL_CSV.as_posix(): _sha256(INTERVAL_CSV),
                },
                "rate_series": RATE,
                "draws": DRAWS,
                "seed": SEED,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print()
    print(
        frame[["family", "point_estimate", "lower_95", "upper_95", "h4c_gate"]]
        .round(4)
        .to_string(index=False)
    )
    print(f"\nH4c: {classification}")


if __name__ == "__main__":
    main()
