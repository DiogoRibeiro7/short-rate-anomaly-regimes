import json
from pathlib import Path

from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app
from short_rate_anomaly_regimes.reporting.release import (
    build_checksum_manifest,
    build_release_issues,
    build_sbom,
    is_checksum_candidate,
    is_disallowed_release_path,
    release_verdict,
    render_adversarial_code_audit,
    render_adversarial_econometric_audit,
    render_release_notes,
    write_checksum_manifest,
    write_release_gate,
)


def test_release_path_filters_reject_local_only_materials() -> None:
    assert is_disallowed_release_path("prompts/15_ADVERSARIAL_RELEASE_PROMPT.md")
    assert is_disallowed_release_path("references/private/article.pdf")
    assert is_disallowed_release_path("data/catalog.duckdb")
    assert not is_disallowed_release_path("references/private/README.md")
    assert not is_disallowed_release_path("src/short_rate_anomaly_regimes/cli.py")

    assert not is_checksum_candidate("prompts/15_ADVERSARIAL_RELEASE_PROMPT.md")
    assert not is_checksum_candidate("artifacts/release/sbom.json")
    assert not is_checksum_candidate("docs/RELEASE_NOTES.md")
    assert is_checksum_candidate("README.md")


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
    issues = build_release_issues(paths=(Path("README.md"),))

    notes = render_release_notes(issues)
    code_audit = render_adversarial_code_audit(issues)
    econometric_audit = render_adversarial_econometric_audit(issues)

    assert "Exact Results" in notes
    assert "Approximate Results" in notes
    assert "Blocked Results" in notes
    assert "Contradicted Results" in notes
    assert "prompts" in notes
    assert "Minimal reproduction" in code_audit
    assert "potentially_publishable_after_major_revision" in econometric_audit


def test_release_audit_command_writes_artifacts(tmp_path: Path) -> None:
    sbom = tmp_path / "release" / "sbom.json"
    checksums = tmp_path / "release" / "checksums.sha256"
    gate = tmp_path / "release" / "gate.json"
    notes = tmp_path / "RELEASE_NOTES.md"
    code_audit = tmp_path / "adversarial_code_audit.md"
    econometric_audit = tmp_path / "adversarial_econometric_audit.md"

    result = CliRunner().invoke(
        app,
        [
            "release-audit",
            "--sbom",
            str(sbom),
            "--checksums",
            str(checksums),
            "--gate",
            str(gate),
            "--release-notes",
            str(notes),
            "--code-audit",
            str(code_audit),
            "--econometric-audit",
            str(econometric_audit),
        ],
    )

    assert result.exit_code == 0
    assert "Wrote release audit artifacts" in result.stdout
    assert json.loads(sbom.read_text(encoding="utf-8"))["project"]["name"]
    assert "README.md" in checksums.read_text(encoding="utf-8")
    assert "source_release" in gate.read_text(encoding="utf-8")
    assert "Release Verdict" in notes.read_text(encoding="utf-8")
    assert "Adversarial Code Audit" in code_audit.read_text(encoding="utf-8")
    assert "Adversarial Econometric Audit" in econometric_audit.read_text(encoding="utf-8")
