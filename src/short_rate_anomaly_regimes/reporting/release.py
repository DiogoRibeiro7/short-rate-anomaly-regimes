"""Release hygiene checks and release artifact writers."""

from __future__ import annotations

import json
import subprocess
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from short_rate_anomaly_regimes.provenance import sha256_file

ReleaseSeverity = Literal["critical", "major", "minor"]

DISALLOWED_RELEASE_PREFIXES: tuple[str, ...] = (
    "prompts/",
    "references/private/",
    "artifacts/tmp/",
)
DISALLOWED_RELEASE_FILES: frozenset[str] = frozenset(
    {
        "artifacts/environment/manifest.json",
        "data/catalog.duckdb",
    }
)
ALLOWED_PRIVATE_REFERENCE_DOCS: frozenset[str] = frozenset({"references/private/README.md"})
CHECKSUM_EXCLUDED_PREFIXES: tuple[str, ...] = (
    *DISALLOWED_RELEASE_PREFIXES,
    "artifacts/release/",
)
CHECKSUM_EXCLUDED_FILES: frozenset[str] = DISALLOWED_RELEASE_FILES | frozenset(
    {
        "docs/RELEASE_NOTES.md",
        "reports/generated/adversarial_code_audit.md",
        "reports/generated/adversarial_econometric_audit.md",
    }
)

REQUIRED_EMPIRICAL_RELEASE_INPUTS: tuple[str, ...] = (
    "data/processed/factors/short_rate_factors.parquet",
    "data/processed/extension/monthly_panel.parquet",
    "artifacts/estimates/time_series",
    "artifacts/estimates/cross_section",
    "artifacts/tables/factors",
    "artifacts/tables/time_series",
    "artifacts/tables/cross_section",
)


@dataclass(frozen=True, slots=True)
class ReleaseIssue:
    """One release gate finding."""

    severity: ReleaseSeverity
    issue_id: str
    location: str
    failure_mechanism: str
    required_fix: str


def normalise_repo_path(path: Path) -> str:
    """Return a stable POSIX-style relative path."""
    return path.as_posix().lstrip("./")


def is_disallowed_release_path(path: str) -> bool:
    """Return whether a path must never be included in a public release."""
    normalised = normalise_repo_path(Path(path))
    if normalised in ALLOWED_PRIVATE_REFERENCE_DOCS:
        return False
    return normalised in DISALLOWED_RELEASE_FILES or any(
        normalised.startswith(prefix) for prefix in DISALLOWED_RELEASE_PREFIXES
    )


def is_checksum_candidate(path: str) -> bool:
    """Return whether a tracked path belongs in the release checksum manifest."""
    normalised = normalise_repo_path(Path(path))
    return normalised not in CHECKSUM_EXCLUDED_FILES and not any(
        normalised.startswith(prefix) for prefix in CHECKSUM_EXCLUDED_PREFIXES
    )


def tracked_files(cwd: Path = Path(".")) -> tuple[Path, ...]:
    """Return tracked and non-ignored source files in deterministic order."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=cwd,
        capture_output=True,
        check=True,
        text=True,
    )
    return tuple(Path(line) for line in result.stdout.splitlines() if line)


def disallowed_tracked_paths(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Return release-forbidden paths present in a candidate tracked-file list."""
    return tuple(
        normalise_repo_path(path)
        for path in paths
        if is_disallowed_release_path(normalise_repo_path(path))
    )


def build_checksum_manifest(
    *,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> list[dict[str, str]]:
    """Build SHA-256 records for release-eligible source and public artifact files."""
    selected_paths = paths if paths is not None else tracked_files(cwd)
    records: list[dict[str, str]] = []
    for path in sorted(selected_paths, key=normalise_repo_path):
        relative = normalise_repo_path(path)
        full_path = cwd / path
        if is_checksum_candidate(relative) and full_path.is_file():
            records.append({"path": relative, "sha256": sha256_file(full_path)})
    return records


def write_checksum_manifest(
    *,
    output_path: Path,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> None:
    """Write a sha256sum-compatible checksum manifest."""
    records = build_checksum_manifest(cwd=cwd, paths=paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "\n".join(f"{record['sha256']}  {record['path']}" for record in records) + "\n",
        encoding="utf-8",
    )


def build_sbom(*, pyproject_path: Path, lock_path: Path) -> dict[str, Any]:
    """Build a minimal software bill of materials from the Poetry lock file."""
    project_data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    project = project_data["project"]
    packages: list[dict[str, Any]] = []
    for package in lock_data.get("package", []):
        packages.append(
            {
                "name": package["name"],
                "version": package["version"],
                "scope": sorted(package.get("groups", [])),
                "optional": bool(package.get("optional", False)),
                "python_versions": package.get("python-versions", ""),
                "file_hashes": [
                    file_record["hash"]
                    for file_record in package.get("files", [])
                    if isinstance(file_record, dict) and "hash" in file_record
                ],
            }
        )
    return {
        "bom_format": "custom-poetry-lock-sbom",
        "schema_version": 1,
        "project": {
            "name": project["name"],
            "version": project["version"],
            "requires_python": project["requires-python"],
            "license": project["license"],
        },
        "lock_file": {
            "path": normalise_repo_path(lock_path),
            "sha256": sha256_file(lock_path),
        },
        "packages": sorted(packages, key=lambda item: (item["name"], item["version"])),
    }


def write_sbom(*, output_path: Path, pyproject_path: Path, lock_path: Path) -> None:
    """Write a deterministic JSON software bill of materials."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            build_sbom(pyproject_path=pyproject_path, lock_path=lock_path),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def build_release_issues(
    *,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> list[ReleaseIssue]:
    """Build release gate issues for the current source checkout."""
    selected_paths = paths if paths is not None else tracked_files(cwd)
    issues: list[ReleaseIssue] = []
    for path in disallowed_tracked_paths(selected_paths):
        issues.append(
            ReleaseIssue(
                severity="critical",
                issue_id="restricted_path_tracked",
                location=path,
                failure_mechanism="A prompt, restricted source, temporary artifact, or local "
                "catalog "
                "would be included in the release.",
                required_fix="Remove the path from Git tracking and keep it ignored locally.",
            )
        )

    missing_inputs = [
        path for path in REQUIRED_EMPIRICAL_RELEASE_INPUTS if not (cwd / path).exists()
    ]
    if missing_inputs:
        issues.append(
            ReleaseIssue(
                severity="major",
                issue_id="empirical_artifacts_missing",
                location=", ".join(missing_inputs),
                failure_mechanism="The repository cannot reproduce manuscript tables or extension "
                "claims from a fresh checkout with the current public inputs.",
                required_fix="Freeze source definitions, register permitted data, generate the "
                "baseline and extension artifacts, and rerun release-audit.",
            )
        )

    if not (cwd / "poetry.lock").is_file():
        issues.append(
            ReleaseIssue(
                severity="critical",
                issue_id="missing_poetry_lock",
                location="poetry.lock",
                failure_mechanism="Dependency resolution is not pinned for clean-room "
                "reproduction.",
                required_fix="Regenerate and commit poetry.lock before release.",
            )
        )
    return issues


def release_verdict(issues: list[ReleaseIssue]) -> dict[str, Any]:
    """Classify release status from issues."""
    critical = [issue for issue in issues if issue.severity == "critical"]
    major = [issue for issue in issues if issue.severity == "major"]
    return {
        "critical_issue_count": len(critical),
        "major_issue_count": len(major),
        "source_release": "blocked" if critical else "permitted",
        "empirical_release": "blocked" if critical or major else "permitted",
        "release_verdict": "do_not_release" if critical else "source_only_release_ready",
    }


def write_release_gate(
    *,
    output_path: Path,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> list[ReleaseIssue]:
    """Write the machine-readable release gate report."""
    issues = build_release_issues(cwd=cwd, paths=paths)
    payload = {
        "verdict": release_verdict(issues),
        "issues": [asdict(issue) for issue in issues],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return issues


def render_release_notes(issues: list[ReleaseIssue]) -> str:
    """Render release notes with required replication-status categories."""
    verdict = release_verdict(issues)
    lines = [
        "# Release Notes",
        "",
        "## Release Verdict",
        "",
        f"- Source-code release: `{verdict['source_release']}`",
        f"- Empirical-results release: `{verdict['empirical_release']}`",
        f"- Critical issues: `{verdict['critical_issue_count']}`",
        f"- Major issues: `{verdict['major_issue_count']}`",
        "",
        "## Exact Results",
        "",
        "- No empirical table is currently classified as exact replication.",
        "",
        "## Approximate Results",
        "",
        "- No empirical table is currently classified as approximate reconstruction.",
        "",
        "## Blocked Results",
        "",
        "- Baseline replication, temporal extension, monetary-regime stability, shock "
        "decomposition, out-of-sample falsification, and manuscript numerical conclusions "
        "remain blocked by missing generated empirical artifacts.",
        "",
        "## Contradicted Results",
        "",
        "- No contradiction is currently recorded because the empirical comparison has not run.",
        "",
        "## Major Unresolved Issues",
        "",
    ]
    major_issues = [issue for issue in issues if issue.severity == "major"]
    if major_issues:
        lines.extend(
            f"- `{issue.issue_id}` at `{issue.location}`: {issue.failure_mechanism}"
            for issue in major_issues
        )
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Restricted Materials",
            "",
            "Copyrighted articles, publisher supplements, `prompts/`, credentials, local catalogs, "
            "and temporary artifacts are excluded from the release.",
            "",
            "## Reproduction",
            "",
            "Use `make check` and `make release-check` from a clean checkout. Public data "
            "acquisition remains disabled until exact source definitions are frozen.",
            "",
        ]
    )
    return "\n".join(lines)


def write_release_notes(*, output_path: Path, issues: list[ReleaseIssue]) -> None:
    """Write markdown release notes."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_release_notes(issues), encoding="utf-8")


def render_adversarial_code_audit(issues: list[ReleaseIssue]) -> str:
    """Render a code-audit report ordered by release severity."""
    lines = [
        "# Adversarial Code Audit",
        "",
        "## Release Verdict",
        "",
        "Source-only release is permitted when no critical restricted-path issue is present. "
        "Empirical-results release is blocked while major missing-input issues remain.",
        "",
        "## Findings",
        "",
    ]
    if not issues:
        lines.append("No critical or major release issue was detected.")
    else:
        severity_rank = {"critical": 0, "major": 1, "minor": 2}
        for issue in sorted(issues, key=lambda item: severity_rank[item.severity]):
            lines.extend(
                [
                    f"### {issue.severity.upper()}: {issue.issue_id}",
                    "",
                    f"- Location: `{issue.location}`",
                    f"- Failure mechanism: {issue.failure_mechanism}",
                    "- Affected results: source-only release gate or empirical-result release "
                    "gate.",
                    "- Minimal reproduction: run `poetry run srar release-audit`.",
                    f"- Required fix: {issue.required_fix}",
                    "",
                ]
            )
    lines.extend(
        [
            "## Targeted Checks",
            "",
            "- Restricted paths are detected before release.",
            "- Checksum records exclude prompt files, restricted sources, local catalogs, and "
            "temporary artifacts.",
            "- Dependency disclosure is generated from `poetry.lock`.",
            "- Empirical commands remain blocked rather than rendering selective placeholder "
            "tables.",
            "",
        ]
    )
    return "\n".join(lines)


def render_adversarial_econometric_audit(issues: list[ReleaseIssue]) -> str:
    """Render an econometric audit focused on claims threatened by the current evidence state."""
    del issues
    return "\n".join(
        [
            "# Adversarial Econometric Audit",
            "",
            "## Verdict",
            "",
            "Classification: `potentially_publishable_after_major_revision`.",
            "",
            "The current contribution is a release-ready research scaffold, not an identified "
            "empirical asset-pricing result.",
            "",
            "## Findings",
            "",
            "### MAJOR: State-variable interpretation is not yet identified",
            "",
            "- Claim threatened: a short-rate innovation prices anomaly returns as a stable "
            "hedging state variable.",
            "- Econometric reason: an AR residual is an innovation relative to the fitted rate "
            "model, but it does not by itself separate monetary policy, information, macro news, "
            "or measurement components.",
            "- Decisive diagnostic: compare beta pricing before and after registered shock "
            "decomposition and spanning tests.",
            "- Repair: keep causal interpretation out of non-identification sections and require "
            "the shock-decomposition gate before stronger language.",
            "",
            "### MAJOR: Two-pass inference is unverified under missing generated artifacts",
            "",
            "- Claim threatened: the short-rate factor earns one common cross-sectional price of "
            "risk.",
            "- Econometric reason: factor strength, beta dispersion, sample intersection, and "
            "covariance corrections cannot be evaluated without first-pass and cross-section "
            "artifacts.",
            "- Decisive diagnostic: inspect beta singular values, weak-factor flags, GRS tests, "
            "Fama-MacBeth uncertainty, and leave-one-anomaly-family systems.",
            "- Repair: generate baseline artifacts and rerun robustness diagnostics before "
            "reporting a pricing verdict.",
            "",
            "### MAJOR: Extension and out-of-sample claims are blocked",
            "",
            "- Claim threatened: post-2013 performance, monetary-regime instability, and forecast "
            "falsification.",
            "- Econometric reason: the extension panel and frozen training vintages are absent, so "
            "there is no valid holdout comparison or predeclared regime inference.",
            "- Decisive diagnostic: rerun temporal, regime, shock, and out-of-sample gates after "
            "compatible panels exist.",
            "- Repair: freeze source vintages, produce monthly panels, and preserve null or "
            "unstable results in the reports.",
            "",
        ]
    )


def write_adversarial_reports(
    *,
    code_report_path: Path,
    econometric_report_path: Path,
    issues: list[ReleaseIssue],
) -> None:
    """Write human-readable adversarial release audit reports."""
    code_report_path.parent.mkdir(parents=True, exist_ok=True)
    econometric_report_path.parent.mkdir(parents=True, exist_ok=True)
    code_report_path.write_text(render_adversarial_code_audit(issues), encoding="utf-8")
    econometric_report_path.write_text(
        render_adversarial_econometric_audit(issues),
        encoding="utf-8",
    )
