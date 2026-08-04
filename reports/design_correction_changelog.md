# Design-Correction Change Log

Milestone: Empirical Input Acquisition and Baseline Reconstruction, Task 1.
Date: 2026-07-31.
Status: applied before any data download. No empirical conclusion is recorded in
this document.

All eight corrections are applied. Each entry states what changed, where, and
what it now forbids.

## 1. Table 1 comparator roles

- Changed: the H1 row of Table 1 ("Replication target and economic hypotheses")
  in `paper/manuscript.tex` read "Improvement versus strongest comparator". It
  now reads "Improvement versus the ex ante CAPM comparator", with the
  interpretation rule "Economic thresholds required against CAPM; the strongest
  observed comparator is a secondary adversarial check".
- Also changed: the H1 row of the method-to-claim table already carried the
  correct wording and is unchanged; the two tables are now consistent.
- Effect: Table 1 no longer permits a reading in which the primary materiality
  benchmark is chosen after observing comparator RMSE.
- Unchanged and already correct: `research/comparator_model_registry.csv` marks
  `capm` as `primary` and `strongest_observed_non_short_rate` as
  `secondary_adversarial`; `research/economic_thresholds.md` fixes CAPM as the
  primary ex ante comparator.

## 2. H4 replaced by H4a, H4b, H4c

- Changed: the single confirmatory hypothesis H4 is removed and replaced by
  three separately classified confirmatory hypotheses.
  - `H4a` cross-sectional identification strength: beta-matrix rank,
    standardized rate-exposure dispersion, and the numerical spanning criterion.
  - `H4b` influence stability: leave-one-anomaly-family refits and standardized
    DFBETA influence on `lambda_rate`.
  - `H4c` fitted-premium precision: the joint-bootstrap interval for the
    rate-attributable fitted-premium spread.
- Files: `research/hypothesis_registry.csv` (one row replaced by three),
  `research/inference_contract.md`, `research/statistical_protocol.md`,
  `research/research_design.md`, `research/mechanism_hypothesis_map.md`,
  `research/weak_factor_registry.csv` (every diagnostic now carries a
  `hypothesis_id`), `research/manuscript_table_figure_map.csv`,
  `paper/manuscript.tex` (both hypothesis tables and the diagnostics paragraph).
- Multiplicity: all three remain inside the single confirmatory family
  `weak_factor_diagnostics`, Holm adjusted where a component gate produces a
  p-value.
- Effect: a weak-factor failure must now be reported with the reason. A factor
  that is well identified but imprecisely estimated is classified differently
  from one that is nearly spanned.

## 3. Numerical factor-spanning criterion

- Previous text: "the rate factor's residual standard deviation after projection
  on the other priced factors is below 10 percent of the raw rate-factor
  standard deviation". This left the regressor set, the sample, and the
  statistic undefined, and its implied bound (`R2_span > 0.99`) was effectively
  unreachable.
- New criterion, fixed in `research/inference_contract.md` and mirrored in
  `research/economic_thresholds.md` and `research/weak_factor_registry.csv`:
  - sample: the frozen common asset-date intersection of the pricing test;
  - dependent variable: the short-rate innovation entering the tested model;
  - regressors: a constant plus the registered non-short-rate comparator factors
    available on that intersection, in the fixed order
    `Mkt-RF, SMB, HML, UMD, RMW, CMA, LIQ, ME, IA, ROE`, with the executed list
    stored alongside the artifact;
  - estimator: OLS;
  - statistics: `R2_span` and `s_span = sd(residual)/sd(rate innovation)`, which
    satisfy `s_span = sqrt(1 - R2_span)`;
  - decision: pass when `R2_span <= 0.90`, equivalently
    `s_span >= sqrt(0.10) = 0.31622776601683794`, with the `R2_span` form
    authoritative and the residual cutoff stated as the exact square root
    rather than a decimal rounded below it;
  - secondary descriptive reporting: the same statistic against `Mkt-RF` alone.
- Both statistics are scale free, so the gate is invariant to rescaling the
  short-rate factor.

## 4. Equivalence-test rule

- Selected: **standard 5 percent TOST, implemented as inclusion of the two-sided
  90 percent joint-bootstrap percentile interval inside the declared bound.**
  Rule label: `tost_5pct_90pct_interval`.
- Rejected as the confirmatory rule: 95 percent confidence-set inclusion. It is
  retained only as a labelled robustness column,
  `strict_95pct_interval_sensitivity`, and may never be reported as the
  confirmatory equivalence test.
- Reason for the choice: 95 percent interval inclusion is an approximately 2.5
  percent one-sided procedure, so reporting it as a 5 percent equivalence test
  would misstate the size. The standard TOST implementation states its size
  correctly.
- Deliberate exception: H4c is a two-sided precision statement about a single
  estimand, not an equivalence test, so it keeps a 95 percent interval. The two
  levels are documented side by side in `research/bootstrap_contract.md` so they
  cannot be interchanged.
- Files: `research/inference_contract.md`, `research/bootstrap_contract.md`,
  `research/economic_thresholds.md`, `research/statistical_protocol.md`,
  `configs/regimes.yaml` (`equivalence_rule: tost_5pct_90pct_interval`,
  enforced by a `Literal` type in `src/short_rate_anomaly_regimes/config.py`),
  `paper/manuscript.tex`.

## 5. Regime labels removed from bootstrap stochastic variables

- Previous text: "factors, portfolio returns, rate series, and regime labels are
  resampled jointly by month".
- New text: the stochastic variables are the market factor, the comparator
  factors, the portfolio returns, and the short-rate level series. A regime
  label is a deterministic calendar function of the observation month, fixed in
  `research/regime_registry.csv`. Each resampled month carries its own frozen
  label as a fixed attribute; labels are never permuted, never drawn
  independently of the month, and never re-derived from the resampled ordering.
- Reason: resampling a known calendar fabricates uncertainty and can break the
  correspondence between an observation and its policy regime.
- Files: `research/inference_contract.md`, `research/bootstrap_contract.md`,
  `paper/manuscript.tex`.

## 6. Post-2022 regime split

- The single regime `inflation_tightening` (2022-03 onward) is split into two.
  - `inflation_tightening`: rapid policy tightening and the subsequent hold at
    the cycle peak.
  - `post_tightening_easing`: reduction from the cycle peak and the wind-down of
    balance-sheet reduction.
- Split boundary: the FOMC decision of 18 September 2024, which lowered the
  target range to 4-3/4 to 5 percent, recorded with its source URL in
  `research/regime_policy_sources.csv`.
- The primary regime system now contains six regimes.

## 7. Transition rule

- Primary rule: `first_full_month_after_policy_action`. A regime begins in the
  first calendar month lying entirely under the new policy stance; the month
  containing the policy action stays with the outgoing regime because it mixes
  both stances.
- Sensitivity rule: `whole_transition_month_belongs_to_new_regime`, the previous
  primary rule, preserved in full and never used for confirmatory
  classification.
- Every boundary is restated under both rules. `research/regime_registry.csv`
  now carries `start_month`/`end_month` (primary) and
  `sensitivity_start_month`/`sensitivity_end_month`, and
  `research/regime_policy_sources.csv` carries `primary_boundary_month` and
  `sensitivity_boundary_month`.

Frozen regime spans and month counts, both rules verified contiguous and
exhaustive over 1972-01 to the 2026-06 extension freeze month (654 months):

| Regime | Primary span | Obs. | Sensitivity span | Obs. |
|---|---|---|---|---|
| `conventional_pre_elb` | 1972-01 to 2008-12 | 444 | 1972-01 to 2008-11 | 443 |
| `elb_qe` | 2009-01 to 2015-12 | 84 | 2008-12 to 2015-11 | 84 |
| `normalisation` | 2016-01 to 2020-03 | 51 | 2015-12 to 2020-02 | 51 |
| `pandemic_elb_qe` | 2020-04 to 2022-03 | 24 | 2020-03 to 2022-02 | 24 |
| `inflation_tightening` | 2022-04 to 2024-09 | 30 | 2022-03 to 2024-08 | 30 |
| `post_tightening_easing` | 2024-10 to 2026-06 | 21 | 2024-09 to 2026-06 | 22 |

## 8. Frozen minimum regime-estimation eligibility

Fixed in `configs/regimes.yaml` under `regime_estimation_eligibility`, typed and
validated in `src/short_rate_anomaly_regimes/config.py`, and mirrored per regime
in `research/regime_registry.csv`.

| Tier | Condition | Permitted |
|---|---|---|
| `blocked_for_regime_specific_estimation_below_36_months` | months < 36 | pooled regime-interaction models only |
| `eligible_first_pass_with_short_sample_flag` | 36 <= months < 60 | regime-specific first-pass betas with a short-sample flag; standalone second pass blocked |
| `eligible_first_pass_and_standalone_second_pass` | months >= 60 and test assets >= 10 and beta rank equals the number of priced factors | regime-specific first pass and standalone regime second pass |

- The 36-month floor is the value already frozen as
  `minimum_regime_observations` in `configs/regimes.yaml`. It was **not**
  relaxed to accommodate the shorter regimes created by correction 6. The
  configuration model now fails validation if the two numbers diverge.
- Resulting eligibility under the primary rule: `conventional_pre_elb` and
  `elb_qe` carry full eligibility; `normalisation` is first-pass only with a
  short-sample flag; `pandemic_elb_qe`, `inflation_tightening`, and
  `post_tightening_easing` are below the floor and enter only pooled
  regime-interaction models.
- This resolves a pre-existing inconsistency: `pandemic_elb_qe` (24 months) was
  previously marked `eligible_with_short_sample_flag` for beta estimation while
  the same configuration file declared a 36-month minimum.
- Declared mitigation, fixed before estimation: `post_pandemic_cycle_combined`
  combines `inflation_tightening` and `post_tightening_easing` (2022-04 to
  2026-06, 51 months) and reaches the first-pass tier with a short-sample flag.
  It is registered as `declared_combination_sensitivity` and may not be selected
  after inspecting results.

## Consequence for the milestone

Correction 8 narrows what H3 can deliver. Under the frozen floors, standalone
regime-specific second-pass estimation is available for two of the six primary
regimes. Regime evidence for the four remaining regimes is restricted to pooled
regime-interaction models and the declared combination. This constraint is
recorded here before any data acquisition so that it cannot later be presented
as a result-driven design choice.

## Verification

- `configs/regimes.yaml` loads and validates under the extended Pydantic model.
- Regime spans were checked programmatically for contiguity, non-overlap, and
  exhaustive coverage of 1972-01 to 2026-06 under both transition rules.
- No bare `H4` identifier remains in `research/` or `paper/` outside the
  explanatory sentence in `research/inference_contract.md`.
