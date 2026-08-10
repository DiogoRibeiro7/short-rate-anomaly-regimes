# Temporal Extension Report

Verdict: `post_publication_compatibility_unsupported`

Hypothesis: `H2`
Replication status: `documented_reconstruction`
Latest common month: `2025-12`
Retrieval date: `2026-07-31`
Locked baseline vintage: `locked_original_1972_2013`
Extension vintage: `extension_retrieved_2026_07_31`
Revision policy: `audit_separately`

## Registered Compatibility Gates

These are the frozen point-estimate gates of the H2 registry row, and they decide the verdict above.

| Gate | Passed |
|---|---|
| fitted_premium_magnitude_within_0_25 | false |
| rmse_deterioration_within_10_percent | false |
| sign_compatibility | false |

- Registered sign gate compares against: `locked_baseline`, passed `false`
- Same-vintage sign comparison against: `revised_history`, passed `false`
- The two sign comparisons agree: `true`

Sign-gate vintage note: the registered sign gate compares the refitted extension with the locked baseline and so is the one H2 gate that spans two vintages; the fitted-premium magnitude gate is vintage isolated against the revised history. The same-vintage sign comparison is reported here for audit and decides nothing. Where the two disagree the registered verdict still follows the locked-baseline column

## Supplementary Inferential Classification

Status: `post_publication_compatibility_unsupported_under_the_bootstrap_interval_standard`
Role: supplementary interval evidence; the registered point-estimate rule above remains the confirmatory classification
Rule: `tost_5pct_90pct_interval`, sensitivity rule `strict_95pct_interval_sensitivity`
Comparison: `refitted_extension_2014_2025_minus_revised_history_1972_2013`
Draws: `10000`

| Estimand | Point Change | Lower 90 | Upper 90 | Bound | Decision |
|---|---|---|---|---|---|
| temporal_fitted_premium_spread_change__book_to_market | -0.926076 | -1.71715 | -0.135721 | 0.25 | inconclusive |
| temporal_fitted_premium_spread_change__earnings_to_price | -0.988143 | -1.67886 | -0.0560734 | 0.25 | inconclusive |
| temporal_fitted_premium_spread_change__equity_duration | 0.918686 | 0.0979915 | 1.46388 | 0.25 | inconclusive |
| temporal_fitted_premium_spread_change__inventory_growth | 0.135773 | -0.408335 | 0.39213 | 0.25 | inconclusive |
| temporal_fitted_premium_spread_change__investment_to_assets | 0.303934 | -0.0301583 | 0.518907 | 0.25 | inconclusive |
| temporal_fitted_premium_spread_change__long_term_reversal | 0.952862 | -0.065578 | 1.8924 | 0.25 | inconclusive |
| temporal_fitted_premium_spread_change__ppe_investment | 0.85835 | -0.0500905 | 1.34963 | 0.25 | inconclusive |
| temporal_rmse_relative_change | 0.910203 | 0.172668 | 1.8442 | 0.1 | difference_exceeds_bound |

Status basis: at least one estimand has its whole 90 percent interval beyond its bound, which is what a demonstrated temporal change asserts

Interval note: both windows are re-estimated inside every draw and the two independent draw sequences are paired index-wise, so the interval describes the temporal comparison rather than either window alone

## Rate Risk Price By Evaluation Window

| Window | Rate Risk Price |
|---|---|
| locked_baseline | -0.698465 |
| refitted_extension | -0.0825459 |
| revised_history | -0.698467 |

- RMSE relative change against the locked baseline: `0.910148`
- RMSE relative change against the revised history: `0.910203`
- Frozen autoregression intercept: `0.0462556`, slope `0.990527`
- Standardized rate-exposure dispersion share: locked baseline `0.253972`, refitted extension `0.579956`, against a floor of `0.1`

Dispersion note: recomputed from each window's own first-pass betas and factor standard deviations. The H4a dispersion floor is 0.1; the extension window clears it, so the extension does not fail the registered H4a dispersion criterion. That criterion does not measure exposure reliability, so a higher share is not evidence that the temporal result is well identified

Vintage isolation: the magnitude and RMSE gates compare the refitted extension with the revised-history baseline, so revised historical values do enter those comparisons, as the quantity the extension is measured against. What the shared vintage achieves is holding the revision contribution common to both sides, so it differences out of the temporal change. The frozen sign gate retains its registered comparator, the locked baseline, and is therefore the one gate in which two vintages meet; a same-vintage sign comparison is reported alongside it as a non-decisional diagnostic. The publication-era against current-vintage effect is reported separately as the locked-against-revised comparison

## Evaluation Windows

| evaluation | vintage | months | lambda_market | lambda_rate | shanken_t_rate | rmse | mae | max_abs | article_fit | replication_status |
|---|---|---|---|---|---|---|---|---|---|---|
| locked_baseline_1972_2013 | publication_era | 504 | 0.601228 | -0.698465 | -2.85954 | 0.100393 | 0.0816409 | 0.238831 | 0.543937 | documented_reconstruction |
| frozen_parameter_extension_2014_2025 | current | 144 | 0.601228 | -0.698465 | -2.85954 | 0.446254 | 0.355177 | 0.963638 | -0.691281 | documented_reconstruction |
| refitted_extension_2014_2025 | current | 144 | 0.997163 | -0.0825459 | -1.49336 | 0.191766 | 0.146386 | 0.683394 | 0.45021 | documented_reconstruction |
| revised_history_1972_2013 | current | 504 | 0.602986 | -0.698467 | -2.85914 | 0.10039 | 0.0816393 | 0.238822 | 0.543963 | documented_reconstruction |

The baseline and extension vintages are labelled separately. The revised-history evaluation is the current-vintage comparator for the registered temporal gates, so revised historical values do enter the temporal verdict, as the quantity the refitted extension is measured against. What the shared vintage removes is the publication-era against current-vintage revision effect, which the locked-baseline comparison reports separately.

## Artifacts Read

- `artifacts/diagnostics/h2_temporal_stability.json`
- `artifacts/tables/extension/temporal_evaluation.csv`
