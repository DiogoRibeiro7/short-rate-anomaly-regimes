"""Tests for the immutable acquisition paths, using a mocked HTTP session."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import pytest

from short_rate_anomaly_regimes.data import comparator_freeze, french_freeze, short_rate_freeze
from short_rate_anomaly_regimes.data.acquisition import (
    canonical_monthly_bytes,
    load_normalized_month_panel,
    write_raw_once,
)
from short_rate_anomaly_regimes.data.comparator_freeze import (
    ComparatorFreezeRecord,
    freeze_comparator_file,
    load_normalized_comparator,
    parse_liquidity_text,
    parse_q_factor_csv,
)
from short_rate_anomaly_regimes.data.french_freeze import (
    FrenchFreezeRecord,
    compare_vintages,
    freeze_french_archive,
    load_normalized_french,
    parse_french_monthly_block,
)
from short_rate_anomaly_regimes.data.short_rate_freeze import (
    SeriesFreezeRecord,
    _canonical_csv_bytes,
    freeze_fred_series,
    load_normalized_series,
)
from short_rate_anomaly_regimes.data.vintage import (
    VintageMode,
)
from short_rate_anomaly_regimes.exceptions import (
    DataAccessError,
    DataValidationError,
    FrozenVintageError,
)
from short_rate_anomaly_regimes.portfolios import q_archive
from short_rate_anomaly_regimes.portfolios.q_archive import (
    freeze_family_panel,
    freeze_q_archive,
    load_family_panel,
    reshape_family_panel,
)


@dataclass
class FakeResponse:
    """Minimal stand-in for a ``requests`` response."""

    content: bytes
    status_code: int = 200
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class FakeSession:
    """Session that returns one canned payload and records the requested URL."""

    response: FakeResponse
    requested: list[str] = field(default_factory=list)

    def get(self, url: str, *, timeout: float) -> FakeResponse:
        """Return the canned response."""
        assert timeout > 0
        self.requested.append(url)
        return self.response


FRED_PAYLOAD = (
    b"observation_date,FEDFUNDS\n"
    b"1972-01-01,3.50\n1972-02-01,3.29\n1972-03-01,3.83\n1972-04-01,4.17\n"
    b"1972-05-01,4.27\n1972-06-01,4.46\n1972-07-01,4.55\n1972-08-01,4.80\n"
)

FRENCH_TEXT = (
    "This file was created by CMPT_ME_BEME_RETS using the 202606 CRSP database.\n"
    "The 1-month TBill return is from Ibbotson and Associates, Inc.\n"
    "\n"
    ",Mkt-RF,SMB,HML,RF\n"
    "197201,  1.85, -0.20,  0.30,  0.29\n"
    "197202,  2.90,  0.50, -0.10,  0.25\n"
    "197203,  0.55, -1.10,  0.44,  0.27\n"
    "197204, -0.35,  0.10, -99.99,  0.29\n"
    "\n"
    "  Annual Factors: January-December\n"
    "\n"
    ",Mkt-RF,SMB,HML,RF\n"
    "1972, 15.00,  1.00,  2.00,  3.50\n"
)

Q_MEMBER_TEXT = (
    "year,month,rank_BM,nstocks,ret_vw\n"
    "1972,1,1,100,1.10\n1972,1,2,110,2.20\n"
    "1972,2,1,101,-0.50\n1972,2,2,111,0.75\n"
)


def _zip_bytes(members: dict[str, str]) -> bytes:
    """Build a byte-identical ZIP for the same members on every call.

    ``ZipFile.writestr`` stamps the local clock into each member by default, so
    two calls a second apart produce different bytes. These tests compare frozen
    checksums, and a fixture whose bytes depend on when it was built cannot
    stand in for a frozen vintage.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), text)
    return buffer.getvalue()


class TestFredFreeze:
    """FRED acquisition must be immutable and fully described."""

    def _freeze(
        self,
        tmp_path: Path,
        payload: bytes = FRED_PAYLOAD,
        mode: VintageMode = VintageMode.UPDATE,
    ) -> SeriesFreezeRecord:
        session = FakeSession(
            FakeResponse(payload, headers={"Last-Modified": "Sat, 01 Aug 2026 00:00:00 GMT"})
        )
        return freeze_fred_series(
            series_id="FEDFUNDS",
            retrieval_date="2026-08-01",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=session,
            mode=mode,
        )

    def test_freeze_records_every_required_field(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path)
        assert record.series_id == "FEDFUNDS"
        assert record.provider.startswith("Federal Reserve Bank of St. Louis")
        assert record.observation_start == "1972-01-01"
        assert record.observation_end == "1972-08-01"
        assert record.observation_count == 8
        assert record.missing_value_count == 0
        assert record.missing_value_code == "."
        assert record.units_declared == "percent_per_annum"
        assert record.frequency_declared == "monthly"
        assert record.frequency_observed.startswith("monthly")
        assert record.raw_sha256 == hashlib.sha256(FRED_PAYLOAD).hexdigest()
        assert record.normalized_sha256 != record.raw_sha256
        assert record.vintage_label == "fred_current_retrieved_2026-08-01"
        assert record.vintage_http_last_modified is not None
        assert record.redistribution_status == "public_domain_us_government_work"
        assert record.declared_metadata_audit["frequency_declared_vs_observed"] == "consistent"

    def test_manifest_is_written_and_reloadable(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path)
        manifest = json.loads(
            (tmp_path / "manifest" / "FEDFUNDS_2026-08-01.json").read_text(encoding="utf-8")
        )
        assert manifest["raw_sha256"] == record.raw_sha256
        assert manifest["metadata_provenance"].startswith("units, frequency")
        series = load_normalized_series(Path(record.normalized_path))
        assert len(series) == 8
        assert series.iloc[0] == pytest.approx(3.50)

    def test_reretrieving_identical_bytes_is_allowed(self, tmp_path: Path) -> None:
        first = self._freeze(tmp_path)
        second = self._freeze(tmp_path)
        assert first.raw_sha256 == second.raw_sha256

    def test_a_revised_series_aborts_the_verification_run(self, tmp_path: Path) -> None:
        """A FRED revision must stop the rebuild, not silently redefine the vintage.

        This is the fresh-clone case the reviewer named: the provenance manifest
        travels in the archive but ``data/raw`` does not, so the download is the
        only evidence available and it must be checked against the recorded hash.
        """
        frozen = self._freeze(tmp_path)
        manifest = tmp_path / "manifest" / "FEDFUNDS_2026-08-01.json"
        before = manifest.read_bytes()
        raw = tmp_path / "raw" / "FEDFUNDS" / "FEDFUNDS_2026-08-01.csv"
        raw.unlink()
        revised = FRED_PAYLOAD + b"1972-09-01,4.87\n"

        with pytest.raises(FrozenVintageError) as raised:
            self._freeze(tmp_path, payload=revised, mode=VintageMode.VERIFY)

        message = str(raised.value)
        assert "FRED series FEDFUNDS at vintage 2026-08-01" in message
        assert frozen.raw_sha256 in message
        assert hashlib.sha256(revised).hexdigest() in message
        assert "make update-vintage-short-rates" in message
        # The committed manifest is untouched and no raw file was written.
        assert manifest.read_bytes() == before
        assert not raw.exists()

    def test_an_unrevised_series_verifies_without_rewriting_the_manifest(
        self, tmp_path: Path
    ) -> None:
        """The match path: identical bytes verify, and the shipped manifest is left alone."""
        self._freeze(tmp_path)
        manifest = tmp_path / "manifest" / "FEDFUNDS_2026-08-01.json"
        raw = tmp_path / "raw" / "FEDFUNDS" / "FEDFUNDS_2026-08-01.csv"
        before = manifest.read_bytes()
        raw.unlink()

        record = self._freeze(tmp_path, mode=VintageMode.VERIFY)

        assert record.raw_sha256 == hashlib.sha256(FRED_PAYLOAD).hexdigest()
        assert raw.read_bytes() == FRED_PAYLOAD
        assert manifest.read_bytes() == before
        assert Path(record.normalized_path).is_file()

    def test_a_manifest_without_a_recorded_hash_cannot_be_created_by_verifying(
        self, tmp_path: Path
    ) -> None:
        """A verification run may not establish a vintage it has nothing to check."""
        with pytest.raises(FrozenVintageError) as raised:
            self._freeze(tmp_path, mode=VintageMode.VERIFY)

        message = str(raised.value)
        assert "No frozen-vintage hash is recorded" in message
        assert "make update-vintage-short-rates" in message
        assert not (tmp_path / "manifest").exists()
        assert not (tmp_path / "raw").exists()

    def test_a_matching_local_raw_file_makes_the_run_offline(self, tmp_path: Path) -> None:
        """Once the frozen bytes are on disk the provider is never contacted."""
        self._freeze(tmp_path)
        session = FakeSession(FakeResponse(b"this payload must never be requested"))

        record = freeze_fred_series(
            series_id="FEDFUNDS",
            retrieval_date="2026-08-01",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=session,
        )

        assert session.requested == []
        assert record.raw_sha256 == hashlib.sha256(FRED_PAYLOAD).hexdigest()

    def test_non_200_status_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"", status_code=503))
        with pytest.raises(DataAccessError, match="Unexpected HTTP status"):
            freeze_fred_series(
                series_id="FEDFUNDS",
                retrieval_date="2026-08-01",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_empty_payload_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b""))
        with pytest.raises(DataAccessError, match="Empty payload"):
            freeze_fred_series(
                series_id="FEDFUNDS",
                retrieval_date="2026-08-01",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_unregistered_series_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataValidationError, match="No declared metadata"):
            freeze_fred_series(
                series_id="NOT_A_SERIES",
                retrieval_date="2026-08-01",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(FRED_PAYLOAD)),
                mode=VintageMode.UPDATE,
            )

    def test_wrong_column_count_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"a,b,c\n1972-01-01,1,2\n"))
        with pytest.raises(DataValidationError, match="Expected two FRED columns"):
            freeze_fred_series(
                series_id="FEDFUNDS",
                retrieval_date="2026-08-01",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_payload_for_another_series_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"observation_date,TB3MS\n1972-01-01,3.50\n"))
        with pytest.raises(DataValidationError, match="carries series 'TB3MS'"):
            freeze_fred_series(
                series_id="FEDFUNDS",
                retrieval_date="2026-08-01",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )
        assert not (tmp_path / "raw").exists()

    def test_legacy_date_header_is_accepted(self, tmp_path: Path) -> None:
        payload = b"DATE,FEDFUNDS\n1972-01-01,3.50\n1972-02-01,3.29\n1972-03-01,3.83\n"
        record = self._freeze(tmp_path, payload=payload)
        assert record.observation_count == 3

    def test_payload_without_a_finite_observation_is_rejected(self, tmp_path: Path) -> None:
        payload = b"observation_date,FEDFUNDS\n1972-01-01,.\n1972-02-01,.\n"
        session = FakeSession(FakeResponse(payload))
        with pytest.raises(DataValidationError, match="no finite observation"):
            freeze_fred_series(
                series_id="FEDFUNDS",
                retrieval_date="2026-08-01",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )
        assert not (tmp_path / "raw").exists()

    def test_malformed_payload_leaves_the_raw_path_free_for_a_retry(self, tmp_path: Path) -> None:
        raw_path = tmp_path / "raw" / "FEDFUNDS" / "FEDFUNDS_2026-08-01.csv"
        with pytest.raises(DataValidationError):
            self._freeze(tmp_path, payload=b"observation_date,FEDFUNDS\n1972-01-01,.\n")
        assert not raw_path.exists()
        assert not (tmp_path / "manifest").exists()

        record = self._freeze(tmp_path)
        assert raw_path.read_bytes() == FRED_PAYLOAD
        assert record.raw_sha256 == hashlib.sha256(FRED_PAYLOAD).hexdigest()

    def test_missing_values_are_counted(self, tmp_path: Path) -> None:
        payload = b"observation_date,DTB3\n1972-01-03,3.50\n1972-01-04,.\n1972-01-05,3.60\n"
        session = FakeSession(FakeResponse(payload))
        record = freeze_fred_series(
            series_id="DTB3",
            retrieval_date="2026-08-01",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=session,
            mode=VintageMode.UPDATE,
        )
        assert record.missing_value_count == 1
        assert record.observation_count == 3


class TestFrenchFreeze:
    """French archives must be parsed, frozen, and comparable across vintages."""

    def _freeze(self, tmp_path: Path, label: str, text: str = FRENCH_TEXT) -> FrenchFreezeRecord:
        payload = _zip_bytes({"F-F_Research_Data_Factors.CSV": text})
        session = FakeSession(FakeResponse(payload, headers={"ETag": '"abc"'}))
        return freeze_french_archive(
            dataset="F-F_Research_Data_Factors",
            url="https://example.invalid/F-F_Research_Data_Factors_CSV.zip",
            vintage_label=label,
            archive_date="2017-07-09",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=session,
            mode=VintageMode.UPDATE,
        )

    def test_monthly_block_is_parsed_and_annual_block_is_ignored(self) -> None:
        frame, descriptive = parse_french_monthly_block(FRENCH_TEXT)
        assert list(frame.columns) == ["Mkt-RF", "SMB", "HML", "RF"]
        assert len(frame) == 4
        assert str(frame.index[0]) == "1972-01"
        assert bool(pd.isna(frame.at[pd.Period("1972-04", freq="M"), "HML"]))
        assert descriptive[0].startswith("This file was created")

    def test_missing_monthly_panel_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="No monthly YYYYMM rows"):
            parse_french_monthly_block("just a description line\n")

    def test_missing_header_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="No column header"):
            parse_french_monthly_block("197201, 1.0, 2.0\n")

    def test_freeze_records_required_metadata(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "publication_era")
        assert record.archive_date == "2017-07-09"
        assert record.file_name == "F-F_Research_Data_Factors_CSV.zip"
        assert record.units == "percent_per_month"
        assert record.missing_value_codes == (-99.99, -999.0)
        assert record.missing_value_count == 1
        assert record.monthly_start == "1972-01"
        assert record.monthly_end == "1972-04"
        assert record.columns == ("Mkt-RF", "SMB", "HML", "RF")
        assert record.source_metadata_lines
        assert record.http_etag == '"abc"'
        assert "not redistributed" in record.redistribution_status

    def test_non_zip_payload_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"not a zip"))
        with pytest.raises(DataAccessError, match="not a ZIP archive"):
            freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="v",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_empty_archive_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(_zip_bytes({})))
        with pytest.raises(DataValidationError, match="contains no files"):
            freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="v",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_non_200_status_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"x", status_code=404))
        with pytest.raises(DataAccessError, match="Unexpected HTTP status"):
            freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="v",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_identical_vintages_compare_as_identical(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "v1")
        frame = load_normalized_french(Path(record.normalized_path))
        summary, differences = compare_vintages(
            historical=frame,
            current=frame,
            dataset="F-F_Research_Data_Factors",
            historical_label="v1",
            current_label="v1",
        )
        assert set(summary["verdict"]) == {"identical_on_common_sample"}
        assert differences.empty

    def test_revised_vintage_is_detected_and_listed(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "v1")
        historical = load_normalized_french(Path(record.normalized_path))
        current = historical.copy()
        revised_month = pd.Period("1972-02", freq="M")
        market_column = current["Mkt-RF"].to_numpy(dtype=float).copy()
        market_column[list(current.index).index(revised_month)] += 0.50
        current["Mkt-RF"] = market_column
        summary, differences = compare_vintages(
            historical=historical,
            current=current,
            dataset="F-F_Research_Data_Factors",
            historical_label="v1",
            current_label="v2",
        )
        market = summary[summary["column"] == "Mkt-RF"].iloc[0]
        assert market["verdict"] == "revised_beyond_publication_rounding"
        assert market["months_beyond_tolerance"] == 1
        assert market["max_absolute_difference"] == pytest.approx(0.50)
        assert len(differences) == 1
        assert differences.iloc[0]["month"] == "1972-02"

    def test_added_observation_is_counted_and_cannot_read_as_identical(
        self, tmp_path: Path
    ) -> None:
        record = self._freeze(tmp_path, "v1")
        historical = load_normalized_french(Path(record.normalized_path))
        current = historical.copy()
        revised_month = pd.Period("1972-04", freq="M")
        current.loc[revised_month, "HML"] = 0.44
        summary, differences = compare_vintages(
            historical=historical,
            current=current,
            dataset="F-F_Research_Data_Factors",
            historical_label="v1",
            current_label="v2",
        )
        hml = summary[summary["column"] == "HML"].iloc[0]
        assert hml["verdict"] != "identical_on_common_sample"
        assert hml["verdict"] == "revised_observation_coverage_changed"
        assert hml["months_only_in_current"] == 1
        assert hml["months_only_in_historical"] == 0
        assert hml["months_with_changed_missingness"] == 1
        assert bool(hml["missingness_identical"]) is False
        assert hml["months_with_any_difference"] == 1
        assert hml["months_beyond_tolerance"] == 1
        assert hml["common_months"] == 3
        added = differences[differences["column"] == "HML"]
        assert len(added) == 1
        assert added.iloc[0]["change_type"] == "observation_added_by_current"
        assert added.iloc[0]["month"] == "1972-04"

    def test_removed_observation_is_counted_as_a_difference(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "v1")
        historical = load_normalized_french(Path(record.normalized_path))
        current = historical.copy()
        current.loc[pd.Period("1972-02", freq="M"), "SMB"] = float("nan")
        summary, differences = compare_vintages(
            historical=historical,
            current=current,
            dataset="F-F_Research_Data_Factors",
            historical_label="v1",
            current_label="v2",
        )
        smb = summary[summary["column"] == "SMB"].iloc[0]
        assert smb["verdict"] == "revised_observation_coverage_changed"
        assert smb["months_only_in_historical"] == 1
        assert smb["months_only_in_current"] == 0
        assert smb["months_beyond_tolerance"] == 1
        assert smb["share_beyond_tolerance"] == pytest.approx(0.25)
        removed = differences[differences["column"] == "SMB"]
        assert len(removed) == 1
        assert removed.iloc[0]["change_type"] == "observation_removed_by_current"

    def test_columns_without_missingness_changes_stay_identical(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "v1")
        historical = load_normalized_french(Path(record.normalized_path))
        current = historical.copy()
        current.loc[pd.Period("1972-04", freq="M"), "HML"] = 0.44
        summary, _ = compare_vintages(
            historical=historical,
            current=current,
            dataset="F-F_Research_Data_Factors",
            historical_label="v1",
            current_label="v2",
        )
        untouched = summary[summary["column"] == "RF"].iloc[0]
        assert untouched["verdict"] == "identical_on_common_sample"
        assert untouched["months_with_changed_missingness"] == 0
        assert bool(untouched["missingness_identical"]) is True

    def test_value_revision_is_labelled_as_such(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "v1")
        historical = load_normalized_french(Path(record.normalized_path))
        current = historical.copy()
        revised = current["SMB"].to_numpy(dtype=float).copy()
        revised[list(current.index).index(pd.Period("1972-02", freq="M"))] += 0.50
        current["SMB"] = revised
        _, differences = compare_vintages(
            historical=historical,
            current=current,
            dataset="F-F_Research_Data_Factors",
            historical_label="v1",
            current_label="v2",
        )
        assert list(differences["change_type"]) == ["value_revision"]

    def test_malformed_member_leaves_the_raw_path_free_for_a_retry(self, tmp_path: Path) -> None:
        raw_path = tmp_path / "raw" / "F-F_Research_Data_Factors"
        raw_path = raw_path / "F-F_Research_Data_Factors_publication_era.zip"
        with pytest.raises(DataValidationError, match="No monthly YYYYMM rows"):
            self._freeze(tmp_path, "publication_era", text="truncated response\n")
        assert not raw_path.exists()
        assert not (tmp_path / "manifest").exists()

        record = self._freeze(tmp_path, "publication_era")
        assert raw_path.exists()
        assert record.raw_sha256 == hashlib.sha256(raw_path.read_bytes()).hexdigest()

    def test_empty_archive_leaves_the_raw_path_free_for_a_retry(self, tmp_path: Path) -> None:
        raw_path = tmp_path / "raw" / "F-F_Research_Data_Factors"
        raw_path = raw_path / "F-F_Research_Data_Factors_publication_era.zip"
        with pytest.raises(DataValidationError, match="contains no files"):
            freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="publication_era",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(_zip_bytes({}))),
                mode=VintageMode.UPDATE,
            )
        assert not raw_path.exists()
        assert self._freeze(tmp_path, "publication_era").monthly_observations == 4

    def test_disjoint_vintages_are_rejected(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "v1")
        frame = load_normalized_french(Path(record.normalized_path))
        other = frame.copy()
        other.index = other.index + 600
        with pytest.raises(ValueError, match="share no comparable"):
            compare_vintages(
                historical=frame,
                current=other,
                dataset="d",
                historical_label="a",
                current_label="b",
            )


class TestQArchive:
    """Anomaly archives must be frozen and reshaped without substitution."""

    def _payload(self) -> bytes:
        return _zip_bytes({"vvg_monthly_2025/portf_bm_monthly_2025.csv": Q_MEMBER_TEXT})

    def test_archive_freeze_records_metadata(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(self._payload()))
        record, payload = freeze_q_archive(
            archive="vvg_monthly_2025",
            vintage_label="test",
            raw_root=tmp_path / "raw",
            manifest_root=tmp_path / "manifest",
            session=session,
            mode=VintageMode.UPDATE,
        )
        assert record.member_count == 1
        assert record.provider.startswith("Hou, Xue, and Zhang")
        assert "no registration" in record.redistribution_status
        assert payload == self._payload()
        assert session.requested[0].endswith("vvg_monthly_2025.zip")

    def test_reshape_produces_a_wide_decile_panel(self) -> None:
        returns, counts, member_sha = reshape_family_panel(
            self._payload(),
            archive="vvg_monthly_2025",
            member="portf_bm_monthly_2025.csv",
            rank_column="rank_BM",
        )
        assert list(returns.columns) == ["decile_01", "decile_02"]
        assert str(returns.index[0]) == "1972-01"
        assert returns.at[pd.Period("1972-02", freq="M"), "decile_01"] == pytest.approx(-0.50)
        assert counts.at[pd.Period("1972-01", freq="M"), "decile_02"] == 110
        assert len(member_sha) == 64

    def test_missing_member_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="has no member"):
            reshape_family_panel(
                self._payload(),
                archive="vvg_monthly_2025",
                member="portf_zzz_monthly_2025.csv",
                rank_column="rank_BM",
            )

    def test_missing_columns_are_rejected(self) -> None:
        payload = _zip_bytes({"a/b.csv": "year,month,rank_BM\n1972,1,1\n"})
        with pytest.raises(DataValidationError, match="missing columns"):
            reshape_family_panel(payload, archive="a", member="b.csv", rank_column="rank_BM")

    def test_family_panel_freeze_records_metadata(self, tmp_path: Path) -> None:
        record = freeze_family_panel(
            self._payload(),
            family="book_to_market",
            specification={
                "archive": "vvg_monthly_2025",
                "member": "portf_bm_monthly_2025.csv",
                "rank_column": "rank_BM",
                "article_label": "BM",
                "article_definition": "value-weighted deciles sorted on the book-to-market ratio",
            },
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            vintage_label="test",
        )
        assert record.weighting == "value_weighted"
        assert record.number_of_portfolios == 2
        assert record.return_units == "percent_per_month"
        assert record.continuous_months is True
        assert record.missing_value_count == 0
        assert record.minimum_stocks_per_portfolio == 100
        panel = load_family_panel(Path(record.normalized_path))
        assert panel.shape == (2, 2)

    def test_non_zip_payload_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"nope"))
        with pytest.raises(DataAccessError, match="not a ZIP archive"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_non_200_status_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"x", status_code=400))
        with pytest.raises(DataAccessError, match="Unexpected HTTP status"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_empty_archive_is_rejected_and_leaves_no_freeze(self, tmp_path: Path) -> None:
        with pytest.raises(DataValidationError, match="contains no files"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(_zip_bytes({}))),
                mode=VintageMode.UPDATE,
            )
        assert not (tmp_path / "raw").exists()
        assert not (tmp_path / "manifest").exists()

    def test_archive_of_only_empty_members_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataValidationError, match="only empty files"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(
                    FakeResponse(_zip_bytes({"vvg_monthly_2025/portf_bm_monthly_2025.csv": ""}))
                ),
                mode=VintageMode.UPDATE,
            )
        assert not (tmp_path / "raw").exists()
        assert not (tmp_path / "manifest").exists()

    def test_hollow_archive_leaves_the_raw_path_free_for_a_retry(self, tmp_path: Path) -> None:
        raw_path = tmp_path / "raw" / "vvg_monthly_2025_test.zip"
        with pytest.raises(DataValidationError):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(_zip_bytes({}))),
                mode=VintageMode.UPDATE,
            )
        record, _ = freeze_q_archive(
            archive="vvg_monthly_2025",
            vintage_label="test",
            raw_root=tmp_path / "raw",
            manifest_root=tmp_path / "manifest",
            session=FakeSession(FakeResponse(self._payload())),
            mode=VintageMode.UPDATE,
        )
        assert raw_path.read_bytes() == self._payload()
        assert record.raw_sha256 == hashlib.sha256(self._payload()).hexdigest()
        assert record.member_count == 1

    def test_a_republished_archive_aborts_the_verification_run(self, tmp_path: Path) -> None:
        freeze_q_archive(
            archive="vvg_monthly_2025",
            vintage_label="test",
            raw_root=tmp_path / "raw",
            manifest_root=tmp_path / "manifest",
            session=FakeSession(FakeResponse(self._payload())),
            mode=VintageMode.UPDATE,
        )
        (tmp_path / "raw" / "vvg_monthly_2025_test.zip").unlink()
        other = _zip_bytes({"vvg_monthly_2025/portf_bm_monthly_2025.csv": Q_MEMBER_TEXT + "\n"})
        with pytest.raises(FrozenVintageError) as raised:
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(other)),
            )
        message = str(raised.value)
        assert "q-factor testing-portfolio archive vvg_monthly_2025 at vintage test" in message
        assert hashlib.sha256(other).hexdigest() in message
        assert "make update-vintage-portfolios" in message


class TestEdgeCases:
    """Explicit coverage for the guard branches in the acquisition path."""

    def test_identical_french_bytes_may_be_refrozen(self, tmp_path: Path) -> None:
        payload = _zip_bytes({"f.CSV": FRENCH_TEXT})
        for _ in range(2):
            record = freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="v",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(payload)),
                mode=VintageMode.UPDATE,
            )
        assert record.raw_sha256 == hashlib.sha256(payload).hexdigest()

    def test_different_french_bytes_abort_the_verification_run(self, tmp_path: Path) -> None:
        freeze_french_archive(
            dataset="F-F_Research_Data_Factors",
            url="https://example.invalid/x.zip",
            vintage_label="v",
            archive_date="2017-07-09",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=FakeSession(FakeResponse(_zip_bytes({"f.CSV": FRENCH_TEXT}))),
            mode=VintageMode.UPDATE,
        )
        frozen_raw = tmp_path / "raw" / "F-F_Research_Data_Factors"
        (frozen_raw / "F-F_Research_Data_Factors_v.zip").unlink()
        with pytest.raises(FrozenVintageError, match="make update-vintage-french"):
            freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="v",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(_zip_bytes({"f.CSV": FRENCH_TEXT + "\n"}))),
            )

    def test_empty_french_payload_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataAccessError, match="Empty payload"):
            freeze_french_archive(
                dataset="F-F_Research_Data_Factors",
                url="https://example.invalid/x.zip",
                vintage_label="v",
                archive_date="2017-07-09",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(b"")),
                mode=VintageMode.UPDATE,
            )

    def test_empty_q_payload_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataAccessError, match="Empty payload"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(b"")),
                mode=VintageMode.UPDATE,
            )


class TestSharedAcquisitionHelpers:
    """Every freeze module must share one raw writer, serializer, and panel loader."""

    def test_no_freeze_module_keeps_a_private_copy_of_the_helpers(self) -> None:
        for module in (french_freeze, comparator_freeze, q_archive):
            assert not hasattr(module, "_write_raw_once")
            assert not hasattr(module, "_canonical_monthly_bytes")
        assert not hasattr(q_archive, "_canonical_panel_bytes")
        assert not hasattr(short_rate_freeze, "_write_raw_once")

    def test_public_loaders_stay_importable_and_agree(self, tmp_path: Path) -> None:
        panel = pd.DataFrame(
            {"a": [1.0, float("nan")], "b": [3.0, 4.0]},
            index=pd.PeriodIndex(["1972-01", "1972-02"], freq="M"),
        )
        path = tmp_path / "panel.csv"
        path.write_bytes(canonical_monthly_bytes(panel))
        expected = load_normalized_month_panel(path)
        for loader in (load_normalized_french, load_normalized_comparator, load_family_panel):
            loaded = loader(path)
            pd.testing.assert_frame_equal(loaded, expected)
        assert bool(pd.isna(expected.at[pd.Period("1972-02", freq="M"), "a"]))

    def test_short_rate_keeps_its_own_date_value_serializer(self) -> None:
        frame = pd.DataFrame({"date": pd.to_datetime(["1972-01-01"]), "value": [3.5]})
        assert _canonical_csv_bytes(frame) == b"date,value\n1972-01-01,3.5000000000\n"

    def test_shared_writer_refuses_differing_bytes(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "raw.bin"
        digest = write_raw_once(path, b"abc")
        assert digest == hashlib.sha256(b"abc").hexdigest()
        assert write_raw_once(path, b"abc") == digest
        with pytest.raises(DataAccessError, match="Refusing to overwrite"):
            write_raw_once(path, b"abd")
        assert path.read_bytes() == b"abc"


Q_FACTOR_CSV = (
    b"year,month,R_F,R_MKT,R_ME,R_IA,R_ROE,R_EG\n"
    b"1972,1,0.30,1.85,0.50,0.20,0.60,0.10\n"
    b"1972,2,0.29,2.90,-0.40,0.35,0.10,0.22\n"
    b"1972,3,0.31,0.55,1.10,-0.15,0.45,-0.05\n"
)

LIQUIDITY_TEXT = (
    b"% LIQUIDITY FACTORS OF PASTOR AND STAMBAUGH (JPE 2003) UPDATED THROUGH DEC 1972\n"
    b"% Column 1: Month\n"
    b"% Column 4: Traded liquidity factor (LIQ_V, 10-1 portfolio return)\n"
    b"%\n"
    b"% Month\tAgg Liq.\tInnov Liq (eq8)\tTraded Liq (LIQ_V)\n"
    b"197201\t -0.01753789\t  0.00425841\t-99\n"
    b"197202\t  0.02110000\t -0.00310000\t 0.04120000\n"
    b"197203\t -0.00450000\t  0.00990000\t-0.01870000\n"
)


class TestComparatorFreeze:
    """Comparator factors must be frozen with the same discipline as every input."""

    def _freeze(
        self,
        tmp_path: Path,
        dataset: str,
        payload: bytes,
        parser: str,
        mode: VintageMode = VintageMode.UPDATE,
    ) -> ComparatorFreezeRecord:
        session = FakeSession(FakeResponse(payload, headers={"ETag": '"z"'}))
        return freeze_comparator_file(
            dataset=dataset,
            url="https://example.invalid/file",
            file_name="file.csv" if parser == "q_factor_csv" else "file.txt",
            parser=parser,
            provider="Test provider",
            attributed_by_article_to="Test attribution",
            units="percent_per_month" if parser == "q_factor_csv" else "decimal_per_month",
            missing_value_code="none" if parser == "q_factor_csv" else "-99",
            redistribution_status="public research data",
            vintage_label="test_vintage",
            archive_date="2026-08-02",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=session,
            mode=mode,
        )

    def test_q_factor_file_is_parsed_into_a_month_panel(self) -> None:
        frame, commentary = parse_q_factor_csv(Q_FACTOR_CSV)
        assert list(frame.columns) == ["R_F", "R_MKT", "R_ME", "R_IA", "R_ROE", "R_EG"]
        assert str(frame.index[0]) == "1972-01"
        assert str(frame.index[-1]) == "1972-03"
        assert commentary == ()
        assert frame.at[pd.Period("1972-02", freq="M"), "R_ME"] == pytest.approx(-0.40)

    def test_q_factor_file_without_year_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="missing columns"):
            parse_q_factor_csv(b"month,R_ME\n1,0.5\n")

    def test_q_factor_file_without_factors_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="no factor columns"):
            parse_q_factor_csv(b"year,month\n1972,1\n")

    def test_liquidity_sentinel_becomes_a_null(self) -> None:
        frame, commentary = parse_liquidity_text(LIQUIDITY_TEXT)
        assert list(frame.columns) == [
            "aggregate_liquidity_level",
            "liquidity_innovation_non_traded",
            "traded_liquidity_factor",
        ]
        assert bool(pd.isna(frame.at[pd.Period("1972-01", freq="M"), "traded_liquidity_factor"]))
        assert frame.at[pd.Period("1972-02", freq="M"), "traded_liquidity_factor"] == pytest.approx(
            0.0412
        )
        assert any("LIQUIDITY FACTORS" in line for line in commentary)

    def test_liquidity_file_without_rows_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="no parsable data rows"):
            parse_liquidity_text(b"% only commentary\n")

    def test_freeze_records_required_metadata(self, tmp_path: Path) -> None:
        record = self._freeze(tmp_path, "q_factors", Q_FACTOR_CSV, "q_factor_csv")
        assert record.dataset == "q_factors"
        assert record.attributed_by_article_to == "Test attribution"
        assert record.monthly_start == "1972-01"
        assert record.monthly_observations == 3
        assert record.missing_value_count == 0
        assert record.raw_sha256 == hashlib.sha256(Q_FACTOR_CSV).hexdigest()
        assert record.http_etag == '"z"'
        assert record.value_range["maximum"] == pytest.approx(2.90)

    def test_liquidity_freeze_counts_the_sentinel_as_missing(self, tmp_path: Path) -> None:
        record = self._freeze(
            tmp_path, "pastor_stambaugh_liquidity", LIQUIDITY_TEXT, "liquidity_text"
        )
        assert record.missing_value_count == 1
        assert record.missing_value_code == "-99"
        assert record.units == "decimal_per_month"
        panel = load_normalized_comparator(Path(record.normalized_path))
        assert panel.shape == (3, 3)

    def test_unknown_parser_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataValidationError, match="Unsupported comparator parser"):
            self._freeze(tmp_path, "q_factors", Q_FACTOR_CSV, "not_a_parser")

    def test_non_200_status_is_rejected(self, tmp_path: Path) -> None:
        session = FakeSession(FakeResponse(b"x", status_code=500))
        with pytest.raises(DataAccessError, match="Unexpected HTTP status"):
            freeze_comparator_file(
                dataset="q_factors",
                url="https://example.invalid/file",
                file_name="file.csv",
                parser="q_factor_csv",
                provider="p",
                attributed_by_article_to="a",
                units="percent_per_month",
                missing_value_code="none",
                redistribution_status="public",
                vintage_label="v",
                archive_date="2026-08-02",
                raw_root=tmp_path / "raw",
                normalized_root=tmp_path / "interim",
                manifest_root=tmp_path / "manifest",
                session=session,
                mode=VintageMode.UPDATE,
            )

    def test_empty_payload_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataAccessError, match="Empty payload"):
            self._freeze(tmp_path, "q_factors", b"", "q_factor_csv")

    def test_an_extended_comparator_file_aborts_the_verification_run(self, tmp_path: Path) -> None:
        self._freeze(tmp_path, "q_factors", Q_FACTOR_CSV, "q_factor_csv")
        (tmp_path / "raw" / "q_factors" / "q_factors_test_vintage.csv").unlink()
        with pytest.raises(FrozenVintageError) as raised:
            self._freeze(
                tmp_path,
                "q_factors",
                Q_FACTOR_CSV + b"1972,4,0.31,1.00,0.10,0.10,0.10,0.10\n",
                "q_factor_csv",
                mode=VintageMode.VERIFY,
            )
        message = str(raised.value)
        assert "comparator file q_factors at vintage test_vintage" in message
        assert "make update-vintage-comparators" in message

    def test_duplicate_months_are_rejected(self, tmp_path: Path) -> None:
        payload = b"year,month,R_ME\n1972,1,0.5\n1972,1,0.6\n"
        with pytest.raises(DataValidationError, match="duplicate months"):
            parse_q_factor_csv(payload)

    def test_header_only_q_factor_file_is_rejected(self) -> None:
        with pytest.raises(DataValidationError, match="no monthly observations"):
            parse_q_factor_csv(b"year,month,R_F,R_MKT\n")

    def test_header_only_payload_leaves_the_raw_path_free_for_a_retry(self, tmp_path: Path) -> None:
        raw_path = tmp_path / "raw" / "q_factors" / "q_factors_test_vintage.csv"
        with pytest.raises(DataValidationError, match="no monthly observations"):
            self._freeze(tmp_path, "q_factors", b"year,month,R_F,R_MKT\n", "q_factor_csv")
        assert not raw_path.exists()
        assert not (tmp_path / "manifest").exists()

        record = self._freeze(tmp_path, "q_factors", Q_FACTOR_CSV, "q_factor_csv")
        assert raw_path.read_bytes() == Q_FACTOR_CSV
        assert record.monthly_observations == 3

    def test_the_unused_q_factor_missing_value_constant_is_gone(self) -> None:
        assert not hasattr(comparator_freeze, "Q_FACTOR_MISSING_VALUE_CODE")
