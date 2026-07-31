# Annotated Literature Review

Review pass: literature review.

## Intertemporal asset pricing and state variables

### Merton (1973)

- Full citation: Merton, Robert C. 1973. "An Intertemporal Capital Asset Pricing Model." Econometrica 41(5): 867-887. DOI: 10.2307/1913811.
- Research question: How do asset prices change when investors hedge shifts in future investment opportunities?
- Data and method: Theoretical continuous-time model.
- Main result: Expected returns depend on market risk and covariance with state variables.
- Relevance: Provides the state-variable logic used by the short-rate ICAPM.
- Boundary: Does not specify the empirical short-rate proxy or anomaly portfolios.
- Verification: JSTOR stable identifier and existing manuscript bibliography.

### Lioui and Maio (2014)

- Full citation: Lioui, Abraham, and Paulo Maio. 2014. "Interest Rate Risk and the Cross Section of Stock Returns." Journal of Financial and Quantitative Analysis 49(2): 483-511. DOI: 10.1017/S0022109014000131.
- Research question: Can interest-rate risk explain cross-sectional stock returns?
- Data and method: Macroeconomic asset-pricing model and cross-sectional stock-return tests.
- Main result: The interest-rate factor is priced and explains cross-sectional returns in addition to the market.
- Relevance: Closest predecessor for the economic channel in the Maio-Santa-Clara baseline.
- Boundary: Not the same table-level anomaly replication target.
- Verification: Cambridge Core article metadata.

## Anomaly pricing and model comparison

### Fama and French (2015)

- Full citation: Fama, Eugene F., and Kenneth R. French. 2015. "A Five-Factor Asset Pricing Model." Journal of Financial Economics 116(1): 1-22. DOI: 10.1016/j.jfineco.2014.10.010.
- Research question: Do profitability and investment factors improve the explanation of average stock returns?
- Data and method: Empirical factor-model tests on portfolios sorted by size, value, profitability, and investment.
- Main result: A five-factor model improves on the three-factor model, with known remaining limitations.
- Relevance: Benchmark comparator for anomaly-pricing claims.
- Boundary: Equity-factor model rather than an ICAPM short-rate state-variable model.
- Verification: Publisher and RePEc metadata.

### Hou, Xue, and Zhang (2015)

- Full citation: Hou, Kewei, Chen Xue, and Lu Zhang. 2015. "Digesting Anomalies: An Investment Approach." The Review of Financial Studies 28(3): 650-705. DOI: 10.1093/rfs/hhu068.
- Research question: Can an investment-based q-factor model summarize a broad set of anomalies?
- Data and method: Empirical q-factor model with market, size, investment, and profitability factors.
- Main result: The model summarizes many anomalies and performs at least comparably to standard benchmarks.
- Relevance: Comparator model and source context for Lu Zhang anomaly portfolios.
- Boundary: Does not identify short-rate innovation risk.
- Verification: Oxford Academic metadata.

### Maio and Santa-Clara (2017)

- Full citation: Maio, Paulo F., and Pedro Santa-Clara. 2017. "Short-Term Interest Rates and Stock Market Anomalies." Journal of Financial and Quantitative Analysis 52(3): 927-961. DOI: 10.1017/S002210901700028X.
- Research question: Do short-term interest-rate innovations help price stock-market anomalies?
- Data and method: Two-factor ICAPM with market excess return and short-rate innovation, tested on anomaly portfolios.
- Main result: The article reports strong cross-sectional fit and negative short-rate risk prices across several anomaly families.
- Relevance: Baseline replication target.
- Boundary: This repository has not yet reproduced the empirical tables from source-compatible inputs.
- Verification: Local article PDF and Cambridge metadata.

## Monetary-policy surprises and information components

### Bernanke and Kuttner (2005)

- Full citation: Bernanke, Ben S., and Kenneth N. Kuttner. 2005. "What Explains the Stock Market's Reaction to Federal Reserve Policy?" Journal of Finance 60(3): 1221-1257. DOI: 10.1111/j.1540-6261.2005.00760.x.
- Research question: How do equity prices respond to unexpected Federal Reserve policy actions?
- Data and method: Event-study decomposition of stock-market reactions to monetary-policy surprises.
- Main result: Unexpected policy actions are associated with broad equity-market responses.
- Relevance: Motivates why rate innovations can mix discount-rate and expected-cash-flow news.
- Boundary: Event-study aggregate equity response, not anomaly-portfolio pricing.
- Verification: Wiley and Federal Reserve working-paper records.

### Jarocinski and Karadi (2020)

- Full citation: Jarocinski, Marek, and Peter Karadi. 2020. "Deconstructing Monetary Policy Surprises: The Role of Information Shocks." American Economic Journal: Macroeconomics 12(2): 1-43. DOI: 10.1257/mac.20180090.
- Research question: Can high-frequency announcement surprises be separated into policy and central-bank-information components?
- Data and method: High-frequency co-movement of interest rates and stock prices around central-bank announcements, followed by macroeconomic analysis.
- Main result: Policy and information components have different interpretations and macroeconomic implications.
- Relevance: Defines the identification boundary for the shock-decomposition extension.
- Boundary: Does not directly price anomaly portfolios.
- Verification: American Economic Association article metadata.

### Swanson and Williams (2014)

- Full citation: Swanson, Eric T., and John C. Williams. 2014. "Measuring the Effect of the Zero Lower Bound on Medium- and Longer-Term Interest Rates." American Economic Review 104(10): 3154-3185. DOI: 10.1257/aer.104.10.3154.
- Research question: How binding is the lower bound for rates across the term structure?
- Data and method: Empirical measurement of yield sensitivity during lower-bound periods.
- Main result: Medium- and longer-term yields can remain informative even when the short rate is constrained.
- Relevance: Motivates regime-specific interpretation of short-rate innovations.
- Boundary: Term-structure evidence, not cross-sectional equity pricing.
- Verification: American Economic Association article metadata.

## Inference, weak factors, and structural instability

### Fama and MacBeth (1973)

- Full citation: Fama, Eugene F., and James D. MacBeth. 1973. "Risk, Return, and Equilibrium: Empirical Tests." Journal of Political Economy 81(3): 607-636. DOI: 10.1086/260061.
- Research question: How can equilibrium risk-return relations be tested empirically?
- Data and method: Cross-sectional regressions of returns on risk measures.
- Main result: Establishes the classic two-step empirical testing architecture.
- Relevance: Baseline inference reference for cross-sectional asset pricing.
- Boundary: Does not correct all generated-regressor or weak-factor concerns.
- Verification: University of Chicago and RePEc metadata.

### Shanken (1992)

- Full citation: Shanken, Jay. 1992. "On the Estimation of Beta-Pricing Models." The Review of Financial Studies 5(1): 1-33. DOI: 10.1093/rfs/5.1.1.
- Research question: How should beta-pricing models account for estimated factor loadings?
- Data and method: Econometric analysis of maximum likelihood and two-pass estimators.
- Main result: Traditional risk-price inference overstates precision without beta-estimation correction.
- Relevance: Baseline article reports Shanken-corrected risk-price statistics.
- Boundary: Requires exact implementation choices to match published tables.
- Verification: RePEc metadata.

### Kan and Zhang (1999)

- Full citation: Kan, Raymond, and Chu Zhang. 1999. "Two-Pass Tests of Asset Pricing Models with Useless Factors." Journal of Finance 54(1): 203-235. DOI: 10.1111/0022-1082.00102.
- Research question: What happens when two-pass tests include useless factors?
- Data and method: Theoretical and simulation analysis.
- Main result: A factor independent of asset returns can appear priced too often in second-pass regressions.
- Relevance: Motivates weak-factor and beta-dispersion diagnostics.
- Boundary: Extreme useless-factor setting, not a direct test of short-rate innovations.
- Verification: RePEc and Wiley DOI metadata.

### Lewellen, Nagel, and Shanken (2010)

- Full citation: Lewellen, Jonathan, Stefan Nagel, and Jay Shanken. 2010. "A Skeptical Appraisal of Asset-Pricing Tests." Journal of Financial Economics 96(2): 175-194. DOI: 10.1016/j.jfineco.2009.09.001.
- Research question: How informative are common cross-sectional asset-pricing tests?
- Data and method: Review and empirical critique of model tests using characteristic-sorted portfolios.
- Main result: High cross-sectional fit can provide weak model support when test assets have strong common structure.
- Relevance: Supports the repository's rank, spanning, and influence diagnostics.
- Boundary: General critique; does not settle the short-rate anomaly claim.
- Verification: Publisher/RePEc metadata.

### Bai and Perron (1998)

- Full citation: Bai, Jushan, and Pierre Perron. 1998. "Estimating and Testing Linear Models with Multiple Structural Changes." Econometrica 66(1): 47-78. DOI: 10.2307/2998540.
- Research question: How can multiple unknown structural breaks be estimated and tested in linear models?
- Data and method: Econometric theory for multiple-break estimation.
- Main result: Provides procedures for estimating and testing structural changes.
- Relevance: Supports the monetary-regime and unknown-break extension design.
- Boundary: General linear-model framework requiring careful adaptation to asset-pricing panels.
- Verification: JSTOR and publisher records.

## Replication and data-vintage sensitivity

### Kenneth French Data Library

- Full citation: French, Kenneth R. 2026. "Kenneth R. French Data Library." Official data library. Stable URL: https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html.
- Research question: What factor and portfolio files are distributed, archived, and revised?
- Data and method: Official factor and portfolio data documentation and download archive.
- Main result: The library documents current files, historical archives, and CRSP-related changes affecting factor construction.
- Relevance: Supports the repository rule that exact archive versions and data vintages must be frozen.
- Boundary: Official documentation, not a journal article.
- Verification: Dartmouth-hosted Kenneth French Data Library page.
