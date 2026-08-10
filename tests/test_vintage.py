"""Tests for frozen-vintage verification and the update-vintage escape hatch.

The archive claims a rebuild that reproduces the published results. Every
provider endpoint it reads serves the current vintage, so that claim rests
entirely on the rule tested here: a download is accepted only when it hashes to
the value recorded in the shipped provenance manifest, and only one explicit
operation may change that recorded value.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import scripts.acquire_short_rates as acquire_short_rates
from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app
from short_rate_anomaly_regimes.data.acquisition import (
    write_raw_for_new_vintage,
    write_raw_once,
)
from short_rate_anomaly_regimes.data.short_rate_freeze import SeriesFreezeRecord
from short_rate_anomaly_regimes.data.vintage import (
    UPDATE_VINTAGE_FLAG,
    VintageMode,
    acquire_frozen_payload,
    announce_mode,
    parse_vintage_mode,
    recorded_sha256,
)
from short_rate_anomaly_regimes.exceptions import FrozenVintageError

PAYLOAD = b"observation_date,FEDFUNDS\n1972-01-01,3.50\n"
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


def _fetch(payload: bytes = PAYLOAD) -> Any:
    def fetch() -> tuple[bytes, dict[str, str]]:
        return payload, {"ETag": '"x"'}

    return fetch


def _write_manifest(path: Path, digest: str | None, field: str = "raw_sha256") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    record: dict[str, object] = {"series_id": "FEDFUNDS"}
    if digest is not None:
        record[field] = digest
    path.write_text(json.dumps(record), encoding="utf-8", newline="\n")
    return path


class TestRecordedHash:
    """The shipped manifest is the only source of an expected hash."""

    def test_absent_manifest_records_nothing(self, tmp_path: Path) -> None:
        assert recorded_sha256(tmp_path / "absent.json") is None

    def test_unreadable_manifest_records_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        assert recorded_sha256(path) is None

    def test_manifest_that_is_not_an_object_records_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        path.write_text("[1, 2]", encoding="utf-8")
        assert recorded_sha256(path) is None

    def test_blank_or_missing_field_records_nothing(self, tmp_path: Path) -> None:
        assert recorded_sha256(_write_manifest(tmp_path / "a.json", None)) is None
        assert recorded_sha256(_write_manifest(tmp_path / "b.json", "   ")) is None

    def test_recorded_hash_is_returned(self, tmp_path: Path) -> None:
        assert recorded_sha256(_write_manifest(tmp_path / "c.json", DIGEST)) == DIGEST


class TestVerification:
    """The match, mismatch, and unrecorded paths of a verification run."""

    def test_matching_bytes_verify(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "m.json", DIGEST)

        verified = acquire_frozen_payload(
            source_label="FRED series FEDFUNDS",
            url="https://example.invalid/f.csv",
            manifest_path=manifest,
            raw_path=tmp_path / "raw.csv",
            mode=VintageMode.VERIFY,
            update_command="make update-vintage-short-rates",
            fetch=_fetch(),
        )

        assert verified.sha256 == DIGEST
        assert verified.payload == PAYLOAD
        assert verified.byte_source == "provider_download"
        assert not verified.reused_local_raw

    def test_mismatched_bytes_abort_with_an_actionable_message(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "m.json", DIGEST)
        revised = PAYLOAD + b"1972-02-01,3.29\n"

        with pytest.raises(FrozenVintageError) as raised:
            acquire_frozen_payload(
                source_label="FRED series FEDFUNDS at vintage 2026-08-01",
                url="https://example.invalid/f.csv",
                manifest_path=manifest,
                raw_path=tmp_path / "raw.csv",
                mode=VintageMode.VERIFY,
                update_command="make update-vintage-short-rates",
                fetch=_fetch(revised),
            )

        message = str(raised.value)
        # The four facts the abort has to carry.
        assert "FRED series FEDFUNDS at vintage 2026-08-01" in message
        assert DIGEST in message
        assert hashlib.sha256(revised).hexdigest() in message
        assert "make update-vintage-short-rates" in message
        # And the two ways out.
        assert "ALFRED" in message
        assert "Internet Archive" in message
        assert not (tmp_path / "raw.csv").exists()

    def test_an_unrecorded_vintage_cannot_be_established_by_verifying(self, tmp_path: Path) -> None:
        with pytest.raises(FrozenVintageError, match="No frozen-vintage hash is recorded"):
            acquire_frozen_payload(
                source_label="FRED series FEDFUNDS",
                url="https://example.invalid/f.csv",
                manifest_path=tmp_path / "absent.json",
                raw_path=tmp_path / "raw.csv",
                mode=VintageMode.VERIFY,
                update_command="make update-vintage-short-rates",
                fetch=_fetch(),
            )

    def test_a_manifest_without_the_hash_field_names_that_reason(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "m.json", None)

        with pytest.raises(FrozenVintageError, match="carries no usable 'raw_sha256' field"):
            acquire_frozen_payload(
                source_label="FRED series FEDFUNDS",
                url="https://example.invalid/f.csv",
                manifest_path=manifest,
                raw_path=tmp_path / "raw.csv",
                mode=VintageMode.VERIFY,
                update_command="make update-vintage-short-rates",
                fetch=_fetch(),
            )

    def test_a_matching_local_raw_file_skips_the_network(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "m.json", DIGEST)
        raw = tmp_path / "raw.csv"
        raw.write_bytes(PAYLOAD)

        def fetch() -> tuple[bytes, dict[str, str]]:  # pragma: no cover - must not run
            raise AssertionError("the provider was contacted despite a matching local file")

        verified = acquire_frozen_payload(
            source_label="FRED series FEDFUNDS",
            url="https://example.invalid/f.csv",
            manifest_path=manifest,
            raw_path=raw,
            mode=VintageMode.VERIFY,
            update_command="make update-vintage-short-rates",
            fetch=fetch,
        )

        assert verified.reused_local_raw
        assert verified.sha256 == DIGEST

    def test_a_stale_local_raw_file_does_not_satisfy_verification(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "m.json", DIGEST)
        raw = tmp_path / "raw.csv"
        raw.write_bytes(b"stale bytes")

        verified = acquire_frozen_payload(
            source_label="FRED series FEDFUNDS",
            url="https://example.invalid/f.csv",
            manifest_path=manifest,
            raw_path=raw,
            mode=VintageMode.VERIFY,
            update_command="make update-vintage-short-rates",
            fetch=_fetch(),
        )

        assert not verified.reused_local_raw


class TestUpdateEscapeHatch:
    """Only an explicit update run may record a different expected hash."""

    def test_update_mode_accepts_bytes_that_verification_would_refuse(self, tmp_path: Path) -> None:
        manifest = _write_manifest(tmp_path / "m.json", DIGEST)
        revised = PAYLOAD + b"1972-02-01,3.29\n"

        verified = acquire_frozen_payload(
            source_label="FRED series FEDFUNDS",
            url="https://example.invalid/f.csv",
            manifest_path=manifest,
            raw_path=tmp_path / "raw.csv",
            mode=VintageMode.UPDATE,
            update_command="make update-vintage-short-rates",
            fetch=_fetch(revised),
        )

        assert verified.sha256 == hashlib.sha256(revised).hexdigest()
        assert verified.mode.writes_provenance

    def test_only_update_mode_writes_provenance(self) -> None:
        assert VintageMode.UPDATE.writes_provenance
        assert not VintageMode.VERIFY.writes_provenance

    def test_only_the_update_writer_replaces_existing_raw_bytes(self, tmp_path: Path) -> None:
        raw = tmp_path / "raw.csv"
        write_raw_once(raw, PAYLOAD)
        replacement = b"a different vintage"

        with pytest.raises(Exception, match="Refusing to overwrite"):
            write_raw_once(raw, replacement)
        digest = write_raw_for_new_vintage(raw, replacement)

        assert raw.read_bytes() == replacement
        assert digest == hashlib.sha256(replacement).hexdigest()

    def test_verification_is_the_default_mode(self) -> None:
        assert parse_vintage_mode([], description="x") is VintageMode.VERIFY

    def test_the_explicit_flag_selects_update(self) -> None:
        assert parse_vintage_mode([UPDATE_VINTAGE_FLAG], description="x") is VintageMode.UPDATE

    def test_an_abbreviated_flag_cannot_select_update(self) -> None:
        """`--update` must not be accepted; a frozen vintage is not changed by a near miss."""
        with pytest.raises(SystemExit):
            parse_vintage_mode(["--update"], description="x")

    def test_the_banner_states_which_mode_is_running(self) -> None:
        assert "MODE verify" in announce_mode(VintageMode.VERIFY)
        assert "MODE update-vintage" in announce_mode(VintageMode.UPDATE)
        assert "WILL be overwritten" in announce_mode(VintageMode.UPDATE)


def _stub_record(series_id: str) -> SeriesFreezeRecord:
    return SeriesFreezeRecord(
        series_id=series_id,
        provider="provider",
        provider_url="https://example.invalid",
        title="title",
        retrieved_at_utc="2026-08-09T00:00:00+00:00",
        raw_path="raw",
        normalized_path="normalized",
        raw_sha256=DIGEST,
        normalized_sha256=DIGEST,
        observation_start="1972-01-01",
        observation_end="1972-01-01",
        observation_count=1,
        missing_value_count=0,
        missing_value_code=".",
        units_declared="percent_per_annum",
        frequency_declared="monthly",
        frequency_observed="monthly_first_of_month_stamped",
        seasonal_adjustment_declared="not_seasonally_adjusted",
        aggregation_of_source_declared="n/a",
        source_notes="notes",
        redistribution_status="public_domain_us_government_work",
        vintage_label="fred_current_retrieved_2026-08-01",
        vintage_source="source",
        vintage_http_last_modified=None,
        vintage_http_etag=None,
        metadata_provenance="declared",
    )


class TestAcquisitionScriptWiring:
    """The scripts must default to verification and write summaries only on update."""

    def _run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        argv: list[str],
    ) -> list[VintageMode]:
        seen: list[VintageMode] = []

        def fake_freeze(**kwargs: Any) -> SeriesFreezeRecord:
            seen.append(kwargs["mode"])
            return _stub_record(str(kwargs["series_id"]))

        monkeypatch.setattr(acquire_short_rates, "freeze_fred_series", fake_freeze)
        monkeypatch.chdir(tmp_path)
        acquire_short_rates.main(argv)
        return seen

    def test_a_plain_run_verifies_and_writes_no_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = self._run(tmp_path, monkeypatch, [])

        assert seen == [VintageMode.VERIFY] * len(acquire_short_rates.SERIES)
        assert not (tmp_path / acquire_short_rates.SUMMARY_CSV).exists()

    def test_the_flag_switches_the_script_into_update_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = self._run(tmp_path, monkeypatch, [UPDATE_VINTAGE_FLAG])

        assert seen == [VintageMode.UPDATE] * len(acquire_short_rates.SERIES)
        assert (tmp_path / acquire_short_rates.SUMMARY_CSV).is_file()


class TestRegistryCommandWiring:
    """`srar acquire-data` verifies unless it is given the explicit flag."""

    def _invoke(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, extra: list[str]) -> Any:
        registry = tmp_path / "registry.yaml"
        registry.write_text(
            "version: 1\n"
            "sources:\n"
            "  - id: frozen_fed\n"
            "    category: short_rate\n"
            "    access: public\n"
            f"    raw_path: {(tmp_path / 'fed.csv').as_posix()}\n"
            "    series_candidates: [FEDFUNDS]\n",
            encoding="utf-8",
        )
        calls: list[dict[str, Any]] = []
        monkeypatch.setattr(
            "short_rate_anomaly_regimes.cli.download_fred_series",
            lambda **kwargs: calls.append(kwargs),
        )
        result = CliRunner().invoke(
            app,
            ["acquire-data", "--registry", str(registry), "--live", *extra],
        )
        assert result.exit_code == 0, result.output
        return calls, result

    def test_a_live_run_verifies_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls, result = self._invoke(tmp_path, monkeypatch, [])

        assert calls[0]["mode"] is VintageMode.VERIFY
        assert "verified against the frozen vintage" in result.stdout

    def test_the_flag_switches_the_command_into_update_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls, result = self._invoke(tmp_path, monkeypatch, [UPDATE_VINTAGE_FLAG])

        assert calls[0]["mode"] is VintageMode.UPDATE
        assert "Recorded a new frozen vintage" in result.stdout


class TestMakefileSeparation:
    """The rebuild and the vintage change must be different commands."""

    def _recipes(self) -> dict[str, list[str]]:
        recipes: dict[str, list[str]] = {}
        current: str | None = None
        for line in Path("Makefile").read_text(encoding="utf-8").splitlines():
            if line[:1].isalpha() and ":" in line:
                current = line.split(":", 1)[0].strip()
                recipes[current] = []
            elif line.startswith("\t") and current is not None:
                recipes[current].append(line)
            elif not line.strip():
                current = None
        return recipes

    def test_no_reproduce_stage_can_refresh_a_frozen_vintage(self) -> None:
        recipes = self._recipes()
        chain = [name for name in recipes if name == "reproduce" or name.startswith("reproduce-")]

        assert chain
        for name in chain:
            for line in recipes[name]:
                assert UPDATE_VINTAGE_FLAG not in line, f"{name} can refresh the frozen vintage"

    def test_every_acquisition_path_has_a_named_update_target(self) -> None:
        recipes = self._recipes()
        expected = {
            "update-vintage",
            "update-vintage-short-rates",
            "update-vintage-french",
            "update-vintage-portfolios",
            "update-vintage-comparators",
        }

        assert expected <= set(recipes)
        for name in expected - {"update-vintage"}:
            assert any(UPDATE_VINTAGE_FLAG in line for line in recipes[name])
