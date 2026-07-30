"""Configuration loading and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


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

    model_config = ConfigDict(extra="allow")

    name: str
    replication_mode: str = Field(pattern="^(strict|reconstruction)$")
    random_seed: int


class BaselineConfig(BaseModel):
    """Validated subset of the baseline configuration."""

    model_config = ConfigDict(extra="allow")

    project: ProjectConfig
    sample: SampleConfig
    portfolio_sets: list[str]


class ConfigError(RuntimeError):
    """Raised when a configuration cannot be loaded or validated."""


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
