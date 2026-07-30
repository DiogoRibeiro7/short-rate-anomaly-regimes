"""Typed source-registry access."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from short_rate_anomaly_regimes.config import load_yaml


class SourceSpec(BaseModel):
    """One source in the research data registry."""

    model_config = ConfigDict(extra="allow")

    id: str
    category: str
    access: str
    raw_path: str | None = None
    required_for_strict_replication: bool = False


class SourceRegistry(BaseModel):
    """Validated source registry."""

    model_config = ConfigDict(extra="forbid")

    version: int
    sources: list[SourceSpec]

    def by_id(self, source_id: str) -> SourceSpec:
        """Return one source specification by identifier."""
        matches = [source for source in self.sources if source.id == source_id]
        if len(matches) != 1:
            raise KeyError(f"Expected one source with id {source_id!r}, found {len(matches)}")
        return matches[0]


def load_registry(path: Path) -> SourceRegistry:
    """Load and validate a source registry."""
    return SourceRegistry.model_validate(load_yaml(path))
