"""Interfaces for licensed CRSP and Compustat portfolio reconstruction."""

from __future__ import annotations

import pandas as pd


def construct_double_sorted_portfolios(
    security_panel: pd.DataFrame,
    *,
    characteristic: str,
    weighting: str,
) -> pd.DataFrame:
    """Construct 5 by 5 size-characteristic portfolios.

    This remains deliberately unimplemented until the original breakpoint universe,
    rebalancing month, accounting lags, delisting return treatment, and weighting rules are
    extracted from the article, supplement, and source papers.
    """
    del security_panel, characteristic, weighting
    raise NotImplementedError("Complete after the portfolio construction contract is frozen")
