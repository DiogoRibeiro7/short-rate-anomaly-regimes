"""Public-data acquisition interfaces.

Network functions are intentionally unimplemented until source licences, exact series definitions,
and raw-file retention rules are approved in Milestone 2.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Downloader(Protocol):
    """Protocol implemented by source-specific downloaders."""

    def download(self, *, output_path: Path) -> Path:
        """Download a source to an immutable raw path."""
        ...


def download_fred_series(*, series_id: str, output_path: Path) -> Path:
    """Download a FRED series after the source contract is approved."""
    raise NotImplementedError(
        "Implement in Milestone 2 after verifying the exact article series and API provenance"
    )


def download_kenneth_french_dataset(*, dataset_name: str, output_path: Path) -> Path:
    """Download a Kenneth French dataset after its exact archive name is recorded."""
    raise NotImplementedError(
        "Implement in Milestone 2 after recording the exact archive and construction definition"
    )
