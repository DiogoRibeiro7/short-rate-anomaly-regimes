# Contributing

This repository is a research codebase. Contributions should preserve a clear distinction between strict replication, documented reconstruction, and exploratory extension.

## Development Setup

```bash
poetry install
poetry run pre-commit install
cp .env.example .env
```

Do not put credentials, licensed source files, proprietary extracts, or generated empirical outputs under version control. Raw and derived data are intentionally ignored except for `.gitkeep` placeholders.

## Quality Gates

Run the full local check before opening or merging changes:

```bash
poetry run ruff check .
poetry run ruff format --check .
poetry run mypy src tests
poetry run pytest
```

For a quick non-Poetry smoke test from a source checkout:

```bash
python -m pytest
```

## Research Discipline

- Update `research/decision_log.md` for empirical choices.
- Update `research/data_access_matrix.csv` when a source status changes.
- Update `research/table_target_manifest.csv` when replication targets change.
- Keep tests and documentation in the same change as code.
- Label results as `documented_reconstruction` whenever original inputs are unavailable.

## Pull Requests

Pull requests should explain the research or engineering reason for the change, list validation commands, and call out any data-access or replication-status implications.
