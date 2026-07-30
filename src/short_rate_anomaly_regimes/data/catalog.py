"""Typed source-registry access."""

from __future__ import annotations

from pathlib import Path

import duckdb
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


def create_catalog_tables(catalog_path: Path) -> None:
    """Create the DuckDB catalog schema idempotently."""
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute(
            """
            create table if not exists sources (
                source_id varchar primary key,
                category varchar not null,
                provider varchar,
                access varchar not null,
                frequency varchar,
                required_for_strict_replication boolean not null,
                raw_path varchar,
                expected_path varchar,
                licence_note varchar,
                exact_series_status varchar
            )
            """
        )
        connection.execute(
            """
            create table if not exists raw_files (
                source_id varchar not null,
                raw_path varchar not null,
                sha256 varchar not null,
                retrieved_at_utc varchar not null,
                url varchar,
                etag varchar,
                last_modified varchar
            )
            """
        )
        connection.execute(
            """
            create table if not exists transformations (
                transformation_id varchar primary key,
                source_id varchar not null,
                input_path varchar not null,
                output_path varchar not null,
                code_version varchar not null,
                created_at_utc varchar not null
            )
            """
        )
        connection.execute(
            """
            create table if not exists schemas (
                source_id varchar primary key,
                date_column varchar,
                expected_columns varchar,
                units varchar,
                sample_start varchar,
                sample_end varchar
            )
            """
        )
        connection.execute(
            """
            create table if not exists validation_results (
                validation_id varchar primary key,
                source_id varchar not null,
                status varchar not null,
                checked_at_utc varchar not null,
                rows integer,
                columns integer,
                missing_values integer,
                message varchar
            )
            """
        )
        connection.execute(
            """
            create table if not exists run_artifacts (
                artifact_id varchar primary key,
                run_id varchar not null,
                artifact_path varchar not null,
                sha256 varchar,
                created_at_utc varchar not null
            )
            """
        )


def build_catalog(catalog_path: Path, registry: SourceRegistry) -> None:
    """Build or refresh source metadata in the DuckDB catalog."""
    create_catalog_tables(catalog_path)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute("delete from sources")
        rows = [
            (
                source.id,
                source.category,
                source.provider,
                source.access,
                source.frequency,
                source.required_for_strict_replication,
                source.raw_path,
                source.expected_path,
                source.licence_note,
                source.exact_series_status,
            )
            for source in registry.sources
        ]
        connection.executemany(
            """
            insert into sources (
                source_id,
                category,
                provider,
                access,
                frequency,
                required_for_strict_replication,
                raw_path,
                expected_path,
                licence_note,
                exact_series_status
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
