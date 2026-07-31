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
- Accessible or located strict-replication evidence rows: `7`
- Inaccessible or pending strict-replication evidence rows: `3`
- Pending `size_asset_growth_25`: Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required
- Pending `size_equity_duration_25`: Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required
- Pending `size_inventory_growth_25`: Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required

## Exact Source Definitions

| Source | Exact Definition Verified | Access Status | Provider Or Category | Raw Path |
|---|---:|---|---|---|
| `article_pdf` | `True` | `present_private_file` | reference | `references/private/maio2017.pdf` |
| `article_supplement` | `True` | `present_private_zip` | reference | `references/private/urn_cambridge.org_id_binary_20170615115101719-0272_S002210901700028X_S002210901700028Xsup001.zip` |
| `french_mkt_rf` | `False` | `article_source_located` | Kenneth French Data Library | `data/raw/kenneth_french/mkt_rf.csv` |
| `french_size_bm_25` | `False` | `article_source_located` | Kenneth French Data Library | `data/raw/kenneth_french/size_bm_25.csv` |
| `french_size_long_term_reversal_25` | `False` | `article_source_located` | Kenneth French Data Library | `data/raw/kenneth_french/size_long_term_reversal_25.csv` |
| `federal_funds_rate` | `False` | `article_source_located` | Federal Reserve Economic Data | `data/raw/fred/federal_funds_rate.csv` |
| `treasury_bill_rate` | `False` | `article_source_located` | Federal Reserve Economic Data or original author source | `data/raw/rates/treasury_bill_rate.csv` |
| `size_asset_growth_25` | `False` | `author_source_identified` | author_data_or_reconstruction | `data/raw/portfolios/size_asset_growth_25.csv` |
| `size_equity_duration_25` | `False` | `author_source_identified` | author_data_or_reconstruction | `data/raw/portfolios/size_equity_duration_25.csv` |
| `size_inventory_growth_25` | `False` | `author_source_identified` | author_data_or_reconstruction | `data/raw/portfolios/size_inventory_growth_25.csv` |

## Factor Reconstruction

- Sample: `1972-01` to `2013-12`, `monthly`, aligned to `month_end`.
- Primary short-rate source id: `federal_funds_rate`.
- Alternative short-rate source ids: `treasury_bill_rate`.
- Innovation model: `ar1_with_intercept` with `full_sample` estimation and `contemporaneous` residual timing.
- Return units: `percent_per_month`.

## Portfolio Reconstruction

- Baseline configured portfolio sets: `size_book_to_market_25, size_asset_growth_25, size_long_term_reversal_25, size_equity_duration_25, size_inventory_growth_25`.
- Registry portfolio-return sources: `french_size_bm_25, french_size_long_term_reversal_25, size_asset_growth_25, size_equity_duration_25, size_inventory_growth_25`.
- Portfolio panels are not silently substituted; unavailable author or WRDS inputs remain missing-input rows until manually registered or reconstructed under the documented reconstruction label.

## Estimator Reconstruction

- Time-series intercept: `True`.
- Time-series covariance: `newey_west` with `automatic` lags.
- Cross-sectional estimators: `ols_two_pass, gls_two_pass, fama_macbeth`.
- Zero-beta intercept: `True`.
- Shanken-style correction: `True`.
- Weak-factor diagnostics: `True`.

## Status Summary

- `reproduced`: 0
- `approximately_reproduced`: 0
- `not_reproducible_missing_input`: 23
- `contradicted`: 0
- `not_attempted`: 0

## Exact And Reconstructed Datasets

No close substitute is labelled as an exact replication.

## Reproduced Tables

None.

## Approximate Reproductions

None.

## Blocked Targets

- `TBL_001` (article_pdf:p.936-p.937:Table 1): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_002` (article_pdf:p.937:Table 2): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_003` (article_pdf:p.938:Table 3): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_004` (article_pdf:p.939-p.942:Table 4): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_005` (article_pdf:p.944-p.948:Table 5): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_006` (article_pdf:p.949:Table 6): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_007` (article_pdf:p.950-p.951:Table 7): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_008` (article_pdf:p.954:Table 8): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `TBL_009` (article_pdf:p.956:Table 9): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A01` (supplement_zip:appendix_pdf:p.20:Table A.1): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A02` (supplement_zip:appendix_pdf:p.21:Table A.2): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A03` (supplement_zip:appendix_pdf:p.21:Table A.3): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A04` (supplement_zip:appendix_pdf:p.22:Table A.4): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A05` (supplement_zip:appendix_pdf:p.23:Table A.5): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A06` (supplement_zip:appendix_pdf:p.23:Table A.6): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A07` (supplement_zip:appendix_pdf:p.24:Table A.7): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A08` (supplement_zip:appendix_pdf:p.25:Table A.8): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A09` (supplement_zip:appendix_pdf:p.25:Table A.9): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A10` (supplement_zip:appendix_pdf:p.26:Table A.10): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A11` (supplement_zip:appendix_pdf:p.27:Table A.11): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A12` (supplement_zip:appendix_pdf:p.28:Table A.12): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A13` (supplement_zip:appendix_pdf:p.29:Table A.13): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet
- `APP_TBL_A14` (supplement_zip:appendix_pdf:p.30:Table A.14): Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet

## Contradicted Targets

None.

## Weak-Factor And Influence Diagnostics

Verdict: `unidentified`
- `data\processed\factors\short_rate_factors.parquet`
No significant-only robustness reporting has been performed.

## Deviations From The Article And Their Causes

Potential numerical differences must be investigated in this fixed order: unit, sample, date_alignment, source_vintage, portfolio_ordering, missing_values, estimator, covariance, rounding, software.
- `french_mkt_rf`: Article identifies Kenneth French online data library for RM and comparator factors; exact archive names still need supplement or source freeze
- `french_size_bm_25`: Article main decile portfolios are from Lu Zhang; double-sorted size-BM robustness mentioned but supplement details remain missing
- `french_size_long_term_reversal_25`: Article main decile portfolios are from Lu Zhang; double-sorted size-reversal robustness mentioned but supplement details remain missing
- `federal_funds_rate`: Article identifies St. Louis Federal Reserve Bank federal funds rate but does not state a FRED series id
- `treasury_bill_rate`: Article identifies St. Louis Federal Reserve Bank 3-month Treasury-bill rate but exact series remains ambiguous
- `size_asset_growth_25`: Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required
- `size_equity_duration_25`: Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required
- `size_inventory_growth_25`: Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required

## Bounded Conclusion

Baseline replication is blocked by missing inputs; this is not evidence that the article is unreliable.

## Appendix: Complete Audit Table

| Target | Source Location | Status | Statistic | Generated Artifact | Notes |
|---|---|---|---|---|---|
| `TBL_001` | `article_pdf:p.936-p.937:Table 1` | `not_reproducible_missing_input` | Factor descriptive statistics and correlations | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_002` | `article_pdf:p.937:Table 2` | `not_reproducible_missing_input` | High-minus-low spread descriptive statistics | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_003` | `article_pdf:p.938:Table 3` | `not_reproducible_missing_input` | CAPM risk premia and model-fit results | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_004` | `article_pdf:p.939-p.942:Table 4` | `not_reproducible_missing_input` | Two-factor ICAPM risk premia using federal funds innovations | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_005` | `article_pdf:p.944-p.948:Table 5` | `not_reproducible_missing_input` | Factor risk-premium decomposition for first and last anomaly deciles | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_006` | `article_pdf:p.949:Table 6` | `not_reproducible_missing_input` | Alternative multifactor model risk premia and fit | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_007` | `article_pdf:p.950-p.951:Table 7` | `not_reproducible_missing_input` | Two-factor ICAPM risk premia using equal-weighted portfolios | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_008` | `article_pdf:p.954:Table 8` | `not_reproducible_missing_input` | Long-horizon predictive regressions for excess market return and output growth | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `TBL_009` | `article_pdf:p.956:Table 9` | `not_reproducible_missing_input` | Alternative two-factor ICAPM specifications | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A01` | `supplement_zip:appendix_pdf:p.20:Table A.1` | `not_reproducible_missing_input` | T-bill-rate ICAPM risk premia | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A02` | `supplement_zip:appendix_pdf:p.21:Table A.2` | `not_reproducible_missing_input` | Alternative short-rate factor definitions | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A03` | `supplement_zip:appendix_pdf:p.21:Table A.3` | `not_reproducible_missing_input` | Restricted sample through 2006-12 | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A04` | `supplement_zip:appendix_pdf:p.22:Table A.4` | `not_reproducible_missing_input` | Additional CFP and investment-growth anomalies | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A05` | `supplement_zip:appendix_pdf:p.23:Table A.5` | `not_reproducible_missing_input` | Alternative statistical inference for risk premia | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A06` | `supplement_zip:appendix_pdf:p.23:Table A.6` | `not_reproducible_missing_input` | Unrestricted zero-beta-rate ICAPM | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A07` | `supplement_zip:appendix_pdf:p.24:Table A.7` | `not_reproducible_missing_input` | Double-sorted size-anomaly portfolio ICAPM | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A08` | `supplement_zip:appendix_pdf:p.25:Table A.8` | `not_reproducible_missing_input` | Additional Kan-Robotti-Shanken evaluation measures | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A09` | `supplement_zip:appendix_pdf:p.25:Table A.9` | `not_reproducible_missing_input` | Covariance-representation GMM risk premia | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A10` | `supplement_zip:appendix_pdf:p.26:Table A.10` | `not_reproducible_missing_input` | Hansen-Jagannathan distance for SDF representation | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A11` | `supplement_zip:appendix_pdf:p.27:Table A.11` | `not_reproducible_missing_input` | SDF representation parameter estimates | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A12` | `supplement_zip:appendix_pdf:p.28:Table A.12` | `not_reproducible_missing_input` | Augmented ICAPM risk premia | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A13` | `supplement_zip:appendix_pdf:p.29:Table A.13` | `not_reproducible_missing_input` | Additional evaluation measures for other ICAPM models | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
| `APP_TBL_A14` | `supplement_zip:appendix_pdf:p.30:Table A.14` | `not_reproducible_missing_input` | Tests of equality of cross-sectional R-squared | `not_generated` | Empirical audit is blocked until baseline generated artifacts exist: data\processed\factors\short_rate_factors.parquet |
