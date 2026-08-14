"""Tests for the article's second cross-sectional evaluation measure."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.article_second_pass import (
    article_cross_sectional_fit,
    kan_robotti_shanken_fit,
)

METRICS = Path("artifacts/tables/cross_section/alternative_fit_metrics.csv")


def _series(values: list[float]) -> pd.Series:
    return pd.Series(values, index=[f"asset_{i}" for i in range(len(values))], dtype=float)


def test_the_two_measures_differ_only_in_the_denominator() -> None:
    """The alternative divides by the second moment where the article divides by the variance."""
    returns = _series([0.4, 0.7, 1.1, 0.9])
    errors = _series([0.05, -0.02, 0.01, -0.04])

    variance = float(np.var(returns.to_numpy()))
    second_moment = float(np.mean(np.square(returns.to_numpy())))
    numerator = float(np.var(errors.to_numpy()))

    assert article_cross_sectional_fit(returns, errors) == pytest.approx(1 - numerator / variance)
    assert kan_robotti_shanken_fit(returns, errors) == pytest.approx(1 - numerator / second_moment)


def test_the_alternative_is_larger_whenever_average_returns_are_not_centred() -> None:
    """The second moment exceeds the variance unless the mean is zero.

    This is the whole mechanism behind the article's caution, so it is asserted
    rather than left as an observation: a nonzero cross-sectional mean inflates
    the denominator, and the measure rises without the pricing errors changing.
    """
    errors = _series([0.05, -0.02, 0.01, -0.04])
    offset = _series([0.4, 0.7, 1.1, 0.9])
    centred = offset - offset.mean()

    assert kan_robotti_shanken_fit(offset, errors) > article_cross_sectional_fit(offset, errors)
    # With a zero cross-sectional mean the second moment is the variance, so the
    # two measures coincide and the gap closes.
    assert kan_robotti_shanken_fit(centred, errors) == pytest.approx(
        article_cross_sectional_fit(centred, errors)
    )


def test_a_model_explaining_no_dispersion_can_still_score_well() -> None:
    """The article's warning, as a constructed case.

    Pricing errors equal to the demeaned average returns explain none of the
    cross-sectional dispersion, so the paper's metric is exactly zero. The
    alternative measure is well above zero purely because average returns have a
    nonzero level.
    """
    returns = _series([0.8, 1.0, 1.2, 1.4])
    errors = returns - returns.mean()

    assert article_cross_sectional_fit(returns, errors) == pytest.approx(0.0)
    assert kan_robotti_shanken_fit(returns, errors) > 0.85


def test_misaligned_or_degenerate_inputs_are_rejected() -> None:
    returns = _series([0.4, 0.7])
    with pytest.raises(ValueError, match="share an index"):
        kan_robotti_shanken_fit(returns, _series([0.1, 0.2]).rename(index={"asset_0": "other"}))
    with pytest.raises(ValueError, match="second moment"):
        kan_robotti_shanken_fit(_series([0.0, 0.0]), _series([0.1, 0.2]))


def test_every_system_with_a_negative_article_fit_scores_positive_on_the_alternative() -> None:
    """The generated evidence for the article's caution.

    Eight systems price the cross-section worse than a constant does, which is
    what a negative equation (6) means. Every one of them scores positive under
    the alternative measure, so reporting that measure alone would describe a
    model that fails as one that succeeds.
    """
    if not METRICS.is_file():
        pytest.skip("the alternative fit metrics are not generated in this checkout")
    frame = pd.read_csv(METRICS)
    negative = frame[frame["article_cross_sectional_fit"] < 0.0]

    assert not negative.empty, "the comparison is only meaningful where the paper's metric fails"
    assert (negative["kan_robotti_shanken_fit"] > 0.0).all()
    assert (frame["alternative_minus_article"] >= 0.0).all(), (
        "the alternative measure cannot be below the article's on excess returns"
    )
