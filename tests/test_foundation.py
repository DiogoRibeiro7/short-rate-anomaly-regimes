import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from short_rate_anomaly_regimes.environment import build_environment_manifest
from short_rate_anomaly_regimes.exceptions import (
    ConfigurationError,
    DataAccessError,
    DataValidationError,
    EstimationError,
    ReplicationBlockError,
    SRARError,
)
from short_rate_anomaly_regimes.run_logging import create_run_metadata, structured_log_record
from short_rate_anomaly_regimes.seed import bootstrap_indices, seed_everything


def test_project_exceptions_share_base_class() -> None:
    exception_types = [
        ConfigurationError,
        DataAccessError,
        DataValidationError,
        ReplicationBlockError,
        EstimationError,
    ]

    assert all(issubclass(exception_type, SRARError) for exception_type in exception_types)


def test_seed_everything_returns_reproducible_generator() -> None:
    first = seed_everything(20260730).normal(size=3)
    second = seed_everything(20260730).normal(size=3)

    np.testing.assert_allclose(first, second)


def test_bootstrap_indices_are_deterministic() -> None:
    first = bootstrap_indices(observations=5, draws=3, seed=7)
    second = bootstrap_indices(observations=5, draws=3, seed=7)

    np.testing.assert_array_equal(first, second)
    assert first.shape == (3, 5)
    assert first.min() >= 0
    assert first.max() < 5


def test_bootstrap_indices_reject_invalid_sizes() -> None:
    with pytest.raises(ValueError, match="observations"):
        bootstrap_indices(observations=0, draws=1, seed=1)
    with pytest.raises(ValueError, match="draws"):
        bootstrap_indices(observations=1, draws=0, seed=1)


def test_run_metadata_and_log_record_include_required_context(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project: test\n", encoding="utf-8")

    metadata = create_run_metadata(config_path=config_path, run_id="fixed-run")
    record = structured_log_record(level="INFO", message="validated config", metadata=metadata)

    assert record["run_id"] == "fixed-run"
    assert record["message"] == "validated config"
    assert len(record["config_checksum"]) == 64
    assert datetime.fromisoformat(record["created_at_utc"]).tzinfo is not None
    assert datetime.fromisoformat(record["timestamp_utc"]).tzinfo is not None


def test_environment_manifest_contains_reproducibility_context(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("project: test\n", encoding="utf-8")

    manifest = build_environment_manifest(config_paths=(config_path,))
    payload = json.loads(json.dumps(manifest))

    assert payload["python"]["version"]
    assert payload["os"]["system"]
    assert payload["git"]["commit"]
    assert payload["config_hashes"][str(config_path)]
    assert "numpy_show_config" in payload["blas"]
