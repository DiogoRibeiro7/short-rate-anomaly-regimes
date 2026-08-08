import json
from pathlib import Path

from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app
from short_rate_anomaly_regimes.reporting.release import (
    ReleaseIssue,
    build_checksum_manifest,
    build_release_environment_manifest,
    build_release_issues,
    build_sbom,
    is_checksum_candidate,
    is_disallowed_release_path,
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


def test_release_environment_manifest_is_path_sanitized(tmp_path: Path) -> None:
    config = tmp_path / "configs" / "baseline.yaml"
    config.parent.mkdir()
    config.write_text("project: demo\n", encoding="utf-8")

    manifest = build_release_environment_manifest(
        cwd=tmp_path,
        config_paths=(Path("configs/baseline.yaml"),),
    )
    rendered = json.dumps(manifest)

    assert manifest["machine_specific_paths_included"] is False
    assert "executable" not in rendered
    assert "configs/baseline.yaml" in manifest["config_hashes"]


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
    assert "Minimal reproduction" in code_audit
    assert "potentially_publishable_after_major_revision" in econometric_audit


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
