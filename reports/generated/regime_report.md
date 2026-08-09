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

Specification caveat: neither the Shanken correction nor the chi-square statistic inverts the residual covariance; it enters only through B' Sigma B, reduced to K by K before any inverse, and through M Sigma M', read through a pseudo-inverse. A residual covariance estimated from T months for N test assets is therefore usable at any T, but as T - N falls its smaller eigenvalues are increasingly noise, and at T <= N some are exactly zero. The chi-square is the statistic to distrust first, because it is referred to chi2(N - K) however few directions its pseudo-inverse measures. The equivalence gates use neither the covariance nor its pseudo-inverse

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

### Boundary Sensitivity By Registered Shift

Any conclusion changed: `false` across shifts `-3`, `0`, `3` months

| shift months | aggregate rate beta holm p value | aggregate rate beta statistic | assets rate beta significant holm | verdict | verdict matches registered boundaries |
|---|---|---|---|---|---|
| -3 | 0.06537 | 19.4352 | 39 | unstable | true |
| 0 | 5.07992e-05 | 37.313 | 26 | unstable | true |
| 3 | 0.051166 | 20.132 | 36 | unstable | true |

### Exploratory Break Battery

Hypothesis: `E1`
Evidence class: `exploratory`
Scope: `equal_weighted_test_assets`

Note: exploratory under hypothesis E1; not a member of the confirmatory regime_stability family and neither confirms nor refutes H3

| break month | break number | break type | candidate count | criterion | df denom | df num | evidence class | hypothesis | max breaks searched | min segment observations | multiplicity family | nobs | p value | scope | selected breaks | statistic | test |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2008-12 | n/a | registered_boundary | n/a | n/a | 642 | 3 | exploratory | E1 | 2 | 12 | not_in_confirmatory_family | 648 | 0.0662912 | equal_weighted_test_assets | n/a | 2.40586 | chow_known_break |
| 2015-12 | n/a | registered_boundary | n/a | n/a | 642 | 3 | exploratory | E1 | 2 | 12 | not_in_confirmatory_family | 648 | 0.0525845 | equal_weighted_test_assets | n/a | 2.58084 | chow_known_break |
| 2020-03 | n/a | registered_boundary | n/a | n/a | 642 | 3 | exploratory | E1 | 2 | 12 | not_in_confirmatory_family | 648 | 0.813223 | equal_weighted_test_assets | n/a | 0.316826 | chow_known_break |
| 2022-03 | n/a | registered_boundary | n/a | n/a | 642 | 3 | exploratory | E1 | 2 | 12 | not_in_confirmatory_family | 648 | 0.168483 | equal_weighted_test_assets | n/a | 1.6872 | chow_known_break |
| 2024-09 | n/a | registered_boundary | n/a | n/a | 642 | 3 | exploratory | E1 | 2 | 12 | not_in_confirmatory_family | 648 | 0.178277 | equal_weighted_test_assets | n/a | 1.64268 | chow_known_break |
| 1989-12 | n/a | estimated_unknown_break | 576 | n/a | n/a | n/a | exploratory | E1 | 2 | 36 | not_in_confirmatory_family | n/a | 0.00243731 | equal_weighted_test_assets | n/a | 9.42235 | quandt_andrews_unknown_break |
| 1998-07 | 1 | estimated_unknown_break | n/a | -592.711 | n/a | n/a | exploratory | E1 | 2 | 36 | not_in_confirmatory_family | n/a | n/a | equal_weighted_test_assets | 2 | n/a | bai_perron_multiple_breaks |
| 2001-08 | 2 | estimated_unknown_break | n/a | -592.711 | n/a | n/a | exploratory | E1 | 2 | 36 | not_in_confirmatory_family | n/a | n/a | equal_weighted_test_assets | 2 | n/a | bai_perron_multiple_breaks |
| n/a | n/a | recursive_residuals | n/a | n/a | n/a | n/a | exploratory | E1 | 2 | n/a | not_in_confirmatory_family | 648 | 0.0709343 | equal_weighted_test_assets | n/a | 1.15022 | cusum_recursive_residuals |

## Artifacts Read

- `artifacts/diagnostics/h3_regime_equivalence.json`
- `artifacts/diagnostics/h3_pooled_beta_stability.json`
