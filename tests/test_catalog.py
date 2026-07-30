from pathlib import Path

import duckdb
import pytest

from short_rate_anomaly_regimes.data.catalog import build_catalog, load_registry


def test_source_registry_loads_known_source() -> None:
    registry = load_registry(Path("configs/data_sources.yaml"))

    source = registry.by_id("french_mkt_rf")

    assert registry.version == 1
    assert source.category == "factor_returns"
    assert source.required_for_strict_replication is True
    assert source.provider == "Kenneth French Data Library"


def test_source_registry_rejects_missing_source_id() -> None:
    registry = load_registry(Path("configs/data_sources.yaml"))

    with pytest.raises(KeyError, match="missing_source"):
        registry.by_id("missing_source")


def test_source_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    registry_path = tmp_path / "data_sources.yaml"
    registry_path.write_text(
        """
version: 1
sources:
  - id: duplicate
    category: factor_returns
    access: public
  - id: duplicate
    category: short_rate
    access: public
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate source ids"):
        load_registry(registry_path)


def test_build_catalog_creates_duckdb_tables(tmp_path: Path) -> None:
    registry = load_registry(Path("configs/data_sources.yaml"))
    catalog_path = tmp_path / "catalog.duckdb"

    build_catalog(catalog_path, registry)
    build_catalog(catalog_path, registry)

    with duckdb.connect(str(catalog_path)) as connection:
        source_count = connection.execute("select count(*) from sources").fetchone()
        table_names = {
            row[0]
            for row in connection.execute(
                "select table_name from information_schema.tables"
            ).fetchall()
        }

    assert source_count == (12,)
    assert {
        "sources",
        "raw_files",
        "transformations",
        "schemas",
        "validation_results",
        "run_artifacts",
    }.issubset(table_names)
