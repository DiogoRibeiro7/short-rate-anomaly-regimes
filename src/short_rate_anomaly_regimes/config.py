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
    asset_pricing: AssetPricingConfig
    comparators: list[str]
    reporting: BaselineReportingConfig


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


class RegimeEligibilityTierConfig(BaseModel):
    """One frozen regime-estimation eligibility tier."""

    model_config = ConfigDict(extra="forbid")

    id: str
    condition: str
    permitted: str


class RegimeEstimationEligibilityConfig(BaseModel):
    """Frozen minimum requirements for regime-specific estimation."""

    model_config = ConfigDict(extra="forbid")

    minimum_months_for_regime_specific_estimation: int = Field(gt=0)
    minimum_months_for_standalone_second_pass: int = Field(gt=0)
    minimum_test_assets_for_standalone_second_pass: int = Field(gt=0)
    required_beta_matrix_rank: str
    short_sample_flag_band_months: list[int] = Field(min_length=2, max_length=2)
    below_minimum_treatment: str
    tiers: list[RegimeEligibilityTierConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> RegimeEstimationEligibilityConfig:
        """Require the second-pass floor to be at least the first-pass floor."""
        if (
            self.minimum_months_for_standalone_second_pass
            < self.minimum_months_for_regime_specific_estimation
        ):
            raise ValueError(
                "minimum_months_for_standalone_second_pass must be at least "
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
