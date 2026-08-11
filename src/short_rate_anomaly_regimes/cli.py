"""Command-line interface for the research repository."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import pandas as pd
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
from short_rate_anomaly_regimes.data.vintage import VintageMode
from short_rate_anomaly_regimes.environment import write_environment_manifest
from short_rate_anomaly_regimes.exceptions import ReplicationBlockError
from short_rate_anomaly_regimes.extensions.temporal import (
    TemporalFreeze,
    write_blocked_temporal_report,
    write_temporal_evidence_report,
)
from short_rate_anomaly_regimes.forecasting.out_of_sample import write_blocked_oos_report
from short_rate_anomaly_regimes.models.diagnostics import (
    write_blocked_robustness_report,
    write_robustness_evidence_report,
)
from short_rate_anomaly_regimes.portfolios.construction import write_construction_manifest
from short_rate_anomaly_regimes.regimes.stability import (
    write_blocked_regime_report,
    write_regime_evidence_report,
)
from short_rate_anomaly_regimes.reporting.artifact_evidence import missing_inputs
from short_rate_anomaly_regimes.reporting.audit import (
    build_missing_input_audit,
    build_table_audit_from_cells,
    load_table_targets,
    write_audit,
    write_audit_json,
    write_replication_report,
)
from short_rate_anomaly_regimes.reporting.manuscript import (
    write_blocked_manuscript_report,
    write_manuscript_output_report,
)
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

#: Registered H3 artifacts the regime report renders. A generated report is
#: blocked only when the artifacts it would read are genuinely absent.
REGIME_EVIDENCE_INPUTS = (
    Path("artifacts/diagnostics/h3_regime_equivalence.json"),
    Path("artifacts/diagnostics/h3_pooled_beta_stability.json"),
)
#: Registered H1 and weak-factor artifacts the robustness report renders.
ROBUSTNESS_EVIDENCE_INPUTS = (
    Path("artifacts/diagnostics/h1_materiality.json"),
    Path("artifacts/diagnostics/weak_factor/h4a_identification_strength.json"),
    Path("artifacts/diagnostics/weak_factor/h4b_influence_stability.json"),
    Path("artifacts/diagnostics/weak_factor/h4c_fitted_premium_precision.json"),
)
#: Registered H2 artifacts the temporal-extension report renders.
TEMPORAL_EVIDENCE_INPUTS = (
    Path("artifacts/diagnostics/h2_temporal_stability.json"),
    Path("artifacts/tables/extension/temporal_evaluation.csv"),
)
#: Evaluation artifacts the out-of-sample falsification gate would report.
OUT_OF_SAMPLE_EVIDENCE_INPUTS = (
    Path("artifacts/tables/out_of_sample/forecast_metrics.csv"),
    Path("artifacts/tables/out_of_sample/model_confidence_set.csv"),
    Path("artifacts/tables/out_of_sample/design.json"),
)
MANUSCRIPT_PATH = Path("paper/manuscript.tex")
MANUSCRIPT_ARTIFACT_MAP_PATH = Path("research/manuscript_artifact_map.csv")
#: Generated reports whose verdicts the manuscript-output report carries forward.
UPSTREAM_GENERATED_REPORTS = (
    Path("reports/generated/replication_report.md"),
    Path("reports/generated/robustness_report.md"),
    Path("reports/generated/temporal_extension_report.md"),
    Path("reports/generated/regime_report.md"),
    Path("reports/generated/shock_decomposition_report.md"),
    Path("reports/generated/out_of_sample_report.md"),
)
ConfigPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
OutputPathOption = Annotated[Path, typer.Option(dir_okay=False)]
InputPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
ConfigPathsOption = Annotated[list[Path], typer.Option("--config", exists=True, dir_okay=False)]
RegistryPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
OptionalSourceIdOption = Annotated[str | None, typer.Option("--source-id")]
RequiredSourceIdOption = Annotated[str, typer.Option("--source-id")]
ExpectedColumnsOption = Annotated[list[str] | None, typer.Option("--expected-column")]
ManualSourcePathOption = Annotated[Path, typer.Option("--file", exists=True, dir_okay=False)]
#: The only switch that may overwrite a recorded expected hash. `make reproduce`
#: never passes it; `make update-vintage` is where it lives.
UpdateVintageOption = Annotated[
    bool,
    typer.Option(
        "--update-vintage",
        help=(
            "Replace the frozen vintage with whatever the providers serve now and overwrite the "
            "recorded expected hashes. Without it, a live run verifies each download against the "
            "recorded hash and aborts on a mismatch."
        ),
    ),
]


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
    update_vintage: UpdateVintageOption = False,
) -> None:
    """Acquire public data sources and verify them against the frozen vintage.

    A live run downloads each source, hashes it, and compares the digest with the
    hash recorded in its shipped provenance manifest; it aborts on a mismatch and
    never rewrites a recorded hash. ``--update-vintage`` is the only way to record
    a different vintage, and it changes the inputs of every downstream result.
    """
    mode = VintageMode.UPDATE if update_vintage else VintageMode.VERIFY
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
            "use --live to download and verify them against the frozen vintage"
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
                mode=mode,
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
                mode=mode,
            )
            acquired += 1
        else:
            raise ReplicationBlockError(
                f"No source-specific downloader is registered for {source.id}"
            )
    if mode is VintageMode.UPDATE:
        console.print(f"Recorded a new frozen vintage for {acquired} sources")
    else:
        console.print(f"Acquired {acquired} sources verified against the frozen vintage")


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
        Path("data/processed/factors/short_rate_innovations_baseline.parquet"),
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
        Path("data/processed/factors/short_rate_innovations_baseline.parquet"),
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

    # The command used to stop here, raising that published targets were "not
    # linked to generated cells yet" and writing nothing. That became false once
    # scripts/audit_published_targets.py started linking them, and because the
    # only writing branch was the blocked one above, the committed artifact
    # stayed frozen at its pre-estimate state: every table labelled
    # not_reproducible_missing_input, including the four whose cells are
    # compared. It shipped in the archive saying nothing had been reproduced.
    cell_audit_path = Path("artifacts/audit/published_target_audit.csv")
    if not cell_audit_path.is_file():
        raise ReplicationBlockError(
            "Baseline artifacts exist, but the cell-level audit has not been generated; "
            f"run scripts/audit_published_targets.py to write {cell_audit_path.as_posix()}"
        )
    records = build_table_audit_from_cells(
        loaded_targets,
        cell_audit=pd.read_csv(cell_audit_path),
        outside_scope_reason=(
            "Outside the current audit pass. The cell-level audit does not compare this "
            "table, which is a scope decision rather than an established missing input."
        ),
    )
    write_audit(records, output)
    write_audit_json(records, json_output)
    write_replication_report(records, report)
    typer.echo(
        f"Wrote table-level audit for {len(records)} published tables to {output.as_posix()}"
    )


@app.command("robustness-diagnostics")
def robustness_diagnostics(
    output: OutputPathOption = Path("reports/generated/robustness_report.md"),
) -> None:
    """Report the registered robustness and weak-factor gate outcomes."""
    missing_paths = missing_inputs(ROBUSTNESS_EVIDENCE_INPUTS)
    if missing_paths:
        write_blocked_robustness_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked robustness report; diagnostics require the registered H1 and "
            f"weak-factor artifacts: {_format_paths(missing_paths)}"
        )
    materiality, identification, influence, precision = ROBUSTNESS_EVIDENCE_INPUTS
    write_robustness_evidence_report(
        output_path=output,
        materiality_path=materiality,
        identification_path=identification,
        influence_path=influence,
        precision_path=precision,
    )
    console.print(f"Wrote robustness report from registered artifacts to {output}")


@app.command("temporal-extension")
def temporal_extension(
    config: ConfigPathOption = Path("configs/extensions.yaml"),
    baseline_config: ConfigPathOption = Path("configs/baseline.yaml"),
    output: OutputPathOption = Path("reports/generated/temporal_extension_report.md"),
) -> None:
    """Report the post-2013 temporal-extension gate with frozen vintage metadata."""
    extension = load_extension_config(config)
    baseline = load_baseline_config(baseline_config)
    portfolio_sets = _compatible_extension_portfolio_sets(extension, tuple(baseline.portfolio_sets))
    freeze = _temporal_freeze_from_config(extension)
    missing_paths = missing_inputs(TEMPORAL_EVIDENCE_INPUTS)
    if missing_paths:
        write_blocked_temporal_report(
            output_path=output,
            freeze=freeze,
            missing_inputs=missing_paths,
        )
        raise ReplicationBlockError(
            "Wrote blocked temporal extension report; the extension report requires the "
            f"registered H2 artifacts: {_format_paths(missing_paths)}"
        )
    stability_path, evaluation_table_path = TEMPORAL_EVIDENCE_INPUTS
    write_temporal_evidence_report(
        output_path=output,
        freeze=freeze,
        stability_path=stability_path,
        evaluation_table_path=evaluation_table_path,
    )
    console.print(
        f"Wrote temporal extension report from registered artifacts to {output} "
        f"for {len(portfolio_sets)} compatible portfolio sets"
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
    """Report the registered regime-stability outcomes."""
    validated = load_regime_config(config)
    required_paths = (Path(validated.base_config), *REGIME_EVIDENCE_INPUTS)
    missing_paths = missing_inputs(required_paths)
    if missing_paths:
        write_blocked_regime_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked regime report; the regime report requires the base configuration "
            f"and the registered H3 artifacts: {_format_paths(missing_paths)}"
        )
    equivalence_path, pooled_beta_path = REGIME_EVIDENCE_INPUTS
    write_regime_evidence_report(
        output_path=output,
        equivalence_path=equivalence_path,
        pooled_beta_path=pooled_beta_path,
    )
    console.print(f"Wrote regime stability report from registered artifacts to {output}")


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
    missing_paths = missing_inputs(OUT_OF_SAMPLE_EVIDENCE_INPUTS)
    if missing_paths:
        write_blocked_oos_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked out-of-sample report; the registered falsification run has not "
            f"produced its evaluation artifacts: {_format_paths(missing_paths)}"
        )
    # This branch used to raise that "panel-specific forecast assembly is not
    # frozen", which stopped being true once scripts/run_out_of_sample.py ran the
    # frozen design. The report is written by that script alongside the tables it
    # summarises, so the gate here verifies the pair rather than rewriting one
    # from the other and risking the two drifting apart.
    if not output.is_file():
        raise ReplicationBlockError(
            "Out-of-sample evaluation artifacts exist but the report does not; run "
            "scripts/run_out_of_sample.py, which writes both together"
        )
    typer.echo(
        "Out-of-sample falsification is generated from the frozen design for "
        f"{validated.out_of_sample.confirmatory_model}; see {output.as_posix()}"
    )


@app.command("build-report")
def build_report(
    config: ConfigPathOption,
    output: OutputPathOption = Path("reports/generated/manuscript_output_report.md"),
) -> None:
    """Report manuscript-output traceability against the generated reports."""
    load_reporting_config(config)
    required_paths = (MANUSCRIPT_PATH, MANUSCRIPT_ARTIFACT_MAP_PATH, *UPSTREAM_GENERATED_REPORTS)
    missing_paths = missing_inputs(required_paths)
    if missing_paths:
        write_blocked_manuscript_report(output_path=output, missing_inputs=missing_paths)
        raise ReplicationBlockError(
            "Wrote blocked manuscript report; manuscript outputs require the manuscript, its "
            f"artifact map, and the generated reports: {_format_paths(missing_paths)}"
        )
    write_manuscript_output_report(
        output_path=output,
        manuscript_path=MANUSCRIPT_PATH,
        artifact_map_path=MANUSCRIPT_ARTIFACT_MAP_PATH,
        upstream_report_paths=UPSTREAM_GENERATED_REPORTS,
    )
    console.print(f"Wrote manuscript output report from mapped artifacts to {output}")


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


def _format_paths(paths: tuple[Path, ...]) -> str:
    return ", ".join(path.as_posix() for path in paths)


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
