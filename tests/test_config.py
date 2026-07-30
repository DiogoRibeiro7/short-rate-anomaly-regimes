from pathlib import Path

import pytest

from short_rate_anomaly_regimes.config import (
    ConfigError,
    load_baseline_config,
    load_extension_config,
    load_project_config,
    load_regime_config,
    load_reporting_config,
    load_yaml,
)


def test_baseline_config_loads() -> None:
    config = load_baseline_config(Path("configs/baseline.yaml"))
    assert config.sample.start == "1972-01"
    assert config.sample.end == "2013-12"
    assert config.project.replication_mode == "strict"
    assert "size_book_to_market_25" in config.portfolio_sets
    assert config.asset_pricing.cross_section.shanken_correction is True


def test_all_project_configs_load() -> None:
    extension_config = load_extension_config(Path("configs/extensions.yaml"))
    regime_config = load_regime_config(Path("configs/regimes.yaml"))
    reporting_config = load_reporting_config(Path("configs/reporting.yaml"))

    assert extension_config.data_freeze.latest_common_month == "2026-06"
    assert extension_config.data_freeze.revision_policy == "audit_separately"
    assert extension_config.shock_decomposition.enabled is True
    assert regime_config.minimum_regime_observations == 36
    assert reporting_config.include_environment_manifest is True
    assert load_project_config(Path("configs/baseline.yaml")).model_dump()


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


def test_baseline_config_rejects_unknown_fields(tmp_path: Path) -> None:
    config_path = tmp_path / "baseline.yaml"
    config_path.write_text(
        """
project:
  name: test
  replication_mode: strict
  random_seed: 1
  surprise_field: forbidden
sample:
  frequency: monthly
  start: "2020-01"
  end: "2020-12"
returns:
  units: percent_per_month
  excess_return_definition: test
  weighting: value_weighted
market_factor:
  source_id: market
  column: Mkt-RF
short_rate:
  primary_series: fed
  alternatives: []
  innovation:
    model: ar1
    estimation: full_sample
    residual_timing: contemporaneous
    standardize: false
portfolio_sets: []
asset_pricing:
  time_series:
    include_intercept: true
    covariance: newey_west
    nw_lags: automatic
  cross_section:
    estimators: []
    include_zero_beta_intercept: true
    shanken_correction: true
    weak_factor_diagnostics: true
comparators: []
reporting:
  decimals: 4
  t_stat_decimals: 2
  significance_levels: [0.05]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        load_baseline_config(config_path)


def test_unknown_project_config_rejected(tmp_path: Path) -> None:
    config_path = tmp_path / "unknown.yaml"
    config_path.write_text("version: 1\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="Unknown project configuration"):
        load_project_config(config_path)
