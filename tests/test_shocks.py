from pathlib import Path

import pandas as pd
import pytest

from short_rate_anomaly_regimes.shocks.decomposition import (
    ShockDecompositionBuild,
    ShockIdentificationRule,
    aggregate_monthly_shocks,
    asset_pricing_factor_design,
    build_shock_decomposition,
    compare_shock_spanning,
    decompose_high_frequency_surprises,
    enforce_policy_language_rule,
    reproduction_audit,
    source_study_summary_statistics,
    write_shock_outputs,
)


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_time": [
                "2020-01-29 14:00",
                "2020-03-15 17:00",
                "2020-03-23 08:00",
                "2020-05-01 14:00",
            ],
            "rate_surprise": [0.02, -0.03, 0.01, 0.02],
            "equity_surprise": [-0.01, -0.04, 0.0, 0.03],
        }
    )


def test_decompose_high_frequency_surprises_preserves_components() -> None:
    shocks = decompose_high_frequency_surprises(
        _events(),
        rate_surprise_column="rate_surprise",
        equity_surprise_column="equity_surprise",
        event_window_minutes=30,
    )

    assert shocks.loc[0, "policy_shock"] == pytest.approx(0.02)
    assert shocks.loc[1, "central_bank_information"] == pytest.approx(-0.03)
    assert shocks.loc[2, "ambiguous_rate_surprise"] == pytest.approx(0.01)
    assert shocks["component_identity_error"].abs().max() == pytest.approx(0.0)
    assert shocks["month"].tolist() == ["2020-01", "2020-03", "2020-03", "2020-05"]


def test_decomposition_validation_guards() -> None:
    with pytest.raises(ValueError, match="Unsupported"):
        decompose_high_frequency_surprises(
            _events(),
            rate_surprise_column="rate_surprise",
            equity_surprise_column="equity_surprise",
            identification="undocumented",
        )
    with pytest.raises(ValueError, match="positive"):
        decompose_high_frequency_surprises(
            _events(),
            rate_surprise_column="rate_surprise",
            equity_surprise_column="equity_surprise",
            event_window_minutes=0,
        )
    with pytest.raises(ValueError, match="missing columns"):
        decompose_high_frequency_surprises(
            _events().drop(columns=["rate_surprise"]),
            rate_surprise_column="rate_surprise",
            equity_surprise_column="equity_surprise",
        )
    with pytest.raises(ValueError, match="cannot be empty"):
        decompose_high_frequency_surprises(
            _events().iloc[0:0],
            rate_surprise_column="rate_surprise",
            equity_surprise_column="equity_surprise",
        )


def test_aggregate_monthly_shocks_explicitly_represents_no_meeting_months() -> None:
    shocks = decompose_high_frequency_surprises(
        _events(),
        rate_surprise_column="rate_surprise",
        equity_surprise_column="equity_surprise",
    )

    monthly = aggregate_monthly_shocks(
        shocks,
        start_month="2020-01",
        end_month="2020-05",
        aggregation="monthly_sum",
    )
    monthly_mean = aggregate_monthly_shocks(
        shocks,
        start_month="2020-01",
        end_month="2020-05",
        aggregation="monthly_mean",
    )
    monthly_abs = aggregate_monthly_shocks(
        shocks,
        start_month="2020-01",
        end_month="2020-05",
        aggregation="monthly_abs_sum",
    )

    assert monthly.loc[pd.Timestamp("2020-02-29"), "meeting_count"] == 0
    assert monthly.loc[pd.Timestamp("2020-03-31"), "multiple_meetings"]
    assert monthly.loc[pd.Timestamp("2020-03-31"), "ambiguous_events"] == 1
    assert monthly_mean.loc[pd.Timestamp("2020-03-31"), "total_rate_surprise"] == pytest.approx(
        -0.01
    )
    assert monthly_abs.loc[pd.Timestamp("2020-03-31"), "total_rate_surprise"] == pytest.approx(0.04)


def test_monthly_aggregation_validation_guards() -> None:
    shocks = decompose_high_frequency_surprises(
        _events(),
        rate_surprise_column="rate_surprise",
        equity_surprise_column="equity_surprise",
    )
    with pytest.raises(ValueError, match="missing columns"):
        aggregate_monthly_shocks(
            shocks.drop(columns=["policy_shock"]),
            start_month="2020-01",
            end_month="2020-05",
        )
    with pytest.raises(ValueError, match="Unsupported"):
        aggregate_monthly_shocks(
            shocks,
            start_month="2020-01",
            end_month="2020-05",
            aggregation="bad_rule",  # type: ignore[arg-type]
        )


def test_summary_reproduction_audit_design_and_language_rule() -> None:
    shocks = decompose_high_frequency_surprises(
        _events(),
        rate_surprise_column="rate_surprise",
        equity_surprise_column="equity_surprise",
    )
    summary = source_study_summary_statistics(shocks)
    target = summary.rename(columns={"value": "target_value"})
    target["tolerance"] = 0.0
    audit = reproduction_audit(summary, target)
    design = asset_pricing_factor_design()

    assert set(audit["status"]) == {"reproduced"}
    assert "policy_shock" in ",".join(design["factor_columns"])
    enforce_policy_language_rule(pd.Series(["AR rate innovation", "identified policy shock"]))
    with pytest.raises(ValueError, match="Only identified"):
        enforce_policy_language_rule(pd.Series(["AR residual policy shock"]))
    with pytest.raises(ValueError, match="Generated statistics"):
        reproduction_audit(pd.DataFrame({"value": [1.0]}), target)
    with pytest.raises(ValueError, match="Target statistics"):
        reproduction_audit(summary, pd.DataFrame({"statistic": ["event_count"]}))


def test_build_shock_decomposition_and_spanning_table() -> None:
    rule = ShockIdentificationRule(
        dataset_id="fixture",
        method="poor_mans_sign_restriction",
        event_window_minutes=30,
        rate_surprise_column="rate_surprise",
        equity_surprise_column="equity_surprise",
    )

    build = build_shock_decomposition(
        _events(),
        rule=rule,
        start_month="2020-01",
        end_month="2020-05",
        aggregation="monthly_sum",
    )
    spanning = compare_shock_spanning(build.monthly_shocks)

    assert isinstance(build, ShockDecompositionBuild)
    assert build.monthly_shocks.shape[0] == 5
    assert {"factor", "total_rate_surprise"} <= set(spanning.columns)
    with pytest.raises(ValueError, match="missing columns"):
        compare_shock_spanning(build.monthly_shocks.drop(columns=["policy_shock"]))


def test_write_shock_outputs(tmp_path: Path) -> None:
    rule = ShockIdentificationRule(
        dataset_id="fixture",
        method="poor_mans_sign_restriction",
        event_window_minutes=30,
        rate_surprise_column="rate_surprise",
        equity_surprise_column="equity_surprise",
    )
    build = build_shock_decomposition(
        _events(),
        rule=rule,
        start_month="2020-01",
        end_month="2020-05",
        aggregation="monthly_sum",
    )

    write_shock_outputs(
        build=build,
        diagnostics_dir=tmp_path / "diagnostics",
        table_dir=tmp_path / "tables",
        monthly_path=tmp_path / "monthly.parquet",
        report_path=tmp_path / "report.md",
        rule=rule,
    )

    assert (tmp_path / "monthly.parquet").is_file()
    assert (tmp_path / "tables" / "asset_pricing_design.csv").is_file()
    assert "AR residual remains a rate innovation" in (tmp_path / "report.md").read_text(
        encoding="utf-8"
    )
