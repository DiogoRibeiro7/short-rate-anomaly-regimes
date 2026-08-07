.PHONY: install validate-metadata lint typecheck manuscript-check manuscript-tables paper paper-clean config-check data-check provenance-check release-check test check clean milestones env-manifest

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

# Result tables are generated from the frozen artifacts, never transcribed. The
# drift guard in tests/test_manuscript_tables.py fails if the committed tables
# stop matching this output.
manuscript-tables:
	poetry run python scripts/build_manuscript_tables.py
	poetry run python scripts/build_manuscript_figures.py

# latexmk runs from paper/ so that \bibliography{references} resolves. Auxiliary
# files go to paper/build/ through -auxdir, which keeps the final PDF in paper/;
# -outdir would move the PDF as well. bibtex runs with paper/build/ as its
# working directory, so BIBINPUTS must name the parent directory for
# references.bib to be found; the trailing separator keeps the default search
# path in place.
paper: manuscript-tables manuscript-check
	cd paper && BIBINPUTS=".;..;" latexmk -pdf -interaction=nonstopmode -halt-on-error -auxdir=build manuscript.tex

paper-clean:
	cd paper && latexmk -C -auxdir=build

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

release-check:
	poetry run srar release-audit

test:
	poetry run pytest

check: validate-metadata lint typecheck manuscript-check config-check data-check provenance-check release-check test

milestones:
	poetry run srar show-milestones

env-manifest:
	poetry run srar environment-manifest --config configs/baseline.yaml --config configs/extensions.yaml --config configs/regimes.yaml --config configs/reporting.yaml --output artifacts/environment/manifest.json

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage build dist
