"""Specification, weak-factor, and influence diagnostics."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f as f_distribution  # type: ignore[import-untyped]

RobustnessVerdict = Literal["robust", "conditionally_robust", "fragile", "unidentified"]
RobustnessFamily = Literal[
    "rate_definition",
    "covariance_bootstrap",
    "portfolio_weighting",
    "test_asset_composition",
    "crisis_influence",
    "sample_endpoints",
    "comparator_factor_models",
]


@dataclass(frozen=True, slots=True)
class WeakFactorReport:
    """Weak-factor diagnostics for a beta matrix and factor panel."""

    rank: int
    n_assets: int
    n_factors: int
    singular_values: tuple[float, ...]
    condition_number: float
    beta_dispersion: dict[str, float]
    factor_spanning: pd.DataFrame
    irrelevant_factors: tuple[str, ...]
    unidentified: bool


@dataclass(frozen=True, slots=True)
class RobustnessDecisionRules:
    """Predeclared robustness classification thresholds."""

    max_material_risk_price_change: float = 0.25
    max_material_rmse_change: float = 0.25
    max_material_mae_change: float = 0.25
    max_material_alpha_change: float = 0.25
    require_no_sign_reversal: bool = True


@dataclass(frozen=True, slots=True)
class RobustnessConclusion:
    """Robustness verdict and supporting rule failures."""

    verdict: RobustnessVerdict
    rule_failures: tuple[str, ...]


DEFAULT_ROBUSTNESS_DECISION_RULES = RobustnessDecisionRules()


def weak_factor_diagnostics(*, betas: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Return compact diagnostics for weak or irrelevant factors."""
    report = weak_factor_report(betas=betas, factors=factors)
    payload: dict[str, float | int | bool | str] = {
        "rank": report.rank,
        "n_assets": report.n_assets,
        "n_factors": report.n_factors,
        "condition_number": report.condition_number,
        "min_singular_value": min(report.singular_values),
        "max_singular_value": max(report.singular_values),
        "unidentified": report.unidentified,
        "irrelevant_factors": ",".join(report.irrelevant_factors),
    }
    for factor_name, dispersion in report.beta_dispersion.items():
        payload[f"beta_dispersion_{factor_name}"] = dispersion
    return pd.Series(payload)


def weak_factor_report(
    *,
    betas: pd.DataFrame,
    factors: pd.DataFrame,
    irrelevant_dispersion_threshold: float = 1e-8,
) -> WeakFactorReport:
    """Compute rank, singular values, dispersion, and spanning diagnostics."""
    if betas.empty:
        raise ValueError("Beta matrix cannot be empty")
    if factors.empty:
        raise ValueError("Factor panel cannot be empty")
    missing_factors = set(betas.columns) - set(factors.columns)
    if missing_factors:
        raise ValueError(
            f"Factor panel is missing beta columns: {', '.join(sorted(missing_factors))}"
        )
    beta_values = betas.to_numpy(dtype=float)
    singular_values = np.linalg.svd(beta_values, compute_uv=False)
    min_singular = float(singular_values.min())
    max_singular = float(singular_values.max())
    rank = int(np.linalg.matrix_rank(beta_values))
    condition_number = float("inf") if min_singular == 0.0 else max_singular / min_singular
    beta_dispersion = {
        str(column): float(pd.to_numeric(betas[column], errors="raise").std(ddof=1))
        for column in betas.columns
    }
    irrelevant_factors = tuple(
        factor
        for factor, dispersion in beta_dispersion.items()
        if dispersion <= irrelevant_dispersion_threshold
    )
    spanning = factor_spanning_tests(factors.loc[:, list(betas.columns)])
    unidentified = rank < len(betas.columns) or bool(irrelevant_factors)
    return WeakFactorReport(
        rank=rank,
        n_assets=int(betas.shape[0]),
        n_factors=int(betas.shape[1]),
        singular_values=tuple(float(value) for value in singular_values),
        condition_number=condition_number,
        beta_dispersion=beta_dispersion,
        factor_spanning=spanning,
        irrelevant_factors=irrelevant_factors,
        unidentified=unidentified,
    )


def factor_spanning_tests(factors: pd.DataFrame) -> pd.DataFrame:
    """Regress each factor on the others to diagnose spanning and redundancy."""
    if factors.shape[1] < 2:
        return pd.DataFrame(columns=["factor", "r_squared", "residual_std", "spanned"])
    clean = factors.astype(float).dropna()
    if clean.empty:
        raise ValueError("Factor panel has no complete observations")
    rows: list[dict[str, float | str | bool]] = []
    for factor_name in clean.columns:
        target_std = float(clean[factor_name].std(ddof=1))
        if target_std <= 1e-12:
            rows.append(
                {
                    "factor": str(factor_name),
                    "r_squared": 1.0,
                    "residual_std": 0.0,
                    "spanned": True,
                }
            )
            continue
        others = clean.drop(columns=[factor_name])
        design = sm.add_constant(others, has_constant="add")
        model = sm.OLS(clean[factor_name], design).fit()
        residual_std = float(model.resid.std(ddof=1))
        rows.append(
            {
                "factor": str(factor_name),
                "r_squared": float(model.rsquared),
                "residual_std": residual_std,
                "spanned": bool(float(model.rsquared) >= 0.99 or residual_std <= 1e-8),
            }
        )
    return pd.DataFrame(rows)


def holm_correction(p_values: pd.Series) -> pd.DataFrame:
    """Apply Holm correction within one registered robustness family."""
    if p_values.empty:
        raise ValueError("p_values cannot be empty")
    clean = pd.to_numeric(p_values, errors="raise").sort_values()
    m = clean.shape[0]
    adjusted_values: dict[str, float] = {}
    running_max = 0.0
    for rank, (name, p_value) in enumerate(clean.items(), start=1):
        adjusted = min(1.0, float(p_value) * (m - rank + 1))
        running_max = max(running_max, adjusted)
        adjusted_values[str(name)] = running_max
    return pd.DataFrame(
        {
            "p_value": p_values.astype(float),
            "holm_p_value": pd.Series(adjusted_values).reindex(p_values.index),
            "family": p_values.name or "unregistered_family",
        }
    )


def specification_table(
    specifications: pd.DataFrame,
    *,
    family_column: str = "family",
    p_value_column: str = "p_value",
) -> pd.DataFrame:
    """Return all registered robustness specifications with within-family Holm p-values."""
    if family_column not in specifications.columns:
        raise ValueError(f"Missing family column {family_column!r}")
    if p_value_column not in specifications.columns:
        raise ValueError(f"Missing p-value column {p_value_column!r}")
    frames: list[pd.DataFrame] = []
    for family, family_frame in specifications.groupby(family_column, sort=True):
        correction = holm_correction(family_frame[p_value_column].rename(str(family)))
        joined = family_frame.copy()
        joined["holm_p_value"] = correction["holm_p_value"].to_numpy(dtype=float)
        frames.append(joined)
    return pd.concat(frames, ignore_index=True)


def economic_diagnostics(
    baseline: pd.Series,
    alternatives: pd.DataFrame,
    *,
    material_change_threshold: float = 0.25,
) -> pd.DataFrame:
    """Compute economic changes across robustness specifications."""
    required = {"risk_price", "rmse", "mae", "max_alpha", "explained_spread"}
    missing_baseline = required - set(baseline.index)
    missing_alternatives = required - set(alternatives.columns)
    if missing_baseline:
        raise ValueError(f"Baseline is missing metrics: {', '.join(sorted(missing_baseline))}")
    if missing_alternatives:
        raise ValueError(
            f"Alternatives are missing metrics: {', '.join(sorted(missing_alternatives))}"
        )
    rows: list[dict[str, float | str | bool]] = []
    for name, row in alternatives.iterrows():
        risk_price_change = _relative_change(
            float(baseline["risk_price"]), float(row["risk_price"])
        )
        rmse_change = _relative_change(float(baseline["rmse"]), float(row["rmse"]))
        mae_change = _relative_change(float(baseline["mae"]), float(row["mae"]))
        alpha_change = _relative_change(float(baseline["max_alpha"]), float(row["max_alpha"]))
        sign_reversal = np.sign(float(baseline["risk_price"])) != np.sign(float(row["risk_price"]))
        material_change = any(
            abs(value) >= material_change_threshold
            for value in (risk_price_change, rmse_change, mae_change, alpha_change)
        )
        rows.append(
            {
                "specification": str(name),
                "risk_price_change": risk_price_change,
                "rmse_change": rmse_change,
                "mae_change": mae_change,
                "max_alpha_change": alpha_change,
                "explained_spread_change": float(row["explained_spread"])
                - float(baseline["explained_spread"]),
                "sign_reversal": bool(sign_reversal),
                "material_change": bool(material_change),
            }
        )
    return pd.DataFrame(rows)


def classify_robustness(
    weak_report: WeakFactorReport,
    economic_table: pd.DataFrame,
    *,
    rules: RobustnessDecisionRules = DEFAULT_ROBUSTNESS_DECISION_RULES,
) -> RobustnessConclusion:
    """Classify robustness using predeclared decision rules."""
    failures: list[str] = []
    if weak_report.unidentified:
        return RobustnessConclusion(verdict="unidentified", rule_failures=("weak_identification",))
    if rules.require_no_sign_reversal and economic_table["sign_reversal"].any():
        failures.append("risk_price_sign_reversal")
    if (economic_table["risk_price_change"].abs() > rules.max_material_risk_price_change).any():
        failures.append("material_risk_price_change")
    if (economic_table["rmse_change"].abs() > rules.max_material_rmse_change).any():
        failures.append("material_rmse_change")
    if (economic_table["mae_change"].abs() > rules.max_material_mae_change).any():
        failures.append("material_mae_change")
    if (economic_table["max_alpha_change"].abs() > rules.max_material_alpha_change).any():
        failures.append("material_alpha_change")
    if not failures:
        verdict: RobustnessVerdict = "robust"
    elif len(failures) <= 2:
        verdict = "conditionally_robust"
    else:
        verdict = "fragile"
    return RobustnessConclusion(verdict=verdict, rule_failures=tuple(failures))


def write_robustness_outputs(
    *,
    weak_report: WeakFactorReport,
    specification_results: pd.DataFrame,
    economic_results: pd.DataFrame,
    conclusion: RobustnessConclusion,
    diagnostics_path: Path,
    table_path: Path,
    report_path: Path,
) -> None:
    """Write robustness diagnostics, tables, and a concise markdown report."""
    for path in (diagnostics_path, table_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_payload = {
        "weak_factor": {
            "rank": weak_report.rank,
            "n_assets": weak_report.n_assets,
            "n_factors": weak_report.n_factors,
            "singular_values": list(weak_report.singular_values),
            "condition_number": weak_report.condition_number,
            "beta_dispersion": weak_report.beta_dispersion,
            "irrelevant_factors": list(weak_report.irrelevant_factors),
            "unidentified": weak_report.unidentified,
        },
        "classification": asdict(conclusion),
    }
    diagnostics_path.write_text(
        json.dumps(diagnostics_payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    specification_results.to_csv(table_path, index=False)
    report_path.write_text(
        "\n".join(
            [
                "# Robustness Report",
                "",
                f"Verdict: `{conclusion.verdict}`",
                "",
                "Rule failures: "
                + (", ".join(conclusion.rule_failures) if conclusion.rule_failures else "none"),
                "",
                "All registered specifications must be shown; significant-only reporting "
                "is prohibited.",
            ]
        ),
        encoding="utf-8",
    )


def grs_test(*, returns: pd.DataFrame, factors: pd.DataFrame) -> pd.Series:
    """Compute the Gibbons-Ross-Shanken joint alpha test."""
    joined = returns.join(factors, how="inner").dropna()
    if joined.empty:
        raise ValueError("No common complete observations between returns and factors")
    asset_names = list(returns.columns)
    factor_names = list(factors.columns)
    excess_returns = joined[asset_names]
    factor_panel = joined[factor_names]
    nobs = int(joined.shape[0])
    n_assets = len(asset_names)
    n_factors = len(factor_names)
    if nobs <= n_assets + n_factors + 1:
        raise ValueError("Insufficient observations for GRS test")
    design = sm.add_constant(factor_panel, has_constant="add")
    alphas: list[float] = []
    residuals: list[pd.Series] = []
    for asset in asset_names:
        model = sm.OLS(excess_returns[asset], design).fit()
        alphas.append(float(model.params["const"]))
        residuals.append(model.resid.rename(asset))
    alpha = np.asarray(alphas, dtype=float)
    if np.allclose(alpha, 0.0, atol=1e-12):
        return pd.Series(
            {
                "statistic": 0.0,
                "p_value": 1.0,
                "df_num": float(n_assets),
                "df_denom": float(nobs - n_assets - n_factors),
                "nobs": float(nobs),
                "n_assets": float(n_assets),
                "n_factors": float(n_factors),
            }
        )
    residual_matrix = pd.concat(residuals, axis=1).to_numpy(dtype=float)
    residual_covariance = residual_matrix.T @ residual_matrix / float(nobs - n_factors - 1)
    factor_mean = factor_panel.mean(axis=0).to_numpy(dtype=float)
    factor_covariance = factor_panel.cov().to_numpy(dtype=float)
    denominator = 1.0 + float(factor_mean.T @ np.linalg.pinv(factor_covariance) @ factor_mean)
    statistic = (
        (nobs - n_assets - n_factors)
        / n_assets
        / denominator
        * float(alpha.T @ np.linalg.pinv(residual_covariance) @ alpha)
    )
    p_value = float(f_distribution.sf(statistic, n_assets, nobs - n_assets - n_factors))
    return pd.Series(
        {
            "statistic": float(statistic),
            "p_value": p_value,
            "df_num": float(n_assets),
            "df_denom": float(nobs - n_assets - n_factors),
            "nobs": float(nobs),
            "n_assets": float(n_assets),
            "n_factors": float(n_factors),
        }
    )


def _relative_change(baseline: float, alternative: float) -> float:
    if baseline == 0.0:
        return float("inf") if alternative != 0.0 else 0.0
    return (alternative - baseline) / abs(baseline)
