.PHONY: install validate-metadata lint typecheck test check clean milestones

install:
	poetry install

validate-metadata:
	poetry check

lint:
	poetry run ruff check .
	poetry run ruff format --check .

typecheck:
	poetry run mypy src tests

test:
	poetry run pytest

check: validate-metadata lint typecheck test

milestones:
	poetry run srar show-milestones

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist
