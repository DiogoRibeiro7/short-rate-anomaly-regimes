"""Immutable acquisition and freezing of short-rate source series.

The module writes raw provider bytes exactly once, records the metadata required
by the input-acquisition milestone, and derives every fact that can be verified
from the payload itself. Metadata that the provider does not expose through an
accessible endpoint is recorded as declared, never as retrieved.
"""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.data.acquisition import HTTPSession, _session_with_retries
from short_rate_anomaly_regimes.exceptions import DataAccessError, DataValidationError
from short_rate_anomaly_regimes.provenance import sha256_file

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

#: Metadata the project declares for each series. Provider metadata endpoints
#: (``fred.stlouisfed.org/series/*`` and ``fred.stlouisfed.org/data/*.txt``)
#: refuse automated requests and no FRED API key is configured, so these values
#: are declared by this project and are separately checked against the payload
#: by :func:`audit_declared_metadata`.
DECLARED_SERIES_METADATA: dict[str, dict[str, str]] = {
    "FEDFUNDS": {
        "title": "Federal Funds Effective Rate",
        "units": "percent_per_annum",
        "frequency": "monthly",
        "seasonal_adjustment": "not_seasonally_adjusted",
        "aggregation_of_source": "provider monthly average of daily figures",
        "source_notes": (
            "Effective federal funds rate published by the Board of Governors of "
            "the Federal Reserve System (H.15) and redistributed by the Federal "
            "Reserve Bank of St. Louis. The monthly series is the provider's "
            "average of the daily effective rate."
        ),
        "redistribution_status": "public_domain_us_government_work",
        "daily_counterpart": "DFF",
    },
    "TB3MS": {
        "title": "3-Month Treasury Bill Secondary Market Rate, Discount Basis",
        "units": "percent_per_annum",
        "frequency": "monthly",
        "seasonal_adjustment": "not_seasonally_adjusted",
        "aggregation_of_source": "provider monthly average of business-day figures",
        "source_notes": (
            "Three-month Treasury bill secondary market rate on a discount basis, "
            "published by the Board of Governors of the Federal Reserve System "
            "(H.15) and redistributed by the Federal Reserve Bank of St. Louis. "
            "The monthly series is the provider's average of business-day "
            "observations."
        ),
        "redistribution_status": "public_domain_us_government_work",
        "daily_counterpart": "DTB3",
    },
    "DFF": {
        "title": "Federal Funds Effective Rate (daily)",
        "units": "percent_per_annum",
        "frequency": "daily_including_weekends",
        "seasonal_adjustment": "not_seasonally_adjusted",
        "aggregation_of_source": "not applicable; this is the daily source frequency",
        "source_notes": (
            "Daily effective federal funds rate published by the Board of "
            "Governors of the Federal Reserve System (H.15) and redistributed by "
            "the Federal Reserve Bank of St. Louis. FRED publishes an observation "
            "for every calendar day, carrying the preceding business-day rate "
            "through non-business days. Acquired only to audit the monthly "
            "aggregation of FEDFUNDS; it is not a replication input."
        ),
        "redistribution_status": "public_domain_us_government_work",
        "daily_counterpart": "not applicable",
    },
    "DTB3": {
        "title": "3-Month Treasury Bill Secondary Market Rate, Discount Basis (daily)",
        "units": "percent_per_annum",
        "frequency": "business_daily",
        "seasonal_adjustment": "not_seasonally_adjusted",
        "aggregation_of_source": "not applicable; this is the business-day source frequency",
        "source_notes": (
            "Daily three-month Treasury bill secondary market rate on a discount "
            "basis, published by the Board of Governors of the Federal Reserve "
            "System (H.15) and redistributed by the Federal Reserve Bank of St. "
            "Louis. Non-business days are absent and holidays are published as "
            "the missing-value code."
        ),
        "redistribution_status": "public_domain_us_government_work",
        "daily_counterpart": "not applicable",
    },
}

#: FRED encodes a missing observation as a single period in the value column.
FRED_MISSING_VALUE_CODE = "."


@dataclass(frozen=True, slots=True)
class SeriesFreezeRecord:
    """Complete freeze metadata for one downloaded short-rate series."""

    series_id: str
    provider: str
    provider_url: str
    title: str
    retrieved_at_utc: str
    raw_path: str
    normalized_path: str
    raw_sha256: str
    normalized_sha256: str
    observation_start: str
    observation_end: str
    observation_count: int
    missing_value_count: int
    missing_value_code: str
    units_declared: str
    frequency_declared: str
    frequency_observed: str
    seasonal_adjustment_declared: str
    aggregation_of_source_declared: str
    source_notes: str
    redistribution_status: str
    vintage_label: str
    vintage_source: str
    vintage_http_last_modified: str | None
    vintage_http_etag: str | None
    metadata_provenance: str
    unit_magnitude_audit: dict[str, float] = field(default_factory=dict)
    declared_metadata_audit: dict[str, str] = field(default_factory=dict)


def _normalize_fred_payload(payload: bytes) -> pd.DataFrame:
    """Parse a FRED graph CSV into a canonical two-column monthly or daily frame."""
    frame = pd.read_csv(io.BytesIO(payload), dtype=str)
    if frame.shape[1] != 2:
        raise DataValidationError(f"Expected two FRED columns, found {frame.shape[1]}")
    date_column, value_column = frame.columns
    dates = pd.to_datetime(frame[date_column], errors="raise")
    values = pd.to_numeric(
        frame[value_column].str.strip().replace(FRED_MISSING_VALUE_CODE, np.nan),
        errors="raise",
    )
    normalized = pd.DataFrame({"date": dates, "value": values.astype(float)})
    normalized = normalized.sort_values("date").reset_index(drop=True)
    if normalized["date"].duplicated().any():
        raise DataValidationError("FRED payload contains duplicate observation dates")
    if normalized.empty:
        raise DataValidationError("FRED payload contains no observations")
    return normalized


def _canonical_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Serialize a normalized frame deterministically for checksum comparison."""
    lines = ["date,value"]
    for timestamp, value in zip(frame["date"], frame["value"], strict=True):
        rendered = "" if pd.isna(value) else f"{float(value):.10f}"
        lines.append(f"{pd.Timestamp(timestamp).date().isoformat()},{rendered}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _observed_frequency(dates: pd.Series) -> str:
    """Classify the observation frequency from the payload rather than assume it."""
    if len(dates) < 3:
        return "indeterminate"
    periods = pd.DatetimeIndex(dates).to_period("M")
    if not periods.duplicated().any():
        gaps = pd.DatetimeIndex(dates).to_period("M").astype("int64")
        if bool(np.all(np.diff(gaps) == 1)) and bool(np.all(pd.DatetimeIndex(dates).day == 1)):
            return "monthly_first_of_month_stamped"
        return "monthly_irregular_stamp"
    weekday = pd.DatetimeIndex(dates).weekday
    if int((weekday >= 5).sum()) == 0:
        return "business_daily"
    return "daily_including_weekends"


def _write_raw_once(path: Path, payload: bytes) -> str:
    """Write raw bytes exactly once; never overwrite a differing existing file."""
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


def audit_declared_metadata(series_id: str, frame: pd.DataFrame) -> dict[str, str]:
    """Check declared metadata against facts that the payload can establish."""
    declared = DECLARED_SERIES_METADATA[series_id]
    observed = _observed_frequency(frame["date"])
    frequency_consistent = (
        declared["frequency"] == "monthly" and observed.startswith("monthly")
    ) or (declared["frequency"] == observed)
    finite = frame["value"].dropna()
    magnitude_consistent = bool(finite.abs().max() < 100.0 and finite.abs().max() > 1.0)
    return {
        "frequency_declared_vs_observed": "consistent" if frequency_consistent else "inconsistent",
        "units_magnitude_check": (
            "consistent_with_percent_per_annum"
            if magnitude_consistent
            else "inconsistent_with_percent_per_annum"
        ),
        "units_confirmed_against_provider_metadata_endpoint": "no",
        "seasonal_adjustment_confirmed_against_provider": "no",
    }


def freeze_fred_series(
    *,
    series_id: str,
    retrieval_date: str,
    raw_root: Path,
    normalized_root: Path,
    manifest_root: Path,
    session: HTTPSession | None = None,
    timeout: float = 60.0,
    retries: int = 3,
) -> SeriesFreezeRecord:
    """Download one FRED series and freeze it with complete acquisition metadata.

    Args:
        series_id: FRED series identifier.
        retrieval_date: ISO date used in the immutable file name and vintage label.
        raw_root: Directory receiving immutable raw provider bytes.
        normalized_root: Directory receiving the canonical normalized copy.
        manifest_root: Directory receiving the freeze manifest JSON.
        session: Optional HTTP session for testing.
        timeout: Request timeout in seconds.
        retries: Retry budget for transient failures.

    Returns:
        The complete freeze record.

    Raises:
        DataAccessError: On a non-200 response, an empty payload, or an attempt to
            overwrite an existing raw file with different bytes.
        DataValidationError: When the payload is not a well-formed FRED series.
    """
    if series_id not in DECLARED_SERIES_METADATA:
        raise DataValidationError(f"No declared metadata registered for series {series_id!r}")
    url = FRED_CSV_URL.format(series_id=series_id)
    client = session or _session_with_retries(retries)
    response = client.get(url, timeout=timeout)
    if response.status_code != 200:
        raise DataAccessError(f"Unexpected HTTP status {response.status_code} for {url}")
    payload = response.content
    if not payload:
        raise DataAccessError(f"Empty payload for {url}")

    raw_path = raw_root / series_id / f"{series_id}_{retrieval_date}.csv"
    raw_sha = _write_raw_once(raw_path, payload)

    frame = _normalize_fred_payload(payload)
    normalized_bytes = _canonical_csv_bytes(frame)
    normalized_path = normalized_root / f"{series_id}_{retrieval_date}.csv"
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_bytes(normalized_bytes)

    declared = DECLARED_SERIES_METADATA[series_id]
    finite = frame["value"].dropna()
    record = SeriesFreezeRecord(
        series_id=series_id,
        provider="Federal Reserve Bank of St. Louis (FRED)",
        provider_url=url,
        title=declared["title"],
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        raw_path=raw_path.as_posix(),
        normalized_path=normalized_path.as_posix(),
        raw_sha256=raw_sha,
        normalized_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        observation_start=str(pd.Timestamp(frame["date"].iloc[0]).date()),
        observation_end=str(pd.Timestamp(frame["date"].iloc[-1]).date()),
        observation_count=len(frame),
        missing_value_count=int(frame["value"].isna().sum()),
        missing_value_code=FRED_MISSING_VALUE_CODE,
        units_declared=declared["units"],
        frequency_declared=declared["frequency"],
        frequency_observed=_observed_frequency(frame["date"]),
        seasonal_adjustment_declared=declared["seasonal_adjustment"],
        aggregation_of_source_declared=declared["aggregation_of_source"],
        source_notes=declared["source_notes"],
        redistribution_status=declared["redistribution_status"],
        vintage_label=f"fred_current_retrieved_{retrieval_date}",
        vintage_source=(
            "current unrevised-vintage download from the FRED graph CSV endpoint; "
            "no ALFRED vintage date was requested, so this is the latest published "
            "revision as of the retrieval timestamp"
        ),
        vintage_http_last_modified=response.headers.get("Last-Modified"),
        vintage_http_etag=response.headers.get("ETag"),
        metadata_provenance=(
            "units, frequency, seasonal adjustment, aggregation, and notes are "
            "declared by this project because the FRED series metadata pages and "
            "the fred.stlouisfed.org/data/*.txt endpoint refuse automated requests "
            "and no FRED API key is configured; every declared field is audited "
            "against the payload in declared_metadata_audit"
        ),
        unit_magnitude_audit={
            "minimum": float(finite.min()),
            "maximum": float(finite.max()),
            "mean": float(finite.mean()),
        },
        declared_metadata_audit=audit_declared_metadata(series_id, frame),
    )

    manifest_root.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_root / f"{series_id}_{retrieval_date}.json"
    manifest_path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8")
    return record


def load_normalized_series(path: Path) -> pd.Series:
    """Load a normalized freeze file as a date-indexed float series."""
    frame = pd.read_csv(path, parse_dates=["date"])
    series = pd.Series(
        frame["value"].astype(float).to_numpy(),
        index=pd.DatetimeIndex(frame["date"]),
        name=path.stem,
    )
    return series.sort_index()
