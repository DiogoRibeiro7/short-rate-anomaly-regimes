import json
import subprocess
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app
from short_rate_anomaly_regimes.reporting.release import (
    REBUILD_ENTRY_POINT_FILE,
    REBUILD_ENTRY_POINT_TARGET,
    REQUIRED_EMPIRICAL_REBUILD_INPUTS,
    REQUIRED_EMPIRICAL_RELEASE_INPUTS,
    ReleaseIssue,
    build_checksum_manifest,
    build_release_environment_manifest,
    build_release_issues,
    build_sbom,
    declares_make_target,
    distributed_release_files,
    is_checksum_candidate,
    is_disallowed_release_path,
    is_distributed_path,
    release_verdict,
    render_adversarial_code_audit,
    render_adversarial_econometric_audit,
    render_data_acquisition_guide,
    render_release_notes,
    write_checksum_manifest,
    write_release_gate,
    write_source_archive,
    write_source_archive_manifest,
)

REPRODUCE_RULE = f"{REBUILD_ENTRY_POINT_TARGET}: {REBUILD_ENTRY_POINT_TARGET}-acquire\n\techo run\n"


def _write(root: Path, relative: str, content: str = "placeholder\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _empirical_input_files() -> tuple[str, ...]:
    """Return one concrete file per required empirical input.

    Directory entries are represented by a non-placeholder member, because a
    directory that carries only a ``.gitkeep`` is an empty directory.
    """
    return tuple(
        required if required.endswith(".parquet") else f"{required}/generated.csv"
        for required in REQUIRED_EMPIRICAL_RELEASE_INPUTS
    )


def _rebuild_repo(root: Path) -> tuple[Path, ...]:
    """Materialise a repository that ships a complete rebuild path."""
    for relative in REQUIRED_EMPIRICAL_REBUILD_INPUTS:
        _write(root, relative)
    _write(root, REBUILD_ENTRY_POINT_FILE, REPRODUCE_RULE)
    _write(root, "poetry.lock", "")
    return tuple(Path(relative) for relative in (*REQUIRED_EMPIRICAL_REBUILD_INPUTS, "poetry.lock"))


def test_release_path_filters_reject_local_only_materials() -> None:
    assert is_disallowed_release_path("prompts/15_ADVERSARIAL_RELEASE_PROMPT.md")
    assert is_disallowed_release_path("references/private/article.pdf")
    assert is_disallowed_release_path("references/private/README.md")
    assert is_disallowed_release_path("data/catalog.duckdb")
    assert not is_disallowed_release_path("src/short_rate_anomaly_regimes/cli.py")

    assert not is_checksum_candidate("prompts/15_ADVERSARIAL_RELEASE_PROMPT.md")
    assert not is_checksum_candidate("artifacts/release/sbom.json")
    assert not is_checksum_candidate("docs/RELEASE_NOTES.md")
    assert is_checksum_candidate("README.md")


def test_required_inputs_are_judged_by_archive_membership_not_by_local_disk(
    tmp_path: Path,
) -> None:
    """A locally generated but undistributed artifact must not satisfy the gate.

    This is the regression the gate previously failed: the required inputs were
    resolved with ``Path.exists()``, so gitignored panels sitting in the author's
    working tree flipped the empirical verdict to permitted for an archive that
    ships only placeholders.
    """
    rebuild_paths = _rebuild_repo(tmp_path)
    for relative in _empirical_input_files():
        _write(tmp_path, relative)
        assert (tmp_path / relative).is_file()

    issues = build_release_issues(cwd=tmp_path, paths=rebuild_paths)
    missing = next(issue for issue in issues if issue.issue_id == "empirical_artifacts_missing")

    for required in REQUIRED_EMPIRICAL_RELEASE_INPUTS:
        assert required in missing.location
    assert release_verdict(issues)["empirical_release"] == "blocked"


def test_required_inputs_are_satisfied_once_the_archive_carries_them(tmp_path: Path) -> None:
    rebuild_paths = _rebuild_repo(tmp_path)
    empirical_files = _empirical_input_files()
    for relative in empirical_files:
        _write(tmp_path, relative)

    issues = build_release_issues(
        cwd=tmp_path,
        paths=(*rebuild_paths, *(Path(relative) for relative in empirical_files)),
    )

    assert not any(issue.issue_id == "empirical_artifacts_missing" for issue in issues)


def test_directory_holding_only_a_placeholder_is_not_distributed(tmp_path: Path) -> None:
    _write(tmp_path, "artifacts/tables/time_series/.gitkeep", "")
    _write(tmp_path, "artifacts/tables/cross_section/prices.csv")

    distributed = distributed_release_files(
        cwd=tmp_path,
        paths=(
            Path("artifacts/tables/time_series/.gitkeep"),
            Path("artifacts/tables/cross_section/prices.csv"),
        ),
    )

    assert not is_distributed_path("artifacts/tables/time_series", distributed)
    assert is_distributed_path("artifacts/tables/cross_section", distributed)
    assert is_distributed_path("artifacts/tables/cross_section/prices.csv", distributed)


def test_distributed_files_exclude_paths_the_archive_never_carries(tmp_path: Path) -> None:
    _write(tmp_path, "prompts/private.md")
    _write(tmp_path, "README.md")

    distributed = distributed_release_files(
        cwd=tmp_path,
        paths=(Path("prompts/private.md"), Path("README.md")),
    )

    assert distributed == frozenset({"README.md"})


def test_rebuild_status_is_reported_beside_the_release_status(tmp_path: Path) -> None:
    rebuild_paths = _rebuild_repo(tmp_path)

    issues = build_release_issues(cwd=tmp_path, paths=rebuild_paths)
    verdict = release_verdict(issues)

    assert verdict["empirical_release"] == "blocked"
    assert (
        verdict["empirical_rebuild"] == "rebuildable_while_frozen_source_bytes_remain_retrievable"
    )
    # The three properties the single field used to blur.
    assert verdict["vintage_integrity"] == "enforced_by_frozen_expected_hashes"
    assert verdict["rebuild_precondition"] == "frozen_source_bytes_remain_retrievable"
    assert verdict["self_contained_empirical_reproduction"].startswith("not_supported")
    assert verdict["empirical_rebuild_entry_point"] == "make reproduce"
    # A rebuild path is not a pass. The release verdict is unchanged by it.
    assert verdict["release_verdict"] == "source_only_release_ready"
    assert verdict["empirical_result_tag"] == "blocked"


def test_missing_rebuild_scripts_block_the_rebuild_status(tmp_path: Path) -> None:
    rebuild_paths = _rebuild_repo(tmp_path)
    dropped = Path("scripts/acquire_short_rates.py")
    kept = tuple(path for path in rebuild_paths if path != dropped)

    issues = build_release_issues(cwd=tmp_path, paths=kept)
    incomplete = next(
        issue for issue in issues if issue.issue_id == "empirical_rebuild_path_incomplete"
    )

    assert incomplete.severity == "major"
    assert dropped.as_posix() in incomplete.location
    assert release_verdict(issues)["empirical_rebuild"] == "blocked"


def test_makefile_without_a_reproduce_target_blocks_the_rebuild_status(tmp_path: Path) -> None:
    rebuild_paths = _rebuild_repo(tmp_path)
    _write(tmp_path, REBUILD_ENTRY_POINT_FILE, "test:\n\tpytest\n")

    issues = build_release_issues(cwd=tmp_path, paths=rebuild_paths)
    missing_entry = next(
        issue for issue in issues if issue.issue_id == "empirical_rebuild_entry_point_missing"
    )

    assert missing_entry.location == REBUILD_ENTRY_POINT_FILE
    assert release_verdict(issues)["empirical_rebuild"] == "blocked"


def test_a_critical_issue_blocks_the_rebuild_status_as_well(tmp_path: Path) -> None:
    rebuild_paths = _rebuild_repo(tmp_path)
    _write(tmp_path, "prompts/private.md")

    issues = build_release_issues(
        cwd=tmp_path,
        paths=(*rebuild_paths, Path("prompts/private.md")),
    )
    verdict = release_verdict(issues)

    assert verdict["source_release"] == "blocked"
    assert verdict["empirical_rebuild"] == "blocked"


def test_declares_make_target_ignores_phony_declarations_and_recipes() -> None:
    makefile = ".PHONY: reproduce test\n\ntest:\n\techo reproduce: not a rule\n"

    assert not declares_make_target(makefile, "reproduce")
    assert declares_make_target(makefile, "test")
    assert declares_make_target("reproduce: stage-one stage-two\n\techo run\n", "reproduce")
    assert not declares_make_target("# reproduce: commented out\n", "reproduce")


def test_repository_makefile_declares_the_documented_rebuild_entry_point() -> None:
    makefile = Path(REBUILD_ENTRY_POINT_FILE).read_text(encoding="utf-8")

    assert declares_make_target(makefile, REBUILD_ENTRY_POINT_TARGET)
    for stage in ("acquire", "panels", "estimates", "extension", "regimes", "reports"):
        assert declares_make_target(makefile, f"{REBUILD_ENTRY_POINT_TARGET}-{stage}")


def test_release_gate_flags_processed_data_without_redistribution_review(tmp_path: Path) -> None:
    issues = build_release_issues(
        cwd=tmp_path,
        paths=(Path("data/processed/factors/public.parquet"), Path("README.md")),
    )

    assert any(issue.issue_id == "processed_data_redistribution_unverified" for issue in issues)


def test_checksum_manifest_hashes_only_release_candidates(tmp_path: Path) -> None:
    kept = tmp_path / "README.md"
    prompt = tmp_path / "prompts" / "private.md"
    kept.write_text("public\n", encoding="utf-8")
    prompt.parent.mkdir()
    prompt.write_text("secret\n", encoding="utf-8")

    records = build_checksum_manifest(
        cwd=tmp_path,
        paths=(Path("README.md"), Path("prompts/private.md")),
    )

    assert [record["path"] for record in records] == ["README.md"]
    assert len(records[0]["sha256"]) == 64

    output = tmp_path / "checksums.sha256"
    write_checksum_manifest(
        output_path=output,
        cwd=tmp_path,
        paths=(Path("README.md"), Path("prompts/private.md")),
    )
    assert "README.md" in output.read_text(encoding="utf-8")
    assert "prompts/private.md" not in output.read_text(encoding="utf-8")


def _write_demo_lock(cwd: Path) -> None:
    (cwd / "poetry.lock").write_text(
        '[[package]]\nname = "Numpy"\nversion = "2.2.6"\n\n'
        '[[package]]\nname = "pandas"\nversion = "2.3.1"\n',
        encoding="utf-8",
    )


def test_release_environment_manifest_is_path_sanitized(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "baseline.yaml"
    config.parent.mkdir()
    config.write_text("project: demo\n", encoding="utf-8")
    _write_demo_lock(tmp_path)

    manifest = build_release_environment_manifest(
        cwd=tmp_path,
        config_paths=(Path("configs/baseline.yaml"),),
    )
    rendered = json.dumps(manifest)

    assert manifest["machine_specific_paths_included"] is False
    assert "executable" not in rendered
    assert "configs/baseline.yaml" in manifest["config_hashes"]


def test_release_environment_manifest_reports_the_locked_environment(tmp_path: Path) -> None:
    """The manifest must describe the rebuild target, not the interpreter that wrote it.

    Reading the live interpreter made the file machine-specific, so it recorded packages
    that were merely installed alongside the project and omitted locked ones that were not.
    """
    _write_demo_lock(tmp_path)

    manifest = build_release_environment_manifest(cwd=tmp_path, config_paths=())

    assert manifest["packages_resolved_from"] == "poetry.lock"
    assert manifest["packages"] == {"numpy": "2.2.6", "pandas": "2.3.1"}


def test_release_environment_manifest_matches_the_repository_lock_file() -> None:
    manifest = build_release_environment_manifest()
    locked = tomllib.loads(Path("poetry.lock").read_text(encoding="utf-8"))
    expected = {str(item["name"]).lower(): str(item["version"]) for item in locked["package"]}

    assert manifest["packages"] == expected


def test_data_acquisition_guide_lists_nonredistributed_sources(tmp_path: Path) -> None:
    data_access = tmp_path / "data_access.csv"
    registry = tmp_path / "sources.yaml"
    data_access.write_text(
        "source_id,exact_definition_verified,access_status,notes\n"
        "article_pdf,true,present_private_file,Private article copy\n"
        "public_factor,false,article_source_located,Freeze exact archive\n",
        encoding="utf-8",
    )
    registry.write_text(
        """
sources:
  - id: article_pdf
    expected_path: references/private/article.pdf
  - id: public_factor
    raw_path: data/raw/public_factor.csv
""",
        encoding="utf-8",
    )

    guide = render_data_acquisition_guide(
        data_access_path=data_access,
        source_registry_path=registry,
    )

    assert "do_not_redistribute" in guide
    assert "data/raw/public_factor.csv" in guide
    assert "prompt files" in guide


def test_source_archive_excludes_local_only_paths(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    prompt = tmp_path / "prompts" / "private.md"
    release_asset = tmp_path / "artifacts" / "release" / "sbom.json"
    private_readme = tmp_path / "references" / "private" / "README.md"
    readme.write_text("public\n", encoding="utf-8")
    prompt.parent.mkdir()
    prompt.write_text("secret\n", encoding="utf-8")
    release_asset.parent.mkdir(parents=True)
    release_asset.write_text("{}\n", encoding="utf-8")
    private_readme.parent.mkdir(parents=True)
    private_readme.write_text("handling notes\n", encoding="utf-8")

    archive = tmp_path / "artifacts" / "release" / "source_release.zip"
    members = write_source_archive(
        output_path=archive,
        cwd=tmp_path,
        paths=(
            Path("README.md"),
            Path("prompts/private.md"),
            Path("artifacts/release/sbom.json"),
            Path("references/private/README.md"),
        ),
    )
    manifest = tmp_path / "artifacts" / "release" / "source_release_manifest.json"
    write_source_archive_manifest(
        output_path=manifest,
        archive_path=archive,
        members=members,
    )

    assert [path.as_posix() for path in members] == ["README.md"]
    assert "README.md" in manifest.read_text(encoding="utf-8")
    assert "prompts/private.md" not in manifest.read_text(encoding="utf-8")
    assert "references/private/README.md" not in manifest.read_text(encoding="utf-8")


def test_build_sbom_reads_poetry_lock(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    lock = tmp_path / "poetry.lock"
    pyproject.write_text(
        """
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.12"
license = "MIT"
""",
        encoding="utf-8",
    )
    lock.write_text(
        """
[[package]]
name = "numpy"
version = "2.1.0"
optional = false
python-versions = ">=3.10"
groups = ["main"]
files = [{file = "numpy.whl", hash = "sha256:abc"}]
""",
        encoding="utf-8",
    )

    sbom = build_sbom(pyproject_path=pyproject, lock_path=lock)

    assert sbom["project"]["name"] == "demo"
    assert sbom["packages"][0]["name"] == "numpy"
    assert sbom["packages"][0]["file_hashes"] == ["sha256:abc"]


def test_release_gate_flags_critical_and_major_issues(tmp_path: Path) -> None:
    output = tmp_path / "release_gate.json"

    issues = write_release_gate(
        output_path=output,
        cwd=tmp_path,
        paths=(Path("prompts/private.md"), Path("README.md")),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert any(issue.issue_id == "restricted_path_tracked" for issue in issues)
    assert any(issue.issue_id == "empirical_artifacts_missing" for issue in issues)
    assert payload["verdict"]["source_release"] == "blocked"
    assert release_verdict(issues)["critical_issue_count"] == 2


def test_release_notes_and_adversarial_reports_include_required_verdicts() -> None:
    """Render the reports from an explicit issue rather than repository state.

    Building the issue list from the live tree made this test depend on an
    artifact being absent, so it began failing the moment the repository could
    actually produce that artifact. The renderers are what is under test here.
    """
    issues = [
        ReleaseIssue(
            issue_id="fixture_issue",
            severity="major",
            location="data/processed/factors/fixture.parquet",
            failure_mechanism="Fixture failure mechanism for the renderers.",
            required_fix="Fixture required fix.",
        )
    ]

    notes = render_release_notes(issues)
    code_audit = render_adversarial_code_audit(issues)
    econometric_audit = render_adversarial_econometric_audit(issues)

    assert "Exact Results" in notes
    assert "Approximate Results" in notes
    assert "Blocked Results" in notes
    assert "Contradicted Results" in notes
    assert "Extension Results" in notes
    assert "source_only_tag_allowed" in notes
    assert "prompts" in notes
    # The notes must carry both facts: what ships, and what can be rebuilt.
    assert "What This Archive Contains" in notes
    assert "Empirical-results release: `blocked`" in notes
    assert "Empirical rebuild: `rebuildable_while_frozen_source_bytes_remain_retrievable`" in notes
    assert "make reproduce" in notes
    assert "Minimal reproduction" in code_audit
    assert "distributed archive membership" in code_audit
    assert "potentially_publishable_after_major_revision" in econometric_audit
    assert "make reproduce" in econometric_audit


def test_release_audit_command_writes_artifacts(tmp_path: Path) -> None:
    sbom = tmp_path / "release" / "sbom.json"
    environment = tmp_path / "release" / "environment_manifest.json"
    checksums = tmp_path / "release" / "checksums.sha256"
    gate = tmp_path / "release" / "gate.json"
    archive = tmp_path / "release" / "source_release.zip"
    archive_manifest = tmp_path / "release" / "source_release_manifest.json"
    notes = tmp_path / "RELEASE_NOTES.md"
    data_guide = tmp_path / "DATA_ACQUISITION.md"
    code_audit = tmp_path / "adversarial_code_audit.md"
    econometric_audit = tmp_path / "adversarial_econometric_audit.md"

    result = CliRunner().invoke(
        app,
        [
            "release-audit",
            "--sbom",
            str(sbom),
            "--environment",
            str(environment),
            "--checksums",
            str(checksums),
            "--gate",
            str(gate),
            "--archive",
            str(archive),
            "--archive-manifest",
            str(archive_manifest),
            "--release-notes",
            str(notes),
            "--data-guide",
            str(data_guide),
            "--code-audit",
            str(code_audit),
            "--econometric-audit",
            str(econometric_audit),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote release audit artifacts" in result.stdout
    assert json.loads(sbom.read_text(encoding="utf-8"))["project"]["name"]
    assert (
        json.loads(environment.read_text(encoding="utf-8"))["machine_specific_paths_included"]
        is False
    )
    assert "README.md" in checksums.read_text(encoding="utf-8")
    assert "source_release" in gate.read_text(encoding="utf-8")
    assert archive.is_file()
    assert "archive_sha256" in archive_manifest.read_text(encoding="utf-8")
    assert "Release Verdict" in notes.read_text(encoding="utf-8")
    assert "Data Acquisition Guide" in data_guide.read_text(encoding="utf-8")
    assert "Adversarial Code Audit" in code_audit.read_text(encoding="utf-8")
    assert "Adversarial Econometric Audit" in econometric_audit.read_text(encoding="utf-8")


def test_rebuild_whitelist_covers_every_script_make_reproduce_runs() -> None:
    """The declared rebuild inputs must not fall behind the reproduce target.

    The whitelist is a contract about what the archive has to carry. If a stage
    gains a script and the list does not, the gate would certify a rebuild path
    that a recipient cannot actually execute.
    """
    # Only the reproduce chain is in scope. Scanning every recipe would let an
    # unrelated developer target either fail this test or force a script into
    # the release contract that no rebuild needs.
    recipes: dict[str, list[str]] = {}
    current = None
    for line in Path("Makefile").read_text(encoding="utf-8").splitlines():
        if line[:1].isalpha() and ":" in line:
            current = line.split(":", 1)[0].strip()
            recipes[current] = []
        elif line.startswith("	") and current is not None:
            recipes[current].append(line)
        elif not line.strip():
            current = None
    chain = [
        target
        for target in recipes
        if target == REBUILD_ENTRY_POINT_TARGET
        or target.startswith(REBUILD_ENTRY_POINT_TARGET + "-")
    ]
    invoked = {
        word
        for target in chain
        for line in recipes[target]
        for word in line.split()
        if word.startswith("scripts/") and word.endswith(".py")
    }
    declared = set(REQUIRED_EMPIRICAL_REBUILD_INPUTS)

    assert chain, "the reproduce chain was not found in the Makefile"
    assert invoked, "no scripts found in the reproduce chain"
    assert invoked <= declared, f"not declared as rebuild inputs: {sorted(invoked - declared)}"


def test_no_tracked_file_differs_from_its_stored_bytes_by_line_endings() -> None:
    """Guard the integrity manifest against line-ending drift.

    ``build_checksum_manifest`` hashes files from the working tree, while git
    stores them under the repository's ``text=auto eol=lf`` rule. A tool that
    writes CRLF therefore produces a manifest whose hashes no recipient of a
    clone can reproduce, which is the one failure an integrity record must not
    have. Editors and generators must write LF; this fails when one does not.
    """
    crlf = bytes((13, 10))
    lf = bytes((10,))
    try:
        listing = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):  # pragma: no cover - git absent
        pytest.skip("git is not available")

    drifted = []
    for name in listing:
        path = Path(name)
        if not path.is_file():
            continue
        disk = path.read_bytes()
        stored = subprocess.run(
            ["git", "show", f"HEAD:{name}"], capture_output=True, check=False
        ).stdout
        if disk != stored and disk.replace(crlf, lf) == stored:
            drifted.append(name)

    assert not drifted, f"line-ending drift against the stored bytes: {drifted}"


def test_package_version_matches_every_declaration() -> None:
    """The version must agree wherever it is declared.

    A release bumps pyproject, the Zenodo record and the citation file. The
    package's own ``__version__`` is easy to miss, and an importer reading a
    stale value on a tagged release cannot tell which is authoritative. A
    Zenodo deposit makes that disagreement permanent.
    """
    import short_rate_anomaly_regimes

    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    declared = pyproject["project"]["version"]
    zenodo = json.loads(Path(".zenodo.json").read_text(encoding="utf-8"))["version"]
    citation = next(
        line.split(":", 1)[1].strip()
        for line in Path("CITATION.cff").read_text(encoding="utf-8").splitlines()
        if line.startswith("version:")
    )

    assert short_rate_anomaly_regimes.__version__ == declared
    assert zenodo == declared
    assert citation == declared
