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
#: Section 4), which is not implemented here, so those cells are recorded as not
#: attempted rather than compared against something else.
UNCERTAINTY_COLUMN = {
    "asymptotic_p_value": "chi_square_asymptotic_p_value",
    "shanken_t_statistic": None,  # resolved per row from the factor
}


def _decimals_of(value: object) -> int:
    """Count the decimals printed for an uncertainty value."""
    text = str(value)
    return len(text.split(".")[1]) if "." in text else 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _generated_column(row: Mapping[Hashable, Any], model: str) -> str | None:
    """Resolve the generated column holding the published statistic on this row."""
    statistic = str(row["statistic"])
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


def main() -> None:
    """Build the cell-level audit and the layer-level classification."""
    published = pd.read_csv(PUBLISHED_CSV)
    generated = pd.read_csv(GENERATED_CSV)
    lookup = generated.set_index(["model", "portfolio_set"])

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
            record["generated_uncertainty"] = np.nan
            record["uncertainty_status"] = "not_attempted_bootstrap_not_implemented"
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
    audit.to_csv(AUDIT_CSV, index=False)

    layers = _classify_layers(audit)
    layers.to_csv(LAYER_CSV, index=False)

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/audit_published_targets.py",
                "replication_mode": "documented_reconstruction",
                "exact_input_available": False,
                "inputs": {
                    PUBLISHED_CSV.as_posix(): _sha256(PUBLISHED_CSV),
                    GENERATED_CSV.as_posix(): _sha256(GENERATED_CSV),
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
    layer_statistics = {
        "R1b": (),  # betas are not tabulated by the article
        "R1c": ("lambda_market", "lambda_rate"),
        "R1d": ("chi_square", "r2_ols"),
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
                    "note": (
                        "The article plots first-pass betas in Figure 3 and reports "
                        "beta-times-lambda decompositions in Table 5, but tabulates no "
                        "beta. There is no statistic-level cell to audit, so this layer "
                        "is evidenced only through the layers that consume it."
                    ),
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
