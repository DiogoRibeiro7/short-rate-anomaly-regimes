"""Table-level replication status records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.types import ReplicationStatus


@dataclass(frozen=True, slots=True)
class TableAuditRecord:
    """Comparison between one published target and one repository output."""

    target_id: str
    output_path: str
    status: ReplicationStatus
    statistic: str
    published_value: float | None
    replicated_value: float | None
    absolute_difference: float | None
    relative_difference: float | None
    tolerance_rule: str
    notes: str


def write_audit(records: list[TableAuditRecord], path: Path) -> None:
    """Write an auditable CSV with one row per target statistic."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([asdict(record) for record in records]).to_csv(path, index=False)
