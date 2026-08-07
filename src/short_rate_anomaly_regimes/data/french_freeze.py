"""Immutable acquisition and freezing of Kenneth French Data Library archives.

Two vintages are handled: the closest archived snapshot to the article's
publication date, retrieved from the Internet Archive, and the current file
retrieved from the library itself. Both are frozen with complete metadata so
that a revision comparison can be made on the common sample.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.data.acquisition import (
    HTTPSession,
    _session_with_retries,
    canonical_monthly_bytes,
    load_normalized_month_panel,
    write_raw_once,
)
from short_rate_anomaly_regimes.exceptions import DataAccessError, DataValidationError

FRENCH_BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"

#: Kenneth French encodes an unavailable observation with these sentinels.
FRENCH_MISSING_VALUE_CODES = (-99.99, -999.0)

_MONTHLY_ROW = re.compile(r"^\s*(\d{6})\s*,")
_HEADER_ROW = re.compile(r"^\s*,")


@dataclass(frozen=True, slots=True)
class FrenchFreezeRecord:
    """Complete freeze metadata for one Kenneth French archive vintage."""

    dataset: str
    vintage_label: str
    archive_date: str
    file_name: str
    source_url: str
    provider: str
    retrieved_at_utc: str
    raw_path: str
    normalized_path: str
    raw_sha256: str
    normalized_sha256: str
    member_name: str
    member_sha256: str
    columns: tuple[str, ...]
    monthly_start: str
    monthly_end: str
    monthly_observations: int
    units: str
    missing_value_codes: tuple[float, ...]
    missing_value_count: int
    redistribution_status: str
    source_metadata_lines: tuple[str, ...]
    http_last_modified: str | None = None
    http_etag: str | None = None
    value_range: dict[str, float] = field(default_factory=dict)


def parse_french_monthly_block(text: str) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Extract the monthly panel and the leading descriptive lines from a French CSV.

    Args:
        text: Decoded contents of the archive member.

    Returns:
        A tuple of the monthly frame indexed by month period and the descriptive
        header lines that precede the monthly panel.

    Raises:
        DataValidationError: When no monthly panel or column header can be found.
    """
    lines = text.splitlines()
    header_index: int | None = None
    first_data_index: int | None = None
    for position, line in enumerate(lines):
        if _MONTHLY_ROW.match(line):
            first_data_index = position
            break
    if first_data_index is None:
        raise DataValidationError("No monthly YYYYMM rows found in the French archive member")
    for position in range(first_data_index - 1, -1, -1):
        if _HEADER_ROW.match(lines[position]) and "," in lines[position]:
            header_index = position
            break
    if header_index is None:
        raise DataValidationError("No column header found above the French monthly panel")

    columns = [part.strip() for part in lines[header_index].split(",")][1:]
    records: list[tuple[str, list[float]]] = []
    for line in lines[first_data_index:]:
        match = _MONTHLY_ROW.match(line)
        if not match:
            break
        parts = [part.strip() for part in line.split(",")]
        values = [float(part) for part in parts[1 : len(columns) + 1]]
        records.append((match.group(1), values))
    if not records:
        raise DataValidationError("French monthly panel is empty")

    index = pd.PeriodIndex([pd.Period(stamp, freq="M") for stamp, _ in records], freq="M")
    frame = pd.DataFrame([values for _, values in records], index=index, columns=columns)
    frame = frame.astype(float)
    frame = frame.mask(frame.isin(FRENCH_MISSING_VALUE_CODES))
    descriptive = tuple(line.strip() for line in lines[:header_index] if line.strip())
    return frame, descriptive


def freeze_french_archive(
    *,
    dataset: str,
    url: str,
    vintage_label: str,
    archive_date: str,
    raw_root: Path,
    normalized_root: Path,
    manifest_root: Path,
    session: HTTPSession | None = None,
    timeout: float = 120.0,
    retries: int = 3,
) -> FrenchFreezeRecord:
    """Download one Kenneth French archive vintage and freeze it with metadata.

    Args:
        dataset: Archive base name without the ``_CSV.zip`` suffix.
        url: Fully qualified download URL for this vintage.
        vintage_label: Stable label recorded with every derived artifact.
        archive_date: ISO date identifying the vintage.
        raw_root: Directory receiving immutable raw ZIP bytes.
        normalized_root: Directory receiving the canonical monthly CSV.
        manifest_root: Directory receiving the freeze manifest JSON.
        session: Optional HTTP session for testing.
        timeout: Request timeout in seconds.
        retries: Retry budget for transient failures.

    Returns:
        The complete freeze record.

    Raises:
        DataAccessError: On a non-200 response, an empty or non-ZIP payload, or an
            attempt to overwrite an existing raw file with different bytes.
        DataValidationError: When the archive contains no parsable member. The
            archive member is extracted and parsed before any raw file is written,
            so a malformed payload never occupies the immutable path and a later
            retry with the valid payload still succeeds.
    """
    client = session or _session_with_retries(retries)
    response = client.get(url, timeout=timeout)
    if response.status_code != 200:
        raise DataAccessError(f"Unexpected HTTP status {response.status_code} for {url}")
    payload = response.content
    if not payload:
        raise DataAccessError(f"Empty payload for {url}")
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise DataAccessError(f"Payload for {url} is not a ZIP archive")

    # The member is extracted and parsed before the raw bytes are committed, so a
    # malformed HTTP 200 cannot permanently occupy the immutable path.
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if not members:
            raise DataValidationError("French archive contains no files")
        member = members[0]
        member_bytes = archive.read(member)
    text = member_bytes.decode("latin-1")
    frame, descriptive = parse_french_monthly_block(text)
    normalized_bytes = canonical_monthly_bytes(frame)

    file_name = f"{dataset}_CSV.zip"
    raw_path = raw_root / dataset / f"{dataset}_{vintage_label}.zip"
    raw_sha = write_raw_once(raw_path, payload)

    normalized_path = normalized_root / f"{dataset}_{vintage_label}.csv"
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_bytes(normalized_bytes)

    record = FrenchFreezeRecord(
        dataset=dataset,
        vintage_label=vintage_label,
        archive_date=archive_date,
        file_name=file_name,
        source_url=url,
        provider="Kenneth French Data Library",
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        raw_path=raw_path.as_posix(),
        normalized_path=normalized_path.as_posix(),
        raw_sha256=raw_sha,
        normalized_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        member_name=member.filename,
        member_sha256=hashlib.sha256(member_bytes).hexdigest(),
        columns=tuple(str(column) for column in frame.columns),
        monthly_start=str(frame.index[0]),
        monthly_end=str(frame.index[-1]),
        monthly_observations=len(frame),
        units="percent_per_month",
        missing_value_codes=FRENCH_MISSING_VALUE_CODES,
        missing_value_count=int(frame.isna().to_numpy().sum()),
        redistribution_status=(
            "public research data provided by the Kenneth French Data Library; raw "
            "archive bytes are retained locally and are not redistributed by this "
            "repository"
        ),
        source_metadata_lines=descriptive,
        http_last_modified=response.headers.get("Last-Modified"),
        http_etag=response.headers.get("ETag"),
        value_range={
            "minimum": float(np.nanmin(frame.to_numpy(dtype=float))),
            "maximum": float(np.nanmax(frame.to_numpy(dtype=float))),
        },
    )
    manifest_root.mkdir(parents=True, exist_ok=True)
    (manifest_root / f"{dataset}_{vintage_label}.json").write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
    return record


def load_normalized_french(path: Path) -> pd.DataFrame:
    """Load a normalized French monthly panel indexed by month period.

    Args:
        path: Path to a normalized French CSV written by this module.

    Returns:
        The month-indexed float panel.
    """
    return load_normalized_month_panel(path)


def _vintage_verdict(
    *,
    months_with_value_difference: int,
    months_beyond_tolerance: int,
    months_with_changed_missingness: int,
) -> str:
    """Label one column's revision, letting a coverage change dominate the verdict."""
    if months_with_changed_missingness:
        return "revised_observation_coverage_changed"
    if months_with_value_difference == 0:
        return "identical_on_common_sample"
    if months_beyond_tolerance == 0:
        return "revised_within_publication_rounding"
    return "revised_beyond_publication_rounding"


def compare_vintages(
    *,
    historical: pd.DataFrame,
    current: pd.DataFrame,
    dataset: str,
    historical_label: str,
    current_label: str,
    tolerance: float = 0.005,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compare two vintages of the same archive on their common sample.

    A revision that adds or removes an observation is a revision, not a
    coincidence of alignment, so a month that is present in exactly one vintage is
    counted as a difference rather than masked. Such a month is reported in
    ``months_only_in_historical`` and ``months_only_in_current``, is included in
    ``months_with_any_difference`` and ``months_beyond_tolerance`` because an
    appearing or disappearing observation is never a rounding difference, and
    forces the verdict away from ``identical_on_common_sample``. The magnitude
    columns remain defined on the months both vintages observe.

    Args:
        historical: Normalized panel from the publication-era vintage.
        current: Normalized panel from the current vintage.
        dataset: Archive name recorded in both outputs.
        historical_label: Vintage label of the historical file.
        current_label: Vintage label of the current file.
        tolerance: Half of the published increment for the archive.

    Returns:
        A per-column summary frame and a frame of every differing month, the
        latter labelled by ``change_type`` as a value revision, an added
        observation, or a removed observation.

    Raises:
        ValueError: If the two vintages share no column or no month.
    """
    shared_columns = [column for column in historical.columns if column in current.columns]
    shared_months = historical.index.intersection(current.index)
    if not shared_columns or len(shared_months) == 0:
        raise ValueError("Vintages share no comparable column or month")

    summaries = []
    differing_rows = []
    for column in shared_columns:
        left = historical.loc[shared_months, column]
        right = current.loc[shared_months, column]
        left_present = left.notna()
        right_present = right.notna()
        both_present = left_present & right_present
        either_present = left_present | right_present
        only_historical = left_present & ~right_present
        only_current = right_present & ~left_present
        missingness_differs = only_historical | only_current

        difference = (right - left).where(both_present)
        absolute = difference.abs()
        changed = (absolute > tolerance).fillna(False)

        months_only_in_historical = int(only_historical.sum())
        months_only_in_current = int(only_current.sum())
        months_with_changed_missingness = months_only_in_historical + months_only_in_current
        months_with_value_difference = int((absolute > 0).sum())
        months_beyond_tolerance = int(changed.sum())
        observed_months = int(either_present.sum())
        summaries.append(
            {
                "dataset": dataset,
                "column": column,
                "historical_vintage": historical_label,
                "current_vintage": current_label,
                "common_months": int(both_present.sum()),
                "months_only_in_historical": months_only_in_historical,
                "months_only_in_current": months_only_in_current,
                "months_with_changed_missingness": months_with_changed_missingness,
                "missingness_identical": months_with_changed_missingness == 0,
                "months_with_any_difference": (
                    months_with_value_difference + months_with_changed_missingness
                ),
                "months_beyond_tolerance": (
                    months_beyond_tolerance + months_with_changed_missingness
                ),
                "share_beyond_tolerance": (
                    float(
                        (months_beyond_tolerance + months_with_changed_missingness)
                        / observed_months
                    )
                    if observed_months
                    else float("nan")
                ),
                "max_absolute_difference": float(absolute.max()) if both_present.any() else 0.0,
                "mean_absolute_difference": float(absolute.mean()) if both_present.any() else 0.0,
                "tolerance": tolerance,
                "verdict": _vintage_verdict(
                    months_with_value_difference=months_with_value_difference,
                    months_beyond_tolerance=months_beyond_tolerance,
                    months_with_changed_missingness=months_with_changed_missingness,
                ),
            }
        )
        for period in shared_months[(changed | missingness_differs).to_numpy()]:
            historical_value = float(left.loc[period])
            current_value = float(right.loc[period])
            if bool(only_current.loc[period]):
                change_type = "observation_added_by_current"
            elif bool(only_historical.loc[period]):
                change_type = "observation_removed_by_current"
            else:
                change_type = "value_revision"
            differing_rows.append(
                {
                    "dataset": dataset,
                    "column": column,
                    "month": str(period),
                    "change_type": change_type,
                    "historical_value": historical_value,
                    "current_value": current_value,
                    "difference": current_value - historical_value,
                }
            )
    return (
        pd.DataFrame.from_records(summaries),
        pd.DataFrame.from_records(
            differing_rows,
            columns=[
                "dataset",
                "column",
                "month",
                "change_type",
                "historical_value",
                "current_value",
                "difference",
            ],
        ),
    )
