# Short Rate Factors Prompt

Complete Milestone 3 using the definitions frozen in Milestone 0.

## Baseline

1. Load the exact federal-funds and Treasury-bill monthly series.
2. Preserve source units and create explicit transformed columns.
3. Estimate the article's autoregression exactly, including intercept, lag count, sample, and residual alignment.
4. Name innovations by rate and method.
5. Align the market factor and risk-free return without look-ahead.
6. Reproduce article factor means, standard deviations, extrema, autocorrelations, and pairwise correlations.

## Diagnostics

- Ljung-Box residual tests at registered lags;
- ARCH-LM test;
- influence statistics and largest absolute residual months;
- recursive coefficient plot;
- known and unknown structural-break diagnostics;
- unit-root tests reported cautiously because the factor is an innovation, not because a test result selects the model.

## Alternative factors

Implement AR(2), local-level state-space, and identified surprise factors only in separate output namespaces. They must never overwrite the baseline AR(1) factor.

## Tests

- simulation recovery for AR parameters;
- exact residual timing test;
- unit-conversion test;
- no-look-ahead test;
- article-statistic tolerance test where targets are available.

## Outputs

Write factor panels, model parameters, diagnostics, and descriptive tables in Parquet, JSON, CSV, and LaTeX.
