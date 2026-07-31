"""Command-line interface for the research repository."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from short_rate_anomaly_regimes.config import (
    ExtensionConfig,
    load_baseline_config,
    load_extension_config,
    load_project_config,
    load_regime_config,
    load_reporting_config,
)
from short_rate_anomaly_regimes.data.acquisition import (
    download_fred_series,
    download_kenneth_french_dataset,
    register_manual_source,
)
from short_rate_anomaly_regimes.data.catalog import build_catalog, load_registry
from short_rate_anomaly_regimes.environment import write_environment_manifest
from short_rate_anomaly_regimes.exceptions import ReplicationBlockError
from short_rate_anomaly_regimes.extensions.temporal import (
    TemporalFreeze,
    write_blocked_temporal_report,
)
from short_rate_anomaly_regimes.forecasting.out_of_sample import write_blocked_oos_report
from short_rate_anomaly_regimes.portfolios.construction import write_construction_manifest
from short_rate_anomaly_regimes.regimes.stability import write_blocked_regime_report
from short_rate_anomaly_regimes.reporting.audit import (
    build_missing_input_audit,
    load_table_targets,
    write_audit,
    write_audit_json,
    write_replication_report,
)
from short_rate_anomaly_regimes.reporting.manuscript import write_blocked_manuscript_report
from short_rate_anomaly_regimes.reporting.release import (
    write_adversarial_reports,
    write_checksum_manifest,
    write_data_acquisition_guide,
    write_release_environment_manifest,
    write_release_gate,
    write_release_notes,
    write_sbom,
    write_source_archive,
    write_source_archive_manifest,
)
from short_rate_anomaly_regimes.shocks.decomposition import write_blocked_shock_report

app = typer.Typer(no_args_is_help=True)
console = Console()
ConfigPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
OutputPathOption = Annotated[Path, typer.Option(dir_okay=False)]
InputPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
ConfigPathsOption = Annotated[list[Path], typer.Option("--config", exists=True, dir_okay=False)]
RegistryPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
OptionalSourceIdOption = Annotated[str | None, typer.Option("--source-id")]
RequiredSourceIdOption = Annotated[str, typer.Option("--source-id")]
ExpectedColumnsOption = Annotated[list[str] | None, typer.Option("--expected-column")]
ManualSourcePathOption = Annotated[Path, typer.Option("--file", exists=True, dir_okay=False)]


@app.command("validate-config")
def validate_config(config: ConfigPathOption) -> None:
    """Validate a known project YAML configuration."""
    validated = load_project_config(config)
    if hasattr(validated, "project"):
        baseline = load_baseline_config(config)
        console.print(
            f"Validated {baseline.project.name} in {baseline.project.replication_mode} mode"
        )
    else:
        console.print(f"Validated {config}")


@app.command("validate-data")
def validate_data(registry: ConfigPathOption) -> None:
    """Validate the source registry without downloading data."""
    validated = load_registry(registry)
    console.print(f"Validated {len(validated.sources)} registered sources")


@app.command("acquire-data")
def acquire_data(
    registry: RegistryPathOption,
    source_id: OptionalSourceIdOption = None,
    live: bool = False,
) -> None:
    """Acquire public data sources when exact source definitions are frozen."""
    validated = load_registry(registry)
    selected_sources = [
        source for source in validated.sources if source_id is None or source.id == source_id
    ]
    if not selected_sources:
        raise KeyError(f"No registered source selected by {source_id!r}")

    public_sources = [source for source in selected_sources if "public" in source.access]
    blocked_sources = [
        source.id
        for source in public_sources
        if source.exact_series_status is not None or source.raw_path is None
    ]
    if not live:
        console.print(
            f"Validated acquisition plan for {len(public_sources)} public sources; "
            "use --live to download exact frozen sources"
        )
        if blocked_sources:
            console.print(f"Blocked pending exact definitions: {', '.join(blocked_sources)}")
        return
    if blocked_sources:
        raise ReplicationBlockError(
            "Cannot acquire sources before exact definitions are frozen: "
            f"{', '.join(blocked_sources)}"
        )

    acquired = 0
    for source in public_sources:
        if source.category in {"short_rate", "risk_free_return"} and source.series_candidates:
            if len(source.series_candidates) != 1:
                raise ReplicationBlockError(f"Ambiguous series candidates for {source.id}")
            download_fred_series(
                series_id=source.series_candidates[0],
                output_path=Path(source.raw_path or ""),
            )
            acquired += 1
        elif source.provider == "Kenneth French Data Library":
            dataset_name = source.model_extra.get("dataset_name") if source.model_extra else None
            if not isinstance(dataset_name, str):
                raise ReplicationBlockError(
                    f"Kenneth French exact archive name is not frozen for {source.id}"
                )
            download_kenneth_french_dataset(
                dataset_name=dataset_name,
                output_path=Path(source.raw_path or ""),
            )
            acquired += 1
        else:
            raise ReplicationBlockError(
                f"No source-specific downloader is registered for {source.id}"
            )
    console.print(f"Acquired {acquired} sources")


@app.command("register-manual-source")
def register_manual_source_command(
    source_id: RequiredSourceIdOption,
    file: ManualSourcePathOption,
    expected_column: ExpectedColumnsOption = None,
    redistribution_status: str = "restricted",
    provenance: OutputPathOption = Path("artifacts/provenance/manual_source.json"),
    sample_start: str | None = None,
    sample_end: str | None = None,
) -> None:
    """Register a manually supplied author or licensed file without copying it."""
    record = register_manual_source(
        source_id=source_id,
        file_path=file,
        expected_columns=tuple(expected_column or ()),
        redistribution_status=redistribution_status,
        provenance_path=provenance,
        sample_start=sample_start,
        sample_end=sample_end,
    )
    console.print(f"Registered manual source {record.source_id} with {record.rows} rows")


@app.command("build-catalog")
def build_catalog_command(
    registry: RegistryPathOption,
    output: OutputPathOption = Path("data/catalog.duckdb"),
) -> None:
    """Create or refresh the DuckDB metadata catalog."""
    validated = load_registry(registry)
    build_catalog(output, validated)
    console.print(f"Built catalog at {output}")


@app.command("environment-manifest")
def environment_manifest(
    config: ConfigPathsOption,
    output: OutputPathOption = Path("artifacts/environment/manifest.json"),
) -> None:
    """Write the Python, package, Git, BLAS, and config-hash manifest."""
    write_environment_manifest(output_path=output, config_paths=tuple(config))
    console.print(f"Wrote environment manifest to {output}")


@app.command("show-milestones")
def show_milestones() -> None:
    """Display the ordered execution milestones."""
    milestones = [
        (0, "Evidence freeze"),
        (1, "Repository foundation"),
        (2, "Data provenance"),
        (3, "Short-rate innovations"),
        (4, "Test asset assembly"),
        (5, "First-pass estimates"),
        (6, "Cross-sectional pricing"),
        (7, "Published result audit"),
        (8, "Robustness and weak factors"),
        (9, "Temporal extension"),
        (10, "Monetary regimes"),
        (11, "Shock decomposition"),
        (12, "Out-of-sample falsification"),
        (13, "Manuscript outputs"),
        (14, "Adversarial audit and release"),
    ]
    table = Table("ID", "Milestone")
    for milestone_id, name in milestones:
        table.add_row(str(milestone_id), name)
    console.print(table)


@app.command("estimate-rate-innovation")
def estimate_rate_innovation(
    config: ConfigPathOption,
) -> None:
    """Run the approved short-rate innovation estimator."""
    validated = load_baseline_config(config)
    registry = load_registry(Path("configs/data_sources.yaml"))
    source_ids = [validated.short_rate.primary_series, *validated.short_rate.alternatives]
    missing_paths: list[str] = []
    for source_id in source_ids:
        source = registry.by_id(source_id)
        if source.raw_path is None or not Path(source.raw_path).is_file():
            missing_paths.append(source.raw_path or source_id)
    if missing_paths:
        raise ReplicationBlockError(
            "Cannot build short-rate factors until raw rate inputs are registered: "
            f"{', '.join(missing_paths)}"
        )
    raise ReplicationBlockError(
        "Raw rate files exist, but their exact parser contract is not frozen in the repository"
    )


@app.command("assemble-test-assets")
def assemble_test_assets(
    registry: RegistryPathOption,
    manifest: OutputPathOption = Path("artifacts/portfolios/construction_manifest.json"),
) -> None:
    """Assemble the approved 25-portfolio test-asset panels."""
    validated = load_registry(registry)
    portfolio_sources = [
        source for source in validated.sources if source.category == "portfolio_returns"
    ]
    write_construction_manifest(manifest)

    blockers: list[str] = []
    for source in portfolio_sources:
        if source.provider == "Kenneth French Data Library":
            dataset_name = source.model_extra.get("dataset_name") if source.model_extra else None
            if not isinstance(dataset_name, str):
                blockers.append(f"{source.id}: exact Kenneth French archive name is not frozen")
                continue
        if source.raw_path is None or not Path(source.raw_path).is_file():
            blockers.append(f"{source.id}: missing raw portfolio file")
    if blockers:
        raise ReplicationBlockError(
            "Cannot assemble test assets until portfolio sources are registered: "
            f"{'; '.join(blockers)}"
        )
    raise ReplicationBlockError(
        "Raw portfolio files exist, but source-specific output contracts are not frozen"
    )


@app.command("estimate-first-pass")
def estimate_first_pass(
    config: ConfigPathOption,
) -> None:
    """Run first-pass time-series regressions after required panels exist."""
    validated = load_baseline_config(config)
    required_paths = [
        Path("data/processed/factors/short_rate_factors.parquet"),
        Path("data/raw/kenneth_french/rf.csv"),
    ]
    required_paths.extend(
        Path("data/processed/portfolios") / f"{portfolio_set}.parquet"
        for portfolio_set in validated.portfolio_sets
    )
    missing_paths = [str(path) for path in required_paths if not path.is_file()]
    if missing_paths:
        raise ReplicationBlockError(
            "Cannot estimate first-pass regressions until required panels are registered: "
            f"{', '.join(missing_paths)}"
        )
    raise ReplicationBlockError(
        "Required panels exist, but the source-specific first-pass run contract is not frozen"
    )


@app.command("estimate-cross-section")
def estimate_cross_section(
    config: ConfigPathOption,
) -> None:
    """Run second-pass cross-sectional pricing after first-pass outputs exist."""
    validated = load_baseline_config(config)
    required_paths = [Path("artifacts/estimates/time_series")]
    required_paths.extend(
        Path("data/processed/portfolios") / f"{portfolio_set}.parquet"
        for portfolio_set in validated.portfolio_sets
    )
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        raise ReplicationBlockError(
            "Cannot estimate cross-sectional prices until first-pass artifacts and "
            f"portfolio panels exist: {', '.join(missing_paths)}"
        )
    raise ReplicationBlockError(
        "Required first-pass artifacts exist, but the cross-section run contract is not frozen"
    )


@app.command("audit-replication")
def audit_replication(
    targets: InputPathOption = Path("research/table_target_manifest.csv"),
    output: OutputPathOption = Path("artifacts/audit/table_replication.csv"),
    json_output: OutputPathOption = Path("artifacts/audit/table_replication.json"),
    report: OutputPathOption = Path("reports/generated/replication_report.md"),
) -> None:
    """Build the baseline replication audit without extension or regime results."""
    loaded_targets = load_table_targets(targets)
    required_paths = [
        Path("artifacts/estimates/time_series"),
        Path("artifacts/estimates/cross_section"),
        Path("data/processed/factors/short_rate_factors.parquet"),
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        records = build_missing_input_audit(
            loaded_targets,
            missing_reason=(
                "Empirical audit is blocked until baseline generated artifacts exist: "
                f"{', '.join(missing_paths)}"
            ),
        )
        write_audit(records, output)
        write_audit_json(records, json_output)
        write_replication_report(records, report)
        raise ReplicationBlockError(
            "Wrote missing-input audit; empirical replication verdict is blocked by: "
            f"{', '.join(missing_paths)}"
        )
    raise ReplicationBlockError(
        "Baseline artifacts exist, but statistic-level published targets are not linked to "
        "generated cells yet"
    )


@app.command("robustness-diagnostics")
def robustness_diagnostics(
    output: OutputPathOption = Path("reports/generated/robustness_report.md"),
) -> None:
    """Run registered robustness and weak-factor diagnostics after baseline outputs exist."""
    required_paths = [
        Path("artifacts/estimates/time_series"),
        Path("artifacts/estimates/cross_section"),
        Path("data/processed/factors/short_rate_factors.parquet"),
        Path("artifacts/audit/table_replication.csv"),
    ]
    missing_paths = [str(path) for path in required_paths if not path.exists()]
    if missing_paths:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            "\n".join(
                [
                    "# Robustness Report",
                    "",
                    "Verdict: `unidentified`",
                    "",
                    "Robustness diagnostics are blocked until baseline generated artifacts exist.",
                    "",
                    "Missing inputs:",
                    *[f"- `{path}`" for path in missing_paths],
                    "",
                    "No significant-only robustness reporting has been performed.",
                ]
            ),
            encoding="utf-8",
        )
        raise ReplicationBlockError(
            "Wrote blocked robustness report; diagnostics require baseline artifacts: "
            f"{', '.join(missing_paths)}"
        )
    raise ReplicationBlockError(
        "Baseline artifacts exist, but registered robustness specification mapping is not frozen"
    )


@app.command("temporal-extension")
def temporal_extension(
    config: ConfigPathOption = Path("configs/extensions.yaml"),
    baseline_config: ConfigPathOption = Path("configs/baseline.yaml"),
    output: OutputPathOption = Path("reports/generated/temporal_extension_report.md"),
) -> None:
    """Run the post-2013 temporal-extension gate with frozen vintage metadata."""
    extension = load_extension_config(config)
    baseline = load_baseline_config(baseline_config)
    required_paths = [
        Path("data/processed/factors/short_rate_factors.parquet"),
        Path("artifacts/estimates/time_series"),
        Path("artifacts/estimates/cross_section"),
    ]
    portfolio_sets = _compatible_extension_portfolio_sets(extension, tuple(baseline.portfolio_sets))
    required_paths.extend(
        Path("data/processed/portfolios") / f"{portfolio_set}.parquet"
        for portfolio_set in portfolio_sets
    )
    missing_paths = tuple(path for path in required_paths if not path.exists())
    freeze = _temporal_freeze_from_config(extension)
    if missing_paths:
        write_blocked_temporal_report(
            output_path=output,
            freeze=freeze,
            missing_inputs=missing_paths,
        )
        raise ReplicationBlockError(
            "Wrote blocked temporal extension report; extension requires baseline and "
            f"post-2013 compatible panels: {', '.join(str(path) for path in missing_paths)}"
        )
    raise ReplicationBlockError(
        "Baseline artifacts exist, but temporal-extension panel assembly is not linked to "
        "source-specific compatible vintages yet"
    )


@app.command("run-baseline")
def run_baseline(config: ConfigPathOption) -> None:
    """Run the strict replication pipeline."""
    del config
    raise NotImplementedError("Complete Milestones 0 through 7 first")


@app.command("run-regimes")
def run_regimes(
    config: ConfigPathOption,
    output: OutputPathOption = Path("reports/generated/regime_report.md"),
) -> None:
    """Run the regime-stability extension."""
    validated = load_regime_config(config)
    required_paths = [
        Path(validated.base_config),
        Path("data/processed/extension/monthly_panel.parquet"),
        Path("data/processed/factors/short_rate_factors.parquet"),
        Path("artifacts/estimates/time_series"),
        Path("artifacts/estimates/cross_section"),
        Path("research/regime_policy_sources.csv"),
    ]
    missing_paths = tuple(path for path in required_paths if not path.exists())
    if missing_paths:
        write_blocked_regime_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked regime report; regime stability requires baseline, extension, "
            f"and verified policy-source inputs: {', '.join(str(path) for path in missing_paths)}"
        )
    raise ReplicationBlockError(
        "Required regime inputs exist, but source-specific regime panel assembly is not frozen"
    )


@app.command("shock-decomposition")
def shock_decomposition(
    config: ConfigPathOption = Path("configs/extensions.yaml"),
    output: OutputPathOption = Path("reports/generated/shock_decomposition_report.md"),
) -> None:
    """Run the high-frequency shock-decomposition gate."""
    validated = load_extension_config(config)
    shock_config = validated.shock_decomposition
    required_paths = [
        Path("research/shock_dataset_selection.csv"),
        Path(shock_config.raw_event_path),
    ]
    missing_paths = tuple(path for path in required_paths if not path.exists())
    if missing_paths:
        write_blocked_shock_report(
            output_path=output,
            missing_inputs=missing_paths,
            selected_dataset=shock_config.selected_dataset_id,
        )
        raise ReplicationBlockError(
            "Wrote blocked shock decomposition report; event-level high-frequency "
            f"shock inputs are missing: {', '.join(str(path) for path in missing_paths)}"
        )
    raise ReplicationBlockError(
        "Selected shock event data exist, but source-study reproduction targets are not frozen"
    )


@app.command("out-of-sample")
def out_of_sample(
    config: ConfigPathOption = Path("configs/extensions.yaml"),
    output: OutputPathOption = Path("reports/generated/out_of_sample_report.md"),
) -> None:
    """Run the out-of-sample falsification gate."""
    validated = load_extension_config(config)
    required_paths = [
        Path("data/processed/extension/monthly_panel.parquet"),
        Path("data/processed/factors/short_rate_factors.parquet"),
        Path("artifacts/estimates/time_series"),
        Path("artifacts/estimates/cross_section"),
    ]
    missing_paths = tuple(path for path in required_paths if not path.exists())
    if missing_paths:
        write_blocked_oos_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked out-of-sample report; falsification requires frozen "
            f"baseline and extension inputs: {', '.join(str(path) for path in missing_paths)}"
        )
    raise ReplicationBlockError(
        "Required OOS inputs exist, but panel-specific forecast assembly is not frozen "
        f"for {validated.out_of_sample.confirmatory_model}"
    )


@app.command("build-report")
def build_report(
    config: ConfigPathOption,
    output: OutputPathOption = Path("reports/generated/manuscript_output_report.md"),
) -> None:
    """Build tables, figures, and the replication report."""
    load_reporting_config(config)
    required_paths = [
        Path("paper/manuscript.tex"),
        Path("research/manuscript_artifact_map.csv"),
        Path("artifacts/audit/table_replication.csv"),
        Path("reports/generated/replication_report.md"),
        Path("reports/generated/robustness_report.md"),
        Path("reports/generated/temporal_extension_report.md"),
        Path("reports/generated/regime_report.md"),
        Path("reports/generated/shock_decomposition_report.md"),
        Path("reports/generated/out_of_sample_report.md"),
        Path("data/processed/extension/monthly_panel.parquet"),
        Path("data/processed/factors/short_rate_factors.parquet"),
    ]
    missing_paths = tuple(path for path in required_paths if not path.exists())
    if missing_paths:
        write_blocked_manuscript_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked manuscript report; manuscript outputs require frozen empirical "
            f"artifacts: {', '.join(str(path) for path in missing_paths)}"
        )
    raise ReplicationBlockError(
        "Required manuscript inputs exist, but final table and figure rendering is not frozen"
    )


@app.command("release-audit")
def release_audit(
    sbom: OutputPathOption = Path("artifacts/release/sbom.json"),
    environment: OutputPathOption = Path("artifacts/release/environment_manifest.json"),
    checksums: OutputPathOption = Path("artifacts/release/source_artifact_checksums.sha256"),
    gate: OutputPathOption = Path("artifacts/release/release_gate.json"),
    archive: OutputPathOption = Path("artifacts/release/source_release.zip"),
    archive_manifest: OutputPathOption = Path("artifacts/release/source_release_manifest.json"),
    release_notes: OutputPathOption = Path("docs/RELEASE_NOTES.md"),
    data_guide: OutputPathOption = Path("docs/DATA_ACQUISITION.md"),
    code_audit: OutputPathOption = Path("reports/generated/adversarial_code_audit.md"),
    econometric_audit: OutputPathOption = Path(
        "reports/generated/adversarial_econometric_audit.md"
    ),
) -> None:
    """Generate release hygiene, SBOM, checksum, and adversarial audit artifacts."""
    write_sbom(
        output_path=sbom,
        pyproject_path=Path("pyproject.toml"),
        lock_path=Path("poetry.lock"),
    )
    write_release_environment_manifest(output_path=environment)
    issues = write_release_gate(output_path=gate)
    write_data_acquisition_guide(
        output_path=data_guide,
        data_access_path=Path("research/data_access_matrix.csv"),
        source_registry_path=Path("configs/data_sources.yaml"),
    )
    write_release_notes(output_path=release_notes, issues=issues)
    write_adversarial_reports(
        code_report_path=code_audit,
        econometric_report_path=econometric_audit,
        issues=issues,
    )
    archive_members = write_source_archive(output_path=archive)
    write_source_archive_manifest(
        output_path=archive_manifest,
        archive_path=archive,
        members=archive_members,
    )
    write_checksum_manifest(output_path=checksums)
    critical_count = sum(issue.severity == "critical" for issue in issues)
    major_count = sum(issue.severity == "major" for issue in issues)
    console.print(
        "Wrote release audit artifacts "
        f"with {critical_count} critical and {major_count} major issues"
    )


def _temporal_freeze_from_config(config: ExtensionConfig) -> TemporalFreeze:
    freeze = config.data_freeze
    return TemporalFreeze(
        baseline_start=freeze.baseline_start,
        baseline_end=freeze.baseline_end,
        extension_start=freeze.extension_start,
        latest_common_month=freeze.latest_common_month,
        retrieval_date=freeze.retrieval_date,
        baseline_vintage_label=freeze.baseline_vintage_label,
        extension_vintage_label=freeze.extension_vintage_label,
        revision_policy=freeze.revision_policy,
    )


def _compatible_extension_portfolio_sets(
    config: ExtensionConfig,
    baseline_portfolio_sets: tuple[str, ...],
) -> tuple[str, ...]:
    baseline = set(baseline_portfolio_sets)
    return tuple(
        portfolio_set
        for portfolio_set in config.data_freeze.compatible_portfolio_sets
        if portfolio_set in baseline
    )


if __name__ == "__main__":
    app()
