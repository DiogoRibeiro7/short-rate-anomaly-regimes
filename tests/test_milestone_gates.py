import pandas as pd
import pytest

from short_rate_anomaly_regimes.portfolios.construction import construct_double_sorted_portfolios


def test_portfolio_construction_rejects_incomplete_security_panel() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        construct_double_sorted_portfolios(
            pd.DataFrame({"date": ["2020-01-31"], "size": [1.0]}),
            characteristic="book_to_market",
            weighting="value",
        )
