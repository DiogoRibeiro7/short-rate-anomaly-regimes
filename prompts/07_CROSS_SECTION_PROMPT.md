# Cross Section Estimation Prompt

Complete Milestone 6.

## Estimators

Implement every estimator verified in the article, including OLS two-pass, GLS two-pass, and Fama-MacBeth when applicable.

For each estimator

- document the beta source and estimation window;
- define whether a zero-beta intercept is included;
- define the GLS weighting matrix and regularisation rule, if any;
- apply Shanken correction exactly where required;
- report uncorrected and corrected uncertainty separately;
- implement weak-factor warnings rather than hiding unstable estimates.

## Model evaluation

Compute risk prices, confidence intervals, individual pricing errors, cross-sectional R-squared, RMSE, MAE, maximum absolute alpha, GRS or article specification tests, and model-comparison metrics frozen in Milestone 0.

Estimate

1. each anomaly set separately;
2. each declared pair or joint system;
3. leave-one-set-out systems;
4. comparator models on identical observations and assets.

## Simulation tests

Simulate factor models with known risk prices under strong and weak factor structures. Verify estimator bias, confidence interval coverage, test size, and failure warnings.

## Acceptance

No model receives a successful replication label from fit alone. The exact target statistic, estimator, and tolerance must match.
