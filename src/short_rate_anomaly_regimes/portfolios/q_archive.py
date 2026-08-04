"""Immutable acquisition of anomaly decile portfolios from the original author source.

The seven baseline anomaly families are attributed by the article to Lu Zhang.
The corresponding public archive is the Hou-Xue-Zhang testing-portfolio library.
This module freezes those archives and reshapes each family into a wide monthly
decile panel without substituting any other portfolio catalogue.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

from short_rate_anomaly_regimes.data.acquisition import (
    HTTPSession,
    _session_with_retries,
    canonical_monthly_bytes,
    load_normalized_month_panel,
    write_raw_once,
)
from short_rate_anomaly_regimes.exceptions import DataAccessError, DataValidationError

Q_ARCHIVE_BASE_URL = "https://global-q.org/uploads/1/2/2/6/122679606"

#: The archive host refuses the default requests user agent with HTTP 400.
Q_ARCHIVE_USER_AGENT = (
    "short-rate-anomaly-regimes/0.1 (academic replication; contact via repository)"
)

#: Mapping from the article's anomaly family to the archive member that carries
#: it. Every entry is the original author source named by the article, not a
#: substitute drawn from another provider.
FAMILY_MEMBERS: dict[str, dict[str, str]] = {
    "book_to_market": {
        "archive": "vvg_monthly_2025",
        "member": "portf_bm_monthly_2025.csv",
        "rank_column": "rank_BM",
        "article_label": "BM",
        "article_definition": "value-weighted deciles sorted on the book-to-market ratio",
    },
    "earnings_to_price": {
        "archive": "vvg_monthly_2025",
        "member": "portf_ep_monthly_2025.csv",
        "rank_column": "rank_EP",
        "article_label": "EP",
        "article_definition": "value-weighted deciles sorted on the earnings-to-price ratio",
    },
    "equity_duration": {
        "archive": "vvg_monthly_2025",
        "member": "portf_dur_monthly_2025.csv",
        "rank_column": "rank_Dur",
        "article_label": "DUR",
        "article_definition": "value-weighted deciles sorted on equity duration",
    },
    "long_term_reversal": {
        "archive": "vvg_monthly_2025",
        "member": "portf_rev_1_monthly_2025.csv",
        "rank_column": "rank_Rev_1",
        "article_label": "REV",
        "article_definition": "value-weighted deciles sorted on long-term prior returns",
    },
    "investment_to_assets": {
        "archive": "inv_monthly_2025",
        "member": "portf_ia_monthly_2025.csv",
        "rank_column": "rank_IA",
        "article_label": "IA",
        "article_definition": "value-weighted deciles sorted on the investment-to-assets ratio",
    },
    "ppe_investment": {
        "archive": "inv_monthly_2025",
        "member": "portf_dpia_monthly_2025.csv",
        "rank_column": "rank_dPIA",
        "article_label": "PIA",
        "article_definition": (
            "value-weighted deciles sorted on changes in property, plant, and "
            "equipment plus changes in inventory scaled by assets"
        ),
    },
    "inventory_growth": {
        "archive": "inv_monthly_2025",
        "member": "portf_ivg_monthly_2025.csv",
        "rank_column": "rank_IVG",
        "article_label": "IVG",
        "article_definition": "value-weighted deciles sorted on inventory growth",
    },
}

#: Declared alternatives for families whose article definition does not pin a
#: single archive member. They are registered before estimation and are never
#: selected after inspecting a pricing result.
DECLARED_FAMILY_ALTERNATIVES: dict[str, tuple[str, ...]] = {
    "long_term_reversal": (
        "portf_rev_6_monthly_2025.csv",
        "portf_rev_12_monthly_2025.csv",
    ),
}

#: Supplement-only families outside the seven baseline anomalies.
SUPPLEMENT_MEMBERS: dict[str, dict[str, str]] = {
    "cash_flow_to_price": {
        "archive": "vvg_monthly_2025",
        "member": "portf_cp_monthly_2025.csv",
        "rank_column": "rank_CP",
        "article_label": "CFP",
        "article_definition": "deciles sorted on the cash-flow-to-price ratio",
    },
    "investment_growth": {
        "archive": "inv_monthly_2025",
        "member": "portf_ig_monthly_2025.csv",
        "rank_column": "rank_IG",
        "article_label": "IG",
        "article_definition": "deciles sorted on investment growth",
    },
}


def _q_session(retries: int) -> requests.Session:
    """Build a session whose user agent the archive host accepts."""
    session = _session_with_retries(retries)
    # The host rejects the default requests user agent with HTTP 400.
    session.headers.update({"User-Agent": Q_ARCHIVE_USER_AGENT})
    return session


@dataclass(frozen=True, slots=True)
class QArchiveRecord:
    """Freeze metadata for one downloaded Hou-Xue-Zhang testing-portfolio archive."""

    archive: str
    source_url: str
    provider: str
    vintage_label: str
    retrieved_at_utc: str
    raw_path: str
    raw_sha256: str
    member_count: int
    redistribution_status: str
    http_last_modified: str | None = None
    http_etag: str | None = None


@dataclass(frozen=True, slots=True)
class FamilyPanelRecord:
    """Freeze metadata for one reshaped anomaly-family decile panel."""

    family: str
    article_label: str
    article_definition: str
    archive: str
    member: str
    member_sha256: str
    normalized_path: str
    normalized_sha256: str
    weighting: str
    number_of_portfolios: int
    sample_start: str
    sample_end: str
    monthly_observations: int
    return_units: str
    missing_value_count: int
    missing_value_codes: str
    continuous_months: bool
    minimum_stocks_per_portfolio: int
    value_range: dict[str, float] = field(default_factory=dict)


def freeze_q_archive(
    *,
    archive: str,
    vintage_label: str,
    raw_root: Path,
    manifest_root: Path,
    session: HTTPSession | None = None,
    timeout: float = 180.0,
    retries: int = 3,
) -> tuple[QArchiveRecord, bytes]:
    """Download one testing-portfolio archive and write its immutable raw bytes.

    Args:
        archive: Archive base name without the ``.zip`` suffix.
        vintage_label: Stable label recorded with every derived artifact.
        raw_root: Directory receiving immutable raw ZIP bytes.
        manifest_root: Directory receiving the archive manifest JSON.
        session: Optional HTTP session for testing.
        timeout: Request timeout in seconds.
        retries: Retry budget for transient failures.

    Returns:
        The archive record and the raw payload.

    Raises:
        DataAccessError: On a non-200 response, an empty or non-ZIP payload, or an
            attempt to overwrite an existing raw file with different bytes.
        DataValidationError: When the archive carries no member or only empty
            members. The archive is inspected before any raw file is written, so a
            hollow payload is neither recorded as a successful freeze nor left
            occupying the immutable path.
    """
    url = f"{Q_ARCHIVE_BASE_URL}/{archive}.zip"
    client = session or _q_session(retries)
    response = client.get(url, timeout=timeout)
    if response.status_code != 200:
        raise DataAccessError(f"Unexpected HTTP status {response.status_code} for {url}")
    payload = response.content
    if not payload:
        raise DataAccessError(f"Empty payload for {url}")
    if not zipfile.is_zipfile(io.BytesIO(payload)):
        raise DataAccessError(f"Payload for {url} is not a ZIP archive")

    with zipfile.ZipFile(io.BytesIO(payload)) as handle:
        members = [item for item in handle.infolist() if not item.is_dir()]
    if not members:
        raise DataValidationError(f"Archive {archive} contains no files")
    if all(member.file_size == 0 for member in members):
        raise DataValidationError(f"Archive {archive} contains only empty files")
    member_count = len(members)

    raw_path = raw_root / f"{archive}_{vintage_label}.zip"
    raw_sha = write_raw_once(raw_path, payload)

    record = QArchiveRecord(
        archive=archive,
        source_url=url,
        provider="Hou, Xue, and Zhang testing-portfolio library (global-q.org)",
        vintage_label=vintage_label,
        retrieved_at_utc=datetime.now(UTC).isoformat(),
        raw_path=raw_path.as_posix(),
        raw_sha256=raw_sha,
        member_count=member_count,
        redistribution_status=(
            "public author-provided research data; the page states no registration "
            "or licensing condition. Raw archive bytes are retained locally and are "
            "not redistributed by this repository."
        ),
        http_last_modified=response.headers.get("Last-Modified"),
        http_etag=response.headers.get("ETag"),
    )
    manifest_root.mkdir(parents=True, exist_ok=True)
    (manifest_root / f"{archive}_{vintage_label}.json").write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8"
    )
    return record, payload


def reshape_family_panel(
    payload: bytes,
    *,
    archive: str,
    member: str,
    rank_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Reshape one long-format archive member into a wide monthly decile panel.

    Args:
        payload: Raw ZIP bytes containing the member.
        archive: Archive base name, used to build the member path.
        member: Member file name inside the archive.
        rank_column: Name of the decile-rank column in the member.

    Returns:
        The wide return panel, the matching stock-count panel, and the member
        SHA-256.

    Raises:
        DataValidationError: If the member is missing or malformed.
    """
    with zipfile.ZipFile(io.BytesIO(payload)) as handle:
        path = f"{archive}/{member}"
        if path not in handle.namelist():
            raise DataValidationError(f"Archive {archive} has no member {member}")
        member_bytes = handle.read(path)
    frame = pd.read_csv(io.BytesIO(member_bytes))
    required = {"year", "month", rank_column, "nstocks", "ret_vw"}
    missing = required - set(frame.columns)
    if missing:
        raise DataValidationError(f"Member {member} is missing columns: {sorted(missing)}")

    frame["period"] = pd.PeriodIndex(
        [
            pd.Period(year=int(y), month=int(m), freq="M")
            for y, m in zip(frame["year"], frame["month"], strict=True)
        ],
        freq="M",
    )
    returns = frame.pivot(index="period", columns=rank_column, values="ret_vw").sort_index()
    counts = frame.pivot(index="period", columns=rank_column, values="nstocks").sort_index()
    returns.columns = [f"decile_{int(rank):02d}" for rank in returns.columns]
    counts.columns = [f"decile_{int(rank):02d}" for rank in counts.columns]
    returns.index.name = "month"
    counts.index.name = "month"
    return returns, counts, hashlib.sha256(member_bytes).hexdigest()


def freeze_family_panel(
    payload: bytes,
    *,
    family: str,
    specification: dict[str, str],
    normalized_root: Path,
    manifest_root: Path,
    vintage_label: str,
) -> FamilyPanelRecord:
    """Reshape and freeze one anomaly-family decile panel with full metadata."""
    returns, counts, member_sha = reshape_family_panel(
        payload,
        archive=specification["archive"],
        member=specification["member"],
        rank_column=specification["rank_column"],
    )
    normalized_bytes = canonical_monthly_bytes(returns)
    normalized_path = normalized_root / f"{family}_{vintage_label}.csv"
    normalized_path.parent.mkdir(parents=True, exist_ok=True)
    normalized_path.write_bytes(normalized_bytes)

    expected = pd.period_range(returns.index[0], returns.index[-1], freq="M")
    record = FamilyPanelRecord(
        family=family,
        article_label=specification["article_label"],
        article_definition=specification["article_definition"],
        archive=specification["archive"],
        member=specification["member"],
        member_sha256=member_sha,
        normalized_path=normalized_path.as_posix(),
        normalized_sha256=hashlib.sha256(normalized_bytes).hexdigest(),
        weighting="value_weighted",
        number_of_portfolios=int(returns.shape[1]),
        sample_start=str(returns.index[0]),
        sample_end=str(returns.index[-1]),
        monthly_observations=len(returns),
        return_units="percent_per_month",
        missing_value_count=int(returns.isna().to_numpy().sum()),
        missing_value_codes=(
            "none observed; the archive omits absent months rather than coding them"
        ),
        continuous_months=bool(list(returns.index) == list(expected)),
        minimum_stocks_per_portfolio=int(counts.to_numpy().min()),
        value_range={
            "minimum": float(returns.to_numpy().min()),
            "maximum": float(returns.to_numpy().max()),
        },
    )
    manifest_root.mkdir(parents=True, exist_ok=True)
    (manifest_root / f"{family}_{vintage_label}.json").write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8"
    )
    return record


def load_family_panel(path: Path) -> pd.DataFrame:
    """Load a normalized decile panel indexed by month period.

    Args:
        path: Path to a normalized decile-panel CSV written by this module.

    Returns:
        The month-indexed float panel.
    """
    return load_normalized_month_panel(path)
