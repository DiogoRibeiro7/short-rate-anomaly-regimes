"""Typed source-registry access."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, model_validator

from short_rate_anomaly_regimes.config import load_yaml


class SourceSpec(BaseModel):
    """One source in the research data registry."""

    model_config = ConfigDict(extra="allow")

    id: str
    category: str
    access: str
    provider: str | None = None
    frequency: str | None = None
    expected_path: str | None = None
    licence_note: str | None = None
    series_candidates: list[str] | None = None
    exact_series_status: str | None = None
    raw_path: str | None = None
    required_for_strict_replication: bool = False


class SourceRegistry(BaseModel):
    """Validated source registry."""

    model_config = ConfigDict(extra="forbid")

    version: int
    sources: list[SourceSpec]

    @model_validator(mode="after")
    def validate_unique_source_ids(self) -> SourceRegistry:
        """Reject duplicate source identifiers."""
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Source registry contains duplicate source ids")
        return self

    def by_id(self, source_id: str) -> SourceSpec:
        """Return one source specification by identifier."""
        matches = [source for source in self.sources if source.id == source_id]
        if len(matches) != 1:
            raise KeyError(f"Expected one source with id {source_id!r}, found {len(matches)}")
        return matches[0]


def load_registry(path: Path) -> SourceRegistry:
    """Load and validate a source registry."""
    return SourceRegistry.model_validate(load_yaml(path))
