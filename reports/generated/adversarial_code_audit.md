# Adversarial Code Audit

## Release Verdict

Source-only release is permitted when no critical restricted-path issue is present. Empirical-results release is blocked while major missing-input issues remain.

## Findings

No critical or major release issue was detected.
## Targeted Checks

- Restricted paths are detected before release.
- Checksum records exclude prompt files, restricted sources, local catalogs, and temporary artifacts.
- Dependency disclosure is generated from `poetry.lock`.
- Empirical commands remain blocked rather than rendering selective placeholder tables.
