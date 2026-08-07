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

| Gate | Passed |
|---|---|
| fitted_premium_magnitude_within_0_25 | false |
| rmse_deterioration_within_10_percent | false |
| sign_compatibility | false |

## Rate Risk Price By Evaluation Window

| Window | Rate Risk Price |
|---|---|
| locked_baseline | -0.698465 |
| refitted_extension | -0.0825459 |
| revised_history | -0.697373 |

- RMSE relative change against the locked baseline: `0.910148`
- RMSE relative change against the revised history: `0.889665`
- Frozen autoregression intercept: `0.0462556`, slope `0.990527`
- Standardized rate-exposure dispersion share: locked baseline `0.254`, refitted extension `0.58`

Dispersion note: the H4a dispersion gate floor is 0.10; the extension window clears it more comfortably than the baseline, so the temporal result is not attributable to a weakly identified factor

Vintage isolation: the temporal gates compare the refitted extension with the revised-history baseline, which shares its vintage, so revised historical data cannot enter the temporal verdict

## Evaluation Windows

| evaluation | vintage | months | lambda_market | lambda_rate | shanken_t_rate | rmse | mae | max_abs | article_fit | replication_status |
|---|---|---|---|---|---|---|---|---|---|---|
| locked_baseline_1972_2013 | publication_era | 504 | 0.601228 | -0.698465 | -2.85954 | 0.100393 | 0.0816409 | 0.238831 | 0.543937 | documented_reconstruction |
| frozen_parameter_extension_2014_2025 | current | 144 | 0.601228 | -0.698465 | -2.85954 | 0.446254 | 0.355177 | 0.963638 | -0.691281 | documented_reconstruction |
| refitted_extension_2014_2025 | current | 144 | 0.997163 | -0.0825459 | -1.49336 | 0.191766 | 0.146386 | 0.683394 | 0.45021 | documented_reconstruction |
| revised_history_1972_2013 | current | 504 | 0.604393 | -0.697373 | -2.86141 | 0.101481 | 0.0821065 | 0.25359 | 0.533951 | documented_reconstruction |

The baseline and extension vintages are labelled separately. Revised historical values enter only the vintage comparison, never the temporal verdict.

## Artifacts Read

- `artifacts/diagnostics/h2_temporal_stability.json`
- `artifacts/tables/extension/temporal_evaluation.csv`
