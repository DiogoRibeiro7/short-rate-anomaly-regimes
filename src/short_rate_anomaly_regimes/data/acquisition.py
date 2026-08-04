"""Immutable public and manual data-ingestion helpers."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from short_rate_anomaly_regimes.exceptions import DataAccessError, DataValidationError
from short_rate_anomaly_regimes.provenance import sha256_file


class ResponseLike(Protocol):
    """Subset of ``requests.Response`` required by the download helpers."""

    status_code: int
    headers: dict[str, str]
    content: bytes


class HTTPSession(Protocol):
    """HTTP session protocol for real or mocked clients."""

    def get(self, url: str, *, timeout: float) -> ResponseLike:
        """Fetch one URL."""


@dataclass(frozen=True, slots=True)
class DownloadRecord:
    """Provenance metadata for one immutable raw download."""

    source_id: str
    url: str
    provider: str
    licence_note: str
    retrieved_at_utc: str
    raw_path: str
    interim_path: str
    sha256: str
    content_type: str
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True, slots=True)
class ManualRegistrationRecord:
    """Metadata for a manually supplied restricted or author-provided source."""

    source_id: str
    file_path: str
    sha256: str
    registered_at_utc: str
    redistribution_status: str
    rows: int
    columns: tuple[str, ...]
    sample_start: str | None
    sample_end: str | None


def _session_with_retries(retries: int) -> requests.Session:
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        backoff_factor=0.5,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def write_raw_once(path: Path, payload: bytes) -> str:
    """Write raw provider bytes exactly once at an immutable path.

    Every freeze module shares this writer so that one rule governs all immutable
    paths: the bytes are written by the first successful acquisition, and a later
    acquisition may only reproduce them.

    Args:
        path: Immutable destination for the raw provider bytes.
        payload: Raw provider bytes.

    Returns:
        The SHA-256 hexadecimal digest of the bytes now stored at ``path``.

    Raises:
        DataAccessError: If ``path`` already exists and holds different bytes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    incoming = hashlib.sha256(payload).hexdigest()
    if path.exists():
        existing = sha256_file(path)
        if existing != incoming:
            raise DataAccessError(
                f"Refusing to overwrite an existing raw file with different bytes: {path}"
            )
        return existing
    path.write_bytes(payload)
    return incoming


def canonical_monthly_bytes(frame: pd.DataFrame) -> bytes:
    """Serialize a month-indexed panel deterministically for checksum comparison.

    Args:
        frame: Panel indexed by monthly periods whose columns are numeric.

    Returns:
        UTF-8 bytes of a ``month,<columns>`` CSV in which every value is rendered
        with ten decimals and every missing observation is an empty field.
    """
    lines = ["month," + ",".join(str(column) for column in frame.columns)]
    for period, row in frame.iterrows():
        rendered = ",".join("" if pd.isna(value) else f"{float(value):.10f}" for value in row)
        lines.append(f"{period},{rendered}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def load_normalized_month_panel(path: Path) -> pd.DataFrame:
    """Load a canonical month-indexed panel written by :func:`canonical_monthly_bytes`.

    Args:
        path: Path to a normalized CSV whose first column is ``month``.

    Returns:
        The panel indexed by monthly periods and sorted by month, with float
        columns and an empty field decoded as a missing observation.
    """
    frame = pd.read_csv(path)
    index = pd.PeriodIndex([pd.Period(str(value), freq="M") for value in frame["month"]], freq="M")
    values = frame.drop(columns=["month"]).astype(float)
    values.index = index
    return values.sort_index()


def _default_interim_path(raw_path: Path) -> Path:
    parts = list(raw_path.parts)
    for index, part in enumerate(parts):
        if part == "raw" and index > 0 and parts[index - 1] == "data":
            parts[index] = "interim"
            return Path(*parts).with_suffix(".csv")
    return raw_path.with_name(f"{raw_path.stem}.interim.csv")


def _default_provenance_path(source_id: str) -> Path:
    return Path("artifacts") / "provenance" / f"{source_id}.json"


def _write_json(payload: DownloadRecord | ManualRegistrationRecord, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = asdict(payload)
    path.write_text(json.dumps(serializable, indent=2, sort_keys=True), encoding="utf-8")


def _require_nonempty_payload(payload: bytes) -> None:
    if not payload:
        raise DataAccessError("Downloaded payload is empty")


def _require_content_type(
    *,
    content_type: str,
    expected_content_types: tuple[str, ...],
) -> None:
    if not expected_content_types:
        return
    normalized = content_type.split(";", maxsplit=1)[0].strip().lower()
    allowed = {expected.lower() for expected in expected_content_types}
    if normalized not in allowed:
        raise DataAccessError(f"Unexpected content type {content_type!r}")


def _require_zip_payload(payload: bytes) -> None:
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise DataAccessError("Downloaded payload is not a valid ZIP archive")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [member for member in archive.infolist() if not member.is_dir()]
        if not members:
            raise DataAccessError("Downloaded ZIP archive contains no files")
        if all(member.file_size == 0 for member in members):
            raise DataAccessError("Downloaded ZIP archive contains only empty files")


def _write_immutable_raw_file(path: Path, payload: bytes) -> str:
    return write_raw_once(path, payload)


def _parse_fred_csv(payload: bytes, interim_path: Path) -> None:
    frame = pd.read_csv(io.BytesIO(payload))
    if frame.empty:
        raise DataValidationError("FRED CSV payload contains no rows")
    interim_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(interim_path, index=False)


def _parse_french_zip(payload: bytes, interim_path: Path) -> None:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.filename.lower().endswith((".csv", ".txt"))
        ]
        if not members:
            raise DataValidationError("Kenneth French ZIP contains no CSV or TXT member")
        extracted = archive.read(members[0])
    if not extracted.strip():
        raise DataValidationError("Kenneth French extracted member is empty")
    interim_path.parent.mkdir(parents=True, exist_ok=True)
    interim_path.write_bytes(extracted)


def download_http_source(
    *,
    source_id: str,
    url: str,
    provider: str,
    licence_note: str,
    raw_path: Path,
    interim_path: Path,
    provenance_path: Path,
    parser: str,
    expected_content_types: tuple[str, ...],
    expect_zip: bool = False,
    session: HTTPSession | None = None,
    timeout: float = 20.0,
    retries: int = 3,
) -> DownloadRecord:
    """Download a public source as immutable raw bytes and parse an interim copy."""
    client = session or _session_with_retries(retries)
    response = client.get(url, timeout=timeout)
    if response.status_code != 200:
        raise DataAccessError(f"Unexpected HTTP status {response.status_code} for {url}")
    payload = response.content
    _require_nonempty_payload(payload)
    content_type = response.headers.get("Content-Type", "")
    _require_content_type(
        content_type=content_type,
        expected_content_types=expected_content_types,
    )
    if expect_zip:
        _require_zip_payload(payload)

    checksum = _write_immutable_raw_file(raw_path, payload)
    if parser == "fred_csv":
        _parse_fred_csv(payload, interim_path)
    elif parser == "kenneth_french_zip":
        _parse_french_zip(payload, interim_path)
    else:
        raise DataValidationError(f"Unsupported parser {parser!r}")

    record = DownloadRecord(
        source_id=source_id,
        url=url,
        provider=provider,
        licence_note=licence_note,
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        raw_path=str(raw_path),
        interim_path=str(interim_path),
        sha256=checksum,
        content_type=content_type,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
    )
    _write_json(record, provenance_path)
    return record


def download_fred_series(
    *,
    series_id: str,
    output_path: Path,
    interim_path: Path | None = None,
    provenance_path: Path | None = None,
    session: HTTPSession | None = None,
    timeout: float = 20.0,
    retries: int = 3,
) -> DownloadRecord:
    """Download one FRED series CSV as immutable raw bytes."""
    source_id = f"fred_{series_id.lower()}"
    return download_http_source(
        source_id=source_id,
        url=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
        provider="Federal Reserve Economic Data",
        licence_note="FRED public data; record series terms and vintage before analysis.",
        raw_path=output_path,
        interim_path=interim_path or _default_interim_path(output_path),
        provenance_path=provenance_path or _default_provenance_path(source_id),
        parser="fred_csv",
        expected_content_types=("text/csv", "text/plain", "application/octet-stream"),
        session=session,
        timeout=timeout,
        retries=retries,
    )


def download_kenneth_french_dataset(
    *,
    dataset_name: str,
    output_path: Path,
    interim_path: Path | None = None,
    provenance_path: Path | None = None,
    session: HTTPSession | None = None,
    timeout: float = 20.0,
    retries: int = 3,
) -> DownloadRecord:
    """Download one Kenneth French ZIP archive as immutable raw bytes."""
    source_id = f"kenneth_french_{dataset_name.lower()}"
    return download_http_source(
        source_id=source_id,
        url=f"https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{dataset_name}_CSV.zip",
        provider="Kenneth French Data Library",
        licence_note="Kenneth French public research data; retain exact archive bytes.",
        raw_path=output_path,
        interim_path=interim_path or _default_interim_path(output_path),
        provenance_path=provenance_path or _default_provenance_path(source_id),
        parser="kenneth_french_zip",
        expected_content_types=("application/zip", "application/x-zip-compressed"),
        expect_zip=True,
        session=session,
        timeout=timeout,
        retries=retries,
    )


def register_manual_source(
    *,
    source_id: str,
    file_path: Path,
    expected_columns: tuple[str, ...],
    redistribution_status: str,
    provenance_path: Path,
    date_column: str = "date",
    sample_start: str | None = None,
    sample_end: str | None = None,
) -> ManualRegistrationRecord:
    """Register a restricted or author-provided file without copying it."""
    if not file_path.is_file():
        raise DataAccessError(f"Manual source file does not exist: {file_path}")
    if redistribution_status not in {"restricted", "no_redistribution", "public"}:
        raise DataValidationError("redistribution_status must be explicit")

    frame = pd.read_csv(file_path)
    missing_columns = set(expected_columns) - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise DataValidationError(f"Manual source is missing expected columns: {missing}")
    if (sample_start is not None or sample_end is not None) and date_column not in frame.columns:
        raise DataValidationError(f"Manual source is missing date column {date_column!r}")

    observed_start: str | None = None
    observed_end: str | None = None
    if date_column in frame.columns:
        dates = pd.to_datetime(frame[date_column], errors="raise").dt.to_period("M")
        observed_start = str(dates.min())
        observed_end = str(dates.max())
    if sample_start is not None and observed_start != sample_start:
        raise DataValidationError(f"Expected sample start {sample_start}, found {observed_start}")
    if sample_end is not None and observed_end != sample_end:
        raise DataValidationError(f"Expected sample end {sample_end}, found {observed_end}")

    record = ManualRegistrationRecord(
        source_id=source_id,
        file_path=str(file_path),
        sha256=sha256_file(file_path),
        registered_at_utc=datetime.now(UTC).isoformat(),
        redistribution_status=redistribution_status,
        rows=len(frame),
        columns=tuple(str(column) for column in frame.columns),
        sample_start=observed_start,
        sample_end=observed_end,
    )
    _write_json(record, provenance_path)
    return record
