import json
from datetime import datetime
from pathlib import Path

import pytest

from short_rate_anomaly_regimes.provenance import create_record, sha256_file, write_record


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
