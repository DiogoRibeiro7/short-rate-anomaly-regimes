# Release Notes

## Release Verdict

- Source-code release: `permitted`
- Empirical-results release: `blocked`
- Source-only tag status: `source_only_tag_allowed`
- Empirical-result tag status: `blocked`
- Critical issues: `0`
- Major issues: `1`

## Exact Results

- No empirical table is currently classified as exact replication.

## Approximate Results

- No empirical table is currently classified as approximate reconstruction.

## Blocked Results

- Baseline replication, temporal extension, monetary-regime stability, shock decomposition, out-of-sample falsification, and manuscript numerical conclusions remain blocked by missing generated empirical artifacts.

## Contradicted Results

- No contradiction is currently recorded because the empirical comparison has not run.

## Extension Results

- Temporal extension, monetary-regime stability, shock decomposition, and out-of-sample falsification are predeclared but blocked by missing generated extension artifacts.

## Major Unresolved Issues

- `empirical_artifacts_missing` at `data/processed/factors/short_rate_factors.parquet, data/processed/extension/monthly_panel.parquet`: The repository cannot reproduce manuscript tables or extension claims from a fresh checkout with the current public inputs.

## Restricted Materials

Copyrighted articles, publisher supplements, `prompts/`, credentials, local catalogs, and temporary artifacts are excluded from the release.

## Reproduction

Use `make check` and `make release-check` from a clean checkout. See `docs/DATA_ACQUISITION.md` for sources that cannot be redistributed. Public data acquisition remains disabled until exact source definitions are frozen.
