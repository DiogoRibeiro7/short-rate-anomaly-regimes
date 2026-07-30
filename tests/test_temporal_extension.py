from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

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
