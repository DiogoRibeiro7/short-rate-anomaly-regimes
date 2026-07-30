"""Command-line interface for the research repository."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from short_rate_anomaly_regimes.config import load_baseline_config, load_project_config
from short_rate_anomaly_regimes.data.acquisition import (
    download_fred_series,
    download_kenneth_french_dataset,
    register_manual_source,
)
from short_rate_anomaly_regimes.data.catalog import build_catalog, load_registry
from short_rate_anomaly_regimes.environment import write_environment_manifest
from short_rate_anomaly_regimes.exceptions import ReplicationBlockError
from short_rate_anomaly_regimes.portfolios.construction import write_construction_manifest

app = typer.Typer(no_args_is_help=True)
console = Console()
ConfigPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]
OutputPathOption = Annotated[Path, typer.Option(dir_okay=False)]
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


@app.command("run-baseline")
def run_baseline(config: ConfigPathOption) -> None:
    """Run the strict replication pipeline."""
    del config
    raise NotImplementedError("Complete Milestones 0 through 7 first")


@app.command("run-regimes")
def run_regimes(config: ConfigPathOption) -> None:
    """Run the regime-stability extension."""
    del config
    raise NotImplementedError("Complete Milestones 9 and 10 first")


@app.command("build-report")
def build_report(config: ConfigPathOption) -> None:
    """Build tables, figures, and the replication report."""
    del config
    raise NotImplementedError("Complete the relevant empirical milestones first")


if __name__ == "__main__":
    app()
