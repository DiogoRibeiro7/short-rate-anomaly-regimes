from pathlib import Path

import pytest

from short_rate_anomaly_regimes.data.catalog import load_registry


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
