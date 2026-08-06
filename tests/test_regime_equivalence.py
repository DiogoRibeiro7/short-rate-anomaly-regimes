"""Tests for the regime-specific fitted premia and the H3 equivalence rule."""

from __future__ import annotations

from typing import Any, TypedDict

import numpy as np
import numpy.typing as npt
import pytest

from short_rate_anomaly_regimes.regimes.equivalence import (
    CONFIRMATORY_RULE,
    STATISTIC_NAMES,
    bootstrap_regime_premia,
    classify_equivalence,
    evaluate_regime_sample,
    paired_difference_draws,
)

FloatArray = npt.NDArray[np.floating[Any]]


class RegimeSample(TypedDict):
    """The four arrays that describe one regime window."""

    rate_level: FloatArray
    lagged_rate_level: FloatArray
    market: FloatArray
    excess_returns: FloatArray


def _sample(n_months: int = 180, n_assets: int = 8, seed: int = 7) -> RegimeSample:
    """Build a small regime sample with a genuine rate exposure."""
    rng = np.random.default_rng(seed)
    lagged = np.empty(n_months)
    lagged[0] = 5.0
    for position in range(1, n_months):
        lagged[position] = 0.95 * lagged[position - 1] + rng.normal(0.0, 0.3)
    level = 0.2 + 0.95 * lagged + rng.normal(0.0, 0.3, n_months)
    innovation = level - (0.2 + 0.95 * lagged)
    market = rng.normal(0.5, 4.0, n_months)
    rate_betas = np.linspace(-1.5, 1.5, n_assets)
    returns = (
        np.outer(market, np.linspace(0.7, 1.3, n_assets))
        + np.outer(innovation, rate_betas)
        + rng.normal(0.0, 2.0, (n_months, n_assets))
    )
    return {
        "rate_level": level,
        "lagged_rate_level": lagged,
        "market": market,
        "excess_returns": returns,
    }


def test_evaluate_regime_sample_recovers_the_premium_identity() -> None:
    """The premia must equal the rate betas times the rate risk price."""
    sample = _sample()
    premia, statistics = evaluate_regime_sample(**sample)

    n_months = sample["excess_returns"].shape[0]
    design = np.column_stack([np.ones(n_months), sample["lagged_rate_level"]])
    innovation = (
        sample["rate_level"] - design @ np.linalg.lstsq(design, sample["rate_level"], rcond=None)[0]
    )
    factors = np.column_stack([np.ones(n_months), sample["market"], innovation])
    betas = np.linalg.lstsq(factors, sample["excess_returns"], rcond=None)[0][1:, :].T

    expected = betas[:, 1] * statistics["lambda_rate"]
    np.testing.assert_allclose(premia, expected, rtol=0, atol=1e-12)
    assert set(statistics) == set(STATISTIC_NAMES)


def test_evaluate_regime_sample_is_invariant_to_rescaling_the_rate() -> None:
    """Fitted premia must not move when the short-rate series is rescaled.

    This is the property that licenses a within-regime innovation for a
    cross-regime comparison, so it is asserted rather than assumed.
    """
    sample = _sample()
    premia, statistics = evaluate_regime_sample(**sample)
    rescaled: RegimeSample = {
        **sample,
        "rate_level": sample["rate_level"] * 100.0,
        "lagged_rate_level": sample["lagged_rate_level"] * 100.0,
    }
    rescaled_premia, rescaled_statistics = evaluate_regime_sample(**rescaled)

    np.testing.assert_allclose(premia, rescaled_premia, rtol=1e-10, atol=1e-12)
    assert rescaled_statistics["lambda_rate"] != pytest.approx(statistics["lambda_rate"])
    for name in ("rmse", "max_abs_error", "article_fit", "dispersion"):
        assert rescaled_statistics[name] == pytest.approx(statistics[name], rel=1e-10)


def test_evaluate_regime_sample_rejects_misaligned_inputs() -> None:
    """Inputs covering different months must be refused."""
    sample = _sample()
    sample["market"] = sample["market"][:-1]
    with pytest.raises(ValueError, match="same months"):
        evaluate_regime_sample(**sample)


def test_bootstrap_point_estimate_matches_a_direct_evaluation() -> None:
    """The reported point estimate must be the estimator, not a draw average."""
    sample = _sample()
    assets = tuple(f"asset_{index:02d}" for index in range(sample["excess_returns"].shape[1]))
    result = bootstrap_regime_premia(
        regime_id="test", assets=assets, block_length=6, draws=50, seed=11, **sample
    )
    premia, statistics = evaluate_regime_sample(**sample)

    np.testing.assert_allclose(result.point_premia, premia, rtol=0, atol=1e-12)
    assert result.point_statistics == statistics
    assert result.premium_draws.shape == (result.successful_draws, len(assets))
    assert result.successful_draws <= result.draws
    for name in STATISTIC_NAMES:
        assert result.statistic_draws[name].size == result.successful_draws


def test_bootstrap_is_reproducible_under_the_same_seed() -> None:
    """A frozen seed must give an identical distribution."""
    sample = _sample()
    assets = tuple(f"asset_{index:02d}" for index in range(sample["excess_returns"].shape[1]))
    first = bootstrap_regime_premia(
        regime_id="a", assets=assets, block_length=6, draws=40, seed=3, **sample
    )
    second = bootstrap_regime_premia(
        regime_id="a", assets=assets, block_length=6, draws=40, seed=3, **sample
    )
    third = bootstrap_regime_premia(
        regime_id="a", assets=assets, block_length=6, draws=40, seed=4, **sample
    )

    np.testing.assert_array_equal(first.premium_draws, second.premium_draws)
    assert not np.array_equal(first.premium_draws, third.premium_draws)


def test_bootstrap_rejects_mismatched_asset_labels() -> None:
    """Asset labels must describe the return matrix."""
    sample = _sample()
    with pytest.raises(ValueError, match="disagree"):
        bootstrap_regime_premia(
            regime_id="test", assets=("only_one",), block_length=6, draws=5, seed=1, **sample
        )


def test_evaluate_regime_sample_rejects_a_degenerate_cross_section() -> None:
    """Identical average returns leave the fit metric undefined."""
    sample = _sample(n_assets=4)
    # Identical columns give exactly equal average returns, so the denominator
    # of the fit metric is exactly zero rather than merely small.
    sample["excess_returns"] = np.tile(sample["excess_returns"][:, :1], (1, 4))
    with pytest.raises(ValueError, match="variance of average returns is zero"):
        evaluate_regime_sample(**sample)


def test_bootstrap_records_failed_draws_without_counting_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A draw that cannot be solved is skipped, not silently filled in."""
    sample = _sample(n_assets=5)
    assets = tuple(f"asset_{index:02d}" for index in range(5))
    calls = {"n": 0}
    real = evaluate_regime_sample

    def flaky(**kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] % 3 == 0:
            raise np.linalg.LinAlgError("singular")
        return real(**kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "short_rate_anomaly_regimes.regimes.equivalence.evaluate_regime_sample", flaky
    )
    result = bootstrap_regime_premia(
        regime_id="flaky", assets=assets, block_length=6, draws=30, seed=1, **sample
    )
    assert 0 < result.successful_draws < result.draws
    assert result.premium_draws.shape == (result.successful_draws, len(assets))
    assert np.isfinite(result.premium_draws).all()


def test_bootstrap_raises_when_every_draw_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """A wholly failed bootstrap must be an error, not an empty distribution."""
    sample = _sample(n_assets=5)
    assets = tuple(f"asset_{index:02d}" for index in range(5))
    calls = {"n": 0}
    real = evaluate_regime_sample

    def only_the_point(**kwargs: object) -> object:
        calls["n"] += 1
        if calls["n"] == 1:
            return real(**kwargs)  # type: ignore[arg-type]
        raise np.linalg.LinAlgError("singular")

    monkeypatch.setattr(
        "short_rate_anomaly_regimes.regimes.equivalence.evaluate_regime_sample", only_the_point
    )
    with pytest.raises(ValueError, match="Every bootstrap draw failed for regime doomed"):
        bootstrap_regime_premia(
            regime_id="doomed", assets=assets, block_length=6, draws=5, seed=1, **sample
        )


def test_paired_difference_truncates_to_the_shorter_run() -> None:
    """Unequal success counts must not reuse or recycle draws."""
    first = np.arange(12.0).reshape(6, 2)
    second = np.ones((4, 2))
    difference = paired_difference_draws(first, second)
    assert difference.shape == (4, 2)
    np.testing.assert_array_equal(difference, first[:4] - 1.0)


def test_classify_equivalence_supports_a_tight_interval_inside_the_bound() -> None:
    """A distribution well inside the bound must be classified as equivalent."""
    outcome = classify_equivalence(
        estimand="tight",
        point_change=0.01,
        change_draws=np.random.default_rng(0).normal(0.01, 0.01, 5000),
        bound=0.25,
    )
    assert outcome.passes
    assert outcome.decision_category == "equivalent_within_bound"
    assert outcome.rule == CONFIRMATORY_RULE


def test_classify_equivalence_separates_imprecision_from_a_real_difference() -> None:
    """A wide interval is inconclusive; an interval beyond the bound is not.

    This distinction is the reason the category exists: failing an equivalence
    test is not evidence of a difference.
    """
    rng = np.random.default_rng(1)
    wide = classify_equivalence(
        estimand="wide",
        point_change=0.0,
        change_draws=rng.normal(0.0, 1.0, 5000),
        bound=0.25,
    )
    assert not wide.passes
    assert wide.decision_category == "inconclusive"

    shifted = classify_equivalence(
        estimand="shifted",
        point_change=2.0,
        change_draws=rng.normal(2.0, 0.05, 5000),
        bound=0.25,
    )
    assert not shifted.passes
    assert shifted.decision_category == "difference_exceeds_bound"


def test_classify_equivalence_uses_only_the_upper_end_for_a_one_sided_bound() -> None:
    """A deterioration bound must not penalise a large improvement."""
    draws = np.random.default_rng(2).normal(-0.8, 0.02, 5000)
    two_sided = classify_equivalence(
        estimand="d", point_change=-0.8, change_draws=draws, bound=0.10
    )
    one_sided = classify_equivalence(
        estimand="d", point_change=-0.8, change_draws=draws, bound=0.10, one_sided=True
    )
    assert not two_sided.passes
    assert one_sided.passes
    assert one_sided.decision_category == "equivalent_within_bound"


def test_ninety_percent_interval_is_never_wider_than_the_ninety_five() -> None:
    """The confirmatory interval must be the narrower of the two reported."""
    outcome = classify_equivalence(
        estimand="x",
        point_change=0.0,
        change_draws=np.random.default_rng(5).normal(0.0, 0.2, 4000),
        bound=0.25,
    )
    assert outcome.lower_95 <= outcome.lower_90
    assert outcome.upper_90 <= outcome.upper_95
    assert not (outcome.passes_strict_sensitivity and not outcome.passes)
