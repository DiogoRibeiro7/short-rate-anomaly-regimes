# Robustness Report

Verdict: `unsupported`

Verdict source: `asset_sets.all_seven_families_joint.h1_primary_classification` in `artifacts/diagnostics/h1_materiality.json`
Hypothesis: `H1`
Replication status: `documented_reconstruction`
Primary comparator: `capm`, selected after observing RMSE: `false`

Decision rule: H1 is supported against the primary comparator only if all three primary gates hold jointly on the identical asset-date intersection.

Multiplicity: The registered secondary comparator family uses Holm adjustment for secondary p-values. The materiality gates executed here are deterministic threshold comparisons on point estimates, so no p-value is generated in this pass and Holm adjustment therefore does not yet apply. No p-value is invented to fill the slot.

## H1 Primary Gates On The Headline Asset Set `all_seven_families_joint`

Treatment model `market_plus_fedfunds_innovation`, comparator `capm`, `70` assets, `504` months, `2` of `3` gates passed, classification `unsupported`

| Gate | Comparison | Threshold | Comparator | Treatment | Observed | Passed |
|---|---|---|---|---|---|---|
| mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.146575 | 0.0816409 | 0.443008 | true |
| max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.475246 | 0.238831 | 0.236415 | false |
| rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.100393 | 0.469737 | true |

Treatment model `market_plus_tbill_innovation`, comparator `capm`, `70` assets, `504` months, `2` of `3` gates passed, classification `unsupported`

| Gate | Comparison | Threshold | Comparator | Treatment | Observed | Passed |
|---|---|---|---|---|---|---|
| mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.146575 | 0.0858156 | 0.414526 | true |
| max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.475246 | 0.278117 | 0.19713 | false |
| rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.108418 | 0.427352 | true |

## H1 Classification By Asset Set

| Asset Set | Treatment Model | Primary Comparator | Primary Classification | Secondary Comparator | Secondary Classification |
|---|---|---|---|---|---|
| all_seven_families_joint | market_plus_fedfunds_innovation | capm | unsupported | carhart_4 | unsupported |
| all_seven_families_joint | market_plus_tbill_innovation | capm | unsupported | carhart_4 | unsupported |
| book_to_market | market_plus_fedfunds_innovation | capm | unsupported | fama_french_5 | unsupported |
| book_to_market | market_plus_tbill_innovation | capm | unsupported | fama_french_5 | unsupported |
| earnings_to_price | market_plus_fedfunds_innovation | capm | unsupported | fama_french_5 | unsupported |
| earnings_to_price | market_plus_tbill_innovation | capm | unsupported | fama_french_5 | unsupported |
| equity_duration | market_plus_fedfunds_innovation | capm | supported | fama_french_5 | unsupported |
| equity_duration | market_plus_tbill_innovation | capm | supported | fama_french_5 | unsupported |
| inventory_growth | market_plus_fedfunds_innovation | capm | unsupported | fama_french_5 | unsupported |
| inventory_growth | market_plus_tbill_innovation | capm | unsupported | fama_french_5 | unsupported |
| investment_to_assets | market_plus_fedfunds_innovation | capm | supported | liquidity | unsupported |
| investment_to_assets | market_plus_tbill_innovation | capm | supported | liquidity | unsupported |
| long_term_reversal | market_plus_fedfunds_innovation | capm | unsupported | carhart_4 | unsupported |
| long_term_reversal | market_plus_tbill_innovation | capm | unsupported | carhart_4 | unsupported |
| ppe_investment | market_plus_fedfunds_innovation | capm | unsupported | liquidity | unsupported |
| ppe_investment | market_plus_tbill_innovation | capm | unsupported | liquidity | unsupported |

## Weak-Factor Gate Outcomes

| Hypothesis | Outcome | Gate Failures |
|---|---|---|
| H4a | true | none |
| H4b | true | none |
| H4c | h4c_passed_interval_excludes_at_least_one_economic_direction | none |

### H4a Identification Strength

- Confirmatory system: `all_seven_families_joint`, rank `2` of `2` priced factors, condition number `4.15902`
- Standardized rate-exposure dispersion share: `0.253972` against a floor of `0.1`
- Spanning R squared: `0.0559645` against a ceiling of `0.9`; residual ratio `0.971615` against a floor of `0.316228`
- Spanning regressors: `Mkt-RF`, `SMB`, `HML`, `UMD`, `RMW`, `CMA`, `LIQ`, `ME`, `IA`, `ROE`, over `504` months

### H4b Influence Stability

- Maximum absolute standardized DFBETA: `0.0896452` at `inventory_growth__decile_05`, against a bound of `1`
- Assets reaching the bound: `0` of `70`
- Leave-one-family refits pass: `true` across `7` refits
- Baseline rate risk price: `-0.698465`, Shanken standard error `0.244258`, t `-2.85954`

### H4c Fitted-Premium Precision

- Estimand: `rate_attributable_fitted_premium_spread_decile_10_minus_decile_01`
- Economic direction bound: `0.25`, `10000` draws, block length `6` selected by `politis_white`

| Family | Point Estimate | Lower 90 | Upper 90 | Spans Both Directions | Gate |
|---|---|---|---|---|---|
| book_to_market | 0.535266 | 0.0704132 | 0.761391 | false | pass |
| earnings_to_price | 0.407112 | 0.0337173 | 0.632192 | false | pass |
| equity_duration | -0.461739 | -0.661488 | -0.0345803 | false | pass |
| long_term_reversal | -0.299183 | -0.623829 | 0.108029 | false | pass |
| investment_to_assets | -0.328348 | -0.485558 | -0.0516887 | false | pass |
| ppe_investment | -0.298081 | -0.432508 | -0.0296896 | false | pass |
| inventory_growth | -0.190763 | -0.394422 | 0.060888 | false | pass |

All registered gates are reported above, whether they passed or failed; significant-only robustness reporting is prohibited.

## Artifacts Read

- `artifacts/diagnostics/h1_materiality.json`
- `artifacts/diagnostics/weak_factor/h4a_identification_strength.json`
- `artifacts/diagnostics/weak_factor/h4b_influence_stability.json`
- `artifacts/diagnostics/weak_factor/h4c_fitted_premium_precision.json`
