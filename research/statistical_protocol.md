# Statistical Protocol

## Baseline Estimators

Implement the article's verified estimators first. The repository is prepared for

- OLS first-pass factor regressions;
- HAC standard errors using the article's Newey-West lag rule;
- OLS and GLS second-pass regressions;
- repeated monthly Fama-MacBeth estimation only when a registered target or
  robustness contract explicitly requires it;
- Shanken correction;
- joint alpha tests;
- cross-sectional fit metrics.

## Short-Rate Innovation Construction

The baseline short-rate innovation is the residual from the article's verified
first-order autoregression with an intercept. The implementation convention is

`u_rate[t] = rate[t] - intercept_hat - rho_hat * rate[t - 1]`.

The first-pass return regression for month `t` must use `u_rate[t]`. The code
must materialize and test this lag explicitly; no estimator may rely on an
implicit shift that could create look-ahead or a one-month mismatch. Alternative
rate definitions, higher-order autoregressions, local-level state-space
innovations, and announcement-surprise proxies are robustness or extension
specifications and do not redefine the strict baseline.

## First-Pass And Second-Pass Design

Use distinct notation for the time-series intercept, factor loadings,
time-series residual, cross-sectional pricing error, and factor risk prices. The
benchmark second pass follows the article's verified no-intercept OLS
cross-sectional regression of full-sample average excess returns on full-sample
estimated betas. Any unrestricted zero-beta-rate specification, GLS estimator,
or repeated monthly cross-sectional estimator is reported as a separate
robustness target.

Estimated-beta uncertainty is handled with the article's Shanken correction when
the baseline risk-price estimator is used. Fitted-premium uncertainty is handled
with the joint moving-block bootstrap in `research/bootstrap_contract.md`, which
re-estimates rate innovations, first-pass betas, second-pass risk prices,
fitted premia, pricing errors, fit metrics, and equivalence statistics in every
draw. Repeated Fama-MacBeth, Kan-Robotti-Shanken, and GMM variants are labelled
separately and mapped to the supplement targets or extension diagnostics that
require them.

## Model Comparison

Model comparison must report pricing-error loss and fit on identical asset-date
intersections within each comparison. Registered outcomes include root mean
squared pricing error, mean absolute pricing error, maximum absolute pricing
error, cross-sectional fit, and joint pricing-error tests when the estimator
justifies the test.

The primary ex ante materiality comparison is against the CAPM on the common
asset-date intersection. H1 also reports a secondary adversarial comparison
against the strongest observed registered non-short-rate comparator by baseline
cross-sectional RMSE. The strongest-observed comparison is not used to choose
the primary comparator; it is reported with explicit model-selection uncertainty
inside the registered secondary family.

## Weak-Factor Analysis

A high cross-sectional fit is not sufficient when factor exposures have little
economically scaled dispersion or the factor is weakly identified. The weak-factor
claim is split into three separately classified confirmatory hypotheses so that
the reason for a failure is visible: H4a cross-sectional identification strength,
H4b influence stability, and H4c fitted-premium precision. Their numerical gates,
including the numerical factor-spanning criterion, are fixed in
`research/inference_contract.md`. Report

- rank of the beta matrix;
- singular values and condition number descriptively, without redundant
  rejection thresholds;
- cross-sectional standard deviation and interquartile range of each beta as
  descriptive statistics;
- cross-sectional dispersion of standardized exposures
  `beta_i_f * standard_deviation(factor_f)` as the confirmatory dispersion
  diagnostic;
- correlations among beta columns;
- first-stage factor relevance measures;
- misspecification-robust confidence sets where feasible;
- sensitivity to excluding one portfolio set at a time.

## Structural Change

Use both declared and estimated break tests. Regime analysis separates stability
of factor construction, portfolio betas, rate-attributable fitted premia,
pricing errors, and cross-sectional fit.

- Chow tests at predeclared policy boundaries;
- pooled time-series regime interaction tests for beta stability;
- regime-specific or locally estimated second-pass models for fitted-premium
  stability;
- pricing-error and fit comparisons on common asset-date intersections;
- pooled regime interactions with a single omitted baseline category;
- equivalence intervals against predeclared numerical economic bounds, decided by
  standard 5 percent TOST implemented as 90 percent interval inclusion;
- Quandt-Andrews unknown-break tests;
- Bai-Perron multiple-break tests with a minimum segment length;
- CUSUM and recursive residual diagnostics;
- rolling and expanding estimates with uncertainty bands.

Exploratory break dates do not replace the predeclared regime system. Boundary
sensitivity checks shift registered regime cutoffs under the configuration rules
and report whether classifications change.

The primary transition rule assigns a regime to the first calendar month lying
entirely under the new policy stance; the month containing the policy action
remains with the outgoing regime. The whole-transition-month rule is retained
as a declared sensitivity analysis only. Minimum regime-estimation eligibility
is frozen in `configs/regimes.yaml`: fewer than 36 months permits pooled
regime-interaction models only, 36 to 71 months permits flagged regime-specific
first-pass betas, and a standalone regime second pass additionally requires at
least 72 months, at least 10 test assets, and full beta-matrix rank. These
floors may not be relaxed for a regime that turns out to be short.

## Temporal Extension And Out-Of-Sample Design

The post-publication extension has two variants: a frozen-parameter evaluation
using the baseline estimates and a refitted evaluation using only information
available at each refit date. Out-of-sample records must store the forecast
origin, training window, refit schedule, model vintage, factor definition, asset
universe, benchmark, and loss function. No-lookahead rules apply to factor
construction, portfolio membership, and sample intersections.

## High-Frequency Decomposition

The high-frequency design is appendix-only until event data and generated
component artifacts exist. It starts from event-level announcement observations
with verified source terms. Event windows, identification variables, component
classification, ambiguous-event handling, monthly aggregation, and no-event
month treatment must be frozen before pricing tests are run. The primary tests
are spanning of the aggregate innovation by decomposed components, incremental
pricing content of the component factors, and component-level weak-factor
diagnostics. The components are constructed under an explicit announcement-based
identification design; causal language does not apply to the aggregate
autoregressive residual.

## Multiple Testing

The primary hypotheses and outputs are frozen in
`research/hypothesis_registry.csv`. Secondary tests use Holm adjustment within
named families. Exploratory findings are labelled exploratory.

Confirmatory families are replication, baseline pricing, temporal extension,
regime stability, and weak-factor diagnostics. The policy-information
decomposition is optional appendix material until its event-data and
factor-strength gates pass. A result can be statistically significant yet fail
the registered economic-magnitude criterion.

## Bootstrap

Use a stationary or moving-block bootstrap for serially dependent monthly data.
The block-length rule, number of draws, and random seed are configuration
values. Never mix bootstrap and asymptotic p-values without labels.

## Economic Significance

For every statistically significant change report

- effect in monthly percentage points;
- annualised effect only when mathematically meaningful;
- change relative to the original anomaly spread;
- impact on cross-sectional RMSE and maximum pricing error;
- confidence interval.

## Numerical Equivalence Bounds

The following bounds are fixed before extension results are observed:

- maximum rate-attributable fitted-premium change: at most 0.25 monthly
  percentage points;
- fitted-premium dispersion change: at most 25 percent of the baseline-regime
  value;
- cross-sectional RMSE deterioration: at most 10 percent of the baseline value;
- maximum absolute pricing-error deterioration: at most 0.25 monthly percentage
  points;
- cross-sectional fit deterioration: at most 0.10 when the fit statistic remains
  interpretable.

The rate-attributable fitted premium is
`pi_rate[i, s] = beta_rate[i, s] * lambda_rate[s]`. Equivalence is not evaluated
with an absolute raw risk-price bound because rescaling the short-rate factor
rescales beta and lambda without changing fitted returns.

## Method-To-Hypothesis Map

| Claim | Primary method | Decision rule |
|---|---|---|
| R1a | Short-rate innovation audit | Replication requires recovery within declared tolerances after inputs and artifacts exist. |
| R1b | First-pass beta audit | Replication requires recovery within declared tolerances after inputs and artifacts exist. |
| R1c | Cross-sectional risk-price audit | Replication requires recovery within declared tolerances after inputs and artifacts exist. |
| R1d | Pricing-error and fit audit | Replication requires recovery within declared tolerances after inputs and artifacts exist. |
| R1e | Comparator-model audit | Replication requires recovery within declared tolerances after inputs and artifacts exist. |
| R1f | Supplementary robustness audit | Replication requires recovery within declared tolerances after inputs and artifacts exist. |
| H1 | No-intercept two-pass OLS with Shanken correction and common-intersection comparator models | RMSE, MAE, and maximum pricing-error improvement must pass materiality thresholds against the strongest comparator. |
| H2 | Frozen and refitted post-publication two-pass evaluations | Sign, magnitude, and pricing-error compatibility must all hold. |
| H3 | Beta interaction tests plus regime-specific fitted-premium and error comparisons | Stability requires all dimensions to remain inside numerical bounds under 5 percent TOST with 90 percent intervals. |
| H4a | Beta-matrix rank, standardized exposure dispersion, and the numerical spanning regression | All three identification gates must pass. |
| H4b | Leave-one-anomaly-family refits and standardized influence diagnostics | No sign reversal, no materiality loss, and no portfolio with standardized influence of one or more. |
| H4c | Joint moving-block bootstrap of the rate-attributable fitted-premium spread | The 95 percent interval may not span both economically positive and negative effects. |
| E1 | Unknown-break tests | Exploratory only; does not confirm regime stability. |
| O1 | Optional monthly component spanning, pricing, and strength tests | Appendix-only unless event data and component-strength gates pass. |
