# Adversarial Econometric Audit

## Verdict

Classification: `potentially_publishable_after_major_revision`.

The current contribution is a release-ready research scaffold, not an identified empirical asset-pricing result.

## Findings

### MAJOR: State-variable interpretation is not yet identified

- Claim threatened: a short-rate innovation prices anomaly returns as a stable hedging state variable.
- Econometric reason: an AR residual is an innovation relative to the fitted rate model, but it does not by itself separate monetary policy, information, macro news, or measurement components.
- Decisive diagnostic: compare beta pricing before and after registered shock decomposition and spanning tests.
- Repair: keep causal interpretation out of non-identification sections and require the shock-decomposition gate before stronger language.

### MAJOR: Two-pass inference is unverified under missing generated artifacts

- Claim threatened: the short-rate factor earns one common cross-sectional price of risk.
- Econometric reason: factor strength, standardized exposure dispersion, sample intersection, and covariance corrections cannot be evaluated without first-pass and cross-section artifacts.
- Decisive diagnostic: inspect standardized exposure dispersion, weak-factor flags, GRS tests, Fama-MacBeth uncertainty, and leave-one-anomaly-family systems.
- Repair: generate baseline artifacts and rerun robustness diagnostics before reporting a pricing verdict.

### MAJOR: Extension and out-of-sample claims are blocked

- Claim threatened: post-2013 performance, monetary-regime instability, and forecast falsification.
- Econometric reason: the extension panel and frozen training vintages are absent, so there is no valid holdout comparison or predeclared regime inference.
- Decisive diagnostic: rerun temporal, regime, shock, and out-of-sample gates after compatible panels exist.
- Repair: freeze source vintages, produce monthly panels, and preserve null or unstable results in the reports.
