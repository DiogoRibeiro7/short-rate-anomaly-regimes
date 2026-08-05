"""Tests for the frozen H1 incremental-pricing materiality comparison."""

from __future__ import annotations

import math

import pandas as pd
import pytest
from scripts.run_h1_materiality import (
    ALTERNATIVE_SHORT_RATE_MODEL,
    BASELINE_SHORT_RATE_MODEL,
    CLASSIFICATION_INCONCLUSIVE,
    CLASSIFICATION_SUPPORTED,
    CLASSIFICATION_UNSUPPORTED,
    GATE_MAE,
    GATE_MAX_ABSOLUTE_ERROR,
    GATE_RMSE,
    MAE_RELATIVE_REDUCTION_THRESHOLD,
    MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD,
    PRIMARY_COMPARATOR,
    REGISTERED_NON_SHORT_RATE_COMPARATORS,
    RMSE_RELATIVE_REDUCTION_THRESHOLD,
    SystemMetrics,
    build_comparison_record,
    build_primary_records,
    build_secondary_records,
    classify_gates,
    evaluate_materiality_gates,
    load_system_metrics,
    require_common_intersection,
    select_strongest_comparator,
)

ASSET_SET = "all_seven_families_joint"


def _system(
    model: str,
    *,
    rmse: float,
    mae: float,
    max_abs: float,
    portfolio_set: str = ASSET_SET,
    n_assets: int = 70,
    n_months: int = 504,
) -> SystemMetrics:
    return SystemMetrics(
        model=model,
        portfolio_set=portfolio_set,
        n_assets=n_assets,
        n_months=n_months,
        root_mean_squared_pricing_error=rmse,
        mean_absolute_pricing_error=mae,
        max_absolute_pricing_error=max_abs,
    )


def _capm(*, rmse: float = 1.0, mae: float = 1.0, max_abs: float = 1.0) -> SystemMetrics:
    return _system(PRIMARY_COMPARATOR, rmse=rmse, mae=mae, max_abs=max_abs)


# ---------------------------------------------------------------------------
# Registered thresholds are frozen.
# ---------------------------------------------------------------------------


def test_registered_thresholds_match_the_frozen_contract() -> None:
    assert RMSE_RELATIVE_REDUCTION_THRESHOLD == 0.10
    assert MAE_RELATIVE_REDUCTION_THRESHOLD == 0.10
    assert MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD == 0.25
    assert PRIMARY_COMPARATOR == "capm"


# ---------------------------------------------------------------------------
# All three gates pass.
# ---------------------------------------------------------------------------


def test_all_three_gates_passing_classifies_as_supported() -> None:
    comparator = _capm(rmse=1.0, mae=1.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.80, mae=0.80, max_abs=0.70)

    gates = evaluate_materiality_gates(treatment, comparator)

    assert [gate.gate for gate in gates] == [GATE_RMSE, GATE_MAE, GATE_MAX_ABSOLUTE_ERROR]
    assert all(gate.passed for gate in gates)
    assert classify_gates(gates) == CLASSIFICATION_SUPPORTED


def test_gates_pass_exactly_at_the_registered_boundary() -> None:
    """Confirm the registered thresholds are inclusive, so equality passes."""
    comparator = _capm(rmse=10.0, mae=10.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=9.0, mae=9.0, max_abs=0.75)

    gates = evaluate_materiality_gates(treatment, comparator)

    assert gates[0].observed == RMSE_RELATIVE_REDUCTION_THRESHOLD
    assert gates[1].observed == MAE_RELATIVE_REDUCTION_THRESHOLD
    assert gates[2].observed == MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD
    assert all(gate.passed for gate in gates)
    assert classify_gates(gates) == CLASSIFICATION_SUPPORTED


# ---------------------------------------------------------------------------
# Each gate failing individually.
# ---------------------------------------------------------------------------


def test_rmse_gate_failing_alone_classifies_as_unsupported() -> None:
    comparator = _capm(rmse=1.0, mae=1.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.95, mae=0.80, max_abs=0.70)

    gates = evaluate_materiality_gates(treatment, comparator)
    outcomes = {gate.gate: gate.passed for gate in gates}

    assert outcomes == {GATE_RMSE: False, GATE_MAE: True, GATE_MAX_ABSOLUTE_ERROR: True}
    assert classify_gates(gates) == CLASSIFICATION_UNSUPPORTED


def test_mae_gate_failing_alone_classifies_as_unsupported() -> None:
    comparator = _capm(rmse=1.0, mae=1.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.80, mae=0.95, max_abs=0.70)

    gates = evaluate_materiality_gates(treatment, comparator)
    outcomes = {gate.gate: gate.passed for gate in gates}

    assert outcomes == {GATE_RMSE: True, GATE_MAE: False, GATE_MAX_ABSOLUTE_ERROR: True}
    assert classify_gates(gates) == CLASSIFICATION_UNSUPPORTED


def test_max_absolute_error_gate_failing_alone_classifies_as_unsupported() -> None:
    comparator = _capm(rmse=1.0, mae=1.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.80, mae=0.80, max_abs=0.80)

    gates = evaluate_materiality_gates(treatment, comparator)
    outcomes = {gate.gate: gate.passed for gate in gates}

    assert outcomes == {GATE_RMSE: True, GATE_MAE: True, GATE_MAX_ABSOLUTE_ERROR: False}
    assert classify_gates(gates) == CLASSIFICATION_UNSUPPORTED


def test_max_absolute_error_gate_is_a_level_not_a_ratio() -> None:
    """Confirm the third gate uses monthly percentage points, not a percentage."""
    comparator = _capm(max_abs=0.30)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.10, mae=0.10, max_abs=0.10)

    gate = evaluate_materiality_gates(treatment, comparator)[2]

    assert gate.observed == pytest.approx(0.20)
    assert gate.passed is False


# ---------------------------------------------------------------------------
# The short-rate model is worse than CAPM.
# ---------------------------------------------------------------------------


def test_short_rate_model_worse_than_capm_fails_every_gate() -> None:
    comparator = _capm(rmse=0.19, mae=0.15, max_abs=0.48)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.25, mae=0.20, max_abs=0.60)

    gates = evaluate_materiality_gates(treatment, comparator)

    assert not any(gate.passed for gate in gates)
    assert all(gate.observed < 0.0 for gate in gates)
    assert classify_gates(gates) == CLASSIFICATION_UNSUPPORTED

    record = build_comparison_record(
        treatment=treatment,
        comparator=comparator,
        comparison_role="primary",
        comparator_selection_rule="chosen ex ante",
        comparator_selected_after_observing_rmse=False,
    )
    assert record["classification"] == CLASSIFICATION_UNSUPPORTED
    assert record["n_gates_passed"] == 0
    assert record["n_gates_total"] == 3


# ---------------------------------------------------------------------------
# Undefined gates are inconclusive rather than silently failing.
# ---------------------------------------------------------------------------


def test_non_finite_metric_classifies_as_inconclusive() -> None:
    comparator = _capm(rmse=1.0, mae=1.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=math.nan, mae=0.80, max_abs=0.70)

    gates = evaluate_materiality_gates(treatment, comparator)

    assert classify_gates(gates) == CLASSIFICATION_INCONCLUSIVE


def test_zero_comparator_metric_classifies_as_inconclusive() -> None:
    comparator = _capm(rmse=0.0, mae=1.0, max_abs=1.0)
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.10, mae=0.80, max_abs=0.70)

    gates = evaluate_materiality_gates(treatment, comparator)

    assert math.isnan(gates[0].observed)
    assert classify_gates(gates) == CLASSIFICATION_INCONCLUSIVE


def test_classification_requires_at_least_one_gate() -> None:
    with pytest.raises(ValueError, match="at least one gate"):
        classify_gates([])


# ---------------------------------------------------------------------------
# Identical asset-date intersections.
# ---------------------------------------------------------------------------


def test_mismatched_asset_counts_are_rejected() -> None:
    comparator = _capm()
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.5, mae=0.5, max_abs=0.5, n_assets=60)

    with pytest.raises(ValueError, match="identical asset-date intersection"):
        require_common_intersection(treatment, comparator)


def test_mismatched_month_counts_are_rejected() -> None:
    comparator = _capm()
    treatment = _system(BASELINE_SHORT_RATE_MODEL, rmse=0.5, mae=0.5, max_abs=0.5, n_months=300)

    with pytest.raises(ValueError, match="identical asset-date intersection"):
        evaluate_materiality_gates(treatment, comparator)


def test_mismatched_portfolio_sets_are_rejected() -> None:
    comparator = _capm()
    treatment = _system(
        BASELINE_SHORT_RATE_MODEL,
        rmse=0.5,
        mae=0.5,
        max_abs=0.5,
        portfolio_set="book_to_market",
        n_assets=70,
    )

    with pytest.raises(ValueError, match="different portfolio sets"):
        require_common_intersection(treatment, comparator)


# ---------------------------------------------------------------------------
# Strongest-observed comparator selection.
# ---------------------------------------------------------------------------


def _metrics_for_selection(
    rmse_by_model: dict[str, float],
) -> dict[tuple[str, str], SystemMetrics]:
    return {
        (ASSET_SET, model): _system(model, rmse=rmse, mae=rmse * 0.8, max_abs=rmse * 2.0)
        for model, rmse in rmse_by_model.items()
    }


def test_strongest_comparator_selection_picks_the_lowest_rmse_model() -> None:
    metrics = _metrics_for_selection(
        {
            "fama_french_3": 0.079828,
            "carhart_4": 0.072036,
            "fama_french_5": 0.074532,
            "q_factor": 0.083197,
            "liquidity": 0.079567,
        }
    )

    assert select_strongest_comparator(metrics, ASSET_SET) == "carhart_4"


def test_strongest_comparator_selection_ignores_short_rate_and_capm_models() -> None:
    metrics = _metrics_for_selection(
        {
            PRIMARY_COMPARATOR: 0.001,
            BASELINE_SHORT_RATE_MODEL: 0.002,
            ALTERNATIVE_SHORT_RATE_MODEL: 0.003,
            "fama_french_3": 0.070,
            "carhart_4": 0.060,
            "fama_french_5": 0.065,
            "q_factor": 0.080,
            "liquidity": 0.090,
        }
    )

    assert select_strongest_comparator(metrics, ASSET_SET) == "carhart_4"
    assert PRIMARY_COMPARATOR not in REGISTERED_NON_SHORT_RATE_COMPARATORS


def test_strongest_comparator_selection_skips_missing_and_non_finite_systems() -> None:
    metrics = _metrics_for_selection({"fama_french_5": math.nan, "q_factor": 0.09})

    assert select_strongest_comparator(metrics, ASSET_SET) == "q_factor"


def test_strongest_comparator_selection_requires_a_candidate() -> None:
    with pytest.raises(ValueError, match="no registered non-short-rate comparator"):
        select_strongest_comparator({}, ASSET_SET)


# ---------------------------------------------------------------------------
# Record construction, roles, and multiplicity labelling.
# ---------------------------------------------------------------------------


def _full_metrics() -> dict[tuple[str, str], SystemMetrics]:
    rows = {
        PRIMARY_COMPARATOR: (0.189327, 0.146575, 0.475246),
        BASELINE_SHORT_RATE_MODEL: (0.100393, 0.081641, 0.238831),
        ALTERNATIVE_SHORT_RATE_MODEL: (0.108418, 0.085816, 0.278117),
        "fama_french_3": (0.079828, 0.062968, 0.240933),
        "carhart_4": (0.072036, 0.055976, 0.242704),
        "fama_french_5": (0.074532, 0.059475, 0.174313),
        "q_factor": (0.083197, 0.066430, 0.216391),
        "liquidity": (0.079567, 0.062306, 0.235379),
    }
    return {
        (ASSET_SET, model): _system(model, rmse=rmse, mae=mae, max_abs=max_abs)
        for model, (rmse, mae, max_abs) in rows.items()
    }


def test_primary_records_cover_both_registered_short_rate_specifications() -> None:
    records = build_primary_records(_full_metrics(), [ASSET_SET])

    assert [record["treatment_model"] for record in records] == [
        BASELINE_SHORT_RATE_MODEL,
        ALTERNATIVE_SHORT_RATE_MODEL,
    ]
    assert records[0]["treatment_role"] == "registered_baseline_short_rate_specification"
    assert records[1]["treatment_role"] == "registered_alternative_short_rate_specification"
    for record in records:
        assert record["comparator_model"] == PRIMARY_COMPARATOR
        assert record["comparator_selected_after_observing_rmse"] is False
        assert record["model_selection_uncertainty"] == "none"
        assert record["replication_status"] == "documented_reconstruction"
        assert record["is_headline_asset_set"] is True


def test_secondary_records_record_model_selection_uncertainty() -> None:
    records = build_secondary_records(_full_metrics(), [ASSET_SET])

    for record in records:
        assert record["comparison_role"] == "secondary_adversarial"
        assert record["comparator_model"] == "carhart_4"
        assert record["comparator_selected_after_observing_rmse"] is True
        assert "AFTER observing" in str(record["model_selection_uncertainty"])
        assert record["p_value_generated"] is False
        assert record["holm_adjustment_applied"] is False
        assert "does not yet apply" in str(record["holm_status"])


def test_comparison_record_carries_every_gate_value_and_threshold() -> None:
    record = build_comparison_record(
        treatment=_system(BASELINE_SHORT_RATE_MODEL, rmse=0.80, mae=0.80, max_abs=0.70),
        comparator=_capm(),
        comparison_role="primary",
        comparator_selection_rule="chosen ex ante",
        comparator_selected_after_observing_rmse=False,
    )

    for gate in (GATE_RMSE, GATE_MAE, GATE_MAX_ABSOLUTE_ERROR):
        for suffix in (
            "treatment_value",
            "comparator_value",
            "observed",
            "threshold",
            "comparison",
            "passed",
        ):
            assert f"{gate}__{suffix}" in record
    assert record[f"{GATE_RMSE}__threshold"] == RMSE_RELATIVE_REDUCTION_THRESHOLD
    assert record[f"{GATE_MAE}__threshold"] == MAE_RELATIVE_REDUCTION_THRESHOLD
    assert record[f"{GATE_MAX_ABSOLUTE_ERROR}__threshold"] == (
        MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD
    )
    assert record["classification"] == CLASSIFICATION_SUPPORTED


# ---------------------------------------------------------------------------
# Loading the baseline table.
# ---------------------------------------------------------------------------


def _baseline_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "portfolio_set": [ASSET_SET, ASSET_SET],
            "model": [PRIMARY_COMPARATOR, BASELINE_SHORT_RATE_MODEL],
            "n_assets": [70, 70],
            "n_months": [504, 504],
            "root_mean_squared_pricing_error": [0.189327, 0.100393],
            "mean_absolute_pricing_error": [0.146575, 0.081641],
            "max_absolute_pricing_error": [0.475246, 0.238831],
        }
    )


def test_load_system_metrics_keys_by_portfolio_set_and_model() -> None:
    metrics = load_system_metrics(_baseline_frame())

    assert set(metrics) == {
        (ASSET_SET, PRIMARY_COMPARATOR),
        (ASSET_SET, BASELINE_SHORT_RATE_MODEL),
    }
    system = metrics[ASSET_SET, BASELINE_SHORT_RATE_MODEL]
    assert system.n_assets == 70
    assert system.root_mean_squared_pricing_error == pytest.approx(0.100393)


def test_load_system_metrics_rejects_missing_columns() -> None:
    frame = _baseline_frame().drop(columns=["max_absolute_pricing_error"])

    with pytest.raises(ValueError, match="missing required columns"):
        load_system_metrics(frame)


def test_load_system_metrics_rejects_duplicate_systems() -> None:
    frame = pd.concat([_baseline_frame(), _baseline_frame()], ignore_index=True)

    with pytest.raises(ValueError, match="duplicate system"):
        load_system_metrics(frame)
