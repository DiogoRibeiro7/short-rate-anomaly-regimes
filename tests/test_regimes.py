import pandas as pd
import pytest

from short_rate_anomaly_regimes.regimes.calendar import RegimeInterval, label_regimes


def test_regime_labels_are_exhaustive() -> None:
    dates = pd.date_range("2008-10-31", periods=5, freq="ME")
    intervals = (
        RegimeInterval("pre", pd.Period("2008-10", freq="M"), pd.Period("2008-11", freq="M")),
        RegimeInterval("elb", pd.Period("2008-12", freq="M"), pd.Period("2009-02", freq="M")),
    )
    labels = label_regimes(dates, intervals)
    assert labels.tolist() == ["pre", "pre", "elb", "elb", "elb"]


def test_regime_labels_reject_overlap() -> None:
    dates = pd.date_range("2008-10-31", periods=3, freq="ME")
    intervals = (
        RegimeInterval("pre", pd.Period("2008-10", freq="M"), pd.Period("2008-11", freq="M")),
        RegimeInterval("elb", pd.Period("2008-11", freq="M"), pd.Period("2008-12", freq="M")),
    )

    with pytest.raises(ValueError, match="Overlapping"):
        label_regimes(dates, intervals)


def test_regime_labels_reject_unlabelled_months() -> None:
    dates = pd.date_range("2008-10-31", periods=3, freq="ME")
    intervals = (
        RegimeInterval("pre", pd.Period("2008-10", freq="M"), pd.Period("2008-10", freq="M")),
    )

    with pytest.raises(ValueError, match="Unlabelled"):
        label_regimes(dates, intervals)
