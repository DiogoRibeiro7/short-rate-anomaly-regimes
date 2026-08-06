"""Tests for the pooled regime-interaction beta-stability workflow."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.run_regime_interactions import (
    AGGREGATE_ASSET,
    OMITTED_REGIME,
    assert_design_agrees,
    asset_columns,
    boundary_sensitivity,
    break_battery,
    build_system,
    interaction_design,
    interaction_wald_battery,
    load_regime_panel,
    rate_interaction_wide,
    registered_intervals,
    shifted_regime_labels,
)

from short_rate_anomaly_regimes.regimes.calendar import interval_from_months
from short_rate_anomaly_regimes.regimes.stability import (
    classify_stability,
    estimate_regime_interactions,
    holm_adjust_tests,
    regime_interaction_wald_tests,
)

MONTHS = 240
REGIME_A = "conventional_pre_elb"
REGIME_B = "elb_qe"


def _synthetic_system(
    *,
    rate_beta_break: float,
    market_beta_break: float = 0.0,
    seed: int = 7,
    months: int = MONTHS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Build a two-regime panel whose rate-beta break size is known by construction.

    Args:
        rate_beta_break: Change in the rate beta applied in the second regime.
        market_beta_break: Change in the market beta applied in the second regime.
        seed: Random seed for the factors and the idiosyncratic noise.
        months: Panel length in months.

    Returns:
        Returns, factors, and regime labels on a shared month-start DatetimeIndex.
    """
    generator = np.random.default_rng(seed)
    index = pd.date_range("2000-01-01", periods=months, freq="MS")
    factors = pd.DataFrame(
        {
            "RM": generator.normal(0.0, 4.0, months),
            "FFR_innovation": generator.normal(0.0, 0.3, months),
        },
        index=index,
    )
    half = months // 2
    regimes = pd.Series(
        [REGIME_A] * half + [REGIME_B] * (months - half),
        index=index,
        dtype="string",
        name="regime",
    )
    late = (regimes == REGIME_B).to_numpy(dtype=float)
    returns = pd.DataFrame(
        {
            f"asset_{position:02d}": (
                0.2
                + (0.9 + 0.1 * position) * factors["RM"]
                + market_beta_break * late * factors["RM"]
                + 0.4 * factors["FFR_innovation"]
                + rate_beta_break * late * factors["FFR_innovation"]
                + generator.normal(0.0, 1.0, months)
            )
            for position in range(3)
        },
        index=index,
    )
    return returns, factors, regimes


def _rate_rows(battery: pd.DataFrame) -> pd.DataFrame:
    """Select the rate-beta restriction rows of a Wald battery.

    Args:
        battery: Output of :func:`interaction_wald_battery`.

    Returns:
        Only the joint rate-beta interaction rows.
    """
    return battery.loc[battery["test"] == "joint_rate_beta_regime_interactions"]


def test_known_rate_beta_break_is_detected() -> None:
    """A constructed regime break in the rate beta must reject the joint restriction."""
    returns, factors, regimes = _synthetic_system(rate_beta_break=3.0)
    battery = interaction_wald_battery(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    rate = _rate_rows(battery)
    assert len(rate) == 3
    assert (rate["p_value"].astype(float) < 1e-6).all()
    adjusted = holm_adjust_tests(battery)
    assert (adjusted["holm_p_value"].astype(float) <= 0.05).all()
    conclusion = classify_stability(adjusted, alpha=0.05)
    assert conclusion.verdict == "unstable"
    assert "joint_rate_beta_regime_interactions" in conclusion.significant_tests


def test_recovered_interaction_coefficient_matches_the_constructed_break() -> None:
    """The estimated rate-beta interaction must recover the constructed break size."""
    returns, factors, regimes = _synthetic_system(rate_beta_break=3.0)
    coefficients = estimate_regime_interactions(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    wide = rate_interaction_wide(coefficients, rate_factor="FFR_innovation")
    column = f"rate_interaction_coefficient__{REGIME_B}"
    assert column in wide.columns
    assert wide[column].to_numpy(dtype=float) == pytest.approx(3.0, abs=0.6)


def test_absent_break_is_not_detected() -> None:
    """A panel with a constant rate beta must not reject the joint restriction."""
    returns, factors, regimes = _synthetic_system(rate_beta_break=0.0, seed=11)
    battery = interaction_wald_battery(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    assert (_rate_rows(battery)["p_value"].astype(float) > 0.05).all()
    adjusted = holm_adjust_tests(battery)
    assert (adjusted["holm_p_value"].astype(float) > 0.05).all()
    assert classify_stability(adjusted, alpha=0.05).verdict == "stable"


def test_market_only_break_leaves_the_rate_beta_restriction_unrejected() -> None:
    """A break confined to the market beta must not reject the rate-beta restriction."""
    returns, factors, regimes = _synthetic_system(
        rate_beta_break=0.0, market_beta_break=0.5, seed=11
    )
    battery = interaction_wald_battery(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    all_factor = battery.loc[battery["test"] == "joint_regime_factor_interactions"]
    assert (all_factor["p_value"].astype(float) < 1e-6).all()
    assert (_rate_rows(battery)["p_value"].astype(float) > 0.05).all()


def test_holm_adjustment_changes_a_borderline_outcome() -> None:
    """Holm must overturn a borderline unadjusted rejection inside the family."""
    tests = pd.DataFrame(
        {
            "asset": ["asset_00", "asset_01", "asset_02", "asset_03"],
            "test": [f"joint_rate_beta_regime_interactions_{position}" for position in range(4)],
            "p_value": [0.03, 0.20, 0.40, 0.60],
        }
    )
    assert classify_stability(tests, alpha=0.05).verdict == "unstable"
    adjusted = holm_adjust_tests(tests)
    assert adjusted["family"].eq("regime_stability").all()
    assert float(adjusted["holm_p_value"].iloc[0]) == pytest.approx(0.12)
    assert (adjusted["holm_p_value"].astype(float) >= adjusted["p_value"].astype(float)).all()
    assert classify_stability(adjusted, alpha=0.05).verdict == "stable"


def test_holm_is_never_looser_than_the_unadjusted_family() -> None:
    """Holm p-values on a real battery must dominate their unadjusted counterparts."""
    returns, factors, regimes = _synthetic_system(rate_beta_break=0.4, seed=5)
    battery = interaction_wald_battery(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    adjusted = holm_adjust_tests(battery)
    holm = adjusted["holm_p_value"].astype(float)
    raw = adjusted["p_value"].astype(float)
    assert (holm >= raw - 1e-12).all()


def test_baseline_category_is_the_single_omitted_regime() -> None:
    """The design must omit exactly one regime category and interact the rest."""
    _, factors, regimes = _synthetic_system(rate_beta_break=1.0)
    design = interaction_design(factors, regimes, reference_regime=REGIME_A)
    assert f"regime_{REGIME_A}" not in design.columns
    assert f"regime_{REGIME_B}" in design.columns
    assert f"FFR_innovation_x_regime_{REGIME_B}" in design.columns
    assert f"RM_x_regime_{REGIME_B}" in design.columns
    assert sum("_x_regime_" in str(column) for column in design.columns) == 2


def test_unknown_reference_regime_is_rejected() -> None:
    """An unregistered baseline category must raise rather than silently reorder."""
    _, factors, regimes = _synthetic_system(rate_beta_break=1.0)
    with pytest.raises(ValueError, match="Unknown reference regime"):
        interaction_design(factors, regimes, reference_regime="not_a_regime")


def test_rebuilt_design_agrees_with_the_stability_module() -> None:
    """The rebuilt design must reproduce the module's all-interaction Wald statistics."""
    returns, factors, regimes = _synthetic_system(rate_beta_break=2.0)
    battery = interaction_wald_battery(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    module_tests = regime_interaction_wald_tests(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    assert assert_design_agrees(battery, module_tests) < 1e-8


def test_design_disagreement_is_raised() -> None:
    """A divergent rebuilt statistic must fail loudly."""
    returns, factors, regimes = _synthetic_system(rate_beta_break=2.0)
    battery = interaction_wald_battery(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    module_tests = regime_interaction_wald_tests(
        returns, factors, regimes, hac_lags=3, reference_regime=REGIME_A
    )
    corrupted = module_tests.copy()
    corrupted["statistic"] = corrupted["statistic"].astype(float) + 1.0
    with pytest.raises(ValueError, match="diverges from the stability module"):
        assert_design_agrees(battery, corrupted)
    with pytest.raises(ValueError, match="disagree on the asset set"):
        assert_design_agrees(battery, module_tests.iloc[:1])


def test_boundary_shift_moves_labels_by_the_declared_months() -> None:
    """Shifting boundaries must move each internal cutoff by exactly the declared months."""
    intervals = (
        interval_from_months(REGIME_A, "2000-01", "2004-12"),
        interval_from_months(REGIME_B, "2005-01", "2009-12"),
    )
    index = pd.date_range("2000-01-01", periods=120, freq="MS")
    registered = shifted_regime_labels(index, intervals, shift_months=0)
    earlier = shifted_regime_labels(index, intervals, shift_months=-3)
    later = shifted_regime_labels(index, intervals, shift_months=3)
    assert int((registered == REGIME_A).sum()) == 60
    assert int((earlier == REGIME_A).sum()) == 57
    assert int((later == REGIME_A).sum()) == 63
    assert earlier.loc[pd.Timestamp("2004-10-01")] == REGIME_B
    assert later.loc[pd.Timestamp("2005-03-01")] == REGIME_A
    for labels in (registered, earlier, later):
        assert labels.notna().all()
        assert len(labels) == 120


def test_registered_intervals_follow_the_frozen_calendar() -> None:
    """The configured primary regimes must match the frozen registry, shifts included."""
    intervals = registered_intervals(Path("configs/regimes.yaml"), last_month="2025-12")
    assert [interval.regime_id for interval in intervals] == [
        "conventional_pre_elb",
        "elb_qe",
        "normalisation",
        "pandemic_elb_qe",
        "inflation_tightening",
        "post_tightening_easing",
    ]
    assert str(intervals[0].start) == "1972-01"
    assert str(intervals[0].end) == "2008-12"
    assert str(intervals[-1].end) == "2025-12"
    index = pd.period_range("1972-01", "2025-12", freq="M").to_timestamp(how="start")
    for shift in (-3, 0, 3):
        labels = shifted_regime_labels(pd.DatetimeIndex(index), intervals, shift_months=shift)
        assert labels.notna().all()
        assert int((labels == "conventional_pre_elb").sum()) == 444 + shift


def test_break_battery_is_labelled_exploratory() -> None:
    """Every break-battery row must be labelled exploratory hypothesis E1."""
    returns, factors, _ = _synthetic_system(rate_beta_break=1.0, months=120)
    table = break_battery(returns.mean(axis=1), factors, boundary_months=("2004-12",))
    assert set(table["evidence_class"]) == {"exploratory"}
    assert set(table["hypothesis"]) == {"E1"}
    assert set(table["multiplicity_family"]) == {"not_in_confirmatory_family"}
    assert {
        "chow_known_break",
        "quandt_andrews_unknown_break",
        "bai_perron_multiple_breaks",
        "cusum_recursive_residuals",
    } <= set(table["test"])
    chow = table.loc[table["test"] == "chow_known_break"]
    assert list(chow["break_month"]) == ["2004-12"]
    assert set(table["scope"]) == {AGGREGATE_ASSET}


def test_boundary_sensitivity_reports_every_declared_shift() -> None:
    """Boundary sensitivity must rerun the pooled tests once per declared shift."""
    returns, factors, _ = _synthetic_system(rate_beta_break=3.0)
    intervals = (
        interval_from_months(OMITTED_REGIME, "2000-01", "2009-12"),
        interval_from_months(REGIME_B, "2010-01", "2019-12"),
    )
    table = boundary_sensitivity(returns, factors, intervals, hac_lags=3, shifts=(-3, 0, 3))
    assert sorted(set(table["shift_months"])) == [-3, 0, 3]
    assert set(table["boundary_rule"]) == {
        "registered_boundaries_shifted_-3_months",
        "registered",
        "registered_boundaries_shifted_+3_months",
    }
    assert set(table["verdict"]) == {"unstable"}
    assert set(table["evidence_class"]) == {"confirmatory"}
    assert set(table["hypothesis"]) == {"H3"}
    assert len(table) == 3 * 2 * len(returns.columns)


def test_panel_loading_and_system_construction(tmp_path: Path) -> None:
    """The month strings must become a DatetimeIndex and the aggregate must be appended."""
    months = pd.period_range("2000-01", periods=24, freq="M")
    generator = np.random.default_rng(3)
    frame = pd.DataFrame(
        {
            "month": [str(month) for month in months],
            "market_excess_return": generator.normal(0.0, 4.0, 24),
            "short_rate_innovation__fedfunds": generator.normal(0.0, 0.3, 24),
            "portfolio_excess_return__book_to_market__decile_01": generator.normal(0.0, 5.0, 24),
            "portfolio_excess_return__book_to_market__decile_02": generator.normal(0.0, 5.0, 24),
            "regime_primary": [REGIME_A] * 12 + [REGIME_B] * 12,
        }
    )
    path = tmp_path / "panel.parquet"
    frame.to_parquet(path, index=False)
    panel = load_regime_panel(path)
    assert isinstance(panel.index, pd.DatetimeIndex)
    assert panel.index[0] == pd.Timestamp("2000-01-01")
    assert "month" not in panel.columns
    assert asset_columns(panel) == [
        "portfolio_excess_return__book_to_market__decile_01",
        "portfolio_excess_return__book_to_market__decile_02",
    ]
    returns, factors = build_system(panel)
    assert list(factors.columns) == ["RM", "FFR_innovation"]
    assert AGGREGATE_ASSET in returns.columns
    expected = panel[asset_columns(panel)].mean(axis=1).to_numpy(dtype=float)
    assert returns[AGGREGATE_ASSET].to_numpy(dtype=float) == pytest.approx(expected)

    gapped = frame.drop(index=[5]).reset_index(drop=True)
    gapped_path = tmp_path / "gapped.parquet"
    gapped.to_parquet(gapped_path, index=False)
    with pytest.raises(ValueError, match="month gaps"):
        load_regime_panel(gapped_path)
