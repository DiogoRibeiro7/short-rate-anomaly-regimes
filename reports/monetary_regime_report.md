# Monetary Regime Report

Milestone 10. Date: 2026-08-06.
Article: Maio and Santa-Clara, *JFQA* 52(3), 927-961.

**Every result carries the label `documented_reconstruction`.** No input in this
design is an exact article input.

**Registered classification: H3
`regime_stability_unsupported_under_the_registered_equivalence_standard`.**

The registry admits three outcomes and they are not interchangeable. Its
`unsupported` reading asserts that "the relation is regime dependent", which is
a positive claim, while its `inconclusive` reading covers a confidence region
too wide to certify invariance. The classification here is therefore **derived**
rather than defaulted: `unsupported` is assigned only because one dimension,
relative RMSE deterioration, has its entire 90 percent interval beyond its bound.

On every other dimension the failure is imprecision, not evidence. Of the 70
per-portfolio equivalence tests, 26 certify equivalence, 44 are inconclusive,
and **none** demonstrates a change exceeding the registered bound. Section 5
keeps these apart, because a failed equivalence test is not a detected
difference.

The registered estimator has two halves, and they do not have the same power.
The regime-specific second passes in sections 3 to 5 are limited by an 84-month
regime, and the classification just described comes from that half alone. The
**pooled interaction model** in section 7 uses all 648 months and rejects beta
stability decisively, with a joint rate-beta statistic of 37.313 on 5 degrees of
freedom, Holm p 5.08e-05, and the registered verdict `unstable`. The two halves
agree in direction; only the pooled half can demonstrate it.

## 1. One vintage across the whole history

Two registered regimes straddle the 2013-12 boundary between the
publication-era and current factor vintages. `elb_qe` runs 2009-01 to 2015-12,
so a panel that switched vintage at its natural break would confound a policy
effect with a data revision inside a single regime.

The regime panel is therefore built on the **current vintage throughout**, by
concatenating the revised-history panel (1972-2013) with the extension panel
(2014-2025) into 648 months, 1972-01 to 2025-12. Milestone 9 licenses this: over
the baseline window the vintage contribution moves the rate risk price by less
than 0.00001 and cross-sectional RMSE by 0.003 percent, against temporal
contributions of 0.6159 and 91 percent. The vintage change is negligible against
the differences measured here.

The short-rate autoregression is re-estimated once over the whole 648 months, so
the factor is a single series rather than two spliced ones.

## 2. Four of six regimes cannot support a standalone second pass

The eligibility floors were frozen before any regime estimate existed. Applying
them:

| Regime | Window | Months | Tier | Standalone second pass |
|---|---|---|---|---|
| `conventional_pre_elb` | 1972-01 to 2008-12 | 444 | eligible, first pass and standalone second pass | yes |
| `elb_qe` | 2009-01 to 2015-12 | 84 | eligible, first pass and standalone second pass | yes |
| `normalisation` | 2016-01 to 2020-03 | 51 | eligible first pass, short-sample flag | no |
| `pandemic_elb_qe` | 2020-04 to 2022-03 | 24 | blocked below 36 months | no |
| `inflation_tightening` | 2022-04 to 2024-09 | 30 | blocked below 36 months | no |
| `post_tightening_easing` | 2024-10 to 2025-12 | 15 | blocked below 36 months | no |

The confirmatory H3 comparison therefore spans **one contrast**,
`elb_qe` against `conventional_pre_elb`. The four ineligible regimes are not
dropped from the record; they enter through the pooled interaction model in
section 7, which borrows strength across regimes rather than estimating each one
alone. This limitation is a consequence of the registered floors, not a choice
made after seeing results.

## 3. The two estimable regimes

| Regime | Months | lambda_market | lambda_rate | Shanken t | RMSE | Article fit | Premium dispersion |
|---|---|---|---|---|---|---|---|
| `conventional_pre_elb` | 444 | 0.4578 | **-0.7259** | -2.87 | 0.1046 | 0.5960 | 0.1753 |
| `elb_qe` | 84 | 1.3270 | **0.0037** | 0.84 | 0.2220 | -0.1717 | 0.0333 |

The pre-ELB estimate reproduces the Milestone 5 baseline closely: -0.7259 on
1972-2008 against -0.6985 on 1972-2013, with the same Shanken t to two decimals.
The ELB estimate is a different object. The rate risk price is not merely
smaller, it is indistinguishable from zero, and the article's cross-sectional
fit is negative, meaning the fitted premia explain less of the cross-section of
average returns than a constant would.

The average absolute rate-attributable fitted premium falls from 0.1517 to
0.0281 monthly percentage points, a collapse of 81 percent. The extreme-decile
spreads tell the same story:

| Family | Pre-ELB spread | ELB spread | Change |
|---|---|---|---|
| `book_to_market` | 0.6061 | -0.0680 | -0.6741 |
| `equity_duration` | -0.5110 | 0.0734 | +0.5844 |
| `earnings_to_price` | 0.4691 | -0.0585 | -0.5276 |
| `investment_to_assets` | -0.3770 | -0.0360 | +0.3409 |
| `long_term_reversal` | -0.3756 | -0.0480 | +0.3276 |
| `ppe_investment` | -0.3237 | -0.0879 | +0.2358 |
| `inventory_growth` | -0.2246 | -0.0277 | +0.1969 |

Every family moves toward zero. This is not a sign reversal of the kind
Milestone 9 found in the temporal comparison; it is a flattening.

## 4. The equivalence tests

The confirmatory rule is the one fixed in `research/inference_contract.md`:
two one-sided tests at the 5 percent level, implemented as inclusion of the
two-sided 90 percent joint-bootstrap percentile interval inside the declared
bound. Blocks are resampled within regime, 10,000 draws, and every draw
recomputes the innovation, the first pass, the second pass, the premia, and the
fit statistics. The stricter 95 percent variant is carried in
`h3_equivalence.csv` under the label `strict_95pct_interval_sensitivity` and
decides nothing; it fails wherever the confirmatory rule fails.

| Gate | Bound | Point change | 90 percent interval | Result |
|---|---|---|---|---|
| Per-portfolio fitted premium | within 0.25 | max 0.5272 | see section 5 | **fail** |
| Dispersion of fitted premia | within 25 percent | -81.0 percent | [-97.2, +23.9] percent | **fail** |
| RMSE deterioration | at most 10 percent | +112.2 percent | [+11.4, +135.9] percent | **fail** |
| Maximum pricing error deterioration | at most 0.25 | +0.3035 | [+0.036, +0.620] | **fail** |
| Article fit deterioration | at most 0.10 | +0.7676 | [-0.347, +1.237] | **fail** |

All five gates fail to certify equivalence. That alone does not settle the
classification, which section 5 resolves.

## 5. What actually failed, and why the distinction matters

An equivalence test can fail two ways: the interval can lie beyond the bound,
which is evidence of a real difference, or it can straddle the bound, which
means the data cannot resolve the question either way. Only the first is a
finding. Sorting all 70 per-portfolio tests:

| Category | Portfolios |
|---|---|
| Equivalent within the bound | 26 |
| Inconclusive, interval straddles the bound | 44 |
| **Difference exceeds the bound** | **0** |

Not one of the 70 test assets shows a fitted-premium change that the registered
test can certify as larger than 0.25 monthly percentage points. Sixteen have
point estimates outside the bound, the largest being 0.5272, but in every case
the 90 percent interval reaches back inside it. Interval widths run from 0.1980
to 0.8091 with a median of 0.3664, against a bound window of 0.50, so only 9 of
70 intervals are too wide to fit inside the bound at any location. The failures
are therefore concentrated where the point estimate sits near the boundary
rather than arising from uniformly hopeless imprecision.

Among the aggregate gates the pattern is the same with one exception:

| Gate | Category |
|---|---|
| Dispersion | inconclusive |
| **RMSE deterioration** | **difference exceeds bound** |
| Maximum pricing error | inconclusive |
| Article fit | inconclusive |

The RMSE result is the one demonstrated exceedance among the equivalence gates.
The entire 90 percent interval for the relative RMSE change, [+11.4, +135.9]
percent, lies above the 10 percent bound. On that gate alone the ELB regime is
established to price the cross-section worse than the conventional regime by
more than the predeclared margin.

That single gate is what carries this half of the classification. Had it too
been inconclusive, the equivalence half would have returned
`regime_stability_inconclusive`, since no other equivalence dimension supplies
affirmative evidence of regime dependence. The classification and its basis are
recorded together in `h3_regime_equivalence.json` under
`dimensions_with_a_demonstrated_exceedance`, so the verdict cannot be read
without the reason for it. The pooled half of the registered estimator, in
section 7, reaches the same direction by a different and far better powered
route.

Everything else is a statement about 84 months of data, not about monetary
policy. The honest summary is: **the point estimates all say the short-rate
factor stops being priced at the effective lower bound, the cross-sectional fit
demonstrably deteriorates, and the fitted-premium changes themselves cannot be
certified as exceeding the registered bound at this sample size.**

## 6. Two caveats that the point estimates alone would hide

**The specification test is not usable in the ELB regime.** Neither the
chi-square statistic nor the Shanken correction inverts the residual covariance:
it enters the second pass only through `B' Sigma B`, reduced to `K x K` before
any inverse, and through `M Sigma M'`, read through a pseudo-inverse. An earlier
version of this section said both invert it, which was wrong and is retracted by
correction 11 in `reports/design_correction_changelog.md`. What a small `T - N`
costs is information, not existence. In `conventional_pre_elb`, `T - N` is 374
and the covariance has condition number 5.5e2. In `elb_qe`, `T - N` is 14 and the
condition number is 1.1e4, so its smaller eigenvalues are largely noise. The
reported ELB chi-square p-value of 2e-59 is an artifact of that
near-indeterminacy and is reported in `regime_second_pass.csv` without being used
for any claim. The equivalence gates use neither the covariance nor its
pseudo-inverse, so the H3 classification is unaffected.

This is a gap in the frozen eligibility floors worth recording: they constrain
months and test-asset count separately but never their difference, so a regime
can clear both while leaving the residual covariance barely determined. The
floors are not changed here.

**The result does not rest on how the innovation was defined.** The inference
contract requires the short-rate innovation to be recomputed in every draw and
blocks to be resampled within regime, so the autoregression is re-estimated
inside each regime window rather than taken from the whole-history fit used to
build the panel. This is a design choice, and `pi_rate` is invariant to
rescaling the innovation but not to redefining it, so the alternative was
computed as well. Holding the whole-history innovation fixed instead, the 70
per-portfolio premium changes correlate at 0.9987 with the reported ones, agree
in sign 70 times out of 70, differ by at most 0.0367, and put 17 rather than 16
portfolios outside the bound at the point estimate. The rate risk price moves
from -0.7259 to -0.7233 pre-ELB and from 0.0037 to 0.0045 at the ELB. Nothing in
the classification turns on the choice.

**The block-length selector fell back in the ELB regime.** Politis-White
returned an optimal block length of 1, outside the contract's admissible
`[2, 24]`, so the declared 12-month fallback applied and the reason is recorded
in `regime_second_pass.csv`. A selected length of 1 is itself informative: with
the funds rate pinned near zero the innovation has a standard deviation of
0.0228 against 0.6229 pre-ELB and almost no serial dependence left to preserve.
The pre-ELB regime selected 6 months by the selector proper.

## 7. The pooled interaction model answers what the regime-specific tests could not

The registered estimator for H3 is
`pooled_beta_interactions_plus_regime_specific_second_pass_models`. Sections 3
to 5 cover the second half. The pooled half uses all 648 months and all six
regimes at once, interacting both factors with the regime label and omitting
`conventional_pre_elb` as the baseline, with HAC lags of 6. Because it borrows
strength across the whole sample instead of estimating each regime alone, it is
not subject to the 84-month precision limit that made section 5 inconclusive.

It rejects beta stability decisively:

| Restriction | Statistic | df | p | Holm p |
|---|---|---|---|---|
| Rate-beta interactions | 37.313 | 5 | 5.18e-07 | 5.08e-05 |
| All factor interactions | 58.859 | 10 | 5.95e-09 | 6.73e-07 |

Per asset, rate-beta interactions are significant for 41 of 70 unadjusted and 26
of 70 after Holm; all-factor interactions for 65 and 54. The registered
`classify_stability` verdict is **`unstable`**.

Holm was applied across the 142 pooled tests, but the registered
`regime_stability` family also contains the 74 equivalence tests of section 4.
Adjusting over the completed family of 216 leaves both joint results
significant by a wide margin: a Bonferroni bound, which is more conservative
than Holm at every step, gives 1.12e-04 and 1.29e-06. The conclusion does not
depend on where the family boundary is drawn.

**One fragility must be recorded.** Shifting every regime boundary by three
months either way leaves the `unstable` verdict intact, but not the aggregate
test that produces it. Its Holm p-value moves from 5.08e-05 at the registered
boundaries to 0.065 at minus three months and 0.051 at plus three, so the
aggregate rate-beta test alone loses 5 percent significance under either shift.
The verdict survives on the per-asset rejections, which actually increase, to 39
and 36 from 26. The registered boundaries are therefore the most favourable of
the three for the aggregate statistic, and its exact p-value should not be
quoted as though it were robust to the boundary convention.

**The break battery is exploratory and is labelled E1 throughout.** It is not a
member of the confirmatory family and neither confirms nor refutes H3. Its most
useful result is negative: the unknown-break methods do not recover the
registered policy dates. Quandt-Andrews puts its maximum at 1989-12 (statistic
9.422, adjusted p 0.00244) and Bai-Perron selects 1998-07 and 2001-08, none of
which is a monetary-regime boundary. Chow tests at the registered boundaries do
not reject at 5 percent: 2008-12 gives p 0.0663 and 2015-12 gives p 0.0526, with
the remaining three far from significance. CUSUM gives 1.150, p 0.0709.

Read together with section 5, that is a coherent picture: the *calendar* dates
on which this cross-section breaks are not the dates on which monetary policy
changed. The regime interactions are strongly significant, but a search that is
not told where to look does not find the policy boundaries.

## 8. Why section 5 was inconclusive, and what that says about the floors

A simulation calibrated to the estimated full-history process, 2,000
replications at each of 16 window lengths, was run as decision support for the
standalone-second-pass floor question, which was open at 60 months when the
simulation ran. **It relaxed no threshold, config, contract, or registry
entry**, and the artifact records that acting on it to loosen a floor would be a
post-hoc design change requiring its own disclosure. The one revision that
followed tightened the floor, from 60 to 72 months, on the computability ground
set out below; it is recorded in `reports/design_correction_changelog.md` and
changed no registered regime's tier. Nothing in section 5 moves as a result.

Months required, on the joint 70-portfolio system, for each criterion to be met
and stay met:

| Criterion | Months required |
|---|---|
| Residual covariance estimable at all | 71 (first simulated window 72) |
| Fitted-premium spread RMSE below the 0.25 bound, all families | 180 |
| Sign-error probability for `lambda_rate` at or below 5 percent | 444 |
| Attenuation ratio at or above 0.50 | 444 |
| Attenuation ratio at or above 0.90 | never within 648 |
| Shanken 95 percent coverage inside [0.90, 0.99] | never within 648 |

One criterion is deliberately excluded from that table. The *standard
deviation* of the fitted-premium spread falls below 0.25 at 60 months, which
looks like support for the frozen floor and is not. At 60 months the estimator
has been attenuated to 14 percent of the true `lambda_rate`, and a shrunken
estimator is mechanically a stable one. The error-counting version of the same
criterion, RMSE about the true value, is not met until 180 months. Quoting the
60 without the attenuation would invert the finding.

The headline is that **36 and 72 are not too strict; on this evidence both are,
if anything, too lax.** Three things follow, none of which relaxes a threshold.

First, the dominant mechanism is errors-in-variables attenuation. It is a `1/T`
quantity — the analytical expression for the estimation-error contribution
carries an explicit `1/T` and vanishes asymptotically under the stationary
process simulated here — but it remains economically large at every sample length
considered here. At 648 months, the full length of the panel, the reliability
ratio of `beta_rate` is 0.386: 61.4 percent of the observed cross-sectional
dispersion of `beta_rate` is still first-pass sampling noise, against 2.7 percent
for `beta_market`. The sampling standard deviation of `lambda_rate`
is essentially flat, 0.1499 at 12 months and 0.1167 at 648: a longer window
moves the estimate rather than tightening it. At 36 months the estimator returns
11 percent of the true risk price and gets the sign wrong 35 percent of the
time; at 72 months, 17 percent and 25 percent. `lambda_market` is the control
that shows the machinery is sound, with coverage between 0.943 and 0.959 at
every window length and a standard deviation falling at root-T.

Second, the previous 60-month floor sat below the 71 months this design needs
merely for the residual covariance of a 70-asset system to exist. A regime of 60
to 70 months would have cleared the registered tier and then failed inside the
standalone second pass that tier authorises. No registered regime ever fell in
that band, so nothing estimated was affected, but it was a latent gap, and it is
the same gap section 6 found empirically at `elb_qe`, where `T - N` is 14,
reached from an independent direction. The floor is now 72 months, the first
window on the sweep at which the covariance exists, which empties the band.

Third, `elb_qe`'s 84 months sit far below the 180 needed for fitted-premium
spreads to be resolved against the very bound the equivalence gates use. The 44
inconclusive verdicts in section 5 are what this predicts. They are a property
of the design at that sample size, not a discovery about the ELB period.

The simulation's caveats sharpen rather than soften this. The calibration treats
full-sample estimated betas as true and uses independent Gaussian disturbances,
so the simulated cross-section is better identified than the real one.
Correcting either would lengthen the required windows, not shorten them.

One thing the caveats do restrict is how the attenuation levels may be read.
Because the calibration is not a fixed point of the two-pass estimator, the
attenuation ratio and coverage are meaningful **as comparisons across window
lengths**, not as absolute measurements of how attenuated any particular real
estimate is. The figures above are used only in that comparative sense. Nothing
here licenses a claim that the article's own risk price, or the baseline
replication of it, is attenuated by any stated amount.

This is decision support for a question the user has not settled. The floors
remain as frozen, and every number in sections 3 to 7 was produced under them.
The full analysis is in `reports/regime_eligibility_power_analysis.md`.

## 9. What this does and does not establish

It establishes that short-rate betas are regime dependent. The pooled
interaction model rejects stability on all 648 months at Holm p 5.08e-05 for the
rate factor alone, and the rejection survives adjustment over the completed
multiplicity family and a three-month shift of every boundary.

It establishes that the article's short-rate pricing relation, reproduced
closely on 1972-2008, does not carry into the 2009-2015 effective-lower-bound
period on these documented reconstruction inputs. The rate risk price falls from
-0.7259 with a Shanken t of -2.87 to 0.0037 with a t of 0.84; the article's fit
metric goes negative; and cross-sectional RMSE deteriorates by more than the
registered bound, demonstrably so.

It does not establish that any individual portfolio's rate-attributable fitted
premium changed by more than the registered 0.25 bound. No test asset reaches
that standard, and 26 of 70 are certified equivalent. Section 8 shows this is
what an 84-month window can deliver: the design needs 180 months to resolve
those spreads against that bound.

It does not locate a cause. That the relation weakens exactly when the policy
rate is pinned near zero is consistent with the mechanism the design was built
to test, but a single regime contrast on 84 months cannot separate it from
anything else that changed after 2008. The exploratory break battery is a
caution here rather than support: left to find breaks on its own, it selects
1989-12, 1998-07 and 2001-08, none of them a policy date, and it does not reject
at any registered boundary.

It does not speak to the four ineligible regimes beyond their interaction
coefficients. Under the registered floors they support no standalone second
pass, and nothing here should be read as a regime-specific result for the
pandemic, the tightening cycle, or the current easing.

## 10. Generated artifacts

| Artifact | Contents |
|---|---|
| `data/processed/regimes/monthly_regimes.parquet` | 648 months, current vintage, primary and sensitivity labels |
| `artifacts/tables/regimes/regime_eligibility.csv` | Tier and gate outcome per regime |
| `artifacts/tables/regimes/regime_second_pass.csv` | Second pass per eligible regime, with block and conditioning detail |
| `artifacts/tables/regimes/regime_fitted_premia.csv` | Per-portfolio premia, changes, and the global-innovation sensitivity |
| `artifacts/tables/regimes/h3_equivalence.csv` | All 74 equivalence tests with both interval rules and the decision category |
| `artifacts/diagnostics/h3_regime_equivalence.json` | Gate outcomes, categories, conditioning, and the classification |
| `artifacts/tables/regimes/pooled_interaction_wald.csv` | 142 pooled tests and per-regime interaction coefficients |
| `artifacts/tables/regimes/boundary_sensitivity.csv` | Every pooled test at boundary shifts of -3, 0, +3 months |
| `artifacts/tables/regimes/break_tests.csv` | Exploratory E1 break battery, excluded from the confirmatory family |
| `artifacts/diagnostics/h3_pooled_beta_stability.json` | Pooled verdict, multiplicity scope, boundary sensitivity |
| `artifacts/tables/regimes/eligibility_power_curve.csv` | Simulated precision at 16 window lengths |
| `artifacts/diagnostics/regime_eligibility_power.json` | Months required per criterion, with the post-hoc disclosure |
| `artifacts/provenance/regime_panel.json`, `regime_equivalence.json`, `regime_interactions.json` | Input and output checksums, seeds, block lengths |
