# Milestones

A milestone passes only when every acceptance gate is satisfied. Later milestones may not reinterpret failed earlier milestones as successful.

## Milestone 0 Evidence freeze

**Objective**

Create a complete article evidence pack before coding the empirical model.

**Tasks**

1. Obtain the final article PDF and supplementary material legally.
2. Record file hashes, publication metadata, and version dates.
3. Extract every equation, table, figure, sample definition, source, transformation, estimator, covariance rule, and comparator model.
4. Replace every `TBD` in `research/table_target_manifest.csv`.
5. Populate a variable-level source map and a table-to-code map.
6. Identify differences between the working-paper and final published versions.

**Deliverables**

- `references/private/article.pdf`
- `references/private/supplement.pdf`
- `artifacts/evidence/article_manifest.json`
- completed `research/table_target_manifest.csv`
- `research/article_method_extraction.md`

**Acceptance gate**

- No baseline variable remains described only as a candidate.
- Every published target has a page, table, panel, row, and column locator.
- Every covariance estimator and lag rule is explicit.
- Any unresolved ambiguity is listed as a blocking issue.

**Stop condition**

If the article or supplement cannot be accessed, strict replication is blocked. The repository may proceed only in reconstruction mode and must say so in every report.

## Milestone 1 Repository foundation

**Objective**

Make the scaffold executable, typed, tested, and reproducible before data work.

**Tasks**

1. Install Poetry dependencies.
2. Configure Ruff, mypy, pytest, pre-commit, and CI.
3. Validate all YAML files through Pydantic models.
4. Add environment and package-lock manifests.
5. Add deterministic random seed handling.
6. Add a CI matrix for Python 3.12.

**Deliverables**

- passing `poetry run ruff check .`
- passing `poetry run mypy src tests`
- passing `poetry run pytest`
- `.github/workflows/ci.yml`
- `artifacts/environment/manifest.json`

**Acceptance gate**

All checks pass from a clean clone. No research output depends on an untracked notebook state.

## Milestone 2 Data provenance

**Objective**

Acquire and validate every baseline input with immutable provenance.

**Tasks**

1. Finalise exact public archive names and series identifiers.
2. Implement public downloaders with retries, timeouts, and content checks.
3. Add manual-ingestion paths for author or licensed data.
4. Preserve raw files without modification.
5. Write SHA-256 hashes, retrieval timestamps, licences, URLs, and source versions.
6. Validate dates, units, missingness, duplicate months, column names, and sample coverage.
7. Create a DuckDB catalogue for metadata and processed panels.

**Deliverables**

- immutable files under `data/raw`
- `artifacts/provenance/*.json`
- `artifacts/data_quality/*.json`
- `data/catalog.duckdb`
- completed `research/data_access_matrix.csv`

**Acceptance gate**

Every required source either passes validation or has an explicit missing-input status. No substitute is silently loaded.

## Milestone 3 Short-rate innovations

**Objective**

Reconstruct the federal-funds and Treasury-bill factors exactly.

**Tasks**

1. Reproduce rate units and timing.
2. Estimate the article's AR innovation model.
3. Verify intercept, lags, sample, missing-value treatment, and residual alignment.
4. Produce innovations for each declared short rate.
5. Test residual autocorrelation, heteroskedasticity, structural breaks, and outliers.
6. Reproduce factor descriptive statistics and correlations.
7. Add AR(2), state-space, and futures-surprise alternatives only after the baseline passes.

**Deliverables**

- `data/processed/factors/short_rate_factors.parquet`
- `artifacts/tables/factor_descriptives.csv`
- `artifacts/diagnostics/rate_innovations.json`
- unit and simulation tests

**Acceptance gate**

Baseline factor statistics match the article within the frozen tolerance or receive a non-reproduced label with a documented cause.

## Milestone 4 Test asset assembly

**Objective**

Produce every 25-portfolio anomaly panel under verified definitions.

**Tasks**

1. Load public French portfolio sets using exact archive versions.
2. Ingest author-provided sets when available.
3. Reconstruct restricted sets only when CRSP and Compustat access exists.
4. Freeze breakpoint universe, size definition, characteristic timing, accounting lags, rebalancing date, delisting treatment, and weighting.
5. Create value-weighted baseline panels and declared equal-weighted robustness panels.
6. Verify portfolio ordering and extreme-spread directions.
7. Reproduce descriptive statistics.

**Deliverables**

- one Parquet file and schema per portfolio set
- `artifacts/portfolios/construction_manifest.json`
- `artifacts/tables/portfolio_descriptives/*.csv`

**Acceptance gate**

Each portfolio set has 25 unique, correctly ordered series and full declared sample coverage. Reconstructed sets carry a reconstruction label unless matched to author data.

## Milestone 5 First-pass estimates

**Objective**

Estimate article-consistent time-series betas and alphas.

**Tasks**

1. Align excess returns, market factor, and rate innovations.
2. Estimate CAPM and each two-factor model.
3. Apply the exact HAC covariance and lag rule.
4. Store coefficients, standard errors, t-statistics, residuals, R-squared, and observation counts.
5. Test monotonic beta patterns across portfolio sorts.
6. Run influence and residual diagnostics without changing the model.

**Deliverables**

- `artifacts/estimates/time_series/*.parquet`
- `artifacts/tables/time_series/*.csv`
- `artifacts/diagnostics/time_series/*.json`

**Acceptance gate**

Coefficient estimates are reproducible from one command and match article targets where published.

## Milestone 6 Cross-sectional pricing

**Objective**

Reproduce risk prices and pricing errors using all article estimators.

**Tasks**

1. Implement OLS two-pass, GLS two-pass, and Fama-MacBeth variants required by the article.
2. Implement Shanken-adjusted inference.
3. Implement the article's specification tests.
4. Compute pricing errors, cross-sectional R-squared, RMSE, MAE, and maximum absolute alpha.
5. Estimate each portfolio set separately and all declared joint systems.
6. Reproduce comparator models with identical samples and test assets.
7. Validate estimators on simulated factor models with known risk prices.

**Deliverables**

- `artifacts/estimates/cross_section/*.parquet`
- `artifacts/tables/cross_section/*.csv`
- estimator simulation tests

**Acceptance gate**

Risk-price and model-fit targets are assigned evidence-based replication labels. Simulations show correct size and acceptable bias under the declared design.

## Milestone 7 Published result audit

**Objective**

Issue a table-by-table replication verdict without extensions.

**Tasks**

1. Compare every target statistic with frozen tolerances.
2. Investigate differences through data, units, timing, software, and rounding.
3. Run an independent second implementation for central estimates.
4. Assign the five allowed replication labels.
5. Produce a machine-readable audit and a human replication report.

**Deliverables**

- `artifacts/audit/table_replication.csv`
- `reports/generated/replication_report.md`
- `reports/generated/replication_report.tex`

**Acceptance gate**

Every target has a status, evidence trail, and explanation. No extension result appears in the baseline verdict.

## Milestone 8 Robustness and weak factors

**Objective**

Determine whether the baseline fit is statistically and economically robust.

**Tasks**

1. Diagnose standardized exposure dispersion, beta-matrix rank, irrelevant factors, and weak identification.
2. Add misspecification-robust inference and confidence sets where feasible.
3. Compare alternative HAC lags and block-bootstrap intervals.
4. Run leave-one-anomaly-set-out and leave-one-portfolio-out tests.
5. Test alternative rate series and innovation models.
6. Measure influence of crisis months and individual years.
7. Adjust secondary-test p-values within registered families.

**Deliverables**

- `artifacts/diagnostics/weak_factor/*.json`
- `artifacts/tables/robustness/*.csv`
- `reports/generated/robustness_report.md`

**Acceptance gate**

The report states whether the baseline result survives weak-factor and influence analysis. Selective robustness reporting is prohibited.

## Milestone 9 Temporal extension

**Objective**

Extend all reproducible baseline inputs from January 2014 to the latest common month.

**Tasks**

1. Fetch only data definitions compatible with the baseline.
2. Freeze an extension cutoff date and vintage.
3. Append new observations without revising baseline-period data unless a revision audit is reported.
4. Estimate post-2013 performance using parameters frozen at December 2013.
5. Estimate expanding and rolling variants separately.
6. Compare pre- and post-publication anomaly spreads and beta patterns.

**Deliverables**

- `data/processed/extension/monthly_panel.parquet`
- `artifacts/tables/extension/*.csv`
- `artifacts/figures/extension/*.pdf`

**Acceptance gate**

The post-2013 evaluation is genuinely out of sample with respect to the original article. Revised historical data are isolated from vintage-consistent results.

## Milestone 10 Monetary regimes

**Objective**

Test the stability of factor loadings and risk prices across interpretable policy regimes.

**Tasks**

1. Validate deterministic regime dates against official policy records.
2. Estimate pooled models with regime interactions.
3. Estimate split-sample models only when each regime meets the minimum observation rule.
4. Conduct joint Wald, Chow, Quandt-Andrews, Bai-Perron, and CUSUM tests.
5. Shift boundaries by plus and minus three months.
6. Interact policy regimes with NBER recessions as a secondary analysis.
7. Report economic as well as statistical changes.

**Deliverables**

- `data/processed/regimes/monthly_regimes.parquet`
- `artifacts/tables/regimes/*.csv`
- `artifacts/figures/regimes/*.pdf`
- `reports/generated/regime_report.md`

**Acceptance gate**

Regime effects are reported jointly and with corrected uncertainty. Regime labels are not chosen to maximise fit.

## Milestone 11 Shock decomposition

**Objective**

Separate monetary-policy shocks from central-bank information and other rate news.

**Tasks**

1. Select a documented high-frequency surprise dataset and verify redistribution terms.
2. Freeze event windows, instruments, equity surprise, and identification rule.
3. Reproduce the source study's shock decomposition before using it in asset pricing.
4. Aggregate event shocks to monthly factors without look-ahead.
5. Test whether policy and information components span the aggregate rate innovation.
6. Re-estimate time-series and cross-sectional models with decomposed shocks.
7. Compare signs, risk prices, fit, and regime dependence.

**Deliverables**

- `data/processed/shocks/monthly_shocks.parquet`
- `artifacts/tables/shocks/*.csv`
- `artifacts/diagnostics/shocks/*.json`

**Acceptance gate**

The decomposition reproduces its source method and passes event-level validation. No causal label is used for a residual AR innovation.

## Milestone 12 Out-of-sample falsification

**Objective**

Test whether the model has stable predictive pricing content rather than in-sample fit only.

**Tasks**

1. Freeze an initial training sample and annual refit rule.
2. Estimate betas and risk prices using information available at each date.
3. Forecast cross-sectional mean returns or pricing relations for the next evaluation block.
4. Compare against CAPM, historical means, and declared multifactor benchmarks.
5. Report RMSE, MAE, out-of-sample R-squared, rank accuracy, and model confidence sets.
6. Repeat with rolling windows and alternative refit frequencies as secondary tests.

**Deliverables**

- `artifacts/forecasts/*.parquet`
- `artifacts/tables/out_of_sample/*.csv`
- `reports/generated/out_of_sample_report.md`

**Acceptance gate**

All tuning and model selection use training data only. Negative out-of-sample performance is reported without model rewriting.

## Milestone 13 Manuscript outputs

**Objective**

Produce the replication paper and extension manuscript from frozen artefacts.

**Tasks**

1. Build all tables and figures from machine-readable outputs.
2. Write separate replication and extension sections.
3. State which original findings are reproduced, approximated, unavailable, narrowed, or extended.
4. Include a complete data and code availability statement.
5. Use the title `Short Term Interest Rate Innovations Across Monetary Regimes`.
6. Avoid causal monetary-policy claims unless Milestone 11 supports them.

**Deliverables**

- `paper/manuscript.tex`
- `paper/references.bib`
- compiled PDF at `paper/manuscript.pdf`
- replication appendix and online appendix

**Acceptance gate**

Every numerical manuscript claim is generated from an artefact and has a source pointer. The abstract does not overstate identification.

## Milestone 14 Adversarial audit and release

**Objective**

Subject the repository and manuscript to independent hostile review before release.

**Tasks**

1. Run code, data, econometric, and manuscript review passes.
2. Reproduce the project in a clean environment.
3. Check for look-ahead, sample drift, unit errors, data leakage, and selective reporting.
4. Verify licences and remove restricted raw data from the release.
5. Create an archival release with checksums and a software bill of materials.
6. Record unresolved issues without suppressing them.

**Deliverables**

- `reports/generated/adversarial_code_review.md`
- `reports/generated/adversarial_econometric_review.md`
- `reports/generated/manuscript_review.md`
- release archive and tag

**Acceptance gate**

No critical unresolved issue remains. Major unresolved issues are either fixed or declared prominently in the release notes and manuscript limitations.
