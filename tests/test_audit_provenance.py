"""Coverage, tolerance, and provenance guarantees of the input-audit layer.

Three separate claims are exercised here. Month coverage must be derived from the
observations that actually enter an aggregate, so a month cannot be certified
complete on the strength of a missing boundary observation. Tolerance verdicts
must not turn on binary representation error at an exactly-equal boundary. And
every audit that attributes a number to a frozen vintage must verify the bytes it
read and record what it read alongside what it wrote.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scripts.acquire_comparator_factors import WINDOW as COMPARATOR_WINDOW
from scripts.acquire_comparator_factors import _statistics
from scripts.audit_portfolio_source_compatibility import (
    OUTPUT_CSV,
    REVERSAL_CSV,
    VINTAGE_LABEL,
    _spread_statistics,
    verify_against_manifest,
)
from scripts.audit_portfolio_source_compatibility import (
    PROVENANCE_JSON as PORTFOLIO_PROVENANCE_JSON,
)
from scripts.audit_published_targets import _decimals_of
from scripts.reconstruct_rate_innovations import (
    INNOVATION_PARQUET,
    INNOVATION_PROVENANCE_JSON,
    TIMING_VARIANTS,
)

from short_rate_anomaly_regimes.data.aggregation_audit import (
    NUMERICAL_EPSILON,
    PRIMARY_TOLERANCE_PERCENTAGE_POINTS,
    SECONDARY_TOLERANCE_PERCENTAGE_POINTS,
    aggregate_daily_to_monthly,
    build_aggregation_difference_frame,
    daily_month_coverage,
    exact_decimal_rounding_check,
    summarise_aggregation,
)
from short_rate_anomaly_regimes.exceptions import DataValidationError
from short_rate_anomaly_regimes.provenance import sha256_file

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _daily_series() -> pd.Series:
    index = pd.date_range("2001-01-01", "2001-03-31", freq="D")
    return pd.Series(np.linspace(1.0, 2.0, len(index)), index=index, name="daily")


def _blanked(daily: pd.Series, start: int, stop: int) -> pd.Series:
    """Return the series with the observations in ``[start, stop)`` set to null."""
    blanked = daily.copy()
    blanked.iloc[start:stop] = np.nan
    return blanked


class TestCoverageFollowsTheAggregatedObservations:
    """A month is complete only if the observations used reach both boundaries."""

    def test_a_fully_observed_month_is_complete(self) -> None:
        coverage = daily_month_coverage(_daily_series())
        assert bool(coverage["complete_month"].all())
        assert list(coverage["first_day"]) == [1, 1, 1]
        assert list(coverage["last_day"]) == [31, 28, 31]

    def test_a_missing_month_start_removes_completeness(self) -> None:
        daily = _blanked(_daily_series(), 0, 4)
        coverage = daily_month_coverage(daily)
        january = coverage.loc[pd.Timestamp("2001-01-01")]
        assert january["observations"] == 31
        assert january["non_missing_observations"] == 27
        assert january["first_day"] == 5
        assert not bool(january["covers_month_start"])
        assert not bool(january["complete_month"])

    def test_a_missing_month_end_removes_completeness(self) -> None:
        daily = _blanked(_daily_series(), 85, 90)
        coverage = daily_month_coverage(daily)
        march = coverage.loc[pd.Timestamp("2001-03-01")]
        assert march["last_day"] == 26
        assert not bool(march["covers_month_end"])
        assert not bool(march["complete_month"])

    def test_a_boundary_gap_within_three_days_is_still_complete(self) -> None:
        daily = _blanked(_daily_series(), 0, 2)
        coverage = daily_month_coverage(daily)
        assert bool(coverage.loc[pd.Timestamp("2001-01-01"), "complete_month"])

    def test_a_month_with_no_observation_left_is_not_complete(self) -> None:
        daily = _blanked(_daily_series(), 31, 59)
        coverage = daily_month_coverage(daily)
        february = coverage.loc[pd.Timestamp("2001-02-01")]
        assert february["observations"] == 28
        assert not bool(february["complete_month"])

    def test_a_non_datetime_index_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="DatetimeIndex"):
            daily_month_coverage(pd.Series([1.0, 2.0], index=["a", "b"]))

    def test_a_month_missing_a_boundary_is_excluded_from_the_summary(self) -> None:
        daily = _daily_series()
        monthly = aggregate_daily_to_monthly(daily, rule="calendar_day_mean")
        frame = build_aggregation_difference_frame(
            monthly=monthly,
            daily=_blanked(daily, 0, 10),
            monthly_series_id="M",
            daily_series_id="D",
            rule="calendar_day_mean",
        )
        assert not bool(
            frame.loc[frame["month"] == pd.Timestamp("2001-01-01"), "complete_month"].iloc[0]
        )
        summary = summarise_aggregation(frame)
        assert summary.complete_months_compared == 2

    def test_the_excluded_month_would_otherwise_have_passed_on_all_rows(self) -> None:
        """The old all-rows rule kept the month; the difference is not cosmetic."""
        daily = _blanked(_daily_series(), 0, 10)
        coverage = daily_month_coverage(daily)
        dated = pd.DatetimeIndex(daily.index)
        january_rows = dated[dated.month == 1]
        assert january_rows.min().day == 1
        assert coverage.loc[pd.Timestamp("2001-01-01"), "first_day"] == 11


class TestExactDecimalCheckSkipsMonthsItCannotCover:
    """The exact-decimal screen and its mean must use the same observations."""

    def _write(self, path: Path, header: str, rows: list[tuple[str, str]]) -> Path:
        path.write_text(
            header + "\n" + "\n".join(f"{date},{value}" for date, value in rows) + "\n",
            encoding="utf-8",
        )
        return path

    def test_an_empty_valued_boundary_row_does_not_certify_the_month(self, tmp_path: Path) -> None:
        dates = pd.date_range("2001-01-01", "2001-01-31", freq="D")
        rows = [(str(date.date()), "" if date.day <= 4 else "1.15") for date in dates]
        daily_path = self._write(tmp_path / "daily.csv", "DATE,D", rows)
        monthly_path = self._write(tmp_path / "monthly.csv", "DATE,M", [("2001-01-01", "1.15")])
        with pytest.raises(ValueError, match="No complete months"):
            exact_decimal_rounding_check(
                monthly_raw_path=monthly_path,
                daily_raw_path=daily_path,
                monthly_series_id="M",
                daily_series_id="D",
                rule="calendar_day_mean",
            )

    def test_a_period_coded_boundary_row_does_not_certify_the_month(self, tmp_path: Path) -> None:
        dates = pd.date_range("2001-01-01", "2001-01-31", freq="D")
        rows = [(str(date.date()), "." if date.day <= 4 else "1.15") for date in dates]
        daily_path = self._write(tmp_path / "daily.csv", "DATE,D", rows)
        monthly_path = self._write(tmp_path / "monthly.csv", "DATE,M", [("2001-01-01", "1.15")])
        with pytest.raises(ValueError, match="No complete months"):
            exact_decimal_rounding_check(
                monthly_raw_path=monthly_path,
                daily_raw_path=daily_path,
                monthly_series_id="M",
                daily_series_id="D",
                rule="calendar_day_mean",
            )

    def test_an_interior_missing_row_leaves_the_month_comparable(self, tmp_path: Path) -> None:
        dates = pd.date_range("2001-01-01", "2001-01-31", freq="D")
        rows = [(str(date.date()), "" if date.day == 17 else "1.15") for date in dates]
        daily_path = self._write(tmp_path / "daily.csv", "DATE,D", rows)
        monthly_path = self._write(tmp_path / "monthly.csv", "DATE,M", [("2001-01-01", "1.15")])
        check = exact_decimal_rounding_check(
            monthly_raw_path=monthly_path,
            daily_raw_path=daily_path,
            monthly_series_id="M",
            daily_series_id="D",
            rule="calendar_day_mean",
        )
        assert check.complete_months_compared == 1
        assert check.exact_decimal_matches == 1


class TestToleranceBoundariesAreEpsilonGuarded:
    """A difference mathematically equal to a tolerance must sit inside it."""

    def _frame(self, differences: list[float]) -> pd.DataFrame:
        absolute = pd.Series(differences).abs()
        return pd.DataFrame(
            {
                "monthly_series_id": "M",
                "daily_series_id": "D",
                "rule": "calendar_day_mean",
                "absolute_difference": absolute,
                "complete_month": True,
                "within_primary_tolerance": absolute
                <= PRIMARY_TOLERANCE_PERCENTAGE_POINTS + NUMERICAL_EPSILON,
                "within_secondary_tolerance": absolute
                <= SECONDARY_TOLERANCE_PERCENTAGE_POINTS + NUMERICAL_EPSILON,
                "exact_to_published_precision": absolute < 5e-9,
            }
        )

    def test_a_representation_inflated_secondary_boundary_is_not_a_failure(self) -> None:
        inflated = 0.72 - 0.71
        assert inflated > SECONDARY_TOLERANCE_PERCENTAGE_POINTS
        assert inflated <= SECONDARY_TOLERANCE_PERCENTAGE_POINTS + NUMERICAL_EPSILON
        summary = summarise_aggregation(self._frame([0.0] * 50 + [inflated]))
        assert summary.share_within_primary_tolerance < 0.99
        assert summary.verdict == "reproduced_within_secondary_tolerance_only"

    def test_a_genuine_excess_over_the_secondary_band_still_fails(self) -> None:
        summary = summarise_aggregation(self._frame([0.0] * 50 + [0.02]))
        assert summary.verdict == "not_reproduced_within_declared_tolerance"

    def test_a_representation_inflated_primary_boundary_is_still_primary(self) -> None:
        inflated = 0.715 - 0.71
        summary = summarise_aggregation(self._frame([inflated]))
        assert summary.verdict == "reproduced_within_primary_tolerance"

    def test_an_empty_table_is_rejected(self) -> None:
        frame = self._frame([0.0])
        frame["complete_month"] = False
        with pytest.raises(ValueError, match="No complete months"):
            summarise_aggregation(frame)


class TestWindowStatisticsUseTheWholeWindow:
    """A candidate is ranked against the article on the article's own months."""

    def _complete(self) -> pd.Series:
        return pd.Series(
            np.linspace(-1.0, 1.0, len(COMPARATOR_WINDOW)),
            index=COMPARATOR_WINDOW,
            name="candidate",
        )

    def test_a_complete_series_reports_the_full_window(self) -> None:
        statistics = _statistics(self._complete())
        assert statistics["months"] == float(len(COMPARATOR_WINDOW))
        assert statistics["months"] == 504.0

    def test_a_month_absent_from_the_file_is_a_failure(self) -> None:
        series = self._complete().drop(index=pd.Period("1987-10", freq="M"))
        with pytest.raises(DataValidationError, match="1987-10"):
            _statistics(series)

    def test_a_null_month_inside_the_window_is_a_failure(self) -> None:
        values = np.linspace(-1.0, 1.0, len(COMPARATOR_WINDOW))
        october_1987 = 189
        assert COMPARATOR_WINDOW[october_1987] == pd.Period("1987-10", freq="M")
        values[october_1987] = np.nan
        series = pd.Series(values, index=COMPARATOR_WINDOW, name="candidate")
        with pytest.raises(DataValidationError, match="missing 1 of 504 months"):
            _statistics(series)

    def test_months_outside_the_window_are_ignored(self) -> None:
        series = self._complete()
        extended = pd.concat(
            [pd.Series([np.nan], index=pd.PeriodIndex(["1971-12"], freq="M")), series]
        )
        assert _statistics(extended)["months"] == 504.0

    def test_the_portfolio_spread_uses_the_same_rule(self) -> None:
        panel = pd.DataFrame(
            {
                "decile_01": np.linspace(0.0, 1.0, len(COMPARATOR_WINDOW)),
                "decile_10": np.linspace(1.0, 2.0, len(COMPARATOR_WINDOW)),
            },
            index=COMPARATOR_WINDOW,
        )
        assert _spread_statistics(panel)["months"] == 504.0
        with pytest.raises(DataValidationError, match="missing 1 of 504 months"):
            _spread_statistics(panel.drop(index=pd.Period("1990-06", freq="M")))


class TestManifestVerification:
    """An audit must refuse to attribute a number to bytes it has not verified."""

    def _fixture(self, tmp_path: Path) -> tuple[Path, Path]:
        target = tmp_path / "panel.csv"
        target.write_text("month,decile_01\n1972-01,0.1\n", encoding="utf-8")
        manifest = tmp_path / "panel.json"
        manifest.write_text(
            json.dumps(
                {
                    "normalized_path": target.as_posix(),
                    "normalized_sha256": sha256_file(target),
                }
            ),
            encoding="utf-8",
        )
        return target, manifest

    def test_a_matching_checksum_is_returned(self, tmp_path: Path) -> None:
        target, manifest = self._fixture(tmp_path)
        digest = verify_against_manifest(
            file_path=target,
            manifest_path=manifest,
            checksum_key="normalized_sha256",
            path_key="normalized_path",
        )
        assert digest == sha256_file(target)

    def test_an_altered_file_is_rejected(self, tmp_path: Path) -> None:
        target, manifest = self._fixture(tmp_path)
        target.write_text("month,decile_01\n1972-01,0.2\n", encoding="utf-8")
        with pytest.raises(DataValidationError, match="Checksum mismatch"):
            verify_against_manifest(
                file_path=target,
                manifest_path=manifest,
                checksum_key="normalized_sha256",
                path_key="normalized_path",
            )

    def test_a_missing_manifest_is_rejected(self, tmp_path: Path) -> None:
        target, _ = self._fixture(tmp_path)
        with pytest.raises(DataValidationError, match="Frozen manifest is missing"):
            verify_against_manifest(
                file_path=target,
                manifest_path=tmp_path / "absent.json",
                checksum_key="normalized_sha256",
                path_key="normalized_path",
            )

    def test_a_manifest_naming_another_file_is_rejected(self, tmp_path: Path) -> None:
        target, manifest = self._fixture(tmp_path)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["normalized_path"] = "data/interim/portfolios/somewhere_else.csv"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DataValidationError, match="but this audit reads"):
            verify_against_manifest(
                file_path=target,
                manifest_path=manifest,
                checksum_key="normalized_sha256",
                path_key="normalized_path",
            )

    def test_a_foreign_vintage_label_is_rejected(self, tmp_path: Path) -> None:
        target, manifest = self._fixture(tmp_path)
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        payload["vintage_label"] = "some_other_vintage"
        manifest.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(DataValidationError, match="records vintage"):
            verify_against_manifest(
                file_path=target,
                manifest_path=manifest,
                checksum_key="normalized_sha256",
                path_key="normalized_path",
            )

    def test_a_manifest_without_the_checksum_field_is_rejected(self, tmp_path: Path) -> None:
        target, manifest = self._fixture(tmp_path)
        manifest.write_text(json.dumps({"normalized_path": target.as_posix()}), encoding="utf-8")
        with pytest.raises(DataValidationError, match="no usable"):
            verify_against_manifest(
                file_path=target,
                manifest_path=manifest,
                checksum_key="normalized_sha256",
                path_key="normalized_path",
            )


#: These checks re-hash the frozen inputs named by each provenance record. Those
#: inputs live under ``data/``, which is deliberately excluded from version
#: control, so the checks can only run where the data has actually been
#: acquired. They are marked ``integration`` and skipped elsewhere rather than
#: weakened, because verifying a checksum against a file that is not present
#: would be no verification at all.
_ACQUIRED_DATA_PRESENT = (REPOSITORY_ROOT / "data" / "interim" / "portfolios").is_dir() and (
    REPOSITORY_ROOT / "data" / "interim" / "fred"
).is_dir()

requires_acquired_data = pytest.mark.skipif(
    not _ACQUIRED_DATA_PRESENT,
    reason="frozen inputs under data/ are not present; run the acquisition scripts first",
)


@pytest.mark.integration
@requires_acquired_data
class TestCommittedProvenanceRecords:
    """The committed audit outputs must still match the record written beside them."""

    def _record(self, relative: Path) -> dict[str, object]:
        path = REPOSITORY_ROOT / relative
        assert path.is_file(), f"missing provenance record {relative}"
        payload: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
        return payload

    def test_the_portfolio_audit_records_its_inputs_and_outputs(self) -> None:
        record = self._record(PORTFOLIO_PROVENANCE_JSON)
        assert record["script"] == "scripts/audit_portfolio_source_compatibility.py"
        assert record["vintage_label"] == VINTAGE_LABEL
        window = record["comparison_window"]
        assert isinstance(window, dict)
        assert (window["start"], window["end"], window["months"]) == ("1972-01", "2013-12", 504)
        assert record["tolerance_at_published_precision"] == 0.005

        inputs = record["verified_inputs"]
        assert isinstance(inputs, dict)
        panels = inputs["normalized_family_panels"]
        assert isinstance(panels, list)
        assert len(panels) == 7
        for entry in panels:
            path = REPOSITORY_ROOT / entry["path"]
            manifest = json.loads((REPOSITORY_ROOT / entry["manifest"]).read_text("utf-8"))
            assert sha256_file(path) == entry["sha256"] == manifest["normalized_sha256"]
        archives = inputs["raw_archives"]
        assert isinstance(archives, list)
        for entry in archives:
            path = REPOSITORY_ROOT / entry["path"]
            manifest = json.loads((REPOSITORY_ROOT / entry["manifest"]).read_text("utf-8"))
            assert sha256_file(path) == entry["sha256"] == manifest["raw_sha256"]

    def test_the_portfolio_audit_output_checksums_are_current(self) -> None:
        record = self._record(PORTFOLIO_PROVENANCE_JSON)
        outputs = record["outputs"]
        assert isinstance(outputs, list)
        recorded = {entry["path"]: entry["sha256"] for entry in outputs}
        assert set(recorded) == {OUTPUT_CSV.as_posix(), REVERSAL_CSV.as_posix()}
        for relative, digest in recorded.items():
            assert sha256_file(REPOSITORY_ROOT / relative) == digest

    def test_the_innovation_panel_is_tied_to_its_frozen_inputs(self) -> None:
        record = self._record(INNOVATION_PROVENANCE_JSON)
        assert record["script"] == "scripts/reconstruct_rate_innovations.py"
        assert record["output_path"] == INNOVATION_PARQUET.as_posix()
        assert sha256_file(REPOSITORY_ROOT / INNOVATION_PARQUET) == record["output_sha256"]
        assert record["timing_variants"] == list(TIMING_VARIANTS)

        window = record["estimation_window"]
        assert isinstance(window, dict)
        assert (window["start"], window["end"], window["months"]) == ("1972-01", "2013-12", 504)

        model = record["ar_model"]
        assert isinstance(model, dict)
        assert model["order"] == 1
        assert model["specification"] == "r_t = a + rho * r_{t-1} + u_t"

        columns = record["columns"]
        assert isinstance(columns, list)
        panel = pd.read_parquet(REPOSITORY_ROOT / INNOVATION_PARQUET)
        assert [str(column) for column in panel.columns] == columns
        assert len(panel) == record["rows"]

        inputs = record["inputs"]
        assert isinstance(inputs, list)
        assert {entry["series_id"] for entry in inputs} == {"FEDFUNDS", "TB3MS", "DTB3"}
        for entry in inputs:
            path = REPOSITORY_ROOT / entry["normalized_path"]
            manifest = json.loads((REPOSITORY_ROOT / entry["manifest"]).read_text("utf-8"))
            assert sha256_file(path) == entry["normalized_sha256"]
            assert manifest["normalized_sha256"] == entry["normalized_sha256"]
            assert manifest["vintage_label"] == entry["vintage_label"]
            assert entry["vintage_label"]


def test_published_precision_survives_csv_parsing() -> None:
    """A p-value printed as ``0.000`` must carry a three-decimal tolerance.

    Letting pandas parse the column turned ``0.000`` into ``0.0``, so
    ``_decimals_of`` counted one decimal and the audit allowed 0.05 either side
    instead of 0.0005. That is a hundredfold loosening, and it reported
    materially different values as recovered. Twenty-eight registry cells were
    affected, the asymptotic p-values among them, so the column is read as text
    and the tolerance is taken from what the article actually printed.
    """
    registry = pd.read_csv(
        Path("research/published_target_values.csv"), dtype={"uncertainty_value": str}
    )
    printed = registry["uncertainty_value"].astype(str)

    assert (printed == "0.000").any(), "the fixture assumes the registry prints a 0.000 p-value"
    for value in printed[printed.str.startswith("0.00")].unique():
        assert _decimals_of(value) == 3
        assert 0.5 * 10.0 ** -_decimals_of(value) == pytest.approx(0.0005)
    # The failure mode itself: the parsed float loses the trailing zeros.
    assert _decimals_of(float("0.000")) == 1
