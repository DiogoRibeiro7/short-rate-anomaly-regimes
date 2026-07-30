# Evidence Freeze Prompt

Complete Milestone 0 only. Do not implement empirical estimators beyond extraction utilities.

## Required work

1. Locate the legally accessible final article PDF and publisher supplement.
2. Store them only under `references/private` and confirm `.gitignore` excludes them.
3. Compute SHA-256 checksums and create `artifacts/evidence/article_manifest.json` with title, authors, DOI, journal, volume, issue, pages, publication date, local path, checksum, and access note.
4. Read the article and supplement line by line. Create `research/article_method_extraction.md` with exact quotations limited to short necessary fragments and mostly paraphrased extraction.
5. Extract all sample endpoints, frequencies, units, release lags, rate series, risk-free definitions, portfolio sources, weighting rules, anomaly definitions, equations, estimators, HAC rules, tests, comparator models, and robustness checks.
6. Replace every placeholder row in `research/table_target_manifest.csv` with one row per published statistic that the project will reproduce.
7. Add page, table, panel, row, and column locators.
8. Compare the final article with the earlier working-paper version. Record any changed samples, tables, variables, or claims.
9. Add a blocking-ambiguity section. Never resolve ambiguity by selecting the most convenient interpretation.

## Tests

- Validate the manifest schema.
- Assert that every target has a unique ID and nonempty source locator.
- Assert that no baseline config field remains `verify_against_article` or `TBD` when the evidence is available.

## Acceptance evidence

Return a concise report listing extracted definitions, remaining blockers, number of table targets, and exact commands that pass.
