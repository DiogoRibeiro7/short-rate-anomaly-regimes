# Manuscript Change Plan

Review pass: structural rewrite.

## Section Map

| Current section | Decision | Destination | Reason | Evidence dependency |
|---|---|---|---|---|
| Abstract | Rewrite | Abstract | Replace repository-status abstract with preliminary research-design abstract | Current audit and source-access status |
| Introduction | Rewrite | Introduction | Center the economic question and replication-first extension | Research design and article target |
| Contribution | Merge | Introduction and discussion | Convert protocol contributions into paper aims | Replication protocol |
| Model | Rewrite | Original framework and economic mechanism; Econometric methods | Separate economic mechanism from estimator mechanics | Baseline config and pending article audit |
| Evidence | Move | Appendices | Main-text path table read like repository documentation | Data access matrix and release gate |
| Replication Design | Rewrite | Data and replication design | Keep table-level discipline but remove operational prose | Replication protocol and table target manifest |
| Baseline Replication Status | Rewrite | Baseline replication results | Keep pending-result status without reporting unavailable estimates | Table replication audit |
| Robustness And Weak-Factor Design | Rewrite | Robustness and weak-factor diagnostics | Convert scaffold context into formal diagnostic design | Statistical protocol |
| Temporal Extension | Merge | Temporal and monetary-regime evidence | Combine with regime section for a coherent extension section | Extensions config |
| Monetary Regimes | Merge | Temporal and monetary-regime evidence | Avoid short standalone outline section | Regime config and statistical protocol |
| Policy and Information Shocks | Rewrite | Policy and information shock decomposition | Preserve identification boundary while marking data gate | Extensions config and shock report gate |
| Out Of Sample Evaluation | Move | Detailed out-of-sample design appendix | Useful design detail, but not central until results exist | Extensions config |
| Interpretation | Merge | Discussion and limitations | Interpretive categories belong with limitations until results exist | Claim-assumption map |
| Limitations | Merge | Discussion and limitations | Consolidate input, interpretive, and econometric limits | Data access matrix and statistical protocol |
| Reproducibility Statement | Move | Data access and reproducibility appendix | Keep file paths and release mechanics out of main text | Release artifacts |
| Data Access Statement | Move | Data access and reproducibility appendix | Same operational detail as reproducibility section | Data access matrix |
| Hypothesis Registry | Move | Hypothesis registry appendix | Registry is important but appendix-level in current draft | Hypothesis registry |
| Robustness Appendix | Merge | Additional diagnostics appendix | Keep pending diagnostic outputs in appendix | Generated reports pending |
| Table-Level Replication Appendix | Rewrite | Table-level replication audit appendix | Keep audit rules and status in appendix | Table replication audit |
| Conclusion | Rewrite | Conclusion | Conclude the preliminary design without empirical claims | Current evidence gate |

## Structural Decisions

- Main text now has eleven sections before appendices.
- Main-text tables with file paths were removed.
- Repository mechanics, release artifacts, hashes, and data-access details were moved to appendices or referenced generically.
- Prompt-like reporting template sentences were converted into formal pending-result paragraphs with hidden empirical-context declarations.
- The manuscript remains explicitly labelled as a preliminary research design.

## Unresolved Items

- Exact article and supplement reconstruction still requires a dedicated framework audit.
- Literature review remains skeletal pending verified primary sources.
- Baseline, robustness, temporal, regime, shock, and out-of-sample results remain gated by missing empirical artifacts.
