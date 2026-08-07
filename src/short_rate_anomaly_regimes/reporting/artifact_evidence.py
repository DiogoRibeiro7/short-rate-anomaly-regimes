"""Helpers for rendering generated reports from machine-readable artifacts.

Generated reports must never contain hand-typed empirical numbers. Every value a
report displays is read from a frozen artifact at render time through these
helpers, and every rendered report names the artifacts it read. Formatting is
display-only: values are shown at six significant digits and are otherwise
reproduced exactly as the artifact records them, including registered
classification strings.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd

#: Display precision for floating-point artifact values.
SIGNIFICANT_DIGITS = 6
#: Rendered stand-in for an artifact field that carries no value.
MISSING_VALUE = "n/a"
#: Rendered stand-in for a report that states no verdict.
UNSTATED_VERDICT = "not stated"

VERDICT_PATTERN = re.compile(r"^Verdict: `(?P<verdict>[^`]+)`", re.MULTILINE)


def missing_inputs(paths: Iterable[Path]) -> tuple[Path, ...]:
    """Return the declared inputs that are absent, in declaration order.

    Args:
        paths: Inputs a report requires before it can be rendered.

    Returns:
        The subset of `paths` that does not exist on disk.
    """
    return tuple(path for path in paths if not path.exists())


def load_json_artifact(path: Path) -> dict[str, Any]:
    """Load a JSON artifact object.

    Args:
        path: Artifact file to read.

    Returns:
        The decoded artifact mapping.

    Raises:
        ValueError: If the artifact does not decode to a JSON object.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object JSON in {path}")
    return payload


def artifact_field(payload: Mapping[str, Any], *keys: str) -> Any:
    """Read a nested artifact field, failing loudly when it is absent.

    Args:
        payload: Decoded artifact mapping.
        keys: Ordered nested keys to traverse.

    Returns:
        The stored artifact value.

    Raises:
        KeyError: If any key in the path is missing.
    """
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            raise KeyError(f"Artifact is missing field {'.'.join(keys)}")
        current = current[key]
    return current


def format_value(value: Any) -> str:
    """Format an artifact value for display without reinterpreting it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{SIGNIFICANT_DIGITS}g}"
    if value is None:
        return MISSING_VALUE
    return str(value)


def format_code(value: Any) -> str:
    """Format an artifact value as inline code."""
    return f"`{format_value(value)}`"


def format_sequence(values: Iterable[Any]) -> str:
    """Format artifact values as a comma-separated inline-code list."""
    formatted = [format_code(value) for value in values]
    return ", ".join(formatted) if formatted else "none"


def markdown_table(headers: Sequence[str], rows: Iterable[Sequence[Any]]) -> list[str]:
    """Render a markdown table whose cells are formatted artifact values."""
    lines = [
        "| " + " | ".join(str(header) for header in headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    lines.extend("| " + " | ".join(format_value(cell) for cell in row) + " |" for row in rows)
    return lines


def dataframe_table(frame: pd.DataFrame) -> list[str]:
    """Render a tabular artifact exactly as its columns and rows are stored."""
    headers = [str(column) for column in frame.columns]
    rows = [list(record) for record in frame.itertuples(index=False, name=None)]
    return markdown_table(headers, rows)


def path_bullets(paths: Iterable[Path]) -> list[str]:
    """Render POSIX-style bullet pointers to artifact paths."""
    return [f"- `{path.as_posix()}`" for path in paths]


def report_verdict(path: Path) -> str:
    """Read the verdict line of an already generated report.

    Args:
        path: Generated markdown report.

    Returns:
        The verdict token, or `UNSTATED_VERDICT` when the report states none.
    """
    match = VERDICT_PATTERN.search(path.read_text(encoding="utf-8"))
    return match.group("verdict") if match is not None else UNSTATED_VERDICT
