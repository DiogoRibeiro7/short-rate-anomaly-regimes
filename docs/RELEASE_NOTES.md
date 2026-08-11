# Release Notes

## Release Verdict

- Source-code release: `permitted`
- Empirical-results release: `blocked`
- Empirical rebuild: `rebuildable_while_frozen_source_bytes_remain_retrievable`
- Rebuild entry point: `make reproduce`
- Source-only tag status: `source_only_tag_allowed`
- Empirical-result tag status: `blocked`
- Vintage integrity: `enforced_by_frozen_expected_hashes`
- Rebuild precondition: `frozen_source_bytes_remain_retrievable`
- Self-contained empirical reproduction: `not_supported_generated_artifacts_are_not_distributed`
- Critical issues: `0`
- Major issues: `1`

These describe three different properties, and only the first two are supported.

1. **Vintage integrity.** Every acquisition download is checked against the SHA-256 recorded in the shipped provenance manifests, and the rebuild aborts when a provider has revised a series rather than rebuilding against the revision. Changing a frozen vintage requires the separate `make update-vintage` operation, which no `reproduce` stage invokes.
2. **Rebuildability, conditional.** `empirical_rebuild` reports that the archive carries a documented, hash-verified rebuild path. That path regenerates the empirical artifacts only while the frozen source bytes remain retrievable. If a provider replaces a file and keeps no immutable historical copy, the rebuild will correctly refuse to run, and a recipient holding only this archive will not be able to regenerate the published result. Failing safely is not the same property as remaining reproducible indefinitely, and the status string is qualified so the two are not read as one.
3. **Self-contained empirical reproduction.** Not supported. The generated panels and estimate stores are not distributed, which is what `empirical_release: blocked` and the `empirical_artifacts_missing` issue record. Where redistribution rights permit it, depositing the frozen source bytes with the archival release would upgrade this property; where they do not, `docs/DATA_ACQUISITION.md` names the most immutable identifier available for each source.

`empirical_release` and `empirical_rebuild` are independent; the second never substitutes for the first.

## What This Archive Contains

- Source code, configuration, the frozen source registry, the pre-specified design, the acquisition and estimation scripts, the manuscript with its generated tables and figures, and the result tables and diagnostics that the manuscript cites.
- It does not contain raw or processed data panels, first-pass and second-pass estimate stores, or any other artifact whose redistribution rights are unrecorded. Those are rebuilt, not shipped.

## Exact Results

- No result is classified as exact replication. The article identifies providers and people rather than files, so every estimate carries `documented_reconstruction`.

## Approximate Results

- Short-rate innovations are classified `approximately_reproduced_under_documented_reconstruction`.
- Risk prices, pricing errors and fit, and comparator models are classified `partially_recovered_under_documented_reconstruction`. See `docs/REPLICATION_STATUS.md` for the layer table.

## Blocked Results

- Reproduction from this archive alone. The generated data panels and estimate stores are not distributed; regenerate them with `make reproduce`.
- Table 5, Tables 7 to 9, and the appendix tables beyond A.1 are not generated in this pass. The tables that are generated are audited cell by cell in `artifacts/audit/published_target_audit.csv`, which is the current record.
- `artifacts/audit/table_replication.csv` is stale and should not be read as the table-level status. It still records all twenty-three tables as `not_generated` and `not_reproducible_missing_input`, including Tables 3, 4, 6 and A.1, whose cells the cell-level audit does compare. It predates the estimates and was never regenerated. Regenerating it is an open item.
- Equal-weighted results and security-level reconstruction remain blocked by inputs this repository cannot obtain.
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

Rebuild the empirical artifacts with `make reproduce`. It runs source acquisition, panel construction, baseline estimation, the temporal extension, the regime analysis, and the paper build in dependency order. The acquisition stage needs network access unless the frozen raw bytes are already on disk; the bootstrap and simulation stages take hours. See `docs/DATA_ACQUISITION.md` for source-by-source access and redistribution status.

## Frozen-Vintage Verification

Every provider endpoint this project reads serves the current vintage: FRED's `fredgraph.csv` returns the latest revision of a series, and the Kenneth French, global-q, and Wharton files are replaced in place when the libraries are rebuilt. The rebuild therefore does not trust the URL. It treats the SHA-256 values in the shipped provenance manifests under `artifacts/provenance` as expected hashes: each acquisition downloads, hashes, and compares, normalises only on a match, and on a mismatch aborts naming the series, the expected hash, the received hash, and what to do next. A verification run rewrites no provenance manifest.

The guarantee is therefore that a rebuild either reproduces the frozen vintage or refuses to run. It is not a guarantee that a provider still serves those bytes. When a provider has revised a series, the archive's own results cannot be regenerated from that provider until the frozen bytes are recovered from an immutable source; `docs/DATA_ACQUISITION.md` names the preferred one for each.

Moving to a new vintage is a deliberate, separate operation: `make update-vintage` and its per-source targets pass `--update-vintage`, which is the only switch that may overwrite a recorded expected hash. It changes the inputs of every downstream result, so `make reproduce` must be re-run in full afterwards and the new vintage reported. No `reproduce` stage passes that switch.
