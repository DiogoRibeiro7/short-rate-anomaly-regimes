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

The current test suite contains 111 tests. All 111 passed. The measured scaffold coverage is 97.85 percent because milestone-specific estimators and data clients are intentionally represented by explicit stubs until their evidence gates are completed.

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

## Scientific status

No empirical replication result has been produced. Strict replication remains blocked until the final article and supplement are obtained legally, hashed, and extracted under Milestone 0. The codebase must use the documented reconstruction label whenever an original input cannot be obtained.
