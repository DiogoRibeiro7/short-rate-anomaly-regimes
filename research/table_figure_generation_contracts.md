# Table And Figure Generation Contracts

These contracts define manuscript outputs before empirical results are generated.
No shell may contain invented numerical cells, dummy stars, or example estimates.

## General Contract

- Every output uses the artifact source listed in
  `research/manuscript_table_figure_map.csv`.
- Each table stores sample, model, estimator, test assets, uncertainty method,
  and evidence gate in metadata before rendering.
- Comparator tables use a common asset-date intersection within each comparison.
- Captions define sample, estimator, standard errors or diagnostic uncertainty,
  and significance notation when significance notation is available.
- Missing source inputs render a blocked-status note rather than empty numerical
  cells.

## Shell List

| Identifier | Render rule |
|---|---|
| MT_DATA | Render from the data-access matrix and source registry. |
| MT_SUMMARY | Render only after baseline factor and innovation diagnostics are frozen. |
| MT_REPLICATION | Render from the table-level replication audit. |
| MT_WEAK | Render only after beta-dispersion and rank diagnostics are frozen. |
| MT_BASELINE | Render only after baseline two-pass estimates are frozen. |
| MT_ROBUST | Render only after comparator and robustness estimates are frozen. |
| MT_POST | Render only after post-publication extension estimates are frozen. |
| MT_REGIME | Render only after regime interaction and equivalence outputs are frozen. |
| MT_SHOCK | Appendix-only; render only after event-level components, monthly aggregates, and component-strength diagnostics are frozen. |
| MF_RATE | Render only after rate series, innovations, and regime labels are frozen. |
| MF_BETA | Render only after baseline beta and average-return artifacts are frozen. |
| MF_ROLLING | Render only after rolling or expanding risk-price artifacts are frozen. |
| MF_ERRORS | Render only after model-comparison loss artifacts are frozen. |
| MF_REGIME | Render only after regime equivalence intervals are frozen. |
| MF_SHOCK | Appendix-only; render only after component-spanning and component-strength artifacts are frozen. |
