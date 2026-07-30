# Repository Foundation Prompt

Complete Milestone 1.

## Required work

1. Make `poetry install` succeed on Python 3.12.
2. Add `.github/workflows/ci.yml` with lint, format, mypy, and pytest jobs.
3. Expand Pydantic schemas to validate every baseline, regime, extension, source, and reporting field. Reject unknown fields except where a source record explicitly allows provider metadata.
4. Add a central seed utility and tests for deterministic bootstrap draws.
5. Add structured logging with run ID, config checksum, git commit, and timestamp.
6. Add an environment manifest command that records Python, OS, package versions, BLAS information, git commit, dirty status, and config hashes.
7. Add a `py.typed` marker.
8. Add exception classes for configuration, data access, data validation, replication block, and estimation failures.
9. Ensure notebooks are not required for any pipeline step.

## Acceptance commands

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
poetry run srar validate-config --config configs/baseline.yaml
poetry run srar validate-data --registry configs/data_sources.yaml
```

All commands must pass from a clean clone.
