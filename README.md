# Short Rate Anomaly Regimes

[![CI](https://github.com/DiogoRibeiro7/short-rate-anomaly-regimes/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/short-rate-anomaly-regimes/actions/workflows/ci.yml)

A reproducible replication and extension of Maio and Santa-Clara (2017), *Short-Term Interest Rates and Stock Market Anomalies*, asking whether short-rate innovations still price equity anomalies after the publication sample and across monetary regimes.

The paper is written and builds from this repository: [`paper/manuscript.pdf`](paper/manuscript.pdf), 26 pages.

## Status

The empirical programme is complete through Milestone 10. Every result table and figure in the manuscript is generated from frozen artifacts rather than transcribed, and a test fails if a committed table stops matching its source.

**Every estimate carries the label `documented_reconstruction`.** The article names its data providers without series codes or archive vintages, and the anomaly decile panels come from the original author's source in a later rebuild, so no result is eligible for an exact-replication label at any recovery rate. The reconstruction can show that a published pattern reappears, and that a pattern fails to extend; it cannot attribute a cell-level discrepancy to the article rather than to the inputs.

The adversarial release gate reports `0` critical and `1` major issue, with `release_verdict: source_only_release_ready`. The single major issue is that the generated data panels and estimate stores are not distributed. See [`artifacts/release/release_gate.json`](artifacts/release/release_gate.json) and [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md).

## What you received, and what you can rebuild

These instructions describe the archive in your hands. The gate reports two independent facts, and neither substitutes for the other.

| Gate field | Value | Meaning |
|---|---|---|
| `empirical_release` | `blocked` | The generated data panels and first- and second-pass estimate stores are **not** in this archive. |
| `empirical_rebuild` | `rebuildable_from_public_sources` | The archive carries a documented, deterministic path to regenerate them: `make reproduce`. |

**In the archive.** Source code, configuration, the frozen source registry, the pre-registration, the acquisition and estimation scripts, the manuscript and its compiled PDF, and the result tables, figures, and diagnostics that the manuscript cites. Every numeric claim in the paper can be traced to a shipped artifact and re-read without running anything.

**Not in the archive.** `data/raw`, `data/interim`, `data/processed`, the estimate stores under `artifacts/estimates/time_series` and `artifacts/estimates/cross_section`, and the first-pass table directory `artifacts/tables/time_series`. These are exactly the paths the release gate reports under `empirical_artifacts_missing`. The data policy forbids redistributing these sources, so they are rebuilt rather than shipped. A fresh clone contains only `.gitkeep` placeholders under `data/`; the release gate resolves required inputs against distributed archive membership, so it says so rather than reading an author's working tree.

**Not rebuildable at all.** The article's exact input files, the event-level high-frequency data for the shock decomposition, and the frozen training vintages for the out-of-sample falsification. These are missing-input blockers that no rebuild resolves. See [`docs/REPLICATION_STATUS.md`](docs/REPLICATION_STATUS.md).

To rebuild:

```bash
poetry install
make reproduce
```

`make reproduce` runs acquisition, panel construction, estimation, the temporal extension, the regime analysis, the generated reports, and the paper build in dependency order. Only the first stage needs network access. Budget hours: the precision, equivalence, interaction, and power stages run 10,000-draw bootstraps, an exhaustive Bai-Perron search, and 32,000 Monte Carlo replications. Stages can be run individually as `make reproduce-acquire`, `reproduce-panels`, `reproduce-estimates`, `reproduce-extension`, `reproduce-regimes`, and `reproduce-reports`.

## Findings

Thresholds, comparators, and decision rules were fixed before the corresponding estimate existed. Every registered gate is reported, whether it passed or failed.

| Claim | Outcome |
|---|---|
| Baseline replication, 1972-2013 | Published qualitative result recovers |
| **H1** incremental pricing vs the ex ante CAPM comparator | `unsupported` on the joint asset set |
| **H2** post-publication compatibility | `post_publication_compatibility_unsupported` |
| **H3** regime stability | `regime_stability_unsupported_under_the_registered_equivalence_standard` |
| **H4a/b/c** weak-factor identification, influence, precision | all `pass` |

On the baseline the short-rate innovation earns a price of risk of `-0.6985` per month with a Shanken *t* of `-2.86`, and roughly halves cross-sectional pricing errors against the market model. Two qualifications follow, and both are pre-registered. The registered materiality standard is not met on the headline asset set, failing its absolute gate by `0.0136` monthly percentage points, and every registered traded multi-factor comparator attains a lower in-sample cross-sectional RMSE on the same seventy portfolios, though on richer factor sets, so that comparison ranks fit rather than models. Refitted post-2013 estimates then reverse sign for five of seven anomaly families, which the design shows is neither a data-vintage artifact nor, by the registered identification gate, a weak-factor artifact.

Across regimes the evidence is deliberately asymmetric. The pooled interaction model rejects beta stability on all 648 months, while of the seventy per-portfolio equivalence tests 26 certify equivalence, 44 are inconclusive, and none demonstrates a change beyond the registered bound. A calibrated simulation locates the shared limitation: two thirds of the cross-sectional dispersion of estimated rate betas is sampling noise even in the full sample, and the nominal Shanken interval for the rate price attains its stated coverage at no simulated sample size. Resolving fitted-premium spreads against the `0.25` bound needs 180 months, and the lower-bound regime has 84.

## Research question

Do innovations in short-term interest rates price several equity anomalies because they represent a stable hedging state variable, or because the aggregate innovation combines monetary-policy shocks, central-bank information, macroeconomic news, and regime-dependent transmission?

## Baseline model

For test asset `i` and month `t`, the first pass is

```text
R_i,t - R_f,t = alpha_i + beta_i,M MKT_t + beta_i,r u_r,t + epsilon_i,t
```

where `u_r,t` is the AR(1) innovation in a short-term interest rate. The second pass is the article's no-intercept cross-sectional regression of average excess returns on full-sample betas,

```text
E[R_i - R_f] = beta_i,M lambda_M + beta_i,r lambda_r
```

with the Shanken (1992) correction applied to both risk prices and pricing errors, the article's chi-square specification test, and its centred cross-sectional fit metric. Eight models are estimated on eight asset sets, 64 systems in total.

## Repository principles

- Replication claims require a table-level evidence trail.
- Missing proprietary or author-supplied data are reported, not silently replaced.
- Every derived dataset has a schema, checksum, provenance record, and transformation log, and a test verifies that every recorded checksum matches the file on disk.
- Every numeric claim in the manuscript names the artifact it came from, and the validator follows `\input` so a generated table obeys the same rule.
- Statistical significance is reported together with economic magnitude and uncertainty.
- Regime definitions are explicit and deterministic in the main analysis.
- The extension is falsifiable. A failure to reject stability is a valid result, and a failed equivalence test is never reported as a detected difference.

## Quick start

```bash
poetry install
poetry run pre-commit install
cp .env.example .env
poetry run srar validate-config --config configs/baseline.yaml
poetry run pytest
```

The test suite also runs from an uninstalled source checkout:

```bash
PYTHONPATH=src python -m pytest
```

Nothing above needs network access or rebuilt data; it verifies the archive as received. Raw and processed data are not redistributed, and `make reproduce` is how you obtain them. See [`docs/DATA_ACQUISITION.md`](docs/DATA_ACQUISITION.md) for source-by-source acquisition and redistribution guidance, and [`research/data_access_matrix.csv`](research/data_access_matrix.csv) for the licence and definition status of each input.

## Quality gates

```bash
poetry check
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests scripts
poetry run python scripts/verify_title.py
poetry run python scripts/verify_manuscript.py
poetry run srar release-audit
poetry run pytest
```

`pytest` enforces a 95 percent coverage floor. The GitHub Actions workflow runs the same gates on pushes and pull requests to `main` and `develop`. `make check` runs the full set locally.

## Building the paper

```bash
make paper
```

This regenerates the result tables and figures from the shipped artifacts, validates the manuscript, and compiles `paper/manuscript.pdf`. It needs no network access and no rebuilt data. `latexmk` runs from `paper/` so that `\bibliography{references}` resolves, with auxiliary files sent to `paper/build/`.

## Analysis scripts

The empirical pipeline lives in [`scripts/`](scripts/) and is driven by `make reproduce`, which runs it in dependency order. Each script writes artifacts under `artifacts/` with a provenance record carrying input and output checksums.

| Stage | Target | Notes |
|---|---|---|
| Acquisition | `make reproduce-acquire` | **Network required.** Pulls the frozen vintages in `configs/data_sources.yaml`. Raw bytes are written once; delete `data/raw` and `data/interim` before re-acquiring against a new vintage. |
| Panels | `make reproduce-panels` | Source audits, AR(1) innovation reconstruction, baseline, comparator, and extension panels. Minutes. |
| Estimation | `make reproduce-estimates` | Baseline replication, published-target audit, H1 materiality, weak-factor diagnostics. **Slow:** `run_h4c_precision.py` is a 10,000-draw moving-block bootstrap. |
| Extension | `make reproduce-extension` | Post-2013 temporal evaluation. Minutes. |
| Regimes | `make reproduce-regimes` | **Slowest.** 10,000 draws per eligible regime, an exhaustive Bai-Perron search at three boundary shifts, and 2,000 replications at each of sixteen window lengths. |
| Reports | `make reproduce-reports` | Rewrites `reports/generated/` and the release assets from the rebuilt artifacts. |

The replication, shock-decomposition, and out-of-sample commands in the report stage exit non-zero by design: their gates are blocked by inputs this repository cannot obtain, and they write a blocked report naming those inputs.

## Repository map

- [`paper/`](paper/): manuscript source, bibliography, and the compiled PDF. `tables/` and `figures/` are generated, never edited by hand.
- [`scripts/`](scripts/): the empirical pipeline and the manuscript table and figure generators.
- [`src/short_rate_anomaly_regimes/`](src/): typed package for configuration, data validation, estimators, regime analysis, provenance, and reporting.
- [`tests/`](tests/): unit tests, drift guards for the generated tables and figures, and the provenance checksum audit.
- [`configs/`](configs/): declarative baseline, source-registry, regime, extension, and reporting configuration.
- [`research/`](research/): pre-registration. Hypothesis registry, economic thresholds, inference and bootstrap contracts, regime registry, and the design-correction changelog.
- [`reports/`](reports/): the analytical reports behind each milestone. `generated/` holds machine-written reports rebuilt from artifacts.
- [`docs/`](docs/): reviewer-facing data policy, replication status, and release notes.
- `data/` and most of `artifacts/`: ignored output locations; result tables, diagnostics, and provenance are tracked.

## Required reading order

1. [`research/research_design.md`](research/research_design.md)
2. [`research/hypothesis_registry.csv`](research/hypothesis_registry.csv)
3. [`research/economic_thresholds.md`](research/economic_thresholds.md)
4. [`research/inference_contract.md`](research/inference_contract.md)
5. [`reports/baseline_replication_audit.md`](reports/baseline_replication_audit.md)

Then the milestone reports: [`robustness_and_weak_factor_report.md`](reports/robustness_and_weak_factor_report.md), [`temporal_extension_report.md`](reports/temporal_extension_report.md), and [`monetary_regime_report.md`](reports/monetary_regime_report.md).

## Known limitations

- No input is an exact article input, so no layer earns an exact-replication label. The cell-level audit classifies each layer as partially recovered rather than reproduced or contradicted.
- The registered materiality standard mixes two relative gates at 10 percent with an absolute gate of `0.25` monthly percentage points, which on these test assets is the stricter bar by a factor of about five. It was frozen before any estimate existed and is applied as frozen; a future pre-registration should express the three gates on a common scale.
- The article's useless-factor bootstrap is not implemented, so its published empirical p-values are recorded as not attempted rather than compared against a different object.
- The high-frequency policy-information decomposition and the out-of-sample falsification are not run. Both are scoped as appendix designs and their generated reports say so.

## Citation

The baseline paper is

Maio, Paulo F., and Pedro Santa-Clara. 2017. Short-Term Interest Rates and Stock Market Anomalies. *Journal of Financial and Quantitative Analysis* 52(3), 927-961. DOI 10.1017/S002210901700028X.

See [`CITATION.cff`](CITATION.cff) for repository citation metadata.

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development rules and [`SECURITY.md`](SECURITY.md) for private reporting and restricted-data handling.
