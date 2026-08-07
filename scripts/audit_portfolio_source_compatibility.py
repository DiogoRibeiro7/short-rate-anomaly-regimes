"""Audit the acquired anomaly panels against the article's published spread statistics.

This is an input-identification diagnostic, not a replication result. It asks
whether the current-vintage panels from the original author source are
source-compatible with the panels the article used, and it resolves the
holding-period ambiguity in the long-term-reversal family.

Every input is verified against its frozen manifest checksum before any
statistic is computed, and the outputs carry a companion provenance record, so
the published figures can only ever be attributed to the exact bytes named in
the manifests.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from short_rate_anomaly_regimes.exceptions import DataValidationError
from short_rate_anomaly_regimes.portfolios.q_archive import (
    FAMILY_MEMBERS,
    load_family_panel,
    reshape_family_panel,
)
from short_rate_anomaly_regimes.provenance import sha256_file

SCRIPT_NAME = "scripts/audit_portfolio_source_compatibility.py"

VINTAGE_LABEL = "global_q_2025_retrieved_20260802"
NORMALIZED_ROOT = Path("data/interim/portfolios")
RAW_ROOT = Path("data/raw/portfolios/global_q")
ARCHIVE_MANIFEST_ROOT = Path("artifacts/provenance/portfolios")
FAMILY_MANIFEST_ROOT = ARCHIVE_MANIFEST_ROOT / "families"
OUTPUT_CSV = Path("artifacts/data_quality/portfolio_source_compatibility.csv")
REVERSAL_CSV = Path("artifacts/data_quality/reversal_holding_period_selection.csv")
PROVENANCE_JSON = Path("artifacts/provenance/portfolio_compatibility_audit.json")

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

#: Reversal holding-period candidates declared before any statistic is inspected.
REVERSAL_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("portf_rev_1_monthly_2025.csv", "rank_Rev_1"),
    ("portf_rev_6_monthly_2025.csv", "rank_Rev_6"),
    ("portf_rev_12_monthly_2025.csv", "rank_Rev_12"),
)


def _read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise DataValidationError(f"Frozen manifest is missing: {path}")
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


def _require(manifest_path: Path, manifest: dict[str, Any], key: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        raise DataValidationError(f"Manifest {manifest_path} carries no usable {key!r} field")
    return value


def verify_against_manifest(
    *,
    file_path: Path,
    manifest_path: Path,
    checksum_key: str,
    path_key: str,
) -> str:
    """Verify one frozen input against the checksum recorded in its manifest.

    Args:
        file_path: File whose bytes are about to be used.
        manifest_path: Frozen manifest JSON recording the expected checksum.
        checksum_key: Manifest field holding the expected SHA-256 digest.
        path_key: Manifest field holding the path the digest was taken from.

    Returns:
        The verified SHA-256 digest of ``file_path``.

    Raises:
        DataValidationError: If the manifest, the file, the recorded path, the
            recorded vintage label, or the checksum does not match.
    """
    manifest = _read_manifest(manifest_path)
    if not file_path.is_file():
        raise DataValidationError(f"Frozen input is missing: {file_path}")
    recorded_path = _require(manifest_path, manifest, path_key)
    if recorded_path != file_path.as_posix():
        raise DataValidationError(
            f"Manifest {manifest_path} records {path_key}={recorded_path!r} "
            f"but this audit reads {file_path.as_posix()!r}"
        )
    recorded_vintage = manifest.get("vintage_label")
    if recorded_vintage is not None and recorded_vintage != VINTAGE_LABEL:
        raise DataValidationError(
            f"Manifest {manifest_path} records vintage {recorded_vintage!r} "
            f"but this audit attributes its output to {VINTAGE_LABEL!r}"
        )
    expected = _require(manifest_path, manifest, checksum_key)
    observed = sha256_file(file_path)
    if observed != expected:
        raise DataValidationError(
            f"Checksum mismatch for {file_path}: manifest {manifest_path} records "
            f"{expected} but the file on disk hashes to {observed}. The frozen input "
            f"has been altered or replaced; refusing to report a compatibility result."
        )
    return observed


def _spread_statistics(panel: pd.DataFrame) -> dict[str, float]:
    """Compute the decile-spread statistics on the full comparison window.

    Args:
        panel: Wide decile panel indexed by month period.

    Returns:
        The mean, standard deviation, minimum, maximum, first-order
        autocorrelation, and month count of the high-minus-low spread.

    Raises:
        DataValidationError: If any month of the comparison window is absent or
            null, since the article's statistics are defined on the full window.
    """
    spread = (panel["decile_10"] - panel["decile_01"]).reindex(WINDOW)
    missing = spread.index[spread.isna()]
    if len(missing):
        raise DataValidationError(
            f"The decile spread is missing {len(missing)} of {len(WINDOW)} months inside "
            f"{WINDOW[0]}..{WINDOW[-1]} (first {missing[0]}); the published statistics are "
            f"defined on the full window and cannot be compared on a shorter sample"
        )
    return {
        "mean": float(spread.mean()),
        "sd": float(spread.std(ddof=1)),
        "min": float(spread.min()),
        "max": float(spread.max()),
        "phi": float(spread.autocorr(lag=1)),
        "months": float(len(spread)),
    }


def _verified_family_inputs() -> dict[str, dict[str, str]]:
    verified: dict[str, dict[str, str]] = {}
    for family in FAMILY_MEMBERS:
        normalized_path = NORMALIZED_ROOT / f"{family}_{VINTAGE_LABEL}.csv"
        manifest_path = FAMILY_MANIFEST_ROOT / f"{family}_{VINTAGE_LABEL}.json"
        digest = verify_against_manifest(
            file_path=normalized_path,
            manifest_path=manifest_path,
            checksum_key="normalized_sha256",
            path_key="normalized_path",
        )
        verified[family] = {
            "path": normalized_path.as_posix(),
            "sha256": digest,
            "manifest": manifest_path.as_posix(),
        }
    return verified


def _verified_archive_payload(archive: str) -> tuple[bytes, dict[str, str]]:
    raw_path = RAW_ROOT / f"{archive}_{VINTAGE_LABEL}.zip"
    manifest_path = ARCHIVE_MANIFEST_ROOT / f"{archive}_{VINTAGE_LABEL}.json"
    digest = verify_against_manifest(
        file_path=raw_path,
        manifest_path=manifest_path,
        checksum_key="raw_sha256",
        path_key="raw_path",
    )
    payload = raw_path.read_bytes()
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise DataValidationError(f"Frozen archive {raw_path} is not a ZIP archive")
    with zipfile.ZipFile(io.BytesIO(payload)) as handle:
        if not handle.namelist():
            raise DataValidationError(f"Frozen archive {raw_path} is empty")
    return payload, {
        "path": raw_path.as_posix(),
        "sha256": digest,
        "manifest": manifest_path.as_posix(),
    }


def main() -> None:
    """Compare every family with its published spread statistics.

    Raises:
        DataValidationError: If any frozen input fails its manifest checksum or
            does not cover the full comparison window.
    """
    verified_families = _verified_family_inputs()
    payload, verified_archive = _verified_archive_payload("vvg_monthly_2025")

    rows = []
    for family in FAMILY_MEMBERS:
        panel = load_family_panel(Path(verified_families[family]["path"]))
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
    pd.DataFrame.from_records(rows).to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    reversal_rows = []
    reversal_members: list[dict[str, str]] = []
    published = PUBLISHED_SPREADS["long_term_reversal"]
    for member, rank_column in REVERSAL_CANDIDATES:
        returns, _, member_sha = reshape_family_panel(
            payload, archive="vvg_monthly_2025", member=member, rank_column=rank_column
        )
        reversal_members.append({"member": member, "member_sha256": member_sha})
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
    frame.to_csv(REVERSAL_CSV, index=False, lineterminator="\n")
    print(f"Closest reversal member: {frame.iloc[0]['member']}")

    _write_provenance(
        verified_families=verified_families,
        verified_archive=verified_archive,
        reversal_members=reversal_members,
    )
    print(f"Wrote {OUTPUT_CSV}, {REVERSAL_CSV}, and {PROVENANCE_JSON}")


def _write_provenance(
    *,
    verified_families: dict[str, dict[str, str]],
    verified_archive: dict[str, str],
    reversal_members: list[dict[str, str]],
) -> None:
    record = {
        "script": SCRIPT_NAME,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "vintage_label": VINTAGE_LABEL,
        "comparison_window": {
            "start": str(WINDOW[0]),
            "end": str(WINDOW[-1]),
            "months": len(WINDOW),
            "frequency": "M",
        },
        "tolerance_at_published_precision": TOLERANCE,
        "published_reference": (
            "article page 937 Table 2 Panel A high-minus-low decile spread statistics"
        ),
        "verified_inputs": {
            "normalized_family_panels": [
                {
                    "family": family,
                    "path": details["path"],
                    "sha256": details["sha256"],
                    "manifest": details["manifest"],
                    "manifest_checksum_field": "normalized_sha256",
                }
                for family, details in sorted(verified_families.items())
            ],
            "raw_archives": [
                {
                    "archive": "vvg_monthly_2025",
                    "path": verified_archive["path"],
                    "sha256": verified_archive["sha256"],
                    "manifest": verified_archive["manifest"],
                    "manifest_checksum_field": "raw_sha256",
                }
            ],
            "reversal_archive_members": sorted(
                reversal_members, key=lambda item: str(item["member"])
            ),
        },
        "outputs": [
            {"path": path.as_posix(), "sha256": sha256_file(path)}
            for path in (OUTPUT_CSV, REVERSAL_CSV)
        ],
    }
    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(record, indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
