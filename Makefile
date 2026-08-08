.PHONY: install validate-metadata lint typecheck manuscript-check manuscript-tables paper paper-clean config-check data-check provenance-check release-check test check clean milestones env-manifest reproduce reproduce-acquire reproduce-panels reproduce-estimates reproduce-extension reproduce-regimes reproduce-reports

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

# ---------------------------------------------------------------------------
# Deterministic rebuild of the empirical artifacts.
#
# The release archive ships source, configuration, the frozen source registry,
# and the result tables the manuscript cites. It does not ship raw or processed
# data panels or the first- and second-pass estimate stores, because their
# redistribution rights are unrecorded. `make reproduce` is the path from the
# archive to those artifacts. `poetry run srar release-audit` reports the two
# facts separately as `empirical_release` and `empirical_rebuild`.
#
# NETWORK: only reproduce-acquire reaches the internet. Every later stage reads
# the frozen files it wrote under data/raw and data/interim.
# SLOW: reproduce-estimates, reproduce-regimes. Budget hours, not minutes.
# The stages are ordered by dependency and are safe to run one at a time.
reproduce: reproduce-acquire reproduce-panels reproduce-estimates reproduce-extension reproduce-regimes reproduce-reports paper release-check

# NETWORK REQUIRED. Downloads the frozen vintages recorded in
# configs/data_sources.yaml: FRED short rates, the Ken French publication-era
# and current archives, the global-q anomaly deciles and q-factors, and the
# Pastor-Stambaugh liquidity series. Raw bytes are written once; a provider
# revision makes a re-download fail rather than silently overwrite, so delete
# data/raw and data/interim before re-acquiring against a new vintage.
reproduce-acquire:
	poetry run python scripts/acquire_short_rates.py
	poetry run python scripts/acquire_french_factors.py
	poetry run python scripts/acquire_anomaly_portfolios.py
	poetry run python scripts/acquire_comparator_factors.py

# Offline. Audits the acquired series, reconstructs the AR(1) short-rate
# innovations, and builds the baseline, comparator, and extension panels.
# Minutes at most.
reproduce-panels:
	poetry run python scripts/audit_rate_aggregation.py
	poetry run python scripts/audit_portfolio_source_compatibility.py
	poetry run python scripts/reconstruct_rate_innovations.py
	poetry run python scripts/build_baseline_panel.py
	poetry run python scripts/build_comparator_panel.py
	poetry run python scripts/build_extension_panels.py

# Offline. SLOW: run_h4c_precision.py runs a 10,000-draw moving-block bootstrap
# of the full two-pass system.
reproduce-estimates:
	poetry run python scripts/run_baseline_replication.py
	poetry run python scripts/audit_published_targets.py
	poetry run python scripts/run_h1_materiality.py
	poetry run python scripts/run_weak_factor_diagnostics.py
	poetry run python scripts/run_h4c_precision.py

# Offline. Minutes.
reproduce-extension:
	poetry run python scripts/run_temporal_extension.py

# Offline. SLOWEST stage: run_regime_equivalence.py bootstraps 10,000 draws per
# eligible regime, run_regime_interactions.py runs an exhaustive Bai-Perron
# break search at three boundary shifts, and analyse_regime_power.py simulates
# 2,000 replications at each of sixteen window lengths.
reproduce-regimes:
	poetry run python scripts/build_regime_panel.py
	poetry run python scripts/run_regime_equivalence.py
	poetry run python scripts/run_regime_interactions.py
	poetry run python scripts/analyse_regime_power.py

# Offline. Rewrites reports/generated/ from the rebuilt artifacts. The three
# `-` prefixed commands exit non-zero by design: their gates are blocked by
# inputs this repository cannot obtain, and they write a blocked report saying
# so. The `-` keeps the rebuild going; it does not suppress a passing gate.
# build-report reads the other generated reports, so it runs last.
reproduce-reports:
	-poetry run srar audit-replication
	poetry run srar robustness-diagnostics
	poetry run srar temporal-extension
	poetry run srar run-regimes --config configs/regimes.yaml
	-poetry run srar shock-decomposition
	-poetry run srar out-of-sample
	poetry run srar build-report --config configs/reporting.yaml
