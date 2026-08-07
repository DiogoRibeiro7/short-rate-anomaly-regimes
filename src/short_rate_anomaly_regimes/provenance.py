"""Data checksums and provenance records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """Immutable metadata for one acquisition or transformation step."""

    source_id: str
    input_paths: tuple[str, ...]
    output_path: str
    sha256: str
    created_at_utc: str
    parameters: dict[str, Any]
    code_version: str


def sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_record(
    *,
    source_id: str,
    input_paths: tuple[Path, ...],
    output_path: Path,
    parameters: dict[str, Any],
    code_version: str,
) -> ProvenanceRecord:
    """Create a provenance record for an existing output file."""
    if not output_path.is_file():
        raise FileNotFoundError(output_path)
    return ProvenanceRecord(
        source_id=source_id,
        input_paths=tuple(str(path) for path in input_paths),
        output_path=str(output_path),
        sha256=sha256_file(output_path),
        created_at_utc=datetime.now(UTC).isoformat(),
        parameters=parameters,
        code_version=code_version,
    )


def write_record(record: ProvenanceRecord, path: Path) -> None:
    """Write a provenance record as stable, sorted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(record), indent=2, sort_keys=True), encoding="utf-8", newline="\n"
    )
