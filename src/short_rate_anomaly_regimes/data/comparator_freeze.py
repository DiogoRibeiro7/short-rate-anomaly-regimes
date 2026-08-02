"""Immutable acquisition of the non-French comparator factors.

Two sources are handled: the Hou-Xue-Zhang q-factor file, which the article
attributes to Lu Zhang, and the Pastor-Stambaugh liquidity file, which the
article attributes to Robert Stambaugh's web page. Both are frozen with the same
metadata discipline as every other input, and neither is substituted for the
other or for a French factor.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from short_rate_anomaly_regimes.data.acquisition import HTTPSession, _session_with_retries
from short_rate_anomaly_regimes.exceptions import DataAccessError, DataValidationError
from short_rate_anomaly_regimes.provenance import sha256_file

#: The q-factor host refuses the default requests user agent.
COMPARATOR_USER_AGENT = (
    "short-rate-anomaly-regimes/0.1 (academic replication; contact via repository)"
)

#: Pastor and Stambaugh publish an unavailable observation as this sentinel.
LIQUIDITY_MISSING_VALUE_CODE = -99.0

#: The q-factor file publishes no sentinel; absent months are omitted.
Q_FACTOR_MISSING_VALUE_CODE = "none; absent months are omitted rather than coded"

_LIQUIDITY_ROW = re.compile(r"^\s*(\d{6})\s+(\S+)\s+(\S+)\s+(\S+)\s*$")


@dataclass(frozen=True, slots=True)
class ComparatorFreezeRecord:
    """Complete freeze metadata for one comparator-factor file vintage."""

    dataset: str
    vintage_label: str
    archive_date: str
    file_name: str
    source_url: str
    provider: str
    attributed_by_article_to: str
    retrieved_at_utc: str
    raw_path: str
    normalized_path: str
    raw_sha256: str
    normalized_sha256: str
    columns: tuple[str, ...]
    monthly_start: str
    monthly_end: str
    monthly_observations: int
    units: str
    missing_value_code: str
    missing_value_count: int
    redistribution_status: str
    source_metadata_lines: tuple[str, ...]
    http_last_modified: str | None = None
    http_etag: str | None = None
    value_range: dict[str, float] = field(default_factory=dict)


def parse_q_factor_csv(payload: bytes) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Parse the q-factor monthly CSV into a month-period panel.

    Args:
        payload: Raw file bytes.

    Returns:
        The monthly frame and an empty descriptive-line tuple, since the file
        carries no header commentary.

    Raises:
        DataValidationError: If the year, month, or factor columns are missing.
    """
    frame = pd.read_csv(io.BytesIO(payload))
    required = {"year", "month"}
    missing = required - set(frame.columns)
    if missing:
        raise DataValidationError(f"q-factor file is missing columns: {sorted(missing)}")
    factor_columns = [column for column in frame.columns if column not in required]
    if not factor_columns:
        raise DataValidationError("q-factor file carries no factor columns")
    index = pd.PeriodIndex(
        [
            pd.Period(year=int(year), month=int(month), freq="M")
            for year, month in zip(frame["year"], frame["month"], strict=True)
        ],
        freq="M",
    )
    values = frame[factor_columns].astype(float)
    values.index = index
    values = values.sort_index()
    if values.index.has_duplicates:
        raise DataValidationError("q-factor file contains duplicate months")
    return values, ()


def parse_liquidity_text(payload: bytes) -> tuple[pd.DataFrame, tuple[str, ...]]:
    """Parse the Pastor-Stambaugh liquidity text file into a month-period panel.

    The file is a whitespace-separated table preceded by percent-prefixed
    commentary. The three data columns are the aggregate liquidity level, the
    innovation in aggregate liquidity, and the traded liquidity factor. The
    sentinel ``-99`` marks months in which the traded factor is undefined.

    Args:
        payload: Raw file bytes.

    Returns:
        The monthly frame and the descriptive commentary lines.

    Raises:
        DataValidationError: If no data rows are present.
    """
    text = payload.decode("latin-1")
    lines = text.splitlines()
    commentary = tuple(
        line.lstrip("%").strip() for line in lines if line.startswith("%") and line.strip("% \t")
    )
    records: list[tuple[str, float, float, float]] = []
    for line in lines:
        match = _LIQUIDITY_ROW.match(line)
        if not match:
            continue
        stamp, level, innovation, traded = match.groups()
        records.append((stamp, float(level), float(innovation), float(traded)))
    if not records:
        raise DataValidationError("Liquidity file contains no parsable data rows")
    index = pd.PeriodIndex([pd.Period(stamp, freq="M") for stamp, *_ in records], freq="M")
    frame = pd.DataFrame(
        [values for _, *values in records],
        index=index,
        columns=[
            "aggregate_liquidity_level",
            "liquidity_innovation_non_traded",
            "traded_liquidity_factor",
        ],
    ).sort_index()
    if frame.index.has_duplicates:
        raise DataValidationError("Liquidity file contains duplicate months")
    return frame.mask(frame == LIQUIDITY_MISSING_VALUE_CODE), commentary


def _canonical_monthly_bytes(frame: pd.DataFrame) -> bytes:
    lines = ["month," + ",".join(str(column) for column in frame.columns)]
    for period, row in frame.iterrows():
        rendered = ",".join("" if pd.isna(value) else f"{float(value):.10f}" for value in row)
        lines.append(f"{period},{rendered}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _write_raw_once(path: Path, payload: bytes) -> str:
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


def freeze_comparator_file(
    *,
    dataset: str,
    url: str,
    file_name: str,
    parser: str,
    provider: str,
    attributed_by_article_to: str,
    units: str,
    missing_value_code: str,
    redistribution_status: str,
    vintage_label: str,
    archive_date: str,
    raw_root: Path,
    normalized_root: Path,
    manifest_root: Path,
    session: HTTPSession | None = None,
    timeout: float = 120.0,
    retries: int = 3,
) -> ComparatorFreezeRecord:
    """Download one comparator-factor file and freeze it with complete metadata.

    Args:
        dataset: Short identifier for the factor family.
        url: Fully qualified download URL for this vintage.
        file_name: Provider file name recorded in the manifest.
        parser: ``q_factor_csv`` or ``liquidity_text``.
        provider: Publishing party.
        attributed_by_article_to: The party the article names as the source.
        units: Declared measurement units of the parsed columns.
        missing_value_code: Provider sentinel description.
        redistribution_status: Redistribution terms recorded with the file.
        vintage_label: Stable label recorded with every derived artifact.
        archive_date: ISO date identifying the vintage.
        raw_root: Directory receiving immutable raw bytes.
        normalized_root: Directory receiving the canonical monthly CSV.
        manifest_root: Directory receiving the freeze manifest JSON.
        session: Optional HTTP session for testing.
        timeout: Request timeout in seconds.
        retries: Retry budget for transient failures.

    Returns:
        The complete freeze record.

    Raises:
        DataAccessError: On a non-200 response, an empty payload, or an attempt to
            overwrite an existing raw file with different bytes.
        DataValidationError: When the parser is unknown or the payload is malformed.
    """
    client = session or _comparator_session(retries)
    response = client.get(url, timeout=timeout)
    if response.status_code != 200:
        raise DataAccessError(f"Unexpected HTTP status {response.status_code} for {url}")
    payload = response.content
    if not payload:
        raise DataAccessError(f"Empty payload for {url}")

    if parser == "q_factor_csv":
        frame, commentary = parse_q_factor_csv(payload)
    elif parser == "liquidity_text":
        frame, commentary = parse_liquidity_text(payload)
    else:
        raise DataValidationError(f"Unsupported comparator parser {parser!r}")

    suffix = Path(file_name).suffix or ".txt"
    raw_path = raw_root / dataset / f"{dataset}_{vintage_label}{suffix}"
    raw_sha = _write_raw_once(raw_path, payload)

    normalized_bytes = _canonical_monthly_bytes(frame)
    normalized_path = normalized_root / f"{dataset}_{vintage_label}.csv"
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_bytes(normalized_bytes)

    values = frame.to_numpy(dtype=float)
    record = ComparatorFreezeRecord(
        dataset=dataset,
        vintage_label=vintage_label,
        archive_date=archive_date,
        file_name=file_name,
        source_url=url,
        provider=provider,
        attributed_by_article_to=attributed_by_article_to,
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        raw_path=raw_path.as_posix(),
        normalized_path=normalized_path.as_posix(),
        raw_sha256=raw_sha,
        normalized_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        columns=tuple(str(column) for column in frame.columns),
        monthly_start=str(frame.index[0]),
        monthly_end=str(frame.index[-1]),
        monthly_observations=len(frame),
        units=units,
        missing_value_code=missing_value_code,
        missing_value_count=int(frame.isna().to_numpy().sum()),
        redistribution_status=redistribution_status,
        source_metadata_lines=commentary,
        http_last_modified=response.headers.get("Last-Modified"),
        http_etag=response.headers.get("ETag"),
        value_range={
            "minimum": float(np.nanmin(values)),
            "maximum": float(np.nanmax(values)),
        },
    )
    manifest_root.mkdir(parents=True, exist_ok=True)
    (manifest_root / f"{dataset}_{vintage_label}.json").write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def _comparator_session(retries: int) -> requests.Session:
    """Build a session whose user agent the comparator hosts accept."""
    session = _session_with_retries(retries)
    session.headers.update({"User-Agent": COMPARATOR_USER_AGENT})
    return session


def load_normalized_comparator(path: Path) -> pd.DataFrame:
    """Load a normalized comparator panel indexed by month period."""
    frame = pd.read_csv(path)
    index = pd.PeriodIndex([pd.Period(str(value), freq="M") for value in frame["month"]], freq="M")
    values = frame.drop(columns=["month"]).astype(float)
    values.index = index
    return values.sort_index()
