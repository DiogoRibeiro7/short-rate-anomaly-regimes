# First Pass Estimation Prompt

Complete Milestone 5.

## Estimation contract

For every portfolio set, weighting, rate factor, and comparator model

1. intersect dates explicitly and record observations lost by each merge;
2. construct excess returns using the frozen risk-free definition;
3. estimate time-series OLS with an intercept;
4. apply the exact article covariance and Newey-West lag rule;
5. store alpha, factor betas, standard errors, t-statistics, p-values, confidence intervals, residuals, R-squared, adjusted R-squared, and `nobs`;
6. preserve a stable asset and factor ordering;
7. never winsorise or remove months in the baseline.

## Diagnostics

Produce residual autocorrelation, heteroskedasticity, normality, leverage, Cook's distance, DFBETA, and crisis-month influence summaries. Diagnostics do not authorise automatic data deletion.

## Independent verification

Implement one central regression through both statsmodels and direct matrix algebra. Add tolerance tests for coefficients and HAC covariance.

## Outputs

Generate machine-readable coefficients and article-formatted tables. Include table metadata with model, sample, rate factor, portfolio set, units, covariance, and code commit.
