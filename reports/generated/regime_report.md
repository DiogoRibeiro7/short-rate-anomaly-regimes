# Regime Stability Report

Verdict: `regime_stability_unsupported_under_the_registered_equivalence_standard`

Hypothesis: `H3`
Replication status: `documented_reconstruction`
Equivalence rule: `tost_5pct_90pct_interval`
Bootstrap draws: `10000`
Reference regime: `conventional_pre_elb`
Innovation definition: `within_regime_ar1`

Classification basis: at least one dimension has its whole 90 percent interval beyond its bound, which is what the registered unsupported reading asserts

## Registered Equivalence Gates

| Dimension | Equivalence Demonstrated |
|---|---|
| article_fit_deterioration | false |
| dispersion_relative_change | false |
| max_abs_error_deterioration | false |
| per_portfolio_fitted_premium_equivalence | false |
| rmse_relative_deterioration | false |

Dimensions with a demonstrated exceedance: `rmse_relative_deterioration`

## Per-Portfolio Equivalence Decisions

| Decision | Portfolios |
|---|---|
| equivalent_within_bound | 26 |
| inconclusive | 44 |

- Portfolios evaluated: `70`
- Portfolios failing the premium bound: `44`
- Maximum absolute point premium change: `0.527201`

## Regime Coverage

- Standalone second pass: `conventional_pre_elb`, `elb_qe`
- Pooled interactions only: `normalisation`, `pandemic_elb_qe`, `inflation_tightening`, `post_tightening_easing`

Coverage note: the registered floors admit only two regimes to a standalone second pass, so the confirmatory comparison spans a single contrast; the other four regimes enter only through the pooled interaction model

## Residual Covariance Conditioning

| Regime | Months | Test Assets | Excess Months | Condition Number |
|---|---|---|---|---|
| conventional_pre_elb | 444 | 70 | 374 | 553.536 |
| elb_qe | 84 | 70 | 14 | 11056.2 |

Specification caveat: the chi-square statistic and the Shanken correction invert a residual covariance estimated from T months for N test assets; where T - N is small that inverse is unstable and the statistic should not be read as evidence. The equivalence gates do not invert it

## Global Innovation Sensitivity

| Statistic | Value |
|---|---|
| correlation | 0.998724 |
| max_absolute_discrepancy | 0.0366677 |
| portfolios_beyond_bound_global_innovation | 17 |
| portfolios_beyond_bound_within_regime_innovation | 16 |
| sign_agreement | 70 |

## Pooled Interaction Beta Stability

Classification: `unstable`
Scope: `pooled_regime_interaction_beta_stability`
Replication status: `documented_reconstruction`

| Test | Statistic | Degrees Of Freedom | P Value | Holm P Value |
|---|---|---|---|---|
| all_factor_interactions | 58.8595 | 10 | 5.95304e-09 | 6.72694e-07 |
| rate_beta_interactions | 37.313 | 5 | 5.1836e-07 | 5.07992e-05 |

Significant tests: `joint_regime_factor_interactions`, `joint_rate_beta_regime_interactions`

- Multiplicity adjustment: `holm` across `142` tests in family `regime_stability`
- Sample: `648` months, `1972-01` to `2025-12`, `70` test assets, vintage `current_throughout`
- Specification: response `test-asset monthly excess return`, regressors `RM`, `FFR_innovation`, HAC lags `6`, omitted baseline regime `conventional_pre_elb`
- Boundary sensitivity changed a conclusion: `false`
- Regimes evidenced only by pooled interactions: `pandemic_elb_qe`, `inflation_tightening`, `post_tightening_easing`

Interpretation: Significant regime interactions indicate parameter instability; they do not by themselves identify a causal effect of monetary policy.

Scope note: this artifact covers the pooled beta half of H3 only; the regime-specific second passes, pricing-error and fit comparisons, and the TOST equivalence intervals are separate members of the same confirmatory family

## Artifacts Read

- `artifacts/diagnostics/h3_regime_equivalence.json`
- `artifacts/diagnostics/h3_pooled_beta_stability.json`
