# Statistical Protocol

## Baseline Estimators

Implement the article's verified estimators first. The repository is prepared for

- OLS first-pass factor regressions;
- HAC standard errors using the article's Newey-West lag rule;
- OLS and GLS second-pass regressions;
- Fama-MacBeth estimation when required by the article;
- Shanken correction;
- joint alpha tests;
- cross-sectional fit metrics.

## Short-Rate Innovation Construction

The baseline short-rate innovation is the residual from the article's verified
first-order autoregression with an intercept. Alternative rate definitions,
higher-order autoregressions, local-level state-space innovations, and
announcement-surprise proxies are robustness or extension specifications and do
not redefine the strict baseline.

## First-Pass And Second-Pass Design

Use distinct notation for the time-series intercept, factor loadings,
time-series residual, cross-sectional pricing error, and factor risk prices. The
benchmark second pass follows the article's verified no-intercept OLS
cross-sectional regression. Any unrestricted zero-beta-rate specification is
reported as a separate robustness target.

Estimated-beta uncertainty is handled with the article's Shanken correction when
the baseline estimator is used. Bootstrap, Fama-MacBeth, Kan-Robotti-Shanken,
and GMM variants are labelled separately and mapped to the supplement targets or
extension diagnostics that require them.

## Model Comparison

Model comparison must report pricing-error loss and fit on identical asset-date
intersections within each comparison. Registered outcomes include root mean
squared pricing error, mean absolute pricing error, maximum absolute pricing
error, cross-sectional fit, and joint pricing-error tests when the estimator
justifies the test.

## Weak-Factor Analysis

A high cross-sectional fit is not sufficient when factor betas have little
dispersion or the factor is weakly identified. Report

- singular values and rank of the beta matrix;
- cross-sectional standard deviation and interquartile range of each beta;
- correlations among beta columns;
- first-stage factor relevance measures;
- misspecification-robust confidence sets where feasible;
- sensitivity to excluding one portfolio set at a time.

## Structural Change

Use both declared and estimated break tests.

- Chow tests at predeclared policy boundaries;
- regime interaction Wald tests;
- pooled regime interactions with a single omitted baseline category;
- equivalence intervals against predeclared economic bounds;
- Quandt-Andrews unknown-break tests;
- Bai-Perron multiple-break tests with a minimum segment length;
- CUSUM and recursive residual diagnostics;
- rolling and expanding estimates with uncertainty bands.

Exploratory break dates do not replace the predeclared regime system. Boundary
sensitivity checks shift registered regime cutoffs under the configuration rules
and report whether classifications change.

## Temporal Extension And Out-Of-Sample Design

The post-publication extension has two variants: a frozen-parameter evaluation
using the baseline estimates and a refitted evaluation using only information
available at each refit date. Out-of-sample records must store the forecast
origin, training window, refit schedule, model vintage, factor definition, asset
universe, benchmark, and loss function. No-lookahead rules apply to factor
construction, portfolio membership, and sample intersections.

## High-Frequency Decomposition

The high-frequency design starts from event-level announcement observations with
verified source terms. Event windows, identification variables, component
classification, ambiguous-event handling, monthly aggregation, and no-event
month treatment must be frozen before pricing tests are run. The primary tests
are spanning of the aggregate innovation by decomposed components and
incremental pricing content of the component factors. Causal language is
restricted to the identified event component design and does not apply to the
aggregate autoregressive residual.

## Multiple Testing

The primary hypotheses and outputs are frozen in
`research/hypothesis_registry.csv`. Secondary tests use Holm adjustment within
named families. Exploratory findings are labelled exploratory.

Confirmatory families are baseline pricing, temporal extension, regime
stability, shock decomposition, and weak-factor diagnostics. A result can be
statistically significant yet fail the registered economic-magnitude criterion.

## Bootstrap

Use a stationary or moving-block bootstrap for serially dependent monthly data.
The block-length rule, number of draws, and random seed are configuration
values. Never mix bootstrap and asymptotic p-values without labels.

## Economic Significance

For every statistically significant change report

- effect in monthly percentage points;
- annualised effect only when mathematically meaningful;
- change relative to the original anomaly spread;
- impact on cross-sectional RMSE and maximum pricing error;
- confidence interval.

## Method-To-Hypothesis Map

| Hypothesis | Primary method | Decision rule |
|---|---|---|
| H1 | No-intercept two-pass OLS with Shanken correction on the article asset intersection | Pricing-error improvement relative to the CAPM must pass the registered materiality standard. |
| H2 | Frozen and refitted post-publication two-pass evaluations | Sign, magnitude, and pricing-error compatibility must all hold. |
| H3 | Pooled regime interactions with equivalence intervals | Stability requires estimates inside economic equivalence bounds. |
| H4 | Monthly component spanning and pricing tests | The aggregate innovation is insufficient if components add content or alter interpretation. |
| H5 | Beta dispersion, rank, singular-value, and robust-inference diagnostics | Pricing interpretation requires all predeclared strength gates to pass. |
| E1 | Unknown-break tests | Exploratory only; does not confirm regime stability. |
