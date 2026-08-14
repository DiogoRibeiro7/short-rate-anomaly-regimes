# Replication Status

The empirical programme is complete through Milestone 10. The baseline is reconstructed and audited against the published tables, the temporal extension and regime analysis are run, and the manuscript reports the results.

**No result is eligible for an exact-replication label.** The article names its data providers without series codes or archive vintages, and the anomaly decile panels come from the original author's source in a later rebuild that matches no published descriptive row on all five statistics. Every estimate therefore carries `documented_reconstruction`, and the layer classifications below say partially recovered rather than reproduced or contradicted.

## What This Release Contains

This section describes the archive you received. The release gate reports the two facts separately, and resolves them against distributed archive membership rather than against an author's working tree, so a fresh clone and a working checkout return the same verdict.

| Gate field | Value | Meaning |
|---|---|---|
| `empirical_release` | `blocked` | The generated data panels and the first- and second-pass estimate stores are not distributed. |
| `empirical_rebuild` | `rebuildable_while_frozen_source_bytes_remain_retrievable` | `make reproduce` regenerates them from the frozen public sources, verifying every download against the checksum recorded in `artifacts/provenance` and refusing to proceed on a mismatch. |
| `vintage_integrity` | `enforced_by_frozen_expected_hashes` | A revised provider file is detected and rejected rather than silently substituted. |
| `rebuild_precondition` | `frozen_source_bytes_remain_retrievable` | The rebuild holds only while those bytes can still be obtained. A provider that replaces a file without keeping an immutable copy leaves the rebuild refusing to run and the recipient unable to regenerate the result. |
| `self_contained_empirical_reproduction` | `not_supported_generated_artifacts_are_not_distributed` | The archive alone does not reproduce the empirical results. |

- **Shipped.** Source, configuration, the frozen source registry, the pre-specified design, the acquisition and estimation scripts, the manuscript and its compiled PDF, and every result table, figure, diagnostic, and provenance record the manuscript cites. The first-pass per-asset stores are not among them; the manuscript cites no table from `artifacts/tables/time_series`, which ships as an empty placeholder. All classifications in this document can be read from the archive without running anything.
- **Not shipped, rebuildable.** `data/raw`, `data/interim`, `data/processed`, `artifacts/estimates/time_series`, `artifacts/estimates/cross_section`, and `artifacts/tables/time_series`. The release gate names a subset of these under `empirical_artifacts_missing`: the two processed parquet panels and the three directories. It does not enumerate `data/raw` or `data/interim`, which are withheld by the same policy but are inputs rather than required release artifacts. The data policy forbids redistributing these sources. A fresh clone carries only `.gitkeep` placeholders there. Rebuild with `make reproduce`; only its acquisition stage needs network access, and only until the frozen raw bytes are on disk, and the bootstrap and simulation stages take hours. The acquisition stage verifies every download against the checksum recorded in `artifacts/provenance` and aborts on a mismatch rather than rebuilding against a revised vintage, so the rebuild either reproduces the frozen vintage or refuses to run; that is not a guarantee that a provider still serves those bytes. Changing the frozen vintage is a separate operation, `make update-vintage`, which no `reproduce` stage invokes. See [`docs/RELEASE_NOTES.md`](RELEASE_NOTES.md) and [`docs/DATA_ACQUISITION.md`](DATA_ACQUISITION.md).
- **Not rebuildable.** Everything under Remaining Blockers below. Those are missing-input blockers, not redistribution ones, and no rebuild resolves them.

## Current State

Estimated: eight models on eight asset sets, 64 systems, over the 504 baseline months from 1972-01 to 2013-12, using the article's own estimators. First pass is OLS with an intercept; second pass is the no-intercept cross-sectional regression on full-sample betas; uncertainty is the Shanken (1992) covariance applied to risk prices and pricing errors; the specification test and centred fit metric follow the article's equations.

| Layer | Recovered | Classification |
|---|---|---|
| R1a short-rate innovations | 9/10 and 10/10 per series | `approximately_reproduced_under_documented_reconstruction` |
| R1b first-pass betas, through the Table 5 premium decomposition | 14 of 42 | `partially_recovered_under_documented_reconstruction` |
| R1c risk prices | 23 of 45 | `partially_recovered_under_documented_reconstruction` |
| R1d pricing errors and fit | 7 of 79 | `partially_recovered_under_documented_reconstruction` |
| R1e comparator models | 3 of 20 | `partially_recovered_under_documented_reconstruction` |

Of 208 unique published cells, all 208 were compared, and 51 fall inside the published rounding. Recovery varies by statistic in a way the estimator predicts: market risk prices land inside the published rounding 20 times of 29 and agree in sign 29 times of 29; rate risk prices agree in sign 16 of 16 but reach printed precision less often; the specification statistic, which inverts a seventy-by-seventy pricing-error covariance through a pseudo-inverse, reaches it in none of 29. See [`reports/baseline_replication_audit.md`](../reports/baseline_replication_audit.md).

Registered hypothesis outcomes are recorded in `artifacts/diagnostics/` and summarised in the repository README. H4a, H4b and H4c pass; H1, H2 and H3 are unsupported against their predeclared standards.

## Remaining Blockers

These are the parts of the original evidence base that this repository still cannot produce.

- **Exact inputs.** The article identifies providers and people rather than files, so no reconstruction is eligible for an exact-replication label at any recovery rate. This bounds every claim here and is not resolvable without the original input files.
- **The article's useless-factor bootstrap.** Implemented, and no longer a blocker. See the section below.

## The Article's Empirical p-Values

All 118 published cells whose uncertainty is an empirical p-value were previously recorded as `not_attempted_bootstrap_not_implemented`. The article's procedure, Internet Appendix Section 4, is now implemented in `src/short_rate_anomaly_regimes/models/useless_factor_bootstrap.py` and run for all 29 systems the article prints a p-value for, at the published 5,000 replications, with no degenerate draws.

The comparison needs one adjustment the other cells do not. A bootstrap p-value is a Monte Carlo quantity with standard error `sqrt(p (1 - p) / B)`, about 0.007 near `p = 0.5` at `B = 5000`, while a p-value printed to three decimals carries a rounding tolerance of 0.0005. For most of the range the procedure's own sampling noise is an order of magnitude wider than the band a cell would have to land in, so a miss says nothing about whether the reconstruction is faithful: the article's own bootstrap, rerun on the article's own data under a different seed, would miss its published value just as often. Those cells are therefore reported as not resolvable rather than not recovered, which is the same distinction the regime analysis draws between an inconclusive result and a demonstrated difference.

| Outcome | Cells |
|---|---|
| `recovered_within_published_rounding` | 36 |
| `not_recovered_within_published_rounding` | 8 |
| `not_resolvable_monte_carlo_error_exceeds_published_rounding` | 74 |

Of the 37 cells where the printed tolerance is attainable at all, 29 are recovered. The 74 unresolvable cells are a property of comparing a simulated quantity against three printed decimals, not a finding about the reconstruction.

What the cells agree on is the inference they were printed to support:

| Verdict at the 5 percent level | Agreement |
|---|---|
| Risk-price significance | 45 of 45 |
| Specification test passes | 27 of 29 |
| Cross-sectional fit significance | 27 of 29 |

The p-value tests a useless-factor null: the factors are resampled on a time sequence independent of the residuals, so they cannot explain returns by construction. It answers how often a factor known to be useless produces a t-ratio this extreme, which is the Kan and Zhang (1999) concern the article guards against. It is not the p-value of a zero risk price in a correctly specified model. The procedure is an audit instrument and enters no registered gate; the repository's own confirmatory inference remains the moving-block bootstrap frozen in `research/bootstrap_contract.md`.
- **The Kan-Robotti-Shanken evaluation statistics of Table A.8.** Not reconstructible from the published description, which is a different blocker from not yet implemented. The appendix defines the first measure, `rho-hat squared`, by an equation, and that one is generated and audited: its CAPM value of 0.92 is recovered within the published rounding. It does not define the `Q-hat_c` statistic or the asymptotic p-values for `rho^2 = 1` and `rho^2 = 0`; footnote 4 records that those came from MATLAB code supplied privately by Kan and Robotti. Implementing Kan, Robotti and Shanken (2013) independently would reconstruct that paper rather than what this article ran, so the cells stay unattempted rather than being compared against a different object.
- **The Table A.9 covariance representation is partly reconstructed.** Unlike Table A.8 it carries no private-code caveat: the appendix prints the GMM moment conditions and defines the pricing errors and fit by reference to the paper's own equations. The risk prices, pricing errors and fit are generated. The t-ratios are not, because the appendix takes them from the GMM covariance that accounts for estimation error in the factor means, and the Shanken standard errors implemented here are a different object that must not be substituted for them.
- **The Table A.10 Hansen-Jagannathan distance is generated; its test is not.** The appendix prints the pricing condition, the stochastic-discount-factor form, the weighting matrix and the distance itself, and names the payoffs, so the distance is reconstructed. It does not say how the p-value for a zero distance is obtained; that distribution is a weighted sum of chi-squares whose weights depend on nuisance parameters, and selecting an implementation would be choosing from a literature the appendix does not cite for the purpose. The Table A.11 coefficient t-ratios come from the Gospodinov, Kan and Robotti (2014) sequential procedure, cited rather than defined, and are not produced.
- **Tables 7 to 9 and Appendix Tables A.2 to A.14.** Outside the scope of the current audit pass. Most report objects this repository does not generate, including the GMM system, the Hansen-Jagannathan distance, and the Kan-Robotti-Shanken metrics, so extending the audit to them requires those estimators first rather than more transcription. Table 5 is now audited: its 84 published cells are compared, and 21 fall inside the published rounding.
- **Equal-weighted results.** Blocked at the current sources.
- **Security-level reconstruction.** Not attempted; CRSP and Compustat access is not confirmed. See [`reports/data_access_feasibility.md`](../reports/data_access_feasibility.md).
- **The high-frequency policy-information decomposition.** Retired, not blocked. The registered source was obtained and cannot support the design: it covers 1990-02 onward, so it reaches 287 of the 504 baseline months, and its information component under the primary identification is nonzero in 99 of 408 months, which the pre-registered factor-strength condition forbids entering the pricing argument. Both facts are properties of the source rather than of any estimate, and both were read before any pricing regression used the data. Its generated report records `retired_from_design`. See [`reports/shock_decomposition_feasibility.md`](../reports/shock_decomposition_feasibility.md). The out-of-sample falsification is run: the two-factor system is refitted annually from a frozen 1999-12 training endpoint and evaluated on 70 portfolios across 26 windows through 2025-12, on the vintage-consistent panel so the evaluation does not cross a data-revision boundary. It attains an out-of-sample R2 of 0.0039 against the historical-mean benchmark and 0.1882 above a zero-return benchmark, so it improves on the historical mean by an economically negligible margin while clearly beating zero. Both sit inside the reported loss band, which is a descriptive screen and not a Hansen-Lunde-Nason confidence set.

## Status Labels

Replication claims must use the labels defined in `research/replication_protocol.md`.

Base labels:

- `reproduced`;
- `approximately_reproduced`;
- `partially_recovered`;
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

1. Implement the GMM, Hansen-Jagannathan and Kan-Robotti-Shanken estimators the remaining appendix tables report, then extend the cell-level audit to them.
