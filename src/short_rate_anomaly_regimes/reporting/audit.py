"""Table-level replication status records and reports."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from short_rate_anomaly_regimes.types import ReplicationStatus

DiscrepancyCause = Literal[
    "unit",
    "sample",
    "date_alignment",
    "source_vintage",
    "portfolio_ordering",
    "missing_values",
    "estimator",
    "covariance",
    "rounding",
    "software",
]

DISCREPANCY_INVESTIGATION_ORDER: tuple[DiscrepancyCause, ...] = (
    "unit",
    "sample",
    "date_alignment",
    "source_vintage",
    "portfolio_ordering",
    "missing_values",
    "estimator",
    "covariance",
    "rounding",
    "software",
)

ALLOWED_STATUSES = tuple(status.value for status in ReplicationStatus)


@dataclass(frozen=True, slots=True)
class TableTarget:
    """One frozen published table target from the manifest."""

    target_id: str
    source_location: str
    description: str
    portfolio_set: str
    model: str
    estimator: str
    tolerance_rule: str
    status: str


@dataclass(frozen=True, slots=True)
class TableAuditRecord:
    """Comparison between one published target and one repository output."""

    target_id: str
    source_location: str
    generated_artifact: str
    status: ReplicationStatus
    statistic: str
    published_value: float | None
    replicated_value: float | None
    absolute_difference: float | None
    relative_difference: float | None
    tolerance_rule: str
    tolerance_value: float | None
    discrepancy_stage: str | None
    independent_check: str
    notes: str


def load_table_targets(path: Path) -> tuple[TableTarget, ...]:
    """Load the frozen table target manifest."""
    frame = pd.read_csv(path)
    required = {
        "target_id",
        "source_location",
        "description",
        "portfolio_set",
        "model",
        "estimator",
        "tolerance_rule",
        "status",
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Table target manifest is missing columns: {', '.join(sorted(missing))}")
    if frame["target_id"].duplicated().any():
        raise ValueError("Table target manifest contains duplicate target ids")
    return tuple(
        TableTarget(
            target_id=str(row.target_id),
            source_location=str(row.source_location),
            description=str(row.description),
            portfolio_set=str(row.portfolio_set),
            model=str(row.model),
            estimator=str(row.estimator),
            tolerance_rule=str(row.tolerance_rule),
            status=str(row.status),
        )
        for row in frame.itertuples(index=False)
    )


def tolerance_from_rule(rule: str) -> float:
    """Map predeclared tolerance rules to numerical absolute tolerances."""
    if rule == "published_rounding":
        return 5e-4
    if rule == "coefficient_rounding":
        return 5e-5
    if rule == "not_applicable":
        return 0.0
    raise ValueError(f"Unsupported tolerance rule: {rule}")


def compare_statistic(
    *,
    target: TableTarget,
    statistic: str,
    published_value: float,
    replicated_value: float,
    generated_artifact: Path,
    reconstructed: bool = False,
    independent_check: str = "not_run",
) -> TableAuditRecord:
    """Compare one generated statistic with a published target."""
    tolerance = tolerance_from_rule(target.tolerance_rule)
    absolute_difference = abs(replicated_value - published_value)
    denominator = abs(published_value)
    relative_difference = None if denominator == 0.0 else absolute_difference / denominator
    if absolute_difference <= tolerance:
        status = (
            ReplicationStatus.APPROXIMATELY_REPRODUCED
            if reconstructed
            else ReplicationStatus.REPRODUCED
        )
        discrepancy_stage = None
        notes = "Generated statistic is within the predeclared tolerance."
    else:
        status = ReplicationStatus.CONTRADICTED
        discrepancy_stage = DISCREPANCY_INVESTIGATION_ORDER[0]
        notes = "Generated statistic exceeds tolerance; investigate differences in order."
    return TableAuditRecord(
        target_id=target.target_id,
        source_location=target.source_location,
        generated_artifact=str(generated_artifact),
        status=status,
        statistic=statistic,
        published_value=float(published_value),
        replicated_value=float(replicated_value),
        absolute_difference=float(absolute_difference),
        relative_difference=relative_difference,
        tolerance_rule=target.tolerance_rule,
        tolerance_value=tolerance,
        discrepancy_stage=discrepancy_stage,
        independent_check=independent_check,
        notes=notes,
    )


def build_missing_input_audit(
    targets: tuple[TableTarget, ...],
    *,
    missing_reason: str,
) -> list[TableAuditRecord]:
    """Create one missing-input audit row per frozen table target."""
    return [
        TableAuditRecord(
            target_id=target.target_id,
            source_location=target.source_location,
            generated_artifact="not_generated",
            status=ReplicationStatus.NOT_REPRODUCIBLE_MISSING_INPUT,
            statistic=target.description,
            published_value=None,
            replicated_value=None,
            absolute_difference=None,
            relative_difference=None,
            tolerance_rule=target.tolerance_rule,
            tolerance_value=None,
            discrepancy_stage=None,
            independent_check="not_run_missing_input",
            notes=missing_reason,
        )
        for target in targets
    ]


def write_audit(records: list[TableAuditRecord], path: Path) -> None:
    """Write an auditable CSV with one row per target statistic."""
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([asdict(record) for record in records])
    if not frame.empty and not set(frame["status"]).issubset(set(ALLOWED_STATUSES)):
        raise ValueError("Audit contains a status outside the allowed replication labels")
    frame.to_csv(path, index=False)


def audit_summary(records: list[TableAuditRecord]) -> pd.Series:
    """Summarise audit status counts."""
    counts = pd.Series([record.status.value for record in records], dtype="string").value_counts()
    return counts.reindex(ALLOWED_STATUSES, fill_value=0).rename("count")


def write_audit_json(records: list[TableAuditRecord], path: Path) -> None:
    """Write machine-readable audit records as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(record) for record in records], indent=2, sort_keys=True),
        encoding="utf-8",
    )


def render_replication_report(
    records: list[TableAuditRecord],
    *,
    title: str = "Replication Report",
) -> str:
    """Render a markdown replication report from audit records."""
    summary = audit_summary(records)
    sections = {
        "reproduced": [r for r in records if r.status == ReplicationStatus.REPRODUCED],
        "approximately_reproduced": [
            r for r in records if r.status == ReplicationStatus.APPROXIMATELY_REPRODUCED
        ],
        "blocked_targets": [
            r for r in records if r.status == ReplicationStatus.NOT_REPRODUCIBLE_MISSING_INPUT
        ],
        "contradicted_targets": [r for r in records if r.status == ReplicationStatus.CONTRADICTED],
    }
    lines = [
        f"# {title}",
        "",
        "## Evidence Availability",
        "",
        "This report distinguishes inaccessible inputs from empirical contradiction.",
        "",
        "## Status Summary",
        "",
    ]
    for status, count in summary.items():
        lines.append(f"- `{status}`: {int(count)}")
    lines.extend(
        [
            "",
            "## Exact And Reconstructed Datasets",
            "",
            "No close substitute is labelled as an exact replication.",
            "",
            "## Reproduced Tables",
            "",
            _format_record_list(sections["reproduced"]),
            "",
            "## Approximate Reproductions",
            "",
            _format_record_list(sections["approximately_reproduced"]),
            "",
            "## Blocked Targets",
            "",
            _format_record_list(sections["blocked_targets"]),
            "",
            "## Contradicted Targets",
            "",
            _format_record_list(sections["contradicted_targets"]),
            "",
            "## Sources Of Numerical Difference",
            "",
            ", ".join(DISCREPANCY_INVESTIGATION_ORDER),
            "",
            "## Baseline Conclusion",
            "",
            _baseline_conclusion(records),
            "",
        ]
    )
    return "\n".join(lines)


def write_replication_report(records: list[TableAuditRecord], path: Path) -> None:
    """Write the markdown replication report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_replication_report(records), encoding="utf-8")


def _format_record_list(records: list[TableAuditRecord]) -> str:
    if not records:
        return "None."
    return "\n".join(
        f"- `{record.target_id}` ({record.source_location}): {record.notes}" for record in records
    )


def _baseline_conclusion(records: list[TableAuditRecord]) -> str:
    if any(record.status == ReplicationStatus.CONTRADICTED for record in records):
        return "At least one target is contradicted after applying the frozen tolerance rules."
    if any(record.status == ReplicationStatus.NOT_REPRODUCIBLE_MISSING_INPUT for record in records):
        return (
            "Baseline replication is blocked by missing inputs; this is not evidence that "
            "the article is unreliable."
        )
    if records and all(record.status == ReplicationStatus.REPRODUCED for record in records):
        return "All audited targets are reproduced within the frozen tolerance rules."
    return "No successful baseline replication conclusion is available yet."
