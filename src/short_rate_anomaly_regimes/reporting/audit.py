"""Table-level replication status records and reports."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd
import yaml

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

ACCESS_AVAILABILITY_TOKENS: tuple[str, ...] = ("present", "acquired", "located")
_AVAILABILITY_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(rf"(?<!not_){token}") for token in ACCESS_AVAILABILITY_TOKENS
)


def is_accessible_access_status(access_status: object) -> bool:
    """Report whether a data-access status asserts the input is in hand.

    The data-access matrix records availability with several vocabularies:
    ``present_...`` for the private article files, ``acquired_...`` for every
    frozen public download, and ``..._located`` for a named source that has been
    identified. A plain substring test would both miss the whole ``acquired_...``
    family and misread negations such as ``not_located`` or ``not_acquired`` as
    availability, so each token is matched only when it is not directly negated.
    """
    text = str(access_status).strip().lower()
    if not text:
        return False
    return any(pattern.search(text) is not None for pattern in _AVAILABILITY_PATTERNS)


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
    article_manifest_path: Path = Path("artifacts/evidence/article_manifest.json"),
    data_access_path: Path = Path("research/data_access_matrix.csv"),
    source_registry_path: Path = Path("configs/data_sources.yaml"),
    baseline_config_path: Path = Path("configs/baseline.yaml"),
    robustness_report_path: Path = Path("reports/generated/robustness_report.md"),
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
    article_manifest = _load_json_if_present(article_manifest_path)
    data_access = _load_csv_if_present(data_access_path)
    source_registry = _load_yaml_if_present(source_registry_path)
    baseline_config = _load_yaml_if_present(baseline_config_path)
    robustness_report = (
        robustness_report_path.read_text(encoding="utf-8")
        if robustness_report_path.is_file()
        else "Weak-factor diagnostics have not been generated."
    )
    lines = [
        f"# {title}",
        "",
        "## Bibliographic Target And Versions",
        "",
        _render_bibliographic_target(article_manifest),
        "",
        "## Accessible And Inaccessible Evidence",
        "",
        "This report distinguishes inaccessible inputs from empirical contradiction.",
        "",
        _render_evidence_availability(article_manifest, data_access),
        "",
        "## Exact Source Definitions",
        "",
        _render_source_definitions(data_access, source_registry),
        "",
        "## Factor Reconstruction",
        "",
        _render_factor_reconstruction(baseline_config),
        "",
        "## Portfolio Reconstruction",
        "",
        _render_portfolio_reconstruction(baseline_config, source_registry),
        "",
        "## Estimator Reconstruction",
        "",
        _render_estimator_reconstruction(baseline_config),
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
            "## Weak-Factor And Influence Diagnostics",
            "",
            _summarise_robustness_report(robustness_report),
            "",
            "## Deviations From The Article And Their Causes",
            "",
            _render_deviations(data_access),
            "",
            "## Bounded Conclusion",
            "",
            _baseline_conclusion(records),
            "",
            "## Appendix: Complete Audit Table",
            "",
            _render_audit_table(records),
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


def _load_json_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return loaded


def _load_yaml_if_present(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected mapping YAML in {path}")
    return loaded


def _load_csv_if_present(path: Path) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    return pd.read_csv(path)


def _render_bibliographic_target(article_manifest: dict[str, Any]) -> str:
    if not article_manifest:
        return "Bibliographic metadata are not available."
    authors = ", ".join(str(author) for author in article_manifest.get("authors", []))
    files = article_manifest.get("files", [])
    file_lines: list[str] = []
    if isinstance(files, list):
        for file_record in files:
            if isinstance(file_record, dict):
                file_lines.append(
                    "- "
                    f"`{file_record.get('role', 'unknown')}`: "
                    f"SHA-256 `{file_record.get('sha256', 'missing')}`; "
                    f"{file_record.get('access_note', 'access note unavailable')}"
                )
    return "\n".join(
        [
            f"- Target: {authors}. {article_manifest.get('publication_date', 'n.d.')}. "
            f"{article_manifest.get('title', 'Untitled')}. "
            f"{article_manifest.get('journal', 'Unknown journal')} "
            f"{article_manifest.get('volume', '')}"
            f"({article_manifest.get('issue', '')}), "
            f"{article_manifest.get('pages', '')}.",
            f"- DOI: `{article_manifest.get('doi', 'not_recorded')}`",
            f"- Evidence-pack status: `{article_manifest.get('status', 'unknown')}`",
            *file_lines,
        ]
    )


def _render_evidence_availability(
    article_manifest: dict[str, Any],
    data_access: pd.DataFrame,
) -> str:
    lines: list[str] = []
    if article_manifest:
        lines.append("- Article and publisher supplement metadata are present as hashes only.")
    if data_access.empty:
        lines.append("- Data-access matrix is unavailable.")
        return "\n".join(lines)
    strict_rows = data_access[data_access["strict_replication_role"] != "extension"]
    accessible_mask = strict_rows["access_status"].map(is_accessible_access_status).astype(bool)
    accessible = strict_rows[accessible_mask]
    inaccessible = strict_rows[~accessible_mask]
    lines.append(f"- Accessible or located strict-replication evidence rows: `{len(accessible)}`")
    lines.append(
        f"- Inaccessible or pending strict-replication evidence rows: `{len(inaccessible)}`"
    )
    for row in inaccessible.itertuples(index=False):
        lines.append(f"- Pending `{row.source_id}`: {row.notes}")
    return "\n".join(lines)


def _render_source_definitions(
    data_access: pd.DataFrame,
    source_registry: dict[str, Any],
) -> str:
    sources = source_registry.get("sources", [])
    source_by_id = {
        str(source.get("id")): source
        for source in sources
        if isinstance(source, dict) and source.get("id") is not None
    }
    if data_access.empty:
        return "Source definitions are unavailable."
    lines = [
        "| Source | Exact Definition Verified | Access Status | Provider Or Category | Raw Path |",
        "|---|---:|---|---|---|",
    ]
    strict_rows = data_access[data_access["strict_replication_role"] != "extension"]
    for row in strict_rows.itertuples(index=False):
        source = source_by_id.get(str(row.source_id), {})
        provider = source.get("provider") or source.get("category") or "not_recorded"
        raw_path = source.get("raw_path") or source.get("expected_path") or "not_recorded"
        lines.append(
            f"| `{row.source_id}` | `{row.exact_definition_verified}` | "
            f"`{row.access_status}` | {provider} | `{raw_path}` |"
        )
    return "\n".join(lines)


def _render_factor_reconstruction(baseline_config: dict[str, Any]) -> str:
    short_rate = _mapping(baseline_config.get("short_rate"))
    innovation = _mapping(short_rate.get("innovation"))
    sample = _mapping(baseline_config.get("sample"))
    returns = _mapping(baseline_config.get("returns"))
    return "\n".join(
        [
            f"- Sample: `{sample.get('start', 'unknown')}` to `{sample.get('end', 'unknown')}`, "
            f"`{sample.get('frequency', 'unknown')}`, aligned to "
            f"`{sample.get('date_alignment', 'unknown')}`.",
            f"- Primary short-rate source id: `{short_rate.get('primary_series', 'unknown')}`.",
            f"- Alternative short-rate source ids: "
            f"`{', '.join(short_rate.get('alternatives', []) or ['none'])}`.",
            f"- Innovation model: `{innovation.get('model', 'unknown')}` with "
            f"`{innovation.get('estimation', 'unknown')}` estimation and "
            f"`{innovation.get('residual_timing', 'unknown')}` residual timing.",
            f"- Return units: `{returns.get('units', 'unknown')}`.",
        ]
    )


def _render_portfolio_reconstruction(
    baseline_config: dict[str, Any],
    source_registry: dict[str, Any],
) -> str:
    portfolio_sets = baseline_config.get("portfolio_sets", [])
    sources = source_registry.get("sources", [])
    registered_portfolios = [
        str(source.get("id"))
        for source in sources
        if isinstance(source, dict) and source.get("category") == "portfolio_returns"
    ]
    return "\n".join(
        [
            f"- Baseline configured portfolio sets: `{', '.join(portfolio_sets)}`.",
            f"- Registry portfolio-return sources: `{', '.join(registered_portfolios)}`.",
            "- Portfolio panels are not silently substituted; unavailable author or WRDS inputs "
            "remain missing-input rows until manually registered or reconstructed under the "
            "documented reconstruction label.",
        ]
    )


def _render_estimator_reconstruction(baseline_config: dict[str, Any]) -> str:
    asset_pricing = _mapping(baseline_config.get("asset_pricing"))
    time_series = _mapping(asset_pricing.get("time_series"))
    cross_section = _mapping(asset_pricing.get("cross_section"))
    return "\n".join(
        [
            f"- Time-series intercept: `{time_series.get('include_intercept', 'unknown')}`.",
            f"- Time-series covariance: `{time_series.get('covariance', 'unknown')}` with "
            f"`{time_series.get('nw_lags', 'unknown')}` lags.",
            f"- Cross-sectional estimators: "
            f"`{', '.join(cross_section.get('estimators', []) or ['unknown'])}`.",
            f"- Zero-beta intercept: "
            f"`{cross_section.get('include_zero_beta_intercept', 'unknown')}`.",
            f"- Shanken-style correction: `{cross_section.get('shanken_correction', 'unknown')}`.",
            f"- Weak-factor diagnostics: "
            f"`{cross_section.get('weak_factor_diagnostics', 'unknown')}`.",
        ]
    )


def _summarise_robustness_report(report: str) -> str:
    relevant_lines = [
        line
        for line in report.splitlines()
        if line.startswith("Verdict:")
        or line.startswith("- `")
        or "No significant-only robustness reporting" in line
    ]
    if not relevant_lines:
        return "Weak-factor and influence diagnostics have not produced a baseline verdict."
    return "\n".join(relevant_lines)


def _render_deviations(data_access: pd.DataFrame) -> str:
    lines = [
        "Potential numerical differences must be investigated in this fixed order: "
        f"{', '.join(DISCREPANCY_INVESTIGATION_ORDER)}.",
    ]
    if data_access.empty:
        lines.append("- Source-level deviations cannot be classified because the matrix is absent.")
        return "\n".join(lines)
    strict_rows = data_access[data_access["strict_replication_role"] != "extension"]
    unresolved = strict_rows[
        strict_rows["exact_definition_verified"].astype("string").str.lower() != "true"
    ]
    if unresolved.empty:
        lines.append("- No source-definition deviation is currently recorded.")
        return "\n".join(lines)
    for row in unresolved.itertuples(index=False):
        lines.append(f"- `{row.source_id}`: {row.notes}")
    return "\n".join(lines)


def _render_audit_table(records: list[TableAuditRecord]) -> str:
    if not records:
        return "No audit records are available."
    lines = [
        "| Target | Source Location | Status | Statistic | Generated Artifact | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for record in records:
        lines.append(
            "| "
            f"`{_escape_table_cell(record.target_id)}` | "
            f"`{_escape_table_cell(record.source_location)}` | "
            f"`{record.status.value}` | "
            f"{_escape_table_cell(record.statistic)} | "
            f"`{_escape_table_cell(record.generated_artifact)}` | "
            f"{_escape_table_cell(record.notes)} |"
        )
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _escape_table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


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
