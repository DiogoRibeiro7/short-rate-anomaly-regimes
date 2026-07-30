# Article Method Extraction

## Milestone 0 Status

Status: `PARTIAL_ARTICLE_EXTRACTED_SUPPLEMENT_MISSING`

The final article PDF is present at `references/private/maio2017.pdf` and remains ignored by Git. The publisher supplement / Internet Appendix is not present under `references/private`, so strict replication is still blocked.

## Article Evidence

- Local private file: `references/private/maio2017.pdf`
- SHA-256: `2666ea25fb1cb2dde9d7e613c088a649757422e0ed44384008143e5424f72fda`
- Evidence manifest: `artifacts/evidence/article_manifest.json`
- DOI: `10.1017/S002210901700028X`
- Journal: `Journal of Financial and Quantitative Analysis`
- Volume and issue: `52(3)`
- Pages: `927-961`
- Publication month: June 2017
- PDF pages: 35

## Extracted Model Definitions

- Article pages 930 and 932 define two ICAPM expected-return beta representations: market plus federal-funds innovation and market plus 3-month Treasury-bill innovation.
- Article page 932 defines the first-pass time-series regression for excess portfolio returns on the excess market return and the federal-funds innovation.
- Article page 932 defines the second-pass cross-sectional OLS regression of average excess returns on first-pass betas. The baseline cross-sectional regression has no intercept.
- Article page 933 defines the joint pricing-error chi-square statistic and states that risk-price t-statistics and pricing-error covariance use Shanken (1992) standard errors.
- Article pages 933-934 define the unconstrained cross-sectional OLS explanatory ratio and the bootstrap p-value procedure. The article states 5,000 bootstrap replications.
- Article page 934 defines the constrained cross-sectional explanatory ratio used for comparator models whose factors are traded returns.
- Article page 935 defines short-rate innovations as AR(1) residuals for the federal funds rate and the 3-month Treasury-bill rate.

## Extracted Data Definitions

- Baseline sample: January 1972 through December 2013.
- Short-rate state variables: federal funds rate and 3-month Treasury-bill rate from the St. Louis Federal Reserve Bank.
- Risk-free return for portfolio excess returns: 1-month Treasury bill from Kenneth French's data library.
- Comparator factors from Kenneth French's data library: market excess return, SMB, HML, UMD, RMW, and CMA.
- Liquidity factor: Robert Stambaugh's web page.
- Hou-Xue-Zhang factors ME, IA, and ROE: Lu Zhang.
- Main testing assets: value-weighted decile portfolios sorted on book-to-market, earnings-to-price, equity duration, long-term reversal, investment-to-assets, property-plant-equipment plus inventory growth scaled by assets, and inventory growth.
- Main portfolio-return source: Lu Zhang.
- Equal-weighted portfolios are used as a robustness variant.
- Double-sorted robustness mentioned in the article uses 25 portfolios sorted on size and book-to-market, size and asset growth, and size and long-term reversal.

## Extracted Table Targets

The main article tables are frozen in `research/table_target_manifest.csv` with article-page locators:

- Table 1: factor descriptives and correlations, article pages 936-937.
- Table 2: high-minus-low spread descriptives, article page 937.
- Table 3: CAPM risk premia and fit, article page 938.
- Table 4: two-factor ICAPM using federal-funds innovations, article pages 939-942.
- Table 5: factor risk-premium decomposition, article pages 944-948.
- Table 6: alternative multifactor models, article page 949.
- Table 7: equal-weighted portfolio ICAPM, article pages 950-951.
- Table 8: predictive regressions, article page 954.
- Table 9: alternative ICAPM specifications, article page 956.

## Remaining Blocking Ambiguities

- `BLOCKED_SUPPLEMENT_MISSING`: publisher supplement / Internet Appendix unavailable locally.
- `BLOCKED_SUPPLEMENT_MISSING`: full bootstrap simulation details are cited as being in the Internet Appendix.
- `BLOCKED_SUPPLEMENT_MISSING`: article text says results based on the Treasury-bill ICAPM are available from the authors rather than fully tabulated in the article.
- `BLOCKED_SUPPLEMENT_MISSING`: robustness results for additional anomalies, unrestricted zero-beta tests, double-sorted portfolios, Kan et al. metrics, GMM, and HJ distance are discussed but not fully tabulated in the article.
- `BLOCKED_WORKING_PAPER_AUDIT`: working-paper versus final-article differences cannot be audited until the prior working-paper version is available.

## Consequence

The article PDF now resolves the main published table locators and baseline methodology at article level. Strict replication remains blocked until the supplement / Internet Appendix is available and extracted.
