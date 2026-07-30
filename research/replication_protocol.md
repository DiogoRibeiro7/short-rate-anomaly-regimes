# Replication Protocol

## Replication labels

Every article statistic receives exactly one label.

- `reproduced` when the same definition and estimator fall within a predeclared numerical tolerance;
- `approximately_reproduced` when the original input or software is unavailable but a close documented reconstruction produces a similar result;
- `not_reproducible_missing_input` when an essential article input cannot be obtained;
- `contradicted` when the same definition and estimator yield a materially different result after independent checks;
- `not_attempted` when an earlier dependency has not passed.

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
