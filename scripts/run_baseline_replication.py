"""Run the baseline first-pass and second-pass replication over every model and asset set.

This produces the generated cells that the published-target audit compares
against. Every output carries the documented-reconstruction label, because no
input in this design is an exact article input.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    article_constrained_fit,
    estimate_article_second_pass,
    residual_covariance_from_first_pass,
)
from short_rate_anomaly_regimes.models.time_series import (
    automatic_newey_west_lags,
    estimate_time_series_betas,
)
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")

FIRST_PASS_PARQUET = Path("artifacts/estimates/time_series/baseline_first_pass_betas.parquet")
SECOND_PASS_PARQUET = Path("artifacts/estimates/cross_section/baseline_second_pass.parquet")
PRICING_ERRORS_PARQUET = Path("artifacts/estimates/cross_section/baseline_pricing_errors.parquet")
RISK_PRICE_CSV = Path("artifacts/tables/cross_section/baseline_risk_prices.csv")
PROVENANCE_JSON = Path("artifacts/provenance/baseline_replication_run.json")

REPLICATION_STATUS = "documented_reconstruction"

#: Factor columns per model, using the article's factor names. The short-rate
#: innovations come from the canonical panel; every other factor comes from the
#: comparator panel. HXZ4 uses the same market factor as the other models,
#: matching the article's single RM row in Table 1.
#: The article restricts the constrained fit of equations (7) and (8) to models
#: whose factors are all traded excess returns, and states at page 934 that it
#: does not apply to the ICAPM because the hedging factors are not returns.
TRADED_FACTOR_MODELS = frozenset(
    {"capm", "fama_french_3", "carhart_4", "fama_french_5", "q_factor", "liquidity"}
)

MODELS: dict[str, tuple[str, ...]] = {
    "capm": ("RM",),
    "market_plus_fedfunds_innovation": ("RM", "FFR_innovation"),
    "market_plus_tbill_innovation": ("RM", "TB_innovation"),
    "fama_french_3": ("RM", "SMB", "HML"),
    "carhart_4": ("RM", "SMB", "HML", "UMD"),
    "fama_french_5": ("RM", "SMB", "HML", "RMW", "CMA"),
    "q_factor": ("RM", "ME", "IA", "ROE"),
    # PS4 in article Table 6: the Fama-French three factors plus traded liquidity.
    "liquidity": ("RM", "SMB", "HML", "LIQ"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex([pd.Period(str(value), freq="M") for value in panel["month"]], freq="M")
    panel = panel.drop(columns=["month"]).set_axis(index)

    comparators = pd.read_parquet(COMPARATOR_PARQUET)
    comparator_index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in comparators["month"]], freq="M"
    )
    comparators = comparators.drop(columns=["month"]).set_axis(comparator_index)

    factors = comparators.copy()
    factors["FFR_innovation"] = panel["short_rate_innovation__fedfunds"]
    factors["TB_innovation"] = panel["short_rate_innovation__tb3ms"]

    asset_sets: dict[str, list[str]] = {}
    for family in FAMILY_MEMBERS:
        columns = sorted(
            column
            for column in panel.columns
            if column.startswith(f"portfolio_excess_return__{family}__")
        )
        asset_sets[family] = columns
    asset_sets["all_seven_families_joint"] = sorted(
        column for column in panel.columns if column.startswith("portfolio_excess_return__")
    )
    return panel, factors, asset_sets


def _short_label(column: str) -> str:
    """Shorten a panel column to ``family__decile`` for readable outputs."""
    return column.removeprefix("portfolio_excess_return__")


def main() -> None:
    """Estimate every model on every registered asset set and write the artifacts."""
    panel, factors, asset_sets = _load_inputs()
    months = len(panel)
    hac_lags = automatic_newey_west_lags(months)

    beta_rows: list[dict[str, object]] = []
    error_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []

    # The estimators in models.time_series align on a DatetimeIndex, so the
    # month periods are converted once at the boundary. Month-start stamps keep
    # the mapping one-to-one and order-preserving.
    timestamps = pd.PeriodIndex(panel.index, freq="M").to_timestamp(how="start")

    for model, factor_names in MODELS.items():
        model_factors = factors[list(factor_names)].set_axis(timestamps)
        for asset_set, columns in asset_sets.items():
            excess_returns = panel[columns].rename(columns={c: _short_label(c) for c in columns})
            excess_returns = excess_returns.set_axis(timestamps)
            first_pass = estimate_time_series_betas(
                excess_returns, model_factors, hac_lags=hac_lags
            )
            # coefficients is indexed by asset with one column per parameter.
            betas = first_pass.coefficients[list(factor_names)]
            mean_returns = excess_returns.mean().rename("mean_return")

            result = estimate_article_second_pass(
                mean_excess_returns=mean_returns,
                betas=betas,
                residual_covariance=residual_covariance_from_first_pass(first_pass.residuals),
                factor_covariance=model_factors.cov(),
                n_months=months,
                portfolio_set=asset_set,
                model=model,
            )

            for asset in betas.index:
                row: dict[str, object] = {
                    "model": model,
                    "portfolio_set": asset_set,
                    "asset": asset,
                    "mean_excess_return": float(mean_returns[asset]),
                    "first_pass_alpha": float(first_pass.coefficients.loc[asset, "const"]),
                    "first_pass_r_squared": float(first_pass.r_squared[asset]),
                }
                for factor in factor_names:
                    row[f"beta_{factor}"] = float(betas.loc[asset, factor])
                beta_rows.append(row)
                error_rows.append(
                    {
                        "model": model,
                        "portfolio_set": asset_set,
                        "asset": asset,
                        "pricing_error": float(result.pricing_errors[asset]),
                        "fitted_mean_return": float(result.fitted_mean_returns[asset]),
                        "mean_excess_return": float(mean_returns[asset]),
                    }
                )

            summary = {
                key: value
                for key, value in asdict(result).items()
                if not isinstance(value, pd.Series | dict)
            }
            for factor in factor_names:
                summary[f"lambda_{factor}"] = float(result.risk_prices[factor])
                summary[f"shanken_t_{factor}"] = float(result.shanken_t_statistics[factor])
                summary[f"shanken_se_{factor}"] = float(result.shanken_standard_errors[factor])
            summary["article_constrained_fit"] = (
                article_constrained_fit(
                    mean_excess_returns=mean_returns,
                    betas=betas,
                    factor_means=model_factors.mean(),
                )
                if model in TRADED_FACTOR_MODELS
                else float("nan")
            )
            summary["constrained_fit_applicable"] = model in TRADED_FACTOR_MODELS
            summary["mean_pricing_error"] = result.diagnostics["mean_pricing_error"]
            summary["replication_status"] = REPLICATION_STATUS
            summary_rows.append(summary)

            print(
                f"{model:32s} {asset_set:26s} N={result.n_assets:3d} "
                f"fit={result.article_cross_sectional_fit: .4f} "
                f"chi2={result.chi_square_statistic:8.2f} "
                f"(p={result.chi_square_asymptotic_p_value:.3f})"
            )

    for path in (FIRST_PASS_PARQUET, SECOND_PASS_PARQUET, RISK_PRICE_CSV):
        path.parent.mkdir(parents=True, exist_ok=True)

    beta_frame = pd.DataFrame.from_records(beta_rows)
    beta_frame.to_parquet(FIRST_PASS_PARQUET, index=False)
    pd.DataFrame.from_records(error_rows).to_parquet(PRICING_ERRORS_PARQUET, index=False)
    summary_frame = pd.DataFrame.from_records(summary_rows)
    summary_frame.to_parquet(SECOND_PASS_PARQUET, index=False)
    summary_frame.to_csv(RISK_PRICE_CSV, index=False)

    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_baseline_replication.py",
                "replication_status": REPLICATION_STATUS,
                "window": {
                    "start": str(panel.index[0]),
                    "end": str(panel.index[-1]),
                    "months": months,
                },
                "inputs": {
                    "baseline_panel": {
                        "path": PANEL_PARQUET.as_posix(),
                        "sha256": _sha256(PANEL_PARQUET),
                    },
                    "comparator_factors": {
                        "path": COMPARATOR_PARQUET.as_posix(),
                        "sha256": _sha256(COMPARATOR_PARQUET),
                    },
                },
                "models": {model: list(names) for model, names in MODELS.items()},
                "asset_sets": {name: len(columns) for name, columns in asset_sets.items()},
                "first_pass": {
                    "estimator": "ols_with_intercept",
                    "covariance": "newey_west",
                    "hac_lags": hac_lags,
                    "hac_lag_rule": (
                        "automatic; the article does not state a lag rule. The choice affects "
                        "only first-pass t-statistics, which the article does not tabulate, and "
                        "does not affect the betas, the second pass, or any audited cell."
                    ),
                },
                "second_pass": {
                    "estimator": "no_intercept_ols_article_equation_4",
                    "uncertainty": "shanken_1992",
                    "fit_metric": "article_cross_sectional_fit_equation_6",
                    "specification_test": "article_equation_5_chi_square_with_pseudo_inverse",
                },
                "outputs": {
                    path.as_posix(): _sha256(path)
                    for path in (
                        FIRST_PASS_PARQUET,
                        SECOND_PASS_PARQUET,
                        PRICING_ERRORS_PARQUET,
                        RISK_PRICE_CSV,
                    )
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote {len(summary_frame)} model-by-asset-set systems to {RISK_PRICE_CSV}")


if __name__ == "__main__":
    main()
