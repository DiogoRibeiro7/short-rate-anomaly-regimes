"""Specification, weak-factor, and influence diagnostics."""

from __future__ import annotations

import pandas as pd


def weak_factor_diagnostics(*, betas: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Return diagnostics for weak or irrelevant factors.

    The final implementation must include rank, dispersion, first-stage strength, and
    misspecification-robust inference appropriate to the selected two-pass estimator.
    """
    del betas, factors
    raise NotImplementedError("Implement under Milestone 8")


def grs_test(*, returns: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Compute the Gibbons-Ross-Shanken joint alpha test."""
    del returns, factors
    raise NotImplementedError("Implement under Milestone 6 and validate by simulation")
