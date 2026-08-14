"""Tests for the first-difference short-rate factor robustness."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

RESULTS = Path("artifacts/tables/cross_section/first_difference_factors.csv")


def _results() -> pd.DataFrame:
    if not RESULTS.is_file():
        pytest.skip("the first-difference estimates are not generated in this checkout")
    return pd.read_csv(RESULTS)


def test_both_definitions_are_estimated_on_the_same_window() -> None:
    """A first difference is undefined in the first month, and the comparison must not
    inherit that as a sample difference.

    Estimating the AR(1) variant on one extra month would leave any gap between
    the two open to being a sample effect rather than a definition effect, which
    is the only thing this comparison is for.
    """
    frame = _results()

    assert frame["n_months"].nunique() == 1, "the two definitions must share one window"


def test_the_recovered_timing_convention_is_not_carrying_the_result() -> None:
    """The paper's factor needs a convention the article never states. This one does not.

    The AR(1) innovation required choosing between two admissible timing
    conventions, recovered by testing them against the published slopes. A first
    difference has nothing to recover. If the two disagreed, the reconstruction's
    central factor would rest on a choice the article does not license.
    """
    frame = _results()
    joint = frame[frame["portfolio_set"] == "all_seven_families_joint"]

    for rate, block in joint.groupby("rate"):
        indexed = block.set_index("factor_definition")
        prices = {str(key): float(value) for key, value in indexed["lambda_rate"].items()}
        t_statistics = {str(key): float(value) for key, value in indexed["shanken_t_rate"].items()}
        assert set(prices) == {"first_difference", "ar1_innovation"}, rate
        # Both negative, both significant, and close in magnitude.
        assert all(value < 0.0 for value in prices.values()), rate
        assert all(value < -1.96 for value in t_statistics.values()), rate
        assert prices["first_difference"] == pytest.approx(prices["ar1_innovation"], rel=0.05), rate


def test_the_sign_and_significance_survive_across_asset_sets() -> None:
    """The robustness claim is about the whole grid, not the headline system alone."""
    frame = _results()
    priced = frame[(frame["lambda_rate"] < 0.0) & (frame["shanken_t_rate"] < -1.96)]

    assert len(priced) >= len(frame) - 2, (
        "the rate price should stay negative and significant on all but a couple of systems"
    )
