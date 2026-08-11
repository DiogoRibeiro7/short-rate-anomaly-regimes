from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app

_REPO_ROOT = Path.cwd()


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


def test_estimate_first_pass_reports_missing_required_panels() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["estimate-first-pass", "--config", "configs/baseline.yaml"])

    assert result.exit_code == 1
    assert "required panels are registered" in str(result.exception)


def test_estimate_first_pass_blocks_unfrozen_run_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factor_path = (
        tmp_path / "data" / "processed" / "factors" / "short_rate_innovations_baseline.parquet"
    )
    rf_path = tmp_path / "data" / "raw" / "kenneth_french" / "rf.csv"
    portfolio_path = tmp_path / "data" / "processed" / "portfolios" / "test_set.parquet"
    for path in (factor_path, rf_path, portfolio_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("placeholder", encoding="utf-8")
    config_path = tmp_path / "baseline.yaml"
    config_path.write_text("project: test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "short_rate_anomaly_regimes.cli.load_baseline_config",
        lambda _: SimpleNamespace(portfolio_sets=["test_set"]),
    )

    result = CliRunner().invoke(
        app,
        ["estimate-first-pass", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "first-pass run contract is not frozen" in str(result.exception)


def test_estimate_cross_section_reports_missing_required_artifacts() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["estimate-cross-section", "--config", "configs/baseline.yaml"])

    assert result.exit_code == 1
    assert "first-pass artifacts" in str(result.exception)


def test_estimate_cross_section_blocks_unfrozen_run_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    time_series_dir = tmp_path / "artifacts" / "estimates" / "time_series"
    portfolio_path = tmp_path / "data" / "processed" / "portfolios" / "test_set.parquet"
    time_series_dir.mkdir(parents=True, exist_ok=True)
    portfolio_path.parent.mkdir(parents=True, exist_ok=True)
    portfolio_path.write_text("placeholder", encoding="utf-8")
    config_path = tmp_path / "baseline.yaml"
    config_path.write_text("project: test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "short_rate_anomaly_regimes.cli.load_baseline_config",
        lambda _: SimpleNamespace(portfolio_sets=["test_set"]),
    )

    result = CliRunner().invoke(
        app,
        ["estimate-cross-section", "--config", str(config_path)],
    )

    assert result.exit_code == 1
    assert "cross-section run contract is not frozen" in str(result.exception)


def test_audit_replication_writes_missing_input_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the blocked branch by making its inputs genuinely absent.

    Run from the repository root this test passed only because the baseline
    artifacts did not exist yet, so it stopped exercising the blocked path the
    moment they did. Working from an empty tree makes the condition real.
    """
    monkeypatch.chdir(tmp_path)
    target_path = tmp_path / "targets.csv"
    audit_path = tmp_path / "audit.csv"
    json_path = tmp_path / "audit.json"
    report_path = tmp_path / "replication_report.md"
    target_path.write_text(
        "target_id,source_location,description,portfolio_set,model,estimator,tolerance_rule,status\n"
        "TBL_001,article_pdf:p.936:Table 1,Target,set,model,est,"
        "published_rounding,article_extracted\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        [
            "audit-replication",
            "--targets",
            str(target_path),
            "--output",
            str(audit_path),
            "--json-output",
            str(json_path),
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 1
    assert audit_path.is_file()
    assert json_path.is_file()
    assert report_path.is_file()
    assert "missing-input audit" in str(result.exception)


def test_robustness_diagnostics_writes_blocked_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "robustness_report.md"
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        ["robustness-diagnostics", "--output", str(report_path)],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    assert "blocked robustness report" in str(result.exception)
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `unidentified`" in report
    assert "- `artifacts/diagnostics/h1_materiality.json`" in report


def test_robustness_diagnostics_reports_registered_gate_outcomes(tmp_path: Path) -> None:
    report_path = tmp_path / "robustness_report.md"

    result = CliRunner().invoke(
        app,
        ["robustness-diagnostics", "--output", str(report_path)],
    )

    assert result.exit_code == 0
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `unsupported`" in report
    assert "H1 Primary Gates On The Headline Asset Set" in report
    assert "Weak-Factor Gate Outcomes" in report
    assert "documented_reconstruction" in report


def test_temporal_extension_writes_blocked_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "temporal_extension_report.md"
    extension_config = str(Path("configs/extensions.yaml").resolve())
    baseline_config = str(Path("configs/baseline.yaml").resolve())
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "temporal-extension",
            "--config",
            extension_config,
            "--baseline-config",
            baseline_config,
            "--output",
            str(report_path),
        ],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    assert "blocked temporal extension report" in str(result.exception)
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `blocked_missing_input`" in report
    assert "Latest common month: `2025-12`" in report
    assert "- `artifacts/diagnostics/h2_temporal_stability.json`" in report


def test_temporal_extension_reports_registered_gate_outcomes(tmp_path: Path) -> None:
    report_path = tmp_path / "temporal_extension_report.md"

    result = CliRunner().invoke(
        app,
        ["temporal-extension", "--output", str(report_path)],
    )

    assert result.exit_code == 0
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `post_publication_compatibility_unsupported`" in report
    assert "Latest common month: `2025-12`" in report
    assert "Registered Compatibility Gates" in report


def test_run_regimes_writes_blocked_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "regime_report.md"
    regime_config = str(Path("configs/regimes.yaml").resolve())
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        ["run-regimes", "--config", regime_config, "--output", str(report_path)],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    assert "blocked regime report" in str(result.exception)
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `blocked_missing_input`" in report
    assert "- `artifacts/diagnostics/h3_regime_equivalence.json`" in report


def test_run_regimes_reports_registered_h3_outcomes(tmp_path: Path) -> None:
    report_path = tmp_path / "regime_report.md"

    result = CliRunner().invoke(
        app,
        ["run-regimes", "--config", "configs/regimes.yaml", "--output", str(report_path)],
    )

    assert result.exit_code == 0
    report = report_path.read_text(encoding="utf-8")
    assert (
        "Verdict: `regime_stability_unsupported_under_the_registered_equivalence_standard`"
        in report
    )
    assert "Pooled Interaction Beta Stability" in report
    assert "documented_reconstruction" in report


def test_shock_decomposition_writes_blocked_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the blocked branch by making its inputs genuinely absent.

    Run from the repository root this passes only while the event data are
    absent, which is the third time that pattern has appeared here. Working from
    an empty tree makes the condition real instead of incidental.
    """
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "extensions.yaml"
    config.write_bytes(Path(_REPO_ROOT / "configs/extensions.yaml").read_bytes())
    report_path = tmp_path / "shock_decomposition_report.md"

    result = CliRunner().invoke(
        app,
        ["shock-decomposition", "--config", str(config), "--output", str(report_path)],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    assert "blocked shock decomposition report" in str(result.exception)
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `blocked_missing_input`" in report
    assert "AR residual must remain labelled a rate innovation" in report


def test_out_of_sample_writes_blocked_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise the blocked branch by making its inputs genuinely absent.

    Run from the repository root this passed only while the falsification had
    never been executed, so it stopped exercising the blocked path the moment
    the artifacts existed. Working from an empty tree makes the condition real,
    which is the same correction the audit-replication test already carries.
    """
    monkeypatch.chdir(tmp_path)
    config = tmp_path / "extensions.yaml"
    config.write_bytes(Path(_REPO_ROOT / "configs/extensions.yaml").read_bytes())
    report_path = tmp_path / "out_of_sample_report.md"

    result = CliRunner().invoke(
        app,
        ["out-of-sample", "--config", str(config), "--output", str(report_path)],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    assert "blocked out-of-sample report" in str(result.exception)
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `blocked_missing_input`" in report
    assert "must not be tuned after test errors are seen" in report
    assert "has not been executed" in report
    assert "- `artifacts/tables/out_of_sample/forecast_metrics.csv`" in report


def test_build_report_writes_blocked_manuscript_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_path = tmp_path / "manuscript_output_report.md"
    reporting_config = str(Path("configs/reporting.yaml").resolve())
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        ["build-report", "--config", reporting_config, "--output", str(report_path)],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    assert "blocked manuscript report" in str(result.exception)
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `blocked_missing_input`" in report
    assert "- `paper/manuscript.tex`" in report


def test_build_report_records_manuscript_traceability(tmp_path: Path) -> None:
    report_path = tmp_path / "manuscript_output_report.md"

    result = CliRunner().invoke(
        app,
        ["build-report", "--config", "configs/reporting.yaml", "--output", str(report_path)],
    )

    assert result.exit_code == 0
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `manuscript_outputs_validated`" in report
    assert "Validation issues: 0" in report
    assert "| reports/generated/regime_report.md |" in report


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
    ]

    for arguments in command_arguments:
        result = runner.invoke(app, arguments)

        assert result.exit_code == 1
        assert isinstance(result.exception, NotImplementedError)


def _write_table_manifest(path: Path) -> None:
    path.write_text(
        "target_id,source_location,description,portfolio_set,model,estimator,"
        "tolerance_rule,status\n"
        "TBL_004,article_pdf:p.940:Table 4,ICAPM risk premia,joint,icapm,two_pass,"
        "published_rounding,article_extracted\n"
        "TBL_005,article_pdf:p.944:Table 5,Premium decomposition,joint,icapm,two_pass,"
        "published_rounding,article_extracted\n",
        encoding="utf-8",
    )


def test_audit_replication_writes_the_table_audit_once_the_estimates_exist(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The command must write on the unblocked path, not only when blocked.

    It previously raised "published targets are not linked to generated cells
    yet" and wrote nothing once the artifacts existed, so its only writing path
    was the blocked one. The committed artifact stayed frozen at its pre-estimate
    state, labelling every table not_reproducible_missing_input including those
    the cell-level audit compares.
    """
    monkeypatch.chdir(tmp_path)
    for directory in ("artifacts/estimates/time_series", "artifacts/estimates/cross_section"):
        (tmp_path / directory).mkdir(parents=True)
    innovations = tmp_path / "data/processed/factors/short_rate_innovations_baseline.parquet"
    innovations.parent.mkdir(parents=True)
    innovations.write_bytes(b"")

    cell_audit = tmp_path / "artifacts/audit/published_target_audit.csv"
    cell_audit.parent.mkdir(parents=True, exist_ok=True)
    cell_audit.write_text(
        "source_table,status\n"
        "Table 4,recovered_within_published_rounding\n"
        "Table 4,not_recovered_within_published_rounding\n",
        encoding="utf-8",
    )
    target_path = tmp_path / "targets.csv"
    _write_table_manifest(target_path)
    audit_path = tmp_path / "audit.csv"

    result = CliRunner().invoke(
        app,
        [
            "audit-replication",
            "--targets",
            str(target_path),
            "--output",
            str(audit_path),
            "--json-output",
            str(tmp_path / "audit.json"),
            "--report",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code == 0, result.output
    written = pd.read_csv(audit_path).set_index("target_id")
    # Covered by the cell audit, and mixed, so neither a recovery nor a failure.
    assert written.loc["TBL_004", "status"] == "partially_recovered"
    assert "1 of 2" in str(written.loc["TBL_004", "notes"])
    # Not covered. Outside the pass is not the same claim as a missing input.
    assert written.loc["TBL_005", "status"] == "not_attempted"


def test_audit_replication_blocks_when_the_cell_audit_is_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silence is what let the artifact go stale, so the gap must be loud."""
    monkeypatch.chdir(tmp_path)
    for directory in ("artifacts/estimates/time_series", "artifacts/estimates/cross_section"):
        (tmp_path / directory).mkdir(parents=True)
    innovations = tmp_path / "data/processed/factors/short_rate_innovations_baseline.parquet"
    innovations.parent.mkdir(parents=True)
    innovations.write_bytes(b"")
    target_path = tmp_path / "targets.csv"
    _write_table_manifest(target_path)

    result = CliRunner().invoke(
        app,
        [
            "audit-replication",
            "--targets",
            str(target_path),
            "--output",
            str(tmp_path / "audit.csv"),
            "--json-output",
            str(tmp_path / "audit.json"),
            "--report",
            str(tmp_path / "report.md"),
        ],
    )

    assert result.exit_code == 1
    assert "cell-level audit has not been generated" in str(result.exception)


def test_the_committed_table_audit_agrees_with_the_cell_audit() -> None:
    """The shipped table-level record must not drift from the cells again."""
    tables = pd.read_csv(Path("artifacts/audit/table_replication.csv"))
    cells = pd.read_csv(Path("artifacts/audit/published_target_audit.csv"))
    covered = set(cells["source_table"].astype(str))

    assert not (tables["status"] == "not_reproducible_missing_input").any()
    for row in tables.itertuples():
        table = str(row.source_location).rsplit(":", 1)[-1].strip()
        if table in covered:
            assert row.status == "partially_recovered", table
        else:
            assert row.status == "not_attempted", table


def test_out_of_sample_reports_the_generated_run_once_it_exists() -> None:
    """The unblocked branch used to raise and write nothing.

    It claimed "panel-specific forecast assembly is not frozen", which stopped
    being true once scripts/run_out_of_sample.py ran the frozen design. The gate
    now verifies that the tables and the report were written together rather
    than rewriting one from the other.
    """
    result = CliRunner().invoke(app, ["out-of-sample"])

    assert result.exit_code == 0, result.output
    assert "generated from the frozen design" in result.output


def test_shock_decomposition_reports_targets_not_frozen_when_the_data_arrive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The second blocked state must write its own report, not inherit the first.

    Raising without writing would leave the missing-input report on disk saying
    the event data are absent while they sit in the tree. That is precisely how
    the table-level audit came to ship a verdict that had stopped being true, so
    the gate is closed here before the data ever arrive rather than after.
    """
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "extensions.yaml"
    config_text = Path(_REPO_ROOT / "configs/extensions.yaml").read_text(encoding="utf-8")
    config_path.write_text(config_text, encoding="utf-8")

    selection = tmp_path / "research" / "shock_dataset_selection.csv"
    selection.parent.mkdir(parents=True)
    selection.write_text("dataset_id\nplaceholder\n", encoding="utf-8")
    raw_event = tmp_path / _shock_raw_event_path(config_text)
    raw_event.parent.mkdir(parents=True, exist_ok=True)
    raw_event.write_text("date,surprise\n2020-01-01,0.0\n", encoding="utf-8")

    report_path = tmp_path / "shock_decomposition_report.md"
    result = CliRunner().invoke(
        app,
        ["shock-decomposition", "--config", str(config_path), "--output", str(report_path)],
    )

    assert result.exit_code == 1
    assert report_path.is_file()
    report = report_path.read_text(encoding="utf-8")
    assert "Verdict: `blocked_targets_not_frozen`" in report
    # The report must not claim the data are missing when they are present.
    assert "blocked_missing_input" not in report
    assert "no longer the data" in report
    assert "must remain labelled a rate" in report


def _shock_raw_event_path(config_text: str) -> str:
    """Read the configured event path out of the frozen extension config."""
    config = yaml.safe_load(config_text)
    return str(config["shock_decomposition"]["raw_event_path"])


def test_no_report_command_blocks_without_rewriting_its_report() -> None:
    """A command that owns a report must never raise while leaving it stale.

    This pattern has cost three separate defects. `audit-replication` and
    `out-of-sample` each raised a message that had stopped being true and wrote
    nothing, so their committed artifacts froze at a state that no longer held,
    and a stale artifact was indistinguishable from a correctly blocked one.
    `shock-decomposition` had the same shape and escaped only because its
    precondition has never been met.

    The invariant applies to commands that own a generated report, because the
    artifact left on disk is what a reader believes. Commands that write no
    report, such as the pipeline stage guards, may refuse freely: there is
    nothing on disk to go stale. Guarding the shape rather than the three known
    cases is what stops a fourth.
    """
    source = Path(_REPO_ROOT / "src/short_rate_anomaly_regimes/cli.py").read_text(encoding="utf-8")
    bodies = source.split("@app.command(")[1:]

    offenders: list[str] = []
    for body in bodies:
        name = body.split('"', 2)[1] if '"' in body else "<unknown>"
        owns_report = 'Path("reports/generated/' in body
        if not owns_report or "ReplicationBlockError" not in body:
            continue
        # Count the writes and the terminal raises. Every raise on a path that
        # owns a report must be preceded by a write on that same path.
        raises = body.count("raise ReplicationBlockError")
        writes = sum(body.count(marker) for marker in ("write_blocked", "write_unfrozen"))
        writes += body.count("write_audit(")
        # A raise guarded by the report being absent is exempt: the defect is a
        # report that contradicts reality, and a report that does not exist
        # cannot. `out-of-sample` uses this to refuse an inconsistent state, in
        # which the evaluation tables exist but the report the driver writes
        # beside them does not, rather than papering over it with a placeholder.
        raises -= body.count("if not output.is_file():")
        if writes < raises:
            offenders.append(f"{name} ({raises} raises, {writes} report writes)")

    assert not offenders, (
        "these commands own a generated report and can raise without rewriting it, so a "
        f"stale verdict would survive the failure: {offenders}"
    )
