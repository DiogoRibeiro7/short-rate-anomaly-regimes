"""Tests for the H4a and H4b weak-factor decision gates.

Every gate is exercised on synthetic data whose properties are known by
construction, on both its pass path and its fail path. A short-rate factor built
as a linear combination of the comparator factors must fail the spanning gate; an
independently drawn one must pass it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import pandas as pd
import pytest
from scripts.run_weak_factor_diagnostics import (
    GATE_DISPERSION,
    GATE_RANK,
    GATE_SPANNING,
    HIGH_DECILE,
    LOW_DECILE,
    MARKET_FACTOR,
    MATERIAL_FITTED_PREMIUM_SPREAD,
    MAX_ABS_STANDARDIZED_DFBETA,
    RATE_FACTOR,
    compare_family_spreads,
    dfbeta_gate_passes,
    estimate_system,
    evaluate_h4a,
    family_fitted_premium_spreads,
    leave_one_family_gate_passes,
    leave_one_family_records,
    prepare_spanning_regressors,
    rank_numerical_tolerance,
    short_asset_label,
    split_asset_label,
    standardized_dfbeta_influence,
)

from short_rate_anomaly_regimes.models.diagnostics import rate_spanning_criterion

MONTHS = 180
HAC_LAGS = 4


def _month_index(months: int = MONTHS) -> pd.PeriodIndex:
    return pd.period_range("1990-01", periods=months, freq="M")


def _comparator_panel(months: int = MONTHS, seed: int = 11) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "Mkt-RF": rng.normal(0.0, 4.0, months),
            "SMB": rng.normal(0.0, 3.0, months),
            "HML": rng.normal(0.0, 3.0, months),
        },
        index=_month_index(months),
    )


def _factor_panel(months: int = MONTHS, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            MARKET_FACTOR: rng.normal(0.0, 4.0, months),
            RATE_FACTOR: rng.normal(0.0, 1.0, months),
        },
        index=_month_index(months),
    )


def _betas(*, rate_loadings: npt.NDArray[np.floating[Any]], seed: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_assets = len(rate_loadings)
    return pd.DataFrame(
        {
            MARKET_FACTOR: 1.0 + rng.normal(0.0, 0.3, n_assets),
            RATE_FACTOR: rate_loadings,
        },
        index=[f"asset_{position:02d}" for position in range(n_assets)],
    )


def _spanned_innovation(comparators: pd.DataFrame, *, noise: float, seed: int = 17) -> pd.Series:
    rng = np.random.default_rng(seed)
    combination = 0.4 * comparators["Mkt-RF"] + 0.6 * comparators["SMB"]
    return pd.Series(
        combination.to_numpy(dtype=float) + rng.normal(0.0, noise, len(comparators)),
        index=comparators.index,
        name=RATE_FACTOR,
    )


def _synthetic_returns(
    *,
    alignment: dict[str, float],
    months: int = MONTHS,
    seed: int = 7,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a panel whose betas and mean returns are known by construction."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("1990-01-01", periods=months, freq="MS")
    market = rng.normal(0.0, 4.0, months)
    rate = rng.normal(0.0, 1.0, months)
    market = market - market.mean()
    rate = rate - rate.mean()
    factors = pd.DataFrame({MARKET_FACTOR: market, RATE_FACTOR: rate}, index=index)
    columns: dict[str, npt.NDArray[np.floating[Any]]] = {}
    for family, weight in alignment.items():
        for position in range(10):
            rate_beta = 1.0 + 0.2 * position
            market_beta = 0.9 + 0.02 * position
            label = f"{family}__decile_{position + 1:02d}"
            columns[label] = (
                weight * rate_beta
                + market_beta * market
                + rate_beta * rate
                + rng.normal(0.0, 0.05, months)
            )
    return pd.DataFrame(columns, index=index), factors


def _influence_inputs(
    *,
    perturbation: float,
    residual_variance: float,
) -> dict[str, object]:
    rate_loadings = np.array([-1.0, -0.6, -0.2, 0.2, 0.6, 1.0])
    assets = [f"family__decile_{position + 1:02d}" for position in range(len(rate_loadings))]
    betas = pd.DataFrame(
        {MARKET_FACTOR: np.ones(len(rate_loadings)), RATE_FACTOR: rate_loadings},
        index=assets,
    )
    mean_returns = pd.Series(
        0.5 * betas[MARKET_FACTOR].to_numpy() + 0.1 * betas[RATE_FACTOR].to_numpy(),
        index=assets,
        name="mean_excess_return",
    )
    mean_returns.iloc[0] = mean_returns.iloc[0] + perturbation
    residual_covariance = pd.DataFrame(
        residual_variance * np.eye(len(assets)), index=assets, columns=assets
    )
    factor_covariance = pd.DataFrame(
        np.diag([20.0, 5.0]),
        index=[MARKET_FACTOR, RATE_FACTOR],
        columns=[MARKET_FACTOR, RATE_FACTOR],
    )
    return {
        "mean_excess_returns": mean_returns,
        "betas": betas,
        "residual_covariance": residual_covariance,
        "factor_covariance": factor_covariance,
        "n_months": 504,
        "portfolio_set": "synthetic",
        "model": "synthetic_model",
    }


def test_short_asset_label_strips_the_panel_prefix() -> None:
    assert short_asset_label("portfolio_excess_return__book_to_market__decile_01") == (
        "book_to_market__decile_01"
    )


def test_split_asset_label_returns_family_and_decile() -> None:
    assert split_asset_label("book_to_market__decile_10") == ("book_to_market", "decile_10")


def test_split_asset_label_rejects_a_label_without_both_parts() -> None:
    with pytest.raises(ValueError, match="family__decile"):
        split_asset_label("book_to_market")


def test_prepare_spanning_regressors_maps_the_market_column_name() -> None:
    comparators = pd.DataFrame({MARKET_FACTOR: [1.0, 2.0], "SMB": [0.5, 0.5]})
    renamed = prepare_spanning_regressors(comparators)
    assert list(renamed.columns) == ["Mkt-RF", "SMB"]
    assert renamed["Mkt-RF"].tolist() == [1.0, 2.0]


def test_spanning_gate_fails_for_a_factor_built_from_the_comparators() -> None:
    comparators = _comparator_panel()
    spanning = rate_spanning_criterion(
        rate_innovation=_spanned_innovation(comparators, noise=0.01),
        comparator_factors=comparators,
    )
    assert spanning.r2_span > 0.90
    assert spanning.passes is False
    assert spanning.passes_residual_ratio_form is False


def test_spanning_gate_passes_for_an_independently_drawn_factor() -> None:
    comparators = _comparator_panel()
    innovation = pd.Series(
        np.random.default_rng(23).normal(0.0, 1.0, len(comparators)),
        index=comparators.index,
        name=RATE_FACTOR,
    )
    spanning = rate_spanning_criterion(rate_innovation=innovation, comparator_factors=comparators)
    assert spanning.r2_span <= 0.90
    assert spanning.passes is True
    assert spanning.executed_regressors == ("Mkt-RF", "SMB", "HML")


def test_h4a_passes_when_every_gate_passes() -> None:
    comparators = _comparator_panel()
    innovation = pd.Series(
        np.random.default_rng(29).normal(0.0, 1.0, len(comparators)),
        index=comparators.index,
        name=RATE_FACTOR,
    )
    spanning = rate_spanning_criterion(rate_innovation=innovation, comparator_factors=comparators)
    betas = _betas(rate_loadings=np.linspace(-2.0, 2.0, 12))
    report, conclusion = evaluate_h4a(betas=betas, factors=_factor_panel(), spanning=spanning)
    assert report.rank == 2
    assert conclusion.gate_failures == ()
    assert conclusion.passes is True
    assert conclusion.standardized_dispersion_share >= 0.10


def test_h4a_rank_gate_fails_for_a_collinear_beta_matrix() -> None:
    comparators = _comparator_panel()
    innovation = pd.Series(
        np.random.default_rng(31).normal(0.0, 1.0, len(comparators)),
        index=comparators.index,
        name=RATE_FACTOR,
    )
    spanning = rate_spanning_criterion(rate_innovation=innovation, comparator_factors=comparators)
    betas = _betas(rate_loadings=np.linspace(-2.0, 2.0, 12))
    betas[RATE_FACTOR] = 2.0 * betas[MARKET_FACTOR]
    report, conclusion = evaluate_h4a(betas=betas, factors=_factor_panel(), spanning=spanning)
    assert report.rank == 1
    assert GATE_RANK in conclusion.gate_failures
    assert conclusion.passes is False


def test_h4a_dispersion_gate_fails_for_a_flat_rate_exposure() -> None:
    comparators = _comparator_panel()
    innovation = pd.Series(
        np.random.default_rng(37).normal(0.0, 1.0, len(comparators)),
        index=comparators.index,
        name=RATE_FACTOR,
    )
    spanning = rate_spanning_criterion(rate_innovation=innovation, comparator_factors=comparators)
    betas = _betas(rate_loadings=np.linspace(0.0, 1e-3, 12))
    report, conclusion = evaluate_h4a(betas=betas, factors=_factor_panel(), spanning=spanning)
    assert report.rank == 2
    assert conclusion.standardized_dispersion_share < 0.10
    assert GATE_DISPERSION in conclusion.gate_failures
    assert conclusion.passes is False


def test_h4a_fails_when_only_the_spanning_gate_fails() -> None:
    comparators = _comparator_panel()
    spanning = rate_spanning_criterion(
        rate_innovation=_spanned_innovation(comparators, noise=0.01),
        comparator_factors=comparators,
    )
    betas = _betas(rate_loadings=np.linspace(-2.0, 2.0, 12))
    _report, conclusion = evaluate_h4a(betas=betas, factors=_factor_panel(), spanning=spanning)
    assert conclusion.rank_gate_passes is True
    assert conclusion.standardized_dispersion_passes is True
    assert conclusion.gate_failures == (GATE_SPANNING,)
    assert conclusion.passes is False


def test_rank_numerical_tolerance_matches_the_declared_rule() -> None:
    comparators = _comparator_panel()
    innovation = pd.Series(
        np.random.default_rng(41).normal(0.0, 1.0, len(comparators)),
        index=comparators.index,
        name=RATE_FACTOR,
    )
    spanning = rate_spanning_criterion(rate_innovation=innovation, comparator_factors=comparators)
    betas = _betas(rate_loadings=np.linspace(-2.0, 2.0, 12))
    report, _conclusion = evaluate_h4a(betas=betas, factors=_factor_panel(), spanning=spanning)
    expected = 12 * np.finfo(float).eps * max(report.singular_values)
    assert rank_numerical_tolerance(report) == pytest.approx(expected)


def test_family_fitted_premium_spreads_use_the_extreme_deciles() -> None:
    rate_betas = pd.Series(
        {
            f"alpha_family__{LOW_DECILE}": 1.0,
            "alpha_family__decile_05": 5.0,
            f"alpha_family__{HIGH_DECILE}": 3.0,
        }
    )
    spreads = family_fitted_premium_spreads(rate_betas=rate_betas, lambda_rate=-0.5)
    assert spreads.to_dict() == pytest.approx({"alpha_family": -1.0})


def test_family_fitted_premium_spreads_reject_a_missing_extreme_decile() -> None:
    rate_betas = pd.Series({f"alpha_family__{LOW_DECILE}": 1.0})
    with pytest.raises(ValueError, match="missing extreme deciles"):
        family_fitted_premium_spreads(rate_betas=rate_betas, lambda_rate=1.0)


def test_family_fitted_premium_spreads_reject_empty_loadings() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        family_fitted_premium_spreads(rate_betas=pd.Series(dtype=float), lambda_rate=1.0)


def test_compare_family_spreads_passes_when_sign_and_materiality_hold() -> None:
    comparison = compare_family_spreads(
        baseline=pd.Series({"alpha_family": 0.80}),
        refit=pd.Series({"alpha_family": 0.60}),
    )
    row = comparison.iloc[0]
    assert bool(row["sign_reversal"]) is False
    assert bool(row["materiality_lost"]) is False
    assert bool(row["passes"]) is True
    assert float(row["spread_change"]) == pytest.approx(-0.20)


def test_compare_family_spreads_flags_a_sign_reversal() -> None:
    comparison = compare_family_spreads(
        baseline=pd.Series({"alpha_family": 0.80}),
        refit=pd.Series({"alpha_family": -0.80}),
    )
    row = comparison.iloc[0]
    assert bool(row["sign_reversal"]) is True
    assert bool(row["passes"]) is False


def test_compare_family_spreads_flags_a_lost_materiality_classification() -> None:
    comparison = compare_family_spreads(
        baseline=pd.Series({"alpha_family": MATERIAL_FITTED_PREMIUM_SPREAD}),
        refit=pd.Series({"alpha_family": MATERIAL_FITTED_PREMIUM_SPREAD / 2.0}),
    )
    row = comparison.iloc[0]
    assert bool(row["baseline_material"]) is True
    assert bool(row["refit_material"]) is False
    assert bool(row["materiality_lost"]) is True
    assert bool(row["passes"]) is False


def test_compare_family_spreads_rejects_an_unknown_refit_family() -> None:
    with pytest.raises(ValueError, match="absent from the baseline"):
        compare_family_spreads(
            baseline=pd.Series({"alpha_family": 1.0}),
            refit=pd.Series({"zeta_family": 1.0}),
        )


def _leave_one_family(alignment: dict[str, float]) -> pd.DataFrame:
    excess_returns, factors = _synthetic_returns(alignment=alignment)
    baseline = estimate_system(
        excess_returns=excess_returns,
        factors=factors,
        hac_lags=HAC_LAGS,
        portfolio_set="synthetic_joint",
        model="synthetic_model",
    )
    return leave_one_family_records(
        baseline=baseline,
        excess_returns=excess_returns,
        factors=factors,
        hac_lags=HAC_LAGS,
    )


def test_leave_one_family_gate_passes_when_every_family_is_aligned() -> None:
    records = _leave_one_family({"alpha_family": 1.0, "zeta_family": 0.6})
    assert set(records["omitted_family"]) == {"alpha_family", "zeta_family"}
    assert (records["n_assets"] == 10).all()
    assert not records["family_sign_reversal"].any()
    assert records["family_material_baseline"].all()
    assert records["family_material_refit"].all()
    assert leave_one_family_gate_passes(records) is True


def test_leave_one_family_gate_fails_when_a_refit_reverses_the_spread_sign() -> None:
    records = _leave_one_family({"alpha_family": 1.0, "zeta_family": -0.2})
    reversed_rows = records[records["family_sign_reversal"]]
    assert not reversed_rows.empty
    assert set(reversed_rows["omitted_family"]) == {"alpha_family"}
    assert leave_one_family_gate_passes(records) is False


def test_leave_one_family_fitted_premium_matches_beta_times_lambda() -> None:
    records = _leave_one_family({"alpha_family": 1.0, "zeta_family": 0.6})
    expected = records["beta_rate"] * records["lambda_rate"]
    assert records["pi_rate"].to_numpy() == pytest.approx(expected.to_numpy())
    high = records[records["decile"] == HIGH_DECILE].set_index(["omitted_family", "family"])
    low = records[records["decile"] == LOW_DECILE].set_index(["omitted_family", "family"])
    assert (high["pi_rate"] - low["pi_rate"]).to_numpy() == pytest.approx(
        high["family_spread_refit"].to_numpy()
    )


def test_leave_one_family_records_reject_a_single_family() -> None:
    excess_returns, factors = _synthetic_returns(alignment={"alpha_family": 1.0})
    baseline = estimate_system(
        excess_returns=excess_returns,
        factors=factors,
        hac_lags=HAC_LAGS,
        portfolio_set="synthetic_joint",
        model="synthetic_model",
    )
    with pytest.raises(ValueError, match="at least two anomaly families"):
        leave_one_family_records(
            baseline=baseline,
            excess_returns=excess_returns,
            factors=factors,
            hac_lags=HAC_LAGS,
        )


def test_leave_one_family_gate_rejects_an_empty_table() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        leave_one_family_gate_passes(pd.DataFrame(columns=["family_gate_passes"]))


def test_dfbeta_gate_passes_when_no_portfolio_moves_the_risk_price() -> None:
    influence = standardized_dfbeta_influence(
        **_influence_inputs(perturbation=0.0, residual_variance=1.0)  # type: ignore[arg-type]
    )
    assert influence["abs_standardized_dfbeta"].max() == pytest.approx(0.0, abs=1e-10)
    assert not influence["reaches_threshold"].any()
    assert dfbeta_gate_passes(influence) is True


def test_dfbeta_gate_fails_when_one_portfolio_dominates_the_risk_price() -> None:
    influence = standardized_dfbeta_influence(
        **_influence_inputs(perturbation=5.0, residual_variance=1e-4)  # type: ignore[arg-type]
    )
    peak = influence.loc[influence["abs_standardized_dfbeta"].idxmax()]
    assert float(peak["abs_standardized_dfbeta"]) >= MAX_ABS_STANDARDIZED_DFBETA
    assert str(peak["asset"]) == "family__decile_01"
    assert bool(peak["reaches_threshold"]) is True
    assert dfbeta_gate_passes(influence) is False


def test_dfbeta_influence_reports_the_leave_one_out_risk_price() -> None:
    influence = standardized_dfbeta_influence(
        **_influence_inputs(perturbation=1.0, residual_variance=1.0)  # type: ignore[arg-type]
    )
    assert len(influence) == 6
    change = influence["lambda_rate_full"] - influence["lambda_rate_leave_one_out"]
    assert influence["delta_lambda_rate"].to_numpy() == pytest.approx(change.to_numpy())
    standardized = influence["delta_lambda_rate"] / influence["shanken_se_lambda_rate_full"]
    assert influence["standardized_dfbeta"].to_numpy() == pytest.approx(standardized.to_numpy())


def test_dfbeta_influence_rejects_a_missing_rate_factor() -> None:
    inputs = _influence_inputs(perturbation=0.0, residual_variance=1.0)
    betas = inputs["betas"]
    assert isinstance(betas, pd.DataFrame)
    inputs["betas"] = betas.rename(columns={RATE_FACTOR: "other"})
    inputs["factor_covariance"] = pd.DataFrame(
        np.diag([20.0, 5.0]),
        index=[MARKET_FACTOR, "other"],
        columns=[MARKET_FACTOR, "other"],
    )
    with pytest.raises(ValueError, match="no 'FFR_innovation' column"):
        standardized_dfbeta_influence(**inputs)  # type: ignore[arg-type]


def test_dfbeta_influence_rejects_a_cross_section_that_is_too_small() -> None:
    inputs = _influence_inputs(perturbation=0.0, residual_variance=1.0)
    mean_returns = inputs["mean_excess_returns"]
    betas = inputs["betas"]
    residual_covariance = inputs["residual_covariance"]
    assert isinstance(mean_returns, pd.Series)
    assert isinstance(betas, pd.DataFrame)
    assert isinstance(residual_covariance, pd.DataFrame)
    retained = list(mean_returns.index[:3])
    inputs["mean_excess_returns"] = mean_returns.loc[retained]
    inputs["betas"] = betas.loc[retained]
    inputs["residual_covariance"] = residual_covariance.loc[retained, retained]
    with pytest.raises(ValueError, match="more retained assets than factors"):
        standardized_dfbeta_influence(**inputs)  # type: ignore[arg-type]


def test_dfbeta_gate_rejects_an_empty_table() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        dfbeta_gate_passes(pd.DataFrame(columns=["abs_standardized_dfbeta"]))
