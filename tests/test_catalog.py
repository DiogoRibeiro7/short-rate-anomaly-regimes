from pathlib import Path

import pytest

from short_rate_anomaly_regimes.data.catalog import load_registry


def test_source_registry_loads_known_source() -> None:
    registry = load_registry(Path("configs/data_sources.yaml"))

    source = registry.by_id("french_mkt_rf")

    assert registry.version == 1
    assert source.category == "factor_returns"
    assert source.required_for_strict_replication is True


def test_source_registry_rejects_missing_source_id() -> None:
    registry = load_registry(Path("configs/data_sources.yaml"))

    with pytest.raises(KeyError, match="missing_source"):
        registry.by_id("missing_source")
