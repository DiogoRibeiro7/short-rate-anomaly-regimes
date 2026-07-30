from pathlib import Path

import pytest

from short_rate_anomaly_regimes.config import ConfigError, load_baseline_config, load_yaml


def test_baseline_config_loads() -> None:
    config = load_baseline_config(Path("configs/baseline.yaml"))
    assert config.sample.start == "1972-01"
    assert config.sample.end == "2013-12"
    assert config.project.replication_mode == "strict"
    assert "size_book_to_market_25" in config.portfolio_sets


def test_load_yaml_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="does not exist"):
        load_yaml(tmp_path / "missing.yaml")


def test_load_yaml_rejects_non_mapping(tmp_path: Path) -> None:
    config_path = tmp_path / "list.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="must contain a mapping"):
        load_yaml(config_path)


def test_baseline_config_rejects_non_monthly_frequency(tmp_path: Path) -> None:
    config_path = tmp_path / "baseline.yaml"
    config_path.write_text(
        """
project:
  name: test
  replication_mode: strict
  random_seed: 1
sample:
  frequency: daily
  start: "2020-01"
  end: "2020-12"
portfolio_sets: []
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="monthly data"):
        load_baseline_config(config_path)
