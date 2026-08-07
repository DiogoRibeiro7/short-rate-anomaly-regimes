"""Tests for the generated manuscript result tables."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

SCRIPT = Path("scripts/build_manuscript_tables.py")
FIGURE_SCRIPT = Path("scripts/build_manuscript_figures.py")
TABLE_ROOT = Path("paper/tables")
FIGURE_ROOT = Path("paper/figures")
MANUSCRIPT = Path("paper/manuscript.tex")


def _load_builder(script: Path = SCRIPT) -> object:
    """Import a generator script as a module."""
    spec = importlib.util.spec_from_file_location(script.stem, script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.skipif(
    not Path("artifacts/tables/cross_section/baseline_risk_prices.csv").exists(),
    reason="generated result artifacts are not present in this checkout",
)


def test_committed_tables_match_a_fresh_regeneration(tmp_path: Path) -> None:
    """The committed tables must be exactly what the generator produces.

    This is the drift guard. If an artifact is regenerated and a number moves,
    the paper must move with it; a table that no longer matches its source is
    the failure mode this whole pipeline exists to prevent.
    """
    module = _load_builder()
    committed = {path.name: path.read_text(encoding="utf-8") for path in TABLE_ROOT.glob("*.tex")}
    assert committed, "no generated tables are committed"

    module.TABLE_ROOT = tmp_path  # type: ignore[attr-defined]
    regenerated = {path.name: path.read_text(encoding="utf-8") for path in module.build_all()}  # type: ignore[attr-defined]

    assert set(regenerated) == set(committed)
    for name in sorted(committed):
        assert regenerated[name] == committed[name], f"{name} has drifted from its artifacts"


def test_every_generated_table_is_included_by_the_manuscript() -> None:
    """A generated table that nothing includes is dead weight and must not linger."""
    manuscript = MANUSCRIPT.read_text(encoding="utf-8")
    included = set(re.findall(r"\\input\{tables/([A-Za-z0-9_]+)\}", manuscript))
    generated = {path.stem for path in TABLE_ROOT.glob("*.tex")}
    assert generated == included


def test_every_numeric_line_in_a_generated_table_names_its_artifact() -> None:
    """Generated rows obey the same traceability rule as the manuscript itself."""
    numeric = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?![A-Za-z_])")
    for path in sorted(TABLE_ROOT.glob("*.tex")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            body = line.split("%", 1)[0]
            # Column widths are layout, not claims; the validator exempts them too.
            if body.lstrip().startswith("\\begin{tabular}"):
                continue
            if numeric.search(body):
                assert "% artifact:" in line, f"{path}:{number} carries a number with no artifact"


def test_generated_tables_declare_their_artifacts_in_the_map() -> None:
    """Every artifact a table cites must be declared for the validator to resolve."""
    declared = {
        row.split(",")[1]
        for row in Path("research/manuscript_artifact_map.csv")
        .read_text(encoding="utf-8")
        .splitlines()[1:]
        if row.strip()
    }
    cited: set[str] = set()
    for path in TABLE_ROOT.glob("*.tex"):
        cited.update(re.findall(r"%\s*artifact:\s*(\S+)", path.read_text(encoding="utf-8")))
    assert cited
    assert cited <= declared, f"undeclared artifacts: {sorted(cited - declared)}"


def test_committed_figures_match_a_fresh_regeneration(tmp_path: Path) -> None:
    """The committed figures must be exactly what the generator produces.

    Figure output is made deterministic by suppressing the embedded creation
    date, so a byte comparison detects a changed artifact and nothing else.
    """
    module = _load_builder(FIGURE_SCRIPT)
    committed = {path.name: path.read_bytes() for path in FIGURE_ROOT.glob("*.pdf")}
    assert committed, "no generated figures are committed"

    module.FIGURE_ROOT = tmp_path  # type: ignore[attr-defined]
    regenerated = {path.name: path.read_bytes() for path in module.build_all()}  # type: ignore[attr-defined]

    assert set(regenerated) == set(committed)
    for name in sorted(committed):
        assert regenerated[name] == committed[name], f"{name} has drifted from its artifacts"


def test_every_generated_figure_is_included_by_the_manuscript() -> None:
    """A generated figure the manuscript never shows must not linger."""
    manuscript = MANUSCRIPT.read_text(encoding="utf-8")
    # The options group is optional: a bare \includegraphics{...} must still count.
    pattern = r"\\includegraphics(?:\[[^]]*\])?\{figures/([A-Za-z0-9_]+)\}"
    included = set(re.findall(pattern, manuscript))
    generated = {path.stem for path in FIGURE_ROOT.glob("*.pdf")}
    assert generated == included
