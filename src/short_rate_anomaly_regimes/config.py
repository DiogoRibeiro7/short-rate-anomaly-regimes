"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from short_rate_anomaly_regimes.exceptions import ConfigurationError


class ConfigError(ConfigurationError):
    """Backward-compatible alias for configuration loading failures."""


class SampleConfig(BaseModel):
    """Monthly sample definition."""

    model_config = ConfigDict(extra="forbid")

    frequency: str = "monthly"
    start: str
    end: str
    date_alignment: str = "month_end"

    @model_validator(mode="after")
    def validate_frequency(self) -> SampleConfig:
        """Reject unsupported frequencies in the baseline pipeline."""
        if self.frequency != "monthly":
            raise ValueError("The baseline replication currently requires monthly data")
        return self


class ProjectConfig(BaseModel):
    """Top-level project settings."""

    model_config = ConfigDict(extra="forbid")

    name: str
    replication_mode: str = Field(pattern="^(strict|reconstruction)$")
    random_seed: int


class ReturnsConfig(BaseModel):
    """Return-series conventions."""

    model_config = ConfigDict(extra="forbid")

    units: str
    excess_return_definition: str
    weighting: str


class MarketFactorConfig(BaseModel):
    """Market-factor source selection."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    column: str


class ShortRateInnovationConfig(BaseModel):
    """Short-rate innovation model settings."""

    model_config = ConfigDict(extra="forbid")

    model: str
    estimation: str
    residual_timing: str
    standardize: bool
    timing_variant: Literal["pre_window_lag", "within_window_lag"]
    timing_variant_sensitivity: Literal["pre_window_lag", "within_window_lag"]
    timing_variant_evidence: str
    intercept_comparison_units: Literal["decimal_rate_units", "percentage_points"]

    @model_validator(mode="after")
    def validate_distinct_timing_variants(self) -> ShortRateInnovationConfig:
        """Require the sensitivity variant to differ from the primary variant."""
        if self.timing_variant == self.timing_variant_sensitivity:
            raise ValueError("timing_variant_sensitivity must differ from timing_variant")
        return self


class ShortRateConfig(BaseModel):
    """Primary and alternative short-rate factors."""

    model_config = ConfigDict(extra="forbid")

    primary_series: str
    alternatives: list[str]
    innovation: ShortRateInnovationConfig


class TimeSeriesConfig(BaseModel):
    """Time-series regression settings."""

    model_config = ConfigDict(extra="forbid")

    include_intercept: bool
    covariance: str
    nw_lags: int | str


class CrossSectionConfig(BaseModel):
    """Cross-sectional pricing settings."""

    model_config = ConfigDict(extra="forbid")

    estimators: list[str]
    include_zero_beta_intercept: bool
    shanken_correction: bool
    weak_factor_diagnostics: bool


class AssetPricingConfig(BaseModel):
    """Asset-pricing estimator configuration."""

    model_config = ConfigDict(extra="forbid")

    time_series: TimeSeriesConfig
    cross_section: CrossSectionConfig


class BaselineReportingConfig(BaseModel):
    """Formatting conventions for baseline tables."""

    model_config = ConfigDict(extra="forbid")

    decimals: int
    t_stat_decimals: int
    significance_levels: list[float]


class BaselineConfig(BaseModel):
    """Validated subset of the baseline configuration."""

    model_config = ConfigDict(extra="forbid")

    project: ProjectConfig
    sample: SampleConfig
    returns: ReturnsConfig
    market_factor: MarketFactorConfig
    short_rate: ShortRateConfig
    portfolio_sets: list[str]
    supplement_portfolio_sets: list[str] = Field(default_factory=list)
    asset_pricing: AssetPricingConfig
    comparators: list[str]
    reporting: BaselineReportingConfig

    @model_validator(mode="after")
    def validate_portfolio_sets_are_disjoint(self) -> BaselineConfig:
        """Reject a supplement set that is also declared as a baseline test asset."""
        overlap = sorted(set(self.portfolio_sets) & set(self.supplement_portfolio_sets))
        if overlap:
            raise ValueError(
                "portfolio_sets and supplement_portfolio_sets must be disjoint; "
                f"both declare {', '.join(overlap)}"
            )
        return self


class ShockIdentificationConfig(BaseModel):
    """Shock-decomposition identification settings."""

    model_config = ConfigDict(extra="forbid")

    primary: str
    alternatives: list[str]


class TemporalDataFreezeConfig(BaseModel):
    """Temporal-extension vintage and cutoff metadata."""

    model_config = ConfigDict(extra="forbid")

    baseline_start: str
    baseline_end: str
    extension_start: str
    latest_common_month: str
    retrieval_date: str
    baseline_vintage_label: str
    extension_vintage_label: str
    revision_policy: str = Field(pattern="^audit_separately$")
    compatible_portfolio_sets: list[str]


class ShockDecompositionConfig(BaseModel):
    """High-frequency shock decomposition settings."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    #: Set when the design is withdrawn rather than merely switched off. A
    #: disabled gate might be re-enabled; a retired one has a recorded reason
    #: that must travel with it, so the two states are not the same field.
    retired: bool = False
    retirement_reason: str | None = None
    selected_dataset_id: str
    selected_dataset_source: str
    raw_event_path: str
    identification: ShockIdentificationConfig
    event_window_minutes: int = Field(gt=0)
    aggregation: str
    preserve_policy_and_information_components: bool


class OutOfSampleConfig(BaseModel):
    """Out-of-sample evaluation settings."""

    model_config = ConfigDict(extra="forbid")

    initial_train_end: str
    expanding_window: bool
    refit_frequency_months: int = Field(gt=0)
    confirmatory_model: str
    factor_definition: str
    benchmarks: list[str]
    evaluation: list[str]


class RobustnessConfig(BaseModel):
    """Registered robustness families."""

    model_config = ConfigDict(extra="forbid")

    rate_innovation_models: list[str]
    covariance_estimators: list[str]
    portfolio_weightings: list[str]
    influential_observation_methods: list[str]


class ExtensionConfig(BaseModel):
    """Validated extension and robustness configuration."""

    model_config = ConfigDict(extra="forbid")

    data_freeze: TemporalDataFreezeConfig
    shock_decomposition: ShockDecompositionConfig
    out_of_sample: OutOfSampleConfig
    robustness: RobustnessConfig


class RegimeSampleConfig(BaseModel):
    """Regime extension sample settings."""

    model_config = ConfigDict(extra="forbid")

    start: str
    end: str


class RegimeIntervalConfig(BaseModel):
    """One deterministic monetary-policy regime interval."""

    model_config = ConfigDict(extra="forbid")

    id: str
    start: str
    end: str
    sensitivity_start: str | None = None
    sensitivity_end: str | None = None

    @model_validator(mode="after")
    def validate_sensitivity_pair(self) -> RegimeIntervalConfig:
        """Require the sensitivity boundaries to be declared as a complete pair.

        Returns:
            The validated regime interval.

        Raises:
            ValueError: If exactly one of the two sensitivity boundaries is declared.
        """
        declared = (self.sensitivity_start is not None, self.sensitivity_end is not None)
        if any(declared) and not all(declared):
            raise ValueError(
                f"Regime {self.id} must declare both sensitivity_start and sensitivity_end "
                "or neither; a single sensitivity boundary does not define an interval"
            )
        return self


class RegimeTransitionRuleConfig(BaseModel):
    """Primary and sensitivity transition-month assignment rules."""

    model_config = ConfigDict(extra="forbid")

    primary: Literal["first_full_month_after_policy_action"]
    sensitivity: Literal["whole_transition_month_belongs_to_new_regime"]
    note: str


class RegimeCombinationConfig(BaseModel):
    """One predeclared combination of adjacent short regimes."""

    model_config = ConfigDict(extra="forbid")

    id: str
    members: list[str] = Field(min_length=2)
    role: str
    reason: str


class RegimeSensitivityConfig(BaseModel):
    """Regime-boundary sensitivity settings."""

    model_config = ConfigDict(extra="forbid")

    boundary_shifts_months: list[int]
    alternative_rules: list[str]


class RegimeDefinitionConfig(BaseModel):
    """Regime labelling configuration."""

    model_config = ConfigDict(extra="forbid")

    primary: str
    transition_rule: RegimeTransitionRuleConfig
    regimes: list[RegimeIntervalConfig]
    declared_combinations: list[RegimeCombinationConfig] = Field(default_factory=list)
    sensitivity: RegimeSensitivityConfig

    @model_validator(mode="after")
    def validate_declared_combinations(self) -> RegimeDefinitionConfig:
        """Require every declared combination to name one adjacent run of configured regimes.

        Returns:
            The validated regime definition.

        Raises:
            ValueError: If regime ids are not unique, or a combination names an
                unconfigured regime, repeats a member, or does not list a single
                consecutive run of regimes in the configured order.
        """
        order = {regime.id: position for position, regime in enumerate(self.regimes)}
        if len(order) != len(self.regimes):
            raise ValueError("regime ids must be unique")
        for combination in self.declared_combinations:
            unknown = [member for member in combination.members if member not in order]
            if unknown:
                raise ValueError(
                    f"Declared combination {combination.id} names unconfigured regimes: "
                    f"{', '.join(unknown)}"
                )
            if len(set(combination.members)) != len(combination.members):
                raise ValueError(f"Declared combination {combination.id} repeats a regime member")
            positions = [order[member] for member in combination.members]
            expected = list(range(positions[0], positions[0] + len(positions)))
            if positions != expected:
                raise ValueError(
                    f"Declared combination {combination.id} must list one consecutive run of "
                    "adjacent regimes in the configured regime order"
                )
        return self


class RegimeEligibilityTierConfig(BaseModel):
    """One frozen regime-estimation eligibility tier."""

    model_config = ConfigDict(extra="forbid")

    id: str
    condition: str
    permitted: str
    note: str | None = None


BLOCKED_TIER_ID_TEMPLATE = "blocked_for_regime_specific_estimation_below_{months}_months"
FIRST_PASS_ONLY_TIER_ID = "eligible_first_pass_with_short_sample_flag"
FIRST_AND_SECOND_PASS_TIER_ID = "eligible_first_pass_and_standalone_second_pass"


def _tier_ids_for_floor(minimum_months_for_regime_specific_estimation: int) -> tuple[str, str, str]:
    """Build the executable tier ids implied by the frozen first-pass month floor.

    Args:
        minimum_months_for_regime_specific_estimation: Frozen month floor below which
            regime-specific estimation is blocked.

    Returns:
        The blocked, first-pass-only and first-and-second-pass tier ids, in that order.
    """
    return (
        BLOCKED_TIER_ID_TEMPLATE.format(months=minimum_months_for_regime_specific_estimation),
        FIRST_PASS_ONLY_TIER_ID,
        FIRST_AND_SECOND_PASS_TIER_ID,
    )


class RegimeEstimationEligibilityConfig(BaseModel):
    """Frozen minimum requirements for regime-specific estimation."""

    model_config = ConfigDict(extra="forbid")

    minimum_months_for_regime_specific_estimation: int = Field(gt=0)
    minimum_months_for_standalone_second_pass: int = Field(gt=0)
    minimum_test_assets_for_standalone_second_pass: int = Field(gt=0)
    required_beta_matrix_rank: Literal["number_of_priced_factors"]
    short_sample_flag_band_months: list[int] = Field(min_length=2, max_length=2)
    below_minimum_treatment: str
    tiers: list[RegimeEligibilityTierConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> RegimeEstimationEligibilityConfig:
        """Require the second-pass floor to exceed the first-pass floor.

        Equal floors would force the short-sample band to run backwards, such as
        ``[36, 35]``, while the schema still requires a two-endpoint band.

        Returns:
            The validated eligibility configuration.

        Raises:
            ValueError: If the floors are not strictly ordered or the short-sample
                band does not span exactly the two floors.
        """
        if (
            self.minimum_months_for_standalone_second_pass
            <= self.minimum_months_for_regime_specific_estimation
        ):
            raise ValueError(
                "minimum_months_for_standalone_second_pass must be strictly greater than "
                "minimum_months_for_regime_specific_estimation"
            )
        lower, upper = self.short_sample_flag_band_months
        if lower != self.minimum_months_for_regime_specific_estimation:
            raise ValueError(
                "short_sample_flag_band_months must start at "
                "minimum_months_for_regime_specific_estimation"
            )
        if upper != self.minimum_months_for_standalone_second_pass - 1:
            raise ValueError(
                "short_sample_flag_band_months must end one month below "
                "minimum_months_for_standalone_second_pass"
            )
        return self

    @model_validator(mode="after")
    def validate_tier_ids(self) -> RegimeEstimationEligibilityConfig:
        """Require the declared tiers to be exactly the tiers the classifier can return.

        The human-readable ``condition`` strings stay in the configuration as the
        documentary record, but they are never parsed. This validator ties the frozen
        tier list to :func:`classify_regime_eligibility`, so a tier that no code can
        assign, or a classifier outcome that no tier declares, fails configuration
        loading instead of silently drifting apart.

        Returns:
            The validated eligibility configuration.

        Raises:
            ValueError: If the declared tier ids differ from the executable tier ids.
        """
        expected = _tier_ids_for_floor(self.minimum_months_for_regime_specific_estimation)
        declared = tuple(tier.id for tier in self.tiers)
        if declared != expected:
            raise ValueError(
                "regime_estimation_eligibility.tiers must declare exactly the executable "
                f"tier ids in order: {', '.join(expected)}"
            )
        return self


def eligibility_tier_ids(
    eligibility_config: RegimeEstimationEligibilityConfig,
) -> tuple[str, str, str]:
    """Return the eligibility tier ids implied by the frozen numeric thresholds.

    Args:
        eligibility_config: Frozen regime-estimation eligibility thresholds.

    Returns:
        The blocked, first-pass-only and first-and-second-pass tier ids, in that order.
    """
    return _tier_ids_for_floor(eligibility_config.minimum_months_for_regime_specific_estimation)


def classify_regime_eligibility(
    months: int,
    test_assets: int,
    beta_rank: int,
    n_priced_factors: int,
    eligibility_config: RegimeEstimationEligibilityConfig,
) -> str:
    """Classify one regime into its frozen estimation-eligibility tier.

    The tier follows only from the frozen numeric thresholds. A regime shorter than
    ``minimum_months_for_regime_specific_estimation`` is blocked from regime-specific
    estimation. A regime that also clears
    ``minimum_months_for_standalone_second_pass``,
    ``minimum_test_assets_for_standalone_second_pass`` and the full beta-matrix rank
    requirement earns the standalone second pass. Every other regime is first pass only:
    that covers the short-sample band and, defensively, a long regime that fails the
    test-asset or rank gate, because the frozen design permits its first-pass betas
    while blocking the standalone second pass.

    Args:
        months: Monthly observations available in the regime.
        test_assets: Test assets available for the regime second pass.
        beta_rank: Rank of the estimated regime beta matrix.
        n_priced_factors: Number of priced factors in the confirmatory model.
        eligibility_config: Frozen regime-estimation eligibility thresholds.

    Returns:
        The id of the frozen eligibility tier that applies to the regime.

    Raises:
        ValueError: If any count is negative or no factor is priced.
    """
    if min(months, test_assets, beta_rank) < 0:
        raise ValueError("months, test_assets and beta_rank must not be negative")
    if n_priced_factors <= 0:
        raise ValueError("n_priced_factors must be positive")
    blocked, first_pass_only, first_and_second_pass = eligibility_tier_ids(eligibility_config)
    if months < eligibility_config.minimum_months_for_regime_specific_estimation:
        return blocked
    if (
        months >= eligibility_config.minimum_months_for_standalone_second_pass
        and test_assets >= eligibility_config.minimum_test_assets_for_standalone_second_pass
        and beta_rank == n_priced_factors
    ):
        return first_and_second_pass
    return first_pass_only


class RegimeConfig(BaseModel):
    """Validated monetary-regime configuration."""

    model_config = ConfigDict(extra="forbid")

    base_config: str
    sample: RegimeSampleConfig
    regime_definition: RegimeDefinitionConfig
    regime_estimation_eligibility: RegimeEstimationEligibilityConfig
    models: list[str]
    structural_break_tests: list[str]
    minimum_regime_observations: int = Field(gt=0)
    multiple_testing_adjustment: str
    equivalence_rule: Literal["tost_5pct_90pct_interval"]

    @model_validator(mode="after")
    def validate_minimum_alignment(self) -> RegimeConfig:
        """Keep the legacy minimum aligned with the frozen eligibility floor."""
        floor = self.regime_estimation_eligibility.minimum_months_for_regime_specific_estimation
        if self.minimum_regime_observations != floor:
            raise ValueError(
                "minimum_regime_observations must equal "
                "regime_estimation_eligibility.minimum_months_for_regime_specific_estimation"
            )
        return self


class ReportingPipelineConfig(BaseModel):
    """Validated report-generation configuration."""

    model_config = ConfigDict(extra="forbid")

    input_config: str
    output_directory: str
    formats: list[str]
    figures: list[str]
    include_environment_manifest: bool
    include_data_checksums: bool
    include_replication_status: bool
    forbid_unlabelled_substitutions: bool


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk.

    Args:
        path: Existing YAML file.

    Returns:
        Parsed mapping.

    Raises:
        ConfigError: If the file is missing or does not contain a mapping.
    """
    if not path.is_file():
        raise ConfigError(f"Configuration file does not exist: {path}")
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ConfigError(f"Configuration must contain a mapping: {path}")
    return payload


def load_baseline_config(path: Path) -> BaselineConfig:
    """Load and validate the baseline research configuration."""
    return BaselineConfig.model_validate(load_yaml(path))


def load_extension_config(path: Path) -> ExtensionConfig:
    """Load and validate extension settings."""
    return ExtensionConfig.model_validate(load_yaml(path))


def load_regime_config(path: Path) -> RegimeConfig:
    """Load and validate monetary-regime settings."""
    return RegimeConfig.model_validate(load_yaml(path))


def load_reporting_config(path: Path) -> ReportingPipelineConfig:
    """Load and validate reporting settings."""
    return ReportingPipelineConfig.model_validate(load_yaml(path))


def load_project_config(path: Path) -> BaseModel:
    """Load one known project configuration based on its file name."""
    loaders = {
        "baseline.yaml": load_baseline_config,
        "extensions.yaml": load_extension_config,
        "regimes.yaml": load_regime_config,
        "reporting.yaml": load_reporting_config,
    }
    loader = loaders.get(path.name)
    if loader is None:
        raise ConfigError(f"Unknown project configuration file: {path.name}")
    return loader(path)
