# Temporal Extension Report

Milestone 9. Date: 2026-08-05.
Article: Maio and Santa-Clara, *JFQA* 52(3), 927-961.

**Every result carries the label `documented_reconstruction`.** No input in this
design is an exact article input.

**Registered classification: H2 `post_publication_compatibility_unsupported`.**
All three registered gates fail.

## 1. Design, and why the vintage question had to be settled first

The baseline uses publication-era factor vintages; any extension must use the
current vintage. Comparing the two directly would confound a change over *time*
with a change in *data vintage*, and the milestone's acceptance gate requires
that revised historical data be isolated from vintage-consistent results.

Three evaluations therefore run, sharing one code path:

| Evaluation | Months | Vintage | Purpose |
|---|---|---|---|
| Locked baseline | 1972-01 to 2013-12 | publication era | The frozen replication baseline |
| Revised history | 1972-01 to 2013-12 | current | Same months, later vintage |
| Refitted extension | 2014-01 to 2025-12 | current | Same vintage, later months |

Differencing the revised history against the locked baseline isolates the
**vintage** effect. Differencing the refitted extension against the revised
history isolates the **temporal** effect. The registered gates are evaluated on
the second comparison, so no revised historical datum enters the temporal
verdict.

A fourth evaluation, **frozen-parameter**, applies the 2013-12 parameters to the
extension months without re-estimating anything: the AR(1) intercept and slope
that build the innovation, the first-pass betas, and the second-pass risk
prices. Nothing estimated after 2013-12 enters it, so it is genuinely out of
sample with respect to the article.

The test assets are the same 2025-vintage decile panels in every window, so
portfolio construction is constant across the comparison.

## 2. Results

| Evaluation | Months | lambda_market | lambda_rate | Shanken t | RMSE | Article fit |
|---|---|---|---|---|---|---|
| Locked baseline | 504 | 0.6012 | **-0.6985** | -2.86 | 0.1004 | 0.5439 |
| Revised history | 504 | 0.6030 | **-0.6985** | -2.86 | 0.1004 | 0.5440 |
| Frozen parameter on 2014-2025 | 144 | 0.6012 | -0.6985 | -2.86 | **0.4463** | **-0.6913** |
| Refitted extension | 144 | 0.9972 | **-0.0825** | -1.49 | 0.1918 | 0.4502 |

## 3. The vintage effect is negligible; the temporal effect is not

| Comparison | lambda_rate change | RMSE relative change | Max abs. spread change |
|---|---|---|---|
| **Vintage** (locked vs revised history) | -0.0000 | -0.003 percent | 0.0007 |
| **Temporal** (revised history vs refitted extension) | **+0.6159** | **+91.0 percent** | **0.9881** |
| Combined, confounded, for completeness | +0.6159 | +91.0 percent | 0.9876 |

The vintage contribution is negligible on every dimension. Recomputing the
baseline window on a nine-year-later vintage leaves the rate risk price and the
cross-sectional RMSE unchanged to four decimals; moving to the post-publication
window moves the risk price by 88 percent of its value.

It is this small because the federal funds series is not revised and both
panels read the same frozen file, so the rate innovation is identical across
vintages by construction, and the test assets are the same portfolio vintage in
every window. Only the market and risk-free factors differ, and over these
months that difference does not move the cross-section measurably. An earlier
version of this table reported a vintage contribution of +0.0011 on the risk
price; that was an artifact of a timing error in the revised-history
autoregression, corrected in the peer-review revision.

This is the separation the acceptance gate asks for, and it is clean: the
post-2013 change cannot be attributed to revised historical data.

## 4. The registered gates

| Gate | Bound | Observed | Result |
|---|---|---|---|
| Sign compatibility of fitted-premium spreads | all families | 2 of 7 compatible | **fail** |
| Fitted-premium magnitude change | within 0.25 monthly pp | 1 of 7 within | **fail** |
| RMSE deterioration | at most 10 percent | +91.0 percent | **fail** |

Per family, the rate-attributable fitted-premium spread
`pi(decile_10) - pi(decile_01)`:

| Family | Locked baseline | Revised history | Refitted extension | Temporal change | Sign kept |
|---|---|---|---|---|---|
| `book_to_market` | 0.5353 | 0.5353 | -0.3908 | -0.9261 | no |
| `earnings_to_price` | 0.4071 | 0.4077 | -0.5804 | -0.9881 | no |
| `equity_duration` | -0.4617 | -0.4622 | 0.4565 | +0.9187 | no |
| `long_term_reversal` | -0.2992 | -0.2993 | 0.6536 | +0.9529 | no |
| `ppe_investment` | -0.2981 | -0.2984 | 0.5600 | +0.8583 | no |
| `investment_to_assets` | -0.3283 | -0.3291 | -0.0251 | +0.3039 | yes |
| `inventory_growth` | -0.1908 | -0.1911 | -0.0553 | +0.1358 | yes |

The temporal change is measured from the revised history, which is the
registered comparator for that gate. Five of seven families reverse sign. The two that keep their sign do so with
spreads that have collapsed toward zero.

## 5. The obvious benign explanation, and why it does not hold

The extension window contains the effective lower bound, so the short-rate
factor has far less variation in it. That invites the reading that H2 fails
because the factor is no longer identified rather than because the relation
changed.

| | Baseline | Extension |
|---|---|---|
| Rate level, mean | 5.723 | 1.844 |
| Innovation standard deviation | 0.5855 | 0.1707 |
| Months with the rate below 0.5 percent | 62 of 504 (12.3 percent) | 60 of 144 (41.7 percent) |

The innovation is indeed only 29 percent as variable. But the registered
identification gate is not the factor's own variance; it is the cross-sectional
dispersion of *standardized* exposures, which is scale aware by construction.

| Window | Standardized rate dispersion | Standardized market dispersion | Share | H4a gate, floor 0.10 |
|---|---|---|---|---|
| Baseline | 0.1341 | 0.5280 | 0.2540 | pass |
| Extension | 0.3310 | 0.5707 | **0.5800** | pass |

The extension window clears the identification floor **more** comfortably than
the baseline does, not less. Smaller factor variation is offset by larger betas,
which is exactly what the standardized measure is designed to capture. The
temporal result is therefore not attributable to a weakly identified factor
under the registered gate.

The extension risk price is nonetheless imprecise in its own right: -0.0825 with
a Shanken t of -1.49, against -0.6985 and -2.86 in the baseline. A collapsed
point estimate with a wide interval is consistent both with a relation that has
weakened and with one estimated on 144 months instead of 504. This report does
not choose between those.

## 6. The frozen-parameter evaluation

Applying the 2013-12 model unchanged to 2014-2025 gives an RMSE of 0.4463
against 0.1004 in the baseline window, and an article cross-sectional fit of
**-0.6913**. A negative fit under this metric means the fitted premia explain
less of the cross-sectional variation in average returns than a constant would.

This is the genuinely out-of-sample number, and it is the one that matters for a
claim of post-publication generalization.

## 7. What this does and does not establish

It establishes that, under the registered standard and on these documented
reconstruction inputs, post-2013 estimates are not compatible with the baseline:
signs reverse, magnitudes move far beyond the predeclared bound, and pricing-error
performance deteriorates by an order of magnitude more than the bound allows.
It also establishes that this is not a data-vintage artifact and not, by the
registered gate, an identification artifact.

It does not establish that the article was wrong about its own sample. The
baseline window reproduces the article's design closely, and H4a, H4b and H4c
all pass there. A relation that holds in one period and not the next is a
statement about stability, not about the original estimate.

It does not isolate a cause. The extension window contains the effective lower
bound, the pandemic response, and the fastest tightening cycle since the early
1980s. Attributing the change to any of those requires the regime analysis in
Milestone 10, which is not run here.

Every input remains a documented reconstruction on a post-publication portfolio
vintage. That caveat applies to the baseline and the extension equally, which is
why the comparison between them is more informative than either alone.

## 8. Generated artifacts

| Artifact | Contents |
|---|---|
| `data/processed/extension/monthly_panel.parquet` | 144 months, 2014-01 to 2025-12, current vintage |
| `data/processed/extension/revised_history_panel.parquet` | 504 baseline months on the current vintage |
| `artifacts/tables/extension/temporal_evaluation.csv` | All four evaluations |
| `artifacts/tables/extension/fitted_premium_spreads.csv` | Per-family spreads and both decompositions |
| `artifacts/tables/extension/vintage_decomposition.csv` | Vintage, temporal, and combined comparisons |
| `artifacts/diagnostics/h2_temporal_stability.json` | Gate outcomes and the classification |
| `artifacts/provenance/extension_panels.json`, `temporal_extension.json` | Input and output checksums |

## 9. Next

1. Milestone 10, monetary regimes, which is where the post-2013 change can be
   located in policy time rather than merely in calendar time.
2. The 60-month standalone-second-pass floor decision, which constrained what
   Milestone 10 could deliver and was, as of this report, the binding open
   question: under the floors frozen at the time, only two of six regimes
   supported a standalone second pass. *Resolved in Milestone 10: the floor is
   now 72 months, and the same two regimes are the two that clear it. See
   `reports/design_correction_changelog.md`.*
