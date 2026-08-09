# Replication Status

The empirical programme is complete through Milestone 10. The baseline is reconstructed and audited against the published tables, the temporal extension and regime analysis are run, and the manuscript reports the results.

**No result is eligible for an exact-replication label.** The article names its data providers without series codes or archive vintages, and the anomaly decile panels come from the original author's source in a later rebuild that matches no published descriptive row on all five statistics. Every estimate therefore carries `documented_reconstruction`, and the layer classifications below say partially recovered rather than reproduced or contradicted.

## What This Release Contains

This section describes the archive you received. The release gate reports the two facts separately, and resolves them against distributed archive membership rather than against an author's working tree, so a fresh clone and a working checkout return the same verdict.

| Gate field | Value | Meaning |
|---|---|---|
| `empirical_release` | `blocked` | The generated data panels and the first- and second-pass estimate stores are not distributed. |
| `empirical_rebuild` | `rebuildable_from_public_sources` | `make reproduce` regenerates them from the frozen public sources, verifying every download against the checksum recorded in `artifacts/provenance` and refusing to proceed on a mismatch. |

- **Shipped.** Source, configuration, the frozen source registry, the pre-registration, the acquisition and estimation scripts, the manuscript and its compiled PDF, and every result table, figure, diagnostic, and provenance record the manuscript cites. The first-pass per-asset stores are not among them; the manuscript cites no table from `artifacts/tables/time_series`, which ships as an empty placeholder. All classifications in this document can be read from the archive without running anything.
- **Not shipped, rebuildable.** `data/raw`, `data/interim`, `data/processed`, `artifacts/estimates/time_series`, `artifacts/estimates/cross_section`, and `artifacts/tables/time_series`. The release gate names a subset of these under `empirical_artifacts_missing`: the two processed parquet panels and the three directories. It does not enumerate `data/raw` or `data/interim`, which are withheld by the same policy but are inputs rather than required release artifacts. The data policy forbids redistributing these sources. A fresh clone carries only `.gitkeep` placeholders there. Rebuild with `make reproduce`; only its acquisition stage needs network access, and only until the frozen raw bytes are on disk, and the bootstrap and simulation stages take hours. The acquisition stage verifies every download against the checksum recorded in `artifacts/provenance` and aborts on a mismatch rather than rebuilding against a revised vintage, so the rebuild either reproduces the frozen vintage or refuses to run; that is not a guarantee that a provider still serves those bytes. Changing the frozen vintage is a separate operation, `make update-vintage`, which no `reproduce` stage invokes. See [`docs/RELEASE_NOTES.md`](RELEASE_NOTES.md) and [`docs/DATA_ACQUISITION.md`](DATA_ACQUISITION.md).
- **Not rebuildable.** Everything under Remaining Blockers below. Those are missing-input blockers, not redistribution ones, and no rebuild resolves them.

## Current State

Estimated: eight models on eight asset sets, 64 systems, over the 504 baseline months from 1972-01 to 2013-12, using the article's own estimators. First pass is OLS with an intercept; second pass is the no-intercept cross-sectional regression on full-sample betas; uncertainty is the Shanken (1992) covariance applied to risk prices and pricing errors; the specification test and centred fit metric follow the article's equations.

| Layer | Recovered | Classification |
|---|---|---|
| R1a short-rate innovations | 9/10 and 10/10 per series | `approximately_reproduced_under_documented_reconstruction` |
| R1b first-pass betas | no published statistic-level target | `no_published_statistic_level_target` |
| R1c risk prices | 23 of 45 | `partially_recovered_under_documented_reconstruction` |
| R1d pricing errors and fit | 3 of 58 | `partially_recovered_under_documented_reconstruction` |
| R1e comparator models | 3 of 20 | `partially_recovered_under_documented_reconstruction` |

Of 123 unique published cells, all 123 were compared. Recovery varies by statistic in a way the estimator predicts: market risk prices land inside the published rounding 20 times of 29 and agree in sign 29 times of 29; rate risk prices agree in sign 16 of 16 but reach printed precision less often; the specification statistic, which inverts a seventy-by-seventy pricing-error covariance through a pseudo-inverse, reaches it in none of 29. See [`reports/baseline_replication_audit.md`](../reports/baseline_replication_audit.md).

Registered hypothesis outcomes are recorded in `artifacts/diagnostics/` and summarised in the repository README. H4a, H4b and H4c pass; H1, H2 and H3 are unsupported against their predeclared standards.

## Remaining Blockers

These are the parts of the original evidence base that this repository still cannot produce.

- **Exact inputs.** The article identifies providers and people rather than files, so no reconstruction is eligible for an exact-replication label at any recovery rate. This bounds every claim here and is not resolvable without the original input files.
- **The article's useless-factor bootstrap.** Every published empirical p-value comes from a 5,000-replication procedure that is not implemented, so those cells are `not_attempted_bootstrap_not_implemented` rather than compared against an asymptotic value that would be a different object.
- **Table 5, Tables 7 to 9, and Appendix Tables A.2 to A.14.** Outside the scope of the current audit pass.
- **Equal-weighted results.** Blocked at the current sources.
- **Security-level reconstruction.** Not attempted; CRSP and Compustat access is not confirmed. See [`reports/data_access_feasibility.md`](../reports/data_access_feasibility.md).
- **The high-frequency policy-information decomposition and the out-of-sample falsification.** Not run. Both remain appendix designs, and their generated reports report `blocked_missing_input` with the specific inputs named.

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

Any result that uses substituted data, reconstructed portfolios, revised series, or unverifiable conventions must not be labelled as exact replication. A completed attempt that fails to recover a published target is the only setting in which `contradicted` may be used, and no result here qualifies, because the inputs are reconstructions.

## Next Evidence Gates

1. Implement the article's useless-factor bootstrap, which would make roughly half the published-target registry auditable.
2. Extend the cell-level audit to Table 5 and the remaining appendix tables.
3. Acquire event-level data for the policy-information decomposition, or retire it from the design.
4. Run the out-of-sample falsification against the frozen 1999-12 training endpoint and annual refit schedule.
