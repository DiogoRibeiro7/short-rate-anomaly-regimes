from pathlib import Path

import pandas as pd
import pytest

from short_rate_anomaly_regimes.reporting.audit import (
    DISCREPANCY_INVESTIGATION_ORDER,
    TableAuditRecord,
    TableTarget,
    audit_summary,
    build_missing_input_audit,
    compare_statistic,
    is_accessible_access_status,
    load_table_targets,
    render_replication_report,
    tolerance_from_rule,
    write_audit,
    write_audit_json,
    write_replication_report,
)
from short_rate_anomaly_regimes.types import ReplicationStatus


def _target() -> TableTarget:
    return TableTarget(
        target_id="TBL_001",
        source_location="article_pdf:p.936:Table 1",
        description="Factor descriptive statistic",
        portfolio_set="all_factors",
        model="icapm",
        estimator="descriptive",
        tolerance_rule="published_rounding",
        status="article_extracted",
    )


def test_load_table_targets_reads_manifest() -> None:
    targets = load_table_targets(Path("research/table_target_manifest.csv"))

    assert targets[0].target_id == "TBL_001"
    assert targets[-1].target_id == "APP_TBL_A14"
    assert len({target.target_id for target in targets}) == len(targets)


def test_load_table_targets_rejects_missing_columns_and_duplicates(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.csv"
    missing_path.write_text("target_id\nTBL_001\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing columns"):
        load_table_targets(missing_path)

    duplicate_path = tmp_path / "duplicate.csv"
    duplicate_path.write_text(
        "target_id,source_location,description,portfolio_set,model,estimator,tolerance_rule,status\n"
        "TBL_001,loc,desc,set,model,est,published_rounding,status\n"
        "TBL_001,loc,desc,set,model,est,published_rounding,status\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate"):
        load_table_targets(duplicate_path)


def test_tolerance_from_rule_returns_predeclared_values() -> None:
    assert tolerance_from_rule("published_rounding") == pytest.approx(5e-4)
    assert tolerance_from_rule("coefficient_rounding") == pytest.approx(5e-5)
    with pytest.raises(ValueError, match="Unsupported"):
        tolerance_from_rule("unregistered")


def test_compare_statistic_assigns_reproduced_within_tolerance() -> None:
    record = compare_statistic(
        target=_target(),
        statistic="mean",
        published_value=0.1234,
        replicated_value=0.12345,
        generated_artifact=Path("artifacts/tables/factors/table.csv"),
        independent_check="matrix_verified",
    )

    assert record.status == ReplicationStatus.REPRODUCED
    assert record.absolute_difference == pytest.approx(0.00005)
    assert record.discrepancy_stage is None
    assert record.independent_check == "matrix_verified"


def test_compare_statistic_labels_reconstructed_close_match_as_approximate() -> None:
    record = compare_statistic(
        target=_target(),
        statistic="mean",
        published_value=1.0,
        replicated_value=1.0001,
        generated_artifact=Path("artifact.csv"),
        reconstructed=True,
    )

    assert record.status == ReplicationStatus.APPROXIMATELY_REPRODUCED


def test_compare_statistic_assigns_contradicted_outside_tolerance() -> None:
    record = compare_statistic(
        target=_target(),
        statistic="mean",
        published_value=1.0,
        replicated_value=1.2,
        generated_artifact=Path("artifact.csv"),
    )

    assert record.status == ReplicationStatus.CONTRADICTED
    assert record.discrepancy_stage == DISCREPANCY_INVESTIGATION_ORDER[0]
    assert record.relative_difference == pytest.approx(0.2)


def test_build_missing_input_audit_creates_one_row_per_target() -> None:
    targets = (_target(),)

    records = build_missing_input_audit(targets, missing_reason="Required panels are missing.")

    assert records[0].status == ReplicationStatus.NOT_REPRODUCIBLE_MISSING_INPUT
    assert records[0].published_value is None
    assert records[0].notes == "Required panels are missing."


def test_write_audit_json_and_markdown_report(tmp_path: Path) -> None:
    records = build_missing_input_audit((_target(),), missing_reason="Missing source data.")
    audit_path = tmp_path / "reports" / "audit.csv"
    json_path = tmp_path / "reports" / "audit.json"
    report_path = tmp_path / "reports" / "replication_report.md"

    write_audit(records, audit_path)
    write_audit_json(records, json_path)
    write_replication_report(records, report_path)

    frame = pd.read_csv(audit_path)
    assert frame.loc[0, "target_id"] == "TBL_001"
    assert frame.loc[0, "status"] == ReplicationStatus.NOT_REPRODUCIBLE_MISSING_INPUT
    assert "Missing source data" in json_path.read_text(encoding="utf-8")
    report = report_path.read_text(encoding="utf-8")
    assert "inaccessible inputs" in report
    assert "not evidence that the article is unreliable" in report


def test_audit_summary_and_rendered_report_sections() -> None:
    reproduced = compare_statistic(
        target=_target(),
        statistic="mean",
        published_value=1.0,
        replicated_value=1.0,
        generated_artifact=Path("artifact.csv"),
    )
    missing = build_missing_input_audit((_target(),), missing_reason="Missing input.")[0]

    summary = audit_summary([reproduced, missing])
    report = render_replication_report([reproduced, missing])

    assert summary.loc[ReplicationStatus.REPRODUCED.value] == 1
    assert summary.loc[ReplicationStatus.NOT_REPRODUCIBLE_MISSING_INPUT.value] == 1
    assert "## Reproduced Tables" in report
    assert "## Blocked Targets" in report


def test_render_replication_report_has_standalone_baseline_structure() -> None:
    records = build_missing_input_audit((_target(),), missing_reason="Missing input.")

    report = render_replication_report(records)

    required_sections = [
        "## Bibliographic Target And Versions",
        "## Accessible And Inaccessible Evidence",
        "## Exact Source Definitions",
        "## Factor Reconstruction",
        "## Portfolio Reconstruction",
        "## Estimator Reconstruction",
        "## Weak-Factor And Influence Diagnostics",
        "## Deviations From The Article And Their Causes",
        "## Bounded Conclusion",
        "## Appendix: Complete Audit Table",
    ]
    for section in required_sections:
        assert section in report
    assert "post-2013" not in report.lower()
    assert "regime" not in report.lower()
    assert "shock decomposition" not in report.lower()
    assert "| `TBL_001` |" in report


def test_render_replication_report_handles_missing_optional_metadata(tmp_path: Path) -> None:
    report = render_replication_report(
        [],
        article_manifest_path=tmp_path / "missing_manifest.json",
        data_access_path=tmp_path / "missing_access.csv",
        source_registry_path=tmp_path / "missing_sources.yaml",
        baseline_config_path=tmp_path / "missing_baseline.yaml",
        robustness_report_path=tmp_path / "missing_robustness.md",
    )

    assert "Bibliographic metadata are not available." in report
    assert "Data-access matrix is unavailable." in report
    assert "Source definitions are unavailable." in report
    assert "Primary short-rate source id: `unknown`" in report
    assert "Weak-factor and influence diagnostics have not produced a baseline verdict." in report
    assert "No audit records are available." in report
    assert "No successful baseline replication conclusion" in report


def test_render_replication_report_rejects_malformed_metadata(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.json"
    bad_yaml = tmp_path / "bad.yaml"
    bad_json.write_text("[1, 2, 3]", encoding="utf-8")
    bad_yaml.write_text("- one\n- two\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected object JSON"):
        render_replication_report(
            [build_missing_input_audit((_target(),), missing_reason="x")[0]],
            article_manifest_path=bad_json,
        )

    with pytest.raises(ValueError, match="Expected mapping YAML"):
        render_replication_report(
            [build_missing_input_audit((_target(),), missing_reason="x")[0]],
            source_registry_path=bad_yaml,
        )


def test_render_replication_report_classifies_all_exact_sources(tmp_path: Path) -> None:
    data_access = tmp_path / "data_access.csv"
    source_registry = tmp_path / "sources.yaml"
    baseline_config = tmp_path / "baseline.yaml"
    robustness_report = tmp_path / "robustness.md"
    data_access.write_text(
        "source_id,exact_definition_verified,access_status,strict_replication_role,notes\n"
        "public_factor,true,present_public_file,required,Exact source is frozen\n"
        "future_extension,false,missing,extension,Excluded extension row\n",
        encoding="utf-8",
    )
    source_registry.write_text(
        """
sources:
  - id: public_factor
    category: factor_returns
    raw_path: data/raw/public_factor.csv
  - id: public_portfolio
    category: portfolio_returns
    raw_path: data/raw/public_portfolio.csv
""",
        encoding="utf-8",
    )
    baseline_config.write_text(
        """
sample:
  start: "1972-01"
  end: "2013-12"
short_rate:
  primary_series: public_factor
  alternatives: []
  innovation:
    model: ar1_with_intercept
portfolio_sets:
  - public_portfolio
asset_pricing:
  cross_section:
    estimators: []
""",
        encoding="utf-8",
    )
    robustness_report.write_text("No baseline diagnostics available yet.", encoding="utf-8")
    reproduced = compare_statistic(
        target=_target(),
        statistic="mean",
        published_value=1.0,
        replicated_value=1.0,
        generated_artifact=Path("artifact.csv"),
    )

    report = render_replication_report(
        [reproduced],
        data_access_path=data_access,
        source_registry_path=source_registry,
        baseline_config_path=baseline_config,
        robustness_report_path=robustness_report,
    )

    assert "No source-definition deviation is currently recorded." in report
    assert "Weak-factor and influence diagnostics have not produced a baseline verdict." in report
    assert "All audited targets are reproduced within the frozen tolerance rules." in report
    assert "future_extension" not in report


def test_is_accessible_access_status_reads_the_acquired_vocabulary() -> None:
    assert is_accessible_access_status("present_private_file")
    assert is_accessible_access_status(
        "acquired_at_two_vintages_exact_file_not_named_by_the_article"
    )
    assert is_accessible_access_status("acquired_documented_reconstruction_series_frozen")
    assert is_accessible_access_status("acquired_from_the_named_original_source_at_a_post_vintage")
    assert is_accessible_access_status("named_source_located_not_acquired")
    assert not is_accessible_access_status("not_located")
    assert not is_accessible_access_status("not_confirmed_and_not_assumed")
    assert not is_accessible_access_status("selected_source_pending_file_and_terms")
    assert not is_accessible_access_status("")


def test_render_replication_report_counts_acquired_sources_as_accessible(tmp_path: Path) -> None:
    data_access = tmp_path / "data_access.csv"
    data_access.write_text(
        "source_id,exact_definition_verified,access_status,strict_replication_role,notes\n"
        "acquired_factor,false,acquired_at_two_vintages,required,Frozen at two vintages\n"
        "private_article,true,present_private_file,required,Local private file\n"
        "absent_portfolio,false,not_located,required,No archive member exposes this panel\n",
        encoding="utf-8",
    )
    records = build_missing_input_audit((_target(),), missing_reason="Missing input.")

    report = render_replication_report(records, data_access_path=data_access)

    assert "Accessible or located strict-replication evidence rows: `2`" in report
    assert "Inaccessible or pending strict-replication evidence rows: `1`" in report
    assert "Pending `absent_portfolio`" in report
    assert "Pending `acquired_factor`" not in report


def test_write_audit_rejects_unallowed_status(tmp_path: Path) -> None:
    record = TableAuditRecord(
        target_id="bad",
        source_location="loc",
        generated_artifact="artifact",
        status="bad_status",  # type: ignore[arg-type]
        statistic="stat",
        published_value=None,
        replicated_value=None,
        absolute_difference=None,
        relative_difference=None,
        tolerance_rule="not_applicable",
        tolerance_value=None,
        discrepancy_stage=None,
        independent_check="not_run",
        notes="bad",
    )

    with pytest.raises(ValueError, match="allowed replication labels"):
        write_audit([record], tmp_path / "audit.csv")
