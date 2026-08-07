"""Interfaces for licensed CRSP and Compustat portfolio reconstruction."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.portfolios.loaders import canonical_25_portfolio_labels

WeightingMethod = Literal["value", "equal"]
PortfolioSetStatus = Literal[
    "exact",
    "author_provided",
    "approximately_reproduced",
    "missing",
]


@dataclass(frozen=True, slots=True)
class PortfolioConstructionRule:
    """Documented construction rule for one portfolio-return set."""

    source_id: str
    status: PortfolioSetStatus
    source_type: str
    formula: str
    breakpoint_rule: str
    weighting: str
    required_inputs: tuple[str, ...]
    output_label: str
    notes: str


@dataclass(frozen=True, slots=True)
class PortfolioConstructionResult:
    """Constructed portfolio panel plus security-level weight audit data."""

    returns: pd.DataFrame
    weights: pd.DataFrame
    status: PortfolioSetStatus


def default_construction_rules() -> tuple[PortfolioConstructionRule, ...]:
    """Return the registered Milestone 4 portfolio-set status matrix."""
    return (
        PortfolioConstructionRule(
            source_id="french_size_bm_25",
            status="missing",
            source_type="public_kenneth_french",
            formula="Monthly value-weighted 5 by 5 returns sorted on size and book-to-market.",
            breakpoint_rule=(
                "Use the exact Kenneth French archive once its filename/version is frozen."
            ),
            weighting="provider_value_weighted",
            required_inputs=("Kenneth French exact monthly 25 Size-BM archive",),
            output_label="missing_source_definition",
            notes="Parser implemented; source registry still lacks the exact archive name.",
        ),
        PortfolioConstructionRule(
            source_id="french_size_long_term_reversal_25",
            status="missing",
            source_type="public_kenneth_french",
            formula="Monthly value-weighted 5 by 5 returns sorted on size and long-term reversal.",
            breakpoint_rule=(
                "Use the exact Kenneth French archive once its filename/version is frozen."
            ),
            weighting="provider_value_weighted",
            required_inputs=("Kenneth French exact monthly 25 Size-Reversal archive",),
            output_label="missing_source_definition",
            notes="Parser implemented; source registry still lacks the exact archive name.",
        ),
        PortfolioConstructionRule(
            source_id="size_asset_growth_25",
            status="missing",
            source_type="author_or_wrds",
            formula="Monthly value-weighted 5 by 5 returns sorted on size and asset growth.",
            breakpoint_rule=(
                "Freeze CRSP/Compustat filters, accounting lag, breakpoint universe, "
                "and rebalancing month before any WRDS reconstruction."
            ),
            weighting="value_weighted_market_equity",
            required_inputs=(
                "author portfolio returns",
                "CRSP monthly returns",
                "Compustat annuals",
            ),
            output_label="not_reproducible_missing_input",
            notes=(
                "Prefer author data; reconstructed output must be labelled "
                "approximately_reproduced."
            ),
        ),
        PortfolioConstructionRule(
            source_id="size_equity_duration_25",
            status="missing",
            source_type="author_or_wrds",
            formula="Monthly value-weighted 5 by 5 returns sorted on size and equity duration.",
            breakpoint_rule=(
                "Freeze source-paper duration formula, CRSP/Compustat filters, lags, "
                "breakpoints, and rebalancing month before reconstruction."
            ),
            weighting="value_weighted_market_equity",
            required_inputs=(
                "author portfolio returns",
                "CRSP monthly returns",
                "Compustat annuals",
            ),
            output_label="not_reproducible_missing_input",
            notes=(
                "Prefer author data; reconstructed output must be labelled "
                "approximately_reproduced."
            ),
        ),
        PortfolioConstructionRule(
            source_id="size_inventory_growth_25",
            status="missing",
            source_type="author_or_wrds",
            formula="Monthly value-weighted 5 by 5 returns sorted on size and inventory growth.",
            breakpoint_rule=(
                "Freeze inventory-growth formula, CRSP/Compustat filters, lags, breakpoints, "
                "and rebalancing month before reconstruction."
            ),
            weighting="value_weighted_market_equity",
            required_inputs=(
                "author portfolio returns",
                "CRSP monthly returns",
                "Compustat annuals",
            ),
            output_label="not_reproducible_missing_input",
            notes=(
                "Prefer author data; reconstructed output must be labelled "
                "approximately_reproduced."
            ),
        ),
    )


def write_construction_manifest(
    path: Path,
    *,
    rules: tuple[PortfolioConstructionRule, ...] | None = None,
) -> None:
    """Write a machine-readable construction manifest and status matrix."""
    selected_rules = rules or default_construction_rules()
    payload = {
        "version": 1,
        "portfolio_sets": [asdict(rule) for rule in selected_rules],
        "status_matrix": [
            {
                "source_id": rule.source_id,
                "exact": rule.status == "exact",
                "author_provided": rule.status == "author_provided",
                "reconstructed": rule.status == "approximately_reproduced",
                "missing": rule.status == "missing",
                "output_label": rule.output_label,
            }
            for rule in selected_rules
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8", newline="\n")


def construct_double_sorted_portfolios(
    security_panel: pd.DataFrame,
    *,
    characteristic: str,
    weighting: WeightingMethod,
    date_column: str = "date",
    return_column: str = "return",
    size_column: str = "market_equity",
    security_id_column: str = "security_id",
    status: PortfolioSetStatus = "approximately_reproduced",
) -> PortfolioConstructionResult:
    """Construct 5 by 5 size-characteristic portfolios from security-level data.

    The engine is intentionally generic. Article-specific CRSP and Compustat filters must be
    frozen outside this function before empirical reconstructed panels are used.
    """
    if status == "exact":
        raise ValueError("Security-level reconstructions cannot be labelled exact")
    if weighting not in {"value", "equal"}:
        raise ValueError("weighting must be 'value' or 'equal'")
    required_columns = {
        date_column,
        return_column,
        size_column,
        characteristic,
        security_id_column,
    }
    missing_columns = required_columns - set(security_panel.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Security panel is missing required columns: {missing}")

    clean = security_panel.loc[:, list(required_columns)].copy()
    clean[date_column] = pd.to_datetime(clean[date_column], errors="raise")
    numeric_columns = [return_column, size_column, characteristic]
    for column in numeric_columns:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    clean = clean.dropna(subset=numeric_columns)
    clean = clean[clean[size_column] > 0].copy()
    if clean.empty:
        raise ValueError("Security panel contains no eligible rows after filters")

    rows: list[dict[str, float | pd.Timestamp]] = []
    weight_pieces: list[pd.DataFrame] = []
    for month, month_frame in clean.groupby(date_column, sort=True):
        assigned = _assign_double_sort_buckets(
            month_frame,
            size_column=size_column,
            characteristic_column=characteristic,
        )
        labels = canonical_25_portfolio_labels(characteristic_prefix=characteristic)
        return_row: dict[str, float | pd.Timestamp] = {date_column: pd.Timestamp(str(month))}
        for label in labels:
            bucket = assigned[assigned["portfolio"] == label].copy()
            if bucket.empty:
                return_row[label] = np.nan
                continue
            if weighting == "value":
                denominator = float(bucket[size_column].sum())
                bucket["weight"] = bucket[size_column] / denominator
            else:
                bucket["weight"] = 1.0 / float(bucket.shape[0])
            portfolio_return = float((bucket[return_column] * bucket["weight"]).sum())
            return_row[label] = portfolio_return
            weight_pieces.append(
                bucket.loc[
                    :,
                    [date_column, security_id_column, "portfolio", "weight"],
                ]
            )
        rows.append(return_row)

    returns = _combine_portfolio_rows(
        rows,
        date_column=date_column,
        characteristic_prefix=characteristic,
    )
    weights = (
        pd.concat(weight_pieces, ignore_index=True)
        if weight_pieces
        else pd.DataFrame(columns=[date_column, security_id_column, "portfolio", "weight"])
    )
    validate_portfolio_weights(weights, date_column=date_column)
    return PortfolioConstructionResult(returns=returns, weights=weights, status=status)


def validate_portfolio_weights(
    weights: pd.DataFrame,
    *,
    date_column: str = "date",
    tolerance: float = 1e-10,
) -> None:
    """Validate that security weights sum to one in each portfolio-month."""
    required_columns = {date_column, "portfolio", "weight"}
    missing_columns = required_columns - set(weights.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Weight panel is missing required columns: {missing}")
    grouped = weights.groupby([date_column, "portfolio"], observed=True)["weight"].sum()
    if not np.allclose(grouped.to_numpy(dtype=float), 1.0, atol=tolerance):
        raise ValueError("Portfolio weights must sum to one within each portfolio-month")


def _assign_double_sort_buckets(
    frame: pd.DataFrame,
    *,
    size_column: str,
    characteristic_column: str,
) -> pd.DataFrame:
    assigned = frame.copy()
    assigned["size_bucket"] = _quintile_codes(assigned[size_column])
    assigned["characteristic_bucket"] = np.nan
    for _size_bucket, size_frame in assigned.groupby("size_bucket", sort=True):
        indexes = size_frame.index
        assigned.loc[indexes, "characteristic_bucket"] = _quintile_codes(
            size_frame[characteristic_column]
        ).to_numpy()
    assigned = assigned.dropna(subset=["size_bucket", "characteristic_bucket"]).copy()
    assigned["size_bucket"] = assigned["size_bucket"].astype(int)
    assigned["characteristic_bucket"] = assigned["characteristic_bucket"].astype(int)
    assigned["portfolio"] = [
        f"size_{size_bucket}_{characteristic_column}_{characteristic_bucket}"
        for size_bucket, characteristic_bucket in zip(
            assigned["size_bucket"],
            assigned["characteristic_bucket"],
            strict=True,
        )
    ]
    return assigned


def _quintile_codes(series: pd.Series) -> pd.Series:
    ranks = series.rank(method="first")
    count = int(ranks.shape[0])
    if count < 5:
        raise ValueError("At least five securities are required per sort group")
    codes = np.floor((ranks.to_numpy(dtype=float) - 1.0) * 5.0 / count).astype(int) + 1
    codes = np.clip(codes, 1, 5)
    return pd.Series(codes, index=series.index)


def _combine_portfolio_rows(
    rows: list[dict[str, float | pd.Timestamp]],
    *,
    date_column: str,
    characteristic_prefix: str,
) -> pd.DataFrame:
    combined = pd.DataFrame(rows)
    ordered_columns = [
        date_column,
        *canonical_25_portfolio_labels(characteristic_prefix=characteristic_prefix),
    ]
    return combined.loc[:, ordered_columns].sort_values(date_column).reset_index(drop=True)
