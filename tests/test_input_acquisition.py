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
    freeze_fred_series,
    load_normalized_series,
)
from short_rate_anomaly_regimes.exceptions import DataAccessError, DataValidationError
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
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in members.items():
            archive.writestr(name, text)
    return buffer.getvalue()


class TestFredFreeze:
    """FRED acquisition must be immutable and fully described."""

    def _freeze(self, tmp_path: Path, payload: bytes = FRED_PAYLOAD) -> SeriesFreezeRecord:
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

    def test_overwriting_with_different_bytes_is_refused(self, tmp_path: Path) -> None:
        self._freeze(tmp_path)
        with pytest.raises(DataAccessError, match="Refusing to overwrite"):
            self._freeze(tmp_path, payload=FRED_PAYLOAD + b"1972-09-01,4.87\n")

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
            )

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
            )

    def test_overwriting_with_different_bytes_is_refused(self, tmp_path: Path) -> None:
        freeze_q_archive(
            archive="vvg_monthly_2025",
            vintage_label="test",
            raw_root=tmp_path / "raw",
            manifest_root=tmp_path / "manifest",
            session=FakeSession(FakeResponse(self._payload())),
        )
        other = _zip_bytes({"vvg_monthly_2025/portf_bm_monthly_2025.csv": Q_MEMBER_TEXT + "\n"})
        with pytest.raises(DataAccessError, match="Refusing to overwrite"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(other)),
            )


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
            )
        assert record.raw_sha256 == hashlib.sha256(payload).hexdigest()

    def test_different_french_bytes_are_refused(self, tmp_path: Path) -> None:
        freeze_french_archive(
            dataset="F-F_Research_Data_Factors",
            url="https://example.invalid/x.zip",
            vintage_label="v",
            archive_date="2017-07-09",
            raw_root=tmp_path / "raw",
            normalized_root=tmp_path / "interim",
            manifest_root=tmp_path / "manifest",
            session=FakeSession(FakeResponse(_zip_bytes({"f.CSV": FRENCH_TEXT}))),
        )
        with pytest.raises(DataAccessError, match="Refusing to overwrite"):
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
            )

    def test_empty_q_payload_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataAccessError, match="Empty payload"):
            freeze_q_archive(
                archive="vvg_monthly_2025",
                vintage_label="test",
                raw_root=tmp_path / "raw",
                manifest_root=tmp_path / "manifest",
                session=FakeSession(FakeResponse(b"")),
            )


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
        self, tmp_path: Path, dataset: str, payload: bytes, parser: str
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
            )

    def test_empty_payload_is_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(DataAccessError, match="Empty payload"):
            self._freeze(tmp_path, "q_factors", b"", "q_factor_csv")

    def test_overwriting_with_different_bytes_is_refused(self, tmp_path: Path) -> None:
        self._freeze(tmp_path, "q_factors", Q_FACTOR_CSV, "q_factor_csv")
        with pytest.raises(DataAccessError, match="Refusing to overwrite"):
            self._freeze(
                tmp_path,
                "q_factors",
                Q_FACTOR_CSV + b"1972,4,0.31,1.00,0.10,0.10,0.10,0.10\n",
                "q_factor_csv",
            )

    def test_duplicate_months_are_rejected(self, tmp_path: Path) -> None:
        payload = b"year,month,R_ME\n1972,1,0.5\n1972,1,0.6\n"
        with pytest.raises(DataValidationError, match="duplicate months"):
            parse_q_factor_csv(payload)
