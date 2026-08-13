from pathlib import Path
from typing import Any

import pytest

from short_rate_anomaly_regimes.config import (
    ConfigError,
    RegimeDefinitionConfig,
    RegimeEstimationEligibilityConfig,
    RegimeIntervalConfig,
    classify_regime_eligibility,
    eligibility_tier_ids,
    load_baseline_config,
    load_extension_config,
    load_project_config,
    load_regime_config,
    load_reporting_config,
    load_yaml,
)


def test_baseline_config_loads() -> None:
    config = load_baseline_config(Path("configs/baseline.yaml"))
    assert config.sample.start == "1972-01"
    assert config.sample.end == "2013-12"
    assert config.project.replication_mode == "strict"
    # The baseline test assets are the seven decile families, not the
    # supplement-only 25-portfolio double sorts.
    assert "book_to_market" in config.portfolio_sets
    assert len(config.portfolio_sets) == 7
    assert "size_book_to_market_25" in config.supplement_portfolio_sets
    assert not set(config.portfolio_sets) & set(config.supplement_portfolio_sets)
    assert config.asset_pricing.cross_section.shanken_correction is True


def test_all_project_configs_load() -> None:
    extension_config = load_extension_config(Path("configs/extensions.yaml"))
    regime_config = load_regime_config(Path("configs/regimes.yaml"))
    reporting_config = load_reporting_config(Path("configs/reporting.yaml"))

    assert extension_config.data_freeze.latest_common_month == "2025-12"
    assert extension_config.data_freeze.revision_policy == "audit_separately"
    # Retired 2026-08-11 on the pre-registered factor-strength condition. The
    # two flags are distinct: a disabled gate might be switched back on, a
    # retired one carries the reason it was withdrawn.
    assert extension_config.shock_decomposition.enabled is False
    assert extension_config.shock_decomposition.retired is True
    assert extension_config.shock_decomposition.retirement_reason
    assert (
        extension_config.shock_decomposition.selected_dataset_id
        == "jarocinski_karadi_fed_shocks_update_202401"
    )
    assert extension_config.out_of_sample.confirmatory_model == "two_factor_market_rate"
    assert "historical_mean" in extension_config.out_of_sample.benchmarks
    assert regime_config.minimum_regime_observations == 36
    assert reporting_config.include_environment_manifest is True
    assert load_project_config(Path("configs/baseline.yaml")).model_dump()


def test_load_yaml_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_yaml(tmp_path / "missing.yaml")


def test_load_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "list.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="must contain a mapping"):
        load_yaml(config_path)


def test_baseline_config_rejects_non_monthly_frequency(tmp_path: Path) -> None:
    config_path = tmp_path / "baseline.yaml"
    config_path.write_text(
        """
project:
  name: test
  replication_mode: strict
  random_seed: 1
sample:
  frequency: daily
  start: "2020-01"
  end: "2020-12"
portfolio_sets: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="monthly data"):
        load_baseline_config(config_path)


def test_baseline_config_rejects_unknown_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "baseline.yaml"
    config_path.write_text(
        """
project:
  name: test
  replication_mode: strict
  random_seed: 1
  surprise_field: forbidden
sample:
  frequency: monthly
  start: "2020-01"
  end: "2020-12"
returns:
  units: percent_per_month
  excess_return_definition: test
  weighting: value_weighted
market_factor:
  source_id: market
  column: Mkt-RF
short_rate:
  primary_series: fed
  alternatives: []
  innovation:
    model: ar1
    estimation: full_sample
    residual_timing: contemporaneous
    standardize: false
portfolio_sets: []
asset_pricing:
  time_series:
    include_intercept: true
    covariance: newey_west
    nw_lags: automatic
  cross_section:
    estimators: []
    include_zero_beta_intercept: false
    shanken_correction: true
    weak_factor_diagnostics: true
comparators: []
reporting:
  decimals: 4
  t_stat_decimals: 2
  significance_levels: [0.05]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_baseline_config(config_path)


def test_unknown_project_config_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "unknown.yaml"
    config_path.write_text("version: 1\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Unknown project configuration"):
        load_project_config(config_path)


def _regime_definition_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "primary": "deterministic_calendar",
        "transition_rule": {
            "primary": "first_full_month_after_policy_action",
            "sensitivity": "whole_transition_month_belongs_to_new_regime",
            "note": "test rule",
        },
        "regimes": [
            {"id": "alpha", "start": "2000-01", "end": "2004-12"},
            {"id": "beta", "start": "2005-01", "end": "2009-12"},
            {"id": "gamma", "start": "2010-01", "end": "2014-12"},
        ],
        "declared_combinations": [],
        "sensitivity": {"boundary_shifts_months": [-3, 3], "alternative_rules": []},
    }
    payload.update(overrides)
    return payload


def _combination(members: list[str]) -> dict[str, Any]:
    return {
        "id": "combo",
        "members": members,
        "role": "declared_combination_sensitivity",
        "reason": "test combination",
    }


def _eligibility_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "minimum_months_for_regime_specific_estimation": 36,
        "minimum_months_for_standalone_second_pass": 60,
        "minimum_test_assets_for_standalone_second_pass": 10,
        "required_beta_matrix_rank": "number_of_priced_factors",
        "short_sample_flag_band_months": [36, 59],
        "below_minimum_treatment": "pooled_regime_interaction_models_only",
        "tiers": [
            {
                "id": "blocked_for_regime_specific_estimation_below_36_months",
                "condition": "months < 36",
                "permitted": "pooled only",
            },
            {
                "id": "eligible_first_pass_with_short_sample_flag",
                "condition": "36 <= months < 60",
                "permitted": "first pass only",
            },
            {
                "id": "eligible_first_pass_and_standalone_second_pass",
                "condition": "months >= 60",
                "permitted": "first and second pass",
            },
        ],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def eligibility() -> RegimeEstimationEligibilityConfig:
    return RegimeEstimationEligibilityConfig.model_validate(_eligibility_payload())


def test_regime_interval_accepts_complete_sensitivity_pair() -> None:
    interval = RegimeIntervalConfig.model_validate(
        {
            "id": "alpha",
            "start": "2000-01",
            "end": "2004-12",
            "sensitivity_start": "1999-12",
            "sensitivity_end": "2004-11",
        }
    )

    assert interval.sensitivity_start == "1999-12"


def test_regime_interval_accepts_absent_sensitivity_pair() -> None:
    interval = RegimeIntervalConfig.model_validate(
        {"id": "alpha", "start": "2000-01", "end": "2004-12"}
    )

    assert interval.sensitivity_start is None
    assert interval.sensitivity_end is None


@pytest.mark.parametrize(
    "half",
    [{"sensitivity_start": "1999-12"}, {"sensitivity_end": "2004-11"}],
)
def test_regime_interval_rejects_half_declared_sensitivity_pair(half: dict[str, str]) -> None:
    with pytest.raises(ValueError, match="both sensitivity_start and sensitivity_end"):
        RegimeIntervalConfig.model_validate(
            {"id": "alpha", "start": "2000-01", "end": "2004-12", **half}
        )


def test_declared_combination_accepts_adjacent_members() -> None:
    definition = RegimeDefinitionConfig.model_validate(
        _regime_definition_payload(declared_combinations=[_combination(["beta", "gamma"])])
    )

    assert definition.declared_combinations[0].members == ["beta", "gamma"]


def test_declared_combination_rejects_unconfigured_member() -> None:
    with pytest.raises(ValueError, match="names unconfigured regimes"):
        RegimeDefinitionConfig.model_validate(
            _regime_definition_payload(declared_combinations=[_combination(["beta", "delta"])])
        )


def test_declared_combination_rejects_duplicate_members() -> None:
    with pytest.raises(ValueError, match="repeats a regime member"):
        RegimeDefinitionConfig.model_validate(
            _regime_definition_payload(declared_combinations=[_combination(["beta", "beta"])])
        )


@pytest.mark.parametrize("members", [["alpha", "gamma"], ["beta", "alpha"]])
def test_declared_combination_rejects_non_adjacent_members(members: list[str]) -> None:
    with pytest.raises(ValueError, match="one consecutive run"):
        RegimeDefinitionConfig.model_validate(
            _regime_definition_payload(declared_combinations=[_combination(members)])
        )


def test_regime_definition_rejects_duplicate_regime_ids() -> None:
    regimes = [
        {"id": "alpha", "start": "2000-01", "end": "2004-12"},
        {"id": "alpha", "start": "2005-01", "end": "2009-12"},
    ]

    with pytest.raises(ValueError, match="regime ids must be unique"):
        RegimeDefinitionConfig.model_validate(_regime_definition_payload(regimes=regimes))


def test_eligibility_rejects_equal_month_floors() -> None:
    payload = _eligibility_payload(
        minimum_months_for_standalone_second_pass=36,
        short_sample_flag_band_months=[36, 35],
    )

    with pytest.raises(ValueError, match="strictly greater"):
        RegimeEstimationEligibilityConfig.model_validate(payload)


def test_eligibility_rejects_lower_second_pass_floor() -> None:
    payload = _eligibility_payload(
        minimum_months_for_standalone_second_pass=24,
        short_sample_flag_band_months=[36, 23],
    )

    with pytest.raises(ValueError, match="strictly greater"):
        RegimeEstimationEligibilityConfig.model_validate(payload)


def test_eligibility_rejects_undeclarable_tier_id() -> None:
    tiers = _eligibility_payload()["tiers"]
    tiers[1] = {**tiers[1], "id": "eligible_first_pass_if_the_authors_feel_like_it"}

    with pytest.raises(ValueError, match="exactly the executable"):
        RegimeEstimationEligibilityConfig.model_validate(_eligibility_payload(tiers=tiers))


def test_eligibility_rejects_tier_id_inconsistent_with_month_floor() -> None:
    payload = _eligibility_payload(
        minimum_months_for_regime_specific_estimation=48,
        short_sample_flag_band_months=[48, 59],
    )

    with pytest.raises(ValueError, match="blocked_for_regime_specific_estimation_below_48_months"):
        RegimeEstimationEligibilityConfig.model_validate(payload)


def test_frozen_config_tier_ids_are_executable() -> None:
    regime_config = load_regime_config(Path("configs/regimes.yaml"))
    declared = tuple(tier.id for tier in regime_config.regime_estimation_eligibility.tiers)

    assert declared == eligibility_tier_ids(regime_config.regime_estimation_eligibility)


@pytest.mark.parametrize(
    ("months", "expected"),
    [
        (0, "blocked_for_regime_specific_estimation_below_36_months"),
        (35, "blocked_for_regime_specific_estimation_below_36_months"),
        (36, "eligible_first_pass_with_short_sample_flag"),
        (59, "eligible_first_pass_with_short_sample_flag"),
        (60, "eligible_first_pass_and_standalone_second_pass"),
        (600, "eligible_first_pass_and_standalone_second_pass"),
    ],
)
def test_classify_regime_eligibility_month_boundaries(
    months: int,
    expected: str,
    eligibility: RegimeEstimationEligibilityConfig,
) -> None:
    assert (
        classify_regime_eligibility(
            months=months,
            test_assets=25,
            beta_rank=2,
            n_priced_factors=2,
            eligibility_config=eligibility,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("test_assets", "expected"),
    [
        (9, "eligible_first_pass_with_short_sample_flag"),
        (10, "eligible_first_pass_and_standalone_second_pass"),
    ],
)
def test_classify_regime_eligibility_test_asset_gate(
    test_assets: int,
    expected: str,
    eligibility: RegimeEstimationEligibilityConfig,
) -> None:
    assert (
        classify_regime_eligibility(
            months=120,
            test_assets=test_assets,
            beta_rank=2,
            n_priced_factors=2,
            eligibility_config=eligibility,
        )
        == expected
    )


@pytest.mark.parametrize(
    ("beta_rank", "expected"),
    [
        (1, "eligible_first_pass_with_short_sample_flag"),
        (2, "eligible_first_pass_and_standalone_second_pass"),
        (3, "eligible_first_pass_with_short_sample_flag"),
    ],
)
def test_classify_regime_eligibility_rank_gate(
    beta_rank: int,
    expected: str,
    eligibility: RegimeEstimationEligibilityConfig,
) -> None:
    assert (
        classify_regime_eligibility(
            months=120,
            test_assets=25,
            beta_rank=beta_rank,
            n_priced_factors=2,
            eligibility_config=eligibility,
        )
        == expected
    )


def test_classify_regime_eligibility_short_regime_ignores_second_pass_gates(
    eligibility: RegimeEstimationEligibilityConfig,
) -> None:
    assert (
        classify_regime_eligibility(
            months=12,
            test_assets=25,
            beta_rank=2,
            n_priced_factors=2,
            eligibility_config=eligibility,
        )
        == "blocked_for_regime_specific_estimation_below_36_months"
    )


def test_classify_regime_eligibility_rejects_negative_counts(
    eligibility: RegimeEstimationEligibilityConfig,
) -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        classify_regime_eligibility(
            months=-1,
            test_assets=25,
            beta_rank=2,
            n_priced_factors=2,
            eligibility_config=eligibility,
        )


def test_classify_regime_eligibility_rejects_unpriced_model(
    eligibility: RegimeEstimationEligibilityConfig,
) -> None:
    with pytest.raises(ValueError, match="n_priced_factors must be positive"):
        classify_regime_eligibility(
            months=120,
            test_assets=25,
            beta_rank=2,
            n_priced_factors=0,
            eligibility_config=eligibility,
        )


def test_frozen_combination_members_are_adjacent_regimes() -> None:
    regime_config = load_regime_config(Path("configs/regimes.yaml"))
    definition = regime_config.regime_definition
    order = [regime.id for regime in definition.regimes]

    for combination in definition.declared_combinations:
        positions = [order.index(member) for member in combination.members]
        assert positions == list(range(positions[0], positions[0] + len(positions)))
