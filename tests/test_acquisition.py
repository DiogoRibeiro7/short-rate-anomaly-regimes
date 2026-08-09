import io
import json
import zipfile
from pathlib import Path

import pytest

from short_rate_anomaly_regimes.data.acquisition import (
    _session_with_retries,
    download_fred_series,
    download_http_source,
    download_kenneth_french_dataset,
    register_manual_source,
)
from short_rate_anomaly_regimes.data.vintage import VintageMode
from short_rate_anomaly_regimes.exceptions import (
    DataAccessError,
    DataValidationError,
    FrozenVintageError,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content: bytes = b"date,value\n2020-01-31,1\n",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = headers or {"Content-Type": "text/csv", "ETag": "fixture-etag"}


class FakeSession:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requested_urls: list[str] = []

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        assert timeout > 0
        self.requested_urls.append(url)
        return self.response


def _zip_payload() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("fixture.csv", "header\n1\n")
    return buffer.getvalue()


def _zip_payload_with_file(name: str, content: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, content)
    return buffer.getvalue()


def test_retry_session_can_be_created() -> None:
    session = _session_with_retries(1)

    assert session.adapters["https://"] is not None


def test_download_fred_series_writes_raw_interim_and_provenance(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw" / "fedfunds.csv"
    interim_path = tmp_path / "interim" / "fedfunds.csv"
    provenance_path = tmp_path / "provenance" / "fedfunds.json"
    session = FakeSession(FakeResponse())

    record = download_fred_series(
        series_id="FEDFUNDS",
        output_path=raw_path,
        interim_path=interim_path,
        provenance_path=provenance_path,
        session=session,
        mode=VintageMode.UPDATE,
    )

    payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert raw_path.read_bytes() == b"date,value\n2020-01-31,1\n"
    assert interim_path.read_text(encoding="utf-8").startswith("date,value")
    assert record.sha256 == payload["sha256"]
    assert session.requested_urls == ["https://fred.stlouisfed.org/graph/fredgraph.csv?id=FEDFUNDS"]


def test_download_fred_series_uses_default_interim_and_provenance_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    raw_path = Path("data/raw/fred/fedfunds.csv")

    download_fred_series(
        series_id="FEDFUNDS",
        output_path=raw_path,
        session=FakeSession(FakeResponse()),
        mode=VintageMode.UPDATE,
    )

    assert Path("data/interim/fred/fedfunds.csv").is_file()
    assert Path("artifacts/provenance/fred_fedfunds.json").is_file()


def test_download_refuses_to_overwrite_nonidentical_raw_file(tmp_path: Path) -> None:
    """A verified download must not clobber a local raw file holding other bytes."""
    raw_path = tmp_path / "raw.csv"
    provenance_path = tmp_path / "provenance.json"
    payload = b"date,value\n2020-01-31,1\n"
    download_fred_series(
        series_id="FEDFUNDS",
        output_path=raw_path,
        interim_path=tmp_path / "interim.csv",
        provenance_path=provenance_path,
        session=FakeSession(FakeResponse(content=payload)),
        mode=VintageMode.UPDATE,
    )
    raw_path.write_bytes(b"existing")

    with pytest.raises(DataAccessError, match="Refusing to overwrite"):
        download_fred_series(
            series_id="FEDFUNDS",
            output_path=raw_path,
            interim_path=tmp_path / "interim.csv",
            provenance_path=provenance_path,
            session=FakeSession(FakeResponse(content=payload)),
        )


def test_download_allows_identical_raw_file(tmp_path: Path) -> None:
    raw_payload = b"date,value\n2020-01-31,1\n"
    raw_path = tmp_path / "raw.csv"
    provenance_path = tmp_path / "provenance.json"
    download_fred_series(
        series_id="FEDFUNDS",
        output_path=raw_path,
        interim_path=tmp_path / "interim.csv",
        provenance_path=provenance_path,
        session=FakeSession(FakeResponse(content=raw_payload)),
        mode=VintageMode.UPDATE,
    )
    recorded = json.loads(provenance_path.read_text(encoding="utf-8"))["sha256"]

    record = download_fred_series(
        series_id="FEDFUNDS",
        output_path=raw_path,
        interim_path=tmp_path / "interim.csv",
        provenance_path=provenance_path,
        session=FakeSession(FakeResponse(content=raw_payload)),
    )

    assert record.sha256 == recorded
    assert json.loads(provenance_path.read_text(encoding="utf-8"))["sha256"] == recorded


def test_registry_download_aborts_when_the_provider_revised_the_file(tmp_path: Path) -> None:
    """The registry-driven path verifies against the recorded hash like every other."""
    raw_path = tmp_path / "raw.csv"
    provenance_path = tmp_path / "provenance.json"
    download_fred_series(
        series_id="FEDFUNDS",
        output_path=raw_path,
        interim_path=tmp_path / "interim.csv",
        provenance_path=provenance_path,
        session=FakeSession(FakeResponse(content=b"date,value\n2020-01-31,1\n")),
        mode=VintageMode.UPDATE,
    )
    recorded = provenance_path.read_bytes()
    raw_path.unlink()

    with pytest.raises(FrozenVintageError) as raised:
        download_fred_series(
            series_id="FEDFUNDS",
            output_path=raw_path,
            interim_path=tmp_path / "interim.csv",
            provenance_path=provenance_path,
            session=FakeSession(FakeResponse(content=b"date,value\n2020-01-31,2\n")),
        )

    assert "fred_fedfunds" in str(raised.value)
    assert "--update-vintage" in str(raised.value)
    assert provenance_path.read_bytes() == recorded
    assert not raw_path.exists()


def test_download_rejects_bad_http_status_and_content_type(tmp_path: Path) -> None:
    with pytest.raises(DataAccessError, match="Unexpected HTTP status"):
        download_fred_series(
            series_id="FEDFUNDS",
            output_path=tmp_path / "raw.csv",
            session=FakeSession(FakeResponse(status_code=500)),
        )

    with pytest.raises(DataAccessError, match="Unexpected content type"):
        download_http_source(
            source_id="source",
            url="https://example.test/file.csv",
            provider="provider",
            licence_note="licence",
            raw_path=tmp_path / "raw.csv",
            interim_path=tmp_path / "interim.csv",
            provenance_path=tmp_path / "provenance.json",
            parser="fred_csv",
            expected_content_types=("text/csv",),
            session=FakeSession(FakeResponse(headers={"Content-Type": "text/html"})),
        )


def test_download_rejects_empty_payload_and_unsupported_parser(tmp_path: Path) -> None:
    with pytest.raises(DataAccessError, match="empty"):
        download_fred_series(
            series_id="FEDFUNDS",
            output_path=tmp_path / "raw.csv",
            session=FakeSession(FakeResponse(content=b"")),
            mode=VintageMode.UPDATE,
        )

    with pytest.raises(DataValidationError, match="Unsupported parser"):
        download_http_source(
            source_id="source",
            url="https://example.test/file.csv",
            provider="provider",
            licence_note="licence",
            raw_path=tmp_path / "raw.csv",
            interim_path=tmp_path / "interim.csv",
            provenance_path=tmp_path / "provenance.json",
            parser="unknown",
            expected_content_types=("text/csv",),
            session=FakeSession(FakeResponse()),
            mode=VintageMode.UPDATE,
        )


def test_download_rejects_empty_fred_csv(tmp_path: Path) -> None:
    with pytest.raises(DataValidationError, match="no rows"):
        download_fred_series(
            series_id="FEDFUNDS",
            output_path=tmp_path / "raw.csv",
            session=FakeSession(FakeResponse(content=b"date,value\n")),
            mode=VintageMode.UPDATE,
        )


def test_download_kenneth_french_dataset_validates_zip_structure(tmp_path: Path) -> None:
    raw_path = tmp_path / "raw.zip"
    interim_path = tmp_path / "interim.csv"
    provenance_path = tmp_path / "provenance.json"

    record = download_kenneth_french_dataset(
        dataset_name="F-F_Research_Data_Factors",
        output_path=raw_path,
        interim_path=interim_path,
        provenance_path=provenance_path,
        session=FakeSession(
            FakeResponse(
                content=_zip_payload(),
                headers={"Content-Type": "application/zip"},
            )
        ),
        mode=VintageMode.UPDATE,
    )

    assert raw_path.is_file()
    assert interim_path.read_text(encoding="utf-8") == "header\n1\n"
    assert record.provider == "Kenneth French Data Library"


def test_download_kenneth_french_dataset_rejects_invalid_zip(tmp_path: Path) -> None:
    with pytest.raises(DataAccessError, match="valid ZIP"):
        download_kenneth_french_dataset(
            dataset_name="bad",
            output_path=tmp_path / "raw.zip",
            session=FakeSession(
                FakeResponse(content=b"not zip", headers={"Content-Type": "application/zip"})
            ),
        )


def test_download_kenneth_french_dataset_rejects_zip_without_data_member(
    tmp_path: Path,
) -> None:
    with pytest.raises(DataValidationError, match="no CSV or TXT"):
        download_kenneth_french_dataset(
            dataset_name="bad",
            output_path=tmp_path / "raw.zip",
            session=FakeSession(
                FakeResponse(
                    content=_zip_payload_with_file("readme.md", "metadata"),
                    headers={"Content-Type": "application/zip"},
                )
            ),
            mode=VintageMode.UPDATE,
        )


def test_download_kenneth_french_dataset_rejects_empty_zip_member(
    tmp_path: Path,
) -> None:
    with pytest.raises(DataAccessError, match="only empty files"):
        download_kenneth_french_dataset(
            dataset_name="bad",
            output_path=tmp_path / "raw.zip",
            session=FakeSession(
                FakeResponse(
                    content=_zip_payload_with_file("fixture.csv", ""),
                    headers={"Content-Type": "application/zip"},
                )
            ),
        )


def test_register_manual_source_records_metadata_without_copying(tmp_path: Path) -> None:
    source_path = tmp_path / "restricted.csv"
    provenance_path = tmp_path / "provenance.json"
    source_path.write_text("date,asset\n2020-01-31,1\n2020-02-29,2\n", encoding="utf-8")

    record = register_manual_source(
        source_id="author_asset_growth",
        file_path=source_path,
        expected_columns=("date", "asset"),
        redistribution_status="restricted",
        provenance_path=provenance_path,
        sample_start="2020-01",
        sample_end="2020-02",
    )

    payload = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert record.file_path == str(source_path)
    assert payload["redistribution_status"] == "restricted"
    assert payload["sha256"]


def test_register_manual_source_rejects_missing_columns(tmp_path: Path) -> None:
    source_path = tmp_path / "restricted.csv"
    source_path.write_text("date,asset\n2020-01-31,1\n", encoding="utf-8")

    with pytest.raises(DataValidationError, match="missing expected columns"):
        register_manual_source(
            source_id="author_asset_growth",
            file_path=source_path,
            expected_columns=("date", "missing"),
            redistribution_status="restricted",
            provenance_path=tmp_path / "provenance.json",
        )


def test_register_manual_source_rejects_missing_file_status_and_sample(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "restricted.csv"
    source_path.write_text("date,asset\n2020-01-31,1\n", encoding="utf-8")

    with pytest.raises(DataAccessError, match="does not exist"):
        register_manual_source(
            source_id="missing",
            file_path=tmp_path / "missing.csv",
            expected_columns=(),
            redistribution_status="restricted",
            provenance_path=tmp_path / "provenance.json",
        )
    with pytest.raises(DataValidationError, match="redistribution_status"):
        register_manual_source(
            source_id="bad_status",
            file_path=source_path,
            expected_columns=(),
            redistribution_status="unknown",
            provenance_path=tmp_path / "provenance.json",
        )
    with pytest.raises(DataValidationError, match="Expected sample start"):
        register_manual_source(
            source_id="bad_sample",
            file_path=source_path,
            expected_columns=("date", "asset"),
            redistribution_status="restricted",
            provenance_path=tmp_path / "provenance.json",
            sample_start="2020-02",
        )
