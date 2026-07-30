# Validation

Latest validation was performed on 30 July 2026 from the repository checkout on Windows with Python 3.13.5.

## Passed checks

- `poetry check`
- `poetry run ruff check .`
- `poetry run ruff format --check .`
- `poetry run mypy src tests scripts`
- `poetry run python scripts/verify_title.py`
- `poetry run srar validate-config --config configs/baseline.yaml`
- `poetry run srar validate-config --config configs/extensions.yaml`
- `poetry run srar validate-config --config configs/regimes.yaml`
- `poetry run srar validate-config --config configs/reporting.yaml`
- `poetry run srar validate-data --registry configs/data_sources.yaml`
- `poetry run srar acquire-data --registry configs/data_sources.yaml`
- `poetry run srar build-catalog --registry configs/data_sources.yaml`
- `poetry run pytest` with `--cov-fail-under=95`
- `poetry run pre-commit run --all-files`

The current test suite contains 124 tests. All 124 passed. The measured scaffold coverage is 96.23 percent because milestone-specific estimators and data clients are intentionally represented by explicit gates until their evidence inputs are completed.

## Current quality status

- The package metadata passes `poetry check`.
- The dependency graph is locked in `poetry.lock`.
- Ruff linting and formatting pass under the repository configuration.
- Strict mypy passes for `src` and `tests`, with an explicit override for untyped `statsmodels` imports.
- Pytest imports from the `src` layout without requiring a manual `PYTHONPATH`.
- GitHub Actions runs the same metadata, lint, format, type-check, and test gates on `main` and `develop`.
- `make check` now includes YAML project-config validation and source-registry validation.
- `make check` now exercises data-acquisition dry-run planning and DuckDB catalog creation.
- `make env-manifest` writes `artifacts/environment/manifest.json` with Python, OS, package, BLAS, Git, and config-hash metadata.
- Portfolio parser, validation, manifest, and synthetic reconstruction tests cover the Milestone 4 test-asset assembly layer.

## Scientific status

No empirical replication result has been produced. The final article and supplement are present locally and hashed, but strict replication remains blocked until exact source versions and required raw inputs are legally obtained and registered. The codebase must use the documented reconstruction label whenever an original input cannot be obtained.
