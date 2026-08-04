"""Tests for short-rate freezing, aggregation auditing, and AR(1) reconstruction."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from short_rate_anomaly_regimes.data.aggregation_audit import (
    aggregate_daily_to_monthly,
    build_aggregation_difference_frame,
    exact_decimal_rounding_check,
    summarise_aggregation,
)
from short_rate_anomaly_regimes.data.baseline_panel import (
    PanelValidationReport,
    build_baseline_panel,
    validate_baseline_panel,
)
from short_rate_anomaly_regimes.data.short_rate_freeze import (
    DECLARED_SERIES_METADATA,
    _canonical_csv_bytes,
    _normalize_fred_payload,
    audit_declared_metadata,
)
from short_rate_anomaly_regimes.exceptions import DataValidationError
from short_rate_anomaly_regimes.rates.baseline_reconstruction import (
    COEFFICIENT_STATISTICS,
    PUBLISHED_ROUNDING_TOLERANCE,
    ARReconstruction,
    classify_replication_target,
    compare_with_published,
    estimate_ar1_reconstruction,
    monthly_rate_from_freeze,
)


def _synthetic_rate(start: str = "1970-01", periods: int = 240) -> pd.Series:
    index = pd.period_range(start, periods=periods, freq="M")
    rng = np.random.default_rng(20260727)
    values = np.empty(periods, dtype=float)
    values[0] = 5.0
    for position in range(1, periods):
        values[position] = 0.05 + 0.98 * values[position - 1] + rng.normal(0.0, 0.4)
    return pd.Series(values, index=index, name="synthetic_rate")


class TestTimingConvention:
    """The AR(1) timing convention must be explicit and free of implicit shifts."""

    def test_pre_window_lag_covers_every_window_month(self) -> None:
        rate = _synthetic_rate()
        result = estimate_ar1_reconstruction(
            rate,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        expected = pd.period_range("1972-01", "1985-12", freq="M")
        assert list(result.innovations.index) == list(expected)
        assert result.regression_observations == len(expected)
        assert result.innovation_start == "1972-01"
        assert result.innovation_end == "1985-12"

    def test_within_window_lag_drops_the_first_window_month(self) -> None:
        rate = _synthetic_rate()
        result = estimate_ar1_reconstruction(
            rate,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="within_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        expected = pd.period_range("1972-02", "1985-12", freq="M")
        assert list(result.innovations.index) == list(expected)
        assert result.innovation_start == "1972-02"

    def test_residual_equals_the_explicit_lagged_definition(self) -> None:
        """u_t must equal r_t - a - rho * r_{t-1} at the same month index."""
        rate = _synthetic_rate()
        result = estimate_ar1_reconstruction(
            rate,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        index = result.innovations.index
        current = rate.reindex(index).to_numpy(dtype=float)
        lagged = rate.reindex(index - 1).to_numpy(dtype=float)
        manual = current - result.intercept - result.slope * lagged
        np.testing.assert_allclose(result.innovations.to_numpy(dtype=float), manual, atol=1e-12)

    def test_no_lookahead_a_future_level_cannot_change_a_past_innovation(self) -> None:
        """Extending the series beyond the window must not alter in-window residuals."""
        rate = _synthetic_rate()
        cutoff = pd.Period("1985-12", freq="M")
        truncated = rate[rate.index <= cutoff]
        base = estimate_ar1_reconstruction(
            truncated,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        extended_levels = rate.copy()
        shifted = extended_levels.index > cutoff
        extended_levels[shifted] = extended_levels[shifted] + 25.0
        extended = estimate_ar1_reconstruction(
            extended_levels,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        np.testing.assert_allclose(
            base.innovations.to_numpy(dtype=float),
            extended.innovations.to_numpy(dtype=float),
            atol=1e-12,
        )

    def test_shifting_the_innovation_by_one_month_breaks_the_definition(self) -> None:
        """A one-month mismatch must be detectable rather than silently absorbed."""
        rate = _synthetic_rate()
        result = estimate_ar1_reconstruction(
            rate,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        shifted = result.innovations.shift(1).dropna()
        aligned = result.innovations.reindex(shifted.index)
        assert not np.allclose(shifted.to_numpy(dtype=float), aligned.to_numpy(dtype=float))

    def test_pre_window_lag_requires_the_month_before_the_window(self) -> None:
        rate = _synthetic_rate(start="1972-01", periods=120)
        with pytest.raises(ValueError, match="Pre-window lag requires"):
            estimate_ar1_reconstruction(
                rate,
                series_id="synthetic",
                replication_mode="test",
                timing_variant="pre_window_lag",
                window_start="1972-01",
                window_end="1980-12",
            )

    def test_gap_in_the_estimation_window_is_rejected(self) -> None:
        rate = _synthetic_rate().drop(pd.Period("1975-06", freq="M"))
        with pytest.raises(ValueError, match="Missing rate levels"):
            estimate_ar1_reconstruction(
                rate,
                series_id="synthetic",
                replication_mode="test",
                timing_variant="pre_window_lag",
                window_start="1972-01",
                window_end="1985-12",
            )


class TestUnitAndScaleAudit:
    """Rate innovations inherit the level scale and the audit must say so."""

    def test_percent_level_is_detected_and_innovation_is_scale_equivariant(self) -> None:
        rate = _synthetic_rate()
        percent = estimate_ar1_reconstruction(
            rate,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        decimal = estimate_ar1_reconstruction(
            rate / 100.0,
            series_id="synthetic",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        assert percent.unit_scale_audit["inferred_level_scale"] == "percent_per_annum"
        assert decimal.unit_scale_audit["inferred_level_scale"] == "decimal_per_annum"
        assert percent.slope == pytest.approx(decimal.slope, abs=1e-12)
        assert percent.r_squared == pytest.approx(decimal.r_squared, abs=1e-12)
        assert percent.slope_t_ratio == pytest.approx(decimal.slope_t_ratio, abs=1e-9)
        assert percent.intercept_decimal_rate_units == pytest.approx(decimal.intercept, abs=1e-12)
        np.testing.assert_allclose(
            percent.innovations.to_numpy(dtype=float) / 100.0,
            decimal.innovations.to_numpy(dtype=float),
            atol=1e-12,
        )


class TestReplicationClassification:
    """A documented reconstruction may never be labelled exact replication."""

    def _perfect_comparison(self) -> pd.DataFrame:
        rate = _synthetic_rate()
        result = estimate_ar1_reconstruction(
            rate,
            series_id="synthetic",
            replication_mode="documented_reconstruction",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        published = {
            "intercept": round(result.intercept_decimal_rate_units, 3),
            "slope": round(result.slope, 3),
            "r_squared": round(result.r_squared, 2),
            "t_intercept": round(result.intercept_t_ratio, 2),
            "t_slope": round(result.slope_t_ratio, 2),
            "mean": round(result.descriptives["mean"], 2),
            "standard_deviation": round(result.descriptives["standard_deviation"], 2),
            "minimum": round(result.descriptives["minimum"], 2),
            "maximum": round(result.descriptives["maximum"], 2),
            "autocorrelation_1": round(result.descriptives["autocorrelation_1"], 2),
        }
        return compare_with_published(result, published)

    def test_exact_numerical_match_without_an_exact_input_is_not_replication(self) -> None:
        comparison = self._perfect_comparison()
        classification = classify_replication_target(
            comparison,
            replication_mode="documented_reconstruction",
            exact_input_available=False,
        )
        assert classification == "approximately_reproduced_under_documented_reconstruction"
        assert "reproduced" in classification
        assert classification != "reproduced"

    def test_the_same_match_with_an_exact_input_is_replication(self) -> None:
        comparison = self._perfect_comparison()
        classification = classify_replication_target(
            comparison,
            replication_mode="exact",
            exact_input_available=True,
        )
        assert classification == "reproduced"

    def test_empty_comparison_is_not_attempted(self) -> None:
        assert (
            classify_replication_target(
                pd.DataFrame(),
                replication_mode="documented_reconstruction",
                exact_input_available=False,
            )
            == "not_attempted"
        )


class TestAggregationAudit:
    """Provider monthly series are never assumed to equal a daily aggregation."""

    def _daily(self) -> pd.Series:
        index = pd.date_range("2001-01-01", "2001-03-31", freq="D")
        return pd.Series(np.linspace(1.0, 2.0, len(index)), index=index, name="daily")

    def test_calendar_and_business_day_means_differ(self) -> None:
        daily = self._daily()
        calendar = aggregate_daily_to_monthly(daily, rule="calendar_day_mean")
        business = aggregate_daily_to_monthly(daily, rule="business_day_mean")
        assert list(calendar.index) == list(business.index)
        assert not np.allclose(calendar.to_numpy(), business.to_numpy())

    def test_unknown_rule_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported aggregation rule"):
            aggregate_daily_to_monthly(self._daily(), rule="median")  # type: ignore[arg-type]

    def test_matching_aggregation_is_reported_as_reproduced(self) -> None:
        daily = self._daily()
        monthly = aggregate_daily_to_monthly(daily, rule="calendar_day_mean")
        frame = build_aggregation_difference_frame(
            monthly=monthly,
            daily=daily,
            monthly_series_id="M",
            daily_series_id="D",
            rule="calendar_day_mean",
        )
        summary = summarise_aggregation(frame)
        assert summary.verdict == "reproduced_within_primary_tolerance"
        assert summary.exact_match_months == summary.complete_months_compared

    def test_wrong_rule_is_reported_as_not_reproduced(self) -> None:
        daily = self._daily()
        monthly = aggregate_daily_to_monthly(daily, rule="calendar_day_mean") + 0.5
        frame = build_aggregation_difference_frame(
            monthly=monthly,
            daily=daily,
            monthly_series_id="M",
            daily_series_id="D",
            rule="calendar_day_mean",
        )
        assert summarise_aggregation(frame).verdict == "not_reproduced_within_declared_tolerance"

    def test_exact_decimal_check_resolves_rounding_ties(self, tmp_path: Path) -> None:
        dates = pd.date_range("2001-01-01", "2001-01-31", freq="D")
        values = ["1.14"] * 15 + ["1.15"] * 16
        daily_path = tmp_path / "daily.csv"
        daily_path.write_text(
            "DATE,D\n"
            + "\n".join(f"{d.date()},{v}" for d, v in zip(dates, values, strict=True))
            + "\n",
            encoding="utf-8",
        )
        exact = sum(Decimal(v) for v in values) / Decimal(len(values))
        published = exact.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        monthly_path = tmp_path / "monthly.csv"
        monthly_path.write_text(f"DATE,M\n2001-01-01,{published}\n", encoding="utf-8")
        check = exact_decimal_rounding_check(
            monthly_raw_path=monthly_path,
            daily_raw_path=daily_path,
            monthly_series_id="M",
            daily_series_id="D",
            rule="calendar_day_mean",
        )
        assert check.complete_months_compared == 1
        assert check.exact_decimal_matches == 1
        assert check.mismatched_months == ()

    def test_month_end_rule_is_rejected_for_the_decimal_check(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not a mean rule"):
            exact_decimal_rounding_check(
                monthly_raw_path=tmp_path / "m.csv",
                daily_raw_path=tmp_path / "d.csv",
                monthly_series_id="M",
                daily_series_id="D",
                rule="month_end_last_observation",
            )


class TestFreezeNormalization:
    """Normalization must be deterministic and preserve the provider missing code."""

    def test_missing_code_becomes_a_null_and_checksum_is_format_stable(self) -> None:
        payload = b"DATE,DTB3\n2001-01-01,1.00\n2001-01-02,.\n2001-01-03,1.50\n"
        reformatted = b"observation_date,DTB3\n2001-01-01,1.0000\n2001-01-02,.\n2001-01-03,1.5\n"
        first = _normalize_fred_payload(payload, "DTB3")
        second = _normalize_fred_payload(reformatted, "DTB3")
        assert int(first["value"].isna().sum()) == 1
        assert _canonical_csv_bytes(first) == _canonical_csv_bytes(second)

    def test_duplicate_dates_are_rejected(self) -> None:
        payload = b"DATE,DTB3\n2001-01-01,1.00\n2001-01-01,1.10\n"
        with pytest.raises(Exception, match="duplicate"):
            _normalize_fred_payload(payload, "DTB3")

    def test_a_payload_for_another_series_is_rejected(self) -> None:
        """Freezing another series under the requested id would corrupt provenance."""
        payload = b"observation_date,TB3MS\n2001-01-01,1.00\n2001-02-01,1.10\n"
        with pytest.raises(DataValidationError):
            _normalize_fred_payload(payload, "FEDFUNDS")

    def test_declared_metadata_is_audited_against_the_payload(self) -> None:
        index = pd.date_range("2001-01-01", periods=36, freq="MS")
        frame = pd.DataFrame({"date": index, "value": np.linspace(2.0, 6.0, len(index))})
        audit = audit_declared_metadata("FEDFUNDS", frame)
        assert audit["frequency_declared_vs_observed"] == "consistent"
        assert audit["units_magnitude_check"] == "consistent_with_percent_per_annum"
        assert audit["units_confirmed_against_provider_metadata_endpoint"] == "no"

    def test_every_declared_series_carries_the_required_metadata_fields(self) -> None:
        required = {
            "title",
            "units",
            "frequency",
            "seasonal_adjustment",
            "aggregation_of_source",
            "source_notes",
            "redistribution_status",
        }
        for series_id, metadata in DECLARED_SERIES_METADATA.items():
            assert required <= set(metadata), series_id


class TestMonthlyRateConversion:
    """Frozen monthly files must convert to period indexing without collisions."""

    def test_duplicate_months_are_rejected(self) -> None:
        index = pd.DatetimeIndex(["2001-01-01", "2001-01-15"])
        with pytest.raises(ValueError, match="more than one observation"):
            monthly_rate_from_freeze(pd.Series([1.0, 2.0], index=index))

    def test_conversion_preserves_order_and_values(self) -> None:
        index = pd.DatetimeIndex(["2001-02-01", "2001-01-01", "2001-03-01"])
        converted = monthly_rate_from_freeze(pd.Series([2.0, 1.0, 3.0], index=index))
        assert list(converted.index.astype(str)) == ["2001-01", "2001-02", "2001-03"]
        assert list(converted.to_numpy()) == [1.0, 2.0, 3.0]


@dataclass(frozen=True)
class PanelInputs:
    """Synthetic inputs for the canonical-panel tests."""

    level: pd.Series
    market: pd.Series
    risk_free: pd.Series
    portfolio: pd.DataFrame
    ar: dict[str, tuple[float, float]] = dataclass_field(default_factory=dict)


class TestCanonicalPanel:
    """The canonical panel must be an inner join with no shifts and no filling."""

    def _inputs(self) -> PanelInputs:
        index = pd.period_range("1971-12", "1985-12", freq="M")
        rng = np.random.default_rng(7)
        level = pd.Series(
            5.0 + np.cumsum(rng.normal(0.0, 0.3, len(index))).clip(-4.0, 20.0),
            index=index,
        ).clip(lower=0.05)
        market = pd.Series(rng.normal(0.6, 4.5, len(index)), index=index)
        risk_free = pd.Series(np.abs(rng.normal(0.4, 0.15, len(index))), index=index)
        portfolio = pd.DataFrame(
            rng.normal(1.0, 5.0, (len(index), 3)),
            index=index,
            columns=["decile_01", "decile_02", "decile_03"],
        )
        return PanelInputs(level=level, market=market, risk_free=risk_free, portfolio=portfolio)

    def _build(self) -> tuple[pd.DataFrame, PanelInputs]:
        parts = self._inputs()
        reconstruction = estimate_ar1_reconstruction(
            parts.level,
            series_id="rate",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        panel = build_baseline_panel(
            market_excess_return=parts.market,
            risk_free_return=parts.risk_free,
            short_rate_levels={"rate": parts.level},
            short_rate_innovations={"rate": reconstruction.innovations},
            portfolio_returns={"fam": parts.portfolio},
            window_start="1972-01",
            window_end="1985-12",
        )
        parts.ar["rate"] = (reconstruction.intercept, reconstruction.slope)
        return panel, parts

    def test_panel_passes_every_declared_check(self) -> None:
        panel, parts = self._build()
        report = validate_baseline_panel(
            panel,
            window_start="1972-01",
            window_end="1985-12",
            raw_portfolio_returns={"fam": parts.portfolio},
            short_rate_levels={"rate": parts.level},
            ar_parameters=parts.ar,
            market_excess_return=parts.market,
        )
        assert report.passed, report.checks
        assert report.sample_start == "1972-01"
        assert report.sample_end == "1985-12"
        assert report.rows == 168

    def test_endpoint_is_binding(self) -> None:
        parts = self._inputs()
        panel = build_baseline_panel(
            market_excess_return=parts.market,
            risk_free_return=parts.risk_free,
            short_rate_levels={"rate": parts.level},
            short_rate_innovations={},
            portfolio_returns={},
            window_start="1972-01",
            window_end="1980-06",
        )
        assert panel.index.max() == pd.Period("1980-06", freq="M")

    def test_a_shifted_innovation_is_detected(self) -> None:
        panel, parts = self._build()
        broken = panel.copy()
        broken["short_rate_innovation__rate"] = (
            broken["short_rate_innovation__rate"].shift(1).bfill()
        )
        report = validate_baseline_panel(
            broken,
            window_start="1972-01",
            window_end="1985-12",
            raw_portfolio_returns={"fam": parts.portfolio},
            short_rate_levels={"rate": parts.level},
            ar_parameters=parts.ar,
            market_excess_return=parts.market,
        )
        assert not report.checks["innovation_has_no_timing_shift"]
        assert not report.passed

    def test_a_shifted_market_factor_is_detected(self) -> None:
        panel, parts = self._build()
        broken = panel.copy()
        broken["market_excess_return"] = broken["market_excess_return"].shift(1).bfill()
        report = validate_baseline_panel(
            broken,
            window_start="1972-01",
            window_end="1985-12",
            raw_portfolio_returns={"fam": parts.portfolio},
            short_rate_levels={"rate": parts.level},
            ar_parameters=parts.ar,
            market_excess_return=parts.market,
        )
        assert not report.checks["market_factor_has_no_timing_shift"]

    def test_forward_filling_is_detected(self) -> None:
        panel, parts = self._build()
        broken = panel.copy()
        column = "portfolio_excess_return__fam__decile_01"
        values = broken[column].to_numpy(dtype=float).copy()
        values[10] = values[9]
        broken[column] = values
        report = validate_baseline_panel(
            broken,
            window_start="1972-01",
            window_end="1985-12",
            raw_portfolio_returns={"fam": parts.portfolio},
            short_rate_levels={"rate": parts.level},
            ar_parameters=parts.ar,
            market_excess_return=parts.market,
        )
        assert not report.checks["no_implicit_forward_filling"]

    def test_non_monthly_index_is_rejected(self) -> None:
        parts = self._inputs()
        market = parts.market.copy()
        market.index = pd.PeriodIndex(market.index, freq="M").to_timestamp()
        with pytest.raises(ValueError, match="monthly PeriodIndex"):
            build_baseline_panel(
                market_excess_return=market,
                risk_free_return=parts.risk_free,
                short_rate_levels={},
                short_rate_innovations={},
                portfolio_returns={},
                window_start="1972-01",
                window_end="1985-12",
            )

    def test_disjoint_inputs_are_rejected(self) -> None:
        parts = self._inputs()
        shifted = parts.risk_free.copy()
        shifted.index = shifted.index + 600
        with pytest.raises(ValueError, match="share no common month"):
            build_baseline_panel(
                market_excess_return=parts.market,
                risk_free_return=shifted,
                short_rate_levels={},
                short_rate_innovations={},
                portfolio_returns={},
                window_start="1972-01",
                window_end="1985-12",
            )

    def test_excess_returns_subtract_the_same_month_risk_free(self) -> None:
        panel, parts = self._build()
        expected = parts.portfolio["decile_02"].reindex(panel.index) - panel["risk_free_return"]
        np.testing.assert_allclose(
            panel["portfolio_excess_return__fam__decile_02"].to_numpy(dtype=float),
            expected.to_numpy(dtype=float),
            atol=1e-12,
        )


class TestGuardBranches:
    """Explicit coverage for reconstruction and panel guard branches."""

    def test_unsupported_timing_variant_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported timing variant"):
            estimate_ar1_reconstruction(
                _synthetic_rate(),
                series_id="s",
                replication_mode="test",
                timing_variant="lead_lag",  # type: ignore[arg-type]
                window_start="1972-01",
                window_end="1985-12",
            )

    def test_non_datetime_index_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="DatetimeIndex"):
            monthly_rate_from_freeze(pd.Series([1.0, 2.0], index=[0, 1]))

    def test_unrecognised_level_scale_is_reported(self) -> None:
        rate = _synthetic_rate() * 1000.0
        result = estimate_ar1_reconstruction(
            rate,
            series_id="s",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        assert result.unit_scale_audit["inferred_level_scale"] == "unrecognised"

    def test_unknown_published_statistic_is_skipped(self) -> None:
        result = estimate_ar1_reconstruction(
            _synthetic_rate(),
            series_id="s",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        comparison = compare_with_published(result, {"slope": 0.98, "half_life": 30.0})
        assert list(comparison["statistic"]) == ["slope"]

    def test_coefficient_only_match_is_classified_separately(self) -> None:
        result = estimate_ar1_reconstruction(
            _synthetic_rate(),
            series_id="s",
            replication_mode="documented_reconstruction",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        published = {
            "intercept": round(result.intercept_decimal_rate_units, 3),
            "slope": round(result.slope, 3),
            "r_squared": round(result.r_squared, 2),
            "t_intercept": round(result.intercept_t_ratio, 2),
            "t_slope": round(result.slope_t_ratio, 2),
            "standard_deviation": round(result.descriptives["standard_deviation"], 2) + 1.0,
        }
        comparison = compare_with_published(result, published)
        assert (
            classify_replication_target(
                comparison,
                replication_mode="documented_reconstruction",
                exact_input_available=False,
            )
            == "approximately_reproduced_coefficients_only_under_documented_reconstruction"
        )
        assert (
            classify_replication_target(
                comparison, replication_mode="exact", exact_input_available=True
            )
            == "approximately_reproduced"
        )

    def test_failed_coefficient_match_is_contradicted_only_with_an_exact_input(self) -> None:
        result = estimate_ar1_reconstruction(
            _synthetic_rate(),
            series_id="s",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        comparison = compare_with_published(result, {"slope": 0.10, "r_squared": 0.05})
        assert (
            classify_replication_target(
                comparison, replication_mode="exact", exact_input_available=True
            )
            == "contradicted"
        )
        assert (
            classify_replication_target(
                comparison,
                replication_mode="documented_reconstruction",
                exact_input_available=False,
            )
            == "not_reproduced_under_documented_reconstruction_exact_input_missing"
        )

    def test_duplicate_months_in_a_panel_input_are_rejected(self) -> None:
        index = pd.PeriodIndex(["1972-01", "1972-01"], freq="M")
        with pytest.raises(ValueError, match="duplicate months"):
            build_baseline_panel(
                market_excess_return=pd.Series([1.0, 2.0], index=index),
                risk_free_return=pd.Series([0.1, 0.2], index=index),
                short_rate_levels={},
                short_rate_innovations={},
                portfolio_returns={},
                window_start="1972-01",
                window_end="1972-01",
            )

    def test_declared_parameters_without_a_panel_column_are_harmless(self) -> None:
        index = pd.period_range("1972-01", "1975-12", freq="M")
        rng = np.random.default_rng(3)
        market = pd.Series(rng.normal(0.6, 4.0, len(index)), index=index)
        risk_free = pd.Series(np.abs(rng.normal(0.4, 0.1, len(index))), index=index)
        portfolio = pd.DataFrame(
            rng.normal(1.0, 5.0, (len(index), 1)), index=index, columns=["decile_01"]
        )
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1975-12",
        )
        report = validate_baseline_panel(
            panel,
            window_start="1972-01",
            window_end="1975-12",
            raw_portfolio_returns={"fam": portfolio, "absent": portfolio},
            short_rate_levels={"missing": pd.Series(dtype=float, index=index)},
            ar_parameters={"missing": (0.0, 0.9)},
            market_excess_return=market,
        )
        assert report.checks["innovation_has_no_timing_shift"]
        assert report.checks["excess_returns_use_same_month_risk_free"]


class TestPanelValidationHardening:
    """Gaps that let an incomplete or untraceable panel pass validation."""

    def _parts(self, end: str = "1985-12") -> tuple[pd.Series, pd.Series, pd.DataFrame]:
        index = pd.period_range("1971-12", end, freq="M")
        rng = np.random.default_rng(11)
        market = pd.Series(rng.normal(0.6, 4.5, len(index)), index=index)
        risk_free = pd.Series(np.abs(rng.normal(0.4, 0.12, len(index))), index=index)
        portfolio = pd.DataFrame(
            rng.normal(1.0, 5.0, (len(index), 2)),
            index=index,
            columns=["decile_01", "decile_02"],
        )
        return market, risk_free, portfolio

    def _validate(
        self,
        panel: pd.DataFrame,
        portfolio: pd.DataFrame,
        market: pd.Series,
        *,
        window_end: str = "1985-12",
        levels: dict[str, pd.Series] | None = None,
        ar: dict[str, tuple[float, float]] | None = None,
    ) -> PanelValidationReport:
        return validate_baseline_panel(
            panel,
            window_start="1972-01",
            window_end=window_end,
            raw_portfolio_returns={"fam": portfolio},
            short_rate_levels=levels or {},
            ar_parameters=ar or {},
            market_excess_return=market,
        )

    def test_a_panel_truncated_at_the_end_fails(self) -> None:
        market, risk_free, portfolio = self._parts()
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1984-06",
        )
        report = self._validate(panel, portfolio, market)
        assert not report.checks["panel_ends_exactly_at_window_end"]
        assert not report.checks["panel_covers_the_whole_frozen_window"]
        assert report.checks["no_observation_after_frozen_endpoint"]
        assert not report.passed

    def test_a_panel_truncated_at_the_start_fails(self) -> None:
        market, risk_free, portfolio = self._parts()
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1974-01",
            window_end="1985-12",
        )
        report = self._validate(panel, portfolio, market)
        assert not report.checks["panel_starts_exactly_at_window_start"]
        assert report.checks["no_observation_before_window_start"]
        assert not report.passed

    def test_a_missing_source_month_cannot_silently_shorten_the_window(self) -> None:
        market, risk_free, portfolio = self._parts()
        gapped = market.drop(pd.Period("1985-12", freq="M"))
        panel = build_baseline_panel(
            market_excess_return=gapped,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1985-12",
        )
        report = self._validate(panel, portfolio, gapped)
        assert not report.checks["panel_ends_exactly_at_window_end"]
        assert not report.passed

    def test_an_innovation_column_without_parameters_fails(self) -> None:
        market, risk_free, portfolio = self._parts()
        level = pd.Series(
            5.0 + np.cumsum(np.random.default_rng(5).normal(0, 0.3, len(market))).clip(-4, 20),
            index=market.index,
        ).clip(lower=0.05)
        reconstruction = estimate_ar1_reconstruction(
            level,
            series_id="rate",
            replication_mode="test",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={"rate": level},
            short_rate_innovations={"rate": reconstruction.innovations},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1985-12",
        )
        # Parameters deliberately withheld: the column can no longer be verified.
        report = self._validate(panel, portfolio, market, levels={"rate": level}, ar={})
        assert not report.checks["innovation_has_no_timing_shift"]
        assert "short_rate_innovation__rate" in report.details["unverifiable_innovation_columns"]
        assert not report.passed

    def test_a_portfolio_column_without_a_frozen_source_fails(self) -> None:
        market, risk_free, portfolio = self._parts()
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1985-12",
        )
        report = validate_baseline_panel(
            panel,
            window_start="1972-01",
            window_end="1985-12",
            raw_portfolio_returns={"fam": portfolio[["decile_01"]]},
            short_rate_levels={},
            ar_parameters={},
            market_excess_return=market,
        )
        assert not report.checks["excess_returns_use_same_month_risk_free"]
        assert "decile_02" in report.details["untraceable_portfolio_columns"]

    def test_a_decimal_scale_return_column_is_caught_per_column(self) -> None:
        market, risk_free, portfolio = self._parts()
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1985-12",
        )
        broken = panel.copy()
        broken["portfolio_excess_return__fam__decile_02"] = (
            broken["portfolio_excess_return__fam__decile_02"] / 100.0
        )
        report = self._validate(broken, portfolio, market)
        assert not report.checks["return_units_are_percent_per_month"]
        assert "decile_02" in report.details["return_columns_outside_declared_units"]

    def test_equal_adjacent_returns_do_not_count_as_forward_filling(self) -> None:
        """Provider returns are published to two decimals, so ties occur naturally."""
        market, risk_free, portfolio = self._parts()
        tied = portfolio.copy()
        values = tied["decile_01"].to_numpy(dtype=float).copy()
        values[20] = values[19]
        values[80] = values[79]
        tied["decile_01"] = values
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": tied},
            window_start="1972-01",
            window_end="1985-12",
        )
        report = self._validate(panel, tied, market)
        assert report.checks["no_implicit_forward_filling"]
        assert report.passed

    def test_a_genuine_forward_fill_is_still_caught(self) -> None:
        market, risk_free, portfolio = self._parts()
        panel = build_baseline_panel(
            market_excess_return=market,
            risk_free_return=risk_free,
            short_rate_levels={},
            short_rate_innovations={},
            portfolio_returns={"fam": portfolio},
            window_start="1972-01",
            window_end="1985-12",
        )
        broken = panel.copy()
        column = "portfolio_excess_return__fam__decile_01"
        values = broken[column].to_numpy(dtype=float).copy()
        values[30] = values[29]
        broken[column] = values
        report = self._validate(broken, portfolio, market)
        assert not report.checks["excess_returns_use_same_month_risk_free"]
        assert not report.checks["no_implicit_forward_filling"]


class TestPublishedComparisonUnits:
    """The published intercept must be compared in the units the article prints."""

    def _result(self) -> ARReconstruction:
        return estimate_ar1_reconstruction(
            _synthetic_rate(),
            series_id="s",
            replication_mode="documented_reconstruction",
            timing_variant="pre_window_lag",
            window_start="1972-01",
            window_end="1985-12",
        )

    def test_published_intercept_is_compared_in_decimal_rate_units(self) -> None:
        result = self._result()
        comparison = compare_with_published(result, {"intercept": 0.000})
        row = comparison.iloc[0]
        assert row["compared_attribute"] == "intercept_decimal_rate_units"
        assert row["comparison_units"] == "decimal_rate_units"
        assert row["reconstructed_value"] == pytest.approx(result.intercept / 100.0)
        assert row["reconstructed_value_percentage_points"] == pytest.approx(result.intercept)

    def test_the_comparison_is_a_hundredfold_tighter_than_in_percentage_points(self) -> None:
        """Guards the regression this fix addresses.

        Against a published target of 0.000 the percentage-point estimate is a
        hundred times further away than the decimal-rate-unit estimate, which is
        why comparing in the wrong units failed for every variant.
        """
        result = self._result()
        comparison = compare_with_published(result, {"intercept": 0.000})
        decimal_difference = float(comparison.iloc[0]["absolute_difference"])
        percentage_point_difference = abs(result.intercept)
        assert percentage_point_difference == pytest.approx(decimal_difference * 100.0, rel=1e-9)
        assert decimal_difference < percentage_point_difference

    def test_a_realistic_intercept_passes_in_decimal_units_and_fails_in_percent(self) -> None:
        result = self._result()
        # The article prints 0.046 percentage points as 0.000 in decimal units.
        realistic = 0.046
        assert abs(realistic / 100.0) < PUBLISHED_ROUNDING_TOLERANCE["intercept"]
        assert abs(realistic) > PUBLISHED_ROUNDING_TOLERANCE["intercept"]
        assert result.intercept_decimal_rate_units == pytest.approx(result.intercept / 100.0)

    def test_the_intercept_actually_reaches_the_classifier(self) -> None:
        result = self._result()
        comparison = compare_with_published(result, {"intercept": 0.000})
        assert set(comparison["statistic"]) & COEFFICIENT_STATISTICS

    def test_a_comparison_without_coefficients_is_not_vacuously_reproduced(self) -> None:
        result = self._result()
        comparison = compare_with_published(
            result,
            {
                "mean": round(result.descriptives["mean"], 2),
                "standard_deviation": round(result.descriptives["standard_deviation"], 2),
                "minimum": round(result.descriptives["minimum"], 2),
                "maximum": round(result.descriptives["maximum"], 2),
                "autocorrelation_1": round(result.descriptives["autocorrelation_1"], 2),
            },
        )
        assert classify_replication_target(
            comparison, replication_mode="exact", exact_input_available=True
        ) not in {"reproduced", "approximately_reproduced"}
