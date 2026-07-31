from pathlib import Path

import pytest

from short_rate_anomaly_regimes.reporting.manuscript import (
    extract_latex_title,
    load_artifact_map,
    render_blocked_manuscript_report,
    validate_manuscript,
    write_blocked_manuscript_report,
)


def test_repository_manuscript_passes_traceability_checks() -> None:
    issues = validate_manuscript(
        manuscript_path=Path("paper/manuscript.tex"),
        artifact_map_path=Path("research/manuscript_artifact_map.csv"),
    )

    assert issues == []


def test_manuscript_checks_reject_title_numeric_and_language_issues(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "bad.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Bad: Title?}\n"
        "\\section{Introduction}\n"
        "The result is 1.23 without a tag.\n"
        "This line says cause outside the approved section.\n"
        "\\section{Policy and Information Shocks}\n"
        "The phrase policy shock is allowed here.\n",
        encoding="utf-8",
    )

    issues = validate_manuscript(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
    )

    checks = {issue.check for issue in issues}
    assert "title_punctuation" in checks
    assert "numeric_artifact_mapping" in checks
    assert "restricted_language" in checks


def test_manuscript_checks_validate_artifact_tags_and_map(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "draft.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Introduction}\n"
        f"The sample ends in 2013-12. % artifact: {artifact.as_posix()}\n",
        encoding="utf-8",
    )

    assert extract_latex_title(manuscript_path.read_text(encoding="utf-8")) == "Clean Title"
    assert (
        validate_manuscript(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
        )
        == []
    )

    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Introduction}\n"
        "The sample ends in 2013-12. % artifact: missing.csv\n",
        encoding="utf-8",
    )
    issues = validate_manuscript(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
    )
    assert issues[0].check == "numeric_artifact_mapping"


def test_artifact_map_and_blocked_report_validation(tmp_path: Path) -> None:
    bad_map = tmp_path / "bad.csv"
    bad_map.write_text("artifact_id\nx\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_artifact_map(bad_map)

    report = render_blocked_manuscript_report(missing_inputs=(Path("missing.csv"),))
    assert "blocked_missing_input" in report

    report_path = tmp_path / "report.md"
    write_blocked_manuscript_report(
        output_path=report_path,
        missing_inputs=(Path("missing.csv"),),
    )
    assert report_path.is_file()


def test_manuscript_checks_empirical_paragraph_context(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "paper.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Results}\n"
        "This empirical result paragraph is marked. % empirical-paragraph\n",
        encoding="utf-8",
    )

    issues = validate_manuscript(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
    )

    assert issues[0].check == "empirical_paragraph_context"

    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Results}\n"
        "This empirical result paragraph is marked. % empirical-paragraph\n"
        "% empirical-context: sample=x; model=x; estimator=x; test_assets=x; "
        "uncertainty=x; economic_magnitude=x\n",
        encoding="utf-8",
    )

    assert (
        validate_manuscript(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
        )
        == []
    )


def test_manuscript_checks_table_and_figure_artifact_sources(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "paper.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Results}\n"
        "\\begin{table}\n"
        "\\caption{Unmapped table}\n"
        "\\end{table}\n",
        encoding="utf-8",
    )

    issues = validate_manuscript(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
    )

    assert issues[0].check == "table_figure_artifact_source"

    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Results}\n"
        "\\begin{figure}\n"
        f"Source: \\artifact{{{artifact.as_posix()}}}\n"
        "\\end{figure}\n",
        encoding="utf-8",
    )

    assert (
        validate_manuscript(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
        )
        == []
    )


def test_manuscript_checks_allow_sentence_case_identification_section(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "paper.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Policy and information shock decomposition}\n"
        "The policy shock label is allowed in this section.\n",
        encoding="utf-8",
    )

    assert (
        validate_manuscript(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
        )
        == []
    )


def test_manuscript_checks_ignore_tabular_layout_widths(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "paper.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\section{Results}\n"
        "\\begin{table}\n"
        "\\begin{tabular}{p{0.22\\linewidth}p{0.40\\linewidth}}\n"
        f"Source & \\artifact{{{artifact.as_posix()}}} \\\\\n"
        "\\end{tabular}\n"
        "\\end{table}\n",
        encoding="utf-8",
    )

    assert (
        validate_manuscript(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
        )
        == []
    )


def test_manuscript_checks_ignore_author_affiliation_metadata(tmp_path: Path) -> None:
    manuscript_path = tmp_path / "paper.tex"
    artifact_map_path = tmp_path / "map.csv"
    artifact = tmp_path / "artifact.csv"
    artifact.write_text("x\n", encoding="utf-8")
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    manuscript_path.write_text(
        "\\title{Clean Title}\n"
        "\\author{Diogo Ribeiro\\inst{1,2,*}\\orcidID{0009-0001-2022-7072}}\n"
        "\\authorrunning{D. Ribeiro}\n"
        "\\institute{Department A \\and Department B}\n",
        encoding="utf-8",
    )

    assert (
        validate_manuscript(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
        )
        == []
    )
