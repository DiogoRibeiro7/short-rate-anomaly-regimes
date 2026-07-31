from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.regimes.calendar import (
    RegimeInterval,
    RegimeSource,
    build_regime_table,
    interval_from_months,
    label_regimes,
    regime_observation_counts,
    shift_regime_boundaries,
    split_sample_eligibility,
)
from short_rate_anomaly_regimes.regimes.stability import (
    bai_perron_breaks,
    chow_test,
    classify_stability,
    cusum_test,
    estimate_regime_interactions,
    holm_adjust_tests,
    quandt_andrews_test,
    regime_interaction_wald_tests,
    write_regime_outputs,
)


def _intervals() -> tuple[RegimeInterval, ...]:
    return (
        RegimeInterval("pre", pd.Period("2008-10", freq="M"), pd.Period("2008-11", freq="M")),
        RegimeInterval("elb", pd.Period("2008-12", freq="M"), pd.Period("2009-02", freq="M")),
    )


def _fixture_panel() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    dates = pd.date_range("2000-01-31", periods=72, freq="ME")
    factors = pd.DataFrame(
        {
            "mkt": np.linspace(-0.03, 0.04, 72),
            "rate": np.sin(np.arange(72)) / 100.0,
        },
        index=dates,
    )
    regimes = pd.Series(
        ["pre"] * 36 + ["post"] * 36,
        index=dates,
        name="regime",
    )
    post = (regimes == "post").astype(float)
    returns = pd.DataFrame(
        {
            "asset_a": 0.01
            + 0.8 * factors["mkt"]
            - 0.2 * factors["rate"]
            + post * 0.5 * factors["rate"],
            "asset_b": -0.01
            + 0.5 * factors["mkt"]
            + 0.1 * factors["rate"]
            - post * 0.3 * factors["rate"],
        },
        index=dates,
    )
    return returns, factors, regimes


def test_regime_labels_are_exhaustive() -> None:
    dates = pd.date_range("2008-10-31", periods=5, freq="ME")
    labels = label_regimes(dates, _intervals())
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


def test_regime_table_sources_and_split_eligibility() -> None:
    source = RegimeSource(
        regime_id="elb",
        boundary_month="2008-12",
        policy_action_date="2008-12-16",
        source_url="https://www.federalreserve.gov/newsevents/pressreleases/monetary20081216b.htm",
        source_note="FOMC lowered the target range.",
    )
    table = build_regime_table(_intervals(), (source,))
    labels = label_regimes(pd.date_range("2008-10-31", periods=5, freq="ME"), _intervals())
    counts = regime_observation_counts(labels)
    eligibility = split_sample_eligibility(labels, minimum_observations=3)

    assert table.set_index("regime_id").loc["elb", "boundary_verified"]
    assert counts.set_index("regime_id").loc["elb", "observations"] == 3
    assert eligibility.set_index("regime_id").loc["elb", "eligible_for_split_sample"]
    assert not bool(eligibility.set_index("regime_id").loc["pre", "eligible_for_split_sample"])
    with pytest.raises(ValueError, match="positive"):
        split_sample_eligibility(labels, minimum_observations=0)


def test_interval_builder_and_boundary_shifts() -> None:
    interval = interval_from_months("test", "2020-01", "2020-03")
    shifted = shift_regime_boundaries(_intervals(), shift_months=1)

    assert interval.end == pd.Period("2020-03", freq="M")
    assert shifted[0].end == pd.Period("2008-12", freq="M")
    assert shifted[1].start == pd.Period("2009-01", freq="M")
    assert shift_regime_boundaries((_intervals()[0],), shift_months=3) == (_intervals()[0],)
    with pytest.raises(ValueError, match="ends before"):
        interval_from_months("bad", "2020-03", "2020-01")
    with pytest.raises(ValueError, match="empty regime"):
        shift_regime_boundaries(_intervals(), shift_months=-3)
    with pytest.raises(ValueError, match="overlaps"):
        shift_regime_boundaries(_intervals(), shift_months=3)


def test_estimate_regime_interactions_and_wald_tests() -> None:
    returns, factors, regimes = _fixture_panel()

    panel = estimate_regime_interactions(returns, factors, regimes, hac_lags=1)
    wald = regime_interaction_wald_tests(returns, factors, regimes, hac_lags=1)

    assert {"asset", "parameter", "coefficient", "p_value"} <= set(panel.columns)
    assert panel["is_regime_interaction"].any()
    assert set(wald["asset"]) == {"asset_a", "asset_b"}
    assert (wald["df"] == 2.0).all()
    with pytest.raises(ValueError, match="Unknown reference"):
        estimate_regime_interactions(returns, factors, regimes, reference_regime="missing")


def test_stability_estimators_detect_known_and_unknown_breaks() -> None:
    dates = pd.date_range("2000-01-31", periods=80, freq="ME")
    x = pd.DataFrame({"mkt": np.linspace(-1.0, 1.0, 80)}, index=dates)
    response = pd.Series(
        np.where(np.arange(80) < 40, 0.5 + 1.0 * x["mkt"], -0.5 + 2.0 * x["mkt"]),
        index=dates,
        name="asset",
    )

    chow = chow_test(
        response,
        x,
        break_month="2003-04",
        min_segment_observations=20,
    )
    qa = quandt_andrews_test(response, x, min_segment_observations=20)
    breaks = bai_perron_breaks(
        response,
        x,
        min_segment_observations=20,
        max_breaks=1,
    )
    cusum = cusum_test(response, x)

    assert chow["statistic"] > 0
    assert qa["break_month"]
    assert breaks.loc[0, "break_month"] == "2003-04"
    assert cusum["statistic"] >= 0


def test_stability_validation_guards() -> None:
    returns, factors, regimes = _fixture_panel()
    response = returns["asset_a"]

    with pytest.raises(TypeError, match="DatetimeIndex"):
        estimate_regime_interactions(returns.reset_index(drop=True), factors, regimes)
    with pytest.raises(ValueError, match="duplicate dates"):
        estimate_regime_interactions(
            pd.DataFrame({"asset_a": [1.0, 2.0]}, index=pd.to_datetime(["2020-01-31"] * 2)),
            factors.iloc[:2],
            regimes.iloc[:2],
        )
    with pytest.raises(ValueError, match="Insufficient observations"):
        chow_test(
            response.iloc[:10], factors.iloc[:10], break_month="2000-03", min_segment_observations=6
        )
    with pytest.raises(ValueError, match="No admissible"):
        quandt_andrews_test(response.iloc[:10], factors.iloc[:10], min_segment_observations=6)
    with pytest.raises(ValueError, match="max_breaks"):
        bai_perron_breaks(response, factors, min_segment_observations=20, max_breaks=-1)
    with pytest.raises(ValueError, match="Insufficient observations"):
        bai_perron_breaks(response.iloc[:10], factors.iloc[:10], min_segment_observations=6)


def test_holm_stability_classification_and_outputs(tmp_path: Path) -> None:
    tests = pd.DataFrame(
        {
            "asset": ["asset_a", "asset_a"],
            "test": ["joint_regime_factor_interactions", "chow_known_break"],
            "p_value": [0.01, 0.20],
            "statistic": [12.0, 1.0],
            "break_month": [pd.NA, "2008-12"],
        }
    )
    adjusted = holm_adjust_tests(tests)
    conclusion = classify_stability(adjusted)
    stable = classify_stability(adjusted.assign(holm_p_value=0.5))

    assert adjusted.loc[0, "holm_p_value"] == pytest.approx(0.02)
    assert conclusion.verdict == "unstable"
    assert stable.verdict == "stable"
    assert classify_stability(pd.DataFrame()).verdict == "inconclusive"
    with pytest.raises(ValueError, match="p_value"):
        holm_adjust_tests(pd.DataFrame({"test": ["missing"]}))

    write_regime_outputs(
        regime_table=pd.DataFrame({"regime_id": ["pre"], "start": ["2000-01"], "end": ["2000-12"]}),
        coefficient_panel=pd.DataFrame(
            {
                "window_end": ["2000-12"],
                "parameter": ["mkt"],
                "coefficient": [1.0],
            }
        ),
        test_results=adjusted,
        conclusion=conclusion,
        table_dir=tmp_path / "tables",
        figure_dir=tmp_path / "figures",
        report_path=tmp_path / "reports" / "regime.md",
    )

    assert (tmp_path / "tables" / "stability_tests.csv").is_file()
    assert (tmp_path / "figures" / "break_dates.pdf").is_file()
    assert "parameter instability" in (tmp_path / "reports" / "regime.md").read_text(
        encoding="utf-8"
    )
