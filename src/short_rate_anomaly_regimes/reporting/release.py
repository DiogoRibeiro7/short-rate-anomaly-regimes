"""Release hygiene checks and release artifact writers."""

from __future__ import annotations

import json
import subprocess
import tomllib
import zipfile
from csv import DictReader
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

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
    "data/processed/factors/short_rate_innovations_baseline.parquet",
    "data/processed/extension/monthly_panel.parquet",
    "artifacts/estimates/time_series",
    "artifacts/estimates/cross_section",
    "artifacts/tables/factors",
    "artifacts/tables/time_series",
    "artifacts/tables/cross_section",
)

# Files a recipient needs in order to rebuild the empirical artifacts from the
# frozen public sources. These are checked against the same distributed-file set
# as REQUIRED_EMPIRICAL_RELEASE_INPUTS, so a rebuild path that exists only on the
# author's disk cannot satisfy the gate either.
REQUIRED_EMPIRICAL_REBUILD_INPUTS: tuple[str, ...] = (
    "Makefile",
    "configs/baseline.yaml",
    "configs/data_sources.yaml",
    "configs/extensions.yaml",
    "configs/regimes.yaml",
    "research/data_access_matrix.csv",
    "scripts/acquire_short_rates.py",
    "scripts/acquire_french_factors.py",
    "scripts/acquire_anomaly_portfolios.py",
    "scripts/acquire_comparator_factors.py",
    "scripts/reconstruct_rate_innovations.py",
    "scripts/build_baseline_panel.py",
    "scripts/build_comparator_panel.py",
    "scripts/build_extension_panels.py",
    "scripts/build_regime_panel.py",
    "scripts/run_baseline_replication.py",
    "scripts/run_useless_factor_bootstrap.py",
    "scripts/run_temporal_extension.py",
    "scripts/run_regime_equivalence.py",
    "scripts/run_regime_interactions.py",
    "scripts/analyse_regime_power.py",
    "scripts/build_manuscript_tables.py",
    "scripts/build_manuscript_figures.py",
    "scripts/audit_rate_aggregation.py",
    "scripts/audit_portfolio_source_compatibility.py",
    "scripts/audit_published_targets.py",
    "scripts/run_h1_materiality.py",
    "scripts/run_h4c_precision.py",
    "scripts/run_weak_factor_diagnostics.py",
    "scripts/verify_title.py",
    "scripts/verify_manuscript.py",
    # The acquisition provenance manifests. Each carries the frozen expected
    # SHA-256 for one source, and `acquire_data` reads them to decide whether a
    # download reproduces the frozen vintage or the rebuild must abort. Shipping
    # the scripts without them leaves a rebuild that downloads whatever a
    # provider serves today with nothing to check it against, which is the exact
    # failure `vintage_integrity` claims is impossible. They were distributed in
    # practice but never required, so the claim rested on habit.
    "artifacts/provenance/short_rate",
    "artifacts/provenance/kenneth_french",
    "artifacts/provenance/portfolios",
    "artifacts/provenance/comparators",
)
REBUILD_ENTRY_POINT_FILE = "Makefile"
REBUILD_ENTRY_POINT_TARGET = "reproduce"
REBUILD_ENTRY_POINT = f"make {REBUILD_ENTRY_POINT_TARGET}"

#: The rebuild status when nothing blocks it. The qualifier is load bearing: the
#: archive ships a hash-verified rebuild path, which fails safely when a provider
#: has revised a series, but failing safely is not the same property as remaining
#: rebuildable indefinitely. Unqualified "rebuildable from public sources" claimed
#: the second while the code only delivers the first.
REBUILDABLE_WHILE_SOURCES_RETRIEVABLE = "rebuildable_while_frozen_source_bytes_remain_retrievable"
REBUILD_BLOCKING_ISSUE_IDS: frozenset[str] = frozenset(
    {
        "empirical_rebuild_path_incomplete",
        "empirical_rebuild_entry_point_missing",
    }
)

# A directory placeholder is not evidence that a directory carries content.
PLACEHOLDER_FILENAMES: frozenset[str] = frozenset({".gitkeep"})

RELEASE_CONFIG_PATHS: tuple[Path, ...] = (
    Path("configs/baseline.yaml"),
    Path("configs/extensions.yaml"),
    Path("configs/regimes.yaml"),
    Path("configs/reporting.yaml"),
    Path("configs/data_sources.yaml"),
)
ARCHIVE_TIMESTAMP = (2026, 7, 31, 0, 0, 0)


@dataclass(frozen=True, slots=True)
class ReleaseIssue:
    """One release gate finding."""

    severity: ReleaseSeverity
    issue_id: str
    location: str
    failure_mechanism: str
    required_fix: str


def normalise_repo_path(path: Path) -> str:
    """Return a stable POSIX-style relative path.

    Only a leading ``./`` is removed. ``str.lstrip`` takes a set of characters
    rather than a prefix, so stripping ``"./"`` also ate the leading dot of every
    dotfile: ``.zenodo.json`` was recorded as ``zenodo.json``, and a recipient
    verifying the checksum manifest could not find the file it names.
    """
    posix = path.as_posix()
    while posix.startswith("./"):
        posix = posix[2:]
    return posix


def is_disallowed_release_path(path: str) -> bool:
    """Return whether a path must never be included in a public release."""
    normalised = normalise_repo_path(Path(path))
    return normalised in DISALLOWED_RELEASE_FILES or any(
        normalised.startswith(prefix) for prefix in DISALLOWED_RELEASE_PREFIXES
    )


def is_checksum_candidate(path: str) -> bool:
    """Return whether a tracked path belongs in the release checksum manifest."""
    normalised = normalise_repo_path(Path(path))
    return normalised not in CHECKSUM_EXCLUDED_FILES and not any(
        normalised.startswith(prefix) for prefix in CHECKSUM_EXCLUDED_PREFIXES
    )


def is_archive_candidate(path: str) -> bool:
    """Return whether a file may be included in the source-release archive."""
    normalised = normalise_repo_path(Path(path))
    return (
        not is_disallowed_release_path(normalised)
        and not normalised.startswith("artifacts/release/")
        and not normalised.startswith("references/private/")
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


def public_processed_data_files(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Return processed-data files that would require redistribution review."""
    return tuple(
        normalise_repo_path(path)
        for path in paths
        if normalise_repo_path(path).startswith("data/processed/")
        and path.name != ".gitkeep"
        and not is_disallowed_release_path(normalise_repo_path(path))
    )


def disallowed_tracked_paths(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Return release-forbidden paths present in a candidate tracked-file list."""
    return tuple(
        normalise_repo_path(path)
        for path in paths
        if is_disallowed_release_path(normalise_repo_path(path))
    )


def distributed_release_files(
    *,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> frozenset[str]:
    """Return the paths a release recipient actually receives.

    Presence is evaluated against the membership of the source archive that
    :func:`write_source_archive` builds, never against the author's working
    tree. A file that exists locally but is ignored, or excluded from the
    archive, is absent as far as this gate is concerned.
    """
    return frozenset(
        normalise_repo_path(path) for path in build_archive_file_list(cwd=cwd, paths=paths)
    )


def is_distributed_path(required: str, distributed: frozenset[str]) -> bool:
    """Return whether a required file or directory is carried by the release archive.

    A directory counts as distributed only when the archive carries at least one
    member below it that is not a directory placeholder; a lone ``.gitkeep`` is
    an empty directory, not an artifact.
    """
    normalised = normalise_repo_path(Path(required))
    if normalised in distributed:
        return True
    prefix = f"{normalised}/"
    return any(
        member.startswith(prefix) and Path(member).name not in PLACEHOLDER_FILENAMES
        for member in distributed
    )


def missing_distributed_paths(
    required: tuple[str, ...],
    distributed: frozenset[str],
) -> tuple[str, ...]:
    """Return required paths the release archive does not carry."""
    return tuple(path for path in required if not is_distributed_path(path, distributed))


def declares_make_target(makefile_text: str, target: str) -> bool:
    """Return whether a Makefile declares a rule for ``target``."""
    for line in makefile_text.splitlines():
        if not line or line.startswith("\t") or line.lstrip().startswith("#") or ":" not in line:
            continue
        names = line.split(":", 1)[0].split()
        if target in names and not names[0].startswith("."):
            return True
    return False


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
        newline="\n",
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
        newline="\n",
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

    processed_data = public_processed_data_files(selected_paths)
    if processed_data:
        issues.append(
            ReleaseIssue(
                severity="major",
                issue_id="processed_data_redistribution_unverified",
                location=", ".join(processed_data),
                failure_mechanism="Processed data files would be included without a recorded "
                "licence and redistribution confirmation.",
                required_fix="Record redistribution rights in the data-access matrix before "
                "including processed data in a release.",
            )
        )

    # Presence is judged against what the recipient gets, not against the
    # author's working tree. Checking ``Path.exists()`` here reported the
    # author's local, gitignored panels as shipped and flipped the empirical
    # verdict to permitted for an archive that carries only placeholders.
    distributed = distributed_release_files(cwd=cwd, paths=selected_paths)

    missing_inputs = missing_distributed_paths(REQUIRED_EMPIRICAL_RELEASE_INPUTS, distributed)
    if missing_inputs:
        issues.append(
            ReleaseIssue(
                severity="major",
                issue_id="empirical_artifacts_missing",
                location=", ".join(missing_inputs),
                failure_mechanism="The distributed archive does not carry these generated "
                "artifacts, so a recipient cannot reproduce manuscript tables or extension "
                "claims from the archive alone.",
                required_fix="Record redistribution rights and ship the generated artifacts, or "
                f"release source-only and direct recipients to the `{REBUILD_ENTRY_POINT}` "
                "rebuild path.",
            )
        )

    missing_rebuild_inputs = missing_distributed_paths(
        REQUIRED_EMPIRICAL_REBUILD_INPUTS, distributed
    )
    if missing_rebuild_inputs:
        issues.append(
            ReleaseIssue(
                severity="major",
                issue_id="empirical_rebuild_path_incomplete",
                location=", ".join(missing_rebuild_inputs),
                failure_mechanism="The distributed archive omits acquisition, panel, or "
                "estimation entry points, so a recipient can neither use the shipped artifacts "
                "nor rebuild them from the frozen public sources.",
                required_fix="Ship the acquisition, panel-construction, estimation, and "
                "manuscript scripts together with the frozen source registry and configs.",
            )
        )
    elif not declares_make_target(
        (cwd / REBUILD_ENTRY_POINT_FILE).read_text(encoding="utf-8"),
        REBUILD_ENTRY_POINT_TARGET,
    ):
        issues.append(
            ReleaseIssue(
                severity="major",
                issue_id="empirical_rebuild_entry_point_missing",
                location=REBUILD_ENTRY_POINT_FILE,
                failure_mechanism="The rebuild scripts ship without a single documented entry "
                "point, so the dependency order between acquisition, panels, estimation, "
                "extension, and regimes is left for the recipient to infer.",
                required_fix=f"Declare a `{REBUILD_ENTRY_POINT_TARGET}` target that runs the "
                "pipeline in dependency order.",
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
    # ``empirical_release`` answers "are the results in the box"; ``empirical_rebuild``
    # answers "can the recipient rebuild them". The second is not a softer version of
    # the first: it is blocked by its own issues, and by anything critical, and it
    # never turns a blocked empirical release into a permitted one.
    rebuild_blocked = bool(critical) or any(
        issue.issue_id in REBUILD_BLOCKING_ISSUE_IDS for issue in issues
    )
    return {
        "critical_issue_count": len(critical),
        "major_issue_count": len(major),
        "source_release": "blocked" if critical else "permitted",
        "empirical_release": "blocked" if critical or major else "permitted",
        "empirical_rebuild": (
            "blocked" if rebuild_blocked else REBUILDABLE_WHILE_SOURCES_RETRIEVABLE
        ),
        "empirical_rebuild_entry_point": REBUILD_ENTRY_POINT,
        # Three properties that the single ``empirical_rebuild`` field used to blur.
        # Hash pinning makes the rebuild vintage-safe, which is a guarantee about what
        # a mismatch does, not a guarantee that a mismatch never happens. A provider
        # that stops serving the frozen bytes leaves the rebuild correctly refusing to
        # run and the recipient unable to regenerate the result.
        "vintage_integrity": "enforced_by_frozen_expected_hashes",
        "rebuild_precondition": "frozen_source_bytes_remain_retrievable",
        "self_contained_empirical_reproduction": (
            "not_supported_generated_artifacts_are_not_distributed"
        ),
        "source_tag": "blocked" if critical else "source_only_tag_allowed",
        "empirical_result_tag": "blocked" if critical or major else "allowed",
        # The verdict must track both dimensions. Reporting
        # ``source_only_release_ready`` while ``empirical_release`` is permitted
        # would contradict the field beside it.
        "release_verdict": (
            "do_not_release"
            if critical
            else "source_only_release_ready"
            if major
            else "full_release_ready"
        ),
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
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
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
        f"- Empirical rebuild: `{verdict['empirical_rebuild']}`",
        f"- Rebuild entry point: `{verdict['empirical_rebuild_entry_point']}`",
        f"- Source-only tag status: `{verdict['source_tag']}`",
        f"- Empirical-result tag status: `{verdict['empirical_result_tag']}`",
        f"- Vintage integrity: `{verdict['vintage_integrity']}`",
        f"- Rebuild precondition: `{verdict['rebuild_precondition']}`",
        "- Self-contained empirical reproduction: "
        f"`{verdict['self_contained_empirical_reproduction']}`",
        f"- Critical issues: `{verdict['critical_issue_count']}`",
        f"- Major issues: `{verdict['major_issue_count']}`",
        "",
        "These describe three different properties, and only the first two are supported.",
        "",
        "1. **Vintage integrity.** Every acquisition download is checked against the "
        "SHA-256 recorded in the shipped provenance manifests, and the rebuild aborts "
        "when a provider has revised a series rather than rebuilding against the "
        "revision. Changing a frozen vintage requires the separate `make update-vintage` "
        "operation, which no `reproduce` stage invokes.",
        "2. **Rebuildability, conditional.** `empirical_rebuild` reports that the archive "
        "carries a documented, hash-verified rebuild path. That path regenerates the "
        "empirical artifacts only while the frozen source bytes remain retrievable. If a "
        "provider replaces a file and keeps no immutable historical copy, the rebuild "
        "will correctly refuse to run, and a recipient holding only this archive will not "
        "be able to regenerate the published result. Failing safely is not the same "
        "property as remaining reproducible indefinitely, and the status string is "
        "qualified so the two are not read as one.",
        "3. **Self-contained empirical reproduction.** Not supported. The generated "
        "panels and estimate stores are not distributed, which is what "
        "`empirical_release: blocked` and the `empirical_artifacts_missing` issue "
        "record. Where redistribution rights permit it, depositing the frozen source "
        "bytes with the archival release would upgrade this property; where they do not, "
        "`docs/DATA_ACQUISITION.md` names the most immutable identifier available for "
        "each source.",
        "",
        "`empirical_release` and `empirical_rebuild` are independent; the second never "
        "substitutes for the first.",
        "",
        "## What This Archive Contains",
        "",
        "- Source code, configuration, the frozen source registry, the pre-specified design, the "
        "acquisition and estimation scripts, the manuscript with its generated tables and "
        "figures, and the result tables and diagnostics that the manuscript cites.",
        "- It does not contain raw or processed data panels, first-pass and second-pass "
        "estimate stores, or any other artifact whose redistribution rights are unrecorded. "
        "Those are rebuilt, not shipped.",
        "",
        "## Exact Results",
        "",
        "- No result is classified as exact replication. The article identifies providers and "
        "people rather than files, so every estimate carries `documented_reconstruction`.",
        "",
        "## Approximate Results",
        "",
        "- Short-rate innovations are classified "
        "`approximately_reproduced_under_documented_reconstruction`.",
        "- Risk prices, pricing errors and fit, and comparator models are classified "
        "`partially_recovered_under_documented_reconstruction`. See "
        "`docs/REPLICATION_STATUS.md` for the layer table.",
        "",
        "## Blocked Results",
        "",
        "- Reproduction from this archive alone. The generated data panels and estimate stores "
        f"are not distributed; regenerate them with `{REBUILD_ENTRY_POINT}`.",
        "- Table 5, Tables 7 to 9, and the appendix tables beyond A.1 are not generated in "
        "this pass. The tables that are generated are audited cell by cell in "
        "`artifacts/audit/published_target_audit.csv`, which is the current record.",
        "- `artifacts/audit/table_replication.csv` is stale and should not be read as the "
        "table-level status. It still records all twenty-three tables as `not_generated` and "
        "`not_reproducible_missing_input`, including Tables 3, 4, 6 and A.1, whose cells the "
        "cell-level audit does compare. It predates the estimates and was never regenerated. "
        "Regenerating it is an open item.",
        "- Equal-weighted results and security-level reconstruction remain blocked by inputs "
        "this repository cannot obtain.",
        "- The high-frequency shock decomposition and the out-of-sample falsification are not "
        "run; their generated reports record `blocked_missing_input` with the inputs named.",
        "",
        "## Contradicted Results",
        "",
        "- No contradiction is recorded. Every input is a reconstruction, so a failure to "
        "recover a published cell cannot be attributed to the article rather than the inputs.",
        "",
        "## Extension Results",
        "",
        "- The temporal extension and the monetary-regime analysis are run, and both are "
        "unsupported against their predeclared standards.",
        "- The shock decomposition and the out-of-sample falsification remain predeclared "
        "appendix designs and are blocked by missing event-level and forecast inputs.",
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
            "Verify the archive with `make check` and `make release-check` from a clean "
            "checkout; neither needs network access or rebuilt data.",
            "",
            f"Rebuild the empirical artifacts with `{REBUILD_ENTRY_POINT}`. It runs source "
            "acquisition, panel construction, baseline estimation, the temporal extension, the "
            "regime analysis, and the paper build in dependency order. The acquisition stage "
            "needs network access unless the frozen raw bytes are already on disk; the "
            "bootstrap and simulation stages take hours. See `docs/DATA_ACQUISITION.md` for "
            "source-by-source access and redistribution status.",
            "",
            "## Frozen-Vintage Verification",
            "",
            "Every provider endpoint this project reads serves the current vintage: FRED's "
            "`fredgraph.csv` returns the latest revision of a series, and the Kenneth French, "
            "global-q, and Wharton files are replaced in place when the libraries are rebuilt. "
            "The rebuild therefore does not trust the URL. It treats the SHA-256 values in the "
            "shipped provenance manifests under `artifacts/provenance` as expected hashes: each "
            "acquisition downloads, hashes, and compares, normalises only on a match, and on a "
            "mismatch aborts naming the series, the expected hash, the received hash, and what "
            "to do next. A verification run rewrites no provenance manifest.",
            "",
            "The guarantee is therefore that a rebuild either reproduces the frozen vintage or "
            "refuses to run. It is not a guarantee that a provider still serves those bytes. "
            "When a provider has revised a series, the archive's own results cannot be "
            "regenerated from that provider until the frozen bytes are recovered from an "
            "immutable source; `docs/DATA_ACQUISITION.md` names the preferred one for each.",
            "",
            "Moving to a new vintage is a deliberate, separate operation: `make update-vintage` "
            "and its per-source targets pass `--update-vintage`, which is the only switch that "
            "may overwrite a recorded expected hash. It changes the inputs of every downstream "
            f"result, so `{REBUILD_ENTRY_POINT}` must be re-run in full afterwards and the new "
            "vintage reported. No `reproduce` stage passes that switch.",
            "",
        ]
    )
    return "\n".join(lines)


def write_release_notes(*, output_path: Path, issues: list[ReleaseIssue]) -> None:
    """Write markdown release notes."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_release_notes(issues), encoding="utf-8", newline="\n")


def locked_package_versions(*, lock_path: Path) -> dict[str, str]:
    """Return the resolved package versions recorded in the Poetry lock file.

    The release manifest must describe the environment a recipient rebuilds, not the
    interpreter that happened to write the file. Reading the lock keeps the manifest
    deterministic across machines; reading the live interpreter did not, and recorded
    whatever unrelated packages shared the author's interpreter.
    """
    lock_data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions = {
        str(package["name"]).lower(): str(package["version"])
        for package in lock_data.get("package", [])
    }
    return dict(sorted(versions.items()))


def build_release_environment_manifest(
    *,
    cwd: Path = Path("."),
    config_paths: tuple[Path, ...] = RELEASE_CONFIG_PATHS,
) -> dict[str, Any]:
    """Build a path-sanitized environment manifest for release assets."""
    return {
        "schema_version": 1,
        "machine_specific_paths_included": False,
        "packages_resolved_from": "poetry.lock",
        "python": {
            "implementation": "CPython",
            "requires_python": ">=3.12,<4.0",
        },
        "packages": locked_package_versions(lock_path=cwd / "poetry.lock"),
        "source_state": "Resolved by the Git commit or tag that carries this manifest.",
        "config_hashes": {
            normalise_repo_path(path): sha256_file(cwd / path)
            for path in config_paths
            if (cwd / path).is_file()
        },
    }


def write_release_environment_manifest(
    *,
    output_path: Path,
    cwd: Path = Path("."),
    config_paths: tuple[Path, ...] = RELEASE_CONFIG_PATHS,
) -> None:
    """Write a sanitized release environment manifest."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            build_release_environment_manifest(cwd=cwd, config_paths=config_paths),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def render_data_acquisition_guide(
    *,
    data_access_path: Path,
    source_registry_path: Path,
) -> str:
    """Render source-by-source acquisition guidance without redistributing raw data."""
    data_rows = _read_csv_rows(data_access_path)
    source_rows = _load_source_registry(source_registry_path)
    source_by_id = {str(row.get("id")): row for row in source_rows if row.get("id") is not None}
    lines = [
        "# Data Acquisition Guide",
        "",
        "This repository does not redistribute copyrighted articles, publisher supplements, "
        "licensed raw data, author-supplied files, or prompt files.",
        "",
        "## Public Processed Data Redistribution",
        "",
        "No public processed data file is currently redistributed beyond tracked placeholders. "
        "Before adding processed data, record source licence and redistribution rights in "
        "`research/data_access_matrix.csv`.",
        "",
        "## Source Instructions",
        "",
        "| Source | Access | Exact Definition | Acquisition Path | Redistribution | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for row in data_rows:
        source_id = str(row.get("source_id", "unknown"))
        source = source_by_id.get(source_id, {})
        acquisition_path = (
            source.get("raw_path") or source.get("expected_path") or "manual_registration"
        )
        redistribution = (
            "do_not_redistribute"
            if row.get("access_status", "").startswith("present_private")
            or "author" in row.get("access_status", "")
            else "verify_before_redistribution"
        )
        lines.append(
            "| "
            f"`{source_id}` | "
            f"`{row.get('access_status', 'unknown')}` | "
            f"`{row.get('exact_definition_verified', 'unknown')}` | "
            f"`{acquisition_path}` | "
            f"`{redistribution}` | "
            f"{_escape_table_cell(row.get('notes', ''))} |"
        )
    lines.extend(
        [
            "",
            "## Frozen-Vintage Verification",
            "",
            "None of the URLs above is a vintage. FRED's `fredgraph.csv?id=<series>` endpoint "
            "returns the latest revision of the series, and the Kenneth French, global-q, and "
            "Wharton files are replaced in place whenever those libraries are rebuilt. The "
            "checksums recorded in the shipped manifests under `artifacts/provenance` are "
            "therefore treated as **expected** hashes, not as a description of whatever "
            "arrived.",
            "",
            "Each acquisition script downloads the file, computes its SHA-256, and compares it "
            "with the recorded value. Only on a match does it normalise the payload and let the "
            "rebuild continue. On a mismatch it aborts, naming the series, the expected hash, "
            "the received hash, and the two ways forward; it writes no file and rewrites no "
            "manifest. When the immutable raw file is already present and already matches, the "
            "provider is not contacted at all.",
            "",
            "| Acquisition | Verifies | Expected hash read from |",
            "|---|---|---|",
            "| `scripts/acquire_short_rates.py` | FEDFUNDS, TB3MS, DFF, DTB3 raw CSV bytes | "
            "`artifacts/provenance/short_rate/<SERIES>_<vintage>.json` |",
            "| `scripts/acquire_french_factors.py` | both vintages of each three-factor, "
            "momentum, and five-factor ZIP | "
            "`artifacts/provenance/kenneth_french/<dataset>_<vintage>.json` |",
            "| `scripts/acquire_anomaly_portfolios.py` | the `vvg_monthly` and `inv_monthly` "
            "testing-portfolio ZIPs | "
            "`artifacts/provenance/portfolios/<archive>_<vintage>.json` |",
            "| `scripts/acquire_comparator_factors.py` | the q-factor CSV and both "
            "Pastor-Stambaugh liquidity files | "
            "`artifacts/provenance/comparators/<dataset>_<vintage>.json` |",
            "| `srar acquire-data --live` | every registry-driven public source | "
            "`artifacts/provenance/<source_id>.json` |",
            "",
            "### Preferred immutable sources",
            "",
            "Where a provider offers an addressable vintage, it is the better place to obtain "
            "the frozen bytes, and the place to look first when verification fails because the "
            "current file has been revised. The frozen vintage recorded in this archive is "
            "**not** switched to these endpoints here: which vintage the results rest on is a "
            "data decision, made and reported deliberately, not a side effect of changing an "
            "acquisition URL.",
            "",
            "- **FRED short rates.** ALFRED serves archival vintages of the same series "
            "(`alfredgraph.csv?id=<series>&vintage_date=<YYYY-MM-DD>`), and the FRED API exposes "
            "`vintage_dates`. A vintage-dated request is reproducible in a way that "
            "`fredgraph.csv` is not.",
            "- **Kenneth French publication-era archives.** Internet Archive snapshots "
            "(`https://web.archive.org/web/<timestamp>id_/<original URL>`) are content-addressed "
            "by capture time and are already the source of the `publication_era_20170709` "
            "vintage. The current-vintage archives have no immutable counterpart.",
            "- **Pastor-Stambaugh liquidity.** The publication-era file is likewise taken from "
            "an Internet Archive snapshot; the current file is served from a live Wharton path "
            "that is extended in place.",
            "- **global-q testing portfolios and q-factors.** No immutable endpoint is "
            "published, and the earliest usable snapshot post-dates the article, so the recorded "
            "checksum is the only vintage pin available for these files.",
            "",
            "### Changing the frozen vintage",
            "",
            "`make update-vintage` and its per-source targets "
            "(`update-vintage-short-rates`, `update-vintage-french`, "
            "`update-vintage-portfolios`, `update-vintage-comparators`) pass "
            "`--update-vintage`. That flag is the only way to overwrite a recorded expected "
            f"hash, and no `{REBUILD_ENTRY_POINT}` stage passes it. Running one of these "
            "targets replaces the raw bytes and the provenance manifests, which changes the "
            f"inputs of every downstream estimate: re-run `{REBUILD_ENTRY_POINT}` in full "
            "afterwards and report the new vintage. A verification failure is not a reason to "
            "run it.",
            "",
            "## Clean-Room Procedure",
            "",
            "1. Clone the repository into an empty workspace.",
            "2. Run `poetry install`.",
            "3. Run `make check` to execute source checks, dry-run data acquisition, catalog "
            "creation, release audit generation, and tests. This stage needs no network access "
            "and no rebuilt data.",
            f"4. Run `{REBUILD_ENTRY_POINT}` to rebuild the empirical artifacts from the frozen "
            "public sources listed above. The acquisition stage needs network access unless the "
            "frozen raw bytes are already under `data/raw`, and it verifies every download "
            "against the recorded hash before anything downstream runs; the bootstrap and "
            "simulation stages take hours. Individual stages are available as "
            "`make reproduce-acquire`, `reproduce-panels`, `reproduce-estimates`, "
            "`reproduce-extension`, `reproduce-regimes`, and `reproduce-reports`.",
            "5. Register restricted files with `poetry run srar register-manual-source` only "
            "when you have legal access; do not copy those files into Git.",
            "6. Rebuild release assets with `poetry run srar release-audit`.",
            "",
        ]
    )
    return "\n".join(lines)


def write_data_acquisition_guide(
    *,
    output_path: Path,
    data_access_path: Path,
    source_registry_path: Path,
) -> None:
    """Write the data acquisition guide."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_data_acquisition_guide(
            data_access_path=data_access_path,
            source_registry_path=source_registry_path,
        ),
        encoding="utf-8",
        newline="\n",
    )


def build_archive_file_list(
    *,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> tuple[Path, ...]:
    """Return deterministic release-archive file members."""
    selected_paths = paths if paths is not None else tracked_files(cwd)
    return tuple(
        path
        for path in sorted(selected_paths, key=normalise_repo_path)
        if is_archive_candidate(normalise_repo_path(path)) and (cwd / path).is_file()
    )


def write_source_archive(
    *,
    output_path: Path,
    cwd: Path = Path("."),
    paths: tuple[Path, ...] | None = None,
) -> tuple[Path, ...]:
    """Write a deterministic source-release ZIP archive."""
    members = build_archive_file_list(cwd=cwd, paths=paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in members:
            info = zipfile.ZipInfo(normalise_repo_path(path), date_time=ARCHIVE_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (cwd / path).read_bytes())
    return members


def write_source_archive_manifest(
    *,
    output_path: Path,
    archive_path: Path,
    members: tuple[Path, ...],
) -> None:
    """Write checksum and member metadata for the source archive."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "archive_path": normalise_repo_path(archive_path),
        "archive_sha256": sha256_file(archive_path),
        "file_count": len(members),
        "excluded": [
            "prompts/",
            "references/private/",
            "artifacts/tmp/",
            "artifacts/release/",
            "artifacts/environment/manifest.json",
            "data/catalog.duckdb",
        ],
        "members": [normalise_repo_path(path) for path in members],
    }
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


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
        "Required-input presence is evaluated against the membership of the source archive "
        "that this audit writes, not against the working tree it runs in. A file that exists "
        "locally but is ignored, or excluded from the archive, counts as absent, and a "
        "directory carrying only a `.gitkeep` placeholder counts as empty.",
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
            "- Required empirical inputs are resolved against distributed archive membership, "
            "so a locally generated but undistributed artifact cannot satisfy the gate.",
            "- The rebuild path is checked as shipped files plus a declared "
            f"`{REBUILD_ENTRY_POINT}` entry point, and is reported separately from whether the "
            "artifacts themselves ship.",
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
            "The empirical programme is run and its registered gates are reported, but the "
            "state variable is not identified, so the contribution is a documented "
            "reconstruction and extension rather than an identified asset-pricing result.",
            "",
            "The archive ships the result tables and diagnostics the manuscript cites. It does "
            "not ship the data panels or estimate stores behind them; those are regenerated "
            f"with `{REBUILD_ENTRY_POINT}` from the frozen public sources. A reviewer who wants "
            "to re-derive rather than re-read the numbers must run that rebuild.",
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
            "### MAJOR: Two-pass inference is not independently verifiable from the archive",
            "",
            "- Claim threatened: the short-rate factor earns one common cross-sectional price of "
            "risk.",
            "- Econometric reason: factor strength, standardized exposure dispersion, sample "
            "intersection, and covariance corrections cannot be re-evaluated from the shipped "
            "result tables alone, because the first-pass and cross-section estimate stores are "
            "not distributed.",
            "- Decisive diagnostic: inspect standardized exposure dispersion, weak-factor flags, "
            "GRS tests, Fama-MacBeth uncertainty, and leave-one-anomaly-family systems.",
            f"- Repair: rebuild the baseline artifacts with `{REBUILD_ENTRY_POINT}` and rerun "
            "the robustness diagnostics against the rebuilt estimate stores.",
            "",
            "### MAJOR: Out-of-sample and shock-decomposition claims remain blocked",
            "",
            "- Claim threatened: forecast falsification and the policy-information split of the "
            "aggregate innovation.",
            "- Econometric reason: the frozen training vintages and the event-level "
            "high-frequency inputs do not exist in this repository at all, so there is no valid "
            "holdout comparison and no decomposed shock series. This is a missing-input "
            "blocker, not a redistribution one, and the rebuild path does not resolve it.",
            "- Decisive diagnostic: rerun the shock and out-of-sample gates once compatible "
            "event-level and forecast inputs exist.",
            "- Repair: acquire the event-level data or retire the design, and preserve null or "
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
    code_report_path.write_text(
        render_adversarial_code_audit(issues), encoding="utf-8", newline="\n"
    )
    econometric_report_path.write_text(
        render_adversarial_econometric_audit(issues),
        encoding="utf-8",
        newline="\n",
    )


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(DictReader(handle))


def _load_source_registry(path: Path) -> list[dict[str, Any]]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected source registry mapping in {path}")
    sources = loaded.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError(f"Expected source registry sources list in {path}")
    return [source for source in sources if isinstance(source, dict)]


def _escape_table_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
