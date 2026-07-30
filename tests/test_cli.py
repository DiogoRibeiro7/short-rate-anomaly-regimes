from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app


def test_validate_config_command_succeeds() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-config", "--config", "configs/baseline.yaml"])

    assert result.exit_code == 0
    assert "Validated short-rate-anomaly-regimes in strict mode" in result.stdout


def test_validate_nonbaseline_config_command_succeeds() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-config", "--config", "configs/regimes.yaml"])

    assert result.exit_code == 0
    assert "Validated configs" in result.stdout


def test_validate_data_command_succeeds() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["validate-data", "--registry", "configs/data_sources.yaml"])

    assert result.exit_code == 0
    assert "registered sources" in result.stdout


def test_acquire_data_dry_run_reports_blocked_sources() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["acquire-data", "--registry", "configs/data_sources.yaml"])

    assert result.exit_code == 0
    assert "Validated acquisition plan" in result.stdout
    assert "Blocked pending exact definitions" in result.stdout


def test_acquire_data_rejects_unknown_source() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["acquire-data", "--registry", "configs/data_sources.yaml", "--source-id", "missing"],
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, KeyError)


def test_acquire_data_live_blocks_unfrozen_sources() -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "acquire-data",
            "--registry",
            "configs/data_sources.yaml",
            "--source-id",
            "federal_funds_rate",
            "--live",
        ],
    )

    assert result.exit_code == 1
    assert "Cannot acquire sources" in str(result.exception)


def test_acquire_data_live_downloads_frozen_fred_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    raw_path = tmp_path / "fed.csv"
    registry_path.write_text(
        f"""
version: 1
sources:
  - id: frozen_fed
    category: short_rate
    access: public
    raw_path: {raw_path.as_posix()}
    series_candidates: [FEDFUNDS]
""",
        encoding="utf-8",
    )
    calls: list[dict[str, Any]] = []

    def fake_download_fred_series(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "short_rate_anomaly_regimes.cli.download_fred_series",
        fake_download_fred_series,
    )

    result = CliRunner().invoke(
        app,
        ["acquire-data", "--registry", str(registry_path), "--source-id", "frozen_fed", "--live"],
    )

    assert result.exit_code == 0
    assert calls[0]["series_id"] == "FEDFUNDS"
    assert "Acquired 1 sources" in result.stdout


def test_acquire_data_live_downloads_frozen_french_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry_path = tmp_path / "registry.yaml"
    raw_path = tmp_path / "french.zip"
    registry_path.write_text(
        f"""
version: 1
sources:
  - id: frozen_french
    category: factor_returns
    provider: Kenneth French Data Library
    access: public
    raw_path: {raw_path.as_posix()}
    dataset_name: F-F_Research_Data_Factors
""",
        encoding="utf-8",
    )
    calls: list[dict[str, Any]] = []

    def fake_download_kenneth_french_dataset(**kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(
        "short_rate_anomaly_regimes.cli.download_kenneth_french_dataset",
        fake_download_kenneth_french_dataset,
    )

    result = CliRunner().invoke(
        app,
        [
            "acquire-data",
            "--registry",
            str(registry_path),
            "--source-id",
            "frozen_french",
            "--live",
        ],
    )

    assert result.exit_code == 0
    assert calls[0]["dataset_name"] == "F-F_Research_Data_Factors"


def test_acquire_data_live_rejects_unregistered_public_downloader(tmp_path: Path) -> None:
    registry_path = tmp_path / "registry.yaml"
    registry_path.write_text(
        """
version: 1
sources:
  - id: unsupported
    category: other
    access: public
    raw_path: data/raw/unsupported.csv
""",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["acquire-data", "--registry", str(registry_path), "--source-id", "unsupported", "--live"],
    )

    assert result.exit_code == 1
    assert "No source-specific downloader" in str(result.exception)


def test_build_catalog_command_writes_duckdb_catalog(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "catalog.duckdb"

    result = runner.invoke(
        app,
        ["build-catalog", "--registry", "configs/data_sources.yaml", "--output", str(output)],
    )

    assert result.exit_code == 0
    assert output.is_file()
    assert "Built catalog" in result.stdout


def test_register_manual_source_command_writes_metadata(tmp_path: Path) -> None:
    runner = CliRunner()
    source_path = tmp_path / "restricted.csv"
    provenance_path = tmp_path / "manual.json"
    source_path.write_text("date,asset\n2020-01-31,1\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "register-manual-source",
            "--source-id",
            "manual_author_file",
            "--file",
            str(source_path),
            "--expected-column",
            "date",
            "--expected-column",
            "asset",
            "--provenance",
            str(provenance_path),
        ],
    )

    assert result.exit_code == 0
    assert provenance_path.is_file()
    assert "Registered manual source manual_author_file" in result.stdout


def test_environment_manifest_command_writes_manifest(tmp_path: Path) -> None:
    runner = CliRunner()
    output = tmp_path / "manifest.json"

    result = runner.invoke(
        app,
        [
            "environment-manifest",
            "--config",
            "configs/baseline.yaml",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert output.is_file()
    assert "Wrote environment manifest" in result.stdout


def test_estimate_rate_innovation_reports_missing_raw_inputs() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["estimate-rate-innovation", "--config", "configs/baseline.yaml"])

    assert result.exit_code == 1
    assert "raw rate inputs are registered" in str(result.exception)


def test_estimate_rate_innovation_blocks_unfrozen_parser_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_path = tmp_path / "rate.csv"
    raw_path.write_text("date,rate\n2020-01-31,1\n", encoding="utf-8")

    config = SimpleNamespace(
        short_rate=SimpleNamespace(primary_series="federal_funds_rate", alternatives=[])
    )
    registry = SimpleNamespace(by_id=lambda source_id: SimpleNamespace(raw_path=str(raw_path)))
    monkeypatch.setattr("short_rate_anomaly_regimes.cli.load_baseline_config", lambda _: config)
    monkeypatch.setattr("short_rate_anomaly_regimes.cli.load_registry", lambda _: registry)

    result = CliRunner().invoke(
        app,
        ["estimate-rate-innovation", "--config", "configs/baseline.yaml"],
    )

    assert result.exit_code == 1
    assert "parser contract is not frozen" in str(result.exception)


def test_show_milestones_command_lists_release_gate() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["show-milestones"])

    assert result.exit_code == 0
    assert "Evidence freeze" in result.stdout
    assert "Adversarial audit and release" in result.stdout


def test_milestone_gated_cli_commands_report_not_implemented() -> None:
    runner = CliRunner()
    command_arguments = [
        ["run-baseline", "--config", "configs/baseline.yaml"],
        ["run-regimes", "--config", "configs/regimes.yaml"],
        ["build-report", "--config", "configs/reporting.yaml"],
    ]

    for arguments in command_arguments:
        result = runner.invoke(app, arguments)

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)
