r"""Generate the manuscript's result figures from the frozen artifacts.

Two figures carry findings that a table states less legibly.

The first shows the short-rate innovation across the registered monetary
regimes. It is the paper's setting in one picture: the series that identifies
the factor loses almost all of its variation once the policy rate reaches the
effective lower bound, which is the fact behind both the temporal and the regime
results.

The second shows the rate-attributable fitted-premium spread per anomaly family
in the baseline window against the refitted extension. The sign reversals that
fail the temporal gates are visible at a glance and are hard to read off a
column of signed numbers.

Both figures are drawn only from artifact files. Like the generated tables, they
are covered by a drift guard so that a regenerated artifact cannot leave a stale
figure in the paper.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

# Headless rendering, so the figures build identically in CI and locally.
matplotlib.use("Agg")

FIGURE_ROOT = Path("paper/figures")

#: The rate columns and regime labels only. The full panel is not published,
#: so the figure reads the small companion artifact rather than the parquet.
REGIME_SERIES = Path("artifacts/tables/regimes/regime_monthly_series.csv")
REGIME_ELIGIBILITY = Path("artifacts/tables/regimes/regime_eligibility.csv")
SPREADS = Path("artifacts/tables/extension/fitted_premium_spreads.csv")

RATE = "fedfunds"

#: Regime labels short enough to sit under a time axis.
REGIME_SHORT_NAMES: dict[str, str] = {
    "conventional_pre_elb": "Conventional",
    "elb_qe": "ELB and QE",
    "normalisation": "Normalisation",
    "pandemic_elb_qe": "Pandemic",
    "inflation_tightening": "Tightening",
    "post_tightening_easing": "Easing",
}

FAMILY_LABELS: dict[str, str] = {
    "book_to_market": "Book to market",
    "earnings_to_price": "Earnings to price",
    "equity_duration": "Equity duration",
    "inventory_growth": "Inventory growth",
    "investment_to_assets": "Investment to assets",
    "long_term_reversal": "Long-term reversal",
    "ppe_investment": "PPE investment",
}


#: Pinning the embedded metadata removes the obvious sources of byte variation:
#: the creation date, the matplotlib version carried in ``Creator``, and the
#: backend in ``Producer``. It does not make the PDF a pure function of the
#: artifacts. Vector serialization details still change across matplotlib
#: releases, so byte equality holds only within one plotting environment. The
#: content manifest below is what the drift guard actually relies on.
DETERMINISTIC_METADATA: dict[str, str | None] = {
    "CreationDate": None,
    "Creator": "short-rate-anomaly-regimes",
    "Producer": "matplotlib",
}

#: Where the version-independent description of every figure is recorded.
CONTENT_MANIFEST = Path("paper/figures/figure_content.json")

#: Coordinates are rounded before they are recorded, so that a difference in the
#: last floating-point digit cannot be mistaken for a changed result.
COORDINATE_PRECISION = 9


@dataclass(frozen=True)
class FigureArtifact:
    """A rendered figure and the version-independent description of what it draws."""

    path: Path
    content: dict[str, Any]


def _round(values: Any) -> list[float | str]:
    """Coerce plotted coordinates to stable JSON scalars.

    Date axes hand back timestamps rather than numbers, and their float encoding
    is an epoch convention rather than a result, so they are recorded as ISO
    strings.
    """
    coordinates: list[float | str] = []
    for value in values:
        isoformat = getattr(value, "isoformat", None)
        coordinates.append(
            isoformat() if callable(isoformat) else round(float(value), COORDINATE_PRECISION)
        )
    return coordinates


def _axes_content(axis: Axes, explicit_xticklabels: list[str]) -> dict[str, Any]:
    """Describe everything the builders draw on one axis.

    Only artists placed explicitly are recorded. Autoscaled limits and
    automatically located ticks are excluded on purpose: they are matplotlib's
    layout decisions, they change across releases, and a change in one is not a
    change in the result. Everything captured here traces back to an artifact
    value, so a difference means the underlying numbers moved.
    """
    lines = [{"x": _round(line.get_xdata()), "y": _round(line.get_ydata())} for line in axis.lines]
    bars = [
        {
            "x": round(float(patch.get_x()), COORDINATE_PRECISION),
            "y": round(float(patch.get_y()), COORDINATE_PRECISION),
            "width": round(float(patch.get_width()), COORDINATE_PRECISION),
            "height": round(float(patch.get_height()), COORDINATE_PRECISION),
        }
        for patch in axis.patches
        if isinstance(patch, Rectangle)
    ]
    legend = axis.get_legend()
    return {
        "title": axis.get_title(),
        "xlabel": axis.get_xlabel(),
        "ylabel": axis.get_ylabel(),
        "lines": lines,
        "bars": bars,
        "explicit_xticklabels": explicit_xticklabels,
        # The x position is data derived; the y position is read off an
        # autoscaled limit, so it is deliberately not recorded.
        "annotations": sorted(
            text.get_text() for text in axis.texts if text.get_text() != axis.get_title()
        ),
        "legend": [text.get_text() for text in legend.get_texts()] if legend else [],
    }


def figure_content(
    figure: Figure,
    explicit_xticklabels: dict[int, list[str]] | None = None,
) -> dict[str, Any]:
    """Describe a figure in terms that do not depend on the plotting library version.

    Tick labels are supplied by the caller rather than read back off the axis.
    ``Axes.get_xticklabels`` cannot distinguish a label the builder chose from
    one matplotlib generated, and on the date axis the generated labels depend
    on the installed locator and formatter, so reading them back would put the
    version dependence straight back into a manifest that exists to remove it.
    The builder is the only place that knows which labels are results.
    """
    supplied = explicit_xticklabels or {}
    return {
        "axes": [
            _axes_content(axis, supplied.get(index, [])) for index, axis in enumerate(figure.axes)
        ]
    }


def _as_float(value: Any) -> float:
    """Narrow a pandas cell to a float.

    Indexing a DataFrame yields a broad union under the pandas stubs, so the
    conversion is funnelled through one annotated helper.
    """
    return float(value)


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.5,
            "figure.dpi": 200,
            "savefig.bbox": "tight",
        }
    )


def build_regime_innovation_figure() -> FigureArtifact:
    """Plot the short-rate level and innovation across the registered regimes."""
    panel = pd.read_csv(REGIME_SERIES)
    panel["month"] = pd.PeriodIndex(
        [pd.Period(str(value), freq="M") for value in panel["month"]], freq="M"
    ).to_timestamp(how="start")
    eligibility = pd.read_csv(REGIME_ELIGIBILITY)

    figure, (upper, lower) = plt.subplots(
        2, 1, figsize=(7.0, 4.4), sharex=True, height_ratios=(1.0, 1.0)
    )

    boundaries = [
        panel.loc[panel["regime_primary"] == regime, "month"].min()
        for regime in eligibility["regime_id"]
    ]
    for axis in (upper, lower):
        for boundary in boundaries[1:]:
            axis.axvline(boundary, color="0.55", linewidth=0.6, linestyle=(0, (4, 3)))

    upper.plot(panel["month"], panel[f"short_rate_level__{RATE}"], color="black", linewidth=0.9)
    upper.set_ylabel("Level, percent")
    upper.set_title(
        "Federal funds rate and its AR(1) innovation across registered regimes", fontsize=9.5
    )

    lower.axhline(0.0, color="0.6", linewidth=0.6)
    lower.plot(
        panel["month"], panel[f"short_rate_innovation__{RATE}"], color="black", linewidth=0.7
    )
    lower.set_ylabel("Innovation")
    lower.set_xlabel("")

    span = panel["month"].max() - panel["month"].min()
    for regime in eligibility["regime_id"]:
        window = panel.loc[panel["regime_primary"] == regime, "month"]
        centre = window.min() + (window.max() - window.min()) / 2
        months = int(eligibility.loc[eligibility["regime_id"] == regime, "months"].iloc[0])
        # Only the two long regimes have room for an in-axis label.
        if (window.max() - window.min()) > span * 0.1:
            upper.annotate(
                f"{REGIME_SHORT_NAMES[str(regime)]}\n{months} months",
                xy=(centre, upper.get_ylim()[1]),
                ha="center",
                va="top",
                fontsize=7.5,
                color="0.35",
            )

    figure.align_ylabels((upper, lower))
    path = FIGURE_ROOT / "regime_innovation.pdf"
    figure.savefig(path, metadata=DETERMINISTIC_METADATA)
    content = figure_content(figure)
    plt.close(figure)
    return FigureArtifact(path=path, content=content)


def build_spread_reversal_figure() -> FigureArtifact:
    """Plot per-family fitted-premium spreads, baseline against refitted extension."""
    frame = pd.read_csv(SPREADS).set_index("family")
    families = [family for family in FAMILY_LABELS if family in frame.index]
    baseline = [_as_float(frame.loc[family, "baseline_spread"]) for family in families]
    extension = [_as_float(frame.loc[family, "refitted_spread"]) for family in families]

    order = sorted(range(len(families)), key=lambda index: baseline[index])
    families = [families[index] for index in order]
    baseline = [baseline[index] for index in order]
    extension = [extension[index] for index in order]

    figure, axis = plt.subplots(figsize=(7.0, 3.1))
    positions = range(len(families))
    axis.axhline(0.0, color="0.4", linewidth=0.7)
    width = 0.38
    axis.bar(
        [position - width / 2 for position in positions],
        baseline,
        width=width,
        color="0.25",
        label="Baseline, 1972\u20132013",
    )
    axis.bar(
        [position + width / 2 for position in positions],
        extension,
        width=width,
        color="0.72",
        edgecolor="0.35",
        linewidth=0.4,
        label="Refitted extension, 2014\u20132025",
    )
    axis.set_xticks(list(positions))
    axis.set_xticklabels([FAMILY_LABELS[family] for family in families], rotation=20, ha="right")
    axis.set_ylabel("Fitted-premium spread")
    axis.set_title(
        "Rate-attributable fitted-premium spread, extreme deciles, by anomaly family",
        fontsize=9.5,
    )
    axis.legend(frameon=False, fontsize=8, loc="upper left")

    path = FIGURE_ROOT / "spread_reversal.pdf"
    figure.savefig(path, metadata=DETERMINISTIC_METADATA)
    # The family order is data driven: it is the baseline-spread sort above, so a
    # changed spread that reorders the bars shows up here as well as in the geometry.
    content = figure_content(figure, {0: [FAMILY_LABELS[family] for family in families]})
    plt.close(figure)
    return FigureArtifact(path=path, content=content)


BUILDERS = (build_regime_innovation_figure, build_spread_reversal_figure)


def build_all() -> list[FigureArtifact]:
    """Regenerate every manuscript result figure."""
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    _style()
    return [builder() for builder in BUILDERS]


def build_content_manifest() -> dict[str, Any]:
    """Return the version-independent content of every figure, keyed by file name."""
    return {artifact.path.name: artifact.content for artifact in build_all()}


def main() -> None:
    """Write every generated figure, its content manifest, and its provenance."""
    artifacts = build_all()
    for artifact in artifacts:
        print(f"wrote {artifact.path.as_posix()}")

    content = {artifact.path.name: artifact.content for artifact in artifacts}
    CONTENT_MANIFEST.write_text(
        json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"wrote {CONTENT_MANIFEST.as_posix()}")

    manifest: dict[str, Any] = {
        "script": "scripts/build_manuscript_figures.py",
        "figures": sorted(artifact.path.name for artifact in artifacts),
        "content_manifest": CONTENT_MANIFEST.as_posix(),
        "sources": [
            REGIME_SERIES.as_posix(),
            REGIME_ELIGIBILITY.as_posix(),
            SPREADS.as_posix(),
        ],
        "replication_status": "documented_reconstruction",
    }
    provenance = Path("artifacts/provenance/manuscript_figures.json")
    with provenance.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
