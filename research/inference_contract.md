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
- Joint resampling: the stochastic variables resampled by the bootstrap are the
  market factor, the comparator factors, the portfolio returns, and the
  short-rate level series. They are resampled jointly by calendar month.
- Regime labels are not stochastic variables and are never resampled. A regime
  label is a deterministic calendar function of the observation month fixed in
  `research/regime_registry.csv`. Each resampled month carries its own frozen
  label as a fixed attribute; labels are never permuted, drawn independently of
  the month, or re-derived from the resampled ordering.
- Recomputed stages: the short-rate innovation, all first-pass regressions, the
  second-pass regression, fitted premia, pricing errors, fit metrics, and
  equivalence statistics are recomputed in every draw.
- Regime boundaries: confirmatory regime labels are fixed calendar labels; for
  regime-specific inference, blocks are resampled within regime.
- Missing observations: apply the frozen common-intersection rule after
  resampling; no bootstrap imputation is allowed.
- Asset and table-target resampling are not used for confirmatory inference.

## Equivalence Tests

The project adopts exactly one confirmatory equivalence rule.

- Selected rule: **standard two one-sided tests (TOST) at the 5 percent level,
  implemented as inclusion of the two-sided 90 percent confidence interval
  inside the predeclared equivalence bound.**
- Rejected alternative: 95 percent confidence-set inclusion. That rule is a
  stricter, non-standard-size procedure (an approximately 2.5 percent one-sided
  test). It is retained only as a labelled robustness column and may never be
  reported as the confirmatory equivalence test.
- Interval source: the joint moving-block bootstrap percentile interval for the
  estimand in `research/bootstrap_contract.md`.
- Decision: equivalence is supported only when the entire 90 percent interval
  lies inside the bound `[-delta, +delta]` declared for that estimand in
  `research/economic_thresholds.md`.
- A failure to reject equality is never a stability classification.
- Every reported equivalence result must state the rule name
  `tost_5pct_90pct_interval` and, where the stricter column is also shown, the
  label `strict_95pct_interval_sensitivity`.

## Multiplicity Families

- Replication table targets: descriptive audit; no p-value adjustment.
- Baseline pricing materiality: one confirmatory family across registered
  comparator models, Holm adjusted for secondary p-values.
- Temporal extension: one confirmatory family across frozen and refitted
  variants.
- Regime stability: one confirmatory family across beta, fitted-premium,
  pricing-error, and fit stability tests.
- Weak-factor diagnostics: one confirmatory family `weak_factor_diagnostics`
  containing H4a, H4b, and H4c. Where a component gate produces a p-value, Holm
  adjustment applies within the family.
- Structural breaks and policy-information decomposition: exploratory or
  appendix-only unless promoted by a later preregistered design.

## Weak-Factor Failure Gates

The former single hypothesis H4 is replaced by three separately classified
confirmatory hypotheses. Each is decided independently and reported
independently; a factor is interpretable only when all three pass.

### H4a Cross-sectional identification strength

Fails if any of the following occurs.

- The rank of the estimated beta matrix is below the number of priced factors.
  Rank is evaluated numerically as the count of singular values exceeding
  `max(n_assets, n_factors) * machine_epsilon * largest_singular_value`.
- The cross-sectional standard deviation of standardized short-rate exposure
  `beta_i_rate * standard_deviation(rate_innovation)` is below 10 percent of
  the cross-sectional standard deviation of standardized market exposure
  `beta_i_mkt * standard_deviation(market_factor)` on the same asset set.
- The numerical factor-spanning criterion below fails.

### Numerical factor-spanning criterion

The criterion is fully specified so it can be executed without discretion.

- Estimation sample: the frozen common asset-date intersection months used by
  the corresponding pricing test.
- Dependent variable: the short-rate innovation entering the tested model.
- Regressor set `S_span`: a constant plus every registered non-short-rate
  comparator factor available on that intersection, in the fixed order
  `Mkt-RF, SMB, HML, UMD, RMW, CMA, LIQ, ME, IA, ROE`. Factors absent from the
  intersection are dropped and the executed list is stored with the artifact.
- Estimator: OLS. Reported statistic: the spanning coefficient of determination
  `R2_span` and the residual standard-deviation ratio
  `s_span = standard_deviation(residual) / standard_deviation(rate_innovation)`,
  which satisfies `s_span = sqrt(1 - R2_span)`.
- Decision rule: the spanning gate **passes** when `R2_span <= 0.90`,
  equivalently `s_span >= 0.3162`. It **fails** when `R2_span > 0.90`.
- Rationale: a factor whose variation is more than 90 percent reproduced by the
  existing traded-factor set retains less than one tenth of its variance as
  independent identifying variation and cannot be separately identified from
  that set in a cross-section of this size.
- Secondary reporting: the same statistic against the minimal regressor set
  `Mkt-RF` alone is always reported next to the primary value. It is descriptive
  and carries no separate threshold.
- The criterion is invariant to rescaling the short-rate factor because both
  `R2_span` and `s_span` are scale free.

### H4b Influence stability

Fails if either of the following occurs.

- A leave-one-anomaly-family refit changes the sign of the rate-attributable
  fitted-premium spread or removes its materiality classification.
- The maximum absolute standardized DFBETA of any single portfolio on
  `lambda_rate` reaches 1.

### H4c Fitted-premium precision

Fails if the 95 percent joint-bootstrap percentile interval for the
rate-attributable fitted-premium spread contains both `+0.25` and `-0.25`
monthly percentage points, that is, when the interval spans both economically
positive and economically negative effects under the threshold contract.

Precision is a two-sided coverage statement about a single estimand, not an
equivalence test, so it uses a 95 percent interval. This is deliberately
different from the confirmatory equivalence rule above, which uses a 90 percent
interval because TOST is a pair of one-sided tests.

### Descriptive-only quantities

Singular values and condition numbers may be reported descriptively, but they
are not separate confirmatory thresholds because the condition number is the
ratio of the largest to smallest singular value. Shanken-adjusted risk-price
intervals are reported descriptively alongside the fitted-premium bootstrap.
