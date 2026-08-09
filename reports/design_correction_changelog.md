# Design-Correction Change Log

Milestone: Empirical Input Acquisition and Baseline Reconstruction, Task 1.
Date: 2026-07-31.
Status: applied before any data download. No empirical conclusion is recorded in
this document.

All eight corrections are applied. Each entry states what changed, where, and
what it now forbids.

Three further corrections, numbers 9 to 11, were applied later and after
estimation. They are appended at the end of this document with their own dates
and their own post-hoc disclosures, and they are the only entries here that were
not settled before data acquisition. Corrections 1 to 8 below are the record as
of 2026-07-31 and are not restated to match them; where correction 8 and
correction 9 disagree, correction 9 is the current configuration. Correction 11
retracts the *reason* correction 9 gave for its change while retaining the change
itself; the floor it set has never moved.

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

## 9. Standalone-second-pass floor raised from 60 to 72 months

Date: 2026-08-06. Milestone 10. Applied after estimation, with the binding
outcome already known, so this is not a threshold frozen before estimation. It
tightens the floor and changes no reported result; no floor has been relaxed at
any point.

- Changed: `minimum_months_for_standalone_second_pass` in `configs/regimes.yaml`
  from 60 to 72, with `short_sample_flag_band_months` moving from `[36, 59]` to
  `[36, 71]` and the tier conditions restated accordingly. The configuration
  validator requires the band to end one month below the floor, so the two move
  together and cannot diverge.
- Also changed, as dependent records only: the `second_pass_eligibility` tier
  label in `research/regime_registry.csv`, the eligibility sentence in
  `research/statistical_protocol.md`, and the floor references in
  `reports/regime_eligibility_power_analysis.md` and
  `reports/monetary_regime_report.md`.
- Reason **as originally stated, and wrong**: "the standalone second pass inverts
  a residual covariance estimated from T months for N test assets, which does not
  exist unless T is greater than N." See the amendment below. The corrected
  reason is that below T = N + 1 the residual covariance is rank deficient and
  this implementation refused to build it, so the tier authorised an estimate the
  code would not produce. 72 is the shortest window on the simulated sweep at
  which that covariance is of full rank, recorded as
  `reading_criteria.feasible_shanken_covariance_full_rank.joint_70_portfolio` in
  `artifacts/diagnostics/regime_eligibility_power.json`, with the exact minimum
  of 71 recorded alongside it as `joint_exact_minimum_months`.
- Effect: no registered regime changes tier. `conventional_pre_elb` has 444
  months and `elb_qe` 84, both eligible before and after; the next longest
  regime is `normalisation` at 51, and no registered regime lies in the vacated
  `[60, 71]` band. No reported result moves.
- What it now forbids: a regime can no longer reach the
  `eligible_first_pass_and_standalone_second_pass` tier at a length where the
  residual covariance of the confirmatory system is rank deficient, so that its
  Shanken standard errors rest on a singular estimate and the degrees of freedom
  of its chi-square overstate what that test measures.
- Superseded above: the tier table in correction 8 records the 36/60 boundaries
  that were frozen on 2026-07-31. That table is left as the record of what
  correction 8 did and is not the current configuration.

## 10. First-pass beta noise reported as a reliability ratio, on the correct variance

Date: 2026-08-09. Applied after estimation, in response to external review. It
corrects a reported statistic and changes no threshold, config, contract, or
registry entry. Every criterion crossing on the power sweep is unchanged.

- Changed: `first_pass_beta_noise_shares` in `scripts/analyse_regime_power.py`,
  now `first_pass_beta_reliability`. The old helper computed the mean
  *individual* first-pass sampling variance of a loading,
  `mean_i(sigma_ii) * [Sigma_f^-1]_kk / T`, and divided it by the observed
  cross-sectional variance of the estimated loadings. That ratio is not the
  estimation-error contribution to cross-sectional dispersion, because first-pass
  errors are correlated across portfolios whenever first-pass residuals are. For
  factor `k` the error vector has covariance
  `[Sigma_f^-1]_kk / T * Sigma_eps`, so its expected cross-sectional variance,
  under the `ddof=1` convention the observed variance uses, is
  `[Sigma_f^-1]_kk / (T (N - 1)) * tr(M_N Sigma_eps)` with `M_N = I - 11'/N`.
  Expanding the trace gives `mean(diagonal) - mean(off-diagonal)`: the diagonal-
  only version drops the second term and overstates the noise whenever residuals
  are on average positively correlated, because the common component of the
  estimation error shifts the cross-sectional mean of the loadings rather than
  their spread. On the 70-portfolio calibration the mean off-diagonal residual
  covariance is 0.388 against a mean residual variance of 4.929.
- Also changed, as reporting: the statistic is now published as a **reliability
  ratio**, signal over observed, with the noise share carried alongside as its
  explicit complement, so the two cannot be confused. The mean individual
  sampling variance is retained under
  `mean_individual_beta_sampling_variance`, in squared-loading units, labelled so
  it cannot be read as a share of dispersion. The diagnostic key
  `first_pass_beta_noise_share_at_calibration_length` is replaced by
  `first_pass_beta_reliability_at_calibration_length`.
- Effect on reported numbers: at the 648-month calibration length the noise share
  of the cross-sectional dispersion of `beta_rate` falls from 66.7 to 61.4
  percent, a reliability ratio of 0.386; for `beta_market` it falls from 2.9 to
  2.7 percent, a reliability ratio of 0.973. The direction of the finding is
  unchanged: the rate cross-section is still majority estimation error and the
  market cross-section is still almost entirely genuine dispersion. Updated in
  `reports/regime_eligibility_power_analysis.md` and
  `reports/monetary_regime_report.md`.
- Also corrected, separately: the claim that the errors-in-variables attenuation
  "does not go away with sample size". Under the stationary process simulated
  here the estimation-error term carries an explicit `1/T` and vanishes
  asymptotically. The supportable statement, now used in both reports, is that it
  remains economically large at every sample length considered here.
- What it now forbids: reporting an average individual sampling variance as a
  share of cross-sectional dispersion. `cross_sectional_residual_dispersion` is a
  named helper with its own tests, and
  `tests/test_regime_power.py` pins the corrected formula against an independent
  Monte Carlo of the cross-sectional error variance, which the diagonal-only
  quantity fails by a factor of about two on a positively correlated system.

## 11. The stated reason for correction 9 was false; the 72-month floor is retained

Date: 2026-08-09. Applied after estimation, in response to external review. It
corrects a justification and a guard in the code. It changes no threshold, no
config value, no contract, no registry entry, and no hypothesis outcome. The
baseline, both eligible regimes, the H3 classification, and the 26/44/0
per-portfolio decision categories are bit-identical before and after.

- **What was wrong.** Correction 9 justified raising the standalone floor with:
  "the standalone second pass inverts a residual covariance estimated from T
  months for N test assets, which does not exist unless T is greater than N."
  Both halves are false. `estimate_article_second_pass` never inverts
  `Sigma_eps`. The only genuine inverse it takes is of the `K x K` gram matrix
  `B'B`. `Sigma_eps` enters through `(B'B)^-1 B' Sigma_eps B (B'B)^-1`, which is
  reduced to `K x K` before any inverse, and through `M Sigma_eps M'`, which is
  read through a pseudo-inverse that is required whatever the rank of
  `Sigma_eps`, because `M = I - B(B'B)^-1 B'` has rank `N - K` and the
  pricing-error covariance is singular even on the full 504-month system. And a
  sample covariance from `T <= N` months does exist; it is rank deficient, not
  undefined. The 72-month floor was therefore an implementation restriction
  described as a mathematical necessity.
- **Changed in code.** `residual_covariance_from_first_pass` no longer refuses
  `T <= N`. It returns the rank-deficient covariance, and the rank reaches the
  reader: `estimate_article_second_pass` records
  `residual_covariance_rank`, `residual_covariance_rank_deficient`, and
  `months_minus_assets` on its diagnostics, so a rank-deficient case is never
  silent. The guards that remain are against input that is degenerate rather than
  merely rank deficient: missing residuals, a window shorter than the caller's
  declared `minimum_months`, an asset with zero residual variance, a non-finite
  covariance, and a window no longer than the number of priced factors.
- **Not changed: the number.** `minimum_months_for_standalone_second_pass` stays
  at 72 and `short_sample_flag_band_months` stays at `[36, 71]`. The floor is now
  a declared conservative restriction rather than a claimed impossibility: at
  `T <= N` the Shanken standard errors of the confirmatory system rest on a
  singular covariance and the chi-square is referred to `chi2(N - K)` while its
  pseudo-inverse measures at most `rank(Sigma_eps)` directions. Moving a
  threshold twice in response to review is what this project's discipline
  forbids, and the floor binds on no registered regime in either direction: the
  eligible regimes are 444 and 84 months and the next is 51.
- **Also corrected, same claim, other sites.** The docstring and error message of
  `residual_covariance_from_first_pass`; the `specification_test_caveat` in
  `artifacts/diagnostics/h3_regime_equivalence.json` and the
  `_residual_conditioning` docstring behind it, both of which asserted that the
  chi-square and the Shanken correction invert `Sigma_eps`; the criterion in
  `scripts/analyse_regime_power.py`, renamed from
  `feasible_shanken_covariance_estimable` to
  `feasible_shanken_covariance_full_rank` with the curve column
  `feasible_shanken_estimable` renamed to `feasible_shanken_full_rank`; and the
  corresponding passages in `reports/regime_eligibility_power_analysis.md` and
  `reports/monetary_regime_report.md`. The power sweep still reports a feasible
  Shanken interval only where the sample covariance is of full rank, which is now
  stated as a reporting choice rather than as a computational limit. Every
  simulated number on that sweep is unchanged by this correction.
- **New, and outside the confirmatory family.** Because the guard no longer
  blocks it, `normalisation` (51 months, 70 test assets) is estimated once as a
  labelled sensitivity in
  `artifacts/tables/regimes/regime_second_pass_short_sample_sensitivity.csv`,
  with `artifacts/diagnostics/regime_short_sample_sensitivity.json` recording
  what it is not. Its residual covariance has rank 48 of 70 and it carries the
  short-sample flag; `lambda_rate = -0.0844`. It enters no registered
  classification, no Holm family, and not the H3 verdict, and its chi-square
  p-value is not readable, because the statistic is referred to 68 degrees of
  freedom while measuring at most 48 directions. It is reported so that the
  restriction is visible rather than asserted.
- What it now forbids: justifying a threshold with a property of the estimator
  that the estimator does not have. A `T < N` residual covariance is now covered
  by a test in `tests/test_article_second_pass.py` that requires it to be
  accepted and to yield finite risk prices, finite Shanken standard errors, and a
  usable chi-square statistic.
