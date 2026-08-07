from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pytest

from short_rate_anomaly_regimes.provenance import create_record, sha256_file, write_record

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PROVENANCE_ROOT = REPOSITORY_ROOT / "artifacts" / "provenance"


def test_sha256_file_hashes_binary_content(tmp_path: Path) -> None:
    output = tmp_path / "artifact.csv"
    output.write_bytes(b"abc")

    assert sha256_file(output) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_create_and_write_provenance_record(tmp_path: Path) -> None:
    input_path = tmp_path / "raw.csv"
    output_path = tmp_path / "processed.csv"
    record_path = tmp_path / "provenance" / "processed.json"
    input_path.write_text("date,value\n2020-01-31,1\n", encoding="utf-8")
    output_path.write_text("date,value\n2020-01-31,2\n", encoding="utf-8")

    record = create_record(
        source_id="test_source",
        input_paths=(input_path,),
        output_path=output_path,
        parameters={"scale": 2},
        code_version="abc123",
    )
    write_record(record, record_path)

    payload = json.loads(record_path.read_text(encoding="utf-8"))
    assert payload["source_id"] == "test_source"
    assert payload["input_paths"] == [str(input_path)]
    assert payload["output_path"] == str(output_path)
    assert payload["parameters"] == {"scale": 2}
    assert payload["code_version"] == "abc123"
    assert payload["sha256"] == sha256_file(output_path)
    assert datetime.fromisoformat(payload["created_at_utc"]).tzinfo is not None


def test_create_record_requires_existing_output(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        create_record(
            source_id="missing",
            input_paths=(),
            output_path=tmp_path / "missing.csv",
            parameters={},
            code_version="abc123",
        )


def _recorded_outputs(payload: object) -> Iterator[tuple[str, str]]:
    """Yield ``(relative_path, sha256)`` pairs from a record's ``outputs`` entry.

    Two shapes are in use across the committed records: a mapping of path to
    digest, and a list of ``{"path": ..., "sha256": ...}`` records. Both state the
    same claim, so both are checked rather than only the shape that happens to be
    more common.
    """
    if not isinstance(payload, dict):
        return
    outputs = payload.get("outputs")
    if isinstance(outputs, dict):
        for path, digest in outputs.items():
            if isinstance(digest, str):
                yield path, digest
            elif isinstance(digest, dict) and isinstance(digest.get("sha256"), str):
                yield path, digest["sha256"]
    elif isinstance(outputs, list):
        for record in outputs:
            if isinstance(record, dict):
                path, digest = record.get("path"), record.get("sha256")
                if isinstance(path, str) and isinstance(digest, str):
                    yield path, digest


def _provenance_records() -> list[Path]:
    if not PROVENANCE_ROOT.is_dir():
        return []
    return sorted(path for path in PROVENANCE_ROOT.rglob("*.json"))


@pytest.mark.parametrize(
    "record_path",
    _provenance_records(),
    ids=lambda path: path.relative_to(PROVENANCE_ROOT).as_posix(),
)
def test_recorded_output_checksums_match_the_files_on_disk(record_path: Path) -> None:
    """Every digest a provenance record claims must be the digest of the artifact.

    This is the repository's central reproducibility claim, so it is asserted
    rather than assumed. It is also the guard against a whole class of silent
    drift: a writer that emits platform-native CRLF line endings hashes bytes that
    git then normalises to LF on commit, leaving a record that describes a file
    that was never committed. An artifact that is absent is skipped, because the
    inputs some scripts need are gitignored and are not present in CI.
    """
    payload = json.loads(record_path.read_text(encoding="utf-8"))
    recorded = list(_recorded_outputs(payload))
    if not recorded:
        pytest.skip(f"{record_path.name} records no output checksums")

    present = [(path, digest) for path, digest in recorded if (REPOSITORY_ROOT / path).is_file()]
    if not present:
        pytest.skip(f"none of the outputs of {record_path.name} are present on disk")

    on_disk = {path: sha256_file(REPOSITORY_ROOT / path) for path, _ in present}
    mismatched = {
        path: {"recorded": digest, "on_disk": on_disk[path]}
        for path, digest in present
        if on_disk[path] != digest
    }
    assert not mismatched, (
        f"{record_path.relative_to(REPOSITORY_ROOT).as_posix()} records checksums that no "
        f"longer describe the committed artifacts: {json.dumps(mismatched, indent=2)}"
    )
