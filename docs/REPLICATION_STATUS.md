# Replication Status

This project has not produced empirical replication results yet. The current repository state is a tested research scaffold with evidence gates for future work.

## Current State

- Code scaffolding is present for configuration, source registry loading, monthly panel validation, provenance, rate innovations, first-pass regressions, cross-sectional OLS, portfolio loading, and audit writing.
- Unverified empirical steps are deliberately gated with `NotImplementedError`.
- Strict replication is blocked until the article, supplement, exact source definitions, and required data inputs are legally obtained and recorded.
- No raw data, licensed data extracts, generated tables, generated figures, or manuscript build products are committed.

## Strict Replication Blockers

The following inputs are still marked as missing or pending in `research/data_access_matrix.csv`:

- article PDF and supplement;
- exact Kenneth French archive definitions for required public files;
- exact short-rate series and aggregation conventions;
- original or reconstructable definitions for asset growth, equity duration, and inventory growth portfolios.

## Status Labels

Replication claims must use the labels defined in `research/replication_protocol.md`:

- `reproduced`;
- `approximately_reproduced`;
- `not_reproducible_missing_input`;
- `contradicted`;
- `not_attempted`.

Any result that uses substituted data, reconstructed portfolios, revised series, or unverifiable conventions must not be labelled as exact replication.

## Next Evidence Gates

Before empirical implementation proceeds, the project should:

1. Obtain legal access to the article and supplement.
2. Extract table targets into `research/table_target_manifest.csv`.
3. Verify source definitions and licence status in `research/data_access_matrix.csv`.
4. Freeze raw-data retention, checksum, and provenance rules.
5. Confirm exact sample endpoints, rate units, portfolio definitions, estimators, covariance rules, and numerical tolerances.
