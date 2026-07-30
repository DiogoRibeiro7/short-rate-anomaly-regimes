# Statistical Protocol

## Baseline estimators

Implement the article's verified estimators first. The repository is prepared for

- OLS first-pass factor regressions;
- HAC standard errors using the article's Newey-West lag rule;
- OLS and GLS second-pass regressions;
- Fama-MacBeth estimation when required by the article;
- Shanken correction;
- joint alpha tests;
- cross-sectional fit metrics.

## Weak-factor analysis

A high cross-sectional fit is not sufficient when factor betas have little dispersion or the factor is weakly identified. Report

- singular values and rank of the beta matrix;
- cross-sectional standard deviation and interquartile range of each beta;
- correlations among beta columns;
- first-stage factor relevance measures;
- misspecification-robust confidence sets where feasible;
- sensitivity to excluding one portfolio set at a time.

## Structural change

Use both declared and estimated break tests.

- Chow tests at predeclared policy boundaries;
- regime interaction Wald tests;
- Quandt-Andrews unknown-break tests;
- Bai-Perron multiple-break tests with a minimum segment length;
- CUSUM and recursive residual diagnostics;
- rolling and expanding estimates with uncertainty bands.

## Multiple testing

The primary hypotheses and outputs are frozen in `research/hypothesis_registry.csv`. Secondary tests use Holm adjustment within named families. Exploratory findings are labelled exploratory.

## Bootstrap

Use a stationary or moving-block bootstrap for serially dependent monthly data. The block-length rule, number of draws, and random seed are configuration values. Never mix bootstrap and asymptotic p-values without labels.

## Economic significance

For every statistically significant change report

- effect in monthly percentage points;
- annualised effect only when mathematically meaningful;
- change relative to the original anomaly spread;
- impact on cross-sectional RMSE and maximum pricing error;
- confidence interval.
