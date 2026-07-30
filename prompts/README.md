# Coding Agent Prompts

Run the prompts in numeric order. Each prompt is a self-contained implementation contract, but no prompt may bypass an earlier acceptance gate.

The agent must update

- `research/decision_log.md` for empirical choices;
- `research/data_access_matrix.csv` for source status;
- `research/table_target_manifest.csv` for replication targets;
- tests and documentation in the same change as code.

A prompt is complete only when its commands pass from a clean checkout and its listed artefacts exist.
