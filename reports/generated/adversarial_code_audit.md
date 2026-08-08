# Adversarial Code Audit

## Release Verdict

Source-only release is permitted when no critical restricted-path issue is present. Empirical-results release is blocked while major missing-input issues remain.

Required-input presence is evaluated against the membership of the source archive that this audit writes, not against the working tree it runs in. A file that exists locally but is ignored, or excluded from the archive, counts as absent, and a directory carrying only a `.gitkeep` placeholder counts as empty.

## Findings

### MAJOR: empirical_artifacts_missing

- Location: `data/processed/factors/short_rate_innovations_baseline.parquet, data/processed/extension/monthly_panel.parquet, artifacts/estimates/time_series, artifacts/estimates/cross_section, artifacts/tables/time_series`
- Failure mechanism: The distributed archive does not carry these generated artifacts, so a recipient cannot reproduce manuscript tables or extension claims from the archive alone.
- Affected results: source-only release gate or empirical-result release gate.
- Minimal reproduction: run `poetry run srar release-audit`.
- Required fix: Record redistribution rights and ship the generated artifacts, or release source-only and direct recipients to the `make reproduce` rebuild path.

## Targeted Checks

- Restricted paths are detected before release.
- Checksum records exclude prompt files, restricted sources, local catalogs, and temporary artifacts.
- Dependency disclosure is generated from `poetry.lock`.
- Required empirical inputs are resolved against distributed archive membership, so a locally generated but undistributed artifact cannot satisfy the gate.
- The rebuild path is checked as shipped files plus a declared `make reproduce` entry point, and is reported separately from whether the artifacts themselves ship.
- Empirical commands remain blocked rather than rendering selective placeholder tables.
