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

- Primary bootstrap unit: calendar months in the aligned return-factor panel.
- Bootstrap type: moving-block bootstrap with overlapping monthly blocks.
- Primary block-length selector: Politis-White automatic block length applied
  to the baseline market excess return and selected short-rate innovation.
- Selector failure condition: fewer than 60 complete factor months, zero sample
  variance, non-finite autocovariances, or a non-finite selected block length
  outside 2 to 24 months.
- Fallback block length: 12 monthly observations.
- Default repetitions: 10,000.
- Random-seed policy: use the project seed and record the draw index range with
  every generated artifact.
- Joint resampling: factors, portfolio returns, short-rate series, and regime
  labels are resampled jointly by month.
- Recomputed stages: the short-rate innovation, all first-pass regressions, the
  second-pass regression, fitted premia, pricing errors, fit metrics, and
  equivalence statistics are recomputed in every draw.
- Regime boundaries: confirmatory regime labels are fixed calendar labels; for
  regime-specific inference, blocks are resampled within regime.
- Missing observations: apply the frozen common-intersection rule after
  resampling; no bootstrap imputation is allowed.
- Asset and table-target resampling are not used for confirmatory inference.

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
- cross-sectional standard deviation of standardized short-rate exposure
  `beta_i_rate * standard_deviation(rate_innovation)` is below 10 percent of
  the cross-sectional standard deviation of standardized market exposure
  `beta_i_mkt * standard_deviation(market_factor)` on the same asset set;
- the rate factor's residual standard deviation after projection on the other
  priced factors is below 10 percent of the raw rate-factor standard deviation;
- leave-one-family systems change the sign of the short-rate fitted-premium
  spread or remove the materiality classification;
- robust-inference intervals include both economically positive and economically
  negative fitted-premium effects under the threshold contract.

Singular values and condition numbers may be reported descriptively, but they
are not separate confirmatory thresholds because the condition number is the
ratio of the largest to smallest singular value.
