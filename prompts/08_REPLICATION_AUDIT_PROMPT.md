# Replication Audit Prompt

Complete Milestone 7. Do not include regime or post-2013 results.

## Required work

1. Load the frozen table target manifest.
2. Compare each generated statistic with its published target using the predeclared tolerance.
3. Create one audit row per statistic with source locator, generated artefact, published value, replicated value, absolute difference, relative difference, status, and notes.
4. Investigate discrepancies in this order: unit, sample, date alignment, source vintage, portfolio ordering, missing values, estimator, covariance, rounding, software.
5. Re-estimate central results using an independent implementation or independent reviewer script.
6. Assign only the allowed labels.
7. Write a replication report that distinguishes inaccessible inputs from empirical contradiction.

## Report structure

- evidence availability;
- exact and reconstructed datasets;
- reproduced tables;
- approximate reproductions;
- blocked targets;
- contradicted targets;
- sources of numerical difference;
- baseline conclusion with scope limits.

## Prohibition

Do not call the article unreliable merely because proprietary data are inaccessible. Do not call a close substitute an exact replication.
