# Master Execution Prompt

You are implementing a scientific replication and extension repository called `short-rate-anomaly-regimes`.

## Mission

Reproduce Maio and Santa-Clara's published short-rate anomaly results as exactly as the available legal inputs permit. Then test temporal stability, monetary-regime dependence, weak-factor sensitivity, and the decomposition of aggregate rate innovations into policy and central-bank information components.

## Non-negotiable rules

1. Work in English.
2. Use Python 3.12, Poetry, Ruff, mypy strict mode, pytest, and pre-commit.
3. Preserve the existing architecture unless a change is justified in `research/decision_log.md`.
4. Never call a reconstruction an exact replication.
5. Never invent article definitions. Mark them `BLOCKED_ARTICLE_EXTRACTION`.
6. Never commit copyrighted article files, restricted CRSP or Compustat data, credentials, or author data without redistribution permission.
7. Every raw file is immutable and receives a SHA-256 provenance record.
8. Every processed dataset has a schema, unit declaration, date convention, and validation report.
9. Every numerical paper result is generated from code and linked to an artefact.
10. Do not introduce machine learning. Use transparent statistical and econometric models.
11. Do not optimise specifications for significance.
12. Preserve negative and null results.
13. Use deterministic seeds where simulation or bootstrap is involved.
14. Avoid causal monetary-policy language unless an explicit identification design supports it.

## Execution protocol

For each milestone

1. read the milestone contract in `research/milestones.md`;
2. inspect all existing code and tests;
3. create an implementation checklist in the pull request description or local work log;
4. implement the smallest coherent vertical slice;
5. add unit, integration, and simulation tests as applicable;
6. run `poetry run ruff check .`, `poetry run ruff format --check .`, `poetry run mypy src tests`, and `poetry run pytest`;
7. generate the required artefacts;
8. update the decision log, access matrix, and target manifest;
9. stop if the acceptance gate fails;
10. report blockers with exact missing evidence rather than guessing.

## Scientific output rules

- Report sample size for every estimate.
- Report units beside every factor and return.
- Report confidence intervals, not only significance stars.
- Report individual pricing errors as well as aggregate fit.
- Compare models on the same dates and test assets.
- Keep confirmatory and exploratory analyses separate.
- Apply the registered multiple-testing rule.
- Treat weak-factor diagnostics as central, not optional.
- Store tables in CSV and Parquet before rendering LaTeX.
- Store figures in PDF and PNG with the generating data.

## Definition of completion

The repository is complete only after Milestone 14 passes. A partially accessible original dataset is not a reason to stop the project, but it changes the relevant outputs from strict replication to documented reconstruction.
