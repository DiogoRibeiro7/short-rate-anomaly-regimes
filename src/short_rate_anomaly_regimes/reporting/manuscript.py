"""Manuscript traceability and language checks."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.reporting.artifact_evidence import (
    markdown_table,
    path_bullets,
    report_verdict,
)

TITLE_PATTERN = re.compile(r"\\title\{(?P<title>[^}]*)\}")
SECTION_PATTERN = re.compile(r"\\section\{(?P<section>[^}]*)\}")
NUMERIC_PATTERN = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?![A-Za-z_])")
ARTIFACT_TAG_PATTERN = re.compile(r"%\s*artifact:\s*(?P<artifact>\S+)")
LATEX_ARTIFACT_PATTERN = re.compile(r"\\artifact\{(?P<artifact>[^}]*)\}")
ENVIRONMENT_BEGIN_PATTERN = re.compile(r"\\begin\{(?P<environment>table|figure)\}")
ENVIRONMENT_END_PATTERN = re.compile(r"\\end\{(?P<environment>table|figure)\}")
INPUT_PATTERN = re.compile(r"\\input\{(?P<path>[^}]*)\}")
EMPIRICAL_PARAGRAPH_PATTERN = re.compile(r"%\s*empirical-paragraph\b")
EMPIRICAL_CONTEXT_PATTERN = re.compile(r"%\s*empirical-context:\s*(?P<context>.*)")
RESTRICTED_LANGUAGE_PATTERN = re.compile(r"\b(cause|effect|policy shock)\b", re.IGNORECASE)
#: Sections in which causal vocabulary is permitted. These must match the
#: manuscript's section titles exactly; a name that matches no real section
#: silently bans the vocabulary everywhere rather than whitelisting anything.
APPROVED_LANGUAGE_SECTIONS = {
    "Policy and Information Shocks",
    "Policy and information shock decomposition",
    "Optional policy-information decomposition",
}
REQUIRED_EMPIRICAL_CONTEXT_FIELDS = frozenset(
    {
        "sample",
        "model",
        "estimator",
        "test_assets",
        "uncertainty",
        "economic_magnitude",
    }
)


@dataclass(frozen=True, slots=True)
class ManuscriptIssue:
    """One manuscript validation issue."""

    line_number: int
    check: str
    message: str


def extract_latex_title(manuscript: str) -> str:
    """Extract the first LaTeX title."""
    match = TITLE_PATTERN.search(manuscript)
    if match is None:
        raise ValueError("No LaTeX title found")
    return match.group("title")


def load_artifact_map(path: Path) -> pd.DataFrame:
    """Load declared manuscript artifact mappings."""
    frame = pd.read_csv(path)
    required = {"artifact_id", "path", "description"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Artifact map is missing columns: {', '.join(sorted(missing))}")
    if frame["artifact_id"].duplicated().any():
        raise ValueError("Artifact map contains duplicate artifact ids")
    return frame


def validate_manuscript(
    *,
    manuscript_path: Path,
    artifact_map_path: Path,
    require_existing_artifacts: bool = True,
) -> list[ManuscriptIssue]:
    """Validate manuscript title, numeric traceability, and restricted language."""
    manuscript = manuscript_path.read_text(encoding="utf-8")
    artifact_map = load_artifact_map(artifact_map_path)
    declared_paths = set(artifact_map["path"].astype(str))
    issues: list[ManuscriptIssue] = []
    title = extract_latex_title(manuscript)
    for symbol in ("?", ":"):
        if symbol in title:
            issues.append(
                ManuscriptIssue(
                    line_number=1,
                    check="title_punctuation",
                    message=f"Title contains forbidden punctuation {symbol!r}",
                )
            )
    if require_existing_artifacts:
        for row in artifact_map.itertuples(index=False):
            artifact_path = Path(str(row.path))
            if not artifact_path.exists():
                issues.append(
                    ManuscriptIssue(
                        line_number=0,
                        check="artifact_exists",
                        message=f"Mapped artifact does not exist: {artifact_path}",
                    )
                )

    for origin, line_number, target in _missing_inputs(manuscript_path, manuscript):
        where = f" in {origin}" if origin else ""
        issues.append(
            ManuscriptIssue(
                line_number=line_number,
                check="input_exists",
                message=f"Included file does not exist{where}: {target}",
            )
        )

    current_section = ""
    current_environment: str | None = None
    environment_start_line = 0
    environment_artifact_paths: set[str] = set()
    for origin, line_number, line in _source_lines(manuscript_path, manuscript):
        where = "" if not origin else f" in {origin}"
        section_match = SECTION_PATTERN.search(line)
        if section_match is not None:
            current_section = section_match.group("section")
        environment_match = ENVIRONMENT_BEGIN_PATTERN.search(line)
        if environment_match is not None:
            current_environment = environment_match.group("environment")
            environment_start_line = line_number
            environment_artifact_paths = set()
        if current_environment is not None:
            environment_artifact_paths.update(_artifact_references(line))
        if _line_has_numeric_claim(line):
            tag_match = ARTIFACT_TAG_PATTERN.search(line)
            if tag_match is None:
                issues.append(
                    ManuscriptIssue(
                        line_number=line_number,
                        check="numeric_artifact_mapping",
                        message=f"Numeric token lacks an artifact tag on the same line{where}",
                    )
                )
            elif tag_match.group("artifact") not in declared_paths:
                issues.append(
                    ManuscriptIssue(
                        line_number=line_number,
                        check="numeric_artifact_mapping",
                        message=(
                            f"Artifact tag is not declared{where}: {tag_match.group('artifact')}"
                        ),
                    )
                )
        end_match = ENVIRONMENT_END_PATTERN.search(line)
        if (
            end_match is not None
            and current_environment is not None
            and current_environment == end_match.group("environment")
        ):
            finished_environment = current_environment
            issues.extend(
                _validate_environment_artifacts(
                    environment=finished_environment,
                    start_line=environment_start_line,
                    artifact_paths=environment_artifact_paths,
                    declared_paths=declared_paths,
                )
            )
            current_environment = None
            environment_start_line = 0
            environment_artifact_paths = set()
        if current_section not in APPROVED_LANGUAGE_SECTIONS:
            for match in RESTRICTED_LANGUAGE_PATTERN.finditer(_strip_comment(line)):
                issues.append(
                    ManuscriptIssue(
                        line_number=line_number,
                        check="restricted_language",
                        message=(
                            f"Restricted term {match.group(0)!r} outside an approved "
                            "identification section"
                        ),
                    )
                )
    # Paragraphs are checked per source document, including every expanded
    # input, so moving an empirical paragraph into an included file does not
    # exempt it from declaring its context.
    for origin, document in _source_documents(manuscript_path, manuscript):
        where = f" in {origin}" if origin else ""
        for paragraph_start_line, paragraph in _iter_paragraphs(document):
            if not EMPIRICAL_PARAGRAPH_PATTERN.search(paragraph):
                continue
            for issue in _validate_empirical_context(paragraph_start_line, paragraph):
                issues.append(
                    ManuscriptIssue(
                        line_number=issue.line_number,
                        check=issue.check,
                        message=f"{issue.message}{where}",
                    )
                )
    return issues


def render_blocked_manuscript_report(*, missing_inputs: tuple[Path, ...]) -> str:
    """Render a blocked manuscript-output report."""
    lines = [
        "# Manuscript Output Report",
        "",
        "Verdict: `blocked_missing_input`",
        "",
        "The manuscript scaffold is present, but empirical manuscript outputs are blocked "
        "until generated tables, figures, audit files, and extension artifacts are frozen.",
        "",
        "Missing inputs:",
        *[f"- `{path.as_posix()}`" for path in missing_inputs],
        "",
        "Numerical manuscript claims must carry artifact mappings. AR innovations must not "
        "be described with causal language.",
        "",
    ]
    return "\n".join(lines)


def write_blocked_manuscript_report(*, output_path: Path, missing_inputs: tuple[Path, ...]) -> None:
    """Write the blocked manuscript report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_blocked_manuscript_report(missing_inputs=missing_inputs),
        encoding="utf-8",
    )


def render_manuscript_output_report(
    *,
    manuscript_path: Path,
    artifact_map_path: Path,
    upstream_report_paths: tuple[Path, ...],
) -> str:
    """Render the manuscript-output report from the manuscript and its artifact map.

    Args:
        manuscript_path: LaTeX manuscript to validate.
        artifact_map_path: Declared manuscript artifact mappings.
        upstream_report_paths: Generated reports whose verdicts the manuscript carries.

    Returns:
        The markdown report. Counts and verdicts are computed at render time from
        the manuscript, the artifact map, and the generated reports themselves.
    """
    artifact_map = load_artifact_map(artifact_map_path)
    mapped_paths = [Path(str(path)) for path in artifact_map["path"].astype(str)]
    absent = [path for path in mapped_paths if not path.exists()]
    issues = validate_manuscript(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
    )
    verdict = "manuscript_outputs_validated" if not issues else "manuscript_validation_failed"
    lines = [
        "# Manuscript Output Report",
        "",
        f"Verdict: `{verdict}`",
        "",
        f"Manuscript: `{manuscript_path.as_posix()}`",
        f"Artifact map: `{artifact_map_path.as_posix()}`",
        f"Mapped artifacts: {len(mapped_paths)}, of which {len(absent)} are absent",
        f"Validation issues: {len(issues)}",
        "",
        "## Validation Issues By Check",
        "",
        *_issue_count_lines(issues),
        "",
        "## Upstream Generated Report Verdicts",
        "",
        *markdown_table(
            ["Report", "Verdict"],
            [[path.as_posix(), report_verdict(path)] for path in upstream_report_paths],
        ),
        "",
        "Numerical manuscript claims carry artifact mappings, and every mapped artifact is "
        "checked for existence at render time. AR innovations are not described with causal "
        "language outside the approved identification sections.",
        "",
        "## Inputs Read",
        "",
        *path_bullets((manuscript_path, artifact_map_path, *upstream_report_paths)),
        "",
    ]
    return "\n".join(lines)


def write_manuscript_output_report(
    *,
    output_path: Path,
    manuscript_path: Path,
    artifact_map_path: Path,
    upstream_report_paths: tuple[Path, ...],
) -> None:
    """Write the manuscript-output report rendered from the manuscript and its map."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_manuscript_output_report(
            manuscript_path=manuscript_path,
            artifact_map_path=artifact_map_path,
            upstream_report_paths=upstream_report_paths,
        ),
        encoding="utf-8",
    )


def _issue_count_lines(issues: Sequence[ManuscriptIssue]) -> list[str]:
    if not issues:
        return ["No manuscript validation issue was raised."]
    counts = Counter(issue.check for issue in issues)
    return markdown_table(
        ["Check", "Issues"],
        [[check, counts[check]] for check in sorted(counts)],
    )


def _line_has_numeric_claim(line: str) -> bool:
    stripped = _strip_comment(line)
    if not stripped:
        return False
    ignored_prefixes = (
        "\\documentclass",
        "\\usepackage",
        "\\newcommand",
        "\\g@addto@macro",
        "\\title",
        "\\author",
        "\\authorrunning",
        "\\institute",
        "\\date",
        "\\bibliography",
        "\\bibliographystyle",
        "\\begin{tabular}",
        "\\cite",
    )
    if stripped.lstrip().startswith(ignored_prefixes):
        return False
    if (
        "\\cite" in stripped
        or "\\artifact{" in stripped
        or stripped.lstrip().startswith(("\\[", "\\]"))
    ):
        return False
    return NUMERIC_PATTERN.search(stripped) is not None


def _resolve_input(root: Path, target: str) -> Path:
    """Resolve one ``\\input`` target relative to the including document."""
    included = root / target
    if included.suffix != ".tex":
        included = included.with_suffix(".tex")
    return included


def _source_documents(
    manuscript_path: Path,
    manuscript: str,
    *,
    origin: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[tuple[str, str]]:
    r"""Return the manuscript and every document it includes, as whole texts.

    Paragraph-level rules need each document intact rather than the flattened
    line stream, because a blank line in an included file ends a paragraph there
    and must not be read as continuing one in the parent.

    Args:
        manuscript_path: Path to the document being expanded.
        manuscript: The document's source text.
        origin: Label for the document, empty for the top-level manuscript.
        seen: Documents already on the include path.

    Returns:
        Pairs of origin label and document text, parents before children.
    """
    documents = [(origin, manuscript)]
    path_guard = seen | {manuscript_path.resolve().as_posix()}
    for line in manuscript.splitlines():
        include_match = INPUT_PATTERN.search(_strip_comment(line))
        if include_match is None:
            continue
        included = _resolve_input(manuscript_path.parent, include_match.group("path"))
        if not included.exists() or included.resolve().as_posix() in path_guard:
            continue
        documents.extend(
            _source_documents(
                included,
                included.read_text(encoding="utf-8"),
                origin=included.as_posix(),
                seen=path_guard,
            )
        )
    return documents


def _missing_inputs(
    manuscript_path: Path,
    manuscript: str,
    *,
    origin: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[tuple[str, int, Path]]:
    r"""Find every ``\\input`` target that does not exist, following includes.

    Recursion mirrors :func:`_source_lines`, so a missing include inside a
    generated table is reported rather than silently skipped during expansion.

    Args:
        manuscript_path: Path to the document being scanned.
        manuscript: The document's source text.
        origin: Label for the document, empty for the top-level manuscript.
        seen: Documents already on the include path.

    Returns:
        Triples of origin label, line number, and the unresolved target path.
    """
    missing: list[tuple[str, int, Path]] = []
    path_guard = seen | {manuscript_path.resolve().as_posix()}
    for line_number, line in enumerate(manuscript.splitlines(), start=1):
        include_match = INPUT_PATTERN.search(_strip_comment(line))
        if include_match is None:
            continue
        included = _resolve_input(manuscript_path.parent, include_match.group("path"))
        if not included.exists():
            missing.append((origin, line_number, included))
            continue
        if included.resolve().as_posix() in path_guard:
            continue
        missing.extend(
            _missing_inputs(
                included,
                included.read_text(encoding="utf-8"),
                origin=included.as_posix(),
                seen=path_guard,
            )
        )
    return missing


def _source_lines(
    manuscript_path: Path,
    manuscript: str,
    *,
    origin: str = "",
    seen: frozenset[str] = frozenset(),
) -> list[tuple[str, int, str]]:
    r"""Yield the manuscript's lines with every ``\\input`` expanded in place.

    Generated result tables live in their own files so that they can be rebuilt
    from artifacts rather than transcribed. Expanding them here means the same
    numeric-traceability and table-source rules apply to a generated table as to
    a number written directly into the manuscript; without this, moving a table
    into an included file would quietly exempt it from every check.

    Expansion recurses, because a one-level expansion would let a wrapper file
    that merely includes another smuggle untagged numbers past the checks. A
    file already on the current include path is not re-entered, so a cyclic
    include terminates instead of recursing forever.

    Args:
        manuscript_path: Path to the document being expanded, used to resolve
            relative inputs.
        manuscript: The document's source text.
        origin: Label for the document, empty for the top-level manuscript.
        seen: Documents already on the include path, guarding against cycles.

    Returns:
        Triples of origin label, line number within that origin, and line text.
    """
    expanded: list[tuple[str, int, str]] = []
    path_guard = seen | {manuscript_path.resolve().as_posix()}
    for line_number, line in enumerate(manuscript.splitlines(), start=1):
        expanded.append((origin, line_number, line))
        include_match = INPUT_PATTERN.search(_strip_comment(line))
        if include_match is None:
            continue
        included = _resolve_input(manuscript_path.parent, include_match.group("path"))
        if not included.exists() or included.resolve().as_posix() in path_guard:
            continue
        expanded.extend(
            _source_lines(
                included,
                included.read_text(encoding="utf-8"),
                origin=included.as_posix(),
                seen=path_guard,
            )
        )
    return expanded


def _strip_comment(line: str) -> str:
    return line.split("%", 1)[0]


def _artifact_references(line: str) -> set[str]:
    references = {match.group("artifact") for match in ARTIFACT_TAG_PATTERN.finditer(line)}
    references.update(match.group("artifact") for match in LATEX_ARTIFACT_PATTERN.finditer(line))
    return references


def _validate_environment_artifacts(
    *,
    environment: str,
    start_line: int,
    artifact_paths: set[str],
    declared_paths: set[str],
) -> list[ManuscriptIssue]:
    if not artifact_paths:
        return [
            ManuscriptIssue(
                line_number=start_line,
                check="table_figure_artifact_source",
                message=f"{environment} environment lacks a machine-readable artifact source",
            )
        ]
    undeclared = sorted(path for path in artifact_paths if path not in declared_paths)
    return [
        ManuscriptIssue(
            line_number=start_line,
            check="table_figure_artifact_source",
            message=f"{environment} artifact source is not declared: {path}",
        )
        for path in undeclared
    ]


def _iter_paragraphs(manuscript: str) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    current_lines: list[str] = []
    current_start = 1
    for line_number, line in enumerate(manuscript.splitlines(), start=1):
        if line.strip():
            if not current_lines:
                current_start = line_number
            current_lines.append(line)
            continue
        if current_lines:
            paragraphs.append((current_start, "\n".join(current_lines)))
            current_lines = []
    if current_lines:
        paragraphs.append((current_start, "\n".join(current_lines)))
    return paragraphs


def _validate_empirical_context(start_line: int, paragraph: str) -> list[ManuscriptIssue]:
    context_match = EMPIRICAL_CONTEXT_PATTERN.search(paragraph)
    if context_match is None:
        return [
            ManuscriptIssue(
                line_number=start_line,
                check="empirical_paragraph_context",
                message="Empirical paragraph lacks a context declaration",
            )
        ]
    context_fields = {
        field.strip().split("=", 1)[0]
        for field in context_match.group("context").split(";")
        if field.strip()
    }
    missing_fields = REQUIRED_EMPIRICAL_CONTEXT_FIELDS - context_fields
    if not missing_fields:
        return []
    return [
        ManuscriptIssue(
            line_number=start_line,
            check="empirical_paragraph_context",
            message=(
                "Empirical paragraph context is missing fields: "
                f"{', '.join(sorted(missing_fields))}"
            ),
        )
    ]
