"""Estimate regime-specific second passes and run the H3 equivalence tests.

Only regimes that clear the frozen eligibility floors get a standalone second
pass. Under the registered floors that is `conventional_pre_elb` and `elb_qe`;
the remaining four are reported here as ineligible rather than silently omitted,
and reach the record only through the pooled interaction model.

Equivalence uses the single confirmatory rule fixed in
``research/inference_contract.md``: two one-sided tests at the 5 percent level,
implemented as inclusion of the two-sided 90 percent joint-bootstrap percentile
interval inside the declared bound. The stricter 95 percent variant is carried
alongside under its own label and decides nothing.

The short-rate innovation is re-estimated within each regime window, because the
inference contract requires the innovation to be recomputed in every draw and
blocks to be resampled within regime. Since `pi_rate` is invariant to rescaling
the innovation, the global-innovation estimates are also computed and reported
as a labelled sensitivity, so the classification can be checked against that
choice rather than resting on it.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.config import load_regime_config
from short_rate_anomaly_regimes.models.article_second_pass import (
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.block_bootstrap import (
    FloatArray,
    recover_lagged_level,
    select_block_length,
)
from short_rate_anomaly_regimes.models.time_series import (
    automatic_newey_west_lags,
    estimate_time_series_betas,
)
from short_rate_anomaly_regimes.regimes.equivalence import (
    CONFIRMATORY_RULE,
    SENSITIVITY_RULE,
    EquivalenceOutcome,
    RegimePremiumBootstrap,
    bootstrap_regime_premia,
    classify_equivalence,
    paired_difference_draws,
)

REGIME_PARQUET = Path("data/processed/regimes/monthly_regimes.parquet")
ELIGIBILITY_CSV = Path("artifacts/tables/regimes/regime_eligibility.csv")

SECOND_PASS_CSV = Path("artifacts/tables/regimes/regime_second_pass.csv")
EQUIVALENCE_CSV = Path("artifacts/tables/regimes/h3_equivalence.csv")
PREMIA_CSV = Path("artifacts/tables/regimes/regime_fitted_premia.csv")
DIAGNOSTIC_JSON = Path("artifacts/diagnostics/h3_regime_equivalence.json")
PROVENANCE_JSON = Path("artifacts/provenance/regime_equivalence.json")

RATE = "fedfunds"
REFERENCE_REGIME = "conventional_pre_elb"

#: research/economic_thresholds.md, "Regime Equivalence".
FITTED_PREMIUM_BOUND = 0.25
DISPERSION_BOUND = 0.25
RMSE_BOUND = 0.10
MAX_ERROR_BOUND = 0.25
FIT_BOUND = 0.10

DRAWS = 10_000
BASE_SEED = 20260805

#: Which draw-level statistic backs each aggregate gate, and how it is compared.
AGGREGATE_GATES = (
    ("dispersion_relative_change", "dispersion", DISPERSION_BOUND, False, "relative"),
    ("rmse_relative_deterioration", "rmse", RMSE_BOUND, True, "relative"),
    ("max_abs_error_deterioration", "max_abs_error", MAX_ERROR_BOUND, True, "absolute"),
    ("article_fit_deterioration", "article_fit", FIT_BOUND, True, "reversed"),
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load() -> pd.DataFrame:
    frame = pd.read_parquet(REGIME_PARQUET)
    index = pd.PeriodIndex([pd.Period(str(v), freq="M") for v in frame["month"]], freq="M")
    return frame.drop(columns=["month"]).set_axis(index)


def _asset_columns(panel: pd.DataFrame) -> list[str]:
    return sorted(c for c in panel.columns if c.startswith("portfolio_excess_return__"))


def _within_regime_innovation(window: pd.DataFrame) -> tuple[FloatArray, FloatArray]:
    """Recover the true lagged level and re-estimate the AR(1) inside one regime."""
    level = window[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    lagged = recover_lagged_level(
        level, window[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float)
    )
    design = np.column_stack([np.ones(level.size), lagged])
    return lagged, level - design @ np.linalg.lstsq(design, level, rcond=None)[0]


def _second_pass_row(window: pd.DataFrame, columns: list[str], regime_id: str) -> dict[str, object]:
    """Estimate the article second pass on one regime with Shanken standard errors."""
    timestamps = pd.PeriodIndex(window.index, freq="M").to_timestamp(how="start")
    returns = window[columns].set_axis(timestamps)
    _, innovation = _within_regime_innovation(window)
    factors = pd.DataFrame(
        {"RM": window["market_excess_return"].to_numpy(dtype=float), "FFR_innovation": innovation},
        index=timestamps,
    )
    first_pass = estimate_time_series_betas(
        returns, factors, hac_lags=automatic_newey_west_lags(len(window))
    )
    result = estimate_article_second_pass(
        mean_excess_returns=returns.mean().rename("mean_return"),
        betas=first_pass.coefficients[["RM", "FFR_innovation"]],
        residual_covariance=residual_covariance_from_first_pass(first_pass.residuals),
        factor_covariance=factors.cov(),
        n_months=len(window),
        portfolio_set="all_seven_families_joint",
        model=regime_id,
    )
    return {
        "lambda_market": float(result.risk_prices["RM"]),
        "lambda_rate": float(result.risk_prices["FFR_innovation"]),
        "shanken_t_market": float(result.shanken_t_statistics["RM"]),
        "shanken_t_rate": float(result.shanken_t_statistics["FFR_innovation"]),
        "rmse": result.root_mean_squared_pricing_error,
        "mae": result.mean_absolute_pricing_error,
        "max_abs_error": result.max_absolute_pricing_error,
        "article_fit": result.article_cross_sectional_fit,
        "chi_square_statistic": result.chi_square_statistic,
        "chi_square_degrees_of_freedom": result.chi_square_degrees_of_freedom,
        "chi_square_asymptotic_p_value": result.chi_square_asymptotic_p_value,
    }


def _bootstrap(
    window: pd.DataFrame, columns: list[str], regime_id: str, seed: int
) -> tuple[RegimePremiumBootstrap, dict[str, object]]:
    """Bootstrap one regime's per-portfolio fitted premia inside its own window."""
    level = window[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
    lagged, innovation = _within_regime_innovation(window)
    selection = select_block_length(
        pd.DataFrame({"market": window["market_excess_return"].to_numpy(float), "rate": innovation})
    )
    result = bootstrap_regime_premia(
        regime_id=regime_id,
        assets=tuple(columns),
        rate_level=level,
        lagged_rate_level=lagged,
        market=window["market_excess_return"].to_numpy(dtype=float),
        excess_returns=window[columns].to_numpy(dtype=float),
        block_length=selection.block_length,
        draws=DRAWS,
        seed=seed,
        block_length_selected_by=selection.selected_by,
    )
    return result, {
        "block_length": selection.block_length,
        "block_length_selected_by": selection.selected_by,
        "block_length_failure_reasons": "; ".join(selection.failure_reasons),
        "successful_draws": result.successful_draws,
    }


def _global_innovation_sensitivity(
    window: pd.DataFrame, columns: list[str]
) -> tuple[FloatArray, float]:
    """Evaluate the same regime holding the whole-history innovation fixed."""
    innovation = window[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float)
    market = window["market_excess_return"].to_numpy(dtype=float)
    returns = window[columns].to_numpy(dtype=float)
    factors = np.column_stack([np.ones(len(window)), market, innovation])
    betas = np.linalg.lstsq(factors, returns, rcond=None)[0][1:, :].T
    mean_returns = returns.mean(axis=0)
    risk_prices = np.linalg.lstsq(betas, mean_returns, rcond=None)[0]
    return betas[:, 1] * risk_prices[1], float(risk_prices[1])


def _residual_conditioning(window: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    """Measure how well the residual covariance is determined in one regime.

    The chi-square specification test and the Shanken correction both need an
    inverse of the residual covariance. With ``T`` months and ``N`` test assets
    that matrix is estimated from ``T`` observations, so a small ``T - N`` makes
    the inverse unstable however well conditioned the point estimates are. This
    is reported so the specification test is not read as evidence when it rests
    on a nearly indeterminate matrix.
    """
    _, innovation = _within_regime_innovation(window)
    returns = window[columns].to_numpy(dtype=float)
    design = np.column_stack(
        [np.ones(len(window)), window["market_excess_return"].to_numpy(dtype=float), innovation]
    )
    residuals = returns - design @ np.linalg.lstsq(design, returns, rcond=None)[0]
    eigenvalues = np.linalg.eigvalsh(np.cov(residuals, rowvar=False))
    return {
        "months": len(window),
        "test_assets": len(columns),
        "excess_months_over_assets": len(window) - len(columns),
        "residual_covariance_condition_number": float(
            eigenvalues.max() / max(float(eigenvalues.min()), 1e-300)
        ),
        "smallest_eigenvalue": float(eigenvalues.min()),
    }


def _aggregate_outcome(
    name: str,
    key: str,
    bound: float,
    one_sided: bool,
    kind: str,
    current: RegimePremiumBootstrap,
    reference: RegimePremiumBootstrap,
) -> EquivalenceOutcome:
    """Compare one draw-level statistic between a regime and the reference."""
    here = current.statistic_draws[key]
    there = reference.statistic_draws[key]
    usable = min(here.size, there.size)
    if kind == "reversed":
        # A deterioration in fit is a fall, so the reference leads the difference.
        draws = there[:usable] - here[:usable]
        point = reference.point_statistics[key] - current.point_statistics[key]
    elif kind == "relative":
        draws = here[:usable] / there[:usable] - 1.0
        point = current.point_statistics[key] / reference.point_statistics[key] - 1.0
    else:
        draws = here[:usable] - there[:usable]
        point = current.point_statistics[key] - reference.point_statistics[key]
    return classify_equivalence(
        estimand=name,
        point_change=float(point),
        change_draws=draws,
        bound=bound,
        one_sided=one_sided,
    )


def main() -> None:
    """Estimate every eligible regime, run the H3 equivalence tests, and classify."""
    panel = _load()
    columns = _asset_columns(panel)
    eligibility = pd.read_csv(ELIGIBILITY_CSV)
    regime_config = load_regime_config(Path("configs/regimes.yaml"))
    if regime_config.equivalence_rule != CONFIRMATORY_RULE:
        raise ValueError("The frozen equivalence rule does not match the implemented rule")
    permitted = eligibility["standalone_second_pass_permitted"]
    eligible = eligibility.loc[permitted, "regime_id"].tolist()
    if REFERENCE_REGIME not in eligible:
        raise ValueError("The reference regime must itself be eligible")

    rows: list[dict[str, object]] = []
    bootstraps: dict[str, RegimePremiumBootstrap] = {}
    sensitivities: dict[str, tuple[FloatArray, float]] = {}
    for offset, regime_id in enumerate(eligibility["regime_id"]):
        window = panel[panel["regime_primary"] == regime_id]
        tier = eligibility.loc[eligibility["regime_id"] == regime_id, "eligibility_tier"].iloc[0]
        if regime_id not in eligible:
            rows.append(
                {
                    "regime_id": regime_id,
                    "months": len(window),
                    "standalone_second_pass": False,
                    "status": "ineligible_pooled_interaction_only",
                    "eligibility_tier": tier,
                }
            )
            continue
        bootstrap, diagnostics = _bootstrap(window, columns, regime_id, BASE_SEED + offset)
        bootstraps[regime_id] = bootstrap
        sensitivities[regime_id] = _global_innovation_sensitivity(window, columns)
        rows.append(
            {
                "regime_id": regime_id,
                "months": len(window),
                "standalone_second_pass": True,
                "status": "estimated",
                "eligibility_tier": tier,
                **_second_pass_row(window, columns, regime_id),
                **diagnostics,
                "dispersion_of_fitted_premia": bootstrap.point_statistics["dispersion"],
                "lambda_rate_global_innovation_sensitivity": sensitivities[regime_id][1],
            }
        )
    second_pass = pd.DataFrame.from_records(rows)
    second_pass["replication_status"] = "documented_reconstruction"

    reference = bootstraps[REFERENCE_REGIME]
    comparisons = [r for r in eligible if r != REFERENCE_REGIME]

    premia_rows: list[dict[str, object]] = []
    outcomes: list[tuple[str, EquivalenceOutcome]] = []
    for regime_id in comparisons:
        current = bootstraps[regime_id]
        premium_differences = paired_difference_draws(
            current.premium_draws, reference.premium_draws
        )
        point_differences = current.point_premia - reference.point_premia
        sensitivity_differences = sensitivities[regime_id][0] - sensitivities[REFERENCE_REGIME][0]
        for position, asset in enumerate(columns):
            outcomes.append(
                (
                    regime_id,
                    classify_equivalence(
                        estimand=f"fitted_premium_change__{asset}",
                        point_change=float(point_differences[position]),
                        change_draws=premium_differences[:, position],
                        bound=FITTED_PREMIUM_BOUND,
                    ),
                )
            )
            premia_rows.append(
                {
                    "regime_id": regime_id,
                    "asset": asset,
                    "reference_premium": float(reference.point_premia[position]),
                    "regime_premium": float(current.point_premia[position]),
                    "change": float(point_differences[position]),
                    "change_global_innovation_sensitivity": float(
                        sensitivity_differences[position]
                    ),
                }
            )
        for name, key, bound, one_sided, kind in AGGREGATE_GATES:
            outcome = _aggregate_outcome(name, key, bound, one_sided, kind, current, reference)
            outcomes.append((regime_id, outcome))

    equivalence = pd.DataFrame.from_records(
        [
            {
                "regime_id": regime_id,
                "reference_regime": REFERENCE_REGIME,
                "estimand": outcome.estimand,
                "point_change": outcome.point_change,
                "lower_90": outcome.lower_90,
                "upper_90": outcome.upper_90,
                "bound": outcome.bound,
                "one_sided_bound": outcome.one_sided,
                "tost_5pct_90pct_interval_passes": outcome.passes,
                "decision_category": outcome.decision_category,
                "strict_95pct_interval_sensitivity_passes": outcome.passes_strict_sensitivity,
                "rule": CONFIRMATORY_RULE,
                "sensitivity_rule": SENSITIVITY_RULE,
            }
            for regime_id, outcome in outcomes
        ]
    )
    premia = pd.DataFrame.from_records(premia_rows)

    is_premium = equivalence["estimand"].str.startswith("fitted_premium_change__")
    premium_gate = equivalence[is_premium]
    aggregate_gate = equivalence[~is_premium]
    gates = {
        "per_portfolio_fitted_premium_equivalence": bool(
            premium_gate["tost_5pct_90pct_interval_passes"].all()
        ),
        **{
            str(name): bool(
                aggregate_gate.loc[
                    aggregate_gate["estimand"] == name, "tost_5pct_90pct_interval_passes"
                ].all()
            )
            for name, _, _, _, _ in AGGREGATE_GATES
        },
    }
    # The registry admits three outcomes, and they are not interchangeable.
    # `unsupported` is registered to mean the relation *is* regime dependent, so
    # it requires at least one dimension whose whole interval lies beyond its
    # bound. Gates that merely fail to certify equivalence leave the question
    # open, which is what the registered `inconclusive` reading describes.
    demonstrated = equivalence["decision_category"] == "difference_exceeds_bound"
    exceeded = sorted(
        {
            "per_portfolio_fitted_premium_equivalence"
            if estimand.startswith("fitted_premium_change__")
            else estimand
            for estimand in equivalence.loc[demonstrated, "estimand"]
        }
    )
    if all(gates.values()):
        classification = "regime_stability_supported"
    elif exceeded:
        classification = "regime_stability_unsupported_under_the_registered_equivalence_standard"
    else:
        classification = "regime_stability_inconclusive_under_the_registered_equivalence_standard"

    for path in (SECOND_PASS_CSV, DIAGNOSTIC_JSON, PROVENANCE_JSON):
        path.parent.mkdir(parents=True, exist_ok=True)
    second_pass.to_csv(SECOND_PASS_CSV, index=False)
    equivalence.to_csv(EQUIVALENCE_CSV, index=False)
    premia.to_csv(PREMIA_CSV, index=False)

    failing = premium_gate.loc[~premium_gate["tost_5pct_90pct_interval_passes"], "estimand"]
    categories = premium_gate["decision_category"].value_counts().to_dict()
    # The sensitivity is reported as agreement in substance rather than as an
    # equality of counts, which a single portfolio crossing the bound would
    # falsify while nothing material had changed.
    sensitivity = {
        "correlation": float(
            np.corrcoef(premia["change"], premia["change_global_innovation_sensitivity"])[0, 1]
        ),
        "sign_agreement": int(
            (
                np.sign(premia["change"]) == np.sign(premia["change_global_innovation_sensitivity"])
            ).sum()
        ),
        "max_absolute_discrepancy": float(
            (premia["change"] - premia["change_global_innovation_sensitivity"]).abs().max()
        ),
        "portfolios_beyond_bound_within_regime_innovation": int(
            (premia["change"].abs() > FITTED_PREMIUM_BOUND).sum()
        ),
        "portfolios_beyond_bound_global_innovation": int(
            (premia["change_global_innovation_sensitivity"].abs() > FITTED_PREMIUM_BOUND).sum()
        ),
    }
    conditioning = {
        regime_id: _residual_conditioning(panel[panel["regime_primary"] == regime_id], columns)
        for regime_id in eligible
    }
    DIAGNOSTIC_JSON.write_text(
        json.dumps(
            {
                "hypothesis": "H3",
                "classification": classification,
                "equivalence_rule": CONFIRMATORY_RULE,
                "reference_regime": REFERENCE_REGIME,
                "regimes_with_standalone_second_pass": eligible,
                "regimes_limited_to_pooled_interactions": [
                    r for r in eligibility["regime_id"] if r not in eligible
                ],
                "gates": gates,
                "dimensions_with_a_demonstrated_exceedance": exceeded,
                "classification_basis": (
                    "at least one dimension has its whole 90 percent interval beyond its "
                    "bound, which is what the registered unsupported reading asserts"
                    if exceeded
                    else "no dimension demonstrates an exceedance; failures are imprecision"
                ),
                "portfolios_failing_the_premium_bound": len(failing),
                "portfolios_evaluated": len(columns),
                "per_portfolio_decision_categories": categories,
                "max_absolute_point_premium_change": float(premia["change"].abs().max()),
                "innovation_definition": "within_regime_ar1",
                "global_innovation_sensitivity": sensitivity,
                "residual_covariance_conditioning": conditioning,
                "specification_test_caveat": (
                    "the chi-square statistic and the Shanken correction invert a residual "
                    "covariance estimated from T months for N test assets; where T - N is "
                    "small that inverse is unstable and the statistic should not be read as "
                    "evidence. The equivalence gates do not invert it"
                ),
                "draws": DRAWS,
                "coverage_note": (
                    "the registered floors admit only two regimes to a standalone second "
                    "pass, so the confirmatory comparison spans a single contrast; the other "
                    "four regimes enter only through the pooled interaction model"
                ),
                "replication_status": "documented_reconstruction",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_regime_equivalence.py",
                "inputs": {p.as_posix(): _sha256(p) for p in (REGIME_PARQUET, ELIGIBILITY_CSV)},
                "outputs": {
                    p.as_posix(): _sha256(p)
                    for p in (SECOND_PASS_CSV, EQUIVALENCE_CSV, PREMIA_CSV, DIAGNOSTIC_JSON)
                },
                "draws": DRAWS,
                "base_seed": BASE_SEED,
                "seeds_by_regime": {k: v.seed for k, v in bootstraps.items()},
                "successful_draws_by_regime": {
                    k: v.successful_draws for k, v in bootstraps.items()
                },
                "block_lengths_by_regime": {k: v.block_length for k, v in bootstraps.items()},
                "bounds": {
                    "fitted_premium": FITTED_PREMIUM_BOUND,
                    "dispersion": DISPERSION_BOUND,
                    "rmse": RMSE_BOUND,
                    "max_error": MAX_ERROR_BOUND,
                    "fit": FIT_BOUND,
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    display = [
        "regime_id",
        "months",
        "lambda_rate",
        "shanken_t_rate",
        "rmse",
        "article_fit",
        "dispersion_of_fitted_premia",
        "block_length",
    ]
    print(second_pass[[c for c in display if c in second_pass]].round(4).to_string(index=False))
    print()
    print(
        aggregate_gate[
            [
                "regime_id",
                "estimand",
                "point_change",
                "lower_90",
                "upper_90",
                "bound",
                "tost_5pct_90pct_interval_passes",
            ]
        ]
        .round(4)
        .to_string(index=False)
    )
    print(
        f"\nper-portfolio premium bound: {len(failing)} of {len(columns)} portfolios fail"
        f"  (max |change| = {premia['change'].abs().max():.4f})"
    )
    print(f"decision categories: {categories}")
    for regime_id, values in conditioning.items():
        print(
            f"conditioning {regime_id}: T-N = {values['excess_months_over_assets']:.0f}, "
            f"condition number = {values['residual_covariance_condition_number']:.3e}"
        )
    print(f"H3: {classification}")


if __name__ == "__main__":
    main()
