# Inference Contract

This contract fixes estimator uncertainty, resampling, multiplicity, and
weak-factor decision gates before empirical results are generated.

## Baseline Second-Pass Inference

- Benchmark estimator: no-intercept OLS cross-sectional regression of
  full-sample average excess returns on full-sample first-pass betas.
- Beta-estimation uncertainty: Shanken-adjusted covariance for the benchmark
  risk-price estimator.
- Cross-sectional pricing error: average return minus fitted risk premium under
  the benchmark second pass.
- Joint pricing-error statistic: use the article's exact statistic when
  verified; otherwise report a Wald statistic using the covariance matrix
  declared with the generated artifact and label it as a reconstruction.

## Bootstrap

- Primary bootstrap unit: moving blocks of monthly observations.
- Default repetitions: 10,000.
- Default block length: automatic monthly block length from the configured
  serial-dependence rule; if the rule is unavailable, use twelve monthly
  observations and label the choice.
- Asset resampling is not used for confirmatory inference.
- Table-target resampling is not used for confirmatory inference.

## Equivalence Tests

- Confidence level: 95 percent two-sided confidence intervals.
- Stability is supported only when the full confidence interval lies inside the
  predeclared equivalence bound.
- A failure to reject equality is never a stability classification.

## Multiplicity Families

- Replication table targets: descriptive audit; no p-value adjustment.
- Baseline pricing materiality: one confirmatory family across registered
  comparator models, Holm adjusted for secondary p-values.
- Temporal extension: one confirmatory family across frozen and refitted
  variants.
- Regime stability: one confirmatory family across beta, fitted-premium,
  pricing-error, and fit stability tests.
- Weak-factor diagnostics: one confirmatory family across strength gates.
- Structural breaks and policy-information decomposition: exploratory or
  appendix-only unless promoted by a later preregistered design.

## Weak-Factor Failure Gates

The short-rate factor fails the confirmatory strength gate if any of the
following occurs:

- beta matrix rank is below the number of priced factors;
- smallest singular value of the beta matrix is below 10 percent of the largest
  singular value;
- cross-sectional standard deviation of short-rate betas is below 10 percent of
  the market-beta standard deviation on the same asset set;
- condition number of the beta matrix exceeds 30;
- leave-one-family systems change the sign of the short-rate fitted-premium
  spread or remove the materiality classification;
- robust-inference intervals include both economically positive and economically
  negative fitted-premium effects under the threshold contract.
