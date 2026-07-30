# Decision Log

Record every decision that can alter an empirical result.

| Date | Decision | Alternatives | Evidence | Consequence | Approved by |
|---|---|---|---|---|---|
| 2026-07-27 | Separate strict replication from documented reconstruction | One mixed pipeline | Missing original portfolio inputs can otherwise be hidden | Every output carries a replication mode and status | Research lead |
| 2026-07-27 | Use deterministic monetary regimes as the primary extension | Hidden Markov regimes | Direct economic interpretation and reproducibility | Estimated regimes may appear only as robustness analysis | Research lead |
| 2026-07-30 | Mark Milestone 0 as blocked pending private article files | Infer methods from abstract or working paper | Final article PDF and supplement are not present under `references/private` | Strict replication cannot proceed; only documented reconstruction scaffolding may continue | Research lead |
| 2026-07-30 | Treat repository-foundation checks as part of the default quality gate | Leave config and registry validation as ad hoc CLI checks | Milestone 1 requires the scaffold to be executable, typed, tested, and reproducible before data work | `make check` now fails on invalid project YAML or source-registry metadata | Research lead |
| 2026-07-30 | Implement data-provenance machinery without live acquisition | Download candidate public data before final evidence freeze | Milestone 0 has not frozen exact article source definitions | Public downloaders, manual registration, and catalog creation are available; current required sources remain explicitly blocked or missing | Research lead |
| 2026-07-30 | Record local final-article PDF while keeping strict replication blocked | Treat article PDF alone as a complete evidence freeze | Publisher supplement / Internet Appendix remains unavailable locally | Main article methods and tables are extracted; strict replication still requires supplement extraction | Research lead |
| 2026-07-30 | Mark publication-document evidence pack complete | Keep supplement as a blocking missing file | Publisher supplement ZIP was supplied locally and hashed | Table targets now include article Tables 1-9 and Appendix Tables A.1-A.14; remaining blockers move to source versions and data acquisition | Research lead |
| 2026-07-30 | Implement short-rate factor builders without fabricating raw inputs | Generate article factor outputs from candidate online series | Raw FFR and Treasury-bill files have not been acquired or registered with immutable provenance | Baseline and alternative factor construction is tested; CLI reports missing raw inputs until data provenance is complete | Research lead |
