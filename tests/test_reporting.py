from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.reporting.audit import TableAuditRecord, write_audit
from short_rate_anomaly_regimes.types import ReplicationStatus


def test_write_audit_creates_parent_directory_and_csv(tmp_path: Path) -> None:
    audit_path = tmp_path / "reports" / "audit.csv"
    records = [
        TableAuditRecord(
            target_id="table_1_alpha",
            output_path="reports/generated/table_1.csv",
            status=ReplicationStatus.NOT_ATTEMPTED,
            statistic="alpha",
            published_value=None,
            replicated_value=None,
            absolute_difference=None,
            relative_difference=None,
            tolerance_rule="not_applicable",
            notes="Blocked until source data are verified.",
        )
    ]

    write_audit(records, audit_path)

    frame = pd.read_csv(audit_path)
    assert frame.loc[0, "target_id"] == "table_1_alpha"
    assert frame.loc[0, "status"] == ReplicationStatus.NOT_ATTEMPTED
    assert frame.loc[0, "notes"] == "Blocked until source data are verified."
