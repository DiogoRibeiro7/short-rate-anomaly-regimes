"""Structured run metadata and log-record helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from short_rate_anomaly_regimes.environment import git_commit
from short_rate_anomaly_regimes.provenance import sha256_file


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Metadata attached to structured run logs."""

    run_id: str
    config_checksum: str
    git_commit: str
    created_at_utc: str


def create_run_metadata(
    *,
    config_path: Path,
    run_id: str | None = None,
    cwd: Path = Path("."),
) -> RunMetadata:
    """Create deterministic-context metadata for one pipeline run."""
    return RunMetadata(
        run_id=run_id or uuid4().hex,
        config_checksum=sha256_file(config_path),
        git_commit=git_commit(cwd),
        created_at_utc=datetime.now(UTC).isoformat(),
    )


def structured_log_record(
    *,
    level: str,
    message: str,
    metadata: RunMetadata,
) -> dict[str, str]:
    """Return one JSON-serializable structured log record."""
    return {
        "level": level,
        "message": message,
        **asdict(metadata),
        "timestamp_utc": datetime.now(UTC).isoformat(),
    }
