# Adversarial Audit and Release Prompt

Complete Milestone 14.

## Independent code audit

Use `prompts/90_ADVERSARIAL_CODE_REVIEW.md`. Search for hidden state, silent coercion, unit errors, date misalignment, look-ahead, mutable raw files, incorrect HAC covariance, unstable matrix inversion, and untested branches.

## Independent econometric audit

Use `prompts/91_ADVERSARIAL_ECONOMETRIC_REVIEW.md`. Attempt to invalidate identification, factor strength, cross-sectional inference, structural-break conclusions, and out-of-sample claims.

## Clean-room reproduction

Build the project from a fresh clone and empty data directory. Acquire only public data automatically. Register restricted data manually. Run all permitted pipelines and compare checksums.

## Release hygiene

- remove copyrighted and restricted data;
- remove credentials and local paths;
- produce a software bill of materials;
- include source and artefact checksums;
- pin the Poetry lock file;
- create release notes listing exact, approximate, blocked, and contradicted results;
- archive code and public processed data only when licences permit.

## Final gate

Do not release with a critical issue. Major unresolved issues must be prominent in the README, manuscript limitations, and release notes.
