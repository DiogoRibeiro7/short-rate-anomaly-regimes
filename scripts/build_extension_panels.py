"""Build the post-2013 extension panel and the revised-history baseline panel.

Two panels are produced by one code path, which is what lets the temporal effect
be separated from the vintage effect.

- The **extension panel** covers 2014-01 to the binding 2025-12 endpoint on the
  current factor vintage. It is genuinely out of sample with respect to the
  article, whose sample ends 2013-12.
- The **revised-history panel** covers the *baseline* window on the *current*
  vintage. It shares its months with the locked baseline panel and its vintage
  with the extension panel, so differencing against one isolates the vintage
  change and against the other isolates the temporal change.

The locked baseline panel is never rewritten here.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.aggregation_audit import aggregate_daily_to_monthly
from short_rate_anomaly_regimes.data.comparator_freeze import load_normalized_comparator
from short_rate_anomaly_regimes.data.french_freeze import load_normalized_french
from short_rate_anomaly_regimes.data.short_rate_freeze import load_normalized_series
from short_rate_anomaly_regimes.exceptions import DataValidationError
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS, load_family_panel
from short_rate_anomaly_regimes.rates.baseline_reconstruction import monthly_rate_from_freeze

BASELINE_START = "1972-01"
BASELINE_END = "2013-12"
EXTENSION_START = "2014-01"
#: Binding common endpoint: the anomaly decile panels end 2025-12 while the rate
#: and factor data run further. See reports/baseline_input_readiness.md.
EXTENSION_END = "2025-12"

FRED_DATE = "2026-08-01"
CURRENT_FRENCH_VINTAGE = "current_20260801"
CURRENT_LIQUIDITY_VINTAGE = "current_20260802"
PORTFOLIO_VINTAGE = "global_q_2025_retrieved_20260802"
Q_VINTAGE = "global_q_2025_retrieved_20260802"

FRED_ROOT = Path("data/interim/fred")
FRENCH_ROOT = Path("data/interim/kenneth_french")
COMPARATOR_ROOT = Path("data/interim/comparators")
PORTFOLIO_ROOT = Path("data/interim/portfolios")

EXTENSION_PARQUET = Path("data/processed/extension/monthly_panel.parquet")
REVISED_HISTORY_PARQUET = Path("data/processed/extension/revised_history_panel.parquet")
COLUMN_METADATA_CSV = Path("artifacts/provenance/extension_panel_column_metadata.csv")
PROVENANCE_JSON = Path("artifacts/provenance/extension_panels.json")

LIQUIDITY_SCALE = 100.0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_sources() -> dict[str, pd.DataFrame]:
    """Load every current-vintage source needed by both panels."""
    three = load_normalized_french(
        FRENCH_ROOT / f"F-F_Research_Data_Factors_{CURRENT_FRENCH_VINTAGE}.csv"
    )
    momentum = load_normalized_french(
        FRENCH_ROOT / f"F-F_Momentum_Factor_{CURRENT_FRENCH_VINTAGE}.csv"
    )
    five = load_normalized_french(
        FRENCH_ROOT / f"F-F_Research_Data_5_Factors_2x3_{CURRENT_FRENCH_VINTAGE}.csv"
    )
    liquidity = load_normalized_comparator(
        COMPARATOR_ROOT / f"pastor_stambaugh_liquidity_{CURRENT_LIQUIDITY_VINTAGE}.csv"
    )
    q_factors = load_normalized_comparator(COMPARATOR_ROOT / f"q_factors_{Q_VINTAGE}.csv")
    return {
        "three": three,
        "momentum": momentum,
        "five": five,
        "liquidity": liquidity,
        "q_factors": q_factors,
    }


def _build(
    window_start: str, window_end: str, label: str
) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    """Assemble one monthly panel on the current vintage over the given window."""
    window = pd.period_range(window_start, window_end, freq="M")
    sources = _load_sources()
    three = sources["three"]
    five = sources["five"]

    levels = {
        "fedfunds": monthly_rate_from_freeze(
            load_normalized_series(FRED_ROOT / f"FEDFUNDS_{FRED_DATE}.csv")
        ),
        "tb3ms": monthly_rate_from_freeze(
            load_normalized_series(FRED_ROOT / f"TB3MS_{FRED_DATE}.csv")
        ),
        "dtb3_monthly_mean": monthly_rate_from_freeze(
            aggregate_daily_to_monthly(
                load_normalized_series(FRED_ROOT / f"DTB3_{FRED_DATE}.csv"),
                rule="available_observation_mean",
            )
        ),
    }

    columns: dict[str, tuple[pd.Series, str, str]] = {
        "market_excess_return": (three["Mkt-RF"], "F-F_Research_Data_Factors", "percent_per_month"),
        "risk_free_return": (three["RF"], "F-F_Research_Data_Factors", "percent_per_month"),
        "SMB": (three["SMB"], "F-F_Research_Data_Factors", "percent_per_month"),
        "HML": (three["HML"], "F-F_Research_Data_Factors", "percent_per_month"),
        "UMD": (sources["momentum"]["Mom"], "F-F_Momentum_Factor", "percent_per_month"),
        "RMW": (five["RMW"], "F-F_Research_Data_5_Factors_2x3", "percent_per_month"),
        "CMA": (five["CMA"], "F-F_Research_Data_5_Factors_2x3", "percent_per_month"),
        "LIQ": (
            sources["liquidity"]["traded_liquidity_factor"] * LIQUIDITY_SCALE,
            "pastor_stambaugh_liquidity",
            "percent_per_month",
        ),
        "ME": (sources["q_factors"]["R_ME"], "q_factors", "percent_per_month"),
        "IA": (sources["q_factors"]["R_IA"], "q_factors", "percent_per_month"),
        "ROE": (sources["q_factors"]["R_ROE"], "q_factors", "percent_per_month"),
    }
    for name, series in levels.items():
        columns[f"short_rate_level__{name}"] = (
            series,
            f"FRED {name.upper()}",
            "annualized_percentage_points",
        )

    panel = pd.DataFrame(index=window)
    panel.index.name = "month"
    metadata: list[dict[str, str]] = []
    for name, (series, source, units) in columns.items():
        aligned = series.reindex(window)
        missing = [str(period) for period in window[aligned.isna()]]
        if missing:
            raise DataValidationError(
                f"{label}: column {name} is missing {len(missing)} months, first {missing[0]}"
            )
        panel[name] = aligned.to_numpy(dtype=float)
        metadata.append(
            {
                "panel": label,
                "column": name,
                "source": source,
                "units": units,
                "vintage": "current",
            }
        )

    risk_free = panel["risk_free_return"]
    for family in FAMILY_MEMBERS:
        family_panel = load_family_panel(
            PORTFOLIO_ROOT / f"{family}_{PORTFOLIO_VINTAGE}.csv"
        ).reindex(window)
        missing_family = [str(period) for period in window[family_panel.isna().any(axis=1)]]
        if missing_family:
            raise DataValidationError(
                f"{label}: family {family} is missing {len(missing_family)} months, "
                f"first {missing_family[0]}"
            )
        for decile in family_panel.columns:
            column = f"portfolio_excess_return__{family}__{decile}"
            panel[column] = family_panel[decile].to_numpy(dtype=float) - risk_free.to_numpy(
                dtype=float
            )
            metadata.append(
                {
                    "panel": label,
                    "column": column,
                    "source": f"global-q.org {family}",
                    "units": "percent_per_month",
                    "vintage": PORTFOLIO_VINTAGE,
                }
            )
    return panel, metadata


def _write(panel: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = panel.reset_index()
    output["month"] = output["month"].astype(str)
    output.to_parquet(path, index=False)


def main() -> None:
    """Build both panels and record their provenance."""
    extension, extension_metadata = _build(EXTENSION_START, EXTENSION_END, "extension")
    revised, revised_metadata = _build(BASELINE_START, BASELINE_END, "revised_history")

    _write(extension, EXTENSION_PARQUET)
    _write(revised, REVISED_HISTORY_PARQUET)

    COLUMN_METADATA_CSV.parent.mkdir(parents=True, exist_ok=True)
    rows = extension_metadata + revised_metadata
    with COLUMN_METADATA_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/build_extension_panels.py",
                "replication_status": "documented_reconstruction",
                "extension": {
                    "path": EXTENSION_PARQUET.as_posix(),
                    "sha256": _sha256(EXTENSION_PARQUET),
                    "start": EXTENSION_START,
                    "end": EXTENSION_END,
                    "months": len(extension),
                    "vintage": "current",
                },
                "revised_history": {
                    "path": REVISED_HISTORY_PARQUET.as_posix(),
                    "sha256": _sha256(REVISED_HISTORY_PARQUET),
                    "start": BASELINE_START,
                    "end": BASELINE_END,
                    "months": len(revised),
                    "vintage": "current",
                    "purpose": (
                        "shares months with the locked baseline panel and vintage with the "
                        "extension panel, so the vintage effect and the temporal effect can "
                        "be separated"
                    ),
                },
                "vintages": {
                    "french": CURRENT_FRENCH_VINTAGE,
                    "liquidity": CURRENT_LIQUIDITY_VINTAGE,
                    "q_factors": Q_VINTAGE,
                    "portfolios": PORTFOLIO_VINTAGE,
                    "fred": FRED_DATE,
                },
                "endpoint_note": (
                    "2025-12 is the binding common endpoint because the anomaly decile panels "
                    "end there while the rate and factor data run to 2026-06 and 2026-05"
                ),
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    print(f"extension panel      : {len(extension)} months x {extension.shape[1]} columns")
    print(f"revised-history panel: {len(revised)} months x {revised.shape[1]} columns")
    print(f"Wrote {EXTENSION_PARQUET}, {REVISED_HISTORY_PARQUET}, {PROVENANCE_JSON}")


if __name__ == "__main__":
    main()
