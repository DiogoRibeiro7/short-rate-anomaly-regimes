"""Policy and central-bank information shock decomposition."""

from __future__ import annotations

import pandas as pd


def decompose_high_frequency_surprises(
    event_data: pd.DataFrame,
    *,
    rate_surprise_column: str,
    equity_surprise_column: str,
) -> pd.DataFrame:
    """Separate policy and information components using a documented identification rule.

    A production implementation must state the exact sign, rotation, normalization, event
    window, and treatment of zero or ambiguous observations. It must not reduce the method to
    an undocumented sign split.
    """
    del event_data, rate_surprise_column, equity_surprise_column
    raise NotImplementedError("Implement after the shock dataset and identification are frozen")
