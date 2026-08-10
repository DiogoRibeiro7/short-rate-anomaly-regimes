"""Tests for generated reports rendered from machine-readable artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from short_rate_anomaly_regimes.extensions.temporal import (
    TemporalFreeze,
    render_temporal_evidence_report,
    write_temporal_evidence_report,
)
from short_rate_anomaly_regimes.models.diagnostics import (
    render_robustness_evidence_report,
    write_blocked_robustness_report,
    write_robustness_evidence_report,
)
from short_rate_anomaly_regimes.regimes.stability import (
    render_regime_evidence_report,
    write_regime_evidence_report,
)
from short_rate_anomaly_regimes.reporting.artifact_evidence import (
    artifact_field,
    dataframe_table,
    format_sequence,
    format_value,
    load_json_artifact,
    markdown_table,
    missing_inputs,
    report_verdict,
)
from short_rate_anomaly_regimes.reporting.manuscript import (
    render_manuscript_output_report,
    write_manuscript_output_report,
)

REGIME_CLASSIFICATION = "regime_stability_unsupported_under_the_registered_equivalence_standard"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _equivalence_artifact() -> dict[str, Any]:
    return {
        "classification": REGIME_CLASSIFICATION,
        "classification_basis": "one dimension lies wholly beyond its bound",
        "coverage_note": "the registered floors admit two regimes to a standalone second pass",
        "dimensions_with_a_demonstrated_exceedance": ["rmse_relative_deterioration"],
        "draws": 10000,
        "equivalence_rule": "tost_5pct_90pct_interval",
        "gates": {"rmse_relative_deterioration": False, "dispersion_relative_change": False},
        "global_innovation_sensitivity": {"correlation": 0.998724},
        "hypothesis": "H3",
        "innovation_definition": "within_regime_ar1",
        "max_absolute_point_premium_change": 0.527201,
        "per_portfolio_decision_categories": {"equivalent_within_bound": 26, "inconclusive": 44},
        "portfolios_evaluated": 70,
        "portfolios_failing_the_premium_bound": 44,
        "reference_regime": "conventional_pre_elb",
        "regimes_limited_to_pooled_interactions": ["normalisation"],
        "regimes_with_standalone_second_pass": ["conventional_pre_elb", "elb_qe"],
        "replication_status": "documented_reconstruction",
        "residual_covariance_conditioning": {
            "elb_qe": {
                "excess_months_over_assets": 14,
                "months": 84,
                "residual_covariance_condition_number": 11056.2,
                "smallest_eigenvalue": 0.00366,
                "test_assets": 70,
            }
        },
        "specification_test_caveat": "the chi-square statistic inverts an unstable covariance",
    }


def _pooled_beta_artifact() -> dict[str, Any]:
    return {
        "boundary_sensitivity": {
            "any_conclusion_changed": False,
            "results": [
                {
                    "aggregate_rate_beta_holm_p_value": 0.06537,
                    "aggregate_rate_beta_statistic": 19.435162,
                    "assets_rate_beta_significant_holm": 39,
                    "shift_months": -3,
                    "verdict": "unstable",
                    "verdict_matches_registered_boundaries": True,
                },
                {
                    "aggregate_rate_beta_holm_p_value": 5.079924e-05,
                    "aggregate_rate_beta_statistic": 37.312958,
                    "assets_rate_beta_significant_holm": 26,
                    "shift_months": 0,
                    "verdict": "unstable",
                    "verdict_matches_registered_boundaries": True,
                },
            ],
            "shifts_months": [-3, 0],
        },
        "classification": "unstable",
        "exploratory_break_tests": {
            "evidence_class": "exploratory",
            "hypothesis": "E1",
            "note": "exploratory under hypothesis E1; not a member of the confirmatory family",
            "results": [
                {
                    "break_month": "2015-12",
                    "break_type": "registered_boundary",
                    "p_value": 0.0525845,
                    "statistic": 2.5808434,
                    "test": "chow_known_break",
                },
                {
                    "break_month": "1998-07",
                    "break_number": 1,
                    "break_type": "estimated_unknown_break",
                    "p_value": None,
                    "test": "bai_perron_multiple_breaks",
                },
            ],
            "scope": "equal_weighted_test_assets",
        },
        "hypothesis": "H3",
        "interpretation_note": "Significant regime interactions indicate parameter instability.",
        "joint_equal_weighted_tests": {
            "rate_beta_interactions": {
                "df": 5.0,
                "holm_p_value": 5.079924e-05,
                "p_value": 5.183596e-07,
                "statistic": 37.312958,
            }
        },
        "multiplicity": {"adjustment": "holm", "family": "regime_stability", "tests_adjusted": 142},
        "pooled_interaction_only_regimes": ["pandemic_elb_qe"],
        "replication_status": "documented_reconstruction",
        "sample": {
            "end": "2025-12",
            "months": 648,
            "start": "1972-01",
            "test_assets": 70,
            "vintage": "current_throughout",
        },
        "scope": "pooled_regime_interaction_beta_stability",
        "scope_note": "this artifact covers the pooled beta half of H3 only",
        "significant_tests": ["joint_rate_beta_regime_interactions"],
        "specification": {
            "hac_lags": 6,
            "omitted_baseline_regime": "conventional_pre_elb",
            "regressors": ["RM", "FFR_innovation"],
            "response": "test-asset monthly excess return",
        },
    }


def _temporal_artifact() -> dict[str, Any]:
    return {
        "classification": "post_publication_compatibility_unsupported",
        "frozen_ar_intercept": 0.046256,
        "frozen_ar_slope": 0.990527,
        "gates": {
            "rmse_deterioration_within_10_percent": False,
            "sign_compatibility": False,
        },
        "hypothesis": "H2",
        "lambda_rate": {
            "locked_baseline": -0.698465,
            "refitted_extension": -0.082546,
            "revised_history": -0.697373,
        },
        "replication_status": "documented_reconstruction",
        "rmse_relative_change_vs_locked_baseline": 0.910148,
        "rmse_relative_change_vs_revised_history": 0.889665,
        "sign_gate_vintage": {
            "gates_agree": True,
            "note": "the registered sign gate compares against the locked baseline",
            "registered_gate_compares_against": "locked_baseline",
            "registered_gate_passes": False,
            "same_vintage_gate_compares_against": "revised_history",
            "same_vintage_gate_passes": False,
        },
        "standardized_rate_exposure_dispersion_share": {
            "floor": 0.1,
            "locked_baseline": 0.254,
            "note": "the H4a dispersion gate floor is 0.10",
            "refitted_extension": 0.58,
        },
        "supplementary_inferential_classification": {
            "comparison": "refitted_extension_2014_2025_minus_revised_history_1972_2013",
            "draws": 10000,
            "estimands": {
                "temporal_fitted_premium_spread_change__book_to_market": {
                    "bound": 0.25,
                    "decision_category": "inconclusive",
                    "lower_90": -1.9,
                    "point_change": -0.93,
                    "upper_90": 0.11,
                },
                "temporal_rmse_relative_change": {
                    "bound": 0.1,
                    "decision_category": "difference_exceeds_bound",
                    "lower_90": 0.42,
                    "point_change": 0.91,
                    "upper_90": 1.71,
                },
            },
            "note": "both windows are re-estimated inside every draw",
            "role": "supplementary interval evidence",
            "rule": "tost_5pct_90pct_interval",
            "sensitivity_rule": "strict_95pct_interval_sensitivity",
            "status": "post_publication_compatibility_unsupported_under_the_bootstrap_"
            "interval_standard",
            "status_basis": "at least one estimand has its whole 90 percent interval beyond "
            "its bound",
        },
        "vintage_isolation": "the temporal gates compare vintage-consistent windows",
    }


def _materiality_artifact() -> dict[str, Any]:
    comparison = {
        "classification": "unsupported",
        "comparator_model": "capm",
        "comparison_role": "primary",
        "n_assets": 70,
        "n_gates_passed": 2,
        "n_gates_total": 3,
        "n_months": 504,
        "rmse_relative_reduction__comparison": "relative_reduction_at_least",
        "rmse_relative_reduction__comparator_value": 0.189327,
        "rmse_relative_reduction__observed": 0.469737,
        "rmse_relative_reduction__passed": True,
        "rmse_relative_reduction__threshold": 0.1,
        "rmse_relative_reduction__treatment_value": 0.100393,
    }
    secondary = {
        **comparison,
        "comparator_model": "carhart_4",
        "comparison_role": "secondary_adversarial",
    }
    off_headline = {
        **comparison,
        "classification": "supported",
        "n_assets": 10,
        "rmse_relative_reduction__comparator_value": 0.193039,
        "rmse_relative_reduction__observed": 0.54428,
        "rmse_relative_reduction__treatment_value": 0.087972,
    }
    off_headline_secondary = {
        **off_headline,
        "classification": "unsupported",
        "comparator_model": "fama_french_5",
        "comparison_role": "secondary_adversarial",
        "rmse_relative_reduction__observed": -2.119,
        "rmse_relative_reduction__passed": False,
    }
    return {
        "asset_sets": {
            "all_seven_families_joint": {
                "h1_primary_classification": "unsupported",
                "primary_comparison": {"market_plus_fedfunds_innovation": comparison},
                "secondary_adversarial_comparison": {"market_plus_fedfunds_innovation": secondary},
            },
            "book_to_market": {
                "h1_primary_classification": "supported",
                "primary_comparison": {"market_plus_fedfunds_innovation": off_headline},
                "secondary_adversarial_comparison": {
                    "market_plus_fedfunds_innovation": off_headline_secondary
                },
            },
        },
        "decision_rule": "H1 is supported only if all three primary gates hold jointly.",
        "headline_asset_set": "all_seven_families_joint",
        "hypothesis": "H1",
        "multiplicity": {"status": "No p-value is invented to fill the slot."},
        "primary_comparator": {"model": "capm", "selected_after_observing_rmse": False},
        "replication_status": "documented_reconstruction",
        "thresholds": {"rmse_relative_reduction": {"threshold": 0.1}},
    }


def _identification_artifact() -> dict[str, Any]:
    return {
        "gate_failures": [],
        "hypothesis": "H4a",
        "passes": True,
        "rate_spanning_criterion": {
            "executed_regressors": ["Mkt-RF", "SMB"],
            "n_months": 504,
            "r2_span": 0.055964,
            "s_span": 0.971615,
        },
        "systems": [
            {"portfolio_set": "descriptive_set", "role": "descriptive"},
            {
                "condition_number": 4.159023,
                "n_factors": 2,
                "portfolio_set": "all_seven_families_joint",
                "rank": 2,
                "role": "confirmatory",
                "standardized_dispersion_share": 0.253972,
            },
        ],
        "thresholds": {
            "dfbeta_influence": {"max_abs_standardized_dfbeta": 1.0},
            "rate_spanning_criterion": {"max_r2_span": 0.9, "min_s_span": 0.316228},
            "standardized_rate_exposure_dispersion": {"min_share_of_market_dispersion": 0.1},
        },
    }


def _influence_artifact() -> dict[str, Any]:
    return {
        "baseline": {
            "lambda_rate": -0.698465,
            "shanken_se_lambda_rate": 0.244258,
            "shanken_t_lambda_rate": -2.859541,
        },
        "dfbeta_influence": {
            "max_abs_standardized_dfbeta": 0.089645,
            "max_abs_standardized_dfbeta_asset": "inventory_growth__decile_05",
            "n_assets": 70,
            "n_assets_reaching_threshold": 0,
        },
        "gate_failures": [],
        "hypothesis": "H4b",
        "leave_one_family_fitted_premium": {"passes": True, "systems": [{"omitted_family": "bm"}]},
        "passes": True,
    }


def _precision_artifact() -> dict[str, Any]:
    return {
        "block_length": 6,
        "block_length_selected_by": "politis_white",
        "classification": "h4c_passed_interval_excludes_at_least_one_economic_direction",
        "draws": 10000,
        "economic_direction_bound": 0.25,
        "estimand": "rate_attributable_fitted_premium_spread_decile_10_minus_decile_01",
        "failing_families": [],
        "hypothesis": "H4c",
        "per_family": [
            {
                "family": "book_to_market",
                "h4c_gate": "pass",
                "interval_spans_both_directions": False,
                "lower_90": 0.070413,
                "lower_95": 0.022276,
                "point_estimate": 0.535266,
                "upper_90": 0.761391,
                "upper_95": 0.832065,
            }
        ],
    }


def test_artifact_helpers_format_and_locate_values(tmp_path: Path) -> None:
    payload_path = _write_json(tmp_path / "payload.json", {"outer": {"inner": 1.5}})

    assert load_json_artifact(payload_path) == {"outer": {"inner": 1.5}}
    assert artifact_field(load_json_artifact(payload_path), "outer", "inner") == 1.5
    assert format_value(True) == "true"
    assert format_value(False) == "false"
    assert format_value(7) == "7"
    assert format_value(0.1234567891) == "0.123457"
    assert format_value(None) == "n/a"
    assert format_value("verbatim") == "verbatim"
    assert format_sequence([]) == "none"
    assert format_sequence(["a", "b"]) == "`a`, `b`"
    assert markdown_table(["A"], [[1]]) == ["| A |", "|---|", "| 1 |"]
    assert dataframe_table(pd.DataFrame({"a": [1]})) == ["| a |", "|---|", "| 1 |"]
    assert missing_inputs((payload_path, tmp_path / "absent.json")) == (tmp_path / "absent.json",)

    with pytest.raises(KeyError, match=re.escape("outer.missing")):
        artifact_field(load_json_artifact(payload_path), "outer", "missing")
    list_path = tmp_path / "list.json"
    list_path.write_text("[1]", encoding="utf-8")
    with pytest.raises(ValueError, match="object JSON"):
        load_json_artifact(list_path)


def test_report_verdict_reads_or_reports_absence(tmp_path: Path) -> None:
    stated = tmp_path / "stated.md"
    stated.write_text("# Report\n\nVerdict: `unstable`\n", encoding="utf-8")
    silent = tmp_path / "silent.md"
    silent.write_text("# Report\n\nNo verdict here.\n", encoding="utf-8")

    assert report_verdict(stated) == "unstable"
    assert report_verdict(silent) == "not stated"


def test_regime_report_renders_registered_h3_outcomes(tmp_path: Path) -> None:
    equivalence_path = _write_json(tmp_path / "h3_equivalence.json", _equivalence_artifact())
    pooled_path = _write_json(tmp_path / "h3_pooled.json", _pooled_beta_artifact())
    output_path = tmp_path / "regime_report.md"

    write_regime_evidence_report(
        output_path=output_path,
        equivalence_path=equivalence_path,
        pooled_beta_path=pooled_path,
    )
    report = output_path.read_text(encoding="utf-8")

    assert report == render_regime_evidence_report(
        equivalence_path=equivalence_path,
        pooled_beta_path=pooled_path,
    )
    assert f"Verdict: `{REGIME_CLASSIFICATION}`" in report
    assert "blocked_missing_input" not in report
    assert "Replication status: `documented_reconstruction`" in report
    assert "| rmse_relative_deterioration | false |" in report
    assert "| equivalent_within_bound | 26 |" in report
    assert "| rate_beta_interactions | 37.313 | 5 | 5.1836e-07 | 5.07992e-05 |" in report
    assert "Classification: `unstable`" in report
    assert "`142` tests in family `regime_stability`" in report
    assert "Interpretation: Significant regime interactions indicate parameter" in report
    assert "- `" + equivalence_path.as_posix() + "`" in report


def test_regime_report_shows_the_evidence_behind_the_boundary_verdict(tmp_path: Path) -> None:
    """The per-shift results are rendered, not only the aggregate boolean.

    `any_conclusion_changed` is a single boolean, so on its own it hides how
    close a shifted boundary runs to the decision level. Each stored shift must
    appear with its statistic and its adjusted p-value.
    """
    pooled = _pooled_beta_artifact()
    report = render_regime_evidence_report(
        equivalence_path=_write_json(tmp_path / "h3_equivalence.json", _equivalence_artifact()),
        pooled_beta_path=_write_json(tmp_path / "h3_pooled.json", pooled),
    )
    sensitivity = artifact_field(pooled, "boundary_sensitivity")

    assert "### Boundary Sensitivity By Registered Shift" in report
    assert "Any conclusion changed: `false` across shifts `-3`, `0` months" in report
    for result in artifact_field(sensitivity, "results"):
        row = " | ".join(
            format_value(result[column])
            for column in (
                "shift_months",
                "aggregate_rate_beta_holm_p_value",
                "aggregate_rate_beta_statistic",
                "assets_rate_beta_significant_holm",
                "verdict",
                "verdict_matches_registered_boundaries",
            )
        )
        assert f"| {row} |" in report
    assert "| -3 | 0.06537 |" in report


def test_regime_report_surfaces_the_exploratory_break_battery(tmp_path: Path) -> None:
    """The stored break rows are rendered under their registered evidence class.

    The rows are exploratory and outside the confirmatory family, so the section
    states that before the table rather than letting the rows read as
    confirmatory evidence.
    """
    pooled = _pooled_beta_artifact()
    report = render_regime_evidence_report(
        equivalence_path=_write_json(tmp_path / "h3_equivalence.json", _equivalence_artifact()),
        pooled_beta_path=_write_json(tmp_path / "h3_pooled.json", pooled),
    )
    breaks = artifact_field(pooled, "exploratory_break_tests")

    assert "### Exploratory Break Battery" in report
    assert "Evidence class: `exploratory`" in report
    assert f"Note: {artifact_field(breaks, 'note')}" in report
    for result in artifact_field(breaks, "results"):
        assert format_value(result["break_month"]) in report
        assert format_value(result["test"]) in report
    assert "| 2015-12 | n/a | registered_boundary | 0.0525845 |" in report
    assert "| 1998-07 | 1 | estimated_unknown_break | n/a |" in report


def test_regime_report_states_when_a_stored_battery_is_empty(tmp_path: Path) -> None:
    """An empty battery is reported as empty rather than rendered as a bare heading."""
    pooled = _pooled_beta_artifact()
    pooled["exploratory_break_tests"]["results"] = []
    report = render_regime_evidence_report(
        equivalence_path=_write_json(tmp_path / "h3_equivalence.json", _equivalence_artifact()),
        pooled_beta_path=_write_json(tmp_path / "h3_pooled.json", pooled),
    )

    assert "### Exploratory Break Battery" in report
    assert "No records are stored for this section." in report


def test_temporal_report_renders_registered_h2_outcomes(tmp_path: Path) -> None:
    stability_path = _write_json(tmp_path / "h2.json", _temporal_artifact())
    evaluation_path = tmp_path / "temporal_evaluation.csv"
    pd.DataFrame(
        {
            "evaluation": ["locked_baseline_1972_2013"],
            "months": [504],
            "lambda_rate": [-0.698465],
            "replication_status": ["documented_reconstruction"],
        }
    ).to_csv(evaluation_path, index=False)
    freeze = TemporalFreeze(
        baseline_start="1972-01",
        baseline_end="2013-12",
        extension_start="2014-01",
        latest_common_month="2025-12",
        retrieval_date="2026-07-31",
        baseline_vintage_label="locked_original_1972_2013",
        extension_vintage_label="extension_retrieved_2026_07_31",
    )
    output_path = tmp_path / "temporal_report.md"

    write_temporal_evidence_report(
        output_path=output_path,
        freeze=freeze,
        stability_path=stability_path,
        evaluation_table_path=evaluation_path,
    )
    report = output_path.read_text(encoding="utf-8")

    assert report == render_temporal_evidence_report(
        freeze=freeze,
        stability_path=stability_path,
        evaluation_table_path=evaluation_path,
    )
    assert "Verdict: `post_publication_compatibility_unsupported`" in report
    assert "blocked_missing_input" not in report
    assert "Latest common month: `2025-12`" in report
    assert "| sign_compatibility | false |" in report
    assert "| refitted_extension | -0.082546 |" in report
    assert "| locked_baseline_1972_2013 | 504 | -0.698465 | documented_reconstruction |" in report
    assert "Vintage isolation: the temporal gates compare vintage-consistent windows" in report
    assert "revised-history evaluation is the current-vintage comparator" in report
    assert "revised historical values do enter the temporal verdict" in report
    assert "never the temporal verdict" not in report


def test_robustness_report_renders_registered_h1_and_weak_factor_outcomes(tmp_path: Path) -> None:
    materiality_path = _write_json(tmp_path / "h1.json", _materiality_artifact())
    identification_path = _write_json(tmp_path / "h4a.json", _identification_artifact())
    influence_path = _write_json(tmp_path / "h4b.json", _influence_artifact())
    precision_path = _write_json(tmp_path / "h4c.json", _precision_artifact())
    output_path = tmp_path / "robustness_report.md"

    write_robustness_evidence_report(
        output_path=output_path,
        materiality_path=materiality_path,
        identification_path=identification_path,
        influence_path=influence_path,
        precision_path=precision_path,
    )
    report = output_path.read_text(encoding="utf-8")

    assert report == render_robustness_evidence_report(
        materiality_path=materiality_path,
        identification_path=identification_path,
        influence_path=influence_path,
        precision_path=precision_path,
    )
    assert "Verdict: `unsupported`" in report
    assert "unidentified" not in report
    assert "Replication status: `documented_reconstruction`" in report
    assert (
        "| rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.100393 "
        "| 0.469737 | true |" in report
    )
    assert "| all_seven_families_joint | market_plus_fedfunds_innovation | capm | unsupported" in (
        report
    )
    assert "| H4a | true | none |" in report
    assert "| H4c | h4c_passed_interval_excludes_at_least_one_economic_direction | none |" in report
    assert "rank `2` of `2` priced factors" in report
    assert "| book_to_market | 0.535266 | 0.022276 | 0.832065 | false | pass |" in report
    assert "significant-only robustness reporting is prohibited" in report


def test_h4c_table_displays_the_interval_the_registered_gate_reads(tmp_path: Path) -> None:
    """H4c renders the 95 percent interval, which is the one the gate evaluates.

    The gate in `scripts/run_h4c_precision.py` sets
    `interval_spans_both_directions` from `lower_95` and `upper_95`. Displaying
    the 90 percent interval beside that verdict showed evidence the gate never
    read, so the report is required to carry the 95 percent bounds.
    """
    report = render_robustness_evidence_report(
        materiality_path=_write_json(tmp_path / "h1.json", _materiality_artifact()),
        identification_path=_write_json(tmp_path / "h4a.json", _identification_artifact()),
        influence_path=_write_json(tmp_path / "h4b.json", _influence_artifact()),
        precision_path=_write_json(tmp_path / "h4c.json", _precision_artifact()),
    )
    family = artifact_field(_precision_artifact(), "per_family")[0]

    assert "| Family | Point Estimate | Lower 95 | Upper 95 |" in report
    assert "Lower 90" not in report
    assert "Upper 90" not in report
    assert format_value(family["lower_95"]) in report
    assert format_value(family["upper_95"]) in report
    assert format_value(family["lower_90"]) not in report
    assert format_value(family["upper_90"]) not in report
    assert "registered H4c gate is evaluated on the 95 percent bootstrap interval" in report


def test_h1_report_renders_gate_values_for_every_asset_set(tmp_path: Path) -> None:
    """Every classification the report lists is backed by displayed gate values.

    The report previously emitted gate values for the headline asset set alone
    while listing a classification for each asset set and model, so the
    off-headline classifications could not be audited from the report.
    """
    materiality = _materiality_artifact()
    report = render_robustness_evidence_report(
        materiality_path=_write_json(tmp_path / "h1.json", materiality),
        identification_path=_write_json(tmp_path / "h4a.json", _identification_artifact()),
        influence_path=_write_json(tmp_path / "h4b.json", _influence_artifact()),
        precision_path=_write_json(tmp_path / "h4c.json", _precision_artifact()),
    )
    gates = sorted(artifact_field(materiality, "thresholds"))
    asset_sets = artifact_field(materiality, "asset_sets")

    assert "## H1 Gate Values By Asset Set And Comparison" in report
    rendered = 0
    for asset_set, record in asset_sets.items():
        for slot in ("primary_comparison", "secondary_adversarial_comparison"):
            for model, comparison in record[slot].items():
                for gate in gates:
                    row = " | ".join(
                        [
                            asset_set,
                            model,
                            str(comparison["comparison_role"]),
                            str(comparison["comparator_model"]),
                            gate,
                            format_value(comparison[f"{gate}__comparison"]),
                            format_value(comparison[f"{gate}__threshold"]),
                            format_value(comparison[f"{gate}__comparator_value"]),
                            format_value(comparison[f"{gate}__treatment_value"]),
                            format_value(comparison[f"{gate}__observed"]),
                            format_value(comparison[f"{gate}__passed"]),
                        ]
                    )
                    assert f"| {row} |" in report
                    rendered += 1
    assert rendered == len(asset_sets) * 2 * len(gates)


def test_robustness_report_requires_a_confirmatory_system(tmp_path: Path) -> None:
    identification = _identification_artifact()
    identification["systems"] = [{"portfolio_set": "descriptive_set", "role": "descriptive"}]
    paths = (
        _write_json(tmp_path / "h1.json", _materiality_artifact()),
        _write_json(tmp_path / "h4a.json", identification),
        _write_json(tmp_path / "h4b.json", _influence_artifact()),
        _write_json(tmp_path / "h4c.json", _precision_artifact()),
    )

    with pytest.raises(ValueError, match="no confirmatory system"):
        render_robustness_evidence_report(
            materiality_path=paths[0],
            identification_path=paths[1],
            influence_path=paths[2],
            precision_path=paths[3],
        )


def test_blocked_robustness_report_lists_missing_artifacts(tmp_path: Path) -> None:
    output_path = tmp_path / "robustness_report.md"

    write_blocked_robustness_report(
        output_path=output_path,
        missing_inputs=(Path("artifacts/diagnostics/h1_materiality.json"),),
    )
    report = output_path.read_text(encoding="utf-8")

    assert "Verdict: `unidentified`" in report
    assert "- `artifacts/diagnostics/h1_materiality.json`" in report


def _manuscript_fixture(tmp_path: Path, *, tagged: bool) -> tuple[Path, Path, Path]:
    artifact_path = tmp_path / "artifact.csv"
    artifact_path.write_text("value\n1\n", encoding="utf-8")
    artifact_map_path = tmp_path / "map.csv"
    artifact_map_path.write_text(
        f"artifact_id,path,description\nartifact,{artifact_path.as_posix()},Fixture artifact\n",
        encoding="utf-8",
    )
    tag = f"  % artifact: {artifact_path.as_posix()}" if tagged else ""
    manuscript_path = tmp_path / "paper.tex"
    manuscript_path.write_text(
        f"\\title{{Short rate anomalies}}\n\\section{{Results}}\nThe estimate is 0.25.{tag}\n",
        encoding="utf-8",
    )
    upstream_path = tmp_path / "upstream.md"
    upstream_path.write_text("# Upstream\n\nVerdict: `unstable`\n", encoding="utf-8")
    return manuscript_path, artifact_map_path, upstream_path


def test_manuscript_output_report_records_validated_outputs(tmp_path: Path) -> None:
    manuscript_path, artifact_map_path, upstream_path = _manuscript_fixture(tmp_path, tagged=True)
    output_path = tmp_path / "manuscript_output_report.md"

    write_manuscript_output_report(
        output_path=output_path,
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
        upstream_report_paths=(upstream_path,),
    )
    report = output_path.read_text(encoding="utf-8")

    assert report == render_manuscript_output_report(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
        upstream_report_paths=(upstream_path,),
    )
    assert "Verdict: `manuscript_outputs_validated`" in report
    assert "blocked_missing_input" not in report
    assert "Mapped artifacts: 1, of which 0 are absent" in report
    assert "Validation issues: 0" in report
    assert "No manuscript validation issue was raised." in report
    assert f"| {upstream_path.as_posix()} | unstable |" in report


def test_manuscript_output_report_counts_validation_failures(tmp_path: Path) -> None:
    manuscript_path, artifact_map_path, upstream_path = _manuscript_fixture(tmp_path, tagged=False)

    report = render_manuscript_output_report(
        manuscript_path=manuscript_path,
        artifact_map_path=artifact_map_path,
        upstream_report_paths=(upstream_path,),
    )

    assert "Verdict: `manuscript_validation_failed`" in report
    assert "| numeric_artifact_mapping | 1 |" in report
