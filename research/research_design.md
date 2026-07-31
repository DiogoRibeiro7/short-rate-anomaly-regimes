# Research Design

## Baseline object

The baseline is a linear two-factor ICAPM-style representation containing the market excess return and the innovation in a short-term interest rate. The published article states that the short-rate factor may be constructed from the federal funds rate or a Treasury-bill rate and that the model explains several joint anomaly portfolio sets.

The strict replication target is the article's sample from January 1972 through December 2013. The exact source series, transformations, portfolio definitions, estimator variants, and table targets must be extracted from the article and supplement in Milestone 0.

## Primary extension

The extension tests whether the interest-rate factor is stable after the
publication sample and across monetary regimes, and whether any pricing content
survives weak-factor and comparator-model diagnostics.

The extension is not designed to prove that the original paper is wrong. It can produce five legitimate outcomes.

1. The original result is stable and survives all extensions.
2. The result survives but only for specific anomaly sets.
3. The result is regime-dependent.
4. The result is too sensitive to weak-factor inference, inaccessible inputs, or a narrow sample to support a broad conclusion.
5. The optional announcement-based decomposition motivates a separate appendix or paper only after event data and component diagnostics are available.

## Replication target and confirmatory hypotheses

### R1 Baseline replication targets

The registered article statistics are recovered within their declared tolerances
after source-compatible inputs and generated artifacts exist. The target is
decomposed into short-rate innovation equations, first-pass betas,
cross-sectional risk prices, pricing errors and fit, comparator-model results,
and supplementary robustness tables.

### H1 Incremental pricing content

The short-rate factor produces economically meaningful incremental pricing
performance relative to the strongest registered non-short-rate comparator on
the common asset-date intersection.

### H2 Temporal stability

The short-rate risk price and the cross-sectional pattern of short-rate betas are stable after 2013.

### H3 Regime invariance

Factor construction, portfolio betas, fitted premia, pricing errors, and
interpretable fit remain within numerical equivalence bounds across conventional
policy, effective-lower-bound policy, quantitative easing, normalisation,
pandemic policy, and inflation tightening.

### H4 Weak-factor strength

The short-rate beta column has enough dispersion, rank contribution, and robust
identification strength to support a pricing interpretation.

## Falsification rules

- Reject a replication claim if the exact published target cannot be linked to the same data definition and estimator.
- Reject stability if beta interactions, regime-specific risk prices, or pricing-error comparisons exceed numerical equivalence bounds after multiple-testing adjustment.
- Treat a factor as weak when beta dispersion, rank diagnostics, or misspecification-robust inference fail declared thresholds.
- Do not substitute statistical significance for economic relevance.

## Primary estimands

- asset-specific market and short-rate betas;
- market and short-rate prices of risk;
- cross-sectional intercept;
- individual pricing errors;
- cross-sectional R-squared;
- root mean squared pricing error;
- mean absolute pricing error;
- GRS joint-alpha statistic;
- regime interaction coefficients;
- structural break dates and confidence intervals;
- out-of-sample pricing error.

## Unit of observation

The baseline unit is the monthly portfolio return. Event-level observations are used only to identify high-frequency monetary shocks and are aggregated to monthly factors under a predeclared rule.

## Interpretation boundary

A priced covariance with a rate innovation does not by itself identify a causal monetary-policy mechanism. Causal language requires an external instrument or an explicit high-frequency identification design.
