# Regime Eligibility Power Analysis

Decision support for the open question on the frozen regime-estimation floors.
Date: 2026-08-06.

This narrative is written by hand. It is not a generated report and does not
live under `reports/generated/`. `scripts/analyse_regime_power.py` produces the
evidence it reads — the curve, the diagnostic, and the provenance record listed
in section 7 — and every table and figure quoted below is transcribed from those
artifacts. The artifacts, not this file, are the record of what was computed.

## 0. Disclosure, before anything else

**This analysis was produced AFTER the frozen 36-month and 72-month eligibility
floors were observed to bind.** It was not part of the preregistered design. It
exists because the floors turned out to exclude four of six registered regimes
from standalone regime-specific estimation, and the project owner asked what the
estimator can actually support at a given sample length.

**No threshold has been relaxed.** Every contract file in `research/` and every
month count in `research/regime_registry.csv` is unchanged, and no criterion in
this report is proposed as a threshold. The values 36, 72, and 10 appear here
only as reference marks drawn on a curve; the script never evaluates them as
gates. It does record them, under `frozen_reference_marks` in
`artifacts/diagnostics/regime_eligibility_power.json`, so that a reader of the
curve can see which marks were current when it was drawn.

**One threshold was tightened after this analysis, and that is disclosed rather
than hidden.** The standalone-second-pass floor in `configs/regimes.yaml` was
raised from 60 to 72 months, and the reason first given for that change was
false. It read that the residual covariance the standalone second pass inverts
does not exist below 71 months; the second pass inverts no such matrix, and the
covariance is rank deficient rather than non-existent. Correction 11 in
`reports/design_correction_changelog.md` retracts the reason and keeps the floor,
which is now stated as a conservative restriction: below 71 months the
confirmatory system's residual covariance is singular, so its Shanken standard
errors rest on a singular estimate and its chi-square p-value is not readable.
The number itself has not moved in either direction. It changed no registered
regime's tier and moved no reported result. Wherever this report reads a
criterion off the curve at 60 months, 60 is a window length on the sweep, not the
floor.

**Acting on this evidence to loosen a floor would be a post-hoc design change.**
A threshold relaxed after seeing that it binds is not the same object as a
threshold frozen before estimation. This report supplies evidence and does not
recommend a number.

## 1. What was simulated

The data-generating process is calibrated to the actual estimated system on the
current 648-month regime panel (1972-01 to 2025-12, 70 value-weighted anomaly
deciles, `market_plus_fedfunds_innovation`):

- **Real betas.** First pass by `estimate_time_series_betas`, the project
  estimator, HAC lag 6 by the project's automatic rule.
- **Real residual covariance.** Built by `residual_covariance_from_first_pass`.
- **Real factor covariance and factor means**, from the same panel.
- **Realistic true risk prices.** The values the design's own no-intercept second
  pass returns on that panel: `lambda_market = 0.6939`,
  `lambda_rate = -0.4978`. Intercepts are set so the population mean excess
  return is exactly `B lambda`.

Each replication draws a window from that system, refits the first pass by plain
least squares (the pattern used in `models/block_bootstrap.py`; the first-pass
HAC covariance never enters the second pass, so this changes no number), and
refits the design's own second pass, `estimate_article_second_pass`, on the joint
70-portfolio system and on each ten-decile family system.

**2,000 replications per window length. Seed 20260727**, the project seed from
`configs/baseline.yaml`, with each window on the derived stream
`seed + window_months`. Every reported statistic carries its own Monte Carlo
standard error in the curve file.

The Shanken covariance is reported twice. **Feasible** uses the simulated sample
residual covariance through `residual_covariance_from_first_pass`. That
covariance exists at every window length, but with no more months than assets it
is rank deficient, and this sweep reports the feasible interval only where it is
of full rank. That is a reporting choice, not a computational limit: no step of
the second pass inverts the residual covariance, so the estimator runs below that
point too. **Oracle** substitutes the calibrated population residual covariance
and is infeasible in practice. The two agree to within Monte Carlo error wherever
both are reported, so the covariance estimate is not what is going wrong.

## 2. The curve

Joint 70-portfolio system, `lambda_rate`, true value `-0.4978`. "Detection" is the
probability of returning a correctly signed estimate whose Shanken t-statistic
exceeds 1.96 in absolute value.

| Months | Mean | Mean / true | SD | RMSE | P(wrong sign) | Shanken SE | 95% coverage | Detection |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 12 | -0.016 | 0.03 | 0.150 | 0.505 | 0.461 | 0.201 | 0.227 | 0.005 |
| 15 | -0.022 | 0.04 | 0.146 | 0.497 | 0.436 | 0.189 | 0.218 | 0.005 |
| 18 | -0.031 | 0.06 | 0.146 | 0.489 | 0.414 | 0.183 | 0.212 | 0.005 |
| 24 | -0.034 | 0.07 | 0.141 | 0.485 | 0.409 | 0.173 | 0.198 | 0.008 |
| 30 | -0.037 | 0.07 | 0.141 | 0.482 | 0.384 | 0.164 | 0.177 | 0.009 |
| **36** | -0.053 | 0.11 | 0.144 | 0.468 | 0.347 | 0.162 | 0.202 | 0.013 |
| 48 | -0.057 | 0.12 | 0.145 | 0.463 | 0.342 | 0.155 | 0.188 | 0.020 |
| 51 | -0.060 | 0.12 | 0.146 | 0.461 | 0.341 | 0.154 | 0.181 | 0.026 |
| 60 | -0.069 | 0.14 | 0.141 | 0.451 | 0.299 | 0.151 | 0.191 | 0.022 |
| **72** | -0.084 | 0.17 | 0.142 | 0.437 | 0.247 | 0.147 | 0.199 | 0.041 |
| 84 | -0.094 | 0.19 | 0.145 | 0.429 | 0.244 | 0.147 | 0.218 | 0.056 |
| 120 | -0.122 | 0.25 | 0.142 | 0.402 | 0.192 | 0.142 | 0.248 | 0.100 |
| 180 | -0.165 | 0.33 | 0.139 | 0.360 | 0.103 | 0.138 | 0.314 | 0.191 |
| 240 | -0.195 | 0.39 | 0.140 | 0.333 | 0.072 | 0.135 | 0.385 | 0.299 |
| 444 | -0.281 | 0.56 | 0.128 | 0.252 | 0.012 | 0.129 | 0.556 | 0.624 |
| 648 | -0.324 | 0.65 | 0.117 | 0.209 | 0.002 | 0.123 | 0.651 | 0.818 |

Standard deviation of the rate-attributable fitted-premium spread
`pi(decile_10) - pi(decile_01)`, joint system, worst family and worst family
root mean squared error, against the 0.25 monthly percentage-point bound in
`research/economic_thresholds.md`:

| Months | 12 | 24 | **36** | 48 | 51 | 60 | **72** | 84 | 120 | 180 | 240 | 444 | 648 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| worst SD | 0.562 | 0.353 | 0.288 | 0.255 | 0.250 | 0.233 | 0.225 | 0.214 | 0.191 | 0.172 | 0.168 | 0.151 | 0.139 |
| worst RMSE | 0.583 | 0.416 | 0.360 | 0.341 | 0.331 | 0.313 | 0.301 | 0.288 | 0.274 | 0.246 | 0.235 | 0.196 | 0.177 |

### 2.1 The one thing that is not the sample length

The standard deviation of `lambda_rate` is essentially **flat** at about 0.14
from 12 months to 648 months. Lengthening the window does not make the estimate
less dispersed; it moves the estimate. At 12 months the estimator returns 3
percent of the true risk price, at 60 months 14 percent, at 648 months 65
percent.

The mechanism is errors-in-variables attenuation in the two-pass estimator.
`first_pass_beta_reliability` splits the observed cross-sectional variance of the
calibration first-pass loadings into genuine exposure dispersion and first-pass
estimation error. At the 648-month calibration length the **reliability ratio**,
signal over observed, is **0.386** for `beta_rate` against **0.973** for
`beta_market`. Equivalently — and the two are exact complements, not two
different measurements — **61.4 percent** of the observed cross-sectional
dispersion of `beta_rate` is first-pass sampling noise, against **2.7 percent**
for `beta_market`. Noisy first-pass betas inflate `B'B` and shrink
`(B'B)^-1 B' rbar` toward zero.

The estimation-error term is a **cross-sectional** variance,
`[Sigma_f^-1]_kk / (T (N - 1)) * tr(M_N Sigma_eps)` with `M_N = I - 11'/N`, and
not the average individual sampling variance. The distinction matters because
first-pass errors are correlated across portfolios: the average off-diagonal
first-pass residual covariance across these seventy portfolios is 0.388 against
an average residual variance of 4.929. The common part of the estimation error
therefore moves the cross-sectional *mean* of the estimated loadings rather than
their *spread*, and `M_N` removes exactly that component. An earlier version of
this report divided the average individual sampling variance by the observed
cross-sectional variance and reported 66.7 percent and 2.9 percent. That
calculation drops every off-diagonal term and overstates the noise share whenever
residuals are positively correlated, which they are here; it has been replaced.
The mean individual sampling variance is still recorded in the diagnostic, under
`mean_individual_beta_sampling_variance`, because it answers a different and
useful question — how precisely a *single* portfolio's loading is estimated — but
it is a variance in squared-loading units and is not a share of any dispersion.

The noise term carries an explicit `1/T`, so under the stationary process
simulated here it falls in proportion to the window length and vanishes
asymptotically. The claim to make is not that the attenuation survives an
infinite sample; it is that **it remains economically large at every sample
length considered here**. At 648 months — the longest window on the sweep, and
the full length of the panel — more than three fifths of the observed dispersion
in `beta_rate` is still estimation error.

The Shanken standard error is not at fault and is not mis-sized. At 60 months it
averages 0.151 against a realised dispersion of 0.141 — very slightly
conservative. **The interval is close to the right width and in the wrong
place.** Coverage fails because the centre is biased, not because the width is
wrong.

`lambda_market` is the control that makes this legible. Its coverage is 0.943 to
0.959 at **every** window length from 12 to 648, and its standard deviation falls
at the parametric root-T rate (1.294 at 12 months to 0.183 at 648). The machinery
works. The rate factor specifically is the weakly identified one.

## 3. Where each criterion is actually met

Shortest window on the sweep from which the criterion holds and keeps holding.
These are **reading conventions for summarising a curve**, not thresholds, not
registered anywhere, and not proposed as replacements for any frozen value.

| Criterion | Joint 70-portfolio | 10-decile family |
|---|---:|---:|
| Sample residual covariance of full rank | **71 months** (exact) | 11 months (exact) |
| SD of fitted-premium spread below 0.25, all families | **60 months** | 180 months |
| RMSE of fitted-premium spread below 0.25, all families | **180 months** | 444 months |
| P(wrong sign on `lambda_rate`) at or below 0.05 | **444 months** | 444 to 648; never for two families |
| Mean estimate at least half the true `lambda_rate` | **444 months** | 444 months (median across families) |
| Mean estimate within 10 percent of the true `lambda_rate` | never on this sweep | never on this sweep (median) |
| 95 percent Shanken coverage inside [0.90, 0.99] | never on this sweep | never on this sweep |

The joint-system entries and the family sign-error and coverage entries are the
crossings recorded in `artifacts/diagnostics/regime_eligibility_power.json`. The
two family attenuation entries are read off the median across the seven families
in the curve file, because the script records that crossing only for the
confirmatory system.

Two of these need reading with care.

**The 60-month entry is the weakest number in this report.** The spread standard
deviation falls below 0.25 at 60 months only because the estimate has by then
been shrunk to 14 percent of its true magnitude, and a shrunk estimator is
mechanically a precise one. The same criterion counting total error rather than
dispersion alone — the RMSE row — is met at 180 months. A criterion that a window
can satisfy by returning approximately zero is not evidence that the window is
adequate.

**The 71-month entry is an arithmetic fact about rank, and an earlier version of
this report overstated what it means.** A sample residual covariance built from
`T` months of `N` test assets has rank at most `T - 1`, so on the confirmatory
70-portfolio system it is of full rank only from 71 months. It was previously
written here, and in correction 9 of `reports/design_correction_changelog.md`,
that below 71 months the Shanken covariance, the t-statistics, and the chi-square
specification test **do not exist**. That is false, and correction 11 retracts
it. The second pass never inverts the residual covariance: it enters only through
`B' Sigma B`, reduced to `K x K` before any inverse is taken, and through
`M Sigma M'`, read through a pseudo-inverse that is needed at any rank because
`M` has rank `N - K`. A rank-deficient covariance is admitted, and every one of
those statistics is computable below 71 months. What is true is that below that
point the Shanken standard errors rest on a covariance that is singular in
`N - rank` directions, and the chi-square is referred to `chi2(N - K)` while its
pseudo-inverse measures at most `rank(Sigma)` of them, so its p-value is not
readable. The 72-month floor is retained on that ground, as a conservative
restriction rather than a necessity, and it has not moved. Under the previous
60-month floor a regime of 60 to 70 months would have satisfied the
`months >= 60 and test_assets >= 10 and beta_rank == K` tier while the
confirmatory system's residual covariance was rank deficient. No registered
regime ever occupied that band, so nothing estimated was affected. Both regimes
that clear the frozen floor are well beyond it (`elb_qe` 84,
`conventional_pre_elb` 444), and the next longest regime, `normalisation` at 51
months, is now reported as a labelled sensitivity in
`artifacts/tables/regimes/regime_second_pass_short_sample_sensitivity.csv`, which
enters no confirmatory family.

## 4. The registered regimes read off the curve

Every registered regime length is a point on the sweep by construction.

| Regime | Months | Mean / true `lambda_rate` | P(wrong sign) | Detection |
|---|---:|---:|---:|---:|
| `post_tightening_easing` | 15 | 0.04 | 0.436 | 0.005 |
| `pandemic_elb_qe` | 24 | 0.07 | 0.409 | 0.008 |
| `inflation_tightening` | 30 | 0.07 | 0.384 | 0.009 |
| `normalisation` | 51 | 0.12 | 0.341 | 0.026 |
| `elb_qe` | 84 | 0.19 | 0.244 | 0.056 |
| `conventional_pre_elb` | 444 | 0.56 | 0.012 | 0.624 |

`elb_qe` currently carries full eligibility. At 84 months this design has a 5.6
percent chance of returning a correctly signed, significant rate risk price. A
coin-flip sign combined with a nominal 5 percent two-sided test would deliver 2.5
percent. Only `conventional_pre_elb` reaches a detection probability above one in
two.

## 5. What the evidence says about 36 and 72

**Neither floor is too strict. On this evidence both are, if anything, too lax.**

Every criterion on the sweep except one is met at a window far longer than the
72-month floor, and the one exception — the spread standard deviation, which
crosses at 60 months — is met for the wrong reason. Sign reliability arrives at
444 months. Half of the true risk price is recovered at 444 months. Total
fitted-premium error falls under the project's own 0.25 bound at 180 months.
Nominal 95 percent Shanken coverage for `lambda_rate` is not reached anywhere on
a sweep that runs to 648 months.

At the 36-month first-pass floor the estimator returns 11 percent of the true
risk price and gets its sign wrong 35 percent of the time. At the 72-month
standalone-second-pass floor it returns 17 percent and gets the sign wrong 25
percent of the time, with a 4.1 percent chance of a correctly signed significant
result.

So the case that these floors wrongly exclude the post-2020 regimes is not
supported here. A 24-month or 30-month regime does not fail the floors by a
technicality; on this calibration such a window recovers about 7 percent of the
risk price and gets the sign wrong two times in five. Nothing on this curve
suggests that admitting those regimes to standalone regime-specific estimation
would produce an interpretable estimate.

This conclusion survives its own main caveat. The two limitations in section 6
that could move the numbers — treating noisy estimated betas as true, and drawing
i.i.d. Gaussian disturbances — both push the simulated system toward being
*better* identified than the real one. Correcting either would lengthen the
windows in section 3, not shorten them. Nothing in the caveats points toward the
floors being too strict.

The curve does not tell the owner where a floor should sit, and this report does
not propose one. It does say which direction the evidence points: the frozen
values are on the permissive side of what this estimator can support, not the
restrictive side. The most defensible action on this evidence is to relax
neither floor and to cite this analysis as a stated limitation on the precision
available inside the regimes that do clear them. The one revision that followed,
raising the second-pass floor from 60 to 72 months, moved in the direction this
section describes and was made on the computability ground in section 3 rather
than on the precision evidence here.

## 6. What this does not establish

1. **The process is not a fixed point of the estimator.** The calibration treats
   the full-sample estimated betas as true, which is what calibrating to the
   actual estimated system means. A simulated first pass then produces noisier
   betas than the process was built from, so the second pass attenuates at every
   window length, including 648. Read the mean, the ratio-to-true, and the
   coverage columns as **comparisons across window lengths**, not as absolute
   statements about any published or generated estimate. The standard deviations
   and the sign-error probabilities are the columns least exposed to this.
2. **The numbers are optimistic, not conservative.** Because the real betas are
   themselves noisy estimates, the true cross-sectional exposure dispersion is
   smaller than the simulated one, so the simulated cross-section is better
   identified than the real one.
3. **The disturbances are Gaussian and serially independent.** No block structure,
   no conditional heteroskedasticity, no fat tails. The moving-block bootstrap in
   `models/block_bootstrap.py` handles the real dependence and produces wider
   intervals than an i.i.d. calibration; at 504 months it implies a fitted-premium
   spread dispersion near 0.21 for `book_to_market` against roughly 0.15 here.
   Real windows are therefore likely to be less precise than these curves show.
4. **This is a statement about estimator precision as a function of sample
   length. It is not an economic conclusion**, about the article, about any
   regime, or about monetary policy. It says nothing about whether a short-rate
   risk price exists, and nothing about what any regime-specific estimate would
   mean if one were produced.
5. **Every input remains a documented reconstruction** on a post-publication
   portfolio vintage, per `reports/baseline_input_readiness.md` section 1.

## 7. Generated artifacts

| Artifact | Contents |
|---|---|
| `artifacts/tables/regimes/eligibility_power_curve.csv` | 368 rows: per system, cross-section, window, and estimand, with Monte Carlo standard errors |
| `artifacts/diagnostics/regime_eligibility_power.json` | Calibrated truth, the first-pass beta reliability decomposition, criterion crossings, the fixed-point caveat, the post-hoc disclosure |
| `artifacts/provenance/regime_power_analysis.json` | Input and output checksums, seed, replications, window grid, `thresholds_changed: []` |
