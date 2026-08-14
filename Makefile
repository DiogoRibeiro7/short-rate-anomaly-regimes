.PHONY: install validate-metadata lint typecheck manuscript-check manuscript-tables paper paper-clean config-check data-check provenance-check release-check test check clean milestones env-manifest reproduce reproduce-acquire reproduce-panels reproduce-estimates reproduce-extension reproduce-regimes reproduce-reports update-vintage update-vintage-short-rates update-vintage-french update-vintage-portfolios update-vintage-comparators

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
# Rebuild of the empirical artifacts, verified against the frozen vintage.
#
# The release archive ships source, configuration, the frozen source registry,
# and the result tables the manuscript cites. It does not ship raw or processed
# data panels or the first- and second-pass estimate stores, because their
# redistribution rights are unrecorded. `make reproduce` is the path from the
# archive to those artifacts. `poetry run srar release-audit` reports the two
# facts separately as `empirical_release` and `empirical_rebuild`.
#
# NETWORK: only reproduce-acquire reaches the internet, and it does not reach it
# at all once the frozen raw bytes are on disk. Every later stage reads the
# frozen files under data/raw and data/interim.
# SLOW: reproduce-estimates, reproduce-regimes. Budget hours, not minutes.
# The stages are ordered by dependency and are safe to run one at a time.
reproduce: reproduce-acquire reproduce-panels reproduce-estimates reproduce-extension reproduce-regimes reproduce-reports paper release-check

# NETWORK REQUIRED unless the frozen raw bytes are already under data/raw.
# VERIFICATION ONLY. Every provider URL here serves the current vintage, so this
# stage downloads each source, hashes it, and compares the digest against the
# raw_sha256 recorded in the shipped manifests under artifacts/provenance. A
# mismatch aborts the stage naming the series, both hashes, and what to do next;
# nothing is written and no recorded hash is changed. This stage can never move
# the archive onto a new vintage: only `make update-vintage` can, and `reproduce`
# never invokes it.
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
# of the full two-pass system, and run_useless_factor_bootstrap.py runs the
# article's own 5,000-replication procedure for each of the twenty-nine systems
# it prints an empirical p-value for. The bootstrap runs before the audit,
# because the audit reads its output to compare those published cells; without
# it they fall back to not attempted.
reproduce-estimates:
	poetry run python scripts/run_baseline_replication.py
	poetry run python scripts/run_useless_factor_bootstrap.py
	poetry run python scripts/run_risk_premium_decomposition.py
	poetry run python scripts/run_alternative_fit_metrics.py
	poetry run python scripts/run_zero_beta_second_pass.py
	poetry run python scripts/run_first_difference_factors.py
	poetry run python scripts/run_restricted_sample.py
	poetry run python scripts/run_covariance_representation.py
	poetry run python scripts/audit_published_targets.py
	poetry run python scripts/run_h1_materiality.py
	poetry run python scripts/run_weak_factor_diagnostics.py
	poetry run python scripts/run_h4c_precision.py

# Offline. Minutes. The out-of-sample falsification refits the two-pass system
# annually from 1999-12 and evaluates through the end of the panel.
reproduce-extension:
	poetry run python scripts/run_temporal_extension.py
	poetry run python scripts/run_out_of_sample.py

# Offline. SLOWEST stage: run_regime_equivalence.py bootstraps 10,000 draws per
# eligible regime, run_regime_interactions.py runs an exhaustive Bai-Perron
# break search at three boundary shifts, and analyse_regime_power.py simulates
# 2,000 replications at each of sixteen window lengths.
reproduce-regimes:
	poetry run python scripts/build_regime_panel.py
	poetry run python scripts/run_regime_equivalence.py
	poetry run python scripts/run_regime_interactions.py
	poetry run python scripts/analyse_regime_power.py

# Offline. Rewrites reports/generated/ from the rebuilt artifacts. The one
# `-` prefixed command exits non-zero by design: their gates are blocked by
# inputs this repository cannot obtain, and they write a blocked report saying
# so. The `-` keeps the rebuild going; it does not suppress a passing gate.
# audit-replication no longer needs one: it now writes the table-level audit
# from the cell-level comparison instead of raising once the estimates exist.
# build-report reads the other generated reports, so it runs last.
reproduce-reports:
	poetry run srar audit-replication
	poetry run srar robustness-diagnostics
	poetry run srar temporal-extension
	poetry run srar run-regimes --config configs/regimes.yaml
	-poetry run srar shock-decomposition
	poetry run srar out-of-sample
	poetry run srar build-report --config configs/reporting.yaml

# ---------------------------------------------------------------------------
# Moving the archive onto a NEW frozen vintage. THIS IS NOT PART OF `reproduce`.
#
# These are the only targets that may overwrite a recorded expected hash. They
# pass `--update-vintage`, which replaces the raw bytes under data/raw, rewrites
# the provenance manifests under artifacts/provenance, and therefore changes the
# inputs of every downstream estimate. The published results were produced from
# the vintage currently recorded; running these invalidates them until the whole
# of `make reproduce` has been re-run and the new vintage reported.
#
# Run one of these only when you intend to change the data, never to make a
# failing `reproduce-acquire` go away. A verification failure means the provider
# revised the series, and the fix for a reproduction is to obtain the frozen
# bytes (ALFRED for FRED, Internet Archive for the publication-era files; see
# docs/DATA_ACQUISITION.md), not to adopt the revision.
update-vintage: update-vintage-short-rates update-vintage-french update-vintage-portfolios update-vintage-comparators

update-vintage-short-rates:
	poetry run python scripts/acquire_short_rates.py --update-vintage

update-vintage-french:
	poetry run python scripts/acquire_french_factors.py --update-vintage

update-vintage-portfolios:
	poetry run python scripts/acquire_anomaly_portfolios.py --update-vintage

update-vintage-comparators:
	poetry run python scripts/acquire_comparator_factors.py --update-vintage
