import pandas as pd
import pytest

from short_rate_anomaly_regimes.data.validation import validate_monthly_panel


def test_duplicate_month_is_rejected() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2020-01-01", "2020-01-31"],
            "asset": [1.0, 2.0],
        }
    )
    with pytest.raises(ValueError, match="calendar month"):
        validate_monthly_panel(frame)
