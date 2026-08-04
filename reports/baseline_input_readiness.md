# Baseline Input Readiness Report

Milestone: Empirical Input Acquisition and Baseline Reconstruction.
Date: 2026-08-02. Revised 2026-08-02 after acquiring the q-factor and
Pastor-Stambaugh liquidity comparators; see section 14 for the revision note.
Article: Maio and Santa-Clara, *JFQA* 52(3), 927-961, DOI `10.1017/S002210901700028X`.

**Verdict: PARTIAL.**

Rate and market inputs are ready. The seven anomaly decile families are available
from the original author source but only in a post-publication vintage, and one
registered portfolio set is unavailable at any vintage. Section 10 states exactly
which replication stages can proceed.

This report contains no empirical conclusion about the article. Every numerical
comparison below is an input-identification diagnostic.

---

## 1. Available exact inputs

**None.** No input in this design currently qualifies as exact.

An input is exact only when the article identifies the source file well enough
that a third party can retrieve the same bytes. The article names institutions
and people, never files. The closest case is recorded below and still falls
short.

| Candidate | Why it is not exact |
|---|---|
| Kenneth French one-month Treasury-bill return (`RF`) | The article names the library and the concept, which map to a single public column, but gives no file name and no archive vintage. Recorded as `closest to an exact input`. |
| Federal funds rate | "the St. Louis Federal Reserve Bank" names a provider, not a series code, vintage, seasonal-adjustment status, or aggregation rule. |
| 3-month Treasury-bill rate | The phrase "3-month TB rate" does not distinguish the secondary-market, auction-based, and constant-maturity variants. |
| Seven anomaly decile families | "All the portfolio return data are obtained from Lu Zhang" names a person. No file, no vintage, no formation rule. |
| Comparator factors | Providers named without files or vintages. The article also does not say which of the three liquidity columns `LIQ` is, or in which units. |

Evidence: `research/publication_evidence_freeze.md`,
`research/rate_definition_evidence.csv`,
`research/portfolio_definition_evidence.csv`.

## 2. Available documented reconstructions

All acquired, checksummed, and frozen.

| Input | Source | Vintage | Coverage | Role |
|---|---|---|---|---|
| `FEDFUNDS` | FRED | `fred_current_retrieved_2026-08-01` | 1954-07 to 2026-06, 864 obs, 0 missing | Primary short rate |
| `TB3MS` | FRED | `fred_current_retrieved_2026-08-01` | 1934-01 to 2026-06, 1110 obs, 0 missing | Alternative short rate |
| `DTB3` | FRED | `fred_current_retrieved_2026-08-01` | 1954-01 to 2026-07, 18934 obs, 799 missing | Sensitivity only |
| `DFF` | FRED | `fred_current_retrieved_2026-08-01` | 1954-07 to 2026-07, 26328 obs | Aggregation audit only |
| `F-F_Research_Data_Factors` | Kenneth French via Internet Archive | `publication_era_20170709` | 1926-07 to 2017-05, 1091 obs | Baseline market and risk-free |
| `F-F_Research_Data_Factors` | Kenneth French | `current_20260801` | 1926-07 to 2026-05, 1199 obs | Extension and revision analysis |
| `F-F_Momentum_Factor` | Kenneth French, both vintages | as above | 1927-01 onward | Comparator factor |
| `F-F_Research_Data_5_Factors_2x3` | Kenneth French, both vintages | as above | 1963-07 onward | Comparator factors |
| Seven anomaly decile families | global-q.org (Hou, Xue, and Zhang; the article's named "Lu Zhang" source) | `global_q_2025_retrieved_20260802` | 1967-01 to 2025-12, 708 continuous months each | Baseline test assets |
| CFP and IG deciles | global-q.org | same | same | Supplement target R1f |
| q-factors `R_ME`, `R_IA`, `R_ROE` | global-q.org (the article's named Lu Zhang source) | `global_q_2025_retrieved_20260802` | 1967-01 to 2025-12, 708 obs, 0 missing | q-factor comparator |
| Pastor-Stambaugh liquidity | Robert Stambaugh, Wharton, via Internet Archive | `publication_era_20170828` | 1962-08 to 2016-12, 653 obs, 65 sentinel | Baseline liquidity comparator |
| Pastor-Stambaugh liquidity | Robert Stambaugh, Wharton | `current_20260802` | 1962-08 to 2025-12, 761 obs, 65 sentinel | Extension liquidity comparator |

Every file carries provider, retrieval timestamp, observation range, units,
frequency, source notes, raw checksum, normalized checksum, vintage information,
and redistribution status in `artifacts/provenance/`. Raw provider bytes are
written once and the writer refuses to overwrite a differing file.

### Verified transformations

The monthly aggregation of both baseline rates is verified exactly, not assumed.

- `FEDFUNDS` equals the calendar-day mean of `DFF` rounded half-up to two
  decimals in **864 of 864** complete months.
- `TB3MS` equals the mean of the available business-day `DTB3` observations
  rounded half-up to two decimals in **846 of 846** complete months.
- Two competing rules are decisively rejected: a business-day-only mean of `DFF`
  matches in 38 percent of months (max error 0.29), and month-end `DTB3` matches
  in 7 percent (max error 2.81).
- `TB3MS` and an arithmetic aggregation of `DTB3` are **not identical**; they
  differ in 817 of 846 months before rounding, bounded exactly by half a
  reporting increment.

Detail: `reports/short_rate_source_report.md`,
`artifacts/data_quality/aggregation_audit.csv`,
`artifacts/data_quality/aggregation_differences.csv`,
`artifacts/data_quality/aggregation_decimal_check.csv`.

### Resolved ambiguities

Two ambiguities the article left open were resolved from the data itself.

**Timing convention.** The article does not say which month supplies the first
lagged rate. Both admissible variants were estimated. Only `pre_window_lag`,
which draws the 1971-12 level and yields 504 regression observations, reproduces
the published statistics; `within_window_lag` (503 observations) does not.

| Statistic | Published | `pre_window_lag` | `within_window_lag` |
|---|---|---|---|
| FEDFUNDS slope | 0.991 | 0.99053 (rounds to 0.991) | 0.99039 (rounds to 0.990) |
| FEDFUNDS t(slope) | 147.26 | 147.2696 | 147.2522 |
| TB3MS slope | 0.992 | 0.99162 (rounds to 0.992) | 0.99149 (rounds to 0.991) |
| TB3MS t(intercept) | 0.89 | 0.8893 | 0.9376 |
| TB3MS t(slope) | 153.18 | 153.1819 | 153.2502 |

`pre_window_lag` is now the primary convention in `configs/baseline.yaml`, with
`within_window_lag` retained as a labelled sensitivity. The convention is tested
automatically in `tests/test_baseline_inputs.py::TestTimingConvention`.

**Intercept units.** The article prints the AR intercept as `0.000` while
printing Table 1 innovation statistics in percent. The reconstructed intercept is
0.046 percentage points for FEDFUNDS, which cannot round to 0.000 in percentage
points but equals 0.00046 in decimal rate units and prints as `0.000`. The
intercept is therefore compared in decimal rate units; the slope, both t-ratios,
and R-squared are scale invariant. This resolves the Table 1 unit ambiguity
recorded as RATE_EV_03.

## 3. Missing inputs

| Input | Status | Consequence |
|---|---|---|
| Equal-weighted deciles for the seven families | **NOT LOCATED** | Article Table 7 cannot be attempted. Every archive member exposes only a `ret_vw` column. No substitute is used. |
| Publication-era vintage of the anomaly deciles | **NOT RECOVERABLE** | The earliest Internet Archive snapshot of the testing-portfolio page is 2019-11-24, after publication, and no archived portfolio ZIP predates the 2024 vintage. |
| Publication-era vintage of the q-factors | **NOT RECOVERABLE** | `global-q.org` was a parked domain in June 2017. This is consistent with the article stating the factors were provided by Lu Zhang directly rather than downloaded. |
| The article's `LIQ` extremes | **NOT REPRODUCED** | The published minimum of −10.14 and maximum of 21.01 are not produced by any column of any recoverable liquidity vintage. See section 3.1. |
| French 25-portfolio double sorts (SBM25, SIA25, SREV25) | Named source located, not acquired | Supplement target R1f. Straightforwardly acquirable; the supplement gives no file name, so the archive must be matched by definition. |
| FRED series metadata endpoint | Inaccessible | Units, seasonal adjustment, and notes are declared by this project rather than retrieved. Every declared field is audited against the payload. Supplying `FRED_API_KEY` would close this. |
| CRSP / Compustat access | Not confirmed and not assumed | No security-level portfolio construction was attempted. |

### 3.1 The liquidity factor: identified column, unexplained extremes

The article says only that "LIQ is obtained from Robert Stambaugh's Web page".
The file there carries three columns: the aggregate liquidity level, the
non-traded innovation, and the traded factor `LIQ_V`. All six candidates, three
columns by two scales, were compared with the article's Table 1 row.

The traded factor multiplied by 100 is the only candidate that is even close.

| Statistic | Published | Traded x 100, 2017 vintage | Traded x 100, 2026 vintage |
|---|---|---|---|
| Mean | 0.43 | 0.4337 | 0.4190 |
| Standard deviation | 3.57 | 3.4684 | 3.6066 |
| Autocorrelation | 0.09 | 0.1000 | 0.0938 |
| Minimum | -10.14 | **-12.4893** | **-13.5627** |
| Maximum | 21.01 | **11.0783** | **13.0124** |

Mean, dispersion, and persistence line up. The extremes do not, and the gap is
large: the article reports a maximum of 21.01, which is 5.9 standard deviations,
while the largest value anywhere in the full 1968 to 2016 history of the traded
factor is 11.08. **No column of any recoverable vintage produces 21.01.**

Three explanations are consistent with the evidence, and this project cannot
distinguish them:

1. the authors used a liquidity series constructed differently from the one on
   that page, for example the original predicted-beta sort of Pastor and
   Stambaugh (2003) rather than the simplified historical-beta sort the
   published file has used since at least 2008;
2. the authors used a vintage that is not archived, with different extremes;
3. the published Table 1 minimum and maximum for this row contain an error.

The comparison is recorded and no explanation is selected. `LIQ` enters R1e and
the secondary H1 comparator family as a documented reconstruction carrying this
caveat explicitly.

Detail: `artifacts/data_quality/liquidity_column_selection.csv`,
`artifacts/data_quality/comparator_source_compatibility.csv`.

### 3.2 q-factor source compatibility

| Factor | Published mean | Computed | Published sd | Computed | Statistics matching |
|---|---|---|---|---|---|
| `ME` | 0.31 | 0.3100 | 3.14 | 3.1259 | 2 of 5 |
| `IA` | 0.44 | 0.4475 | 1.87 | 1.8718 | 2 of 5 |
| `ROE` | 0.57 | 0.5562 | 2.62 | 2.6097 | 0 of 5 |

The same signature as the anomaly portfolios: right lineage, different vintage.
The mean of `ME` reproduces exactly at published precision. No factor matches on
all five statistics, so no q-factor comparator target can be labelled exact.

## 4. R1 targets unblocked by the acquired data

| Target | Status | Basis |
|---|---|---|
| **R1a** short-rate innovations | **Unblocked** and classified | Both rate reconstructions estimated on the exact baseline window under both timing conventions. |
| **R1b** first-pass betas | **Unblocked for reconstruction-labelled estimation** | Market factor, risk-free return, innovations, and 70 decile portfolios are aligned in the canonical panel. |
| **R1c** cross-sectional risk prices | **Unblocked for reconstruction-labelled estimation** | Depends only on R1b inputs; the no-intercept OLS second pass and the Shanken correction are explicit in the article. |
| **R1d** pricing errors and fit | **Unblocked for reconstruction-labelled estimation** | The article's fit definition is verified as `1 - var_N(alpha)/var_N(mean excess return)` (p.933, eq. 6), so the contract fallback is not needed. |
| **R1e** comparator models | **Unblocked for reconstruction-labelled estimation** | All six registered comparator models are available, one primary and five secondary: CAPM, FF3, C4, and FF5 at the publication-era French vintage, the q-factor model at the 2025 vintage, and the liquidity model at a publication-era vintage. The liquidity input carries the tail incompatibility recorded in section 3.1. |

## 5. R1 targets still blocked

| Target | Status | Blocking input |
|---|---|---|
| **R1f** supplementary robustness | **Blocked** | Table 7 is permanently blocked by the missing equal-weighted deciles. Table A.7 is blocked pending acquisition of the French 25-portfolio sets. Table A.4 requires equal-weighted CFP and IG variants, which are unavailable. |

No target is classified as contradicted. A completed source-compatible attempt
that fails to recover a published value is the only setting in which that label
may be used, and no such attempt has been made.

### R1a classification, per rate series

| Series | Timing variant | Classification |
|---|---|---|
| `FEDFUNDS` | `pre_window_lag` | `approximately_reproduced_under_documented_reconstruction` |
| `FEDFUNDS` | `within_window_lag` | `not_reproduced_under_documented_reconstruction_exact_input_missing` |
| `TB3MS` | `pre_window_lag` | `approximately_reproduced_under_documented_reconstruction` |
| `TB3MS` | `within_window_lag` | `not_reproduced_under_documented_reconstruction_exact_input_missing` |
| `DTB3` monthly mean | both | `not_attempted_no_published_target_for_this_series` |

Under `pre_window_lag`, 9 of 10 published statistics match at published precision
for FEDFUNDS and 10 of 10 for TB3MS. The single exception is the FEDFUNDS
`t(slope)` at 147.2696 against a published 147.26, a relative difference of 0.007
percent, which passes the registered relative band for t-ratios.

The intercept is compared in the article's decimal rate units, as the design
correction requires. An earlier revision of this report quoted 8 of 10 and 9 of
10 because the comparison code emitted the percentage-point estimate against a
decimal-unit published target, so the intercept row failed for every variant and
never reached the classifier. That defect is fixed and regression-tested; the
classification itself is unchanged.

**This is not exact replication and is not labelled as such.** The article does
not identify the source file it used, so source identity cannot be established.
Numerical proximity is not source identity. The classification logic enforces
this: `tests/test_baseline_inputs.py::TestReplicationClassification` asserts that
an exact numerical match without an exact input still returns
`approximately_reproduced_under_documented_reconstruction`.

## 6. Differences between historical and current vintages

Baseline window, 1972-01 to 2013-12, 504 months. Tolerance 0.005, half the
smallest published increment. Since the archives publish to two decimals, any
genuine revision is at least 0.01 and always exceeds the tolerance; the magnitude
columns carry the information.

| Column | Months revised | Share | Max abs. | Mean abs. |
|---|---|---|---|---|
| `RF` | 2 | 0.4% | 0.01 | 0.00004 |
| `Mkt-RF` | 318 | 63.1% | 0.15 | 0.0124 |
| `SMB` | 488 | 96.8% | 1.77 | 0.1081 |
| `HML` | 496 | 98.4% | 2.20 | 0.2007 |
| `Mom` | 487 | 96.6% | 1.78 | 0.0923 |
| `RMW` | 485 | 96.2% | 1.18 | 0.1706 |
| `CMA` | 484 | 96.0% | 1.34 | 0.1159 |

The risk-free return is effectively stable, the market factor is mildly revised,
and every other comparator factor is substantially revised. The current file is
therefore **not** a substitute for the publication-era file inside the baseline
window. Vintage assignment is fixed in
`reports/french_vintage_difference_report.md`: publication-era for R1b to R1f
and the baseline panel, current for the post-2013 extension and regime work.

Limitation: the snapshot is dated nine days after the article's download stamp
and an unknown interval after the authors retrieved their data. It is the closest
publicly recoverable vintage, not a certified copy, and is labelled
`closest_recoverable_publication_era_vintage`.

## 7. Portfolio families available for baseline estimation

All seven baseline families are available from the original author source. No
substitute from French, Stambaugh, or any other catalogue was used for any
family.

| Family | Label | Archive member | Portfolios | Sample | Status |
|---|---|---|---|---|---|
| Book-to-market | BM | `portf_bm_monthly_2025.csv` | 10 VW | 1967-01 to 2025-12 | Available |
| Earnings-to-price | EP | `portf_ep_monthly_2025.csv` | 10 VW | same | Available |
| Equity duration | DUR | `portf_dur_monthly_2025.csv` | 10 VW | same | Available |
| Long-term reversal | REV | `portf_rev_1_monthly_2025.csv` | 10 VW | same | Available; holding period resolved |
| Investment-to-assets | IA | `portf_ia_monthly_2025.csv` | 10 VW | same | Available |
| PPE + inventory investment | PIA | `portf_dpia_monthly_2025.csv` | 10 VW | same | Available |
| Inventory growth | IVG | `portf_ivg_monthly_2025.csv` | 10 VW | same | Available |

Every family is continuous over 708 months with no missing values.

**Reversal holding period.** The article states no holding period and the archive
offers 1-, 6-, and 12-month members. Total absolute distance to the published
Table 2 row is 1.97, 5.74, and 11.37 respectively, so the 1-month member is
selected. The other two remain registered as declared alternatives.

**Source compatibility.** The current vintage is close to but not identical with
the article's panels, which is the expected signature of the same source lineage
rebuilt on revised accounting and return data.

| Family | Published spread mean | Computed | Published sd | Computed |
|---|---|---|---|---|
| BM | 0.69 | 0.664 | 4.86 | 4.721 |
| EP | 0.58 | 0.499 | 4.83 | 4.773 |
| DUR | -0.52 | -0.547 | 4.34 | 4.490 |
| REV | -0.41 | -0.397 | 5.21 | 5.173 |
| IA | -0.42 | -0.428 | 3.62 | 3.596 |
| PIA | -0.49 | -0.507 | 3.00 | 3.014 |
| IVG | -0.36 | -0.346 | 3.15 | 3.170 |

Because no family matches at published precision on all five statistics, no
portfolio-dependent target can be labelled exact replication regardless of what
the pricing tests produce.

Full record: `research/anomaly_portfolio_availability.csv`,
`artifacts/data_quality/portfolio_source_compatibility.csv`,
`artifacts/data_quality/reversal_holding_period_selection.csv`.

## 8. Exact analyses permitted

**None.** No analysis may carry an exact-replication label under the current
evidence, because no input is exact. This holds for every layer, including R1a,
where the published AR statistics are closely recovered.

An exact label becomes available only if the authors supply their input files, or
if a source-file-level identification is obtained that the publication itself does
not provide.

## 9. Reconstruction-only analyses permitted

Every analysis below is permitted with a mandatory `documented_reconstruction`
label on each output.

1. R1a short-rate innovation audit for FEDFUNDS and TB3MS under both timing
   conventions, with the DTB3 aggregation as a sensitivity.
2. R1b first-pass betas for all 70 decile portfolios on the market factor and the
   selected short-rate innovation, 1972-01 to 2013-12.
3. R1c no-intercept OLS cross-sectional risk prices with the Shanken correction.
4. R1d pricing errors, the article's cross-sectional fit metric, the chi-square
   pricing-error statistic, and the bootstrap.
5. R1e comparator models: CAPM, FF3, C4, and FF5 on the publication-era French
   vintage, the q-factor model on the 2025 vintage, and the liquidity model on
   the publication-era liquidity vintage with its recorded tail caveat.
6. H1 incremental-pricing materiality against the ex ante CAPM comparator.
7. H4a, H4b, and H4c weak-factor diagnostics on the frozen panel.
8. The revised-history vintage audit, clearly separated from the baseline verdict.

9. The H1 secondary adversarial comparison against the strongest observed
   registered non-short-rate comparator, which now draws on the complete field
   of five secondary models rather than a truncated one.

Not permitted until further acquisition: any equal-weighted result and any
double-sorted result.

## 10. Final verdict

**PARTIAL.**

Rate and market inputs are ready, verified, and frozen. The canonical panel
passes every declared check. Original anomaly portfolios remain unavailable at
the publication vintage, and one registered portfolio set is unavailable at any
vintage.

### Replication stages that can proceed now

| Stage | Can proceed | Label required |
|---|---|---|
| R1a short-rate innovation audit | Yes | documented reconstruction |
| R1b first-pass betas, 70 portfolios | Yes | documented reconstruction |
| R1c cross-sectional risk prices | Yes | documented reconstruction |
| R1d pricing errors and article fit metric | Yes | documented reconstruction |
| R1e CAPM, FF3, C4, FF5 comparators | Yes | documented reconstruction |
| R1e q-factor comparator | Yes | documented reconstruction; 2025 vintage only |
| R1e liquidity comparator | Yes | documented reconstruction; tail incompatibility recorded |
| H1 secondary adversarial comparison | Yes | complete field of five secondary comparators |
| R1f Table 7 equal-weighted | No | permanently blocked at current sources |
| R1f Table A.7 double sorts | No | blocked on acquisition |
| R1f Table A.4 CFP and IG | Value-weighted only | equal-weighted variants unavailable |
| H1 materiality against CAPM | Yes | documented reconstruction |
| H4a, H4b, H4c weak-factor diagnostics | Yes | documented reconstruction |
| H2, H3 post-2013 extension and regimes | Yes, to 2025-12 | extension endpoint binds at the portfolio sample |

### Binding sample constraints

- Baseline panel: 1972-01 to 2013-12, 504 months, complete.
- Extension endpoint: **2025-12**, set by the anomaly portfolio panels, not the
  2026-06 rate and 2026-05 factor data. `configs/extensions.yaml` now records
  `latest_common_month: 2025-12` and lists the seven acquired anomaly decile
  families as the compatible portfolio sets, replacing the five 25-portfolio
  double sorts that are not acquired at any vintage.
- `research/regime_registry.csv` still ends `post_tightening_easing` and
  `post_pandemic_cycle_combined` at 2026-06. Those rows are not owned by this
  report and remain to be corrected to the 2025-12 panel endpoint.
- Under the frozen regime-eligibility floors, standalone regime-specific second
  passes are available for `conventional_pre_elb` and `elb_qe` only. The three
  post-2020 regimes fall below the 36-month floor and enter pooled interactions
  only. See `reports/design_correction_changelog.md`, correction 8.

## 11. Canonical baseline panel

`data/processed/baseline_panel.parquet` and `.csv`,
SHA-256 `f1354c66d8983bfe…` (parquet).

- 504 months, 1972-01 to 2013-12, 78 numeric columns.
- 1 market excess return, 1 risk-free return, 3 short-rate levels, 3 short-rate
  innovations, 70 anomaly portfolio excess returns.
- Constant `source_vintage_id` and `replication_status` columns; per-column
  source, vintage, units, and exact-or-reconstructed status in
  `artifacts/provenance/baseline_panel_column_metadata.csv`.

All 14 validation checks pass: unique monthly keys, monotonically increasing
dates, no internal month gaps, no observation before the window start, no
observation after the frozen endpoint, no missing values, no infinite values, no
implicit forward filling, return units, rate units, risk-free units, no
innovation timing shift, no market-factor timing shift, and same-month risk-free
subtraction in every excess return.

Record: `artifacts/data_quality/baseline_panel_validation.json`.

## 12. Acceptance gates

| Gate | Status | Evidence |
|---|---|---|
| All raw public inputs have checksums and source metadata | **PASS** | `artifacts/provenance/` manifests for 4 FRED series, 6 French archive vintages, 2 q archives, 9 portfolio panels |
| Short-rate aggregation is verified | **PASS** | 864/864 and 846/846 exact-decimal matches; two competing rules rejected |
| The timing convention is tested automatically | **PASS** | `tests/test_baseline_inputs.py::TestTimingConvention`, 7 tests including no-lookahead and shift-detection |
| R1a is classified without conflating reconstruction and replication | **PASS** | Classification enforced in code and asserted in `TestReplicationClassification` |
| Market and risk-free vintages are frozen | **PASS** | `publication_era_20170709` and `current_20260801`, both checksummed and compared |
| Comparator factor sources are frozen with explicit availability | **PASS** | q-factors and liquidity acquired; liquidity at a publication-era and a current vintage; the `LIQ` column and scale identified empirically and the unreproduced extremes recorded |
| Every anomaly family has an explicit availability status | **PASS** | `research/anomaly_portfolio_availability.csv`, 14 rows including the unavailable equal-weighted set |
| The canonical panel passes unit, date, missingness, and alignment checks | **PASS** | 14 of 14 checks |
| No licensed database access is assumed | **PASS** | No CRSP, Compustat, or WRDS access used or assumed; no security-level construction attempted |
| No result paragraph has been written | **PASS** | Every comparison is an input-identification diagnostic; the manuscript's planned-results sections are unchanged |

## 13. Recommended next actions

1. Contact the authors for the original portfolio and factor files. This is the
   only route to an exact-replication label on any portfolio-dependent target.
2. Acquire the three French 25-portfolio double sorts to unblock Table A.7.
3. Configure `FRED_API_KEY` to convert declared FRED metadata into retrieved
   metadata.
4. Correct the regime rows in `research/regime_registry.csv` that still end at
   2026-06 so that they respect the 2025-12 portfolio endpoint.
   `configs/extensions.yaml` has already been updated.
5. Ask the authors which liquidity series they used. That is the only way to
   close the `LIQ` extremes question.

## 14. Revision note, 2026-08-02

The q-factor and Pastor-Stambaugh liquidity comparators were acquired after this
report was first issued. Three things changed.

- **R1e moved from partially blocked to unblocked** for reconstruction-labelled
  estimation. All six registered comparator models are now available, the CAPM
  primary comparator plus the five secondary models, so the H1 secondary
  adversarial comparison draws on a complete field instead of a truncated one. A
  truncated field would have made that comparison easier to pass and would have
  had to be disclosed as a limitation. `configs/baseline.yaml` now lists all six
  under `comparators:`, so the configuration and
  `research/comparator_model_registry.csv` agree.
- **A correction.** An earlier record in this project stated that the article's
  footnote 18 URL for Stambaugh's page no longer resolves. It does resolve. The
  earlier claim came from PDF text extraction rendering the tilde as U+223C
  TILDE OPERATOR rather than ASCII, which produced an unreachable URL. The
  affected records in `research/portfolio_definition_evidence.csv`,
  `research/publication_evidence_freeze.md`, and
  `research/data_access_matrix.csv` are corrected and marked as corrections.
- **A new open incompatibility** was found and recorded rather than resolved:
  the article's `LIQ` minimum and maximum are not produced by any column of any
  recoverable liquidity vintage. See section 3.1.
