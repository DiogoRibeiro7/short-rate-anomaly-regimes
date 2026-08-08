# Release Notes

## Release Verdict

- Source-code release: `permitted`
- Empirical-results release: `blocked`
- Empirical rebuild: `rebuildable_from_public_sources`
- Rebuild entry point: `make reproduce`
- Source-only tag status: `source_only_tag_allowed`
- Empirical-result tag status: `blocked`
- Critical issues: `0`
- Major issues: `1`

`empirical_release` reports whether the generated artifacts travel inside this archive. `empirical_rebuild` reports whether the archive carries a documented, deterministic path to regenerate them from the frozen public sources. The two are independent; the second never substitutes for the first.

## What This Archive Contains

- Source code, configuration, the frozen source registry, the pre-registration, the acquisition and estimation scripts, the manuscript with its generated tables and figures, and the result tables and diagnostics that the manuscript cites.
- It does not contain raw or processed data panels, first-pass and second-pass estimate stores, or any other artifact whose redistribution rights are unrecorded. Those are rebuilt, not shipped.

## Exact Results

- No result is classified as exact replication. The article identifies providers and people rather than files, so every estimate carries `documented_reconstruction`.

## Approximate Results

- Short-rate innovations are classified `approximately_reproduced_under_documented_reconstruction`.
- Risk prices, pricing errors and fit, and comparator models are classified `partially_recovered_under_documented_reconstruction`. See `docs/REPLICATION_STATUS.md` for the layer table.

## Blocked Results

- Reproduction from this archive alone. The generated data panels and estimate stores are not distributed; regenerate them with `make reproduce`.
- The article's useless-factor bootstrap, Table 5 and the appendix tables, equal-weighted results, and security-level reconstruction remain blocked by inputs this repository cannot obtain.
- The high-frequency shock decomposition and the out-of-sample falsification are not run; their generated reports record `blocked_missing_input` with the inputs named.

## Contradicted Results

- No contradiction is recorded. Every input is a reconstruction, so a failure to recover a published cell cannot be attributed to the article rather than the inputs.

## Extension Results

- The temporal extension and the monetary-regime analysis are run, and both are unsupported against their predeclared standards.
- The shock decomposition and the out-of-sample falsification remain predeclared appendix designs and are blocked by missing event-level and forecast inputs.

## Major Unresolved Issues

- `empirical_artifacts_missing` at `data/processed/factors/short_rate_innovations_baseline.parquet, data/processed/extension/monthly_panel.parquet, artifacts/estimates/time_series, artifacts/estimates/cross_section, artifacts/tables/time_series`: The distributed archive does not carry these generated artifacts, so a recipient cannot reproduce manuscript tables or extension claims from the archive alone.

## Restricted Materials

Copyrighted articles, publisher supplements, `prompts/`, credentials, local catalogs, and temporary artifacts are excluded from the release.

## Reproduction

Verify the archive with `make check` and `make release-check` from a clean checkout; neither needs network access or rebuilt data.

Rebuild the empirical artifacts with `make reproduce`. It runs source acquisition, panel construction, baseline estimation, the temporal extension, the regime analysis, and the paper build in dependency order. The acquisition stage needs network access and pulls the frozen vintages recorded in `configs/data_sources.yaml`; the bootstrap and simulation stages take hours. See `docs/DATA_ACQUISITION.md` for source-by-source access and redistribution status.
