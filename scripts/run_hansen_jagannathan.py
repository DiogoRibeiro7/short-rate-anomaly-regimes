"""Compute the Hansen-Jagannathan distance of Internet Appendix 2.9.

The appendix estimates the ICAPM in stochastic-discount-factor form,
``M = b1 + b2 RM + b3 rate``, by first-step GMM under the Hansen and Jagannathan
(1997) weighting matrix, and reports the resulting distance in Table A.10.
Everything needed is printed: equation (5) gives the pricing condition, (6) the
SDF, (7) the weighting matrix ``W = (E[R R'])^-1``, and (8) the distance
``HJ = (alpha' W alpha)^(1/2)``. The testing payoffs are stated too, as the gross
returns on the seventy equity portfolios together with the gross risk-free rate.

Two things are deliberately not produced.

The p-value. The appendix reports that the model "is not rejected by this
specification test as the p-values are above 5%", but does not say how that
p-value is obtained. The distribution of the HJ distance under the null is a
weighted sum of chi-squares whose weights depend on nuisance parameters, and
choosing an implementation would be selecting one from a literature the appendix
does not cite for this purpose. The distance is generated; the test is not.

The SDF coefficient t-ratios of Table A.11, which come from the sequential
procedure of Gospodinov, Kan and Robotti (2014) with Bonferroni adjustment. That
is a separate estimator, cited rather than defined here.

Note that these pricing errors are not the beta-representation alphas. They are
``E[M R] - 1`` on gross payoffs, a different object with a different scale, and
the two must not be compared.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PANEL_PARQUET = Path("data/processed/baseline_panel.parquet")
COMPARATOR_PARQUET = Path("data/processed/comparator_factors.parquet")
OUTPUT_CSV = Path("artifacts/tables/cross_section/hansen_jagannathan_distance.csv")
PROVENANCE_JSON = Path("artifacts/provenance/hansen_jagannathan_distance.json")

MODELS: dict[str, tuple[str, ...]] = {
    "capm": ("RM",),
    "market_plus_fedfunds_innovation": ("RM", "FFR_innovation"),
    "market_plus_tbill_innovation": ("RM", "TB_innovation"),
}

#: The panel stores returns in percent per month, so a gross return is one plus
#: the percentage divided by a hundred. Getting this wrong would not fail loudly:
#: it would rescale every pricing error and produce a plausible distance.
PERCENT = 100.0

REPLICATION_STATUS = "documented_reconstruction"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def hansen_jagannathan_distance(
    gross_payoffs: pd.DataFrame,
    factors: pd.DataFrame,
) -> tuple[float, pd.Series, pd.Series]:
    """Return the HJ distance, the SDF coefficients, and the pricing errors.

    The SDF is linear in a constant and the factors, so the pricing errors are
    ``alpha = G b - 1`` with ``G = E[R f']``, and minimising ``alpha' W alpha``
    under ``W = (E[R R'])^-1`` has the closed form ``b = (G' W G)^-1 G' W 1``.

    Args:
        gross_payoffs: Months by payoffs, as gross returns.
        factors: Months by priced factors, sharing the payoff index.

    Returns:
        The distance, the SDF coefficients including the constant, and the errors.

    Raises:
        ValueError: If the inputs are misaligned or the second-moment matrix is singular.
    """
    if not gross_payoffs.index.equals(factors.index):
        raise ValueError("Payoffs and factors must share a time index")
    n_months = len(gross_payoffs)
    payoffs = gross_payoffs.to_numpy(dtype=float)
    design = np.column_stack([np.ones(n_months), factors.to_numpy(dtype=float)])

    second_moment = payoffs.T @ payoffs / n_months
    if np.linalg.matrix_rank(second_moment) < second_moment.shape[0]:
        raise ValueError("The payoff second-moment matrix is singular; W is undefined")
    weighting = np.linalg.inv(second_moment)

    moments = payoffs.T @ design / n_months
    ones = np.ones(payoffs.shape[1])
    bread = moments.T @ weighting
    coefficients = np.linalg.solve(bread @ moments, bread @ ones)
    errors = moments @ coefficients - ones
    distance = float(np.sqrt(errors @ weighting @ errors))

    names = ["constant", *factors.columns]
    return (
        distance,
        pd.Series(coefficients, index=names, name="sdf_coefficient"),
        pd.Series(errors, index=gross_payoffs.columns, name="pricing_error"),
    )


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return the gross payoffs and the factor panel."""
    panel = pd.read_parquet(PANEL_PARQUET)
    index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    ).to_timestamp(how="start")
    panel = panel.drop(columns=["month"]).set_axis(index)

    comparators = pd.read_parquet(COMPARATOR_PARQUET)
    comparator_index = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in comparators["month"]], freq="M"
    ).to_timestamp(how="start")
    factors = comparators.drop(columns=["month"]).set_axis(comparator_index)
    factors["FFR_innovation"] = panel["short_rate_innovation__fedfunds"]
    factors["TB_innovation"] = panel["short_rate_innovation__tb3ms"]

    columns = sorted(c for c in panel.columns if c.startswith("portfolio_excess_return__"))
    risk_free = panel["risk_free_return"].astype(float)
    gross = pd.DataFrame(
        {
            c.removeprefix("portfolio_excess_return__"): 1.0
            + (panel[c].astype(float) + risk_free) / PERCENT
            for c in columns
        },
        index=panel.index,
    )
    # The appendix adds the gross risk-free rate to the seventy equity payoffs.
    gross["risk_free"] = 1.0 + risk_free / PERCENT
    return gross, factors


def main() -> None:
    """Compute the distance for each registered model."""
    gross, factors = load_inputs()

    rows: list[dict[str, Any]] = []
    for model, factor_names in MODELS.items():
        distance, coefficients, errors = hansen_jagannathan_distance(
            gross, factors[list(factor_names)]
        )
        record: dict[str, Any] = {
            "model": model,
            "n_payoffs": int(gross.shape[1]),
            "n_months": len(gross),
            "hansen_jagannathan_distance": distance,
            "max_abs_pricing_error": float(np.max(np.abs(errors.to_numpy(dtype=float)))),
            "replication_status": REPLICATION_STATUS,
        }
        for name, value in coefficients.items():
            record[f"sdf_{name}"] = float(value)
        rows.append(record)

    frame = pd.DataFrame.from_records(rows)
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    print(f"payoffs: {gross.shape[1]} gross returns over {len(gross)} months")
    for entry in frame.to_dict("records"):
        record = {str(key): value for key, value in entry.items()}
        print(f"  {record['model']:<32} HJ={float(record['hansen_jagannathan_distance']):.6f}")

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_hansen_jagannathan.py",
                "replication_status": REPLICATION_STATUS,
                "specification": "internet_appendix_equations_5_to_8_sdf_representation",
                "payoffs": (
                    "the gross returns on the seventy equity portfolios together with the "
                    "gross risk-free rate, as the appendix states"
                ),
                "units": (
                    "the panel stores returns in percent per month, so a gross return is one "
                    "plus the percentage over a hundred; an error here would rescale every "
                    "pricing error and still produce a plausible distance"
                ),
                "not_produced": (
                    "the p-value for the null that the distance is zero, whose distribution "
                    "the appendix does not state, and the Table A.11 SDF coefficient t-ratios, "
                    "which come from the Gospodinov, Kan and Robotti (2014) sequential "
                    "procedure that the appendix cites rather than defines"
                ),
                "pricing_errors_are_not_alphas": (
                    "these errors are E[M R] - 1 on gross payoffs, a different object from the "
                    "beta-representation alphas and on a different scale"
                ),
                "inputs": {
                    path.as_posix(): _sha256(path) for path in (PANEL_PARQUET, COMPARATOR_PARQUET)
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
