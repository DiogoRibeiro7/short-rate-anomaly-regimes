# Adversarial Code Audit

## Release Verdict

Source-only release is permitted when no critical restricted-path issue is present. Empirical-results release is blocked while major missing-input issues remain.

## Findings

### MAJOR: empirical_artifacts_missing

- Location: `data/processed/factors/short_rate_factors.parquet, data/processed/extension/monthly_panel.parquet`
- Failure mechanism: The repository cannot reproduce manuscript tables or extension claims from a fresh checkout with the current public inputs.
- Affected results: source-only release gate or empirical-result release gate.
- Minimal reproduction: run `poetry run srar release-audit`.
- Required fix: Freeze source definitions, register permitted data, generate the baseline and extension artifacts, and rerun release-audit.

## Targeted Checks

- Restricted paths are detected before release.
- Checksum records exclude prompt files, restricted sources, local catalogs, and temporary artifacts.
- Dependency disclosure is generated from `poetry.lock`.
- Empirical commands remain blocked rather than rendering selective placeholder tables.
