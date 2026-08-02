"""Acquire the q-factor and Pastor-Stambaugh liquidity comparator files.

The script also resolves two definitional ambiguities the article leaves open by
comparing every admissible candidate with the article's Table 1 Panel A row for
that factor. The comparison identifies inputs; it is not a replication result.
"""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.comparator_freeze import (
    freeze_comparator_file,
    load_normalized_comparator,
)

RAW_ROOT = Path("data/raw/comparators")
NORMALIZED_ROOT = Path("data/interim/comparators")
MANIFEST_ROOT = Path("artifacts/provenance/comparators")
SUMMARY_CSV = Path("artifacts/provenance/comparator_freeze_summary.csv")
COMPATIBILITY_CSV = Path("artifacts/data_quality/comparator_source_compatibility.csv")
LIQUIDITY_SELECTION_CSV = Path("artifacts/data_quality/liquidity_column_selection.csv")

WINDOW = pd.period_range("1972-01", "2013-12", freq="M")

STAMBAUGH_BASE = "https://finance.wharton.upenn.edu/~stambaug"

SPECIFICATIONS = (
    {
        "dataset": "q_factors",
        "url": ("https://global-q.org/uploads/1/2/2/6/122679606/q5_factors_monthly_2025.csv"),
        "file_name": "q5_factors_monthly_2025.csv",
        "parser": "q_factor_csv",
        "provider": "Hou, Xue, and Zhang q-factor library (global-q.org)",
        "attributed_by_article_to": "Lu Zhang",
        "units": "percent_per_month",
        "missing_value_code": "none; absent months are omitted rather than coded",
        "redistribution_status": (
            "public author-provided research data; the download page states no "
            "registration or licensing condition. Raw bytes are retained locally and "
            "are not redistributed by this repository."
        ),
        "vintage_label": "global_q_2025_retrieved_20260802",
        "archive_date": "2026-08-02",
    },
    {
        "dataset": "pastor_stambaugh_liquidity",
        "url": (
            "https://web.archive.org/web/20170828055543id_/"
            "http://finance.wharton.upenn.edu/~stambaug/liq_data_1962_2016.txt"
        ),
        "file_name": "liq_data_1962_2016.txt",
        "parser": "liquidity_text",
        "provider": "Robert Stambaugh, Wharton",
        "attributed_by_article_to": "Robert Stambaugh's web page",
        "units": "decimal_per_month",
        "missing_value_code": "-99",
        "redistribution_status": (
            "public author-provided research data; no licensing condition is stated on "
            "the source page. Raw bytes are retained locally and are not redistributed "
            "by this repository."
        ),
        "vintage_label": "publication_era_20170828",
        "archive_date": "2017-08-28",
    },
    {
        "dataset": "pastor_stambaugh_liquidity",
        "url": f"{STAMBAUGH_BASE}/liq_data_1962_2025.txt",
        "file_name": "liq_data_1962_2025.txt",
        "parser": "liquidity_text",
        "provider": "Robert Stambaugh, Wharton",
        "attributed_by_article_to": "Robert Stambaugh's web page",
        "units": "decimal_per_month",
        "missing_value_code": "-99",
        "redistribution_status": (
            "public author-provided research data; no licensing condition is stated on "
            "the source page. Raw bytes are retained locally and are not redistributed "
            "by this repository."
        ),
        "vintage_label": "current_20260802",
        "archive_date": "2026-08-02",
    },
)

#: Article page 936, Table 1 Panel A, sample 1972-01 to 2013-12.
PUBLISHED_TABLE_ONE = {
    "LIQ": {"mean": 0.43, "sd": 3.57, "min": -10.14, "max": 21.01, "phi": 0.09},
    "ME": {"mean": 0.31, "sd": 3.14, "min": -14.45, "max": 22.41, "phi": 0.03},
    "IA": {"mean": 0.44, "sd": 1.87, "min": -7.13, "max": 9.41, "phi": 0.06},
    "ROE": {"mean": 0.57, "sd": 2.62, "min": -13.85, "max": 10.39, "phi": 0.10},
}

TOLERANCE = 0.005


def _statistics(series: pd.Series) -> dict[str, float]:
    window = series.index.intersection(WINDOW)
    values = series.loc[window].dropna()
    return {
        "mean": float(values.mean()),
        "sd": float(values.std(ddof=1)),
        "min": float(values.min()),
        "max": float(values.max()),
        "phi": float(values.autocorr(lag=1)),
        "months": float(len(values)),
    }


def _compare(label: str, series: pd.Series, source: str) -> dict[str, object]:
    computed = _statistics(series)
    published = PUBLISHED_TABLE_ONE[label]
    row: dict[str, object] = {"factor": label, "source": source, "months": computed["months"]}
    matched = 0
    total = 0.0
    for statistic, published_value in published.items():
        difference = computed[statistic] - published_value
        row[f"published_{statistic}"] = published_value
        row[f"computed_{statistic}"] = round(computed[statistic], 4)
        row[f"difference_{statistic}"] = round(difference, 4)
        matched += int(abs(difference) <= TOLERANCE)
        total += abs(difference)
    row["statistics_matching_at_published_precision"] = matched
    row["statistics_compared"] = len(published)
    row["total_absolute_distance"] = round(total, 4)
    return row


def main() -> None:
    """Freeze both comparator sources and audit them against the article."""
    records = []
    for specification in SPECIFICATIONS:
        record = freeze_comparator_file(
            dataset=specification["dataset"],
            url=specification["url"],
            file_name=specification["file_name"],
            parser=specification["parser"],
            provider=specification["provider"],
            attributed_by_article_to=specification["attributed_by_article_to"],
            units=specification["units"],
            missing_value_code=specification["missing_value_code"],
            redistribution_status=specification["redistribution_status"],
            vintage_label=specification["vintage_label"],
            archive_date=specification["archive_date"],
            raw_root=RAW_ROOT,
            normalized_root=NORMALIZED_ROOT,
            manifest_root=MANIFEST_ROOT,
        )
        records.append(record)
        print(
            f"{record.dataset:28s} {record.vintage_label:26s} "
            f"{record.monthly_start}..{record.monthly_end} n={record.monthly_observations} "
            f"cols={list(record.columns)} missing={record.missing_value_count} "
            f"sha={record.raw_sha256[:12]}"
        )

    rows = []
    for record in records:
        row = {
            key: value
            for key, value in asdict(record).items()
            if not isinstance(value, dict | tuple | list)
        }
        row["columns"] = ";".join(record.columns)
        row["source_metadata_lines"] = " | ".join(record.source_metadata_lines)
        row["value_minimum"] = record.value_range["minimum"]
        row["value_maximum"] = record.value_range["maximum"]
        rows.append(row)
    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    # Resolve which liquidity column and scale the article's LIQ refers to.
    liquidity = load_normalized_comparator(
        NORMALIZED_ROOT / "pastor_stambaugh_liquidity_publication_era_20170828.csv"
    )
    selection_rows = []
    for column in liquidity.columns:
        for scale, scale_label in ((1.0, "as_published"), (100.0, "times_one_hundred")):
            candidate = _compare("LIQ", liquidity[column] * scale, f"{column}|{scale_label}")
            candidate["column"] = column
            candidate["scale"] = scale_label
            selection_rows.append(candidate)
    selection = pd.DataFrame.from_records(selection_rows).sort_values("total_absolute_distance")
    selection["selected"] = [True] + [False] * (len(selection) - 1)
    LIQUIDITY_SELECTION_CSV.parent.mkdir(parents=True, exist_ok=True)
    selection.to_csv(LIQUIDITY_SELECTION_CSV, index=False)
    chosen = selection.iloc[0]
    print(
        f"\nLIQ resolved to column {chosen['column']!r} scaled {chosen['scale']} "
        f"(distance {chosen['total_absolute_distance']}, "
        f"{int(chosen['statistics_matching_at_published_precision'])}/5 at published precision)"
    )

    q_factors = load_normalized_comparator(
        NORMALIZED_ROOT / "q_factors_global_q_2025_retrieved_20260802.csv"
    )
    compatibility = [
        _compare(label, q_factors[column] * 1.0, f"q5_factors_2025|{column}")
        for label, column in (("ME", "R_ME"), ("IA", "R_IA"), ("ROE", "R_ROE"))
    ]
    compatibility.append(
        _compare(
            "LIQ",
            liquidity[str(chosen["column"])]
            * (100.0 if chosen["scale"] == "times_one_hundred" else 1.0),
            f"pastor_stambaugh_publication_era|{chosen['column']}",
        )
    )
    current_liquidity = load_normalized_comparator(
        NORMALIZED_ROOT / "pastor_stambaugh_liquidity_current_20260802.csv"
    )
    compatibility.append(
        _compare(
            "LIQ",
            current_liquidity[str(chosen["column"])]
            * (100.0 if chosen["scale"] == "times_one_hundred" else 1.0),
            f"pastor_stambaugh_current|{chosen['column']}",
        )
    )
    frame = pd.DataFrame.from_records(compatibility)
    frame.to_csv(COMPATIBILITY_CSV, index=False)
    print()
    print(
        frame[
            [
                "factor",
                "source",
                "months",
                "published_mean",
                "computed_mean",
                "published_sd",
                "computed_sd",
                "statistics_matching_at_published_precision",
                "total_absolute_distance",
            ]
        ].to_string(index=False)
    )
    print(f"\nWrote {SUMMARY_CSV}, {COMPATIBILITY_CSV}, and {LIQUIDITY_SELECTION_CSV}")


if __name__ == "__main__":
    main()
