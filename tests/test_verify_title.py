import pytest
from scripts.verify_title import extract_title


def test_extract_title_returns_first_latex_title() -> None:
    expected = "Short Term Interest Rate Innovations Across Monetary Regimes"
    manuscript = f"\\title{{{expected}}}\n"

    assert extract_title(manuscript) == expected


def test_extract_title_rejects_missing_title() -> None:
    with pytest.raises(RuntimeError, match="No LaTeX title"):
        extract_title("\\section{Introduction}")


def test_extract_title_rejects_unterminated_title() -> None:
    with pytest.raises(RuntimeError, match="Unterminated"):
        extract_title("\\title{Incomplete")
