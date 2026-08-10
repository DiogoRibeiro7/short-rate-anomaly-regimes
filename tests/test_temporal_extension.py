import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.run_temporal_extension import (
    BASELINE_PARQUET,
    EXTENSION_PARQUET,
    FEDFUNDS_CSV,
    FITTED_PREMIUM_BOUND,
    RATE,
    REVISED_PARQUET,
    _inferential_status,
    _load,
    _spread_pairs,
    lagged_level,
    load_current_vintage_rate,
    pre_window_lag,
    rate_level,
    relative_change_draws,
    spread_draws,
    standardized_dispersion_share,
    window_bootstrap,
)

from short_rate_anomaly_regimes.extensions.temporal import (
    TemporalFreeze,
    TemporalPanelBuild,
    aggregate_pattern_change,
    build_temporal_panel,
    compare_pre_post_patterns,
    evaluate_frozen_pricing,
    observation_summary_table,
    pricing_error_summary,
    refit_windows,
    revision_audit_table,
    write_boundary_figure,
    write_temporal_extension_outputs,
)
from short_rate_anomaly_regimes.models.block_bootstrap import recover_lagged_level
from short_rate_anomaly_regimes.portfolios.q_archive import FAMILY_MEMBERS
from short_rate_anomaly_regimes.regimes.equivalence import (
    EquivalenceOutcome,
    classify_equivalence,
    paired_difference_draws,
)


def _freeze() -> TemporalFreeze:
    return TemporalFreeze(
        baseline_start="1972-01",
        baseline_end="2013-12",
        extension_start="2014-01",
        latest_common_month="2014-03",
        retrieval_date="2026-07-31",
        baseline_vintage_label="locked_original_1972_2013",
        extension_vintage_label="extension_retrieved_2026_07_31",
    )


def test_build_temporal_panel_labels_vintages_and_reduced_universe() -> None:
    baseline = pd.DataFrame(
        {"asset_a": [0.01, 0.02], "asset_b": [0.03, 0.04]},
        index=pd.to_datetime(["2013-11-30", "2013-12-31"]),
    )
    extension = pd.DataFrame(
        {
            "asset_a": [0.01, 0.02, 0.03, 0.04, 0.05],
            "asset_c": [0.06, 0.07, 0.08, 0.09, 0.10],
        },
        index=pd.to_datetime(
            ["2013-11-30", "2013-12-31", "2014-01-31", "2014-02-28", "2014-03-31"]
        ),
    )

    built = build_temporal_panel(
        locked_baseline=baseline,
        extension_vintage=extension,
        freeze=_freeze(),
    )

    assert built.monthly_panel["vintage"].unique().tolist() == [
        "locked_original_1972_2013",
        "extension_retrieved_2026_07_31",
    ]
    assert built.monthly_panel["sample_period"].unique().tolist() == [
        "locked_baseline",
        "post_publication_extension",
    ]
    assert built.revision_audit.empty
    assert (
        built.universe.set_index("series_id").loc["asset_b", "status"]
        == "baseline_only_not_extended"
    )
    assert (
        built.universe.set_index("series_id").loc["asset_c", "status"]
        == "extension_only_not_in_baseline"
    )
    assert set(built.observation_summary["sample_period"]) == {
        "locked_baseline",
        "post_publication_extension",
    }


def test_build_temporal_panel_rejects_revised_locked_baseline_values() -> None:
    baseline = pd.DataFrame(
        {"asset_a": [0.01, 0.02]},
        index=pd.to_datetime(["2013-11-30", "2013-12-31"]),
    )
    extension = pd.DataFrame(
        {"asset_a": [0.01, 0.03, 0.04]},
        index=pd.to_datetime(["2013-11-30", "2013-12-31", "2014-01-31"]),
    )

    audit = revision_audit_table(locked_baseline=baseline, revised_history=extension)

    assert audit.loc[0, "month"] == "2013-12"
    with pytest.raises(ValueError, match="Revised baseline-period data detected"):
        build_temporal_panel(
            locked_baseline=baseline,
            extension_vintage=extension,
            freeze=_freeze(),
        )
    allowed = build_temporal_panel(
        locked_baseline=baseline,
        extension_vintage=extension,
        freeze=_freeze(),
        allow_revisions=True,
    )
    assert not allowed.revision_audit.empty


def test_build_temporal_panel_validation_guards() -> None:
    baseline = pd.DataFrame(
        {"asset_a": [0.01]},
        index=pd.to_datetime(["2013-12-31"]),
    )
    extension = pd.DataFrame(
        {"asset_a": [0.02]},
        index=pd.to_datetime(["2014-01-31"]),
    )

    invalid_policy = replace(_freeze(), revision_policy="merge")
    with pytest.raises(ValueError, match="revision_policy"):
        build_temporal_panel(
            locked_baseline=baseline,
            extension_vintage=extension,
            freeze=invalid_policy,
        )

    invalid_start = replace(_freeze(), extension_start="2013-12")
    with pytest.raises(ValueError, match="extension_start"):
        build_temporal_panel(
            locked_baseline=baseline,
            extension_vintage=extension,
            freeze=invalid_start,
        )

    invalid_end = replace(_freeze(), latest_common_month="2013-12")
    with pytest.raises(ValueError, match="latest_common_month"):
        build_temporal_panel(
            locked_baseline=baseline,
            extension_vintage=extension,
            freeze=invalid_end,
        )

    with pytest.raises(ValueError, match="no observations"):
        build_temporal_panel(
            locked_baseline=baseline.iloc[0:0],
            extension_vintage=extension,
            freeze=_freeze(),
        )

    with pytest.raises(ValueError, match="No compatible series"):
        build_temporal_panel(
            locked_baseline=baseline.rename(columns={"asset_a": "baseline_only"}),
            extension_vintage=extension,
            freeze=_freeze(),
        )

    with pytest.raises(ValueError, match="no post-baseline observations"):
        build_temporal_panel(
            locked_baseline=baseline,
            extension_vintage=extension.loc[extension.index < "2014-01-01"],
            freeze=_freeze(),
        )


def test_revision_audit_skips_joint_missing_values_and_index_errors() -> None:
    dates = pd.to_datetime(["2013-12-31"])
    locked = pd.DataFrame({"asset_a": [float("nan")]}, index=dates)
    revised = pd.DataFrame({"asset_a": [float("nan")]}, index=dates)

    assert revision_audit_table(locked_baseline=locked, revised_history=revised).empty
    with pytest.raises(TypeError, match="DatetimeIndex"):
        revision_audit_table(
            locked_baseline=pd.DataFrame({"asset_a": [1.0]}, index=["2013-12"]),
            revised_history=revised,
        )
    duplicated = pd.DataFrame(
        {"asset_a": [1.0, 1.0]},
        index=pd.to_datetime(["2013-12-31", "2013-12-31"]),
    )
    with pytest.raises(ValueError, match="duplicate dates"):
        revision_audit_table(locked_baseline=duplicated, revised_history=revised)


def test_evaluate_frozen_pricing_uses_december_2013_parameters() -> None:
    post_returns = pd.DataFrame(
        {"asset_a": [0.05, 0.07], "asset_b": [0.02, 0.04]},
        index=pd.to_datetime(["2014-01-31", "2014-02-28"]),
    )
    frozen_betas = pd.DataFrame(
        {"mkt": [1.0, 0.5], "rate": [0.2, -0.1]},
        index=["asset_a", "asset_b"],
    )
    frozen_prices = pd.Series({"const": 0.01, "mkt": 0.03, "rate": -0.02})

    table, summary = evaluate_frozen_pricing(
        post_returns=post_returns,
        frozen_betas=frozen_betas,
        frozen_risk_prices=frozen_prices,
    )

    assert table.loc[0, "frozen_expected_mean_return"] == pytest.approx(0.036)
    assert table.loc[0, "frozen_pricing_error"] == pytest.approx(0.024)
    assert summary["rmse"] > 0
    assert summary["n_assets"] == 2.0


def test_evaluate_frozen_pricing_validation_guards() -> None:
    returns = pd.DataFrame({"asset_a": [0.01]}, index=pd.to_datetime(["2014-01-31"]))
    betas = pd.DataFrame({"mkt": [1.0]}, index=["asset_a"])
    prices = pd.Series({"mkt": 0.02})

    with pytest.raises(ValueError, match="post_returns"):
        evaluate_frozen_pricing(
            post_returns=returns.iloc[0:0],
            frozen_betas=betas,
            frozen_risk_prices=prices,
        )
    with pytest.raises(ValueError, match="frozen_betas"):
        evaluate_frozen_pricing(
            post_returns=returns,
            frozen_betas=betas.iloc[0:0],
            frozen_risk_prices=prices,
        )
    with pytest.raises(ValueError, match="No common assets"):
        evaluate_frozen_pricing(
            post_returns=returns.rename(columns={"asset_a": "other"}),
            frozen_betas=betas,
            frozen_risk_prices=prices,
        )
    with pytest.raises(ValueError, match="missing factors"):
        evaluate_frozen_pricing(
            post_returns=returns,
            frozen_betas=betas,
            frozen_risk_prices=pd.Series({"rate": 0.01}),
        )

    flat_observed = pd.Series([0.01, 0.01], index=["a", "b"])
    summary = pricing_error_summary(errors=pd.Series([0.0, 0.01]), observed=flat_observed)
    assert pd.isna(summary["out_of_sample_r2"])


def test_compare_pre_post_patterns_and_publication_decay_summary() -> None:
    dates = pd.date_range("2013-01-31", periods=3, freq="ME")
    pre_returns = pd.DataFrame({"low": [0.01, 0.02, 0.01], "high": [0.05, 0.04, 0.06]}, index=dates)
    post_returns = pd.DataFrame(
        {"low": [0.02, 0.02, 0.03], "high": [0.03, 0.03, 0.04]},
        index=pd.date_range("2014-01-31", periods=3, freq="ME"),
    )
    pre_betas = pd.DataFrame({"rate": [-0.5, 0.7]}, index=["low", "high"])
    post_betas = pd.DataFrame({"rate": [0.6, -0.4]}, index=["low", "high"])

    patterns = compare_pre_post_patterns(
        pre_returns=pre_returns,
        post_returns=post_returns,
        pre_betas=pre_betas,
        post_betas=post_betas,
    )
    summary = aggregate_pattern_change(patterns, factor_names=("rate",))

    assert set(patterns["asset"]) == {"low", "high"}
    assert summary["post_high_minus_low_spread"] < summary["pre_high_minus_low_spread"]
    assert summary["rate_beta_rank_correlation"] == pytest.approx(-1.0)
    skipped = aggregate_pattern_change(patterns, factor_names=("missing",))
    assert "missing_beta_rank_correlation" not in skipped


def test_compare_pre_post_patterns_validation_guards() -> None:
    returns = pd.DataFrame({"asset_a": [0.01]}, index=pd.to_datetime(["2013-12-31"]))
    betas = pd.DataFrame({"mkt": [1.0]}, index=["asset_a"])

    with pytest.raises(ValueError, match="No common assets"):
        compare_pre_post_patterns(
            pre_returns=returns,
            post_returns=returns.rename(columns={"asset_a": "other"}),
            pre_betas=betas,
            post_betas=betas,
        )
    with pytest.raises(ValueError, match="No common factors"):
        compare_pre_post_patterns(
            pre_returns=returns,
            post_returns=returns,
            pre_betas=betas,
            post_betas=betas.rename(columns={"mkt": "rate"}),
        )
    with pytest.raises(ValueError, match="pattern_table"):
        aggregate_pattern_change(pd.DataFrame(), factor_names=("mkt",))


def test_refit_windows_separates_expanding_and_rolling_designs() -> None:
    dates = pd.date_range("1999-01-31", periods=60, freq="ME")

    expanding = refit_windows(
        dates,
        initial_train_end="1999-12",
        evaluation_end="2001-12",
        refit_frequency_months=12,
    )
    rolling = refit_windows(
        dates,
        initial_train_end="1999-12",
        evaluation_end="2001-12",
        refit_frequency_months=12,
        rolling_window_months=12,
    )

    assert expanding.loc[0, "window_type"] == "expanding"
    assert rolling.loc[0, "window_type"] == "rolling"
    assert expanding.loc[1, "train_start"] == "1999-01"
    assert rolling.loc[1, "train_start"] == "2000-01"


def test_refit_windows_validation_guards() -> None:
    dates = pd.date_range("1999-01-31", periods=12, freq="ME")

    with pytest.raises(ValueError, match="refit_frequency"):
        refit_windows(
            dates,
            initial_train_end="1999-12",
            evaluation_end="2000-12",
            refit_frequency_months=0,
        )
    with pytest.raises(ValueError, match="rolling_window"):
        refit_windows(
            dates,
            initial_train_end="1999-12",
            evaluation_end="2000-12",
            refit_frequency_months=12,
            rolling_window_months=0,
        )
    with pytest.raises(ValueError, match="dates"):
        refit_windows(
            pd.DatetimeIndex([]),
            initial_train_end="1999-12",
            evaluation_end="2000-12",
            refit_frequency_months=12,
        )


def test_output_helpers_reject_missing_columns(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Monthly panel"):
        observation_summary_table(pd.DataFrame({"value": [1.0]}))
    with pytest.raises(ValueError, match="Monthly panel"):
        write_boundary_figure(
            pd.DataFrame({"month": ["2014-01"], "value": [1.0]}),
            output_path=tmp_path / "figure.pdf",
            boundary_month="2013-12",
        )


def test_write_temporal_extension_outputs(tmp_path: Path) -> None:
    freeze = _freeze()
    panel_build = TemporalPanelBuild(
        monthly_panel=pd.DataFrame(
            {
                "month": ["2013-12", "2014-01"],
                "series_id": ["asset_a", "asset_a"],
                "value": [0.01, 0.02],
                "vintage": [
                    "locked_original_1972_2013",
                    "extension_retrieved_2026_07_31",
                ],
                "sample_period": ["locked_baseline", "post_publication_extension"],
            }
        ),
        revision_audit=pd.DataFrame(
            columns=[
                "month",
                "series_id",
                "baseline_value",
                "revised_value",
                "absolute_revision",
                "relative_revision",
            ]
        ),
        universe=pd.DataFrame(
            {
                "series_id": ["asset_a"],
                "in_locked_baseline": [True],
                "in_extension_vintage": [True],
                "included_in_extension": [True],
                "status": ["included_compatible_definition"],
            }
        ),
        observation_summary=pd.DataFrame(
            {
                "sample_period": ["locked_baseline", "post_publication_extension"],
                "vintage": ["locked_original_1972_2013", "extension_retrieved_2026_07_31"],
                "observations": [1, 1],
                "first_month": ["2013-12", "2014-01"],
                "last_month": ["2013-12", "2014-01"],
                "n_series": [1, 1],
            }
        ),
    )
    frozen = pd.DataFrame(
        {
            "asset": ["asset_a"],
            "post_mean_return": [0.02],
            "frozen_expected_mean_return": [0.015],
            "frozen_pricing_error": [0.005],
        }
    )
    patterns = pd.DataFrame(
        {
            "asset": ["asset_a"],
            "pre_mean_return": [0.01],
            "post_mean_return": [0.02],
            "mean_return_change": [0.01],
        }
    )

    write_temporal_extension_outputs(
        panel_build=panel_build,
        frozen_pricing=frozen,
        pattern_comparison=patterns,
        pattern_summary=pd.Series({"spread_change": 0.01}),
        table_dir=tmp_path / "tables",
        figure_dir=tmp_path / "figures",
        report_path=tmp_path / "reports" / "temporal.md",
        freeze=freeze,
    )

    assert (tmp_path / "tables" / "freeze_metadata.json").is_file()
    assert (tmp_path / "figures" / "december_2013_boundary.pdf").is_file()
    assert "vintages are labelled" in (tmp_path / "reports" / "temporal.md").read_text(
        encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# H2 autoregressive timing convention
#
# The vintage-isolation design compares the locked baseline with the revised
# history over the same months, so the difference between them is a vintage
# difference only if the two share an autoregressive timing convention. The
# project's frozen convention is the pre-window lag: the month *before* the
# window supplies the lag for the window's first month. Seeding a window's
# recursion with its own first month instead silently changes the timing of one
# system and turns the vintage comparison into a vintage-plus-timing comparison.
# --------------------------------------------------------------------------- #

H2_STABILITY = Path("artifacts/diagnostics/h2_temporal_stability.json")

PANEL_INPUTS = (BASELINE_PARQUET, EXTENSION_PARQUET, REVISED_PARQUET, FEDFUNDS_CSV)

requires_panels = pytest.mark.skipif(
    not all(path.is_file() for path in PANEL_INPUTS),
    reason="the H2 panels and the frozen rate series are not present in this checkout",
)


def test_the_h2_diagnostic_declares_one_pre_window_lag_for_every_evaluation() -> None:
    """The published H2 artifact must record the timing convention it was run under.

    This is the committed-artifact half of the guard: the shipped diagnostic has
    to state that every evaluation used the pre-window lag, and the lag it records
    for the locked baseline has to be the same number the revised history used.
    If those two ever diverge, the vintage decomposition is measuring a timing
    change as though it were a data revision.
    """
    stability = json.loads(H2_STABILITY.read_text(encoding="utf-8"))
    timing = stability["ar_timing_convention"]

    assert timing["convention"] == "pre_window_lag"
    levels = timing["pre_window_lag_level"]
    assert levels["locked_baseline_1972_2013"] == pytest.approx(
        levels["revised_history_1972_2013"], abs=1e-12
    )
    assert timing["locked_baseline_recovered_first_lag"] == pytest.approx(
        levels["locked_baseline_1972_2013"], abs=1e-8
    )


@requires_panels
def test_every_h2_evaluation_lags_its_first_month_on_the_preceding_month() -> None:
    """Each AR(1) must start from the observed month before its own window.

    Three claims are asserted together because the design needs all three: the
    locked baseline's recovered first lag is the observed December 1971 level, the
    revised history is built with that same lag rather than with its own January
    1972 level, and the extension window starts from the observed December 2013
    level rather than from a row of the baseline panel.
    """
    rate = load_current_vintage_rate()
    baseline = _load(BASELINE_PARQUET)
    revised = _load(REVISED_PARQUET)
    extension = _load(EXTENSION_PARQUET)

    december_1971 = rate_level(rate, pd.Period("1971-12", freq="M"))
    december_2013 = rate_level(rate, pd.Period("2013-12", freq="M"))

    recovered_baseline_first_lag = float(
        recover_lagged_level(
            baseline[f"short_rate_level__{RATE}"].to_numpy(dtype=float),
            baseline[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float),
        )[0]
    )
    assert recovered_baseline_first_lag == pytest.approx(december_1971, abs=1e-8)

    revised_first_lag = lagged_level(revised, previous_level=pre_window_lag(rate, revised))[0]
    assert revised_first_lag == pytest.approx(recovered_baseline_first_lag, abs=1e-8)
    # The bug the guard exists for: the first window month used as its own lag.
    assert revised_first_lag != pytest.approx(float(revised[f"short_rate_level__{RATE}"].iloc[0]))

    assert pre_window_lag(rate, extension) == pytest.approx(december_2013, abs=1e-12)
    assert pre_window_lag(rate, extension) == pytest.approx(
        float(baseline[f"short_rate_level__{RATE}"].iloc[-1]), abs=1e-12
    )


@requires_panels
def test_the_two_historical_vintage_designs_share_an_identical_lag_vector() -> None:
    """The locked baseline and the revised history must lag every month alike.

    Agreement on the first month alone would not settle it, so the whole recovered
    baseline lag vector is compared against the revised design. Any difference
    that survives here would enter the vintage decomposition as though a rate
    revision had caused it.
    """
    rate = load_current_vintage_rate()
    baseline = _load(BASELINE_PARQUET)
    revised = _load(REVISED_PARQUET)

    recovered = recover_lagged_level(
        baseline[f"short_rate_level__{RATE}"].to_numpy(dtype=float),
        baseline[f"short_rate_innovation__{RATE}"].to_numpy(dtype=float),
    )
    built = lagged_level(revised, previous_level=pre_window_lag(rate, revised))

    assert np.allclose(recovered, built, atol=1e-8)


def test_pre_window_lag_refuses_to_substitute_a_missing_preceding_month() -> None:
    """A series that stops at the window start must raise rather than improvise."""
    rate = pd.Series(
        [3.51, 3.30, 3.83],
        index=pd.period_range("1972-01", periods=3, freq="M"),
    )
    panel = pd.DataFrame(
        {f"short_rate_level__{RATE}": [3.51, 3.30, 3.83]},
        index=pd.period_range("1972-01", periods=3, freq="M"),
    )

    with pytest.raises(ValueError, match="1971-12"):
        pre_window_lag(rate, panel)


# --------------------------------------------------------------------------- #
# H2 supplementary inferential classification
#
# The registered H2 rule compares point estimates, so on its own it can only
# report supported or unsupported. The registry defines a third outcome for
# evidence too imprecise to classify, and the joint bootstrap below is what
# makes that outcome reachable. These tests hold two things apart: that the
# interval machinery distinguishes a demonstrated change from imprecision, and
# that it never touches the frozen verdict.
# --------------------------------------------------------------------------- #


def _outcome(category: str, *, passes: bool) -> EquivalenceOutcome:
    """Build an outcome carrying one decision category, for the status reducer."""
    return EquivalenceOutcome(
        estimand="synthetic",
        point_change=0.0,
        lower_90=-1.0,
        upper_90=1.0,
        lower_95=-2.0,
        upper_95=2.0,
        bound=FITTED_PREMIUM_BOUND,
        one_sided=False,
        passes=passes,
        passes_strict_sensitivity=passes,
        decision_category=category,
    )


def test_inferential_status_separates_imprecision_from_a_demonstrated_change() -> None:
    """Failing the interval test is not the same claim as exceeding the bound.

    All three registry outcomes must be reachable, and the middle one must not
    absorb the third: a run in which every estimand merely straddles its bound
    has demonstrated nothing about the economic relation and has to say so.
    """
    equivalent = _outcome("equivalent_within_bound", passes=True)
    inconclusive = _outcome("inconclusive", passes=False)
    exceeds = _outcome("difference_exceeds_bound", passes=False)

    assert _inferential_status([equivalent, equivalent]).endswith(
        "supported_under_the_bootstrap_interval_standard"
    )
    assert "inconclusive" in _inferential_status([equivalent, inconclusive])
    assert "unsupported" in _inferential_status([inconclusive, exceeds])
    # A single demonstrated exceedance outranks any number of open estimands.
    assert "unsupported" in _inferential_status([exceeds, inconclusive, inconclusive])


def test_relative_change_draws_pair_index_wise_and_truncate_to_the_shorter_run() -> None:
    """The ratio pairing must reuse no draw and must follow the difference rule."""
    current = np.array([2.0, 3.0, 4.0])
    reference = np.array([1.0, 2.0])

    paired = relative_change_draws(current, reference)

    assert paired.size == 2
    assert paired == pytest.approx([1.0, 0.5])
    assert paired_difference_draws(current, reference).size == paired.size


def _synthetic_window(months: int, seed: int) -> tuple[pd.DataFrame, list[str]]:
    """Build a panel carrying one extreme-decile pair for every registered family."""
    rng = np.random.default_rng(seed)
    level = np.cumsum(rng.normal(0.0, 0.3, size=months)) + 5.0
    market = rng.normal(0.5, 4.0, size=months)
    columns = [
        f"portfolio_excess_return__{family}__decile_{decile}"
        for family in FAMILY_MEMBERS
        for decile in ("01", "10")
    ]
    innovation = level - np.concatenate([[level[0]], level[:-1]])
    data: dict[str, object] = {
        f"short_rate_level__{RATE}": level,
        "market_excess_return": market,
    }
    for position, column in enumerate(columns):
        loading = 0.4 + 0.1 * position
        data[column] = (
            0.2
            + loading * market
            + (0.5 - 0.1 * position) * innovation
            + rng.normal(0.0, 1.0, months)
        )
    panel = pd.DataFrame(data, index=pd.period_range("2000-01", periods=months, freq="M"))
    return panel, columns


def test_the_joint_bootstrap_pairs_two_re_estimated_windows_into_one_comparison() -> None:
    """Both windows must be re-estimated per draw and differenced draw by draw.

    This is the end-to-end shape of the temporal interval: two independent
    window bootstraps, collapsed to the per-family extreme-decile spread, then
    paired. The point change the interval is built around has to be the same
    quantity the registered magnitude gate compares, so it is checked against a
    spread difference computed outside the bootstrap.
    """
    first, columns = _synthetic_window(120, seed=11)
    second, _ = _synthetic_window(96, seed=12)

    results = []
    for label, panel, seed in (("first", first, 101), ("second", second, 202)):
        level = panel[f"short_rate_level__{RATE}"].to_numpy(dtype=float)
        lagged = np.concatenate([[level[0] - 0.1], level[:-1]])
        design = np.column_stack([np.ones(level.size), lagged])
        innovation = level - design @ np.linalg.lstsq(design, level, rcond=None)[0]
        bootstrap, selection = window_bootstrap(
            window_id=label,
            panel=panel,
            columns=columns,
            lagged=lagged,
            innovation=innovation,
            seed=seed,
        )
        results.append((bootstrap, selection))

    first_bootstrap, first_selection = results[0]
    second_bootstrap, _ = results[1]

    assert first_selection.block_length >= 2
    assert first_bootstrap.months == 120
    assert second_bootstrap.months == 96
    # Every draw solved a full re-estimation, so the RMSE distribution is not
    # degenerate at the point estimate.
    assert first_bootstrap.statistic_draws["rmse"].std() > 0.0

    first_spreads = spread_draws(first_bootstrap, columns)
    second_spreads = spread_draws(second_bootstrap, columns)
    assert set(first_spreads) == set(FAMILY_MEMBERS)

    pairs = _spread_pairs(columns)
    for family, (low, high) in pairs.items():
        expected = first_bootstrap.premium_draws[:, high] - first_bootstrap.premium_draws[:, low]
        assert first_spreads[family] == pytest.approx(expected)

    family = next(iter(FAMILY_MEMBERS))
    low, high = pairs[family]
    point_change = float(
        (first_bootstrap.point_premia[high] - first_bootstrap.point_premia[low])
        - (second_bootstrap.point_premia[high] - second_bootstrap.point_premia[low])
    )
    outcome = classify_equivalence(
        estimand=f"temporal_fitted_premium_spread_change__{family}",
        point_change=point_change,
        change_draws=paired_difference_draws(first_spreads[family], second_spreads[family]),
        bound=FITTED_PREMIUM_BOUND,
    )

    assert outcome.decision_category in {
        "equivalent_within_bound",
        "difference_exceeds_bound",
        "inconclusive",
    }
    assert outcome.lower_90 <= outcome.upper_90
    assert outcome.lower_95 <= outcome.lower_90
    assert outcome.upper_95 >= outcome.upper_90


def test_standardized_dispersion_share_is_computed_from_the_window_it_describes() -> None:
    """The H4a share must follow the betas and factor scales it is handed.

    The diagnostic previously carried two literal constants, so a rebuild on new
    data would have reported the old window. Scaling the rate innovation scales
    the share by construction, which a hard-coded value cannot do.
    """
    betas = pd.DataFrame({"RM": [1.0, 0.5, 1.5], "FFR_innovation": [0.4, -0.2, 0.1]})
    market = np.array([1.0, -2.0, 3.0, -1.0])
    innovation = np.array([0.5, -0.5, 1.0, 0.0])

    share = standardized_dispersion_share(betas, market=market, innovation=innovation)
    expected = float(np.std(betas["FFR_innovation"] * innovation.std(ddof=1), ddof=1)) / float(
        np.std(betas["RM"] * market.std(ddof=1), ddof=1)
    )

    assert share == pytest.approx(expected)
    assert standardized_dispersion_share(
        betas, market=market, innovation=innovation * 2.0
    ) == pytest.approx(2.0 * share)


def test_standardized_dispersion_share_refuses_an_undefined_ratio() -> None:
    """A zero market dispersion leaves the share undefined rather than infinite."""
    betas = pd.DataFrame({"RM": [1.0, 1.0, 1.0], "FFR_innovation": [0.4, -0.2, 0.1]})

    with pytest.raises(ValueError, match="market-exposure dispersion is zero"):
        standardized_dispersion_share(
            betas,
            market=np.array([1.0, -2.0, 3.0]),
            innovation=np.array([0.5, -0.5, 1.0]),
        )


def test_the_h2_artifact_carries_an_inferential_status_beside_the_frozen_verdict() -> None:
    """The shipped artifact must record both classifications, and keep them apart.

    The registered verdict is the point-estimate rule and must stay under
    ``classification``. The interval classification is recorded separately, per
    estimand, with a three-way decision so that the registry's ``inconclusive``
    outcome is reachable from the artifact rather than only in principle.
    """
    stability = json.loads(H2_STABILITY.read_text(encoding="utf-8"))

    assert stability["classification"] in {
        "post_publication_compatibility_supported",
        "post_publication_compatibility_unsupported",
    }
    assert stability["classification_role"] == "registered_confirmatory_point_estimate_rule"

    inferential = stability["supplementary_inferential_classification"]
    assert inferential["status"].endswith("_under_the_bootstrap_interval_standard")
    assert inferential["status"] != stability["classification"]
    assert inferential["rule"] == "tost_5pct_90pct_interval"
    assert inferential["draws"] == 10_000

    estimands = inferential["estimands"]
    expected = {f"temporal_fitted_premium_spread_change__{family}" for family in FAMILY_MEMBERS}
    assert expected | {"temporal_rmse_relative_change"} == set(estimands)
    for name, record in estimands.items():
        assert record["decision_category"] in {
            "equivalent_within_bound",
            "difference_exceeds_bound",
            "inconclusive",
        }
        assert record["lower_90"] <= record["upper_90"]
        assert record["bound"] == (
            0.10 if name == "temporal_rmse_relative_change" else FITTED_PREMIUM_BOUND
        )
    assert estimands["temporal_rmse_relative_change"]["one_sided_bound"] is True

    # The reduction rule the artifact reports has to be the one implemented.
    categories = [record["decision_category"] for record in estimands.values()]
    if all(record["tost_5pct_90pct_interval_passes"] for record in estimands.values()):
        assert "supported_under" in inferential["status"]
    elif "difference_exceeds_bound" in categories:
        assert "unsupported_under" in inferential["status"]
    else:
        assert "inconclusive_under" in inferential["status"]

    for window in inferential["windows"].values():
        assert window["successful_draws"] > 0
        assert 2 <= window["block_length"] <= 24


def test_the_h2_artifact_reports_both_sign_vintages_and_names_the_registered_one() -> None:
    """The sign gate spans two vintages, so the artifact must say which it uses.

    The registered gate compares the refitted extension with the locked
    baseline; the same-vintage comparison against the revised history is
    reported beside it and decides nothing. Recording only one of the two left
    the manuscript's vintage-isolation claim unverifiable from the artifact.
    """
    stability = json.loads(H2_STABILITY.read_text(encoding="utf-8"))
    sign_gate = stability["sign_gate_vintage"]

    assert sign_gate["registered_gate_compares_against"] == "locked_baseline"
    assert sign_gate["same_vintage_gate_compares_against"] == "revised_history"
    assert sign_gate["registered_gate_passes"] == stability["gates"]["sign_compatibility"]
    assert sign_gate["gates_agree"] == (
        sign_gate["registered_gate_passes"] == sign_gate["same_vintage_gate_passes"]
    )


def test_the_h2_artifact_states_what_the_shared_vintage_does_and_does_not_achieve() -> None:
    """The artifact must not deny that revised values enter the comparison.

    They are the quantity the extension is measured against. What the shared
    vintage achieves is holding the revision contribution common to both sides
    so that it differences out, which is a different claim from excluding it.
    """
    stability = json.loads(H2_STABILITY.read_text(encoding="utf-8"))
    isolation = stability["vintage_isolation"]

    assert "revised historical values do enter the comparison" in isolation
    assert "cannot enter the temporal verdict" not in isolation
    assert "differences out" in isolation


def test_the_h2_dispersion_note_does_not_claim_the_factor_is_well_identified() -> None:
    """H4a dispersion is a registered gate, not a measure of exposure reliability.

    The artifact previously read the extension's higher share as evidence that
    the temporal result was not driven by a weak factor. The permitted claim is
    only that the extension does not fail the registered criterion.
    """
    stability = json.loads(H2_STABILITY.read_text(encoding="utf-8"))
    dispersion = stability["standardized_rate_exposure_dispersion_share"]

    assert dispersion["floor"] == 0.10
    assert dispersion["refitted_extension"] >= dispersion["floor"]
    assert "does not fail the registered H4a dispersion criterion" in dispersion["note"]
    assert "not attributable to a weakly identified factor" not in dispersion["note"]
    # Recomputed rather than pinned: the stale literals were 0.2540 and 0.5800,
    # which the live values agree with only to four decimal places.
    assert dispersion["locked_baseline"] != 0.2540
    assert dispersion["refitted_extension"] != 0.5800
