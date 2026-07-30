# Article Method Extraction

## Milestone 0 Status

Status: `ARTICLE_AND_SUPPLEMENT_EXTRACTED`

The final article PDF and publisher supplement ZIP are present under `references/private` and remain ignored by Git. The committed evidence manifest records their SHA-256 hashes without redistributing the restricted files.

## Article Evidence

- Local private article: `references/private/maio2017.pdf`
- Article SHA-256: `2666ea25fb1cb2dde9d7e613c088a649757422e0ed44384008143e5424f72fda`
- Local private supplement ZIP: `references/private/urn_cambridge.org_id_binary_20170615115101719-0272_S002210901700028X_S002210901700028Xsup001.zip`
- Supplement ZIP SHA-256: `576bad1d91202338729804b2dad86e2dfb6309fae6e9605c31f49c3d1e0f6e10`
- Supplement ZIP member: `suppl data/JFQA_ms16881_Maio_Santa_Clara_InternetAppendix.pdf`
- Extracted appendix PDF SHA-256: `df4f5418e44cf632dbf6de0e7b0bc260850031144cd316e16f8f6ee2b7fbcae4`
- Evidence manifest: `artifacts/evidence/article_manifest.json`
- DOI: `10.1017/S002210901700028X`
- Journal: `Journal of Financial and Quantitative Analysis`
- Volume and issue: `52(3)`
- Article pages: `927-961`
- Article PDF pages: 35
- Internet Appendix pages: 30

## Extracted Model Definitions

- Article pages 930 and 932 define two ICAPM expected-return beta representations: market plus federal-funds innovation and market plus 3-month Treasury-bill innovation.
- Article page 932 defines the first-pass time-series regression for excess portfolio returns on the excess market return and the federal-funds innovation.
- Article page 932 defines the second-pass cross-sectional OLS regression of average excess returns on first-pass betas. The baseline cross-sectional regression has no intercept.
- Article page 933 defines the joint pricing-error chi-square statistic and states that risk-price t-statistics and pricing-error covariance use Shanken (1992) standard errors.
- Article pages 933-934 define the unconstrained cross-sectional OLS explanatory ratio and the bootstrap p-value procedure. The article states 5,000 bootstrap replications.
- Article page 934 defines the constrained cross-sectional explanatory ratio used for comparator models whose factors are traded returns.
- Article page 935 defines short-rate innovations as AR(1) residuals for the federal funds rate and the 3-month Treasury-bill rate.
- Appendix Section 1 and Table A.1 provide the T-bill-rate ICAPM results that the article says are available from the authors.
- Appendix Section 2.1 and Table A.2 define first-difference short-rate factors as robustness alternatives.
- Appendix Section 2.5 and Table A.6 define the unrestricted zero-beta second-pass regression with portfolio returns and an intercept.
- Appendix Section 2.7 and Table A.8 define the Kan-Robotti-Shanken additional evaluation metrics.
- Appendix Section 2.8 and Table A.9 define the covariance-representation GMM implementation.
- Appendix Section 2.9 and Tables A.10-A.11 define Hansen-Jagannathan SDF-distance tests.
- Appendix Section 4 gives the cross-sectional bootstrap algorithm used for empirical p-values.

## Extracted Data Definitions

- Baseline sample: January 1972 through December 2013.
- Restricted-sample robustness endpoint: December 2006.
- Short-rate state variables: federal funds rate and 3-month Treasury-bill rate from the St. Louis Federal Reserve Bank.
- Risk-free return for portfolio excess returns: 1-month Treasury bill from Kenneth French's data library.
- Comparator factors from Kenneth French's data library: market excess return, SMB, HML, UMD, RMW, and CMA.
- Liquidity factor: Robert Stambaugh's web page.
- Hou-Xue-Zhang factors ME, IA, and ROE: Lu Zhang.
- Main testing assets: value-weighted decile portfolios sorted on book-to-market, earnings-to-price, equity duration, long-term reversal, investment-to-assets, property-plant-equipment plus inventory growth scaled by assets, and inventory growth.
- Main decile portfolio-return source: Lu Zhang.
- Additional CFP and IG anomaly deciles in Appendix Table A.4 are from Lu Zhang and include value- and equal-weighted variants.
- Double-sorted robustness in Appendix Table A.7 uses value-weighted 25 portfolios sorted on size/book-to-market, size/asset growth, and size/long-term reversal from Kenneth French's website.

## Extracted Table Targets

The main article tables and Internet Appendix tables are frozen in `research/table_target_manifest.csv` with source locators:

- Article Tables 1-9: article pages 936-956.
- Appendix Tables A.1-A.14: Internet Appendix PDF pages 20-30.

## Remaining Blocking Ambiguities

- `BLOCKED_WORKING_PAPER_AUDIT`: working-paper versus final-article differences cannot be audited until the prior working-paper version is available.
- `BLOCKED_SOURCE_VERSION`: the article and appendix identify source providers but do not provide immutable archive snapshots or vintage identifiers for every public source.
- `BLOCKED_AUTHOR_DATA`: Lu Zhang portfolio files and factor files must be manually registered or downloaded from an approved public/author location before strict data replication can proceed.

## Consequence

The article and supplement evidence pack is now complete at the publication-document level. The next strict-replication blockers are source-version freeze, author/public data acquisition, and working-paper audit.
