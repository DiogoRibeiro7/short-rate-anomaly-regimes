# Decision Log

Record every decision that can alter an empirical result.

| Date | Decision | Alternatives | Evidence | Consequence | Approved by |
|---|---|---|---|---|---|
| 2026-07-27 | Separate strict replication from documented reconstruction | One mixed pipeline | Missing original portfolio inputs can otherwise be hidden | Every output carries a replication mode and status | Research lead |
| 2026-07-27 | Use deterministic monetary regimes as the primary extension | Hidden Markov regimes | Direct economic interpretation and reproducibility | Estimated regimes may appear only as robustness analysis | Research lead |
| 2026-07-30 | Mark Milestone 0 as blocked pending private article files | Infer methods from abstract or working paper | Final article PDF and supplement are not present under `references/private` | Strict replication cannot proceed; only documented reconstruction scaffolding may continue | Research lead |
| 2026-07-30 | Treat repository-foundation checks as part of the default quality gate | Leave config and registry validation as ad hoc CLI checks | Milestone 1 requires the scaffold to be executable, typed, tested, and reproducible before data work | `make check` now fails on invalid project YAML or source-registry metadata | Research lead |
