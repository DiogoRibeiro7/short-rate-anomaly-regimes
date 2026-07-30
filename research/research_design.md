# Research Design

## Baseline object

The baseline is a linear two-factor ICAPM-style representation containing the market excess return and the innovation in a short-term interest rate. The published article states that the short-rate factor may be constructed from the federal funds rate or a Treasury-bill rate and that the model explains several joint anomaly portfolio sets.

The strict replication target is the article's sample from January 1972 through December 2013. The exact source series, transformations, portfolio definitions, estimator variants, and table targets must be extracted from the article and supplement in Milestone 0.

## Primary extension

The extension tests whether the interest-rate factor is stable across monetary regimes and whether its pricing content survives decomposition into policy and central-bank information components.

The extension is not designed to prove that the original paper is wrong. It can produce five legitimate outcomes.

1. The original result is stable and survives all extensions.
2. The result survives but only for specific anomaly sets.
3. The result is regime-dependent.
4. The aggregate short-rate innovation is primarily an information or macro-news proxy.
5. The result is too sensitive to weak-factor inference, inaccessible inputs, or a narrow sample to support a broad conclusion.

## Confirmatory hypotheses

### H1 Baseline replication

The market and short-rate two-factor model materially reduces cross-sectional pricing errors relative to the CAPM for the article's joint anomaly portfolios.

### H2 Temporal stability

The short-rate risk price and the cross-sectional pattern of short-rate betas are stable after 2013.

### H3 Regime invariance

The short-rate risk price and factor loadings do not vary across conventional policy, effective-lower-bound policy, quantitative easing, normalisation, pandemic policy, and inflation tightening.

### H4 Shock sufficiency

An aggregate AR innovation in the short rate is sufficient. Separating policy and central-bank information components does not materially improve pricing performance or alter interpretation.

## Falsification rules

- Reject a replication claim if the exact published target cannot be linked to the same data definition and estimator.
- Reject stability if joint tests show economically meaningful regime interactions after multiple-testing adjustment.
- Reject shock sufficiency if decomposed shocks have different signs, risk prices, or explanatory power and the aggregate factor masks those differences.
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
