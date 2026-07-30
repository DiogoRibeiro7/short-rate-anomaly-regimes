from pathlib import Path

from short_rate_anomaly_regimes.config import load_baseline_config


def test_baseline_config_loads() -> None:
    config = load_baseline_config(Path("configs/baseline.yaml"))
    assert config.sample.start == "1972-01"
    assert config.sample.end == "2013-12"
    assert config.project.replication_mode == "strict"
    assert "size_book_to_market_25" in config.portfolio_sets
