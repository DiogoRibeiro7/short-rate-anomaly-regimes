"""Tests for the article's Table 5 risk-premium decomposition."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from scripts.run_risk_premium_decomposition import (
    FACTOR_OF_PREMIUM,
    HIGH_DECILE,
    LOW_DECILE,
    MODEL,
)

DECOMPOSITION = Path("artifacts/tables/cross_section/risk_premium_decomposition.csv")
BETAS = Path("artifacts/estimates/time_series/baseline_first_pass_betas.parquet")
ERRORS = Path("artifacts/estimates/cross_section/baseline_pricing_errors.parquet")


def _decomposition() -> pd.DataFrame:
    if not DECOMPOSITION.is_file():
        pytest.skip("the decomposition artifact is not generated in this checkout")
    return pd.read_csv(DECOMPOSITION)


def test_the_difference_row_is_low_minus_high() -> None:
    """The article reads every spread as low decile minus high decile.

    Reversing the convention would flip the sign of all seven difference rows
    and silently invert the economic reading the article draws from the table.
    """
    frame = _decomposition()

    for stem in ("mean_excess_return", "pricing_error", *FACTOR_OF_PREMIUM):
        difference = frame[f"{stem}_d1"] - frame[f"{stem}_d10"]
        pd.testing.assert_series_equal(
            frame[f"{stem}_dif"], difference, check_names=False, atol=1e-12
        )


def test_the_decomposition_reads_the_per_family_system() -> None:
    """Pricing errors must come from each family's own estimation, not the joint one.

    The joint seventy-portfolio system carries the same asset names as the
    per-family systems, so keying on the asset alone returns the joint system's
    pricing error for a per-family row. The values differ, and the article
    estimates this table within each anomaly group.
    """
    if not ERRORS.is_file():
        pytest.skip("baseline estimates are not generated in this checkout")
    frame = _decomposition().set_index("portfolio_set")
    errors = pd.read_parquet(ERRORS)
    errors = errors.loc[errors["model"] == MODEL].set_index(["portfolio_set", "asset"])

    for family in frame.index:
        for label, decile in (("d1", LOW_DECILE), ("d10", HIGH_DECILE)):
            own = float(errors.loc[(family, f"{family}__{decile}"), "pricing_error"])
            assert float(frame.loc[family, f"pricing_error_{label}"]) == pytest.approx(own)


def test_the_premium_is_the_loading_times_the_price_of_risk() -> None:
    """The decomposition must be beta times lambda, not a refitted quantity."""
    if not BETAS.is_file():
        pytest.skip("baseline estimates are not generated in this checkout")
    frame = _decomposition().set_index("portfolio_set")
    betas = pd.read_parquet(BETAS)
    betas = betas.loc[betas["model"] == MODEL].set_index(["portfolio_set", "asset"])
    prices = pd.read_csv("artifacts/tables/cross_section/baseline_risk_prices.csv")
    prices = prices.loc[prices["model"] == MODEL].set_index("portfolio_set")

    for family in frame.index:
        for stem, (beta_column, price_column) in FACTOR_OF_PREMIUM.items():
            loading = float(betas.loc[(family, f"{family}__{LOW_DECILE}"), beta_column])
            price = float(prices.loc[family, price_column])
            assert float(frame.loc[family, f"{stem}_d1"]) == pytest.approx(loading * price)


def test_every_table_five_cell_is_compared_and_agrees_in_sign() -> None:
    """The audit must reach all 84 cells, and the signs are the article's claim."""
    audit_path = Path("artifacts/audit/published_target_audit.csv")
    if not audit_path.is_file():
        pytest.skip("the audit is not generated in this checkout")
    audit = pd.read_csv(audit_path)
    cells = audit.loc[audit["source_table"] == "Table 5"]

    assert len(cells) == 84
    assert not cells["generated_value"].isna().any(), "every cell must have a counterpart"
    same_sign = (cells["generated_value"] > 0) == (cells["published_value"] > 0)
    assert same_sign.all(), "the article's economic reading rests on these signs"
