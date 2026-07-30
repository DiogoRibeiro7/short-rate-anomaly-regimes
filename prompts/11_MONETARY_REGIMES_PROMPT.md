# Monetary Regimes Prompt

Complete Milestone 10.

## Regime validation

Use the deterministic calendar in `configs/regimes.yaml` as a proposal, not unquestioned truth. Verify dates against official policy actions and record sources. Freeze the final regime table before estimation.

## Models

1. pooled constant-beta baseline;
2. pooled model with regime interactions in factor loadings;
3. cross-sectional pricing with regime-specific risk prices;
4. split-sample estimates when a regime has at least the declared minimum observations;
5. rolling estimates with confidence bands.

## Tests

- joint Wald tests for all regime interactions;
- Chow tests at known boundaries;
- Quandt-Andrews unknown-break tests;
- Bai-Perron multiple breaks with minimum segment length and penalty rule;
- CUSUM and recursive residual tests;
- plus and minus three-month boundary sensitivity;
- Holm correction for the registered family.

## Interpretation

A significant regime interaction indicates parameter instability, not automatically a change caused by monetary policy. Compare estimated unknown breaks with declared policy boundaries and recessions without forcing alignment.

## Outputs

Produce a regime table, coefficient panels, break-date plots, rolling beta plots, cross-sectional error comparisons, and a concise stability verdict.
