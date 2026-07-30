"""Portfolio-return loading and harmonisation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from short_rate_anomaly_regimes.data.validation import validate_monthly_panel


def load_monthly_portfolios(path: Path, *, date_column: str = "date") -> pd.DataFrame:
    """Load a validated monthly portfolio-return panel from CSV or Parquet."""
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
    else:
        raise ValueError(f"Unsupported portfolio file extension: {path.suffix}")
    validate_monthly_panel(frame, date_column=date_column)
    frame = frame.copy()
    frame[date_column] = pd.to_datetime(frame[date_column])
    return frame.set_index(date_column).sort_index()
