# Short Rate Anomaly Regimes

[![CI](https://github.com/DiogoRibeiro7/short-rate-anomaly-regimes/actions/workflows/ci.yml/badge.svg)](https://github.com/DiogoRibeiro7/short-rate-anomaly-regimes/actions/workflows/ci.yml)

A reproducible research repository for replicating and extending Maio and Santa-Clara's study of short-term interest-rate innovations and stock-market anomalies.

## Status

This repository is an evidence-gated research scaffold. It currently contains configuration, typed pipeline interfaces, validation utilities, tests, and tracked milestone documents. It does not yet contain raw data, licensed data extracts, or empirical replication results.

Strict replication remains blocked until the final article, supplement, source definitions, and required licensed data inputs are legally obtained, hashed, and recorded in `research/data_access_matrix.csv`.

The adversarial release gate currently reports `0` critical issues and `1` major unresolved issue: source-code release is permitted, but empirical-results release is blocked until generated factor and extension-panel artifacts exist. See `docs/RELEASE_NOTES.md` and `artifacts/release/release_gate.json`.

See `docs/REPLICATION_STATUS.md` for the current replication state and `docs/DATA_POLICY.md` for source and artifact handling rules.

The repository has two deliberately separate tracks.

1. **Strict replication** reconstructs the published design as closely as the available paper, supplement, code, and data permit.
2. **Documented reconstruction** uses transparent substitutes when an original input is unavailable and never labels those results as reproduced.

The proposed follow-up paper is titled **Short Term Interest Rate Innovations Across Monetary Regimes**.

## Research question

Do innovations in short-term interest rates price several equity anomalies because they represent a stable hedging state variable, or because the aggregate innovation combines monetary-policy shocks, central-bank information, macroeconomic news, and regime-dependent transmission?

## Baseline model

For test asset `i` and month `t`, estimate

```text
R_i,t - R_f,t = alpha_i + beta_i,M MKT_t + beta_i,r u_r,t + epsilon_i,t
```

where `u_r,t` is the innovation obtained from an autoregressive model for a short-term interest rate. The initial baseline uses an AR(1), subject to verification against the published article and supplement.

The cross-sectional pricing relation is

```text
E[R_i - R_f] = lambda_0 + beta_i,M lambda_M + beta_i,r lambda_r
```

The replication must estimate the original variants, test assets, weighting choices, standard errors, and evaluation metrics before any extension is interpreted.

## Repository principles

- Replication claims require a table-level evidence trail.
- Missing proprietary or author-supplied data are reported, not silently replaced.
- Every derived dataset has a schema, checksum, provenance record, and transformation log.
- Statistical significance is reported together with economic magnitude and uncertainty.
- Regime definitions are explicit and deterministic in the main analysis.
- No machine-learning method is required or introduced by default.
- The extension is falsifiable. A failure to reject stability is a valid result.

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
python -m pytest
```

Data acquisition is intentionally disabled until the source licence and exact variable definition have been recorded in `research/data_access_matrix.csv`. See `docs/DATA_ACQUISITION.md` for source-by-source acquisition and redistribution guidance.

## Quality gates

```bash
poetry check
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests scripts
poetry run python scripts/verify_title.py
poetry run srar release-audit
poetry run pytest
```

The test command enforces a minimum 95 percent coverage floor. The GitHub Actions workflow runs the same gates on pushes and pull requests to `main` and `develop`.

## Main commands

```bash
poetry run srar validate-config --config configs/baseline.yaml
poetry run srar show-milestones
poetry run srar validate-data --registry configs/data_sources.yaml
poetry run srar estimate-rate-innovation --config configs/baseline.yaml
poetry run srar run-baseline --config configs/baseline.yaml
poetry run srar run-regimes --config configs/regimes.yaml
poetry run srar build-report --config configs/reporting.yaml
poetry run srar release-audit
```

Most commands are scaffolded and fail with an explicit `NotImplementedError` until the corresponding milestone acceptance gates have been completed.

## Repository map

- `src/short_rate_anomaly_regimes/`: typed Python package for configuration, data validation, factor construction, estimators, provenance, and reporting.
- `tests/`: focused unit tests for currently implemented behavior.
- `configs/`: declarative baseline, source-registry, regime, extension, and reporting configuration.
- `docs/`: reviewer-facing data policy and replication status.
- `research/`: research design, assumption map, data-access matrix, milestones, and replication protocol.
- `data/`, `artifacts/`, `reports/generated/`, and `paper/build/`: ignored output locations with tracked placeholders only.
- `artifacts/release/`: generated source-release assets, including SBOM, sanitized environment manifest, checksums, archive manifest, and source archive.
- `paper/`: manuscript source, bibliography, and the canonical compiled PDF at `paper/manuscript.pdf`.

## Required reading order

1. `research/research_design.md`
2. `research/claim_assumption_map.md`
3. `research/milestones.md`
4. `research/replication_protocol.md`

## Expected outputs

- immutable raw-data manifests;
- validated monthly factor and portfolio panels;
- rate-innovation diagnostics;
- baseline time-series and cross-sectional tables;
- a table-by-table replication audit;
- regime-stability tests;
- monetary-policy and information-shock decompositions;
- out-of-sample and weak-factor diagnostics;
- a reproducible manuscript and replication report.

## Citation

The baseline paper is

Maio, Paulo F., and Pedro Santa-Clara. 2017. Short-Term Interest Rates and Stock Market Anomalies. *Journal of Financial and Quantitative Analysis* 52(3), 927–961. DOI 10.1017/S002210901700028X.

See `CITATION.cff` for repository citation metadata.

## Contributing and security

See `CONTRIBUTING.md` for development rules and `SECURITY.md` for private reporting and restricted-data handling.
