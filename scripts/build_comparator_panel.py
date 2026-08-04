"""Assemble the frozen comparator-factor panel for the baseline window.

The panel carries the article's factor names, each drawn from the vintage the
vintage-assignment decision in reports/french_vintage_difference_report.md fixes
for the baseline window. Provenance is written per column so that a later
comparator result can be traced to the file it came from.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.comparator_freeze import load_normalized_comparator
from short_rate_anomaly_regimes.data.french_freeze import load_normalized_french
from short_rate_anomaly_regimes.exceptions import DataValidationError

WINDOW_START = "1972-01"
WINDOW_END = "2013-12"

FRENCH_ROOT = Path("data/interim/kenneth_french")
COMPARATOR_ROOT = Path("data/interim/comparators")

FRENCH_VINTAGE = "publication_era_20170709"
LIQUIDITY_VINTAGE = "publication_era_20170828"
Q_VINTAGE = "global_q_2025_retrieved_20260802"

PANEL_PARQUET = Path("data/processed/comparator_factors.parquet")
COLUMN_METADATA_CSV = Path("artifacts/provenance/comparator_panel_column_metadata.csv")
PROVENANCE_JSON = Path("artifacts/provenance/comparator_panel.json")

#: The traded Pastor-Stambaugh factor is published in decimal units while every
#: other factor here is percent per month. See reports/baseline_input_readiness.md
#: section 3.1 for how the column and scale were identified.
LIQUIDITY_SCALE = 100.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Build the comparator panel and record its per-column provenance."""
    window = pd.period_range(WINDOW_START, WINDOW_END, freq="M")

    three_factor = load_normalized_french(
        FRENCH_ROOT / f"F-F_Research_Data_Factors_{FRENCH_VINTAGE}.csv"
    )
    momentum = load_normalized_french(FRENCH_ROOT / f"F-F_Momentum_Factor_{FRENCH_VINTAGE}.csv")
    five_factor = load_normalized_french(
        FRENCH_ROOT / f"F-F_Research_Data_5_Factors_2x3_{FRENCH_VINTAGE}.csv"
    )
    liquidity = load_normalized_comparator(
        COMPARATOR_ROOT / f"pastor_stambaugh_liquidity_{LIQUIDITY_VINTAGE}.csv"
    )
    q_factors = load_normalized_comparator(COMPARATOR_ROOT / f"q_factors_{Q_VINTAGE}.csv")

    # RM, SMB and HML come from the three-factor archive. The five-factor archive
    # publishes its own SMB by a different construction and, in the current
    # vintage, a market series that is not identical; only RMW and CMA are taken
    # from it. See artifacts/data_quality/french_shared_factor_consistency.csv.
    columns: dict[str, tuple[pd.Series, str, str, str]] = {
        "RM": (three_factor["Mkt-RF"], "F-F_Research_Data_Factors", FRENCH_VINTAGE, "Mkt-RF"),
        "SMB": (three_factor["SMB"], "F-F_Research_Data_Factors", FRENCH_VINTAGE, "SMB"),
        "HML": (three_factor["HML"], "F-F_Research_Data_Factors", FRENCH_VINTAGE, "HML"),
        "UMD": (momentum["Mom"], "F-F_Momentum_Factor", FRENCH_VINTAGE, "Mom"),
        "RMW": (five_factor["RMW"], "F-F_Research_Data_5_Factors_2x3", FRENCH_VINTAGE, "RMW"),
        "CMA": (five_factor["CMA"], "F-F_Research_Data_5_Factors_2x3", FRENCH_VINTAGE, "CMA"),
        "LIQ": (
            liquidity["traded_liquidity_factor"] * LIQUIDITY_SCALE,
            "pastor_stambaugh_liquidity",
            LIQUIDITY_VINTAGE,
            "traded_liquidity_factor times 100",
        ),
        "ME": (q_factors["R_ME"], "q_factors", Q_VINTAGE, "R_ME"),
        "IA": (q_factors["R_IA"], "q_factors", Q_VINTAGE, "R_IA"),
        "ROE": (q_factors["R_ROE"], "q_factors", Q_VINTAGE, "R_ROE"),
    }

    panel = pd.DataFrame(index=window)
    panel.index.name = "month"
    for name, (series, _, _, _) in columns.items():
        aligned = series.reindex(window)
        missing = [str(period) for period in window[aligned.isna()]]
        if missing:
            raise DataValidationError(
                f"Comparator factor {name} is missing {len(missing)} baseline months, "
                f"first {missing[0]}"
            )
        panel[name] = aligned.to_numpy(dtype=float)

    PANEL_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    output = panel.reset_index()
    output["month"] = output["month"].astype(str)
    output.to_parquet(PANEL_PARQUET, index=False)

    rows = [
        {
            "column": name,
            "source_dataset": dataset,
            "source_vintage": vintage,
            "source_column": source_column,
            "units": "percent_per_month",
            "exact_or_reconstructed": (
                "documented_reconstruction; current vintage only, no publication-era vintage exists"
                if vintage == Q_VINTAGE
                else "documented_reconstruction; publication-era vintage"
            ),
        }
        for name, (_, dataset, vintage, source_column) in columns.items()
    ]
    COLUMN_METADATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    with COLUMN_METADATA_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/build_comparator_panel.py",
                "window": {"start": WINDOW_START, "end": WINDOW_END, "months": len(window)},
                "panel_path": PANEL_PARQUET.as_posix(),
                "panel_sha256": _sha256(PANEL_PARQUET),
                "columns": list(columns),
                "column_metadata": COLUMN_METADATA_CSV.as_posix(),
                "liquidity_scale": LIQUIDITY_SCALE,
                "vintages": {
                    "french": FRENCH_VINTAGE,
                    "liquidity": LIQUIDITY_VINTAGE,
                    "q_factors": Q_VINTAGE,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    print(f"Comparator panel: {len(panel)} months x {panel.shape[1]} factors")
    print(panel.describe().T[["mean", "std", "min", "max"]].round(4).to_string())
    print(f"Wrote {PANEL_PARQUET} and {PROVENANCE_JSON}")


if __name__ == "__main__":
    main()
