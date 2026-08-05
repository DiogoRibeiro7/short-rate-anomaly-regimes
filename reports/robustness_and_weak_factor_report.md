# Robustness and Weak-Factor Report

Milestone 8. Date: 2026-08-05.
Article: Maio and Santa-Clara, *JFQA* 52(3), 927-961.

**Every result carries the label `documented_reconstruction`.** No input in this
design is an exact article input. See `reports/baseline_input_readiness.md`
section 1.

Selective robustness reporting is prohibited by the milestone gate. Every
registered gate is reported below, whether it passed or failed.

Confirmatory system throughout: `market_plus_fedfunds_innovation` on the joint
70-portfolio set, 504 months, 1972-01 to 2013-12. `lambda_rate = -0.6985`
(Shanken standard error 0.2443, t = -2.86), `lambda_market = 0.6012`.

## 1. Summary of registered classifications

| Claim | Classification |
|---|---|
| **H1** incremental pricing vs the ex ante CAPM comparator | **unsupported** on the joint set; supported on two of seven families |
| **H4a** cross-sectional identification strength | **pass** |
| **H4b** influence stability | **pass** |
| **H4c** fitted-premium precision | **pass** |

The weak-factor condition is met on all three of its components. The
incremental-pricing materiality standard is not met on the headline asset set.
These are registered classifications against predeclared thresholds, not
economic conclusions.

## 2. H1 incremental pricing materiality

Primary comparator: CAPM, chosen ex ante and independently of observed RMSE.
All three gates must hold.

Joint 70-portfolio system:

| Gate | Threshold | CAPM | Short-rate model | Observed | Result |
|---|---|---|---|---|---|
| RMSE reduction | at least 10 percent | 0.1893 | 0.1004 | 47.0 percent | pass |
| MAE reduction | at least 10 percent | 0.1466 | 0.0816 | 44.3 percent | pass |
| Maximum absolute pricing-error reduction | at least 0.25 monthly pp | 0.4752 | 0.2388 | 0.2364 pp | **fail** |

**Registered classification: unsupported.** Two of three gates pass; the third
misses by 0.0136 monthly percentage points.

### 2.1 The binding gate, stated plainly

The two relative gates clear by roughly a factor of four. The absolute gate is
the only one that fails, and it fails narrowly. That asymmetry deserves to be on
the record because it, alone, determines the headline classification.

CAPM's own maximum absolute pricing error on this asset set is 0.4752 monthly
percentage points. Requiring an absolute reduction of 0.25 pp therefore requires
cutting that statistic by **52.6 percent**. The short-rate model cut it by 49.7
percent. In relative terms the third gate is a five-times-stricter bar than the
first two, which ask for 10 percent.

Nothing in `research/economic_thresholds.md` states that the asymmetry was
intended. The threshold was nonetheless frozen before any estimate existed, and
it is used here exactly as frozen. It has not been adjusted, and adjusting it
now, in the knowledge that it is the binding constraint, would not be
defensible. If the relative-versus-absolute mismatch is judged to be a design
error rather than a deliberate choice, the place to record that is a stated
limitation, not a revision.

### 2.2 Per asset set

`supported` for `equity_duration` and `investment_to_assets` under both the
baseline federal-funds specification and the registered Treasury-bill
alternative. `unsupported` for the other five families and for the joint system.
The relative gates pass in all sixteen rows; the absolute gate is the binding
one in six of eight asset sets.

### 2.3 Secondary adversarial comparison

The strongest observed non-short-rate comparator per asset set, selected **after**
observing baseline RMSE: `carhart_4` for the joint set and long-term reversal,
`fama_french_5` for four families, `liquidity` for two. Every one of the sixteen
secondary comparisons is `unsupported`; all three gates fail in every row.

Each row records `comparator_selected_after_observing_rmse = True` and carries an
explicit model-selection-uncertainty note. This selection never feeds the choice
of primary comparator.

### 2.4 Multiplicity

No p-value is produced. The gates are deterministic threshold comparisons on
point estimates, so the Holm adjustment registered for the secondary comparator
family has nothing to adjust and does not yet apply. This is recorded in every
row rather than resolved by inventing a p-value.

## 3. H4a cross-sectional identification strength

| Gate | Threshold | Observed | Result |
|---|---|---|---|
| Beta-matrix rank | equal to the number of priced factors | 2 of 2 | pass |
| Standardized rate-exposure dispersion | at least 0.10 of standardized market dispersion | 0.2540 | pass |
| Numerical spanning criterion | `R2_span` at most 0.90 | 0.0560 | pass |

Per family the standardized dispersion share ranges from 0.1903 to 0.3894, so no
family sits near the floor.

The spanning regression executed all ten registered non-short-rate comparator
factors over 504 months, in the frozen order. `s_span = 0.9716` against a minimum
of `sqrt(0.10) = 0.3162`. The descriptive market-only reference is
`R2 = 0.0186`. The rate innovation is a long way from being spanned by the
existing traded-factor set.

**H4a passes.**

## 4. H4b influence stability

| Gate | Threshold | Observed | Result |
|---|---|---|---|
| Leave-one-anomaly-family refits | no sign reversal, no materiality loss | 0 reversals, 0 losses in 7 refits | pass |
| Standardized DFBETA on `lambda_rate` | maximum absolute below 1 | 0.0896 | pass |

Across the seven leave-one-family refits `lambda_rate` moves within
`[-0.7519, -0.6777]`, and the largest absolute change in any per-asset
rate-attributable fitted premium is 0.0332 monthly percentage points. The
largest single-portfolio influence is 0.0896 at `inventory_growth__decile_05`;
no portfolio of the seventy reaches the bound.

**H4b passes.**

One reporting note. The seven single-family systems are marked `descriptive`,
not confirmatory: the frozen contract fixes the joint 70-portfolio system as the
tested system. Descriptive per-family DFBETA maxima reach 0.848, which is
reported and decides nothing. Reporting them matters because they are the rows
most likely to be quoted out of context.

## 5. H4c fitted-premium precision

Estimand: the rate-attributable fitted-premium spread
`pi_rate(decile_10) - pi_rate(decile_01)` per family, which is the object the
article tabulates as `DIF` in Table 5. The gate fails when the 95 percent
joint-bootstrap interval contains both `+0.25` and `-0.25`.

| Family | Point estimate | 95 percent interval | Result |
|---|---|---|---|
| `book_to_market` | 0.5353 | [0.0223, 0.8321] | pass |
| `earnings_to_price` | 0.4071 | [-0.0064, 0.6953] | pass |
| `equity_duration` | -0.4617 | [-0.7265, 0.0063] | pass |
| `long_term_reversal` | -0.2992 | [-0.7079, 0.1588] | pass |
| `investment_to_assets` | -0.3283 | [-0.5342, -0.0239] | pass |
| `ppe_investment` | -0.2981 | [-0.4829, 0.0012] | pass |
| `inventory_growth` | -0.1908 | [-0.4524, 0.0931] | pass |

**H4c passes for every family.** No interval spans both economic directions.

### 5.1 Bootstrap execution

Moving-block bootstrap, 10,000 repetitions, project seed 20260727. Each draw
resamples calendar months jointly and recomputes the entire chain: the AR(1)
short-rate innovation, all seventy first-pass betas, the no-intercept second
pass, and the fitted premia.

Block length **6 months**, selected by Politis-White. Raw optimal lengths were
2.388 for the market factor and 5.318 for the rate innovation; the maximum is
taken so the block is long enough for the more persistent series, and the result
lies inside the declared `[2, 24]` bounds, so the declared 12-month fallback was
not used.

Regime labels are not among the resampled variables, per the design correction.
Only calendar months are drawn; no asset and no label is resampled.

### 5.2 The selector is implemented in this repository

`arch` is a declared project dependency but is not installed in the working
environment, and installation is unavailable there. Falling back to the
contract's fixed 12-month block for that reason would have degraded a frozen
contract for a tooling reason: the contract's declared failure conditions are
data conditions, not a missing dependency.

The Politis-White selector is therefore implemented in
`src/short_rate_anomaly_regimes/models/block_bootstrap.py`, following Politis
and White (2004) with the Patton, Politis and White (2009) correction and the
`4/3` denominator constant that applies to the moving-block case. This is the
better arrangement for a replication in any case: the formula behind every
generated interval is auditable in the repository rather than delegated to a
library call.

### 5.3 One definition the contract did not pin

The contract names "the rate-attributable fitted-premium spread" without
defining "spread". It is defined here as `pi(decile_10) - pi(decile_01)`, which
matches the article's Table 5 `DIF` across extreme deciles. The definition must
be signed, because an unsigned spread could never span both economic directions
and the gate would be vacuous. This is a clarification of the frozen contract,
recorded rather than assumed.

## 6. Independent cross-validation

The fitted-premium spreads are computed twice, by two implementations that share
no code path:

- the bootstrap module, in vectorised array algebra, re-estimating the AR(1) and
  both passes from scratch;
- the weak-factor diagnostics, using the general first-pass estimator with HAC
  inference and the article second-pass module.

The two agree to **1.6e-15** across all seven families. The recomputed betas also
match the stored first-pass betas exactly.

A second check covers the bootstrap's most delicate input. The pre-window lagged
rate level for 1972-01 is not carried by the canonical panel, and is recovered by
inverting the autoregression the panel already embeds. The recovered interior
lags reproduce the observed previous-month levels to 1e-14, the recovered
coefficients match the stored AR estimates, and the implied 1971-12 level is
4.1400, which is exactly the frozen FEDFUNDS value for that month.

## 7. What this does not establish

The weak-factor gates say the short-rate factor is well enough identified,
stable enough to test-asset composition, and precisely enough estimated to
support a pricing interpretation. They do not say the interpretation is correct.

The H1 classification says the registered materiality standard is not met on the
headline asset set. It does not say the short-rate factor adds nothing: two of
three gates pass by a wide margin, and the failing gate misses narrowly. Nor
does it evaluate the article, whose own materiality standard is not this one.

Every input remains a documented reconstruction on a post-publication portfolio
vintage. Nothing here distinguishes a threshold outcome from a vintage effect.

## 8. Generated artifacts

| Artifact | Contents |
|---|---|
| `artifacts/diagnostics/weak_factor/h4a_identification_strength.json` | Rank, dispersion, spanning, with executed regressors |
| `artifacts/diagnostics/weak_factor/h4b_influence_stability.json` | Leave-one-family and DFBETA outcomes |
| `artifacts/diagnostics/weak_factor/h4c_fitted_premium_precision.json` | Bootstrap intervals and the gate decision |
| `artifacts/diagnostics/h1_materiality.json` | Every H1 gate value and threshold per asset set |
| `artifacts/tables/robustness/leave_one_family.csv` | 420 rows, omitted family by retained asset |
| `artifacts/tables/robustness/dfbeta_influence.csv` | 140 rows, confirmatory and descriptive |
| `artifacts/tables/robustness/h4c_fitted_premium_intervals.csv` | Per-family intervals |
| `artifacts/tables/robustness/h1_primary_comparison.csv` | Primary comparator gates |
| `artifacts/tables/robustness/h1_secondary_adversarial.csv` | Secondary comparator gates with selection uncertainty |
| `artifacts/provenance/*.json` | Input and output checksums, thresholds, contract sources |

## 9. Remaining unspecified points, recorded not resolved

1. The DFBETA standardizer is not specified as full-sample or leave-one-out. The
   full-sample Shanken standard error is used and the leave-one-out value is
   reported alongside. The gate outcome is the same under either.
2. The materiality bound is not stated as inclusive or exclusive. It is applied
   inclusively, matching the "reaches 1" wording of the DFBETA rule.
   `inventory_growth` carries no baseline materiality classification at 0.191, so
   it has none to lose; this is recorded rather than counted as a pass.
3. H1 gate comparisons are exact rather than tolerance-based. No observed value
   is near a boundary, so nothing turns on it here.

## 10. Next

1. The article's 5,000-replication useless-factor bootstrap, which would make
   roughly half the published-target registry auditable.
2. H2 temporal extension and H3 regime stability, both of which the acquired
   inputs support to 2025-12.
3. The 60-month standalone-second-pass floor remains an open decision and is
   still uncontaminated by any regime estimate.
