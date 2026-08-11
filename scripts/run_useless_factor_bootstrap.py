"""Run the article's useless-factor bootstrap for every system with a published p-value.

Every empirical p-value the article prints comes from the 5,000-replication
procedure of Internet Appendix Section 4. Until it was implemented, those cells
were recorded as ``not_attempted_bootstrap_not_implemented``: comparing them
against an asymptotic p-value would have compared two different objects, and the
audit refused to do that. This script generates the missing side of that
comparison.

Scope is taken from the published-target registry rather than from the model
grid, so the systems estimated here are exactly those the article prints an
empirical p-value for. Running the full grid would generate cells with nothing
to audit them against.

The result is a reconstruction of the article's bootstrap, not the article's own
bootstrap: the algorithm is the published one, but its inputs are reconstructed
panels, so every row carries ``documented_reconstruction``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from short_rate_anomaly_regimes.models.useless_factor_bootstrap import (
    ARTICLE_REPLICATIONS,
    REPLICATION_STATUS,
    bootstrap_useless_factor_p_values,
)

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")
TARGET_REGISTRY = Path("research/published_target_values.csv")
BASELINE_CONFIG = Path("configs/baseline.yaml")

P_VALUE_CSV = Path("artifacts/tables/cross_section/useless_factor_bootstrap_p_values.csv")
DIAGNOSTICS_JSON = Path("artifacts/diagnostics/useless_factor_bootstrap.json")
PROVENANCE_JSON = Path("artifacts/provenance/useless_factor_bootstrap.json")

#: The registry's ``uncertainty_type`` for a cell whose p-value comes from the
#: article's bootstrap. These are the only cells this script can serve.
BOOTSTRAP_UNCERTAINTY = "empirical_bootstrap_p_value"

MODELS: dict[str, tuple[str, ...]] = {
    "capm": ("RM",),
    "market_plus_fedfunds_innovation": ("RM", "FFR_innovation"),
    "market_plus_tbill_innovation": ("RM", "TB_innovation"),
    "fama_french_3": ("RM", "SMB", "HML"),
    "carhart_4": ("RM", "SMB", "HML", "UMD"),
    "fama_french_5": ("RM", "SMB", "HML", "RMW", "CMA"),
    "q_factor": ("RM", "ME", "IA", "ROE"),
    "liquidity": ("RM", "SMB", "HML", "LIQ"),
}

FAMILY_MEMBERS = (
    "book_to_market",
    "earnings_to_price",
    "equity_duration",
    "inventory_growth",
    "investment_to_assets",
    "long_term_reversal",
    "ppe_investment",
)

#: The registry names risk prices per factor. This maps a registry statistic to
#: the factor column whose p-value answers it.
STATISTIC_TO_FACTOR: dict[str, str] = {
    "lambda_market": "RM",
    "lambda_smb": "SMB",
    "lambda_hml": "HML",
    "lambda_umd": "UMD",
    "lambda_rmw": "RMW",
    "lambda_cma": "CMA",
    "lambda_liq": "LIQ",
    "lambda_me": "ME",
    "lambda_ia": "IA",
    "lambda_roe": "ROE",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _short_label(column: str) -> str:
    return column.removeprefix("portfolio_excess_return__")


def _load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, list[str]]]:
    """Load the baseline panel, the factor panel, and the registered asset sets."""
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
        asset_sets[family] = sorted(
            column
            for column in panel.columns
            if column.startswith(f"portfolio_excess_return__{family}__")
        )
    asset_sets["all_seven_families_joint"] = sorted(
        column for column in panel.columns if column.startswith("portfolio_excess_return__")
    )
    return panel, factors, asset_sets


def registered_bootstrap_systems() -> list[tuple[str, str]]:
    """Return the (model, portfolio set) systems the article prints a p-value for."""
    registry = pd.read_csv(TARGET_REGISTRY)
    bootstrap_rows = registry.loc[registry["uncertainty_type"] == BOOTSTRAP_UNCERTAINTY]
    systems = bootstrap_rows[["model", "portfolio_set"]].drop_duplicates()
    return sorted((str(row.model), str(row.portfolio_set)) for row in systems.itertuples())


def main() -> None:
    """Estimate the bootstrap for every registered system and write the artifacts."""
    panel, factors, asset_sets = _load_inputs()
    months = len(panel)
    seed = int(
        yaml.safe_load(BASELINE_CONFIG.read_text(encoding="utf-8"))["project"]["random_seed"]
    )
    timestamps = pd.PeriodIndex(panel.index, freq="M").to_timestamp(how="start")

    rows: list[dict[str, object]] = []
    system_diagnostics: list[dict[str, object]] = []
    degenerate_total = 0

    for position, (model, portfolio_set) in enumerate(registered_bootstrap_systems()):
        factor_names = MODELS[model]
        model_factors = factors[list(factor_names)].set_axis(timestamps)
        columns = asset_sets[portfolio_set]
        excess_returns = panel[columns].rename(columns={c: _short_label(c) for c in columns})
        excess_returns = excess_returns.set_axis(timestamps)

        # A distinct seed per system, derived from the project seed rather than
        # drawn, so a rerun reproduces every cell and no two systems share a
        # replication sequence.
        result = bootstrap_useless_factor_p_values(
            excess_returns=excess_returns,
            factors=model_factors,
            portfolio_set=portfolio_set,
            model=model,
            seed=seed + position,
            n_replications=ARTICLE_REPLICATIONS,
        )
        print(
            f"{model} / {portfolio_set}: "
            f"chi2 p={result.chi_square_p_value:.4f} fit p={result.article_fit_p_value:.4f}"
        )

        for statistic, factor in STATISTIC_TO_FACTOR.items():
            if factor not in factor_names:
                continue
            rows.append(
                {
                    "model": model,
                    "portfolio_set": portfolio_set,
                    "statistic": statistic,
                    "generated_value": float(result.sample_risk_prices[factor]),
                    "shanken_t_statistic": float(result.sample_shanken_t_statistics[factor]),
                    "empirical_p_value": float(result.risk_price_p_values[factor]),
                    "bootstrap_t_statistic_median": float(
                        result.bootstrap_t_statistic_medians[factor]
                    ),
                    "replication_status": REPLICATION_STATUS,
                }
            )
        # The rate risk price is named ``lambda_rate`` in the registry whichever
        # short rate the model uses, because the article prints one row for it.
        for factor in ("FFR_innovation", "TB_innovation"):
            if factor not in factor_names:
                continue
            rows.append(
                {
                    "model": model,
                    "portfolio_set": portfolio_set,
                    "statistic": "lambda_rate",
                    "generated_value": float(result.sample_risk_prices[factor]),
                    "shanken_t_statistic": float(result.sample_shanken_t_statistics[factor]),
                    "empirical_p_value": float(result.risk_price_p_values[factor]),
                    "bootstrap_t_statistic_median": float(
                        result.bootstrap_t_statistic_medians[factor]
                    ),
                    "replication_status": REPLICATION_STATUS,
                }
            )
        rows.append(
            {
                "model": model,
                "portfolio_set": portfolio_set,
                "statistic": "chi_square",
                "generated_value": result.sample_chi_square,
                "shanken_t_statistic": float("nan"),
                "empirical_p_value": result.chi_square_p_value,
                "bootstrap_t_statistic_median": float("nan"),
                "replication_status": REPLICATION_STATUS,
            }
        )
        rows.append(
            {
                "model": model,
                "portfolio_set": portfolio_set,
                "statistic": "r2_ols",
                "generated_value": result.sample_article_fit,
                "shanken_t_statistic": float("nan"),
                "empirical_p_value": result.article_fit_p_value,
                "bootstrap_t_statistic_median": float("nan"),
                "replication_status": REPLICATION_STATUS,
            }
        )

        degenerate_total += result.n_replications_degenerate
        system_diagnostics.append(
            {
                "model": model,
                "portfolio_set": portfolio_set,
                "seed": result.seed,
                "n_assets": result.n_assets,
                "replications_completed": result.n_replications_completed,
                "replications_degenerate": result.n_replications_degenerate,
                **{key: float(value) for key, value in result.diagnostics.items()},
            }
        )

    frame = pd.DataFrame.from_records(rows).sort_values(
        ["model", "portfolio_set", "statistic"], ignore_index=True
    )
    P_VALUE_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(P_VALUE_CSV, index=False, lineterminator="\n")

    DIAGNOSTICS_JSON.parent.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS_JSON.write_text(
        json.dumps(
            {
                "procedure": "article_useless_factor_bootstrap_internet_appendix_section_4",
                "replications_requested_per_system": ARTICLE_REPLICATIONS,
                "systems": len(system_diagnostics),
                "project_seed": seed,
                "seed_rule": "project seed plus the system's index in sorted registry order",
                "replications_degenerate_total": degenerate_total,
                "null": (
                    "factors are resampled on a time sequence independent of the residual "
                    "sequence, so the factors cannot explain returns by construction"
                ),
                "what_the_p_value_answers": (
                    "how often a factor known to be useless produces a t-ratio this extreme in a "
                    "cross-section of this shape. It is not the p-value of lambda equals zero in "
                    "a correctly specified model"
                ),
                "role": "replication_audit_only_not_a_registered_gate",
                "confirmatory_bootstrap_is_elsewhere": (
                    "the repository's own inference remains the moving-block bootstrap frozen in "
                    "research/bootstrap_contract.md, which differs in resampling unit, block "
                    "length and replication count"
                ),
                "replication_status": REPLICATION_STATUS,
                "per_system": system_diagnostics,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_useless_factor_bootstrap.py",
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
                    "published_target_registry": {
                        "path": TARGET_REGISTRY.as_posix(),
                        "sha256": _sha256(TARGET_REGISTRY),
                    },
                },
                "outputs": {
                    path.as_posix(): _sha256(path) for path in (P_VALUE_CSV, DIAGNOSTICS_JSON)
                },
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {P_VALUE_CSV.as_posix()} with {len(frame)} rows")


if __name__ == "__main__":
    main()
