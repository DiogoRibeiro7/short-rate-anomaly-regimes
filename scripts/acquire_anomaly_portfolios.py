"""Acquire the seven baseline anomaly decile families from the original author source."""

from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path

from short_rate_anomaly_regimes.portfolios.q_archive import (
    DECLARED_FAMILY_ALTERNATIVES,
    FAMILY_MEMBERS,
    SUPPLEMENT_MEMBERS,
    freeze_family_panel,
    freeze_q_archive,
)

VINTAGE_LABEL = "global_q_2025_retrieved_20260802"
RAW_ROOT = Path("data/raw/portfolios/global_q")
NORMALIZED_ROOT = Path("data/interim/portfolios")
ARCHIVE_MANIFEST_ROOT = Path("artifacts/provenance/portfolios")
PANEL_MANIFEST_ROOT = Path("artifacts/provenance/portfolios/families")
SUMMARY_CSV = Path("artifacts/provenance/anomaly_portfolio_summary.csv")


def main() -> None:
    """Freeze both archives and reshape every registered anomaly family."""
    specifications = {**FAMILY_MEMBERS, **SUPPLEMENT_MEMBERS}
    archives = sorted({spec["archive"] for spec in specifications.values()})
    payloads: dict[str, bytes] = {}
    for archive in archives:
        record, payload = freeze_q_archive(
            archive=archive,
            vintage_label=VINTAGE_LABEL,
            raw_root=RAW_ROOT,
            manifest_root=ARCHIVE_MANIFEST_ROOT,
        )
        payloads[archive] = payload
        print(f"{archive}: {record.member_count} members sha={record.raw_sha256[:12]}")

    rows = []
    for family, specification in specifications.items():
        panel_record = freeze_family_panel(
            payloads[specification["archive"]],
            family=family,
            specification=specification,
            normalized_root=NORMALIZED_ROOT,
            manifest_root=PANEL_MANIFEST_ROOT,
            vintage_label=VINTAGE_LABEL,
        )
        row = {
            key: value for key, value in asdict(panel_record).items() if not isinstance(value, dict)
        }
        row["value_minimum"] = panel_record.value_range["minimum"]
        row["value_maximum"] = panel_record.value_range["maximum"]
        row["baseline_family"] = family in FAMILY_MEMBERS
        row["declared_alternatives"] = ";".join(DECLARED_FAMILY_ALTERNATIVES.get(family, ()))
        rows.append(row)
        print(
            f"{family:22s} {panel_record.article_label:4s} "
            f"n_portfolios={panel_record.number_of_portfolios} "
            f"{panel_record.sample_start}..{panel_record.sample_end} "
            f"months={panel_record.monthly_observations} "
            f"continuous={panel_record.continuous_months} "
            f"min_stocks={panel_record.minimum_stocks_per_portfolio}"
        )

    SUMMARY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {SUMMARY_CSV}")


if __name__ == "__main__":
    main()
