# Manuscript Prompt

Complete Milestone 13 after empirical artefacts are frozen.

## Title

Use `Short Term Interest Rate Innovations Across Monetary Regimes`.

Do not use a question mark or colon in the paper title.

## Writing rules

- Cite the original article as the starting point and contribution being extended.
- Distinguish exact replication, approximate reconstruction, and new extension evidence.
- State all unavailable inputs plainly.
- Describe the model mathematically before discussing results.
- Avoid adversarial language and claims of error when the contribution is a limitation or extension.
- Avoid causal language for AR innovations.
- Report null results and instability.
- Keep literature claims tied to references.
- Generate every number and table from repository artefacts.

## Required sections

Use `research/paper_outline.md`. Add a reproducibility statement, data access statement, hypothesis registry, robustness appendix, and table-level replication appendix.

## Automated checks

Create a script that scans manuscript numeric tokens and verifies that declared results have an artefact mapping. Check that the title contains neither `?` nor `:`. Check that words such as `cause`, `effect`, and `policy shock` occur only in approved identification sections or citations.
