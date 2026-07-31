# Original Framework Audit

Review pass: original framework reconstruction.

## Evidence Read

- Article: Maio and Santa-Clara, `Short-Term Interest Rates and Stock Market Anomalies`, Journal of Financial and Quantitative Analysis, pages 927-961.
- Supplement: publisher Internet Appendix PDF extracted from the locally provided supplement ZIP.
- Repository targets: `research/table_target_manifest.csv` and `artifacts/audit/table_replication.csv`.

## Verified Baseline Entries

| Item | Status | Verified entry | Article or supplement location |
|---|---|---|---|
| Economic motivation and state-variable interpretation | verified | The article uses a discrete-time ICAPM in which innovations in state variables proxy changes in future investment opportunities. | Article p. 931, Section II |
| Short-rate series used | verified | The two state variables are the federal funds rate and the 3-month Treasury-bill rate. | Article p. 931, Section II; p. 935, Section III.B |
| Frequency and sample dates | verified | The asset-pricing sample is monthly from January 1972 through December 2013. | Article p. 935, Section III.B; Tables 1-4 notes |
| Units | verified | Risk prices, factor means, and returns in the tables are reported in percent. | Article table notes, especially Tables 3-5 |
| Federal-funds innovation specification | verified | The article fits `FFR_{t+1}=0.000+0.991 FFR_t` and defines the innovation as the realized rate less the fitted AR component. | Article p. 935, Section III.B |
| Treasury-bill innovation specification | verified | The article fits `TB_{t+1}=0.000+0.992 TB_t` and defines the analogous innovation. | Article p. 935, Section III.B |
| Autoregressive estimation window | ambiguous | The article reports the AR estimates inside the January 1972 to December 2013 data section, but the exact estimation-window implementation must be checked in code once source data are frozen. | Article p. 935, Section III.B |
| Market and risk-free factors | verified | `RM` is the excess market return; the 1-month Treasury-bill rate from Kenneth French is used to construct portfolio excess returns. | Article p. 932, Section III.A; p. 937, Section III.B |
| Alternative factor sources | verified | CAPM, FF3, C4, and FF5 factors are from Kenneth French; LIQ is from Robert Stambaugh; ME, IA, and ROE are from Lu Zhang. | Article p. 935, Section III.B |
| Exact source-file identifiers | ambiguous | Source providers are named, but exact download file names and archive vintages are not fully specified in the article text. | Article p. 935 and source notes |
| Anomaly families | verified | The primary anomaly families are BM, DUR, EP, REV, IA, PIA, and IVG. | Article pp. 935-937, Section III.B; Tables 2-4 notes |
| Portfolio dimensions | verified | The primary tests use decile portfolios and include a joint system containing all seven anomaly families. | Article pp. 936-940 |
| Portfolio source | verified | Primary portfolio return data are obtained from Lu Zhang. | Article p. 937, Section III.B |
| First-pass regression | verified | Betas are estimated from time-series multiple regressions of portfolio excess returns on the market excess return and interest-rate innovation. | Article p. 932, equation 3 |
| Second-pass estimator | verified | Expected returns are estimated with OLS cross-sectional regressions of average excess returns on estimated betas. | Article p. 932, equation 4 |
| Benchmark intercept treatment | verified | The benchmark cross-sectional regression does not include an intercept. | Article pp. 932-933 |
| Pricing-error notation | verified | The article denotes cross-sectional pricing errors by alpha in the second-pass equation. | Article p. 932, equation 4 |
| Covariance and standard-error corrections | verified | Risk-price t-statistics and variance of pricing errors use Shanken standard errors. | Article p. 933 |
| Bootstrap inference | verified | The article reports empirical p-values from a bootstrap simulation under a useless-factor design. | Article pp. 933-934 |
| Pricing-error statistic | verified | The article reports a chi-square joint pricing-error statistic using a pseudo-inverse of the pricing-error covariance matrix. | Article p. 933, equation 5 |
| Fit statistic | verified | The article reports the cross-sectional OLS coefficient of determination. | Article p. 933, equation 6 |
| Constrained fit statistic for traded-factor models | verified | The article defines a constrained cross-sectional R-squared for alternative models whose factors are traded portfolio returns. | Article p. 934, equations 7-8 |
| Comparator models | verified | Comparators include CAPM, FF3, Carhart four-factor, Pastor-Stambaugh four-factor, Hou-Xue-Zhang four-factor, and Fama-French five-factor models. | Article pp. 931-932 |
| Table 1 | verified | Descriptive statistics and correlations for risk factors. | Article pp. 936-937 |
| Table 2 | verified | Descriptive statistics and correlations for high-minus-low anomaly spreads. | Article p. 937 |
| Table 3 | verified | CAPM risk premia and fit results. | Article p. 938 |
| Table 4 | verified | Two-factor ICAPM results using federal-funds innovations. | Article pp. 939-942 |
| Table 5 | verified | Accounting decomposition of risk premia for extreme deciles. | Article pp. 944-948 |
| Table 6 | verified | Alternative multifactor model results. | Article p. 949 |
| Table 7 | verified | Equal-weighted portfolio ICAPM results. | Article pp. 950-951 |
| Table 8 | verified | Long-horizon predictive regressions. | Article p. 954 |
| Table 9 | verified | Alternative ICAPM specifications. | Article p. 956 |
| Figure 1 | verified | Pricing errors and t-statistics for BM, DUR, EP, and REV deciles. | Article p. 942 |
| Figure 2 | verified | Pricing errors and t-statistics for IA, PIA, and IVG deciles. | Article p. 943 |

## Verified Supplement Entries

| Item | Status | Verified entry | Supplement location |
|---|---|---|---|
| Table A.1 | verified | T-bill-rate ICAPM risk premia for value-weighted portfolios. | Internet Appendix p. 20 |
| Table A.2 | verified | Alternative short-rate factor definitions. | Internet Appendix p. 21 |
| Table A.3 | verified | Restricted sample through 2006-12. | Internet Appendix p. 21 |
| Table A.4 | verified | Additional anomalies. | Internet Appendix p. 22 |
| Table A.5 | verified | Alternative statistical inference for risk premia. | Internet Appendix p. 23 |
| Table A.6 | verified | Unrestricted zero-beta-rate second-pass design. | Internet Appendix p. 23 |
| Table A.7 | verified | Double-sorted size-anomaly portfolios. | Internet Appendix p. 24 |
| Table A.8 | verified | Kan-Robotti-Shanken additional evaluation measures. | Internet Appendix p. 25 |
| Table A.9 | verified | Covariance-representation GMM risk premia. | Internet Appendix p. 25 |
| Table A.10 | verified | Hansen-Jagannathan distance. | Internet Appendix p. 26 |
| Table A.11 | verified | SDF parameter estimates. | Internet Appendix p. 27 |
| Table A.12 | verified | Augmented ICAPM with additional state variables. | Internet Appendix p. 28 |
| Table A.13 | verified | Additional evaluation measures for other ICAPM models. | Internet Appendix p. 29 |
| Table A.14 | verified | Tests of equality of cross-sectional R-squared. | Internet Appendix p. 30 |

## Ambiguities To Preserve

- The St. Louis Federal Reserve Bank rate sources are identified, but exact FRED series identifiers and vintage retrieval dates are not fully specified in the article text.
- Portfolio sources are attributed to Lu Zhang, but strict replication still requires exact files and construction vintages.
- The article describes the AR innovation equations and sample, but computational replication still requires confirming how missing observations, timing alignment, and rate units are implemented in source data.
- Bootstrap and Shanken procedures are described at the paper level, but exact computational equality requires implementation-level verification.
