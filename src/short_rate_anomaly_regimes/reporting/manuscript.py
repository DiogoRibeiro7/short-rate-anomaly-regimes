"""Manuscript traceability and language checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TITLE_PATTERN = re.compile(r"\\title\{(?P<title>[^}]*)\}")
SECTION_PATTERN = re.compile(r"\\section\{(?P<section>[^}]*)\}")
NUMERIC_PATTERN = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?![A-Za-z_])")
ARTIFACT_TAG_PATTERN = re.compile(r"%\s*artifact:\s*(?P<artifact>\S+)")
RESTRICTED_LANGUAGE_PATTERN = re.compile(r"\b(cause|effect|policy shock)\b", re.IGNORECASE)
APPROVED_LANGUAGE_SECTIONS = {"Policy and Information Shocks"}


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

    current_section = ""
    for line_number, line in enumerate(manuscript.splitlines(), start=1):
        section_match = SECTION_PATTERN.search(line)
        if section_match is not None:
            current_section = section_match.group("section")
        if _line_has_numeric_claim(line):
            tag_match = ARTIFACT_TAG_PATTERN.search(line)
            if tag_match is None:
                issues.append(
                    ManuscriptIssue(
                        line_number=line_number,
                        check="numeric_artifact_mapping",
                        message="Numeric token lacks an artifact tag on the same line",
                    )
                )
            elif tag_match.group("artifact") not in declared_paths:
                issues.append(
                    ManuscriptIssue(
                        line_number=line_number,
                        check="numeric_artifact_mapping",
                        message=f"Artifact tag is not declared: {tag_match.group('artifact')}",
                    )
                )
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
    ]
    return "\n".join(lines)


def write_blocked_manuscript_report(*, output_path: Path, missing_inputs: tuple[Path, ...]) -> None:
    """Write the blocked manuscript report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_blocked_manuscript_report(missing_inputs=missing_inputs),
        encoding="utf-8",
    )


def _line_has_numeric_claim(line: str) -> bool:
    stripped = _strip_comment(line)
    if not stripped:
        return False
    ignored_prefixes = (
        "\\documentclass",
        "\\usepackage",
        "\\newcommand",
        "\\title",
        "\\author",
        "\\date",
        "\\bibliography",
        "\\bibliographystyle",
        "\\cite",
    )
    if stripped.lstrip().startswith(ignored_prefixes):
        return False
    if "\\cite" in stripped or stripped.lstrip().startswith(("\\[", "\\]")):
        return False
    return NUMERIC_PATTERN.search(stripped) is not None


def _strip_comment(line: str) -> str:
    return line.split("%", 1)[0]
