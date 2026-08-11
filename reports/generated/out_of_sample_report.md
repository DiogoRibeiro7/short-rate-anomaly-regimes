# Out-of-Sample Falsification Report

Verdict: `generated_from_frozen_design`

Initial training endpoint: `1999-12`
Refit frequency months: `12`
Evaluation end: `2025-12`
Confirmatory model: `two_factor_market_rate`
Lowest-loss model: `two_factor_market_rate`

## Losses

| Model | RMSE | MAE | Out-of-sample R2 | Within loss band |
|---|---|---|---|---|
| `two_factor_market_rate` | 1.6158 | 1.2366 | 0.0039 | yes |
| `historical_mean` | 1.6190 | 1.2419 | 0.0000 | yes |
| `zero_excess_return` | 1.7647 | 1.4402 | -0.1882 | no |

The out-of-sample R2 is measured against the first registered benchmark, `historical_mean`, so that benchmark reads 0 by construction.

## What the loss band is, and is not

The `included_in_confidence_set` column marks models whose mean squared error lies within a fixed band of the lowest observed loss. It is a descriptive screen. It is **not** the Hansen, Lunde and Nason (2011) model confidence set: there is no resampling, no equal-predictive-ability statistic, and no coverage guarantee at any level. A model inside the band has not been shown to be equivalent to the leader, and a model outside it has not been shown to be worse. The rule is recorded in the `selection_rule` column of the shipped table.

## Interpretation

Results from this design are evidence about the stability of pricing errors, not a substitute for the baseline replication audit. Negative out-of-sample performance must be preserved and investigated without changing the confirmatory specification, which is frozen in the configuration and was not revised after these errors were seen. The confirmatory model attains an out-of-sample R2 of 0.0039 against `historical_mean`.
