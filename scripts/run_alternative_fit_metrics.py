"""Compute the article's second evaluation measure beside its first.

Internet Appendix Section 2.7 defines an alternative cross-sectional fit,
``rho-hat squared``, which replaces the variance in the denominator of the
paper's equation (6) with the cross-sectional second moment. The article
introduces it because equation (6) can be negative, and warns in the same
paragraph that the replacement has its own failure mode: a model "can have a
large value of rho-hat squared just by fitting well the cross-sectional mean
despite not explaining any cross-sectional dispersion in risk premia".

That warning is why both are reported here and neither is reported alone. The
gap between them is informative in its own right: it is large exactly when a
system's apparent fit comes from the level of average returns rather than from
their spread, which is the distinction the paper's own results turn on.

Nothing is re-estimated. Pricing errors and mean excess returns are already
stored by ``scripts/run_baseline_replication.py``, and both metrics are
functions of those two vectors alone.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.models.article_second_pass import (
    article_cross_sectional_fit,
    kan_robotti_shanken_fit,
)

ERRORS_PARQUET = Path("artifacts/estimates/cross_section/baseline_pricing_errors.parquet")
OUTPUT_CSV = Path("artifacts/tables/cross_section/alternative_fit_metrics.csv")
PROVENANCE_JSON = Path("artifacts/provenance/alternative_fit_metrics.json")

REPLICATION_STATUS = "documented_reconstruction"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_metrics() -> pd.DataFrame:
    """Return both fit metrics for every stored system."""
    errors = pd.read_parquet(ERRORS_PARQUET)
    rows: list[dict[str, object]] = []
    for (model, portfolio_set), block in errors.groupby(["model", "portfolio_set"], sort=True):
        indexed = block.set_index("asset")
        mean_returns = indexed["mean_excess_return"].astype(float)
        pricing_errors = indexed["pricing_error"].astype(float)
        article_fit = article_cross_sectional_fit(mean_returns, pricing_errors)
        alternative_fit = kan_robotti_shanken_fit(mean_returns, pricing_errors)
        rows.append(
            {
                "model": str(model),
                "portfolio_set": str(portfolio_set),
                "n_assets": len(indexed),
                "article_cross_sectional_fit": article_fit,
                "kan_robotti_shanken_fit": alternative_fit,
                # Positive when the alternative measure flatters the system. The
                # article names the mechanism: the second moment carries the
                # level of average returns, which a model can fit without
                # explaining any of their spread.
                "alternative_minus_article": alternative_fit - article_fit,
                "replication_status": REPLICATION_STATUS,
            }
        )
    return pd.DataFrame.from_records(rows)


def main() -> None:
    """Write both metrics and record their provenance."""
    frame = build_metrics()
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    negative = frame.loc[frame["article_cross_sectional_fit"] < 0.0]
    print(f"systems: {len(frame)}")
    print(
        "article fit negative in "
        f"{len(negative)}; of those, the alternative measure is positive in "
        f"{int((negative['kan_robotti_shanken_fit'] > 0.0).sum())}"
    )
    print("widest gaps between the two measures:")
    for record in frame.nlargest(5, "alternative_minus_article").to_dict("records"):
        print(
            f"  {str(record['model'])[:32]:<32} {str(record['portfolio_set'])[:22]:<22} "
            f"article={float(record['article_cross_sectional_fit']):+.4f} "
            f"alternative={float(record['kan_robotti_shanken_fit']):+.4f}"
        )

    PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": "scripts/run_alternative_fit_metrics.py",
                "replication_status": REPLICATION_STATUS,
                "article_metric": "equation_6_variance_denominator",
                "alternative_metric": "internet_appendix_equation_2_second_moment_denominator",
                "centring_convention": (
                    "the numerator variance is centred in both metrics, matching the "
                    "article's equation (6); the appendix does not state the convention "
                    "for its own equation (2), so the two differ only in the denominator"
                ),
                "why_both": (
                    "the article warns that the alternative measure can be large purely by "
                    "fitting the cross-sectional mean, so it is reported beside the paper's "
                    "metric rather than instead of it"
                ),
                "reestimated": False,
                "inputs": {ERRORS_PARQUET.as_posix(): _sha256(ERRORS_PARQUET)},
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
