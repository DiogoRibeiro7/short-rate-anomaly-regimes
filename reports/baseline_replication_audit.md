# Baseline Replication Audit

Milestones 5 to 7: first-pass estimates, cross-sectional pricing, and the
published-result audit.
Date: 2026-08-04.
Article: Maio and Santa-Clara, *JFQA* 52(3), 927-961, DOI `10.1017/S002210901700028X`.

**Every result below carries the label `documented_reconstruction`.** No input in
this design is an exact article input, so no target can receive an
exact-replication label at any recovery rate. See
`reports/baseline_input_readiness.md` section 1.

## 1. What was estimated

Eight models on eight asset sets, 64 systems in total, on the frozen canonical
panel of 504 months from 1972-01 to 2013-12.

| Model | Factors |
|---|---|
| `capm` | RM |
| `market_plus_fedfunds_innovation` | RM, federal funds innovation |
| `market_plus_tbill_innovation` | RM, Treasury-bill innovation |
| `fama_french_3` | RM, SMB, HML |
| `carhart_4` | RM, SMB, HML, UMD |
| `fama_french_5` | RM, SMB, HML, RMW, CMA |
| `q_factor` | RM, ME, IA, ROE |
| `liquidity` | RM, SMB, HML, LIQ |

Asset sets: the seven value-weighted decile families separately, and the joint
70-portfolio system.

Estimators, all as the article defines them:

- First pass: OLS with an intercept, article equation (3), contemporaneous
  alignment of the return and the innovation.
- Second pass: no-intercept OLS of average excess returns on full-sample betas,
  article equation (4).
- Uncertainty: the Shanken (1992) covariance, applied to both the risk prices and
  the pricing errors.
- Specification test: `alpha' var(alpha)^+ alpha ~ chi2(N - K)`, article
  equation (5), with a pseudo-inverse.
- Fit: `1 - var_N(alpha) / var_N(mean excess return)`, article equation (6), the
  centred cross-sectional variance ratio. This is **not** the uncentred
  contract fallback; the two are separate labels and the second pass has no
  intercept, so they genuinely differ.
- Constrained fit: article equations (7) and (8), computed only for models whose
  factors are all traded excess returns. The article states at page 934 that the
  restriction does not apply to the ICAPM, and the code enforces that.

Two implementation notes. The first-pass HAC lag rule is chosen automatically
because the article states none; it affects only first-pass t-statistics, which
the article does not tabulate, and affects no audited cell. The pseudo-inverse
cutoff is a declared project value of `1e-15`, recorded with every artifact,
because the article does not state one.

## 2. What could be audited

`research/published_target_values.csv` holds 212 registry rows transcribed from
Tables 3, 4, 6, and A.1 and independently re-verified cell by cell against the
source text. After collapsing rows that repeat a point estimate under two
printed uncertainty measures, that is **123 unique published cells**, of which
**123 were compared**.

A cell counts as recovered when it agrees with the article to the precision the
article prints, that is within half of the last printed increment.

| Statistic | Cells | Recovered | Share | Median abs. difference | Max abs. difference |
|---|---|---|---|---|---|
| `lambda_market` | 29 | 20 | 0.690 | 0.0033 | 0.0117 |
| `lambda_rate` | 16 | 3 | 0.188 | 0.0137 | 0.0901 |
| `r2_ols` | 29 | 3 | 0.103 | 0.0251 | 0.2863 |
| `chi_square` | 29 | 0 | 0.000 | 0.7458 | 7.4110 |
| `r2_constrained` | 5 | 1 | 0.200 | 0.0162 | 0.0492 |
| Comparator factor prices | 15 | 2 | 0.133 | 0.0193 | 0.1350 |

## 3. Layer classification

| Layer | Cells | Recovered | Classification |
|---|---|---|---|
| **R1a** short-rate innovations | 10 per rate | 9/10 and 10/10 | `approximately_reproduced_under_documented_reconstruction` |
| **R1b** first-pass betas | 0 | — | `no_published_statistic_level_target` |
| **R1c** risk prices | 45 | 23 | `partially_recovered_under_documented_reconstruction` |
| **R1d** pricing errors and fit | 58 | 3 | `partially_recovered_under_documented_reconstruction` |
| **R1e** comparator models | 20 | 3 | `partially_recovered_under_documented_reconstruction` |

**R1b has no statistic-level target.** The article plots first-pass betas in
Figure 3 and reports beta-times-lambda decompositions for the extreme deciles in
Table 5, but tabulates no beta. There is nothing to compare cell by cell, so the
layer is evidenced only through the layers that consume it. This is a property
of what the article published, not a gap in this reconstruction.

## 4. Reading the numbers honestly

The recovery rate varies sharply by statistic, and the pattern is informative
about the reconstruction rather than about the article.

**Risk prices on the market factor reproduce well.** 20 of 29 cells land inside
the published rounding, with a median absolute difference of 0.0033 monthly
percentage points against values printed to two decimals. All 29 agree in sign.

**Risk prices on the rate factor reproduce in sign and magnitude but less often
at printed precision.** All 16 cells are negative, as published. The median
absolute difference is 0.0137, roughly four times that of the market factor,
which is what one expects of the parameter that depends most on the exact
cross-section of test assets.

**The chi-square statistic reproduces least well, and this is expected.** It
inverts a 10-by-10 or 70-by-70 pricing-error covariance through a pseudo-inverse.
That construction amplifies small differences in the residual covariance, so a
portfolio vintage difference that moves a risk price by 0.003 can move the
statistic by a whole unit. Zero of 29 cells land inside the published rounding,
while the statistics remain in the same region as the published ones.

**The common cause is the known portfolio vintage.** The anomaly decile panels
come from the original author source but in a 2025 rebuild, and
`artifacts/data_quality/portfolio_source_compatibility.csv` already records that
none of the seven families matches its published Table 2 row on all five
descriptive statistics. A cross-sectional estimator applied to slightly
different portfolios produces slightly different cells. Nothing in this audit
distinguishes that explanation from an estimator discrepancy, and this report
does not claim to.

**What this audit does not establish.** It does not confirm the article, and it
does not contradict it. A contradiction label requires a completed attempt on
source-compatible inputs, and the inputs here are documented reconstructions.
The partial-recovery classifications say exactly that and no more.

## 5. Not attempted

- **The article's empirical p-values.** Every bootstrap p-value in Tables 3, 4, 6,
  and A.1 comes from the article's 5,000-replication useless-factor bootstrap
  (Internet Appendix Section 4). That procedure is not implemented in this pass,
  so those cells are recorded as `not_attempted_bootstrap_not_implemented`
  rather than compared against an asymptotic value that would not be the same
  object.
- **Table 5, Tables 7 to 9, and Appendix Tables A.2 to A.14.** Outside the scope
  of this pass.
- **Equal-weighted results.** Permanently blocked at the current sources.

## 6. Generated artifacts

| Artifact | Contents |
|---|---|
| `artifacts/estimates/time_series/baseline_first_pass_betas.parquet` | Betas, first-pass alphas and R-squared for every model, asset set, and asset |
| `artifacts/estimates/cross_section/baseline_second_pass.parquet` | Risk prices, Shanken standard errors and t-statistics, fit, chi-square for all 64 systems |
| `artifacts/estimates/cross_section/baseline_pricing_errors.parquet` | Pricing error and fitted mean return per asset |
| `artifacts/tables/cross_section/baseline_risk_prices.csv` | The audit-ready summary table |
| `artifacts/audit/published_target_audit.csv` | Cell-level comparison against all 212 registry rows |
| `artifacts/audit/replication_layer_classification.csv` | The layer classification above |
| `artifacts/provenance/baseline_replication_run.json` | Input checksums, model definitions, estimator declarations, output checksums |
| `artifacts/provenance/comparator_panel.json` | Comparator factor panel provenance |

## 7. Next

1. Implement the article's bootstrap so the empirical p-values become auditable.
2. Extend the audit to Table 5 and the remaining appendix tables.
3. H1 incremental-pricing materiality against the ex ante CAPM comparator, which
   the acquired inputs now support in full.
4. H4a, H4b, and H4c weak-factor diagnostics, whose spanning gate is implemented
   but has no production caller yet.
