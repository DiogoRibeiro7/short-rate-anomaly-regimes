.PHONY: install validate-metadata lint typecheck manuscript-check config-check data-check provenance-check test check clean milestones env-manifest

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
	poetry run python scripts/verify_manuscript.py

config-check:
	poetry run srar validate-config --config configs/baseline.yaml
	poetry run srar validate-config --config configs/extensions.yaml
	poetry run srar validate-config --config configs/regimes.yaml
	poetry run srar validate-config --config configs/reporting.yaml

data-check:
	poetry run srar validate-data --registry configs/data_sources.yaml

provenance-check:
	poetry run srar acquire-data --registry configs/data_sources.yaml
	poetry run srar build-catalog --registry configs/data_sources.yaml

test:
	poetry run pytest

check: validate-metadata lint typecheck manuscript-check config-check data-check provenance-check test

milestones:
	poetry run srar show-milestones

env-manifest:
	poetry run srar environment-manifest --config configs/baseline.yaml --config configs/extensions.yaml --config configs/regimes.yaml --config configs/reporting.yaml --output artifacts/environment/manifest.json

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist
