"""Portfolio-return loading and harmonisation."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

from short_rate_anomaly_regimes.data.validation import validate_monthly_panel

PortfolioUnits = Literal["percent_return", "decimal_return"]


@dataclass(frozen=True, slots=True)
class PortfolioColumnMap:
    """Mapping from a source portfolio label to the canonical 5 by 5 label."""

    original: str
    canonical: str
    size_bucket: int
    characteristic_bucket: int


@dataclass(frozen=True, slots=True)
class FrenchPortfolioPanel:
    """Parsed Kenneth French 25-portfolio panel with source labels preserved."""

    source_id: str
    raw: pd.DataFrame
    processed: pd.DataFrame
    column_map: tuple[PortfolioColumnMap, ...]
    units: str


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


def canonical_25_portfolio_labels(
    *,
    size_prefix: str = "size",
    characteristic_prefix: str = "characteristic",
) -> tuple[str, ...]:
    """Return row-major canonical labels for 5 by 5 size-characteristic portfolios."""
    return tuple(
        f"{size_prefix}_{size_bucket}_{characteristic_prefix}_{characteristic_bucket}"
        for size_bucket in range(1, 6)
        for characteristic_bucket in range(1, 6)
    )


def load_kenneth_french_25_portfolios(
    path: Path,
    *,
    source_id: str,
    characteristic_prefix: str,
    input_units: PortfolioUnits = "percent_return",
) -> FrenchPortfolioPanel:
    """Parse one Kenneth French monthly 25-portfolio text, CSV, or ZIP archive."""
    text = _read_french_payload(path)
    return parse_kenneth_french_25_portfolios(
        text,
        source_id=source_id,
        characteristic_prefix=characteristic_prefix,
        input_units=input_units,
    )


def parse_kenneth_french_25_portfolios(
    text: str,
    *,
    source_id: str,
    characteristic_prefix: str,
    input_units: PortfolioUnits = "percent_return",
) -> FrenchPortfolioPanel:
    """Parse the monthly block from a Kenneth French 25-portfolio payload."""
    header, rows = _extract_monthly_french_rows(text)
    original_labels = tuple(label.strip() for label in header[1:26])
    if len(original_labels) != 25 or any(label == "" for label in original_labels):
        raise ValueError("Kenneth French monthly block must contain 25 portfolio labels")

    normalized_rows = [_normalize_french_row(row, width=26) for row in rows]
    raw = pd.DataFrame(normalized_rows, columns=("date", *original_labels))
    dates = pd.to_datetime(raw["date"], format="%Y%m", errors="raise") + pd.offsets.MonthEnd(0)
    raw.insert(1, "month", dates)

    canonical_labels = canonical_25_portfolio_labels(characteristic_prefix=characteristic_prefix)
    values = raw.loc[:, list(original_labels)].apply(pd.to_numeric, errors="coerce")
    values = values.mask(values <= -99.0)
    if input_units == "percent_return":
        values = values / 100.0
    processed = values.copy()
    processed.columns = list(canonical_labels)
    processed.insert(0, "date", dates)
    validate_25_portfolio_panel(
        processed,
        units="decimal_return",
        characteristic_prefix=characteristic_prefix,
    )

    column_map = tuple(
        PortfolioColumnMap(
            original=original,
            canonical=canonical,
            size_bucket=(index // 5) + 1,
            characteristic_bucket=(index % 5) + 1,
        )
        for index, (original, canonical) in enumerate(
            zip(original_labels, canonical_labels, strict=True)
        )
    )
    return FrenchPortfolioPanel(
        source_id=source_id,
        raw=raw,
        processed=processed,
        column_map=column_map,
        units="decimal_return",
    )


def validate_25_portfolio_panel(
    frame: pd.DataFrame,
    *,
    date_column: str = "date",
    units: PortfolioUnits = "decimal_return",
    sample_start: str | None = None,
    sample_end: str | None = None,
    characteristic_prefix: str = "characteristic",
) -> None:
    """Validate canonical 5 by 5 monthly portfolio-return panels."""
    expected_columns = canonical_25_portfolio_labels(characteristic_prefix=characteristic_prefix)
    if tuple(column for column in frame.columns if column != date_column) != expected_columns:
        raise ValueError("Portfolio columns must use canonical 5 by 5 ordering")
    bounds = (-1.0, 2.0) if units == "decimal_return" else (-100.0, 200.0)
    validate_monthly_panel(
        frame,
        date_column=date_column,
        expected_columns=(date_column, *expected_columns),
        sample_start=sample_start,
        sample_end=sample_end,
        numeric_bounds=bounds,
        units=units,
        expected_portfolio_count=25,
    )


def portfolio_descriptive_statistics(
    frame: pd.DataFrame,
    *,
    date_column: str = "date",
) -> pd.DataFrame:
    """Compute monthly portfolio-return descriptive statistics."""
    returns = frame.drop(columns=[date_column]) if date_column in frame.columns else frame
    rows: list[dict[str, float | str | int]] = []
    for column in returns.columns:
        series = pd.to_numeric(returns[column], errors="coerce").dropna()
        rows.append(
            {
                "portfolio": str(column),
                "observations": int(series.shape[0]),
                "mean": float(series.mean()),
                "std": float(series.std(ddof=1)),
                "min": float(series.min()),
                "max": float(series.max()),
            }
        )
    return pd.DataFrame(rows)


def extreme_spread_summary(
    frame: pd.DataFrame,
    *,
    date_column: str = "date",
    characteristic_prefix: str = "characteristic",
    expected_sign: Literal["positive", "negative"] | None = None,
) -> pd.DataFrame:
    """Compute high-minus-low characteristic spreads within each size bucket."""
    returns = frame.drop(columns=[date_column]) if date_column in frame.columns else frame
    rows: list[dict[str, float | str | int]] = []
    for size_bucket in range(1, 6):
        high = f"size_{size_bucket}_{characteristic_prefix}_5"
        low = f"size_{size_bucket}_{characteristic_prefix}_1"
        spread = pd.to_numeric(returns[high] - returns[low], errors="coerce").dropna()
        mean = float(spread.mean())
        if expected_sign == "positive" and mean < 0:
            raise ValueError(f"Expected positive high-minus-low spread for size {size_bucket}")
        if expected_sign == "negative" and mean > 0:
            raise ValueError(f"Expected negative high-minus-low spread for size {size_bucket}")
        rows.append(
            {
                "size_bucket": size_bucket,
                "spread": f"{high}_minus_{low}",
                "observations": int(spread.shape[0]),
                "mean": mean,
                "std": float(spread.std(ddof=1)),
            }
        )
    return pd.DataFrame(rows)


def _read_french_payload(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [
                member
                for member in archive.infolist()
                if not member.is_dir() and member.filename.lower().endswith((".csv", ".txt"))
            ]
            if not members:
                raise ValueError("Kenneth French ZIP contains no CSV or TXT member")
            payload = archive.read(members[0])
        return payload.decode("utf-8-sig")
    return path.read_text(encoding="utf-8-sig")


def _extract_monthly_french_rows(text: str) -> tuple[tuple[str, ...], list[tuple[str, ...]]]:
    reader = csv.reader(io.StringIO(text))
    previous_nonempty: tuple[str, ...] | None = None
    header: tuple[str, ...] | None = None
    rows: list[tuple[str, ...]] = []
    in_monthly_block = False
    for raw_row in reader:
        row = tuple(cell.strip() for cell in raw_row)
        if not any(row):
            if in_monthly_block:
                break
            continue
        first_cell = row[0]
        if len(first_cell) == 6 and first_cell.isdigit():
            if not in_monthly_block:
                header = previous_nonempty
                in_monthly_block = True
            rows.append(row)
            continue
        if in_monthly_block:
            break
        previous_nonempty = row
    if header is None or not rows:
        raise ValueError("Could not locate Kenneth French monthly portfolio block")
    return header, rows


def _normalize_french_row(row: tuple[str, ...], *, width: int) -> tuple[str, ...]:
    if len(row) < width:
        row = (*row, *([""] * (width - len(row))))
    if len(row) > width:
        row = row[:width]
    if not np.isfinite(float(row[0])):
        raise ValueError("Monthly portfolio row has an invalid date")
    return row
