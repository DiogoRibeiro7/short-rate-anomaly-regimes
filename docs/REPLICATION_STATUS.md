# Replication Status

This project has not produced empirical replication results yet. The current repository state is a tested research scaffold with evidence gates for future work.

## Current State

- Code scaffolding is present for configuration, source registry loading, monthly panel validation, provenance, rate innovations, first-pass regressions, cross-sectional OLS, portfolio loading, and audit writing.
- Repository-foundation checks now validate every project YAML file and the source registry through typed CLI commands.
- Data-provenance commands exist for dry-run acquisition planning, manual source registration, and DuckDB catalog creation, but live acquisition is blocked until exact article source definitions are frozen.
- Short-rate factor construction code is implemented for baseline AR(1) innovations, alternate namespaces, diagnostics, and artifact writing; actual factor output generation is blocked until raw rate inputs are registered.
- Test-asset assembly code is implemented for Kenneth French 25-portfolio parsing, canonical ordering, validation, construction manifests, and synthetic double-sort reconstruction tests; actual portfolio output generation is blocked until exact archive names and author or WRDS inputs are registered.
- First-pass time-series estimation code is implemented for excess-return construction, explicit date intersection accounting, OLS with intercept, Newey-West inference, independent matrix-HAC verification, residual/influence diagnostics, and artifact writing; actual first-pass output generation is blocked until factor, risk-free, and portfolio panels exist.
- Cross-sectional pricing code is implemented for OLS, GLS, fixed-beta Fama-MacBeth, Shanken-style corrected uncertainty, weak-factor warnings, leave-one-group systems, GRS diagnostics, simulation checks, model-evaluation tables, and artifact writing; actual second-pass output generation is blocked until first-pass artifacts and portfolio panels exist.
- Replication-audit code is implemented for frozen table-target loading, tolerance-based statistic comparison, allowed status assignment, missing-input audit rows, CSV/JSON output, and a standalone baseline-only replication report. The current committed audit marks all 23 frozen table targets as `not_reproducible_missing_input` because baseline generated artifacts are absent; the report includes bibliographic evidence, source definitions, factor/portfolio/estimator reconstruction, weak-factor diagnostics, deviations, a bounded conclusion, and the complete audit table.
- Robustness and weak-factor diagnostics are implemented for beta-matrix rank, descriptive singular values and condition numbers, standardized exposure dispersion, factor spanning, irrelevant-factor flags, Holm correction within registered robustness families, economic-change flags, and predeclared classification as `robust`, `conditionally_robust`, `fragile`, or `unidentified`. The current robustness report is `unidentified` because baseline generated artifacts are absent.
- Temporal-extension scaffolding is implemented for locked baseline vintages, post-2013 extension vintages, revised-history audit tables, reduced extension universes, December 2013 frozen-parameter pricing checks, expanding and rolling window plans, and December 2013 boundary figures. The current temporal report is `blocked_missing_input` because compatible baseline and extension panels are absent.
- Monetary-regime stability code is implemented for source-recorded regime tables, deterministic labels, boundary-shift sensitivity, split-sample eligibility, pooled regime interactions, joint Wald tests, Chow tests, Quandt-Andrews scans, Bai-Perron-style break selection, CUSUM diagnostics, Holm correction, stability verdicts, and report/figure writers. The current regime report is `blocked_missing_input` because baseline factors and extension panels are absent.
- Shock-decomposition code is implemented for the selected Jarocinski-Karadi updated Fed shock source, rejected-candidate records, event-level sign decomposition into policy, central-bank-information, and ambiguous components, no-meeting monthly aggregation, source-study statistic audits, asset-pricing factor design, spanning correlations, and policy-language enforcement. The current shock report is `blocked_missing_input` because the event-level shock file is absent and redistribution terms still need to be recorded.
- Out-of-sample falsification code is implemented for frozen annual refit schedules, expanding and rolling windows, no-lookahead two-pass forecasts, historical-mean and zero-return benchmarks, forecast vintage records, cross-sectional error metrics, rank diagnostics, model-confidence sets, and report/table writers. The current out-of-sample report is `blocked_missing_input` because baseline factors and extension panels are absent.
- Manuscript-output scaffolding is implemented for the required outline, full extension-paper draft, reproducibility statement, data access statement, hypothesis registry, robustness appendix, table-level replication appendix, artifact-map validation, numeric-claim traceability, empirical-paragraph context declarations, table/figure artifact-source checks, title checks, and restricted causal-language checks. The current manuscript-output report is `blocked_missing_input` because empirical tables and extension panels are absent.
- Adversarial release checks are implemented for restricted-path detection, processed-data redistribution warnings, sanitized environment manifests, SBOM generation from `poetry.lock`, source and public-artifact checksums, deterministic source archive packaging, archive manifests, data-acquisition guidance, release notes, and code/econometric audit reports. The current release gate reports `0` critical issues and `1` major unresolved issue; source-code release and a source-only tag are permitted, while empirical-results release and empirical-result tagging remain blocked by missing factor and extension-panel artifacts.
- Empirical input acquisition is complete for the rate, market, risk-free, and anomaly-portfolio layers. Four FRED rate series, six Kenneth French archive vintages, and two Hou-Xue-Zhang testing-portfolio archives are frozen with raw and normalized checksums, retrieval timestamps, observation ranges, units, frequency, source notes, vintage information, and redistribution status under `artifacts/provenance/`.
- The monthly aggregation of both baseline rate series is verified exactly rather than assumed: `FEDFUNDS` equals the rounded calendar-day mean of `DFF` in 864 of 864 complete months, `TB3MS` equals the rounded mean of available business-day `DTB3` observations in 846 of 846, and two competing aggregation rules are rejected.
- The article's unstated AR(1) timing convention is resolved from the published statistics and tested automatically. R1a is classified per rate series as `approximately_reproduced_under_documented_reconstruction`; it is not, and may not be, labelled exact replication, because the article names a provider without a series code or vintage.
- The canonical baseline panel exists at `data/processed/baseline_panel.parquet`: 504 months from 1972-01 to 2013-12, 78 columns, passing all 14 validation checks for keys, ordering, gaps, endpoint, missingness, infinities, forward filling, units, and timing alignment.
- The overall input-readiness verdict is `PARTIAL`. See `reports/baseline_input_readiness.md` for the per-target breakdown of which replication stages can proceed.
- Unverified empirical steps are deliberately gated with explicit exceptions.
- Strict replication remains blocked. Inputs are now acquired, but no input qualifies as exact, because the article names providers and people rather than files. Every downstream analysis therefore carries a `documented_reconstruction` label. The final article PDF and publisher supplement ZIP are present locally and hashed.
- The current article extraction status is documented in `research/article_method_extraction.md`.
- No raw data, licensed data extracts, generated tables, generated figures, or manuscript build products are committed.

## Strict Replication Blockers

The following inputs are still marked as missing or pending in `research/data_access_matrix.csv`:

- exact Kenneth French archive definitions for required public files;
- exact short-rate series and aggregation conventions;
- original or reconstructable definitions for asset growth, equity duration, and inventory growth portfolios.
- processed short-rate factors, risk-free returns, and portfolio panels required for first-pass regressions.
- first-pass coefficient, residual, and covariance artifacts required for cross-sectional pricing.
- generated baseline statistic cells required to move audit rows from missing-input status to reproduced, approximate, or contradicted labels.
- generated baseline and robustness specification cells required to classify empirical robustness beyond `unidentified`.
- source-compatible post-2013 portfolio and factor panels required for temporal extension without revising the locked baseline vintage.
- baseline factor outputs and temporal-extension monthly panels required before monetary-regime stability can be estimated.
- selected Jarocinski-Karadi high-frequency event file and redistribution review required before shock decomposition can produce monthly factors.
- baseline factor outputs, compatible portfolio panels, and temporal-extension monthly panels required before out-of-sample falsification can run.
- frozen empirical tables, figures, and extension artifacts required before the manuscript can contain numerical conclusions.
- generated factor and extension-panel artifacts required before empirical-results release is permitted by `artifacts/release/release_gate.json`.

## Status Labels

Replication claims must use the labels defined in `research/replication_protocol.md`.

Base labels:

- `reproduced`;
- `approximately_reproduced`;
- `not_reproducible_missing_input`;
- `contradicted`;
- `not_attempted`.

Authorised reconstruction-qualified sub-labels. Each refines exactly one base label, is still exactly one label for the statistic, and is used whenever the article does not identify the source file, so that no reconstruction can be read as exact replication. The first three are the exact strings returned by `classify_replication_target` in `src/short_rate_anomaly_regimes/rates/baseline_reconstruction.py` when no exact input is available; the fourth is emitted by `scripts/reconstruct_rate_innovations.py`:

- `approximately_reproduced_under_documented_reconstruction`, refining `approximately_reproduced`;
- `approximately_reproduced_coefficients_only_under_documented_reconstruction`, refining `approximately_reproduced`;
- `not_reproduced_under_documented_reconstruction_exact_input_missing`, refining `not_reproducible_missing_input`;
- `not_attempted_no_published_target_for_this_series`, refining `not_attempted`.

Any result that uses substituted data, reconstructed portfolios, revised series, or unverifiable conventions must not be labelled as exact replication.

## Next Evidence Gates

Before empirical outputs are generated, the project should:

1. Verify source definitions and licence status in `research/data_access_matrix.csv`.
2. Freeze exact public archive names, source versions, and short-rate series identifiers.
3. Register author-provided portfolio returns or freeze WRDS reconstruction definitions.
4. Confirm exact sample endpoints, rate units, portfolio definitions, estimators, covariance rules, and numerical tolerances.
