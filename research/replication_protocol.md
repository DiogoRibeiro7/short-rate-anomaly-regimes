# Replication Protocol

## Replication labels

Every article statistic receives exactly one label.

- `reproduced` when the same definition and estimator fall within a predeclared numerical tolerance;
- `approximately_reproduced` when the original input or software is unavailable but a close documented reconstruction produces a similar result;
- `partially_recovered` when a target carries several statistics and some land inside the published rounding while others do not, so neither a recovery nor a failure label describes the target as a whole;
- `not_reproducible_missing_input` when an essential article input cannot be obtained;
- `contradicted` when the same definition and estimator yield a materially different result after independent checks;
- `not_attempted` when an earlier dependency has not passed.

### Reconstruction-qualified sub-labels

When the article does not identify the source file it used, source identity
cannot be established and numerical proximity is not source identity. Targets
estimated from a documented reconstruction therefore carry one of the authorised
sub-labels below instead of a bare base label. Each sub-label refines exactly one
base label, is still exactly one label for the statistic, and may never be
reported as exact replication.

These are the exact strings emitted by
`short_rate_anomaly_regimes.rates.baseline_reconstruction.classify_replication_target`
when no exact input is available:

- `approximately_reproduced_under_documented_reconstruction` refines
  `approximately_reproduced`, and applies when the coefficient layer and the
  descriptive layer both fall within the declared tolerances;
- `approximately_reproduced_coefficients_only_under_documented_reconstruction`
  refines `approximately_reproduced`, and applies when the coefficient layer
  falls within tolerance and the descriptive layer does not;
- `not_reproduced_under_documented_reconstruction_exact_input_missing` refines
  `not_reproducible_missing_input`, and applies when the coefficient layer does
  not fall within tolerance while the exact input remains unavailable. It is not
  a contradiction, because `contradicted` requires a completed source-compatible
  attempt.

When an exact input is available the same function returns the base labels
`reproduced`, `approximately_reproduced`, or `contradicted`, and it returns
`not_attempted` for an empty comparison.

One further sub-label is emitted by `scripts/reconstruct_rate_innovations.py`:

- `not_attempted_no_published_target_for_this_series` refines `not_attempted`,
  and applies to a registered sensitivity series for which the article publishes
  no target at all.

No label outside this closed set, base or sub-label, may appear in a replication
claim, an audit artifact, or the manuscript.

## Evidence chain

Each table target must link to

1. a page, table, panel, row, and column in the article or supplement;
2. the exact raw source files;
3. transformation code and configuration;
4. intermediate checksums;
5. estimator code and version;
6. generated table cells;
7. numerical tolerance and status decision.

## Tolerance hierarchy

The tolerance is set before viewing the replicated estimate.

- exact counts and dates must match exactly;
- means, standard deviations, and correlations use absolute and relative tolerances based on published rounding;
- coefficients and risk prices use a tolerance derived from the displayed decimals and scale;
- t-statistics allow small differences due to covariance implementation only after confirming the same lag rule;
- p-values are compared through the underlying statistic when possible.

## Prohibited shortcuts

- digitising a published table and treating it as source data;
- replacing a missing portfolio set without changing the replication label;
- choosing a FRED series because it gives a closer result;
- changing sample endpoints after seeing results;
- reporting only the best rate or anomaly specification;
- using current data revisions without preserving vintage information when the revision can matter;
- describing a reconstruction as an exact replication.
