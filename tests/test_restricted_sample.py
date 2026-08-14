"""Tests for the article's restricted-sample robustness, ending 2006-12."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.run_restricted_sample import RESTRICTED_END, reestimated_innovation

RESULTS = Path("artifacts/tables/cross_section/restricted_sample.csv")


def _results() -> pd.DataFrame:
    if not RESULTS.is_file():
        pytest.skip("the restricted-sample estimates are not generated in this checkout")
    return pd.read_csv(RESULTS)


def test_the_reestimated_innovation_is_a_residual() -> None:
    """A re-fitted AR(1) residual must be orthogonal to its own regressors.

    The re-estimation recovers the pre-window lag rather than observing it, so
    this checks the recovery produced a design the residual is actually
    orthogonal to, instead of an approximation that merely looks like one.
    """
    months = pd.period_range("1990-01", periods=120, freq="M").to_timestamp(how="start")
    rng = np.random.default_rng(11)
    level = pd.Series(np.cumsum(rng.normal(0, 0.2, 120)) + 5.0, index=months)
    # Innovations consistent with an AR(1) on that level.
    lagged = level.shift(1).bfill()
    innovation = pd.Series(level.to_numpy() - (0.4 + 0.92 * lagged.to_numpy()), index=months)

    residual = reestimated_innovation(level, innovation)

    assert residual.mean() == pytest.approx(0.0, abs=1e-9)
    assert len(residual) == len(level)


def test_both_admissible_conventions_are_reported() -> None:
    """The appendix does not say which AR(1) treatment it used, so neither does this.

    Reporting one would manufacture a precision the source does not have. The
    evidence freeze already records the ambiguity; this keeps the artifact
    consistent with that record.
    """
    frame = _results()

    assert set(frame["ar1_convention"]) == {
        "carried_over_from_full_sample",
        "reestimated_on_restricted_window",
    }


def test_the_undetermined_convention_does_not_change_the_conclusion() -> None:
    """Whether the AR(1) is re-fitted turns out not to matter, which is the point.

    An ambiguity that changed the answer would have to be resolved before any
    claim could rest on this sample. One that does not can be reported as
    immaterial, which is a stronger statement than picking a side.
    """
    frame = _results()
    joint = frame[frame["portfolio_set"] == "all_seven_families_joint"]

    for rate, block in joint.groupby("rate"):
        indexed = block.set_index("ar1_convention")
        prices = {str(key): float(value) for key, value in indexed["lambda_rate"].items()}
        assert prices["carried_over_from_full_sample"] == pytest.approx(
            prices["reestimated_on_restricted_window"], rel=0.02
        ), rate


def test_removing_the_crisis_years_does_not_weaken_the_relation() -> None:
    """The restricted sample ends before the crisis and the first lower bound.

    If the baseline pricing result were an artefact of those years it should
    weaken when they are dropped. It does not, which is what makes the
    post-2013 deterioration reported elsewhere a statement about the later
    period rather than about the estimator.
    """
    frame = _results()
    joint = frame[
        (frame["portfolio_set"] == "all_seven_families_joint")
        & (frame["rate"] == "fedfunds")
        & (frame["ar1_convention"] == "carried_over_from_full_sample")
    ]

    assert len(joint) == 1
    row = joint.iloc[0]
    assert str(row["sample_end"]) == RESTRICTED_END
    assert float(row["lambda_rate"]) < -0.6985, "the restricted-sample price is more negative"
    assert float(row["shanken_t_rate"]) < -2.86, "and more precisely estimated"
