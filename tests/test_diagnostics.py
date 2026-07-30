from pathlib import Path

import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.diagnostics import (
    RobustnessDecisionRules,
    classify_robustness,
    economic_diagnostics,
    factor_spanning_tests,
    holm_correction,
    specification_table,
    weak_factor_diagnostics,
    weak_factor_report,
    write_robustness_outputs,
)


def _betas() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "mkt": [0.8, 1.0, 1.2, 1.4, 0.7],
            "rate": [-0.4, -0.1, 0.2, 0.6, -0.7],
        },
        index=["a", "b", "c", "d", "e"],
    )


def _factors() -> pd.DataFrame:
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    return pd.DataFrame(
        {
            "mkt": [-0.03, -0.01, 0.0, 0.02, 0.04, 0.01, -0.02, 0.03],
            "rate": [0.01, 0.02, -0.01, 0.0, 0.03, -0.02, 0.01, 0.02],
        },
        index=dates,
    )


def test_weak_factor_report_contains_rank_singular_values_and_dispersion() -> None:
    report = weak_factor_report(betas=_betas(), factors=_factors())
    compact = weak_factor_diagnostics(betas=_betas(), factors=_factors())

    assert report.rank == 2
    assert report.n_assets == 5
    assert report.n_factors == 2
    assert len(report.singular_values) == 2
    assert report.beta_dispersion["mkt"] > 0
    assert compact["rank"] == 2
    assert not bool(compact["unidentified"])


def test_weak_factor_report_rejects_empty_or_misaligned_inputs() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        weak_factor_report(betas=pd.DataFrame(), factors=_factors())
    with pytest.raises(ValueError, match="cannot be empty"):
        weak_factor_report(betas=_betas(), factors=pd.DataFrame())
    with pytest.raises(ValueError, match="missing beta columns"):
        weak_factor_report(betas=_betas(), factors=_factors().drop(columns=["rate"]))


def test_weak_factor_report_flags_irrelevant_factor() -> None:
    betas = pd.DataFrame({"mkt": [1.0, 1.1, 0.9], "flat": [0.2, 0.2, 0.2]})
    factors = pd.DataFrame(
        {
            "mkt": [0.01, 0.02, -0.01, 0.0],
            "flat": [0.01, 0.01, 0.01, 0.01],
        },
        index=pd.date_range("2020-01-31", periods=4, freq="ME"),
    )

    report = weak_factor_report(betas=betas, factors=factors)

    assert "flat" in report.irrelevant_factors
    assert report.unidentified


def test_factor_spanning_tests_flags_redundant_factor() -> None:
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    factors = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, 7, 8],
            "b": [2, 4, 6, 8, 10, 12, 14, 16],
        },
        index=dates,
    )

    spanning = factor_spanning_tests(factors)

    assert spanning["spanned"].all()


def test_factor_spanning_tests_single_factor_returns_empty_table() -> None:
    spanning = factor_spanning_tests(_factors()[["mkt"]])

    assert spanning.empty
    assert spanning.columns.tolist() == ["factor", "r_squared", "residual_std", "spanned"]


def test_holm_correction_and_specification_table() -> None:
    p_values = pd.Series({"a": 0.01, "b": 0.04, "c": 0.2}, name="rate_definition")
    corrected = holm_correction(p_values)
    specs = pd.DataFrame(
        {
            "family": ["rate_definition", "rate_definition", "covariance_bootstrap"],
            "specification": ["a", "b", "c"],
            "p_value": [0.01, 0.04, 0.03],
        }
    )

    table = specification_table(specs)

    assert corrected.loc["a", "holm_p_value"] == pytest.approx(0.03)
    assert "holm_p_value" in table.columns
    with pytest.raises(ValueError, match="cannot be empty"):
        holm_correction(pd.Series(dtype=float))


def test_specification_table_rejects_missing_columns() -> None:
    with pytest.raises(ValueError, match="Missing family"):
        specification_table(pd.DataFrame({"p_value": [0.1]}))
    with pytest.raises(ValueError, match="Missing p-value"):
        specification_table(pd.DataFrame({"family": ["rate_definition"]}))


def test_economic_diagnostics_flags_sign_reversal_and_material_change() -> None:
    baseline = pd.Series(
        {
            "risk_price": 0.04,
            "rmse": 0.02,
            "mae": 0.015,
            "max_alpha": 0.03,
            "explained_spread": 0.5,
        }
    )
    alternatives = pd.DataFrame(
        {
            "risk_price": [-0.02, 0.041],
            "rmse": [0.04, 0.021],
            "mae": [0.03, 0.016],
            "max_alpha": [0.07, 0.031],
            "explained_spread": [0.2, 0.51],
        },
        index=["fragile_spec", "stable_spec"],
    )

    table = economic_diagnostics(baseline, alternatives)

    assert table.loc[0, "sign_reversal"]
    assert table.loc[0, "material_change"]
    assert not bool(table.loc[1, "sign_reversal"])


def test_economic_diagnostics_rejects_missing_metrics() -> None:
    with pytest.raises(ValueError, match="Baseline is missing"):
        economic_diagnostics(pd.Series({"risk_price": 0.1}), pd.DataFrame())


def test_classify_robustness_verdicts() -> None:
    report = weak_factor_report(betas=_betas(), factors=_factors())
    stable = pd.DataFrame(
        {
            "sign_reversal": [False],
            "risk_price_change": [0.01],
            "rmse_change": [0.01],
            "mae_change": [0.01],
            "max_alpha_change": [0.01],
        }
    )
    fragile = pd.DataFrame(
        {
            "sign_reversal": [True],
            "risk_price_change": [0.5],
            "rmse_change": [0.5],
            "mae_change": [0.5],
            "max_alpha_change": [0.5],
        }
    )

    assert classify_robustness(report, stable).verdict == "robust"
    assert classify_robustness(report, fragile).verdict == "fragile"

    unidentified_report = weak_factor_report(
        betas=pd.DataFrame({"mkt": [1.0, 1.0], "flat": [0.2, 0.2]}),
        factors=pd.DataFrame(
            {"mkt": [0.01, 0.02, 0.03], "flat": [0.01, 0.01, 0.01]},
            index=pd.date_range("2020-01-31", periods=3, freq="ME"),
        ),
    )
    assert classify_robustness(unidentified_report, stable).verdict == "unidentified"

    conditional = classify_robustness(
        report,
        fragile.assign(rmse_change=0.0, mae_change=0.0, max_alpha_change=0.0),
        rules=RobustnessDecisionRules(max_material_risk_price_change=0.25),
    )
    assert conditional.verdict == "conditionally_robust"


def test_write_robustness_outputs(tmp_path: Path) -> None:
    report = weak_factor_report(betas=_betas(), factors=_factors())
    specs = pd.DataFrame(
        {
            "family": ["rate_definition"],
            "specification": ["baseline"],
            "p_value": [0.5],
            "holm_p_value": [0.5],
        }
    )
    economic = pd.DataFrame(
        {
            "sign_reversal": [False],
            "risk_price_change": [0.01],
            "rmse_change": [0.01],
            "mae_change": [0.01],
            "max_alpha_change": [0.01],
        }
    )
    conclusion = classify_robustness(report, economic)

    write_robustness_outputs(
        weak_report=report,
        specification_results=specs,
        economic_results=economic,
        conclusion=conclusion,
        diagnostics_path=tmp_path / "diagnostics" / "weak.json",
        table_path=tmp_path / "tables" / "specs.csv",
        report_path=tmp_path / "reports" / "robustness.md",
    )

    assert (tmp_path / "diagnostics" / "weak.json").is_file()
    assert (tmp_path / "tables" / "specs.csv").is_file()
    assert "Verdict" in (tmp_path / "reports" / "robustness.md").read_text(encoding="utf-8")
