# Short Rate Anomaly Regimes

[![CI](https://github.com/DiogoRibeiro7/short-rate-anomaly-regimes/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/short-rate-anomaly-regimes/actions/workflows/ci.yml)

A reproducible replication and extension of Maio and Santa-Clara (2017), *Short-Term Interest Rates and Stock Market Anomalies*, asking whether short-rate innovations still price equity anomalies after the publication sample and across monetary regimes.

The paper is written and builds from this repository: [`paper/manuscript.pdf`](paper/manuscript.pdf), 24 pages.

## Status

The empirical programme is complete through Milestone 10. Every result table and figure in the manuscript is generated from frozen artifacts rather than transcribed, and a test fails if a committed table stops matching its source.

**Every estimate carries the label `documented_reconstruction`.** The article names its data providers without series codes or archive vintages, and the anomaly decile panels come from the original author's source in a later rebuild, so no result is eligible for an exact-replication label at any recovery rate. The reconstruction can show that a published pattern reappears, and that a pattern fails to extend; it cannot attribute a cell-level discrepancy to the article rather than to the inputs.

The adversarial release gate reports `0` critical and `0` major issues, with `release_verdict: full_release_ready`. See [`artifacts/release/release_gate.json`](artifacts/release/release_gate.json) and [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md).

## Findings

Thresholds, comparators, and decision rules were fixed before the corresponding estimate existed. Every registered gate is reported, whether it passed or failed.

| Claim | Outcome |
|---|---|
| Baseline replication, 1972-2013 | Published qualitative result recovers |
| **H1** incremental pricing vs the ex ante CAPM comparator | `unsupported` on the joint asset set |
| **H2** post-publication compatibility | `post_publication_compatibility_unsupported` |
| **H3** regime stability | `regime_stability_unsupported_under_the_registered_equivalence_standard` |
| **H4a/b/c** weak-factor identification, influence, precision | all `pass` |

On the baseline the short-rate innovation earns a price of risk of `-0.6985` per month with a Shanken *t* of `-2.86`, and roughly halves cross-sectional pricing errors against the market model. Two qualifications follow, and both are pre-registered. The registered materiality standard is not met on the headline asset set, failing its absolute gate by `0.0136` monthly percentage points, and every traded multi-factor comparator attains a lower cross-sectional RMSE on the same seventy portfolios. Refitted post-2013 estimates then reverse sign for five of seven anomaly families, which the design shows is neither a data-vintage artifact nor, by the registered identification gate, a weak-factor artifact.

Across regimes the evidence is deliberately asymmetric. The pooled interaction model rejects beta stability on all 648 months, while of the seventy per-portfolio equivalence tests 26 certify equivalence, 44 are inconclusive, and none demonstrates a change beyond the registered bound. A simulation shows that imprecision is a property of two-pass estimation at regime-length samples rather than a fact about the periods: resolving fitted-premium spreads against the `0.25` bound needs 180 months, and the lower-bound regime has 84.

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

Raw and processed data are not redistributed. See [`docs/DATA_ACQUISITION.md`](docs/DATA_ACQUISITION.md) for source-by-source acquisition and redistribution guidance, and [`research/data_access_matrix.csv`](research/data_access_matrix.csv) for the licence and definition status of each input.

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

This regenerates the result tables and figures from the artifacts, validates the manuscript, and compiles `paper/manuscript.pdf`. `latexmk` runs from `paper/` so that `\bibliography{references}` resolves, with auxiliary files sent to `paper/build/`.

## Analysis scripts

The empirical pipeline lives in [`scripts/`](scripts/), run in dependency order. Each writes artifacts under `artifacts/` with a provenance record carrying input and output checksums.

```bash
PYTHONPATH=src poetry run python scripts/acquire_short_rates.py
PYTHONPATH=src poetry run python scripts/reconstruct_rate_innovations.py
PYTHONPATH=src poetry run python scripts/build_baseline_panel.py
PYTHONPATH=src poetry run python scripts/run_baseline_replication.py
PYTHONPATH=src poetry run python scripts/run_h1_materiality.py
PYTHONPATH=src poetry run python scripts/run_weak_factor_diagnostics.py
PYTHONPATH=src poetry run python scripts/build_extension_panels.py
PYTHONPATH=src poetry run python scripts/run_temporal_extension.py
PYTHONPATH=src poetry run python scripts/build_regime_panel.py
PYTHONPATH=src poetry run python scripts/run_regime_equivalence.py
PYTHONPATH=src poetry run python scripts/run_regime_interactions.py
```

Two are slow: the pooled interaction script runs an exhaustive Bai-Perron search, and `analyse_regime_power.py` simulates 2,000 replications at each of sixteen window lengths.

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
