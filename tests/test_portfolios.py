import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from short_rate_anomaly_regimes.cli import app
from short_rate_anomaly_regimes.portfolios.construction import (
    construct_double_sorted_portfolios,
    default_construction_rules,
    validate_portfolio_weights,
    write_construction_manifest,
)
from short_rate_anomaly_regimes.portfolios.loaders import (
    canonical_25_portfolio_labels,
    extreme_spread_summary,
    load_kenneth_french_25_portfolios,
    load_monthly_portfolios,
    parse_kenneth_french_25_portfolios,
    portfolio_descriptive_statistics,
    validate_25_portfolio_panel,
)


def _french_25_fixture() -> str:
    labels = [f"raw_{index}" for index in range(1, 26)]
    row_1 = ",".join(["202001", *(str(index) for index in range(1, 26))])
    row_2 = ",".join(["202002", *(str(index + 1) for index in range(1, 26))])
    return "\n".join(
        [
            "metadata line",
            "," + ",".join(labels),
            row_1,
            row_2,
            "",
            "Annual Returns:",
            "2020,1",
        ]
    )


def _security_panel() -> pd.DataFrame:
    rows: list[dict[str, float | int | str]] = []
    for month in ["2020-01-31", "2020-02-29"]:
        for security in range(1, 26):
            rows.append(
                {
                    "date": month,
                    "security_id": f"firm_{security}",
                    "market_equity": float(security),
                    "asset_growth": float(security % 5),
                    "return": float(security) / 100.0,
                }
            )
    return pd.DataFrame(rows)


def test_load_monthly_portfolios_reads_csv_with_datetime_index(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "portfolios.csv"
    portfolio_path.write_text(
        "date,asset_a,asset_b\n2020-01-31,0.01,0.04\n2020-02-29,0.02,0.03\n",
        encoding="utf-8",
    )

    frame = load_monthly_portfolios(portfolio_path)

    assert isinstance(frame.index, pd.DatetimeIndex)
    assert frame.index.tolist() == [
        pd.Timestamp("2020-01-31"),
        pd.Timestamp("2020-02-29"),
    ]
    assert frame.loc[pd.Timestamp("2020-01-31"), "asset_a"] == pytest.approx(0.01)


def test_load_monthly_portfolios_reads_parquet(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "portfolios.parquet"
    pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-02-29"],
            "asset": [0.01, 0.02],
        }
    ).to_parquet(portfolio_path)

    frame = load_monthly_portfolios(portfolio_path)

    assert frame.index.tolist() == [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-29")]
    assert frame.loc[pd.Timestamp("2020-02-29"), "asset"] == pytest.approx(0.02)


def test_load_monthly_portfolios_rejects_unsupported_extension(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "portfolios.txt"
    portfolio_path.write_text("date,asset\n2020-01-31,0.01\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported portfolio file extension"):
        load_monthly_portfolios(portfolio_path)


def test_load_monthly_portfolios_runs_monthly_validation(tmp_path: Path) -> None:
    portfolio_path = tmp_path / "invalid.csv"
    portfolio_path.write_text(
        "date,asset\n2020-01-01,0.01\n2020-01-31,0.02\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="calendar month"):
        load_monthly_portfolios(portfolio_path)


def test_parse_kenneth_french_25_portfolios_preserves_and_canonicalizes_labels() -> None:
    parsed = parse_kenneth_french_25_portfolios(
        _french_25_fixture(),
        source_id="french_size_bm_25",
        characteristic_prefix="bm",
    )

    assert parsed.raw.columns[:3].tolist() == ["date", "month", "raw_1"]
    assert parsed.processed.columns.tolist() == [
        "date",
        *canonical_25_portfolio_labels(characteristic_prefix="bm"),
    ]
    assert parsed.processed.loc[0, "size_1_bm_1"] == pytest.approx(0.01)
    assert parsed.column_map[0].original == "raw_1"
    assert parsed.column_map[0].canonical == "size_1_bm_1"


def test_load_kenneth_french_25_portfolios_reads_zip_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "french.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("fixture.csv", _french_25_fixture())

    parsed = load_kenneth_french_25_portfolios(
        archive_path,
        source_id="french_size_long_term_reversal_25",
        characteristic_prefix="long_term_reversal",
    )

    assert parsed.processed.shape == (2, 26)
    assert "size_5_long_term_reversal_5" in parsed.processed.columns


def test_parse_kenneth_french_25_portfolios_rejects_malformed_payload() -> None:
    with pytest.raises(ValueError, match="Could not locate"):
        parse_kenneth_french_25_portfolios(
            "not a monthly table",
            source_id="bad",
            characteristic_prefix="bm",
        )


def test_validate_25_portfolio_panel_rejects_wrong_ordering() -> None:
    labels = list(canonical_25_portfolio_labels(characteristic_prefix="bm"))
    frame = pd.DataFrame([[pd.Timestamp("2020-01-31"), *([0.01] * 25)]], columns=["date", *labels])
    reordered = frame.loc[:, ["date", labels[1], labels[0], *labels[2:]]]

    with pytest.raises(ValueError, match="canonical 5 by 5 ordering"):
        validate_25_portfolio_panel(reordered, characteristic_prefix="bm")


def test_portfolio_descriptives_and_extreme_spread_summary() -> None:
    parsed = parse_kenneth_french_25_portfolios(
        _french_25_fixture(),
        source_id="french_size_bm_25",
        characteristic_prefix="bm",
    )

    descriptives = portfolio_descriptive_statistics(parsed.processed)
    spreads = extreme_spread_summary(
        parsed.processed,
        characteristic_prefix="bm",
        expected_sign="positive",
    )

    assert descriptives.shape[0] == 25
    assert spreads["mean"].gt(0).all()


def test_extreme_spread_summary_rejects_wrong_declared_direction() -> None:
    parsed = parse_kenneth_french_25_portfolios(
        _french_25_fixture(),
        source_id="french_size_bm_25",
        characteristic_prefix="bm",
    )

    with pytest.raises(ValueError, match="Expected negative"):
        extreme_spread_summary(
            parsed.processed,
            characteristic_prefix="bm",
            expected_sign="negative",
        )


def test_construct_double_sorted_portfolios_value_weights_security_panel() -> None:
    result = construct_double_sorted_portfolios(
        _security_panel(),
        characteristic="asset_growth",
        weighting="value",
    )

    assert result.status == "approximately_reproduced"
    assert result.returns.columns.tolist() == [
        "date",
        *canonical_25_portfolio_labels(characteristic_prefix="asset_growth"),
    ]
    assert result.returns.shape == (2, 26)
    assert result.weights.groupby(["date", "portfolio"])["weight"].sum().eq(1.0).all()


def test_construct_double_sorted_portfolios_equal_weights_security_panel() -> None:
    result = construct_double_sorted_portfolios(
        _security_panel(),
        characteristic="asset_growth",
        weighting="equal",
    )

    assert result.weights["weight"].between(0.0, 1.0).all()


def test_construct_double_sorted_portfolios_rejects_exact_reconstruction_label() -> None:
    with pytest.raises(ValueError, match="cannot be labelled exact"):
        construct_double_sorted_portfolios(
            _security_panel(),
            characteristic="asset_growth",
            weighting="value",
            status="exact",
        )


def test_construct_double_sorted_portfolios_validates_required_columns() -> None:
    with pytest.raises(ValueError, match="missing required columns"):
        construct_double_sorted_portfolios(
            pd.DataFrame({"date": ["2020-01-31"]}),
            characteristic="asset_growth",
            weighting="value",
        )


def test_validate_portfolio_weights_rejects_bad_sums() -> None:
    weights = pd.DataFrame(
        {
            "date": ["2020-01-31", "2020-01-31"],
            "portfolio": ["p1", "p1"],
            "weight": [0.4, 0.4],
        }
    )

    with pytest.raises(ValueError, match="sum to one"):
        validate_portfolio_weights(weights)


def test_write_construction_manifest_records_status_matrix(tmp_path: Path) -> None:
    manifest_path = tmp_path / "construction_manifest.json"

    write_construction_manifest(manifest_path)

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert len(payload["portfolio_sets"]) == len(default_construction_rules())
    assert {row["source_id"] for row in payload["status_matrix"]} >= {
        "french_size_bm_25",
        "size_asset_growth_25",
    }


def test_assemble_test_assets_command_writes_manifest_and_reports_blockers(tmp_path: Path) -> None:
    manifest_path = tmp_path / "construction_manifest.json"

    result = CliRunner().invoke(
        app,
        [
            "assemble-test-assets",
            "--registry",
            "configs/data_sources.yaml",
            "--manifest",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 1
    assert manifest_path.is_file()
    assert "portfolio sources are registered" in str(result.exception)
