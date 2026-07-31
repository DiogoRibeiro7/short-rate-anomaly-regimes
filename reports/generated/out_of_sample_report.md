# Out-of-Sample Falsification Report

Verdict: `blocked_missing_input`

Out-of-sample falsification is blocked until baseline factors, compatible portfolio panels, and temporal-extension outputs exist. The refit schedule is frozen before evaluation and must not be tuned after test errors are seen.

Missing inputs:
- `data/processed/extension/monthly_panel.parquet`
- `data/processed/factors/short_rate_factors.parquet`