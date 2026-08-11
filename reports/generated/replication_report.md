# Replication Report

## Bibliographic Target And Versions

- Target: Paulo F. Maio, Pedro Santa-Clara. 2017-06. Short-Term Interest Rates and Stock Market Anomalies. Journal of Financial and Quantitative Analysis 52(3), 927-961.
- DOI: `10.1017/S002210901700028X`
- Evidence-pack status: `complete`
- `article_pdf`: SHA-256 `2666ea25fb1cb2dde9d7e613c088a649757422e0ed44384008143e5424f72fda`; Private legal research copy supplied locally; do not redistribute.
- `supplement`: SHA-256 `576bad1d91202338729804b2dad86e2dfb6309fae6e9605c31f49c3d1e0f6e10`; Publisher supplementary ZIP supplied locally; do not redistribute.

## Accessible And Inaccessible Evidence

This report distinguishes inaccessible inputs from empirical contradiction.

- Article and publisher supplement metadata are present as hashes only.
- Accessible or located strict-replication evidence rows: `15`
- Inaccessible or pending strict-replication evidence rows: `2`
- Pending `anomaly_deciles_equal_weighted`: Every archive member exposes only a ret_vw column. Article Table 7 cannot be attempted and no substitute is used
- Pending `crsp_compustat`: No licensed database access is assumed and no security-level portfolio construction was attempted

## Exact Source Definitions

| Source | Exact Definition Verified | Access Status | Provider Or Category | Raw Path |
|---|---:|---|---|---|
| `article_pdf` | `True` | `present_private_file` | reference | `references/private/maio2017.pdf` |
| `article_supplement` | `True` | `present_private_zip` | reference | `references/private/urn_cambridge.org_id_binary_20170615115101719-0272_S002210901700028X_S002210901700028Xsup001.zip` |
| `french_mkt_rf` | `False` | `acquired_at_two_vintages_exact_file_not_named_by_the_article` | Kenneth French Data Library | `data/raw/kenneth_french/mkt_rf.csv` |
| `french_rf` | `False` | `acquired_at_two_vintages_closest_to_an_exact_input` | not_recorded | `not_recorded` |
| `french_momentum` | `False` | `acquired_at_two_vintages` | not_recorded | `not_recorded` |
| `french_five_factor` | `False` | `acquired_at_two_vintages` | not_recorded | `not_recorded` |
| `federal_funds_rate` | `False` | `acquired_documented_reconstruction_series_frozen` | Federal Reserve Economic Data | `data/raw/fred/federal_funds_rate.csv` |
| `treasury_bill_rate` | `False` | `acquired_documented_reconstruction_series_frozen` | Federal Reserve Economic Data | `data/raw/rates/treasury_bill_rate.csv` |
| `treasury_bill_rate_daily` | `False` | `acquired_sensitivity_only` | not_recorded | `not_recorded` |
| `federal_funds_rate_daily` | `False` | `acquired_audit_input_only` | not_recorded | `not_recorded` |
| `anomaly_deciles_seven_families` | `False` | `acquired_from_the_named_original_source_at_a_post_publication_vintage` | not_recorded | `not_recorded` |
| `anomaly_deciles_equal_weighted` | `False` | `not_located` | not_recorded | `not_recorded` |
| `anomaly_deciles_cfp_and_ig` | `False` | `acquired_from_the_named_original_source_at_a_post_publication_vintage` | not_recorded | `not_recorded` |
| `size_double_sorted_25` | `False` | `named_source_located_not_acquired` | not_recorded | `not_recorded` |
| `stambaugh_liquidity` | `False` | `acquired_at_two_vintages_column_and_scale_identified_empirically` | not_recorded | `not_recorded` |
| `hou_xue_zhang_factors` | `False` | `acquired_from_the_named_original_source_at_a_post_publication_vintage` | not_recorded | `not_recorded` |
| `crsp_compustat` | `False` | `not_confirmed_and_not_assumed` | not_recorded | `not_recorded` |

## Factor Reconstruction

- Sample: `1972-01` to `2013-12`, `monthly`, aligned to `month_end`.
- Primary short-rate source id: `federal_funds_rate`.
- Alternative short-rate source ids: `treasury_bill_rate`.
- Innovation model: `ar1_with_intercept` with `full_sample` estimation and `contemporaneous` residual timing.
- Return units: `percent_per_month`.

## Portfolio Reconstruction

- Baseline configured portfolio sets: `book_to_market, earnings_to_price, equity_duration, long_term_reversal, investment_to_assets, ppe_investment, inventory_growth`.
- Registry portfolio-return sources: `french_size_bm_25, french_size_long_term_reversal_25, size_asset_growth_25, size_equity_duration_25, size_inventory_growth_25`.
- Portfolio panels are not silently substituted; unavailable author or WRDS inputs remain missing-input rows until manually registered or reconstructed under the documented reconstruction label.

## Estimator Reconstruction

- Time-series intercept: `True`.
- Time-series covariance: `newey_west` with `automatic` lags.
- Cross-sectional estimators: `ols_two_pass, gls_two_pass, fama_macbeth`.
- Zero-beta intercept: `False`.
- Shanken-style correction: `True`.
- Weak-factor diagnostics: `True`.

## Status Summary

- `reproduced`: 0
- `approximately_reproduced`: 0
- `partially_recovered`: 5
- `not_reproducible_missing_input`: 0
- `contradicted`: 0
- `not_attempted`: 18

## Exact And Reconstructed Datasets

No close substitute is labelled as an exact replication.

## Reproduced Tables

None.

## Approximate Reproductions

None.

## Blocked Targets

None.

## Contradicted Targets

None.

## Weak-Factor And Influence Diagnostics

Verdict: `unsupported`
- `artifacts/diagnostics/h1_materiality.json`
- `artifacts/diagnostics/weak_factor/h4a_identification_strength.json`
- `artifacts/diagnostics/weak_factor/h4b_influence_stability.json`
- `artifacts/diagnostics/weak_factor/h4c_fitted_premium_precision.json`

## Deviations From The Article And Their Causes

Potential numerical differences must be investigated in this fixed order: unit, sample, date_alignment, source_vintage, portfolio_ordering, missing_values, estimator, covariance, rounding, software.
- `french_mkt_rf`: Publication-era vintage obtained from the Internet Archive snapshot of 2017-07-09; both vintages frozen with checksums in artifacts/provenance/kenneth_french and compared in reports/french_vintage_difference_report.md
- `french_rf`: The RF column of the same archive; the article names the one-month Treasury-bill return from this library and it maps to a single public column. Revised in only 2 of 504 baseline months
- `french_momentum`: Carhart comparator factor; revised in 487 of 504 baseline months with a maximum revision of 1.78
- `french_five_factor`: Fama-French five-factor comparator; RMW and CMA revised in more than 96 percent of baseline months
- `federal_funds_rate`: FRED FEDFUNDS frozen with raw and normalized checksums; monthly aggregation verified as the calendar-day mean of DFF rounded half-up to two decimals in 864 of 864 complete months
- `treasury_bill_rate`: FRED TB3MS frozen with raw and normalized checksums; monthly aggregation verified as the mean of available business-day DTB3 observations rounded half-up to two decimals in 869 of 869 complete months
- `treasury_bill_rate_daily`: FRED DTB3; no daily source or aggregation rule appears in the article or supplement so it can never carry an exact-replication label
- `federal_funds_rate_daily`: FRED DFF acquired solely to verify the FEDFUNDS monthly aggregation; it enters no replication or extension estimate
- `anomaly_deciles_seven_families`: All seven families obtained from global-q.org which is the article's named Lu Zhang source; no publication-era vintage is recoverable because the earliest Internet Archive snapshot of the testing-portfolio page is 2019-11-24
- `anomaly_deciles_equal_weighted`: Every archive member exposes only a ret_vw column. Article Table 7 cannot be attempted and no substitute is used
- `anomaly_deciles_cfp_and_ig`: Supplement Table A.4 families; the equal-weighted variants that table also requires are unavailable
- `size_double_sorted_25`: SBM25 SIA25 and SREV25 are attributed to Kenneth French's website without a file name; the archive must be matched by definition rather than by name before acquisition
- `stambaugh_liquidity`: Footnote 18 resolves; the earlier dead-URL record was a PDF text-extraction artifact. LIQ is identified as the traded liquidity factor times 100 from the published mean standard deviation and autocorrelation; the published minimum and maximum are not reproduced by any recoverable vintage and are recorded as an open incompatibility
- `hou_xue_zhang_factors`: R_ME R_IA and R_ROE from the q5 monthly file; no publication-era vintage exists because global-q.org was a parked domain in June 2017 which is consistent with the article stating that these factors were provided by Lu Zhang directly
- `crsp_compustat`: No licensed database access is assumed and no security-level portfolio construction was attempted

## Bounded Conclusion

No successful baseline replication conclusion is available yet.

## Appendix: Complete Audit Table

| Target | Source Location | Status | Statistic | Generated Artifact | Notes |
|---|---|---|---|---|---|
| `TBL_001` | `article_pdf:p.936-p.937:Table 1` | `not_attempted` | Factor descriptive statistics and correlations | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `TBL_002` | `article_pdf:p.937:Table 2` | `not_attempted` | High-minus-low spread descriptive statistics | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `TBL_003` | `article_pdf:p.938:Table 3` | `partially_recovered` | CAPM risk premia and model-fit results | `artifacts/audit/published_target_audit.csv` | 14 of 40 published cells fall inside the published rounding under documented reconstruction. No exact-replication label is available at any recovery rate, because the article names providers and people rather than files. |
| `TBL_004` | `article_pdf:p.939-p.942:Table 4` | `partially_recovered` | Two-factor ICAPM risk premia using federal funds innovations | `artifacts/audit/published_target_audit.csv` | 14 of 56 published cells fall inside the published rounding under documented reconstruction. No exact-replication label is available at any recovery rate, because the article names providers and people rather than files. |
| `TBL_005` | `article_pdf:p.944-p.948:Table 5` | `partially_recovered` | Factor risk-premium decomposition for first and last anomaly deciles | `artifacts/audit/published_target_audit.csv` | 21 of 84 published cells fall inside the published rounding under documented reconstruction. No exact-replication label is available at any recovery rate, because the article names providers and people rather than files. |
| `TBL_006` | `article_pdf:p.949:Table 6` | `partially_recovered` | Alternative multifactor model risk premia and fit | `artifacts/audit/published_target_audit.csv` | 10 of 60 published cells fall inside the published rounding under documented reconstruction. No exact-replication label is available at any recovery rate, because the article names providers and people rather than files. |
| `TBL_007` | `article_pdf:p.950-p.951:Table 7` | `not_attempted` | Two-factor ICAPM risk premia using equal-weighted portfolios | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `TBL_008` | `article_pdf:p.954:Table 8` | `not_attempted` | Long-horizon predictive regressions for excess market return and output growth | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `TBL_009` | `article_pdf:p.956:Table 9` | `not_attempted` | Alternative two-factor ICAPM specifications | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A01` | `supplement_zip:appendix_pdf:p.20:Table A.1` | `partially_recovered` | T-bill-rate ICAPM risk premia | `artifacts/audit/published_target_audit.csv` | 16 of 56 published cells fall inside the published rounding under documented reconstruction. No exact-replication label is available at any recovery rate, because the article names providers and people rather than files. |
| `APP_TBL_A02` | `supplement_zip:appendix_pdf:p.21:Table A.2` | `not_attempted` | Alternative short-rate factor definitions | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A03` | `supplement_zip:appendix_pdf:p.21:Table A.3` | `not_attempted` | Restricted sample through 2006-12 | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A04` | `supplement_zip:appendix_pdf:p.22:Table A.4` | `not_attempted` | Additional CFP and investment-growth anomalies | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A05` | `supplement_zip:appendix_pdf:p.23:Table A.5` | `not_attempted` | Alternative statistical inference for risk premia | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A06` | `supplement_zip:appendix_pdf:p.23:Table A.6` | `not_attempted` | Unrestricted zero-beta-rate ICAPM | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A07` | `supplement_zip:appendix_pdf:p.24:Table A.7` | `not_attempted` | Double-sorted size-anomaly portfolio ICAPM | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A08` | `supplement_zip:appendix_pdf:p.25:Table A.8` | `not_attempted` | Additional Kan-Robotti-Shanken evaluation measures | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A09` | `supplement_zip:appendix_pdf:p.25:Table A.9` | `not_attempted` | Covariance-representation GMM risk premia | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A10` | `supplement_zip:appendix_pdf:p.26:Table A.10` | `not_attempted` | Hansen-Jagannathan distance for SDF representation | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A11` | `supplement_zip:appendix_pdf:p.27:Table A.11` | `not_attempted` | SDF representation parameter estimates | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A12` | `supplement_zip:appendix_pdf:p.28:Table A.12` | `not_attempted` | Augmented ICAPM risk premia | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A13` | `supplement_zip:appendix_pdf:p.29:Table A.13` | `not_attempted` | Additional evaluation measures for other ICAPM models | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
| `APP_TBL_A14` | `supplement_zip:appendix_pdf:p.30:Table A.14` | `not_attempted` | Tests of equality of cross-sectional R-squared | `not_generated` | Outside the current audit pass. The cell-level audit does not compare this table, which is a scope decision rather than an established missing input. |
