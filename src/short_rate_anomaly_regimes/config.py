"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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


class RegimeSensitivityConfig(BaseModel):
    """Regime-boundary sensitivity settings."""

    model_config = ConfigDict(extra="forbid")

    boundary_shifts_months: list[int]
    alternative_rules: list[str]


class RegimeDefinitionConfig(BaseModel):
    """Regime labelling configuration."""

    model_config = ConfigDict(extra="forbid")

    primary: str
    regimes: list[RegimeIntervalConfig]
    sensitivity: RegimeSensitivityConfig


class RegimeConfig(BaseModel):
    """Validated monetary-regime configuration."""

    model_config = ConfigDict(extra="forbid")

    base_config: str
    sample: RegimeSampleConfig
    regime_definition: RegimeDefinitionConfig
    models: list[str]
    structural_break_tests: list[str]
    minimum_regime_observations: int = Field(gt=0)
    multiple_testing_adjustment: str


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
