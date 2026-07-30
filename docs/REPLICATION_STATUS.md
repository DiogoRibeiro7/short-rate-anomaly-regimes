# Replication Status

This project has not produced empirical replication results yet. The current repository state is a tested research scaffold with evidence gates for future work.

## Current State

- Code scaffolding is present for configuration, source registry loading, monthly panel validation, provenance, rate innovations, first-pass regressions, cross-sectional OLS, portfolio loading, and audit writing.
- Repository-foundation checks now validate every project YAML file and the source registry through typed CLI commands.
- Data-provenance commands exist for dry-run acquisition planning, manual source registration, and DuckDB catalog creation, but live acquisition is blocked until exact article source definitions are frozen.
- Short-rate factor construction code is implemented for baseline AR(1) innovations, alternate namespaces, diagnostics, and artifact writing; actual factor output generation is blocked until raw rate inputs are registered.
- Test-asset assembly code is implemented for Kenneth French 25-portfolio parsing, canonical ordering, validation, construction manifests, and synthetic double-sort reconstruction tests; actual portfolio output generation is blocked until exact archive names and author or WRDS inputs are registered.
- Unverified empirical steps are deliberately gated with explicit exceptions.
- Strict replication is blocked until exact source definitions and required data inputs are legally obtained and recorded. The final article PDF and publisher supplement ZIP are present locally and hashed.
- The current article extraction status is documented in `research/article_method_extraction.md`.
- No raw data, licensed data extracts, generated tables, generated figures, or manuscript build products are committed.

## Strict Replication Blockers

The following inputs are still marked as missing or pending in `research/data_access_matrix.csv`:

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

Before empirical outputs are generated, the project should:

1. Verify source definitions and licence status in `research/data_access_matrix.csv`.
2. Freeze exact public archive names, source versions, and short-rate series identifiers.
3. Register author-provided portfolio returns or freeze WRDS reconstruction definitions.
4. Confirm exact sample endpoints, rate units, portfolio definitions, estimators, covariance rules, and numerical tolerances.
