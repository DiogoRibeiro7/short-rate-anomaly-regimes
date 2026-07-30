"""Command-line interface for the research repository."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from short_rate_anomaly_regimes.config import load_baseline_config
from short_rate_anomaly_regimes.data.catalog import load_registry

app = typer.Typer(no_args_is_help=True)
console = Console()
ConfigPathOption = Annotated[Path, typer.Option(exists=True, dir_okay=False)]


@app.command("validate-config")
def validate_config(config: ConfigPathOption) -> None:
    """Validate the baseline YAML configuration."""
    validated = load_baseline_config(config)
    console.print(
        f"Validated {validated.project.name} in {validated.project.replication_mode} mode"
    )


@app.command("validate-data")
def validate_data(registry: ConfigPathOption) -> None:
    """Validate the source registry without downloading data."""
    validated = load_registry(registry)
    console.print(f"Validated {len(validated.sources)} registered sources")


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
    del config
    raise NotImplementedError("Complete Milestones 2 and 3 first")


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
