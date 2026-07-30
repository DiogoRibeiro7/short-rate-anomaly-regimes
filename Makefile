.PHONY: install validate-metadata lint typecheck manuscript-check test check clean milestones

install:
	poetry install

validate-metadata:
	poetry check

lint:
	poetry run ruff check .
	poetry run ruff format --check .

typecheck:
	poetry run mypy src tests scripts

manuscript-check:
	poetry run python scripts/verify_title.py

test:
	poetry run pytest

check: validate-metadata lint typecheck manuscript-check test

milestones:
	poetry run srar show-milestones

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist
