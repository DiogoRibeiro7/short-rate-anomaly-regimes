"""Audit the acquired anomaly panels against the article's published spread statistics.

This is an input-identification diagnostic, not a replication result. It asks
whether the current-vintage panels from the original author source are
source-compatible with the panels the article used, and it resolves the
holding-period ambiguity in the long-term-reversal family.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.portfolios.q_archive import (
    FAMILY_MEMBERS,
    load_family_panel,
    reshape_family_panel,
)

VINTAGE_LABEL = "global_q_2025_retrieved_20260802"
NORMALIZED_ROOT = Path("data/interim/portfolios")
RAW_ROOT = Path("data/raw/portfolios/global_q")
OUTPUT_CSV = Path("artifacts/data_quality/portfolio_source_compatibility.csv")
REVERSAL_CSV = Path("artifacts/data_quality/reversal_holding_period_selection.csv")

WINDOW = pd.period_range("1972-01", "2013-12", freq="M")

#: Article page 937, Table 2 Panel A. High-minus-low spread between the tenth and
#: first decile within each family, 1972-01 to 2013-12.
PUBLISHED_SPREADS: dict[str, dict[str, float]] = {
    "book_to_market": {"mean": 0.69, "sd": 4.86, "min": -14.18, "max": 20.45, "phi": 0.11},
    "investment_to_assets": {"mean": -0.42, "sd": 3.62, "min": -14.39, "max": 11.83, "phi": 0.04},
    "ppe_investment": {"mean": -0.49, "sd": 3.00, "min": -10.37, "max": 8.60, "phi": 0.08},
    "equity_duration": {"mean": -0.52, "sd": 4.34, "min": -21.38, "max": 15.77, "phi": 0.09},
    "earnings_to_price": {"mean": 0.58, "sd": 4.83, "min": -15.47, "max": 22.53, "phi": 0.02},
    "long_term_reversal": {"mean": -0.41, "sd": 5.21, "min": -32.99, "max": 18.08, "phi": 0.06},
    "inventory_growth": {"mean": -0.36, "sd": 3.15, "min": -9.69, "max": 12.04, "phi": 0.07},
}

TOLERANCE = 0.005


def _spread_statistics(panel: pd.DataFrame) -> dict[str, float]:
    window = panel.index.intersection(WINDOW)
    spread = panel.loc[window, "decile_10"] - panel.loc[window, "decile_01"]
    return {
        "mean": float(spread.mean()),
        "sd": float(spread.std(ddof=1)),
        "min": float(spread.min()),
        "max": float(spread.max()),
        "phi": float(spread.autocorr(lag=1)),
        "months": float(len(spread)),
    }


def main() -> None:
    """Compare every family with its published spread statistics."""
    rows = []
    for family in FAMILY_MEMBERS:
        panel = load_family_panel(NORMALIZED_ROOT / f"{family}_{VINTAGE_LABEL}.csv")
        computed = _spread_statistics(panel)
        published = PUBLISHED_SPREADS[family]
        row: dict[str, object] = {"family": family, "months_compared": computed["months"]}
        matched = 0
        for statistic, published_value in published.items():
            difference = computed[statistic] - published_value
            row[f"published_{statistic}"] = published_value
            row[f"computed_{statistic}"] = round(computed[statistic], 4)
            row[f"difference_{statistic}"] = round(difference, 4)
            matched += int(abs(difference) <= TOLERANCE)
        row["statistics_matching_at_published_precision"] = matched
        row["statistics_compared"] = len(published)
        row["source_compatibility"] = (
            "identical_at_published_precision"
            if matched == len(published)
            else "same_source_lineage_different_vintage_or_construction"
        )
        rows.append(row)
        print(
            f"{family:22s} matched {matched}/{len(published)} "
            f"mean {computed['mean']:+.2f} vs {published['mean']:+.2f}  "
            f"sd {computed['sd']:.2f} vs {published['sd']:.2f}"
        )

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame.from_records(rows).to_csv(OUTPUT_CSV, index=False)

    payload = (RAW_ROOT / f"vvg_monthly_2025_{VINTAGE_LABEL}.zip").read_bytes()
    with zipfile.ZipFile(io.BytesIO(payload)) as handle:
        assert handle.namelist()
    reversal_rows = []
    published = PUBLISHED_SPREADS["long_term_reversal"]
    for member, rank_column in (
        ("portf_rev_1_monthly_2025.csv", "rank_Rev_1"),
        ("portf_rev_6_monthly_2025.csv", "rank_Rev_6"),
        ("portf_rev_12_monthly_2025.csv", "rank_Rev_12"),
    ):
        returns, _, _ = reshape_family_panel(
            payload, archive="vvg_monthly_2025", member=member, rank_column=rank_column
        )
        computed = _spread_statistics(returns)
        distance = sum(
            abs(computed[key] - published[key]) for key in ("mean", "sd", "min", "max", "phi")
        )
        reversal_rows.append(
            {
                "member": member,
                "holding_period_months": rank_column.split("_")[-1],
                **{f"computed_{key}": round(computed[key], 4) for key in published},
                **{f"published_{key}": value for key, value in published.items()},
                "total_absolute_distance": round(distance, 4),
            }
        )
        print(f"{member:34s} distance to published Table 2 row = {distance:.4f}")
    frame = pd.DataFrame.from_records(reversal_rows).sort_values("total_absolute_distance")
    frame["selected"] = [True] + [False] * (len(frame) - 1)
    frame.to_csv(REVERSAL_CSV, index=False)
    print(f"Closest reversal member: {frame.iloc[0]['member']}")
    print(f"Wrote {OUTPUT_CSV} and {REVERSAL_CSV}")


if __name__ == "__main__":
    main()
