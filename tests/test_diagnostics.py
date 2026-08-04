import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.models.diagnostics import (
    MAX_SPANNING_R_SQUARED,
    MIN_SPANNING_RESIDUAL_RATIO,
    REGISTERED_SPANNING_REGRESSORS,
    SPANNING_DECISION_TOLERANCE,
    H4aIdentificationConclusion,
    RobustnessDecisionRules,
    WeakFactorReport,
    classify_h4a_identification_strength,
    classify_robustness,
    economic_diagnostics,
    factor_redundancy_diagnostics,
    holm_correction,
    rate_spanning_criterion,
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
    assert report.standardized_exposure_dispersion["rate"] > 0
    assert compact["rank"] == 2
    assert compact["standardized_exposure_dispersion_rate"] > 0
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


def test_factor_redundancy_diagnostics_flags_redundant_factor() -> None:
    dates = pd.date_range("2020-01-31", periods=8, freq="ME")
    factors = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6, 7, 8],
            "b": [2, 4, 6, 8, 10, 12, 14, 16],
        },
        index=dates,
    )

    redundancy = factor_redundancy_diagnostics(factors)

    assert redundancy["numerically_redundant"].all()


def test_factor_redundancy_diagnostics_single_factor_returns_empty_table() -> None:
    redundancy = factor_redundancy_diagnostics(_factors()[["mkt"]])

    assert redundancy.empty
    assert redundancy.columns.tolist() == [
        "factor",
        "r_squared",
        "residual_std",
        "numerically_redundant",
    ]


def _spanning_inputs(
    target_r2: float,
    *,
    names: tuple[str, ...] = ("Mkt-RF", "SMB", "HML"),
    n_months: int = 120,
    seed: int = 7,
) -> tuple[pd.Series, pd.DataFrame]:
    """Build a rate innovation whose in-sample spanning R-squared equals target_r2."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("1990-01-31", periods=n_months, freq="ME")
    regressors = rng.normal(size=(n_months, len(names)))
    design = np.column_stack([np.ones(n_months), regressors])
    spanned_part = regressors @ np.linspace(1.0, 2.0, len(names))
    spanned_part = spanned_part - spanned_part.mean()
    raw = rng.normal(size=n_months)
    coefficients, *_ = np.linalg.lstsq(design, raw, rcond=None)
    orthogonal_part = raw - design @ coefficients
    scale = (
        spanned_part.std(ddof=1)
        * math.sqrt((1.0 - target_r2) / target_r2)
        / orthogonal_part.std(ddof=1)
    )
    rate = pd.Series(spanned_part + scale * orthogonal_part, index=index, name="rate_innovation")
    return rate, pd.DataFrame(regressors, index=index, columns=list(names))


def test_rate_spanning_criterion_fails_clearly_spanned_factor() -> None:
    rate, comparators = _spanning_inputs(0.98)

    result = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)

    assert result.r2_span == pytest.approx(0.98)
    assert result.r2_span > MAX_SPANNING_R_SQUARED
    assert result.s_span < MIN_SPANNING_RESIDUAL_RATIO
    assert not result.passes
    assert not result.passes_residual_ratio_form
    assert result.n_months == 120
    assert result.executed_regressors == ("Mkt-RF", "SMB", "HML")


def test_rate_spanning_criterion_passes_clearly_independent_factor() -> None:
    rate, comparators = _spanning_inputs(0.05)

    result = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)

    assert result.r2_span == pytest.approx(0.05)
    assert result.s_span == pytest.approx(math.sqrt(1.0 - result.r2_span))
    assert result.passes
    assert result.passes_residual_ratio_form
    assert result.market_only_regressors == ("Mkt-RF",)
    assert result.market_only_r2_span <= result.r2_span
    assert result.market_only_s_span == pytest.approx(math.sqrt(1.0 - result.market_only_r2_span))


def test_spanning_threshold_forms_are_consistent_to_full_precision() -> None:
    assert abs(MIN_SPANNING_RESIDUAL_RATIO - math.sqrt(0.10)) == 0.0
    assert MIN_SPANNING_RESIDUAL_RATIO > 0.3162
    assert abs(MIN_SPANNING_RESIDUAL_RATIO**2 - (1.0 - MAX_SPANNING_R_SQUARED)) <= 1e-15


@pytest.mark.parametrize("target_r2", [0.8999, 0.90, 0.9001])
def test_rate_spanning_criterion_boundary_agrees_in_both_forms(target_r2: float) -> None:
    rate, comparators = _spanning_inputs(target_r2)

    result = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)

    assert result.r2_span == pytest.approx(target_r2)
    assert result.s_span == pytest.approx(math.sqrt(1.0 - result.r2_span))
    assert result.passes == result.passes_residual_ratio_form
    assert result.passes == (result.r2_span <= MAX_SPANNING_R_SQUARED + SPANNING_DECISION_TOLERANCE)
    assert result.passes == (
        result.s_span >= MIN_SPANNING_RESIDUAL_RATIO - SPANNING_DECISION_TOLERANCE
    )
    if target_r2 == 0.8999:
        assert result.passes
    if target_r2 == 0.9001:
        assert not result.passes
    if target_r2 != 0.90:
        assert result.passes == (result.r2_span <= MAX_SPANNING_R_SQUARED)
        assert result.passes == (result.s_span >= MIN_SPANNING_RESIDUAL_RATIO)


def test_exact_boundary_is_resolved_by_the_declared_tolerance() -> None:
    rate, comparators = _spanning_inputs(0.90)

    result = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)

    assert result.r2_span == 0.90
    assert result.s_span < MIN_SPANNING_RESIDUAL_RATIO
    assert MIN_SPANNING_RESIDUAL_RATIO - result.s_span < 1e-15
    assert result.passes
    assert result.passes_residual_ratio_form


def test_rate_spanning_criterion_records_executed_regressors_when_factors_absent() -> None:
    rate, comparators = _spanning_inputs(0.4, names=("ROE", "HML", "Mkt-RF"))
    comparators["UNREGISTERED"] = comparators["HML"].to_numpy() * -1.0
    scrambled = comparators.loc[:, ["UNREGISTERED", "ROE", "HML", "Mkt-RF"]]

    result = rate_spanning_criterion(rate_innovation=rate, comparator_factors=scrambled)

    assert result.executed_regressors == ("Mkt-RF", "HML", "ROE")
    assert [
        name for name in REGISTERED_SPANNING_REGRESSORS if name in result.executed_regressors
    ] == list(result.executed_regressors)
    assert "UNREGISTERED" not in result.executed_regressors
    assert set(REGISTERED_SPANNING_REGRESSORS) - set(result.executed_regressors)


def test_rate_spanning_criterion_is_scale_invariant() -> None:
    rate, comparators = _spanning_inputs(0.95)

    baseline = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)
    rescaled = rate_spanning_criterion(rate_innovation=rate * 100.0, comparator_factors=comparators)

    assert rescaled.r2_span == pytest.approx(baseline.r2_span)
    assert rescaled.s_span == pytest.approx(baseline.s_span)
    assert rescaled.market_only_r2_span == pytest.approx(baseline.market_only_r2_span)
    assert rescaled.market_only_s_span == pytest.approx(baseline.market_only_s_span)
    assert rescaled.passes == baseline.passes
    assert not baseline.passes


def test_rate_spanning_criterion_rejects_invalid_inputs() -> None:
    rate, comparators = _spanning_inputs(0.5)

    with pytest.raises(ValueError, match="cannot be empty"):
        rate_spanning_criterion(
            rate_innovation=pd.Series(dtype=float), comparator_factors=comparators
        )
    with pytest.raises(ValueError, match="cannot be empty"):
        rate_spanning_criterion(rate_innovation=rate, comparator_factors=pd.DataFrame())
    with pytest.raises(ValueError, match="no registered spanning regressor"):
        rate_spanning_criterion(
            rate_innovation=rate,
            comparator_factors=comparators.rename(columns=lambda name: f"x_{name}"),
        )
    with pytest.raises(ValueError, match="missing 'Mkt-RF'"):
        rate_spanning_criterion(
            rate_innovation=rate, comparator_factors=comparators.drop(columns=["Mkt-RF"])
        )
    with pytest.raises(ValueError, match="insufficient"):
        rate_spanning_criterion(
            rate_innovation=rate.iloc[:4], comparator_factors=comparators.iloc[:4]
        )


def _h4a_conclusion(target_r2: float) -> tuple[WeakFactorReport, H4aIdentificationConclusion]:
    report = weak_factor_report(betas=_betas(), factors=_factors())
    rate, comparators = _spanning_inputs(target_r2)
    spanning = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)
    conclusion = classify_h4a_identification_strength(
        weak_report=report,
        spanning=spanning,
        rate_factor="rate",
        market_factor="mkt",
    )
    return report, conclusion


def test_classify_h4a_identification_strength_consumes_the_spanning_gate() -> None:
    _, passing = _h4a_conclusion(0.20)
    _, failing = _h4a_conclusion(0.99)

    assert passing.passes
    assert passing.gate_failures == ()
    assert passing.rank_gate_passes
    assert passing.standardized_dispersion_passes
    assert passing.standardized_dispersion_share > 0.10
    assert not failing.passes
    assert failing.gate_failures == ("rate_spanning_criterion",)
    assert failing.rank_gate_passes
    assert failing.standardized_dispersion_passes


def test_classify_h4a_identification_strength_rejects_unknown_factor_names() -> None:
    report = weak_factor_report(betas=_betas(), factors=_factors())
    rate, comparators = _spanning_inputs(0.2)
    spanning = rate_spanning_criterion(rate_innovation=rate, comparator_factors=comparators)

    with pytest.raises(ValueError, match="missing factors"):
        classify_h4a_identification_strength(
            weak_report=report, spanning=spanning, rate_factor="absent", market_factor="mkt"
        )


def test_robustness_cannot_be_robust_when_the_spanning_gate_fails() -> None:
    report, failing = _h4a_conclusion(0.99)
    stable = pd.DataFrame(
        {
            "sign_reversal": [False],
            "risk_price_change": [0.01],
            "rmse_change": [0.01],
            "mae_change": [0.01],
            "max_alpha_change": [0.01],
        }
    )

    assert classify_robustness(report, stable).verdict == "robust"
    gated = classify_robustness(report, stable, h4a=failing)
    assert gated.verdict == "unidentified"
    assert "rate_spanning_criterion" in gated.rule_failures


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


def test_write_robustness_outputs_stores_executed_spanning_regressors(tmp_path: Path) -> None:
    report, failing = _h4a_conclusion(0.99)
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
    diagnostics_path = tmp_path / "diagnostics" / "weak.json"

    write_robustness_outputs(
        weak_report=report,
        specification_results=specs,
        economic_results=economic,
        conclusion=classify_robustness(report, economic, h4a=failing),
        diagnostics_path=diagnostics_path,
        table_path=tmp_path / "tables" / "specs.csv",
        report_path=tmp_path / "reports" / "robustness.md",
        h4a=failing,
    )

    payload = json.loads(diagnostics_path.read_text(encoding="utf-8"))
    spanning = payload["h4a_identification_strength"]["rate_spanning_criterion"]
    assert spanning["executed_regressors"] == ["Mkt-RF", "SMB", "HML"]
    assert spanning["market_only_regressors"] == ["Mkt-RF"]
    assert spanning["passes"] is False
    assert spanning["n_months"] == 120
    assert payload["classification"]["verdict"] == "unidentified"
