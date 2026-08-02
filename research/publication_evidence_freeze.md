# Publication Evidence Freeze

Milestone: Empirical Input Acquisition and Baseline Reconstruction, Task 2.
Date: 2026-07-31.

Source documents, already hashed in `artifacts/evidence/article_manifest.json`:

- Article: Maio and Santa-Clara, "Short-Term Interest Rates and Stock Market
  Anomalies", *Journal of Financial and Quantitative Analysis* 52(3), 927-961,
  DOI `10.1017/S002210901700028X`. Local file `references/private/maio2017.pdf`,
  SHA-256 `2666ea25fb1cb2dde9d7e613c088a649757422e0ed44384008143e5424f72fda`.
- Internet Appendix: `suppl data/JFQA_ms16881_Maio_Santa_Clara_InternetAppendix.pdf`
  inside the publisher supplement ZIP, SHA-256
  `df4f5418e44cf632dbf6de0e7b0bc260850031144cd316e16f8f6ee2b7fbcae4`.

Machine-readable records:

- `research/rate_definition_evidence.csv` — nine rate-definition records.
- `research/portfolio_definition_evidence.csv` — sixteen portfolio and factor
  records.

Rule applied throughout: **no definition is recorded that the article or
supplement does not provide.** Where a field is not stated, the record says
"not stated" rather than supplying a plausible value.

## 1. What the publication actually fixes

The article states the following without ambiguity.

- The two ICAPM state variables are the federal funds rate and the 3-month
  Treasury-bill rate (p.930, p.932, p.935).
- Innovations are AR(1) residuals with an intercept, and the residual is written
  out explicitly: `FFR-tilde_{t+1} = FFR_{t+1} - 0.000 - 0.991 FFR_t` (p.935).
- The published AR(1) estimates are

  | Rate | Intercept | t | Slope | t | R-squared |
  |---|---|---|---|---|---|
  | FFR | 0.000 | 0.99 | 0.991 | 147.26 | 0.98 |
  | TB | 0.000 | 0.89 | 0.992 | 153.18 | 0.98 |

- The first pass aligns the return and the innovation contemporaneously,
  equation (3) on p.932. There is no lag or lead in the published specification.
- The second pass is a no-intercept OLS cross-sectional regression of average
  excess returns on first-pass betas, equation (4) on p.932, with the
  no-intercept choice justified on p.932-933.
- Uncertainty uses Shanken (1992) standard errors for both risk-price
  t-statistics and the pricing-error covariance (p.933).
- The joint statistic is `alpha' var(alpha)^pseudo-inverse alpha ~ chi2(N - K)`,
  equation (5) on p.933.
- The fit metric is `R2_OLS = 1 - var_N(alpha_i) / var_N(R_i - R_f)`, equation
  (6) on p.933, a centred cross-sectional variance ratio that may be negative.
  A constrained variant, equations (7) and (8) on p.934, applies only to
  comparator models with traded factors and explicitly not to the ICAPM.
- The bootstrap uses 5,000 replications with returns and factors resampled
  independently under a useless-factor null (p.933-934).
- The baseline sample is January 1972 to December 2013, and the start date is
  set by the availability of the Hou-Xue-Zhang factors (p.935).
- The restricted-sample robustness endpoint is 2006:12 (Internet Appendix
  Section 2.2).
- The test assets are value-weighted deciles for seven anomalies: BM, EP, DUR,
  REV, IA, PIA, IVG (p.936-937).
- Portfolio excess returns use the Kenneth French 1-month Treasury-bill return
  (p.937).

Consequence for `research/fit_metric_contract.md`: the article's fit definition
is **verified**, so the mechanical uncentred fallback is not used for baseline
targets. The contract has been updated accordingly.

## 2. What the publication does not fix

These are the frozen ambiguities. Each one is recorded against the specific
record in the evidence CSVs and each one blocks an exact-replication label.

### 2.1 Rate series (blocks R1a)

- **Provider without series.** "The data on the FFR and the 3-month TB rate are
  from the St. Louis Federal Reserve Bank" (p.935) names an institution. It does
  not give a series code, a database, a vintage, a seasonal-adjustment status,
  or a daily-to-monthly aggregation rule.
- **"3-month TB rate" is not unique.** The St. Louis Federal Reserve Bank
  publishes a secondary-market rate, an auction-based rate, and a
  constant-maturity rate at this maturity, monthly and daily. The article does
  not distinguish them.
- **Units.** Table 1 heads every column "(%)", but the same table mixes monthly
  percent returns (RM at 0.53) with rate-factor values (FFR-tilde standard
  deviation 0.59). The article never says the rate factor is measured in
  annualized rate percentage points rather than monthly percent. This is a unit
  ambiguity that a reconstruction must resolve by audit, not by assumption.
- **First regression pair.** The article does not say which month supplies the
  first lagged rate. If the AR(1) uses regressor months 1972:01-2013:11, the
  innovation exists for 503 months; if the rate level is taken from 1971:12, it
  covers all 504 baseline months.
- **Rounded or unrounded coefficients.** The residual definition on p.935 is
  written with the rounded values 0.000 and 0.991. The article does not say
  whether the empirical factor used those rounded values or the unrounded
  estimates.
- **No daily source is named anywhere.** Neither the article nor the appendix
  mentions a daily rate series or an aggregation rule from daily to monthly.
  Any daily series is therefore a sensitivity input only.

### 2.2 Test-asset portfolios (blocks R1b, and through it R1c, R1d, R1e, R1f)

- **Attribution to a person, not a file.** "All the portfolio return data are
  obtained from Lu Zhang" (p.937). No file name, no URL, no vintage, no version
  date.
- **No formation rules.** The article gives no breakpoints, no exchange screens,
  no formation month, no rebalancing frequency, no holding period, no accounting
  lag, and no delisting-return treatment for any of the seven families. The
  anomaly literature is cited for the economic phenomenon, not for the
  construction.
- **Equity duration is the most exposed.** DUR requires a cash-flow forecasting
  model. The article cites Dechow, Sloan, and Soliman (2004) for the anomaly but
  does not state which duration formula or parameterisation produced the
  deciles.
- **Comparator factors.** RM, SMB, HML, UMD, RMW, and CMA are attributed to
  Kenneth French's library with a URL in footnote 17 but no file name and no
  vintage. LIQ is attributed to Robert Stambaugh's web page. The footnote 18 URL
  does resolve; an earlier record in this project reported it as dead, which was
  an artifact of PDF text extraction rendering the tilde as U+223C rather than
  ASCII. The article does not say whether LIQ is the traded factor, the
  innovation series, or the aggregate level. ME, IA, and ROE are attributed to Lu
  Zhang.
- **Supplement portfolios.** The double-sorted 25-portfolio sets are attributed
  to "Kenneth French's website" (Internet Appendix Section 2.6) without a file
  name. The appendix labels one of them "size and asset growth", which does not
  match a French archive title verbatim, so the archive has to be matched by
  definition rather than by name.

### 2.3 Estimator details not stated

- The first-pass residual covariance estimator and any Newey-West lag rule are
  not stated for equation (3).
- The numerical tolerance of the pseudo-inverse in equation (5) is not stated.
- The appendix does not say whether the restricted-sample AR(1) (Section 2.2) is
  re-estimated on 1972:01-2006:12 or carried over from the full sample.

## 3. Replication-target evidence status

`research/hypothesis_registry.csv` now carries `evidence_status`,
`evidence_locator`, and `blocking_ambiguity` for every row. The replication
targets read as follows.

| Target | Evidence status | Principal blocking ambiguity |
|---|---|---|
| R1a | Published target frozen; exact source file not named | Provider without series code, vintage, or aggregation rule; first AR regression pair not stated; rounded-versus-unrounded coefficients |
| R1b | Published target frozen; test-asset source not reproducible from the publication | Deciles attributed to a person; no formation rules; first-pass covariance estimator not stated |
| R1c | Published target frozen; estimator verified, inputs not frozen | Blocked only through its portfolio and factor inputs |
| R1d | Published target frozen; fit definition verified | Pseudo-inverse tolerance not stated |
| R1e | Published target frozen; comparator factor files not named | Providers named without files or vintages; the LIQ column and scale are unstated and were identified empirically after acquisition |
| R1f | Published target frozen; supplement inputs partially named | French double-sort archive not named; CFP and IG deciles attributed to a person |

The estimator layer of this replication is well specified. The **input** layer is
not. R1c and R1d are blocked only by the inputs they consume, not by any
remaining ambiguity in their own definitions.

## 4. Consequences carried into Tasks 3 to 9

1. No short-rate series can be labelled an exact article input. FEDFUNDS and
   TB3MS are documented reconstructions of a named concept. This is recorded in
   `research/short_rate_series_registry.csv` and is not changed by a successful
   numerical match against the published AR(1) coefficients.
2. A daily Treasury-bill series is a sensitivity input only, because no daily
   source and no aggregation rule appear in the publication.
3. The seven anomaly decile families cannot be reproduced from the publication
   alone at any level of effort. Task 7 therefore searches for the original
   author files first and records an explicit availability status per family
   rather than substituting a different catalogue.
4. The Kenneth French 1-month Treasury-bill return is the single rate input with
   an unambiguous mapping to one public series, and is therefore the strongest
   exact-input candidate in the whole design.
5. The article's fit metric is used directly; the fallback in
   `research/fit_metric_contract.md` is reserved for cases where the article
   definition does not apply.
