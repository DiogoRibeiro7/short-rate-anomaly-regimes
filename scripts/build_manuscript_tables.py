r"""Generate the manuscript's result tables from the frozen artifacts.

Every numeric cell in the paper's result tables is produced here and written to
``paper/tables/*.tex``, which the manuscript includes. Nothing is transcribed by
hand, so a regenerated artifact cannot silently disagree with the published
table, and ``tests/test_manuscript_tables.py`` fails if the committed ``.tex``
files drift from what this script produces.

Each emitted row carries a trailing ``% artifact:`` comment naming the file the
row came from. ``validate_manuscript`` follows the manuscript's ``\\input``
directives, so those tags are checked by the same rule that governs numbers
written directly into the manuscript.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

TABLE_ROOT = Path("paper/tables")

AR1_COMPARISON = Path("artifacts/tables/factors/ar1_published_target_comparison.csv")
BASELINE_PRICES = Path("artifacts/tables/cross_section/baseline_risk_prices.csv")
H1_PRIMARY = Path("artifacts/tables/robustness/h1_primary_comparison.csv")
TEMPORAL = Path("artifacts/tables/extension/temporal_evaluation.csv")
REGIME_SECOND_PASS = Path("artifacts/tables/regimes/regime_second_pass.csv")
REGIME_ELIGIBILITY = Path("artifacts/tables/regimes/regime_eligibility.csv")
TARGET_AUDIT = Path("artifacts/audit/published_target_audit.csv")
LAYERS = Path("artifacts/audit/replication_layer_classification.csv")
R1A_CLASSIFICATION = Path("artifacts/diagnostics/rates/r1a_classification.csv")

HEADLINE_SET = "all_seven_families_joint"
TIMING = "pre_window_lag"

#: Registered models in the order the manuscript presents them, with the column
#: holding each model's own short-rate risk price where it has one.
BASELINE_MODELS: tuple[tuple[str, str, str | None], ...] = (
    ("capm", "CAPM", None),
    ("market_plus_fedfunds_innovation", "Market + funds-rate", "lambda_FFR_innovation"),
    ("market_plus_tbill_innovation", "Market + bill-rate", "lambda_TB_innovation"),
    ("fama_french_3", "Fama-French three", None),
    ("carhart_4", "Carhart four", None),
    ("fama_french_5", "Fama-French five", None),
    ("q_factor", "$q$-factor", None),
    ("liquidity", "Liquidity", None),
)

#: Statistic key to the label used in the recovery table.
RECOVERY_STATISTICS: tuple[tuple[str, str], ...] = (
    ("lambda_market", "Market risk price"),
    ("lambda_rate", "Rate risk price"),
    ("r2_ols", "Cross-sectional fit"),
    ("chi_square", "Specification statistic"),
    ("r2_constrained", "Constrained fit"),
)

TEMPORAL_ROWS: tuple[tuple[str, str], ...] = (
    ("locked_baseline_1972_2013", "Locked baseline, 1972--2013"),
    ("revised_history_1972_2013", "Revised history, same months"),
    ("frozen_parameter_extension_2014_2025", "Frozen parameters on 2014--2025"),
    ("refitted_extension_2014_2025", "Refitted extension, 2014--2025"),
)

REGIME_LABELS: dict[str, str] = {
    "conventional_pre_elb": "Conventional, 1972--2008",
    "elb_qe": "Lower bound, 2009--2015",
}


def _as_float(value: Any) -> float:
    """Narrow a pandas cell to a float.

    Indexing a DataFrame yields a broad union under the pandas stubs, so the
    conversion is funnelled through one annotated helper rather than repeated
    with a cast at every call site.
    """
    return float(value)


def _as_int(value: Any) -> int:
    """Narrow a pandas cell to an int."""
    return int(value)


def _number(value: float | None, places: int) -> str:
    """Render one cell, using an em dash where the model has no such parameter."""
    if value is None or pd.isna(value):
        return "---"
    return f"{value:.{places}f}".replace("-", "$-$")


#: Any emitted line carrying a numeral must name the artifact it came from, the
#: same rule the manuscript itself obeys. Captions and column headers contain
#: sample dates and symbols such as ``\chi^2``, so tagging is applied to every
#: line rather than to data rows only.
NUMERIC = re.compile(r"(?<![A-Za-z_])[-+]?\d+(?:\.\d+)?(?![A-Za-z_])")


def _document(lines: Iterable[str], tag: str) -> str:
    tagged: list[str] = []
    for line in lines:
        body = line.split("%", 1)[0]
        # ``\begin{tabular}`` carries column widths rather than claims, and the
        # validator exempts it for that reason; tagging it would be noise.
        exempt = body.lstrip().startswith("\\begin{tabular}")
        needs_tag = not exempt and NUMERIC.search(body) is not None and "% artifact:" not in line
        tagged.append(f"{line} {tag}" if needs_tag else line)
    return "\n".join(tagged) + "\n"


def _write(name: str, lines: Iterable[str], tag: str) -> Path:
    path = TABLE_ROOT / f"{name}.tex"
    # Explicit LF: git normalises these files to LF, and a CRLF write would
    # make the bytes on disk differ from the bytes the repository stores.
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(_document(lines, tag))
    return path


def build_ar1_table() -> Path:
    """Emit the short-rate reconstruction against its published targets."""
    frame = pd.read_csv(AR1_COMPARISON)
    frame = frame[frame["timing_variant"] == TIMING].set_index(["series_id", "statistic"])
    tag = f"% artifact: {AR1_COMPARISON.as_posix()}"

    rows: list[str] = []
    for series, label in (("FEDFUNDS", "Federal funds"), ("TB3MS", "Treasury bill")):

        def cell(statistic: str, places: int, column: str, name: str = series) -> str:
            return _number(_as_float(frame.loc[(name, statistic), column]), places)

        rows.append(
            f"{label}, reconstructed & {cell('intercept', 6, 'reconstructed_value')} & "
            f"{cell('slope', 4, 'reconstructed_value')} & "
            f"{cell('t_slope', 2, 'reconstructed_value')} & "
            f"{cell('r_squared', 4, 'reconstructed_value')} & "
            f"{cell('standard_deviation', 4, 'reconstructed_value')} \\\\ {tag}"
        )
        rows.append(
            f"{label}, published & {cell('intercept', 3, 'published_value')} & "
            f"{cell('slope', 3, 'published_value')} & --- & "
            f"{cell('r_squared', 2, 'published_value')} & "
            f"{cell('standard_deviation', 2, 'published_value')} \\\\ {tag}"
        )

    return _write(
        "ar1",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Short-rate innovation reconstruction, 1972-01 to 2013-12, under the",
            "recovered pre-window-lag timing convention. Published values are those printed",
            "by \\citet{maio_santaclara_2017}. The intercept is in decimal rate units and the",
            "innovation standard deviation in annualized percentage points.}",
            "\\label{tab:ar1}",
            "\\begin{tabular}{lccccc}",
            "\\toprule",
            "Series & Intercept & Slope & Slope $t$ & $R^2$ & Innovation s.d. \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


def build_baseline_table() -> Path:
    """Emit the baseline cross-sectional pricing table for all registered models."""
    frame = pd.read_csv(BASELINE_PRICES)
    frame = frame[frame["portfolio_set"] == HEADLINE_SET].set_index("model")
    tag = f"% artifact: {BASELINE_PRICES.as_posix()}"

    rows: list[str] = []
    for index, (model, label, rate_column) in enumerate(BASELINE_MODELS):
        row = frame.loc[model]
        rate = _as_float(row[rate_column]) if rate_column else None
        rate_t = (
            _as_float(row[f"shanken_t_{rate_column.removeprefix('lambda_')}"])
            if rate_column
            else None
        )
        rows.append(
            f"{label} & {_number(_as_float(row['lambda_RM']), 3)} & {_number(rate, 3)} & "
            f"{_number(_as_float(row['root_mean_squared_pricing_error']), 4)} & "
            f"{_number(_as_float(row['mean_absolute_pricing_error']), 4)} & "
            f"{_number(_as_float(row['max_absolute_pricing_error']), 4)} & "
            f"{_number(_as_float(row['article_cross_sectional_fit']), 3)} & "
            f"{_number(_as_float(row['chi_square_statistic']), 2)} "
            f"({_as_float(row['chi_square_asymptotic_p_value']):.3f}) \\\\ {tag}"
        )
        rows.append(
            f" & ({_number(_as_float(row['shanken_t_RM']), 2)}) & "
            f"{'(' + _number(rate_t, 2) + ')' if rate_column else ''} & & & & & \\\\ {tag}"
        )
        if index == 2:
            rows.append("\\midrule")

    return _write(
        "baseline",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\small",
            "\\caption{Baseline cross-sectional pricing, joint seventy-portfolio system,",
            "1972-01 to 2013-12, 504 months. Risk prices are monthly percentage points with",
            "Shanken $t$-ratios beneath. Fit is the article's centred cross-sectional variance",
            "ratio. All rows carry the label \\texttt{documented\\_reconstruction}.}",
            "\\label{tab:baseline}",
            "\\begin{tabular}{lccccccc}",
            "\\toprule",
            "Model & $\\lambda_{RM}$ & $\\lambda_{\\text{rate}}$ & RMSE & MAE & "
            "$\\max|\\alpha|$ & Fit & $\\chi^2$ ($p$) \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


def build_h1_table() -> Path:
    """Emit the incremental-pricing materiality gates."""
    frame = pd.read_csv(H1_PRIMARY)
    row = frame[
        (frame["portfolio_set"] == HEADLINE_SET)
        & (frame["treatment_model"] == "market_plus_fedfunds_innovation")
        & (frame["comparison_role"] == "primary")
    ].iloc[0]
    tag = f"% artifact: {H1_PRIMARY.as_posix()}"

    gates = (
        ("RMSE reduction", "rmse_relative_reduction", "relative"),
        ("MAE reduction", "mae_relative_reduction", "relative"),
        ("$\\max|\\alpha|$ reduction", "max_absolute_error_reduction", "absolute"),
    )
    rows: list[str] = []
    for label, prefix, kind in gates:
        passed = bool(row[f"{prefix}__passed"])
        observed = _as_float(row[f"{prefix}__observed"])
        threshold = _as_float(row[f"{prefix}__threshold"])
        if kind == "relative":
            bound = f"$\\geq {threshold:.0%}$".replace("%", "\\%")
            seen = f"{observed:.1%}".replace("%", "\\%")
        else:
            bound = f"$\\geq {threshold:.2f}$ pp"
            seen = f"{observed:.4f} pp"
        verdict = "pass" if passed else "\\textbf{fail}"
        rows.append(
            f"{label} & {bound} & "
            f"{_number(_as_float(row[f'{prefix}__comparator_value']), 4)} & "
            f"{_number(_as_float(row[f'{prefix}__treatment_value']), 4)} & "
            f"{verdict}, {seen} \\\\ {tag}"
        )

    return _write(
        "h1",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Incremental-pricing materiality against the ex ante CAPM comparator,",
            "joint seventy-portfolio system. All three gates must hold for the claim to be",
            "supported; the registered classification is"
            " \\texttt{" + str(row["classification"]) + "}.}",
            "\\label{tab:h1}",
            "\\begin{tabular}{lcccl}",
            "\\toprule",
            "Gate & Threshold & CAPM & Market + rate & Result \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


def build_temporal_table() -> Path:
    """Emit the four temporal evaluations."""
    frame = pd.read_csv(TEMPORAL).set_index("evaluation")
    tag = f"% artifact: {TEMPORAL.as_posix()}"
    rows = [
        f"{label} & {_as_int(frame.loc[key, 'months'])} & "
        f"{_number(_as_float(frame.loc[key, 'lambda_market']), 4)} & "
        f"{_number(_as_float(frame.loc[key, 'lambda_rate']), 4)} & "
        f"{_number(_as_float(frame.loc[key, 'rmse']), 4)} & "
        f"{_number(_as_float(frame.loc[key, 'article_fit']), 3)} \\\\ {tag}"
        for key, label in TEMPORAL_ROWS
    ]
    return _write(
        "temporal",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Temporal evaluations. The locked baseline and revised history share",
            "months and differ in vintage; the revised history and refitted extension share",
            "vintage and differ in months, so differencing isolates one change at a time.}",
            "\\label{tab:temporal}",
            "\\begin{tabular}{lccccc}",
            "\\toprule",
            "Evaluation & Months & $\\lambda_{RM}$ & $\\lambda_{\\text{rate}}$ & RMSE & Fit \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


def build_regime_table() -> Path:
    """Emit the regime-specific second passes for the eligible regimes."""
    frame = pd.read_csv(REGIME_SECOND_PASS).set_index("regime_id")
    tag = f"% artifact: {REGIME_SECOND_PASS.as_posix()}"
    rows = [
        f"{label} & {_as_int(frame.loc[key, 'months'])} & "
        f"{_number(_as_float(frame.loc[key, 'lambda_market']), 3)} & "
        f"{_number(_as_float(frame.loc[key, 'lambda_rate']), 4)} & "
        f"{_number(_as_float(frame.loc[key, 'shanken_t_rate']), 2)} & "
        f"{_number(_as_float(frame.loc[key, 'rmse']), 4)} & "
        f"{_number(_as_float(frame.loc[key, 'article_fit']), 3)} & "
        f"{_number(_as_float(frame.loc[key, 'dispersion_of_fitted_premia']), 4)} \\\\ {tag}"
        for key, label in REGIME_LABELS.items()
        if bool(frame.loc[key, "standalone_second_pass"])
    ]
    return _write(
        "regimes",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Regime-specific second passes on the joint seventy-portfolio system,",
            "current vintage throughout. Only regimes clearing the frozen eligibility floors",
            "appear. Dispersion is the cross-sectional standard deviation of",
            "rate-attributable fitted premia.}",
            "\\label{tab:regimes}",
            "\\begin{tabular}{lccccccc}",
            "\\toprule",
            "Regime & Months & $\\lambda_{RM}$ & $\\lambda_{\\text{rate}}$ & Shanken $t$ & "
            "RMSE & Fit & Dispersion \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


def build_eligibility_table() -> Path:
    """Emit the regime eligibility tiers."""
    frame = pd.read_csv(REGIME_ELIGIBILITY)
    tag = f"% artifact: {REGIME_ELIGIBILITY.as_posix()}"
    rows = [
        f"\\texttt{{{str(row['regime_id']).replace('_', '\\_')}}} & "
        f"{row['start_month']} to {row['end_month']} & {_as_int(row['months'])} & "
        f"{'yes' if bool(row['standalone_second_pass_permitted']) else 'no'} & "
        f"{'yes' if bool(row['regime_specific_first_pass_permitted']) else 'no'} \\\\ {tag}"
        for _, row in frame.iterrows()
    ]
    return _write(
        "eligibility",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Registered monetary regimes and their estimation eligibility under the",
            "frozen floors. Regimes without a standalone second pass enter the analysis only",
            "through the pooled interaction model.}",
            "\\label{tab:eligibility}",
            "\\begin{tabular}{llccc}",
            "\\toprule",
            "Regime & Window & Months & Second pass & First pass \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


def build_recovery_table() -> Path:
    """Emit cell-level recovery by statistic, collapsing repeated point estimates."""
    frame = pd.read_csv(TARGET_AUDIT)
    unique = frame.drop_duplicates(subset=["source_table", "portfolio_set", "model", "statistic"])
    tag = f"% artifact: {TARGET_AUDIT.as_posix()}"

    rows: list[str] = []
    for statistic, label in RECOVERY_STATISTICS:
        subset = unique[unique["statistic"] == statistic]
        if subset.empty:
            continue
        recovered = int(subset["within_published_rounding"].sum())
        difference = subset["difference"].abs()
        rows.append(
            f"{label} & {len(subset)} & {recovered} & "
            f"{recovered / len(subset):.3f} & {difference.median():.4f} & "
            f"{difference.max():.4f} \\\\ {tag}"
        )

    comparator = unique[unique["statistic"].str.startswith("lambda_")]
    comparator = comparator[~comparator["statistic"].isin({"lambda_market", "lambda_rate"})]
    if not comparator.empty:
        recovered = int(comparator["within_published_rounding"].sum())
        difference = comparator["difference"].abs()
        rows.append(
            f"Comparator factor prices & {len(comparator)} & {recovered} & "
            f"{recovered / len(comparator):.3f} & {difference.median():.4f} & "
            f"{difference.max():.4f} \\\\ {tag}"
        )

    return _write(
        "recovery",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Cell-level recovery by statistic. A cell counts as recovered when it",
            "agrees with the article to the precision the article prints, that is within half",
            "of the last printed increment.}",
            "\\label{tab:recovery}",
            "\\begin{tabular}{lccccc}",
            "\\toprule",
            "Statistic & Cells & Recovered & Share & Median $|\\Delta|$ & Max $|\\Delta|$ \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


#: Layer descriptions. These name what each layer covers; they carry no numbers.
LAYER_DESCRIPTIONS: dict[str, str] = {
    "R1a": "short-rate innovations",
    "R1b": "first-pass betas",
    "R1c": "risk prices",
    "R1d": "pricing errors and fit",
    "R1e": "comparator models",
}


def build_layer_table() -> Path:
    """Emit the replication layer classification.

    The short-rate layer is classified in its own artifact rather than in the
    cell-level table, because the article prints its Table 1 statistics outside
    the pricing tables the audit walks.
    """
    frame = pd.read_csv(LAYERS)
    tag = f"% artifact: {LAYERS.as_posix()}"
    rate_tag = f"% artifact: {R1A_CLASSIFICATION.as_posix()}"

    rate = pd.read_csv(R1A_CLASSIFICATION)
    rate = rate[rate["timing_variant"] == TIMING]
    rate = rate[rate["replication_mode"] == "documented_reconstruction"]
    rate_class = str(rate["r1a_classification"].iloc[0]).replace("_", " ")
    rows = [f"R1a {LAYER_DESCRIPTIONS['R1a']} & per series & {rate_class} \\\\ {rate_tag}"]
    for _, row in frame.iterrows():
        layer = str(row["layer"])
        compared = _as_int(row["cells_compared"])
        recovered = "---" if compared == 0 else f"{_as_int(row['cells_recovered'])} of {compared}"
        rows.append(
            f"{layer} {LAYER_DESCRIPTIONS.get(layer, '')} & {recovered} & "
            f"{str(row['classification']).replace('_', ' ')} \\\\ {tag}"
        )
    return _write(
        "layers",
        [
            "\\begin{table}[htbp]",
            "\\centering",
            "\\caption{Replication layer classification. No layer is eligible for an",
            "exact-replication label, because no input is an exact article input.}",
            "\\label{tab:layers}",
            "\\begin{tabular}{p{0.30\\linewidth}p{0.14\\linewidth}p{0.44\\linewidth}}",
            "\\toprule",
            "Layer & Recovered & Classification \\\\",
            "\\midrule",
            *rows,
            "\\bottomrule",
            "\\end{tabular}",
            "\\end{table}",
        ],
        tag,
    )


BUILDERS = (
    build_ar1_table,
    build_baseline_table,
    build_h1_table,
    build_temporal_table,
    build_regime_table,
    build_eligibility_table,
    build_recovery_table,
    build_layer_table,
)


def build_all() -> list[Path]:
    """Regenerate every manuscript result table."""
    TABLE_ROOT.mkdir(parents=True, exist_ok=True)
    return [builder() for builder in BUILDERS]


def main() -> None:
    """Write every generated table and report where it went."""
    for path in build_all():
        print(f"wrote {path.as_posix()}")
    manifest = {
        "script": "scripts/build_manuscript_tables.py",
        "tables": sorted(path.name for path in TABLE_ROOT.glob("*.tex")),
        "replication_status": "documented_reconstruction",
    }
    provenance = Path("artifacts/provenance/manuscript_tables.json")
    with provenance.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
