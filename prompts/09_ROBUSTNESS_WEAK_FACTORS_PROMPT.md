# Robustness and Weak Factors Prompt

Complete Milestone 8.

## Weak-factor core

Implement and report

- beta-matrix rank and singular values;
- cross-sectional beta dispersion;
- condition numbers;
- factor spanning and redundancy tests;
- irrelevant-factor diagnostics;
- misspecification-robust risk-price inference where computationally feasible;
- confidence regions that remain valid under weak identification when available.

## Registered robustness families

1. rate definition and innovation model;
2. covariance and bootstrap method;
3. portfolio weighting;
4. test-asset composition;
5. crisis and influential observations;
6. sample endpoints;
7. comparator factor models.

Apply Holm correction within each family. Show all specifications in a specification table or curve, not only significant results.

## Economic diagnostics

For every robustness result report the change in risk price, RMSE, MAE, maximum alpha, and explained anomaly spread. Flag sign reversals and economically material changes even when statistically insignificant.

## Acceptance

Conclude with one of `robust`, `conditionally_robust`, `fragile`, or `unidentified`, using explicit decision rules written before computing the classification.
