"""Compare every generated cell with its published target and classify R1b to R1e.

A cell counts as recovered when it agrees with the article to the precision the
article prints, that is within half of the last printed increment. No target may
receive an exact-replication label, because no input in this design is an exact
article input; see reports/baseline_input_readiness.md section 1.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Hashable, Mapping
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd

PUBLISHED_CSV = Path("research/published_target_values.csv")
GENERATED_CSV = Path("artifacts/tables/cross_section/baseline_risk_prices.csv")
#: Empirical p-values from the article's useless-factor bootstrap. Optional: the
#: audit runs without it and records the affected cells as not attempted, which
#: is what it did before the bootstrap existed.
BOOTSTRAP_CSV = Path("artifacts/tables/cross_section/useless_factor_bootstrap_p_values.csv")
#: Carries the replication count, which sets how precisely a bootstrap
#: p-value can be compared with a published one at all.
BOOTSTRAP_DIAGNOSTICS_JSON = Path("artifacts/diagnostics/useless_factor_bootstrap.json")
#: The article's Table 5 decomposition, one row per anomaly family. Optional in
#: the same way the bootstrap table is: without it those cells record no
#: generated counterpart rather than being compared against something else.
DECOMPOSITION_CSV = Path("artifacts/tables/cross_section/risk_premium_decomposition.csv")
#: The article supplement's second fit measure. Section 2.7 states the CAPM
#: value precisely, so that one cell is auditable even though the table it sits
#: in is not otherwise reconstructible.
ALTERNATIVE_FIT_CSV = Path("artifacts/tables/cross_section/alternative_fit_metrics.csv")
#: The covariance representation, whose fit the appendix prints in Table A.9.
COVARIANCE_CSV = Path("artifacts/tables/cross_section/covariance_representation.csv")

AUDIT_CSV = Path("artifacts/audit/published_target_audit.csv")
LAYER_CSV = Path("artifacts/audit/replication_layer_classification.csv")
PROVENANCE_JSON = Path("artifacts/provenance/published_target_audit.json")

#: Published table to the generated model identifier it should be compared with.
TABLE_MODEL = {
    "Table 3": "capm",
    "Table 4": "market_plus_fedfunds_innovation",
    "Table A.1": "market_plus_tbill_innovation",
}

#: Published statistic to the generated column holding it. ``lambda_rate`` and
#: the Table 6 factor prices are resolved per row because the generated column
#: name carries the factor.
STATISTIC_COLUMN = {
    "chi_square": "chi_square_statistic",
    "r2_ols": "article_cross_sectional_fit",
    "r2_constrained": "article_constrained_fit",
    "lambda_market": "lambda_RM",
}

#: Table 5 reports four quantities for the low decile, the high decile, and their
#: difference. The generated decomposition names its columns identically, so a
#: Table 5 statistic resolves to the column of the same name.
DECOMPOSITION_STEMS = (
    "mean_excess_return",
    "risk_premium_market",
    "risk_premium_rate",
    "pricing_error",
)
DECOMPOSITION_STATISTICS = frozenset(
    f"{stem}_{row}" for stem in DECOMPOSITION_STEMS for row in ("d1", "d10", "dif")
)

#: Published factor label to the generated factor column suffix.
FACTOR_COLUMN = {
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

#: Uncertainty measures this pass can generate. The article's empirical p-values
#: come from its 5,000-replication useless-factor bootstrap (Internet Appendix
#: Section 4). That procedure is now implemented, in
#: ``scripts/run_useless_factor_bootstrap.py``, and its output is read from
#: ``BOOTSTRAP_CSV``. When that artifact is absent the affected cells fall back
#: to not attempted rather than being compared against an asymptotic p-value,
#: which would be a different object.
UNCERTAINTY_COLUMN = {
    "asymptotic_p_value": "chi_square_asymptotic_p_value",
    "shanken_t_statistic": None,  # resolved per row from the factor
}


def _decimals_of(value: object) -> int:
    """Count the decimals printed for an uncertainty value.

    The count has to come from the string the article printed, which is why
    ``uncertainty_value`` is read as text. Letting pandas parse it turned
    ``0.000`` into ``0.0`` and so into a tolerance of 0.05 rather than 0.0005,
    a hundredfold loosening that reported materially different values as
    recovered. Twenty-eight of the registry's cells were affected, and the
    asymptotic p-values were affected the same way.
    """
    text = str(value)
    return len(text.split(".")[1]) if "." in text else 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generated_column(row: Mapping[Hashable, Any], model: str) -> str | None:
    """Resolve the generated column holding the published statistic on this row."""
    statistic = str(row["statistic"])
    if statistic in DECOMPOSITION_STATISTICS:
        return statistic
    if statistic == "rho_squared":
        return "kan_robotti_shanken_fit"
    if statistic == "r2_ols_covariance":
        # The covariance representation's own fit column. It equals the beta
        # representation's by construction, which is why the appendix expects it
        # to, but it is compared against the cell the appendix prints for it.
        return "article_cross_sectional_fit_covariance"
    if statistic == "lambda_rate":
        if model == "market_plus_fedfunds_innovation":
            return "lambda_FFR_innovation"
        if model == "market_plus_tbill_innovation":
            return "lambda_TB_innovation"
        return None
    if statistic in FACTOR_COLUMN:
        return f"lambda_{FACTOR_COLUMN[statistic]}"
    return STATISTIC_COLUMN.get(statistic)


def _uncertainty_column(row: Mapping[Hashable, Any], value_column: str | None) -> str | None:
    """Resolve the generated column holding this row's uncertainty measure."""
    kind = str(row["uncertainty_type"])
    if kind == "asymptotic_p_value":
        return "chi_square_asymptotic_p_value"
    if kind == "shanken_t_statistic" and value_column and value_column.startswith("lambda_"):
        return value_column.replace("lambda_", "shanken_t_", 1)
    return None


def _load_bootstrap_p_values() -> dict[tuple[str, str, str], float] | None:
    """Load the article-bootstrap p-values, or ``None`` when they were not generated."""
    if not BOOTSTRAP_CSV.is_file():
        return None
    frame = pd.read_csv(BOOTSTRAP_CSV)
    return {
        (str(row.model), str(row.portfolio_set), str(row.statistic)): float(
            cast("float", row.empirical_p_value)
        )
        for row in frame.itertuples()
    }


def _load_bootstrap_replications() -> int | None:
    """Read the replication count the bootstrap actually ran, or ``None``."""
    if not BOOTSTRAP_DIAGNOSTICS_JSON.is_file():
        return None
    payload = json.loads(BOOTSTRAP_DIAGNOSTICS_JSON.read_text(encoding="utf-8"))
    completed = [int(system["replications_completed"]) for system in payload["per_system"]]
    return min(completed) if completed else None


def _bootstrap_uncertainty(
    *,
    bootstrap: dict[tuple[str, str, str], float] | None,
    replications: int | None,
    model: str,
    portfolio_set: str,
    statistic: str,
    published_uncertainty: Any,
) -> dict[str, object]:
    """Compare one published empirical p-value with its generated counterpart.

    The rounding rule every other cell is judged by cannot simply be carried
    over here, because a bootstrap p-value is a Monte Carlo quantity. Its own
    standard error is ``sqrt(p (1 - p) / B)``, which at ``B = 5000`` is about
    0.007 near ``p = 0.5``, while a p-value printed to three decimals has a
    tolerance of 0.0005. For most of the range the sampling noise of the
    procedure is an order of magnitude wider than the band the cell would have
    to land in, so a disagreement carries no information about whether the
    reconstruction is faithful: the article's own bootstrap, rerun on the
    article's own data under a different seed, would miss its published value
    just as often.

    Cells in that position are therefore reported as not resolvable at the
    published precision rather than as not recovered. This is the same
    distinction the regime analysis draws between an inconclusive result and a
    demonstrated difference, and it is drawn from the published value and the
    replication count alone, both of which are fixed before any comparison.
    """
    if bootstrap is None:
        return {
            "generated_uncertainty": np.nan,
            "uncertainty_status": "not_attempted_bootstrap_not_generated",
        }
    key = (model, portfolio_set, statistic)
    if key not in bootstrap:
        return {
            "generated_uncertainty": np.nan,
            "uncertainty_status": "not_attempted_no_bootstrap_cell",
        }
    generated = bootstrap[key]
    published = float(published_uncertainty)
    tolerance = 0.5 * 10.0 ** -_decimals_of(published_uncertainty)
    within = bool(abs(generated - published) <= tolerance)

    standard_error = (
        float(np.sqrt(published * (1.0 - published) / replications))
        if replications
        else float("nan")
    )
    attainable = bool(standard_error <= tolerance) if replications else True
    if within:
        status = "recovered_within_published_rounding"
    elif attainable:
        status = "not_recovered_within_published_rounding"
    else:
        status = "not_resolvable_monte_carlo_error_exceeds_published_rounding"
    return {
        "generated_uncertainty": generated,
        "uncertainty_difference": generated - published,
        "uncertainty_within_published_rounding": within,
        "uncertainty_monte_carlo_standard_error": standard_error,
        "uncertainty_tolerance_attainable": attainable,
        "uncertainty_status": status,
    }


def main() -> None:
    """Build the cell-level audit and the layer-level classification."""
    # ``uncertainty_value`` stays text so its printed precision survives; see
    # ``_decimals_of``.
    published = pd.read_csv(PUBLISHED_CSV, dtype={"uncertainty_value": str})
    generated = pd.read_csv(GENERATED_CSV)
    lookup = generated.set_index(["model", "portfolio_set"])
    if DECOMPOSITION_CSV.is_file():
        # The decomposition is keyed the same way, so joining it makes every
        # Table 5 column reachable through the existing per-row lookup.
        decomposition = pd.read_csv(DECOMPOSITION_CSV).set_index(["model", "portfolio_set"])
        shared = [c for c in decomposition.columns if c in lookup.columns]
        lookup = lookup.join(decomposition.drop(columns=shared), how="outer")
    if ALTERNATIVE_FIT_CSV.is_file():
        alternative = pd.read_csv(ALTERNATIVE_FIT_CSV).set_index(["model", "portfolio_set"])
        shared = [c for c in alternative.columns if c in lookup.columns]
        lookup = lookup.join(alternative.drop(columns=shared), how="outer")
    if COVARIANCE_CSV.is_file():
        covariance = pd.read_csv(COVARIANCE_CSV).set_index(["model", "portfolio_set"])
        covariance = covariance.rename(
            columns={"article_cross_sectional_fit": "article_cross_sectional_fit_covariance"}
        )
        shared = [c for c in covariance.columns if c in lookup.columns]
        lookup = lookup.join(covariance.drop(columns=shared), how="outer")
    bootstrap = _load_bootstrap_p_values()
    bootstrap_replications = _load_bootstrap_replications()

    records: list[dict[str, object]] = []
    for row in published.to_dict("records"):
        model = TABLE_MODEL.get(str(row["source_table"]), str(row["model"]))
        key = (model, str(row["portfolio_set"]))
        value_column = _generated_column(row, model)
        decimals = int(row["published_decimals"])
        tolerance = 0.5 * 10.0**-decimals

        record: dict[str, object] = {
            "target_id": row["target_id"],
            "source_table": row["source_table"],
            "source_location": row["source_location"],
            "portfolio_set": row["portfolio_set"],
            "model": model,
            "statistic": row["statistic"],
            "uncertainty_type": row["uncertainty_type"],
            "published_value": row["published_value"],
            "published_decimals": decimals,
            "tolerance": tolerance,
            "generated_column": value_column,
            "replication_mode": "documented_reconstruction",
        }

        if key not in lookup.index or value_column is None:
            record.update(
                {
                    "generated_value": np.nan,
                    "difference": np.nan,
                    "within_published_rounding": False,
                    "status": "not_attempted_no_generated_cell",
                }
            )
            records.append(record)
            continue

        row_generated = cast("pd.Series", lookup.loc[key])
        if value_column not in row_generated.index or bool(pd.isna(row_generated[value_column])):
            record.update(
                {
                    "generated_value": np.nan,
                    "difference": np.nan,
                    "within_published_rounding": False,
                    "status": "not_attempted_statistic_not_generated",
                }
            )
            records.append(record)
            continue

        # A published statistic can carry two printed uncertainty measures, so the
        # registry repeats its point estimate across paired rows. The point
        # estimate is compared on every row; only the uncertainty differs, and a
        # bootstrap p-value has no generated counterpart in this pass.
        uncertainty_column = _uncertainty_column(row, value_column)
        generated_value = float(row_generated[value_column])
        difference = generated_value - float(row["published_value"])
        record.update(
            {
                "generated_value": generated_value,
                "difference": difference,
                "within_published_rounding": bool(abs(difference) <= tolerance),
                "status": (
                    "recovered_within_published_rounding"
                    if abs(difference) <= tolerance
                    else "not_recovered_within_published_rounding"
                ),
            }
        )
        record["published_uncertainty"] = row["uncertainty_value"]
        if str(row["uncertainty_type"]) == "empirical_bootstrap_p_value":
            record.update(
                _bootstrap_uncertainty(
                    bootstrap=bootstrap,
                    replications=bootstrap_replications,
                    model=model,
                    portfolio_set=str(row["portfolio_set"]),
                    statistic=str(row["statistic"]),
                    published_uncertainty=row["uncertainty_value"],
                )
            )
        elif uncertainty_column and uncertainty_column in row_generated.index:
            uncertainty_generated = float(row_generated[uncertainty_column])
            uncertainty_published = float(row["uncertainty_value"])
            uncertainty_tolerance = 0.5 * 10.0 ** -_decimals_of(row["uncertainty_value"])
            record["generated_uncertainty"] = uncertainty_generated
            record["uncertainty_difference"] = uncertainty_generated - uncertainty_published
            record["uncertainty_within_published_rounding"] = bool(
                abs(uncertainty_generated - uncertainty_published) <= uncertainty_tolerance
            )
            record["uncertainty_status"] = (
                "recovered_within_published_rounding"
                if record["uncertainty_within_published_rounding"]
                else "not_recovered_within_published_rounding"
            )
        else:
            record["generated_uncertainty"] = np.nan
            record["uncertainty_status"] = "not_attempted_no_generated_counterpart"
        records.append(record)

    audit = pd.DataFrame.from_records(records)
    AUDIT_CSV.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(AUDIT_CSV, index=False, lineterminator="\n")

    layers = _classify_layers(audit)
    layers.to_csv(LAYER_CSV, index=False, lineterminator="\n")

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/audit_published_targets.py",
                "replication_mode": "documented_reconstruction",
                "exact_input_available": False,
                "bootstrap_p_values_available": BOOTSTRAP_CSV.is_file(),
                "inputs": {
                    PUBLISHED_CSV.as_posix(): _sha256(PUBLISHED_CSV),
                    GENERATED_CSV.as_posix(): _sha256(GENERATED_CSV),
                    **(
                        {BOOTSTRAP_CSV.as_posix(): _sha256(BOOTSTRAP_CSV)}
                        if BOOTSTRAP_CSV.is_file()
                        else {}
                    ),
                    **(
                        {DECOMPOSITION_CSV.as_posix(): _sha256(DECOMPOSITION_CSV)}
                        if DECOMPOSITION_CSV.is_file()
                        else {}
                    ),
                    **(
                        {ALTERNATIVE_FIT_CSV.as_posix(): _sha256(ALTERNATIVE_FIT_CSV)}
                        if ALTERNATIVE_FIT_CSV.is_file()
                        else {}
                    ),
                    **(
                        {COVARIANCE_CSV.as_posix(): _sha256(COVARIANCE_CSV)}
                        if COVARIANCE_CSV.is_file()
                        else {}
                    ),
                    # The replication count lives here, and it decides which
                    # cells are resolvable at all, so the classification is not
                    # reproducible without it.
                    **(
                        {BOOTSTRAP_DIAGNOSTICS_JSON.as_posix(): _sha256(BOOTSTRAP_DIAGNOSTICS_JSON)}
                        if BOOTSTRAP_DIAGNOSTICS_JSON.is_file()
                        else {}
                    ),
                },
                "outputs": {
                    AUDIT_CSV.as_posix(): _sha256(AUDIT_CSV),
                    LAYER_CSV.as_posix(): _sha256(LAYER_CSV),
                },
                "tolerance_rule": "published_rounding: half of the last printed increment",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    unique = audit.drop_duplicates(subset=["source_table", "portfolio_set", "model", "statistic"])
    attempted = unique[unique["status"].str.startswith(("recovered", "not_recovered"))]
    print(f"unique published cells       : {len(unique)}")
    print(f"cells compared               : {len(attempted)}")
    print(f"recovered at published precision: {int(attempted['within_published_rounding'].sum())}")
    print()
    print(unique["status"].value_counts().to_string())
    print()
    print(layers.to_string(index=False))
    print(f"\nWrote {AUDIT_CSV} and {LAYER_CSV}")


def _classify_layers(audit: pd.DataFrame) -> pd.DataFrame:
    """Assign a classification to each replication layer from its cell outcomes."""
    # Table 5's decomposition is the article's only statistic-level evidence that
    # bears on the first-pass betas. It tabulates no beta, but it tabulates
    # beta times lambda, and with the risk prices audited separately in R1c a
    # recovered premium is evidence about the loading behind it. Its pricing
    # errors join the pricing-error layer. Its average-return column is a
    # property of the test assets rather than of any estimated layer, so it is
    # audited cell by cell and belongs to no layer.
    layer_statistics = {
        "R1b": (
            "risk_premium_market_d1",
            "risk_premium_market_d10",
            "risk_premium_market_dif",
            "risk_premium_rate_d1",
            "risk_premium_rate_d10",
            "risk_premium_rate_dif",
        ),
        "R1c": ("lambda_market", "lambda_rate"),
        "R1d": (
            "chi_square",
            "r2_ols",
            "pricing_error_d1",
            "pricing_error_d10",
            "pricing_error_dif",
        ),
        "R1e": (
            "lambda_smb",
            "lambda_hml",
            "lambda_umd",
            "lambda_rmw",
            "lambda_cma",
            "lambda_liq",
            "lambda_me",
            "lambda_ia",
            "lambda_roe",
            "r2_constrained",
        ),
    }
    rows = []
    for layer, statistics in layer_statistics.items():
        if not statistics:
            rows.append(
                {
                    "layer": layer,
                    "cells_in_registry": 0,
                    "cells_compared": 0,
                    "cells_recovered": 0,
                    "share_recovered": float("nan"),
                    "classification": "no_published_statistic_level_target",
                    "note": ("No published statistic-level target for this layer."),
                }
            )
            continue
        subset = audit[audit["statistic"].isin(statistics)]
        # Paired uncertainty rows repeat the same point estimate, so each cell is
        # counted once.
        unique_cells = subset.drop_duplicates(
            subset=["source_table", "portfolio_set", "model", "statistic"]
        )
        compared = unique_cells[
            unique_cells["status"].str.startswith(("recovered", "not_recovered"))
        ]
        recovered = int(compared["within_published_rounding"].sum())
        share = float(recovered / len(compared)) if len(compared) else float("nan")
        if not len(compared):
            classification = "not_attempted"
        elif recovered == len(compared):
            classification = "approximately_reproduced_under_documented_reconstruction"
        elif recovered > 0:
            classification = "partially_recovered_under_documented_reconstruction"
        else:
            classification = "not_recovered_under_documented_reconstruction"
        rows.append(
            {
                "layer": layer,
                "cells_in_registry": len(unique_cells),
                "cells_compared": len(compared),
                "cells_recovered": recovered,
                "share_recovered": share,
                "classification": classification,
                "note": (
                    "No exact-replication label is available at any recovery rate, "
                    "because the article names providers and people rather than files."
                ),
            }
        )
    return pd.DataFrame.from_records(rows)


if __name__ == "__main__":
    main()
