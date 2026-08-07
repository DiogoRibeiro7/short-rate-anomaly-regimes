"""Build the vintage-consistent full-history panel and attach regime labels.

Regime analysis cannot run on the locked baseline panel joined to the extension
panel, because two registered regimes straddle the 2013-12 boundary between the
publication-era and current factor vintages. A regime that changed vintage
mid-way would confound a policy effect with a data revision.

The panel is therefore built on the **current vintage throughout**, by
concatenating the revised-history panel with the extension panel. Milestone 9
established that the vintage effect over the baseline window is negligible
against the effects being measured here: it moves the rate risk price by 0.0011
and cross-sectional RMSE by 1.1 percent. See
``reports/temporal_extension_report.md`` section 3.

Labels follow the frozen registry. The primary transition rule assigns a regime
to the first calendar month lying entirely under the new policy stance; the
whole-transition-month rule is attached as a declared sensitivity.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.config import (
    classify_regime_eligibility,
    load_baseline_config,
    load_regime_config,
)
from short_rate_anomaly_regimes.models.block_bootstrap import recover_lagged_level

REVISED_PARQUET = Path("data/processed/extension/revised_history_panel.parquet")
EXTENSION_PARQUET = Path("data/processed/extension/monthly_panel.parquet")
BASELINE_PARQUET = Path("data/processed/baseline_panel.parquet")

REGIME_PARQUET = Path("data/processed/regimes/monthly_regimes.parquet")
ELIGIBILITY_CSV = Path("artifacts/tables/regimes/regime_eligibility.csv")
#: The rate columns and labels alone, small enough to publish alongside the
#: results. The full panel carries seventy portfolio columns and stays out of
#: version control, but a figure that plots only the rate needs this much.
SERIES_CSV = Path("artifacts/tables/regimes/regime_monthly_series.csv")
PROVENANCE_JSON = Path("artifacts/provenance/regime_panel.json")

RATE = "fedfunds"
N_PRICED_FACTORS = 2
N_TEST_ASSETS = 70


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    index = pd.PeriodIndex([pd.Period(str(v), freq="M") for v in frame["month"]], freq="M")
    return frame.drop(columns=["month"]).set_axis(index)


def _label(index: pd.PeriodIndex, intervals: list[tuple[str, str, str]]) -> pd.Series:
    """Assign one regime label per month from explicit closed month intervals."""
    labels = pd.Series(index=index, dtype="object")
    for regime_id, start, end in intervals:
        window = pd.period_range(start, end, freq="M")
        covered = index.intersection(window)
        labels.loc[covered] = regime_id
    return labels


def main() -> None:
    """Concatenate the vintage-consistent history, label regimes, and gate eligibility."""
    revised = _load(REVISED_PARQUET)
    extension = _load(EXTENSION_PARQUET)
    if list(revised.columns) != list(extension.columns):
        raise ValueError("The revised-history and extension panels disagree on columns")
    panel = pd.concat([revised, extension]).sort_index()
    panel.index.name = "month"
    expected = pd.period_range(panel.index[0], panel.index[-1], freq="M")
    if list(panel.index) != list(expected):
        raise ValueError("The concatenated regime panel has month gaps")
    if panel.index.has_duplicates:
        raise ValueError("The concatenated regime panel has duplicate months")

    # The short-rate innovation is re-estimated once over the whole history, so
    # the factor is one series rather than two spliced ones.
    level = panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    baseline = _load(BASELINE_PARQUET)
    first_lag = float(
        recover_lagged_level(
            baseline[f"short_rate_level__{RATE}"].to_numpy(dtype=float),
            baseline[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float),
        )[0]
    )
    lagged = np.concatenate([[first_lag], level[:-1]])
    design = np.column_stack([np.ones(level.size), lagged])
    coefficients = np.linalg.lstsq(design, level, rcond=None)[0]
    panel[f"short_rate_innovation__{RATE}"] = level - design @ coefficients

    regime_config = load_regime_config(Path("configs/regimes.yaml"))
    baseline_config = load_baseline_config(Path("configs/baseline.yaml"))
    last_month = str(panel.index[-1])

    primary: list[tuple[str, str, str]] = []
    sensitivity: list[tuple[str, str, str]] = []
    for interval in regime_config.regime_definition.regimes:
        end = last_month if interval.end == "latest_available" else interval.end
        primary.append((interval.id, interval.start, end))
        if interval.sensitivity_start and interval.sensitivity_end:
            sensitivity_end = (
                last_month
                if interval.sensitivity_end == "latest_available"
                else interval.sensitivity_end
            )
            sensitivity.append((interval.id, interval.sensitivity_start, sensitivity_end))

    month_index = pd.PeriodIndex(panel.index, freq="M")
    panel["regime_primary"] = _label(month_index, primary)
    panel["regime_sensitivity"] = _label(month_index, sensitivity)
    unlabelled = panel["regime_primary"].isna().sum()
    if unlabelled:
        raise ValueError(f"{unlabelled} months carry no primary regime label")

    eligibility = regime_config.regime_estimation_eligibility
    rows = []
    for regime_id, start, end in primary:
        months = int((panel["regime_primary"] == regime_id).sum())
        tier = classify_regime_eligibility(
            months=months,
            test_assets=N_TEST_ASSETS,
            beta_rank=N_PRICED_FACTORS,
            n_priced_factors=N_PRICED_FACTORS,
            eligibility_config=eligibility,
        )
        rows.append(
            {
                "regime_id": regime_id,
                "start_month": start,
                "end_month": end,
                "months": months,
                "test_assets": N_TEST_ASSETS,
                "eligibility_tier": tier,
                "standalone_second_pass_permitted": tier.startswith(
                    "eligible_first_pass_and_standalone"
                ),
                "regime_specific_first_pass_permitted": tier.startswith("eligible"),
            }
        )
    frame = pd.DataFrame.from_records(rows)

    REGIME_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    ELIGIBILITY_CSV.parent.mkdir(parents=True, exist_ok=True)
    output = panel.reset_index()
    output["month"] = output["month"].astype(str)
    output.to_parquet(REGIME_PARQUET, index=False)
    frame.to_csv(ELIGIBILITY_CSV, index=False, lineterminator="\n")
    output[
        [
            "month",
            f"short_rate_level__{RATE}",
            f"short_rate_innovation__{RATE}",
            "regime_primary",
            "regime_sensitivity",
        ]
    ].to_csv(SERIES_CSV, index=False, lineterminator="\n")

    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/build_regime_panel.py",
                "replication_status": "documented_reconstruction",
                "vintage": "current_throughout",
                "vintage_rationale": (
                    "two registered regimes straddle the 2013-12 vintage boundary; the "
                    "Milestone 9 decomposition shows the vintage effect over the baseline "
                    "window is 1.1 percent of RMSE against temporal effects of 89 percent"
                ),
                "months": len(panel),
                "start": str(panel.index[0]),
                "end": last_month,
                "inputs": {
                    p.as_posix(): _sha256(p)
                    for p in (REVISED_PARQUET, EXTENSION_PARQUET, BASELINE_PARQUET)
                },
                "outputs": {
                    REGIME_PARQUET.as_posix(): _sha256(REGIME_PARQUET),
                    ELIGIBILITY_CSV.as_posix(): _sha256(ELIGIBILITY_CSV),
                    SERIES_CSV.as_posix(): _sha256(SERIES_CSV),
                },
                "short_rate_ar": {
                    "intercept": float(coefficients[0]),
                    "slope": float(coefficients[1]),
                    "note": "re-estimated once over the whole history, not spliced",
                },
                "transition_rule": regime_config.regime_definition.transition_rule.primary,
                "comparators": list(baseline_config.comparators),
                "eligibility_floors": {
                    "regime_specific": (eligibility.minimum_months_for_regime_specific_estimation),
                    "standalone_second_pass": (
                        eligibility.minimum_months_for_standalone_second_pass
                    ),
                    "test_assets": eligibility.minimum_test_assets_for_standalone_second_pass,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(f"regime panel: {len(panel)} months {panel.index[0]}..{panel.index[-1]}, current vintage")
    print(frame.to_string(index=False))
    permitted = frame.loc[frame["standalone_second_pass_permitted"], "regime_id"].tolist()
    print(f"\nstandalone second pass permitted for: {permitted or 'none'}")


if __name__ == "__main__":
    main()
