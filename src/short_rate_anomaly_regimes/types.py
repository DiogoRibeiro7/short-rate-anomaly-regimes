"""Shared typed objects for the research pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import NewType

import pandas as pd

SourceId = NewType("SourceId", str)
PortfolioSetId = NewType("PortfolioSetId", str)


class ReplicationStatus(StrEnum):
    """Allowed labels for table-level replication outcomes."""

    REPRODUCED = "reproduced"
    APPROXIMATELY_REPRODUCED = "approximately_reproduced"
    #: Some of a target's statistics land inside the published rounding and
    #: others do not. The layer classification has always reported this state
    #: as `partially_recovered_under_documented_reconstruction`; the enum did
    #: not carry it, which forced the table-level audit to choose between
    #: overstating and understating. Added 2026-08-11, design correction 14.
    PARTIALLY_RECOVERED = "partially_recovered"
    NOT_REPRODUCIBLE_MISSING_INPUT = "not_reproducible_missing_input"
    CONTRADICTED = "contradicted"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class DataArtifact:
    """A validated dataset with provenance metadata."""

    source_id: SourceId
    path: Path
    sha256: str
    rows: int
    columns: tuple[str, ...]
    start: pd.Timestamp
    end: pd.Timestamp


@dataclass(frozen=True, slots=True)
class RateInnovationResult:
    """Output of a short-rate innovation model."""

    innovations: pd.Series
    fitted_values: pd.Series
    parameters: pd.Series
    diagnostics: pd.Series
