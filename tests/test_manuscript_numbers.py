"""Check that the manuscript's headline numbers still match their artifacts.

The manuscript validator requires every numeric line to carry a declared
``% artifact:`` tag, which establishes that a number has a source. It does not
check that the number still equals what that source says. Every defect found in
three review passes lived in exactly that gap: the estimates were right and the
prose describing them had drifted. The registry grew from 212 rows to 296 and
the body said 296 unique cells when there were 207; a layer note asserted Table 5
offered nothing to audit after it had been audited; the appendix listed the
useless-factor bootstrap as not implemented after it was implemented.

Each fact below recomputes a headline number from the shipped artifacts and
requires the resulting string to appear in the manuscript. When an artifact
moves, the recomputation moves with it and the assertion fails until the prose
is corrected, which is the direction of enforcement the validator was missing.

These are deliberately the numbers a reader carries away, not every number in the
paper. A claim that cannot be recomputed from an artifact does not belong here;
it belongs in the artifact first.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import numpy as np
import pandas as pd
import pytest

MANUSCRIPT = Path("paper/manuscript.tex")
TABLE_ROOT = Path("paper/tables")
AUDIT = Path("artifacts/audit/published_target_audit.csv")
LAYERS = Path("artifacts/audit/replication_layer_classification.csv")
FORECASTS = Path("artifacts/tables/out_of_sample/forecast_metrics.csv")
COVARIANCE = Path("artifacts/tables/cross_section/covariance_representation.csv")
HJ_DISTANCE = Path("artifacts/tables/cross_section/hansen_jagannathan_distance.csv")
CELL_KEY = ["source_table", "portfolio_set", "model", "statistic"]


def _typeset_text() -> str:
    """Return the manuscript together with the tables it inputs.

    Several headline numbers reach the page through generated tables rather than
    through prose, so reading ``manuscript.tex`` alone would declare a number
    missing that the paper does in fact print. The built document is the object
    a reader sees, and it is the object checked here.
    """
    parts = [MANUSCRIPT.read_text(encoding="utf-8")]
    parts.extend(path.read_text(encoding="utf-8") for path in sorted(TABLE_ROOT.glob("*.tex")))
    # Lowercased: a sentence-initial "All 45" and a mid-sentence "all 45" are the
    # same claim, and this check is about the number rather than the casing.
    return "\n".join(parts).lower()


def _unique_cells() -> pd.DataFrame:
    """Collapse the rows that repeat a point estimate under two uncertainty measures."""
    return pd.read_csv(AUDIT).drop_duplicates(subset=CELL_KEY)


def _audit_totals() -> list[str]:
    cells = _unique_cells()
    recovered = int((cells["status"] == "recovered_within_published_rounding").sum())
    return [f"{len(cells)} unique published cells", f"{recovered} fall inside"]


def _layer_counts() -> list[str]:
    layers = pd.read_csv(LAYERS).set_index("layer")
    recovered = {key: int(value) for key, value in layers["cells_recovered"].items()}
    registry = {key: int(value) for key, value in layers["cells_in_registry"].items()}
    return [f"{recovered[layer]} of {registry[layer]}" for layer in ("R1b", "R1c", "R1d", "R1e")]


def _table_five() -> list[str]:
    cells = _unique_cells()
    block = cells[cells["source_table"] == "Table 5"]
    recovered = int((block["status"] == "recovered_within_published_rounding").sum())
    signs = int(
        (
            np.sign(block["generated_value"].astype(float))
            == np.sign(block["published_value"].astype(float))
        ).sum()
    )
    assert signs == len(block), "the manuscript claims every Table 5 cell agrees in sign"
    return [f"{len(block)} published cells, {recovered} fall inside"]


def _bootstrap_agreement() -> list[str]:
    audit = pd.read_csv(AUDIT)
    block = audit[audit["uncertainty_type"] == "empirical_bootstrap_p_value"].copy()
    block["published_uncertainty"] = block["published_uncertainty"].astype(float)
    block["generated_uncertainty"] = block["generated_uncertainty"].astype(float)

    prices = block[block["statistic"].isin(["lambda_rate", "lambda_market"])]
    agree = int(
        ((prices["published_uncertainty"] < 0.05) == (prices["generated_uncertainty"] < 0.05)).sum()
    )
    assert agree == len(prices), "the manuscript claims every risk-price verdict agrees"
    return [f"all {agree} risk-price cells", f"{agree} published"]


def _out_of_sample() -> list[str]:
    skill = {
        str(key): float(cast("float", value))
        for key, value in pd.read_csv(FORECASTS).set_index("model")["out_of_sample_r2"].items()
    }
    model = skill["two_factor_market_rate"]
    zero = skill["zero_excess_return"]
    return [f"{model:.4f}", f"{abs(zero):.4f}"]


def _hansen_jagannathan() -> list[str]:
    """The distances the appendix section reports, and the ordering behind them."""
    distances = {
        str(key): float(value)
        for key, value in pd.read_csv(HJ_DISTANCE)
        .set_index("model")["hansen_jagannathan_distance"]
        .items()
    }
    assert distances["market_plus_fedfunds_innovation"] < distances["capm"], (
        "the manuscript states the ICAPM prices better than the CAPM under this metric"
    )
    return [
        f"{distances['market_plus_fedfunds_innovation']:.4f}",
        f"{distances['market_plus_tbill_innovation']:.4f}",
        f"{distances['capm']:.4f}",
    ]


def _covariance_representation() -> list[str]:
    """The covariance prices, and the identity the appendix predicts."""
    frame = pd.read_csv(COVARIANCE)
    joint = frame[frame["portfolio_set"] == "all_seven_families_joint"]
    rate = float(joint["gamma_FFR_innovation"].dropna().iloc[0])
    market = float(joint["gamma_RM"].dropna().iloc[0])
    assert (frame["max_abs_price_gap_against_transform"] < 1e-8).all(), (
        "the manuscript states both routes agree; they no longer do"
    )
    return [f"{abs(rate):.3f}", f"{abs(market):.3f}"]


#: Name to the strings the manuscript must contain, recomputed from artifacts.
FACTS: dict[str, Callable[[], list[str]]] = {
    "cell-level audit totals": _audit_totals,
    "replication layer counts": _layer_counts,
    "Table 5 recovery and signs": _table_five,
    "bootstrap inferential agreement": _bootstrap_agreement,
    "out-of-sample skill": _out_of_sample,
    "Hansen-Jagannathan distances": _hansen_jagannathan,
    "covariance representation prices": _covariance_representation,
}


@pytest.mark.parametrize("name", sorted(FACTS))
def test_manuscript_states_the_number_its_artifact_reports(name: str) -> None:
    """A headline number must equal what the artifact behind it says."""
    required = (AUDIT, LAYERS, FORECASTS, COVARIANCE, HJ_DISTANCE)
    if not all(path.is_file() for path in required):
        pytest.skip("the audit artifacts are not generated in this checkout")
    manuscript = _typeset_text()

    missing = [fragment for fragment in FACTS[name]() if fragment.lower() not in manuscript]

    assert not missing, (
        f"{name}: the artifacts report values the manuscript does not state. "
        f"Missing fragments: {missing}. Either the prose is stale or the artifact moved."
    )


def test_every_layer_the_classifier_reports_is_described_in_the_manuscript() -> None:
    """A layer that gains cells must not stay described as having no target.

    R1b carried a note saying the article tabulated nothing to compare, which
    stopped being true when Table 5 was audited into it. Nothing failed, because
    no check tied the note to the classifier's own output.
    """
    if not LAYERS.is_file():
        pytest.skip("the layer classification is not generated in this checkout")
    layers = pd.read_csv(LAYERS)
    manuscript = MANUSCRIPT.read_text(encoding="utf-8")

    with_cells = layers[layers["cells_in_registry"] > 0]
    assert not with_cells.empty
    assert "carries no statistic-level target" not in manuscript, (
        "a layer now carries cells, so the manuscript may not say the layer has no target"
    )


def test_the_bootstrap_is_not_described_as_unimplemented() -> None:
    """The appendix listed the bootstrap as not implemented after it was implemented."""
    manuscript = MANUSCRIPT.read_text(encoding="utf-8")
    diagnostics = Path("artifacts/diagnostics/useless_factor_bootstrap.json")
    if not diagnostics.is_file():
        pytest.skip("the bootstrap has not been run in this checkout")

    payload = json.loads(diagnostics.read_text(encoding="utf-8"))
    assert payload["systems"] > 0
    for stale in ("which is\nnot implemented here", "not implemented here"):
        assert stale not in manuscript, "the bootstrap has been run; the manuscript says otherwise"
