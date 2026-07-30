import pandas as pd
import pytest

from short_rate_anomaly_regimes.portfolios.construction import construct_double_sorted_portfolios
from short_rate_anomaly_regimes.regimes.stability import (
    bai_perron_breaks,
    estimate_regime_interactions,
)
from short_rate_anomaly_regimes.shocks.decomposition import decompose_high_frequency_surprises


def test_portfolio_construction_rejects_incomplete_security_panel() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        construct_double_sorted_portfolios(
            pd.DataFrame({"date": ["2020-01-31"], "size": [1.0]}),
            characteristic="book_to_market",
            weighting="value",
        )


def test_shock_decomposition_is_identification_gated() -> None:
    with pytest.raises(NotImplementedError, match="identification"):
        decompose_high_frequency_surprises(
            pd.DataFrame({"rate": [0.01], "equity": [-0.02]}),
            rate_surprise_column="rate",
            equity_surprise_column="equity",
        )


def test_regime_stability_estimators_are_milestone_gated() -> None:
    with pytest.raises(NotImplementedError, match="Milestone 10"):
        estimate_regime_interactions()

    with pytest.raises(NotImplementedError, match="Milestone 10"):
        bai_perron_breaks()
