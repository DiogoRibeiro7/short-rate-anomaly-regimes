# Manuscript Decision Log

## 2026-07-31 Structural rewrite

- Completed the structural rewrite review pass.
- Reclassified the manuscript as a preliminary research design because baseline empirical artifacts are not yet generated.
- Reorganized the main text into eleven academic sections before appendices.
- Moved repository mechanics, source paths, release artifacts, and audit machinery out of the main economic argument.
- Preserved the distinction among exact replication, documented reconstruction, extension evidence, and missing-input status.
- Kept the interpretation boundary that an autoregressive short-rate residual is a rate innovation unless a high-frequency identification design supports narrower language.
- Left baseline, robustness, temporal, regime, shock-decomposition, and out-of-sample result sections as pending-result sections.

## Gate Status

- Structural rewrite pass complete.
- Framework, literature, mechanism, data, methods, and table-architecture passes remain eligible before empirical results.
- Baseline result writing remains blocked until frozen baseline result artifacts exist.

## Unresolved Items

- Original framework reconstruction must be verified directly against the article and supplement.
- Literature review must be expanded with verified primary scholarly sources.
- Empirical result writing must wait for generated baseline and extension artifacts.

## 2026-07-31 Original framework reconstruction

- Completed the original-framework reconstruction review pass through the baseline framework and table-target audit.
- Read the locally available article PDF and Internet Appendix PDF directly.
- Verified the ICAPM state variables, AR innovation form, two-pass estimator, no-intercept benchmark second pass, Shanken standard errors, bootstrap p-values, table groups, and anomaly portfolio families.
- Updated the manuscript's original-framework section to use only verified baseline mechanics.
- Left exact source-file identifiers and archive vintages as unresolved because the article identifies source providers but not every download artifact needed for computational exactness.

## Gate Status

- Original-framework reconstruction pass complete for paper-level framework reconstruction.
- Exact computational replication remains blocked by source-file and generated-artifact gates.

## 2026-07-31 Literature review

- Completed the literature-review pass.
- Verified primary or authoritative records for ICAPM theory, interest-rate risk, anomaly model comparison, monetary-policy surprises, information shocks, lower-bound regimes, two-pass inference, useless factors, asset-pricing test criticism, structural breaks, and factor-data vintage documentation.
- Added an annotated review at `research/annotated_literature_review.md`.
- Expanded `paper/references.bib` with verified bibliographic metadata and DOI or stable URL fields.
- Rewrote the manuscript related-literature section by research question rather than by author list.

## Gate Status

- Literature-review pass complete.
- Literature can be further deepened, but every citation now used in the manuscript has verified metadata.

## 2026-07-31 Economic mechanism and hypotheses

- Completed the economic-mechanism and hypotheses pass.
- Rewrote `research/hypothesis_registry.csv` with explicit nulls, alternatives, primary outcomes, estimators, samples, test assets, direction or equivalence criteria, multiplicity families, and interpretation rules.
- Repaired the stability hypothesis by replacing failure-to-reject language with an equivalence-interval design.
- Strengthened the post-publication hypothesis so a nonzero risk price is insufficient without sign, economic-magnitude, and pricing-error compatibility.
- Reframed shock decomposition around incremental pricing content and interpretation of the aggregate rate innovation.
- Added `research/mechanism_hypothesis_map.md` and a manuscript mechanism-to-hypothesis table.

## Gate Status

- Economic-mechanism and hypotheses pass complete.
- Hypothesis interpretation remains gated by missing baseline, extension, and shock artifacts.

## 2026-07-31 Data and portfolio section

- Completed the data and portfolio-section pass.
- Revised the manuscript data section to distinguish exact replication inputs, documented reconstructions, unavailable inputs, and extension inputs.
- Added a manuscript data-source table with human-readable source, frequency, transformation, and status fields.
- Added `research/data_flow_diagram.md` as the source contract for the manuscript data-flow figure.
- Updated `research/data_dictionary.md` with source-status classes, portfolio-family statuses, common-intersection rules, and survivorship-treatment discipline.

## Gate Status

- Data and portfolio-section pass complete.
- Definitive portfolio construction remains blocked until exact source files, vintages, and documentation are frozen.

## 2026-07-31 Econometric methods

- Completed the econometric-methods pass.
- Expanded `research/statistical_protocol.md` with short-rate innovation construction, first-pass and second-pass notation, model comparison, weak-factor diagnostics, temporal extension, regime equivalence, high-frequency decomposition, out-of-sample design, and multiplicity rules.
- Rewrote the manuscript econometric-methods section to define the design before result interpretation.
- Added a manuscript method-to-hypothesis table.

## Gate Status

- Econometric-methods pass complete.
- Baseline estimator mechanics are verified, but empirical interpretation remains blocked by missing generated artifacts.

## 2026-07-31 Table and figure architecture

- Completed the table and figure architecture pass.
- Added `research/manuscript_table_figure_map.csv` for the planned main tables and figures, including evidence gates and artifact sources.
- Added `research/table_figure_generation_contracts.md` and `research/latex_table_figure_shells.tex`.
- Updated `research/table_target_manifest.csv` with presentation roles while preserving the frozen target identifiers and order.
- Added a manuscript appendix describing the planned evidence sequence.

## Gate Status

- Table and figure architecture pass complete.
- Baseline result writing is blocked because frozen baseline result artifacts do not exist.
