"""Verify the manuscript title follows the project's title convention."""

from __future__ import annotations

from pathlib import Path


def extract_title(manuscript: str) -> str:
    """Extract the first LaTeX ``\\title{...}`` value.

    Args:
        manuscript: Complete LaTeX manuscript text.

    Returns:
        The title content without the surrounding LaTeX command.

    Raises:
        RuntimeError: If a title declaration is absent or unterminated.
    """
    prefix = r"\title{"
    start = manuscript.find(prefix)
    if start < 0:
        raise RuntimeError("No LaTeX title found")

    content_start = start + len(prefix)
    content_end = manuscript.find("}", content_start)
    if content_end < 0:
        raise RuntimeError("Unterminated LaTeX title")

    return manuscript[content_start:content_end]


def main() -> None:
    """Reject question marks or colons in the manuscript title."""
    manuscript = Path("paper/manuscript.tex").read_text(encoding="utf-8")
    title = extract_title(manuscript)
    forbidden = [symbol for symbol in ("?", ":") if symbol in title]
    if forbidden:
        raise RuntimeError(f"Forbidden title punctuation found: {forbidden}")
    print(title)


if __name__ == "__main__":
    main()
