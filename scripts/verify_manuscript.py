"""Verify manuscript traceability and language rules."""

from __future__ import annotations

from pathlib import Path

from short_rate_anomaly_regimes.reporting.manuscript import validate_manuscript


def main() -> None:
    """Run manuscript validation checks."""
    issues = validate_manuscript(
        manuscript_path=Path("paper/manuscript.tex"),
        artifact_map_path=Path("research/manuscript_artifact_map.csv"),
    )
    if issues:
        formatted = "\n".join(
            f"{issue.line_number}: {issue.check}: {issue.message}" for issue in issues
        )
        raise RuntimeError(f"Manuscript validation failed:\n{formatted}")
    print("Manuscript validation passed")


if __name__ == "__main__":
    main()
