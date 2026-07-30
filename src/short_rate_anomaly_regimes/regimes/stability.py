"""Parameter-stability tests for factor loadings and risk prices."""

from __future__ import annotations

import pandas as pd


def estimate_regime_interactions(*args: object, **kwargs: object) -> pd.DataFrame:
    """Estimate regime-specific changes relative to a declared reference regime."""
    del args, kwargs
    raise NotImplementedError("Implement in Milestone 10 with robust covariance and joint tests")


def bai_perron_breaks(*args: object, **kwargs: object) -> pd.DataFrame:
    """Estimate multiple structural breaks with minimum segment constraints."""
    del args, kwargs
    raise NotImplementedError("Implement in Milestone 10 and validate on simulated breaks")
