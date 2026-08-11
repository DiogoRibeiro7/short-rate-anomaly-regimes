"""Decompose average returns into factor risk premia for the extreme deciles.

This is the object the article's Table 5 reports: for the lowest and highest
decile of each anomaly, the average excess return, the risk premium attributable
to each factor, and the pricing error left over. The premium attributable to a
factor is ``beta_i,k * lambda_k``, the loading times the estimated price of that
factor's risk, and the difference row is the low-minus-high spread that the
article reads as what the model does and does not explain.

Nothing here is re-estimated. Every input is already stored by
``scripts/run_baseline_replication.py``: the first-pass betas, the second-pass
risk prices, and the per-asset pricing errors and mean returns. The
decomposition is arithmetic on those, which is why it belongs in its own small
artifact rather than inside the estimation run.

Until this existed the 84 published cells of Table 5 had no generated
counterpart and the audit recorded the whole table as outside its pass.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pandas as pd

BETAS_PARQUET = Path("artifacts/estimates/time_series/baseline_first_pass_betas.parquet")
ERRORS_PARQUET = Path("artifacts/estimates/cross_section/baseline_pricing_errors.parquet")
RISK_PRICE_CSV = Path("artifacts/tables/cross_section/baseline_risk_prices.csv")

OUTPUT_CSV = Path("artifacts/tables/cross_section/risk_premium_decomposition.csv")
PROVENANCE_JSON = Path("artifacts/provenance/risk_premium_decomposition.json")

#: The article reports Table 5 for the ICAPM built on the federal funds rate.
MODEL = "market_plus_fedfunds_innovation"

#: The article's D1 and D10. Its note defines D1 as the lowest decile and DIF as
#: the difference across the extreme deciles, and its discussion reads every
#: spread as low minus high, so DIF is D1 minus D10 and not the reverse.
LOW_DECILE = "decile_01"
HIGH_DECILE = "decile_10"

FAMILIES = (
    "book_to_market",
    "earnings_to_price",
    "equity_duration",
    "inventory_growth",
    "investment_to_assets",
    "long_term_reversal",
    "ppe_investment",
)

#: Statistic stem to the factor whose premium it reports. The market and rate
#: columns are the two the article prints.
FACTOR_OF_PREMIUM = {
    "risk_premium_market": ("beta_RM", "lambda_RM"),
    "risk_premium_rate": ("beta_FFR_innovation", "lambda_FFR_innovation"),
}

REPLICATION_STATUS = "documented_reconstruction"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _column(frame: pd.DataFrame, column: str) -> dict[Any, float]:
    """Return one column as a plain mapping keyed by the frame's index.

    Reading cells through ``.loc`` with a tuple key yields a union the pandas
    stubs will not narrow, and the lookups here are all by key rather than by
    slice, so the column is materialised once as a dictionary instead.
    """
    return {key: float(cast("float", value)) for key, value in frame[column].items()}


def build_decomposition() -> pd.DataFrame:
    """Return one row per anomaly family with the twelve Table 5 quantities."""
    betas = pd.read_parquet(BETAS_PARQUET)
    errors = pd.read_parquet(ERRORS_PARQUET)
    prices = pd.read_csv(RISK_PRICE_CSV)

    # Keyed by portfolio set as well as asset. The joint seventy-portfolio system
    # carries the same asset names as the per-family systems, so keying on the
    # asset alone silently returns the joint system's pricing errors for a
    # per-family row. The article estimates Table 5 within each anomaly group.
    betas = betas.loc[betas["model"] == MODEL].set_index(["portfolio_set", "asset"])
    errors = errors.loc[errors["model"] == MODEL].set_index(["portfolio_set", "asset"])
    prices = prices.loc[prices["model"] == MODEL].set_index("portfolio_set")

    mean_returns = _column(errors, "mean_excess_return")
    pricing_errors = _column(errors, "pricing_error")
    loadings = {stem: _column(betas, beta) for stem, (beta, _) in FACTOR_OF_PREMIUM.items()}
    risk_prices = {stem: _column(prices, price) for stem, (_, price) in FACTOR_OF_PREMIUM.items()}

    rows: list[dict[str, object]] = []
    for family in FAMILIES:
        record: dict[str, object] = {"model": MODEL, "portfolio_set": family}
        per_decile: dict[str, dict[str, float]] = {}
        for label, decile in (("d1", LOW_DECILE), ("d10", HIGH_DECILE)):
            key = (family, f"{family}__{decile}")
            values = {
                "mean_excess_return": mean_returns[key],
                "pricing_error": pricing_errors[key],
            }
            for stem in FACTOR_OF_PREMIUM:
                values[stem] = loadings[stem][key] * risk_prices[stem][family]
            per_decile[label] = values
            for stem, value in values.items():
                record[f"{stem}_{label}"] = value
        # The article's DIF row, low minus high, on every quantity.
        for stem in per_decile["d1"]:
            record[f"{stem}_dif"] = per_decile["d1"][stem] - per_decile["d10"][stem]
        record["replication_status"] = REPLICATION_STATUS
        rows.append(record)
    return pd.DataFrame.from_records(rows)


def main() -> None:
    """Write the decomposition and record its provenance."""
    frame = build_decomposition()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    for row in frame.itertuples():
        print(
            f"{row.portfolio_set:<22} "
            f"dif E(R)={row.mean_excess_return_dif:+.3f} "
            f"rate={row.risk_premium_rate_dif:+.3f} "
            f"alpha={row.pricing_error_dif:+.3f}"
        )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_risk_premium_decomposition.py",
                "replication_status": REPLICATION_STATUS,
                "model": MODEL,
                "definition": (
                    "the premium attributable to factor k is beta_i,k times lambda_k, the "
                    "first-pass loading times the second-pass price of that factor's risk"
                ),
                "difference_convention": "d1 minus d10, the article's low-minus-high spread",
                "reestimated": False,
                "inputs": {
                    path.as_posix(): _sha256(path)
                    for path in (BETAS_PARQUET, ERRORS_PARQUET, RISK_PRICE_CSV)
                },
                "outputs": {OUTPUT_CSV.as_posix(): _sha256(OUTPUT_CSV)},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {OUTPUT_CSV.as_posix()}")


if __name__ == "__main__":
    main()
