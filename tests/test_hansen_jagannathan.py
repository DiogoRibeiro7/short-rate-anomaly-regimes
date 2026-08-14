"""Tests for the Hansen-Jagannathan distance, Internet Appendix 2.9."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.run_hansen_jagannathan import hansen_jagannathan_distance

RESULTS = Path("artifacts/tables/cross_section/hansen_jagannathan_distance.csv")


def test_a_payoff_set_the_sdf_prices_exactly_has_zero_distance() -> None:
    """The distance measures mispricing, so exact pricing must give zero.

    The construction is exact rather than approximate: with payoffs
    ``R_it = (1 + e_it) / M_t`` and the noise demeaned in sample, every pricing
    error ``E[M R] - 1`` is zero by construction, whatever the payoffs look like.
    A distance that failed to vanish here would be measuring something other than
    the pricing errors.
    """
    rng = np.random.default_rng(3)
    months = pd.period_range("1980-01", periods=400, freq="M").to_timestamp(how="start")
    factors = pd.DataFrame({"market": rng.normal(0.0, 0.04, 400)}, index=months)
    # A strictly positive SDF, so dividing by it is safe.
    sdf = 1.0 - 2.0 * factors["market"].to_numpy()
    assert (sdf > 0).all()

    noise = rng.normal(0.0, 0.05, (400, 8))
    noise -= noise.mean(axis=0)
    payoffs = pd.DataFrame(
        (1.0 + noise) / sdf[:, None],
        index=months,
        columns=[f"payoff_{i}" for i in range(8)],
    )

    distance, coefficients, errors = hansen_jagannathan_distance(payoffs, factors)

    assert distance == pytest.approx(0.0, abs=1e-10)
    assert np.max(np.abs(errors.to_numpy(dtype=float))) == pytest.approx(0.0, abs=1e-10)
    # The recovered SDF is the one used to build the payoffs.
    assert coefficients["constant"] == pytest.approx(1.0, abs=1e-8)
    assert coefficients["market"] == pytest.approx(-2.0, abs=1e-8)


def test_mispricing_raises_the_distance_above_zero() -> None:
    """A payoff the SDF cannot price must move the distance off zero."""
    rng = np.random.default_rng(4)
    months = pd.period_range("1980-01", periods=400, freq="M").to_timestamp(how="start")
    factors = pd.DataFrame({"market": rng.normal(0.0, 0.04, 400)}, index=months)
    payoffs = pd.DataFrame(
        1.0 + rng.normal(0.005, 0.05, (400, 8)),
        index=months,
        columns=[f"payoff_{i}" for i in range(8)],
    )

    distance, _, _ = hansen_jagannathan_distance(payoffs, factors)

    assert distance > 0.0


def test_misaligned_inputs_are_rejected() -> None:
    rng = np.random.default_rng(5)
    months = pd.period_range("1980-01", periods=50, freq="M").to_timestamp(how="start")
    payoffs = pd.DataFrame(1.0 + rng.normal(0, 0.05, (50, 4)), index=months)
    factors = pd.DataFrame({"market": rng.normal(0, 0.04, 50)}, index=months)

    with pytest.raises(ValueError, match="share a time index"):
        hansen_jagannathan_distance(payoffs, factors.iloc[1:])


def test_the_generated_payoffs_are_gross_returns() -> None:
    """The appendix prices gross returns. Net returns would rescale everything silently.

    A gross monthly return sits near one; a net one near zero. Nothing in the
    arithmetic would complain about the wrong choice, so the artifact records the
    payoff count and this checks the distance is on the scale gross payoffs imply.
    """
    if not RESULTS.is_file():
        pytest.skip("the distance is not generated in this checkout")
    frame = pd.read_csv(RESULTS)

    # Seventy equity portfolios plus the gross risk-free rate.
    assert (frame["n_payoffs"] == 71).all()
    assert (frame["hansen_jagannathan_distance"] > 0.0).all()
    assert (frame["hansen_jagannathan_distance"] < 2.0).all()


def test_both_short_rate_models_price_better_than_the_capm() -> None:
    """The appendix reports the CAPM strongly rejected and the ICAPM not rejected.

    The p-value that supports that statement is not reconstructible, but the
    distance it is computed from is, and the ordering is a consequence the
    reconstruction can either meet or miss.
    """
    if not RESULTS.is_file():
        pytest.skip("the distance is not generated in this checkout")
    frame = pd.read_csv(RESULTS).set_index("model")
    distances = {
        str(key): float(value) for key, value in frame["hansen_jagannathan_distance"].items()
    }

    assert distances["market_plus_fedfunds_innovation"] < distances["capm"]
    assert distances["market_plus_tbill_innovation"] < distances["capm"]
