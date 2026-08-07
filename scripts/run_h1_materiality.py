"""Execute the frozen H1 incremental-pricing materiality comparison.

The design is preregistered in `research/economic_thresholds.md` (section
"Incremental Pricing Materiality"), row `H1` of
`research/hypothesis_registry.csv`, `research/comparator_model_registry.csv`,
`research/statistical_protocol.md` (section "Model Comparison") and
`research/inference_contract.md` (section "Multiplicity Families"). This module
executes that design; it does not revise it.

The primary comparator is the CAPM, fixed ex ante and independently of any
observed root mean squared pricing error. H1 is supported against the primary
comparator only when all three primary materiality gates hold jointly. The
strongest observed registered non-short-rate comparator is a secondary
adversarial comparison that is selected after observing RMSE and therefore
carries model-selection uncertainty; it never selects the primary comparator.

Every gate here is a deterministic threshold comparison on point estimates
already produced by the baseline replication. No p-value is generated in this
pass, so the Holm adjustment registered for the secondary comparator family has
nothing to adjust and does not yet apply.

All inputs in this project are documented reconstructions, so every output row
carries the `documented_reconstruction` label.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd

BASELINE_RISK_PRICES_CSV: Final = Path("artifacts/tables/cross_section/baseline_risk_prices.csv")
BASELINE_PRICING_ERRORS_PARQUET: Final = Path(
    "artifacts/estimates/cross_section/baseline_pricing_errors.parquet"
)

PRIMARY_COMPARISON_CSV: Final = Path("artifacts/tables/robustness/h1_primary_comparison.csv")
SECONDARY_ADVERSARIAL_CSV: Final = Path("artifacts/tables/robustness/h1_secondary_adversarial.csv")
DIAGNOSTICS_JSON: Final = Path("artifacts/diagnostics/h1_materiality.json")
PROVENANCE_JSON: Final = Path("artifacts/provenance/h1_materiality.json")

SCRIPT_NAME: Final = "scripts/run_h1_materiality.py"
REPLICATION_STATUS: Final = "documented_reconstruction"

#: Registered materiality thresholds, frozen in
#: `research/economic_thresholds.md`. These are not tuning parameters.
RMSE_RELATIVE_REDUCTION_THRESHOLD: Final = 0.10
MAE_RELATIVE_REDUCTION_THRESHOLD: Final = 0.10
MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD: Final = 0.25

#: The ex ante primary comparator. Fixed before estimation and independent of
#: observed RMSE, per `research/comparator_model_registry.csv`.
PRIMARY_COMPARATOR: Final = "capm"
PRIMARY_COMPARATOR_SELECTION_RULE: Final = (
    "chosen ex ante as primary comparator independently of observed RMSE"
)

#: The registered baseline short-rate specification and its registered
#: alternative. The alternative is reported as an alternative specification,
#: never as the baseline.
BASELINE_SHORT_RATE_MODEL: Final = "market_plus_fedfunds_innovation"
ALTERNATIVE_SHORT_RATE_MODEL: Final = "market_plus_tbill_innovation"
SHORT_RATE_MODEL_ROLES: Final[Mapping[str, str]] = {
    BASELINE_SHORT_RATE_MODEL: "registered_baseline_short_rate_specification",
    ALTERNATIVE_SHORT_RATE_MODEL: "registered_alternative_short_rate_specification",
}

#: Registered secondary non-short-rate comparators, from
#: `research/comparator_model_registry.csv`.
REGISTERED_NON_SHORT_RATE_COMPARATORS: Final[tuple[str, ...]] = (
    "fama_french_3",
    "carhart_4",
    "fama_french_5",
    "q_factor",
    "liquidity",
)
STRONGEST_COMPARATOR_SELECTION_RULE: Final = (
    "selected after observing baseline cross-sectional RMSE; lowest RMSE among the "
    "registered non-short-rate comparators on the same asset set; not used to choose "
    "the primary comparator"
)
MODEL_SELECTION_UNCERTAINTY_NOTE: Final = (
    "This comparator was chosen AFTER observing cross-sectional RMSE. The comparison "
    "therefore carries model-selection uncertainty and is reported as a secondary "
    "adversarial check only, per research/statistical_protocol.md."
)

HEADLINE_ASSET_SET: Final = "all_seven_families_joint"

#: Multiplicity handling, from `research/inference_contract.md`.
MULTIPLICITY_FAMILY: Final = "baseline_pricing"
HOLM_STATUS_NOTE: Final = (
    "The registered secondary comparator family uses Holm adjustment for secondary "
    "p-values. The materiality gates executed here are deterministic threshold "
    "comparisons on point estimates, so no p-value is generated in this pass and Holm "
    "adjustment therefore does not yet apply. No p-value is invented to fill the slot."
)

#: Registered classification vocabulary for H1, from the H1 row of
#: `research/hypothesis_registry.csv`.
CLASSIFICATION_SUPPORTED: Final = "supported"
CLASSIFICATION_UNSUPPORTED: Final = "unsupported"
CLASSIFICATION_INCONCLUSIVE: Final = "inconclusive"
CLASSIFICATION_INTERPRETATIONS: Final[Mapping[str, str]] = {
    CLASSIFICATION_SUPPORTED: (
        "The short-rate factor has economically meaningful incremental pricing content "
        "against the ex ante primary comparator in the baseline sample."
    ),
    CLASSIFICATION_UNSUPPORTED: (
        "The baseline does not support an economically meaningful incremental pricing claim."
    ),
    CLASSIFICATION_INCONCLUSIVE: (
        "The pricing result is blocked, weakly identified, or too imprecise for interpretation."
    ),
}

GATE_RMSE: Final = "rmse_relative_reduction"
GATE_MAE: Final = "mae_relative_reduction"
GATE_MAX_ABSOLUTE_ERROR: Final = "max_absolute_error_reduction"

RELATIVE_REDUCTION: Final = "relative_reduction_at_least"
ABSOLUTE_REDUCTION: Final = "absolute_reduction_at_least"


@dataclass(frozen=True, slots=True)
class SystemMetrics:
    """Pricing-loss metrics for one estimated (model, portfolio_set) system.

    Attributes:
        model: Registered model identifier.
        portfolio_set: Registered test-asset set identifier.
        n_assets: Number of test assets in the estimated system.
        n_months: Number of months in the estimated system.
        root_mean_squared_pricing_error: Cross-sectional RMSE.
        mean_absolute_pricing_error: Cross-sectional MAE.
        max_absolute_pricing_error: Maximum absolute cross-sectional pricing error.
    """

    model: str
    portfolio_set: str
    n_assets: int
    n_months: int
    root_mean_squared_pricing_error: float
    mean_absolute_pricing_error: float
    max_absolute_pricing_error: float


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """Outcome of a single registered materiality gate.

    Attributes:
        gate: Registered gate identifier.
        metric: Underlying pricing-loss metric compared.
        treatment_value: Metric value for the short-rate model.
        comparator_value: Metric value for the comparator model.
        observed: Observed improvement in the gate's own units.
        threshold: Registered threshold the observed value must reach.
        comparison: Direction and unit of the registered comparison.
        passed: Whether the observed improvement reaches the threshold.
    """

    gate: str
    metric: str
    treatment_value: float
    comparator_value: float
    observed: float
    threshold: float
    comparison: str
    passed: bool


def _sha256(path: Path) -> str:
    """Return the SHA-256 hex digest of a file.

    Args:
        path: File to digest.

    Returns:
        Lowercase hexadecimal SHA-256 digest.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_system_metrics(frame: pd.DataFrame) -> dict[tuple[str, str], SystemMetrics]:
    """Load the baseline pricing-loss metrics keyed by portfolio set and model.

    Args:
        frame: Baseline risk-price table with one row per estimated system.

    Returns:
        Mapping from ``(portfolio_set, model)`` to its pricing-loss metrics.

    Raises:
        ValueError: If a required column is missing or a system is duplicated.
    """
    required = (
        "portfolio_set",
        "model",
        "n_assets",
        "n_months",
        "root_mean_squared_pricing_error",
        "mean_absolute_pricing_error",
        "max_absolute_pricing_error",
    )
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"baseline risk-price table is missing required columns: {missing}")

    metrics: dict[tuple[str, str], SystemMetrics] = {}
    for record in frame[list(required)].to_dict(orient="records"):
        key = (str(record["portfolio_set"]), str(record["model"]))
        if key in metrics:
            raise ValueError(f"duplicate system in baseline risk-price table: {key}")
        metrics[key] = SystemMetrics(
            model=key[1],
            portfolio_set=key[0],
            n_assets=int(record["n_assets"]),
            n_months=int(record["n_months"]),
            root_mean_squared_pricing_error=float(record["root_mean_squared_pricing_error"]),
            mean_absolute_pricing_error=float(record["mean_absolute_pricing_error"]),
            max_absolute_pricing_error=float(record["max_absolute_pricing_error"]),
        )
    return metrics


def require_common_intersection(treatment: SystemMetrics, comparator: SystemMetrics) -> None:
    """Verify that two compared systems share an identical asset-date intersection.

    The registered protocol requires every model comparison to run on identical
    assets and months within the comparison.

    Args:
        treatment: Short-rate system being evaluated.
        comparator: Comparator system.

    Returns:
        None.

    Raises:
        ValueError: If the two systems differ in portfolio set, asset count, or month count.
    """
    if treatment.portfolio_set != comparator.portfolio_set:
        raise ValueError(
            "comparison spans different portfolio sets: "
            f"{treatment.portfolio_set} vs {comparator.portfolio_set}"
        )
    if (treatment.n_assets, treatment.n_months) != (comparator.n_assets, comparator.n_months):
        raise ValueError(
            "comparison is not on an identical asset-date intersection for "
            f"{treatment.portfolio_set}: {treatment.model} has "
            f"({treatment.n_assets}, {treatment.n_months}) but {comparator.model} has "
            f"({comparator.n_assets}, {comparator.n_months})"
        )


def _relative_reduction(treatment_value: float, comparator_value: float) -> float:
    """Return the fractional reduction of the treatment metric versus the comparator.

    Args:
        treatment_value: Metric value for the short-rate model.
        comparator_value: Metric value for the comparator model.

    Returns:
        ``(comparator - treatment) / comparator``, or NaN when the comparator
        value is not a strictly positive finite number and the ratio is
        undefined.
    """
    if not math.isfinite(treatment_value) or not math.isfinite(comparator_value):
        return math.nan
    if comparator_value <= 0.0:
        return math.nan
    return (comparator_value - treatment_value) / comparator_value


def _absolute_reduction(treatment_value: float, comparator_value: float) -> float:
    """Return the level reduction of the treatment metric versus the comparator.

    Args:
        treatment_value: Metric value for the short-rate model.
        comparator_value: Metric value for the comparator model.

    Returns:
        ``comparator - treatment``, or NaN when either input is not finite.
    """
    if not math.isfinite(treatment_value) or not math.isfinite(comparator_value):
        return math.nan
    return comparator_value - treatment_value


def evaluate_materiality_gates(
    treatment: SystemMetrics, comparator: SystemMetrics
) -> tuple[GateOutcome, ...]:
    """Evaluate the three registered H1 materiality gates for one comparison.

    Args:
        treatment: Short-rate system being evaluated.
        comparator: Comparator system on the identical asset-date intersection.

    Returns:
        The RMSE, MAE, and maximum-absolute-error gate outcomes, in registered order.

    Raises:
        ValueError: If the two systems are not on an identical asset-date intersection.
    """
    require_common_intersection(treatment, comparator)

    rmse_observed = _relative_reduction(
        treatment.root_mean_squared_pricing_error,
        comparator.root_mean_squared_pricing_error,
    )
    mae_observed = _relative_reduction(
        treatment.mean_absolute_pricing_error,
        comparator.mean_absolute_pricing_error,
    )
    max_observed = _absolute_reduction(
        treatment.max_absolute_pricing_error,
        comparator.max_absolute_pricing_error,
    )
    return (
        GateOutcome(
            gate=GATE_RMSE,
            metric="root_mean_squared_pricing_error",
            treatment_value=treatment.root_mean_squared_pricing_error,
            comparator_value=comparator.root_mean_squared_pricing_error,
            observed=rmse_observed,
            threshold=RMSE_RELATIVE_REDUCTION_THRESHOLD,
            comparison=RELATIVE_REDUCTION,
            passed=bool(
                math.isfinite(rmse_observed) and rmse_observed >= RMSE_RELATIVE_REDUCTION_THRESHOLD
            ),
        ),
        GateOutcome(
            gate=GATE_MAE,
            metric="mean_absolute_pricing_error",
            treatment_value=treatment.mean_absolute_pricing_error,
            comparator_value=comparator.mean_absolute_pricing_error,
            observed=mae_observed,
            threshold=MAE_RELATIVE_REDUCTION_THRESHOLD,
            comparison=RELATIVE_REDUCTION,
            passed=bool(
                math.isfinite(mae_observed) and mae_observed >= MAE_RELATIVE_REDUCTION_THRESHOLD
            ),
        ),
        GateOutcome(
            gate=GATE_MAX_ABSOLUTE_ERROR,
            metric="max_absolute_pricing_error",
            treatment_value=treatment.max_absolute_pricing_error,
            comparator_value=comparator.max_absolute_pricing_error,
            observed=max_observed,
            threshold=MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD,
            comparison=ABSOLUTE_REDUCTION,
            passed=bool(
                math.isfinite(max_observed)
                and max_observed >= MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD
            ),
        ),
    )


def classify_gates(gates: Sequence[GateOutcome]) -> str:
    """Classify one comparison under the registered H1 vocabulary.

    Args:
        gates: Gate outcomes for a single comparison.

    Returns:
        ``"supported"`` when every gate passes, ``"inconclusive"`` when any gate
        value is undefined so the gate cannot be decided, and ``"unsupported"``
        otherwise.

    Raises:
        ValueError: If no gate outcomes are supplied.
    """
    if not gates:
        raise ValueError("classification requires at least one gate outcome")
    if any(not math.isfinite(gate.observed) for gate in gates):
        return CLASSIFICATION_INCONCLUSIVE
    if all(gate.passed for gate in gates):
        return CLASSIFICATION_SUPPORTED
    return CLASSIFICATION_UNSUPPORTED


def select_strongest_comparator(
    metrics: Mapping[tuple[str, str], SystemMetrics],
    portfolio_set: str,
    candidates: Sequence[str] = REGISTERED_NON_SHORT_RATE_COMPARATORS,
) -> str:
    """Select the strongest observed registered non-short-rate comparator.

    Strength is the lowest baseline cross-sectional RMSE on the given asset set.
    This selection happens after RMSE is observed and is used only for the
    secondary adversarial comparison; it never selects the primary comparator.
    Ties break on the model identifier so the result is deterministic.

    Args:
        metrics: Loaded system metrics keyed by ``(portfolio_set, model)``.
        portfolio_set: Asset set on which to rank the comparators.
        candidates: Registered non-short-rate comparator identifiers.

    Returns:
        The identifier of the lowest-RMSE candidate on that asset set.

    Raises:
        ValueError: If no candidate has a finite RMSE on the asset set.
    """
    ranked: list[tuple[float, str]] = []
    for model in candidates:
        system = metrics.get((portfolio_set, model))
        if system is None:
            continue
        if not math.isfinite(system.root_mean_squared_pricing_error):
            continue
        ranked.append((system.root_mean_squared_pricing_error, model))
    if not ranked:
        raise ValueError(
            f"no registered non-short-rate comparator is available for {portfolio_set}"
        )
    return min(ranked)[1]


def build_comparison_record(
    *,
    treatment: SystemMetrics,
    comparator: SystemMetrics,
    comparison_role: str,
    comparator_selection_rule: str,
    comparator_selected_after_observing_rmse: bool,
) -> dict[str, object]:
    """Build one flat comparison record with every gate value and threshold.

    Args:
        treatment: Short-rate system being evaluated.
        comparator: Comparator system on the identical asset-date intersection.
        comparison_role: ``"primary"`` or ``"secondary_adversarial"``.
        comparator_selection_rule: Registered rule that produced this comparator.
        comparator_selected_after_observing_rmse: Whether the comparator was
            picked after RMSE was observed, which implies model-selection
            uncertainty.

    Returns:
        A flat record carrying the gate values, thresholds, pass flags, the
        registered classification, and the multiplicity status.

    Raises:
        ValueError: If the two systems are not on an identical asset-date intersection.
    """
    gates = evaluate_materiality_gates(treatment, comparator)
    classification = classify_gates(gates)

    record: dict[str, object] = {
        "portfolio_set": treatment.portfolio_set,
        "is_headline_asset_set": treatment.portfolio_set == HEADLINE_ASSET_SET,
        "comparison_role": comparison_role,
        "treatment_model": treatment.model,
        "treatment_role": SHORT_RATE_MODEL_ROLES.get(treatment.model, "unregistered_specification"),
        "comparator_model": comparator.model,
        "comparator_selection_rule": comparator_selection_rule,
        "comparator_selected_after_observing_rmse": comparator_selected_after_observing_rmse,
        "model_selection_uncertainty": (
            MODEL_SELECTION_UNCERTAINTY_NOTE if comparator_selected_after_observing_rmse else "none"
        ),
        "n_assets": treatment.n_assets,
        "n_months": treatment.n_months,
        "common_intersection_verified": True,
    }
    for gate in gates:
        record[f"{gate.gate}__treatment_value"] = gate.treatment_value
        record[f"{gate.gate}__comparator_value"] = gate.comparator_value
        record[f"{gate.gate}__observed"] = gate.observed
        record[f"{gate.gate}__threshold"] = gate.threshold
        record[f"{gate.gate}__comparison"] = gate.comparison
        record[f"{gate.gate}__passed"] = gate.passed
    record["n_gates_passed"] = sum(gate.passed for gate in gates)
    record["n_gates_total"] = len(gates)
    record["classification"] = classification
    record["classification_interpretation"] = CLASSIFICATION_INTERPRETATIONS[classification]
    record["multiplicity_family"] = MULTIPLICITY_FAMILY
    record["p_value_generated"] = False
    record["holm_adjustment_applied"] = False
    record["holm_status"] = HOLM_STATUS_NOTE
    record["replication_status"] = REPLICATION_STATUS
    return record


def build_primary_records(
    metrics: Mapping[tuple[str, str], SystemMetrics],
    portfolio_sets: Sequence[str],
) -> list[dict[str, object]]:
    """Build the primary CAPM comparison records for every asset set.

    Args:
        metrics: Loaded system metrics keyed by ``(portfolio_set, model)``.
        portfolio_sets: Asset sets to evaluate, in report order.

    Returns:
        One record per asset set and registered short-rate specification.

    Raises:
        KeyError: If a required system is absent from the baseline metrics.
    """
    records: list[dict[str, object]] = []
    for portfolio_set in portfolio_sets:
        comparator = metrics[portfolio_set, PRIMARY_COMPARATOR]
        for model in SHORT_RATE_MODEL_ROLES:
            records.append(
                build_comparison_record(
                    treatment=metrics[portfolio_set, model],
                    comparator=comparator,
                    comparison_role="primary",
                    comparator_selection_rule=PRIMARY_COMPARATOR_SELECTION_RULE,
                    comparator_selected_after_observing_rmse=False,
                )
            )
    return records


def build_secondary_records(
    metrics: Mapping[tuple[str, str], SystemMetrics],
    portfolio_sets: Sequence[str],
) -> list[dict[str, object]]:
    """Build the secondary adversarial comparison records for every asset set.

    Args:
        metrics: Loaded system metrics keyed by ``(portfolio_set, model)``.
        portfolio_sets: Asset sets to evaluate, in report order.

    Returns:
        One record per asset set and registered short-rate specification,
        against the strongest observed non-short-rate comparator.

    Raises:
        KeyError: If a required system is absent from the baseline metrics.
        ValueError: If no registered non-short-rate comparator is available.
    """
    records: list[dict[str, object]] = []
    for portfolio_set in portfolio_sets:
        strongest = select_strongest_comparator(metrics, portfolio_set)
        comparator = metrics[portfolio_set, strongest]
        for model in SHORT_RATE_MODEL_ROLES:
            records.append(
                build_comparison_record(
                    treatment=metrics[portfolio_set, model],
                    comparator=comparator,
                    comparison_role="secondary_adversarial",
                    comparator_selection_rule=STRONGEST_COMPARATOR_SELECTION_RULE,
                    comparator_selected_after_observing_rmse=True,
                )
            )
    return records


def _diagnostics_payload(
    primary_records: Sequence[Mapping[str, object]],
    secondary_records: Sequence[Mapping[str, object]],
    portfolio_sets: Sequence[str],
) -> dict[str, object]:
    """Assemble the per-asset-set diagnostics payload.

    Args:
        primary_records: Primary CAPM comparison records.
        secondary_records: Secondary adversarial comparison records.
        portfolio_sets: Asset sets in report order.

    Returns:
        A JSON-serializable payload keyed by asset set, then comparison role,
        then treatment model.
    """
    per_asset_set: dict[str, object] = {}
    for portfolio_set in portfolio_sets:
        primary = {
            str(record["treatment_model"]): dict(record)
            for record in primary_records
            if record["portfolio_set"] == portfolio_set
        }
        secondary = {
            str(record["treatment_model"]): dict(record)
            for record in secondary_records
            if record["portfolio_set"] == portfolio_set
        }
        per_asset_set[portfolio_set] = {
            "is_headline_asset_set": portfolio_set == HEADLINE_ASSET_SET,
            "primary_comparison": primary,
            "secondary_adversarial_comparison": secondary,
            "h1_primary_classification": primary[BASELINE_SHORT_RATE_MODEL]["classification"],
        }
    return {
        "script": SCRIPT_NAME,
        "hypothesis": "H1",
        "replication_status": REPLICATION_STATUS,
        "headline_asset_set": HEADLINE_ASSET_SET,
        "primary_comparator": {
            "model": PRIMARY_COMPARATOR,
            "selection_rule": PRIMARY_COMPARATOR_SELECTION_RULE,
            "selected_after_observing_rmse": False,
        },
        "short_rate_models": dict(SHORT_RATE_MODEL_ROLES),
        "registered_non_short_rate_comparators": list(REGISTERED_NON_SHORT_RATE_COMPARATORS),
        "thresholds": {
            GATE_RMSE: {
                "threshold": RMSE_RELATIVE_REDUCTION_THRESHOLD,
                "comparison": RELATIVE_REDUCTION,
                "units": "fraction_of_comparator_rmse",
            },
            GATE_MAE: {
                "threshold": MAE_RELATIVE_REDUCTION_THRESHOLD,
                "comparison": RELATIVE_REDUCTION,
                "units": "fraction_of_comparator_mae",
            },
            GATE_MAX_ABSOLUTE_ERROR: {
                "threshold": MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD,
                "comparison": ABSOLUTE_REDUCTION,
                "units": "monthly_percentage_points",
            },
        },
        "decision_rule": (
            "H1 is supported against the primary comparator only if all three primary "
            "gates hold jointly on the identical asset-date intersection."
        ),
        "multiplicity": {
            "family": MULTIPLICITY_FAMILY,
            "registered_adjustment": "holm_for_secondary_p_values",
            "p_value_generated": False,
            "holm_adjustment_applied": False,
            "status": HOLM_STATUS_NOTE,
        },
        "classification_vocabulary": dict(CLASSIFICATION_INTERPRETATIONS),
        "asset_sets": per_asset_set,
    }


def _as_float(value: object) -> float:
    """Coerce a comparison-record value to a float for display.

    Args:
        value: Numeric value taken from a comparison record.

    Returns:
        The value as a float.

    Raises:
        TypeError: If the value is not numeric.
    """
    if isinstance(value, int | float):
        return float(value)
    raise TypeError(f"expected a numeric comparison-record value, got {type(value)!r}")


def _flag(passed: object) -> str:
    """Render a gate pass flag for the printed table.

    Args:
        passed: Gate pass indicator from a comparison record.

    Returns:
        ``"PASS"`` when the gate holds and ``"fail"`` otherwise.
    """
    return "PASS" if bool(passed) else "fail"


def _print_gate_table(records: Sequence[Mapping[str, object]], title: str) -> None:
    """Print a fixed-width table of gate outcomes.

    Args:
        records: Comparison records to display.
        title: Heading printed above the table.

    Returns:
        None.
    """
    print(f"\n{title}")
    header = (
        f"{'portfolio_set':26s} {'short_rate_model':32s} {'comparator':16s} "
        f"{'dRMSE%':>8s} {'g1':>4s} {'dMAE%':>8s} {'g2':>4s} "
        f"{'dMaxAbs':>9s} {'g3':>4s}  {'classification':<14s}"
    )
    print(header)
    print("-" * len(header))
    for record in records:
        rmse_flag = _flag(record[f"{GATE_RMSE}__passed"])
        mae_flag = _flag(record[f"{GATE_MAE}__passed"])
        max_flag = _flag(record[f"{GATE_MAX_ABSOLUTE_ERROR}__passed"])
        print(
            f"{record['portfolio_set']!s:26s} "
            f"{record['treatment_model']!s:32s} "
            f"{record['comparator_model']!s:16s} "
            f"{_as_float(record[f'{GATE_RMSE}__observed']) * 100.0:8.2f} "
            f"{rmse_flag:>4s} "
            f"{_as_float(record[f'{GATE_MAE}__observed']) * 100.0:8.2f} "
            f"{mae_flag:>4s} "
            f"{_as_float(record[f'{GATE_MAX_ABSOLUTE_ERROR}__observed']):9.4f} "
            f"{max_flag:>4s}  "
            f"{record['classification']!s:<14s}"
        )


def main() -> None:
    """Run the registered H1 materiality comparison and write every artifact.

    Returns:
        None.

    Raises:
        FileNotFoundError: If the baseline risk-price table is absent.
        ValueError: If the baseline table is malformed or a comparison is not on
            an identical asset-date intersection.
    """
    if not BASELINE_RISK_PRICES_CSV.is_file():
        raise FileNotFoundError(BASELINE_RISK_PRICES_CSV)

    frame = pd.read_csv(BASELINE_RISK_PRICES_CSV)
    metrics = load_system_metrics(frame)

    observed_sets = list(dict.fromkeys(str(value) for value in frame["portfolio_set"]))
    portfolio_sets = [HEADLINE_ASSET_SET] + [
        name for name in observed_sets if name != HEADLINE_ASSET_SET
    ]

    primary_records = build_primary_records(metrics, portfolio_sets)
    secondary_records = build_secondary_records(metrics, portfolio_sets)

    for path in (
        PRIMARY_COMPARISON_CSV,
        SECONDARY_ADVERSARIAL_CSV,
        DIAGNOSTICS_JSON,
        PROVENANCE_JSON,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame.from_records(primary_records).to_csv(
        PRIMARY_COMPARISON_CSV, index=False, lineterminator="\n"
    )
    pd.DataFrame.from_records(secondary_records).to_csv(
        SECONDARY_ADVERSARIAL_CSV, index=False, lineterminator="\n"
    )

    DIAGNOSTICS_JSON.write_text(
        json.dumps(
            _diagnostics_payload(primary_records, secondary_records, portfolio_sets),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    inputs = {
        path.as_posix(): _sha256(path)
        for path in (BASELINE_RISK_PRICES_CSV, BASELINE_PRICING_ERRORS_PARQUET)
        if path.is_file()
    }
    PROVENANCE_JSON.write_text(
        json.dumps(
            {
                "script": SCRIPT_NAME,
                "hypothesis": "H1",
                "replication_status": REPLICATION_STATUS,
                "inputs": inputs,
                "outputs": {
                    path.as_posix(): _sha256(path)
                    for path in (
                        PRIMARY_COMPARISON_CSV,
                        SECONDARY_ADVERSARIAL_CSV,
                        DIAGNOSTICS_JSON,
                    )
                },
                "thresholds": {
                    GATE_RMSE: RMSE_RELATIVE_REDUCTION_THRESHOLD,
                    GATE_MAE: MAE_RELATIVE_REDUCTION_THRESHOLD,
                    GATE_MAX_ABSOLUTE_ERROR: MAX_ABSOLUTE_ERROR_REDUCTION_THRESHOLD,
                },
                "threshold_source": "research/economic_thresholds.md",
                "primary_comparator": PRIMARY_COMPARATOR,
                "primary_comparator_selection_rule": PRIMARY_COMPARATOR_SELECTION_RULE,
                "strongest_comparator_selection_rule": STRONGEST_COMPARATOR_SELECTION_RULE,
                "strongest_observed_comparator": {
                    portfolio_set: select_strongest_comparator(metrics, portfolio_set)
                    for portfolio_set in portfolio_sets
                },
                "multiplicity_family": MULTIPLICITY_FAMILY,
                "holm_status": HOLM_STATUS_NOTE,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )

    _print_gate_table(
        primary_records,
        "H1 primary materiality gates versus the ex ante CAPM comparator",
    )
    _print_gate_table(
        secondary_records,
        "H1 secondary adversarial gates versus the strongest observed non-short-rate comparator",
    )

    print(
        "\nGate legend: g1 RMSE at least 10 percent lower; g2 MAE at least 10 percent lower; "
        "g3 maximum absolute pricing error at least 0.25 monthly percentage points lower."
    )
    print(f"Secondary comparator selection: {MODEL_SELECTION_UNCERTAINTY_NOTE}")
    print(f"Multiplicity: {HOLM_STATUS_NOTE}")

    headline = next(
        record
        for record in primary_records
        if record["portfolio_set"] == HEADLINE_ASSET_SET
        and record["treatment_model"] == BASELINE_SHORT_RATE_MODEL
    )
    print(
        f"\nHeadline asset set {HEADLINE_ASSET_SET}: registered H1 primary classification is "
        f"{headline['classification']} "
        f"({headline['n_gates_passed']}/{headline['n_gates_total']} primary gates passed)."
    )
    print(f"Wrote {PRIMARY_COMPARISON_CSV}, {SECONDARY_ADVERSARIAL_CSV}, {DIAGNOSTICS_JSON}")


if __name__ == "__main__":
    main()
