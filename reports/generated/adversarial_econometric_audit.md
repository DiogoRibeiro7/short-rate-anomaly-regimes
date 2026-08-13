# Adversarial Econometric Audit

## Verdict

Classification: `potentially_publishable_after_major_revision`.

The empirical programme is run and its registered gates are reported, but the state variable is not identified, so the contribution is a documented reconstruction and extension rather than an identified asset-pricing result.

The archive ships the result tables and diagnostics the manuscript cites. It does not ship the data panels or estimate stores behind them; those are regenerated with `make reproduce` from the frozen public sources. A reviewer who wants to re-derive rather than re-read the numbers must run that rebuild.

## Findings

### MAJOR: State-variable interpretation is not yet identified

- Claim threatened: a short-rate innovation prices anomaly returns as a stable hedging state variable.
- Econometric reason: an AR residual is an innovation relative to the fitted rate model, but it does not by itself separate monetary policy, information, macro news, or measurement components.
- Decisive diagnostic: compare beta pricing before and after registered shock decomposition and spanning tests.
- Repair: keep causal interpretation out of non-identification sections and require the shock-decomposition gate before stronger language.

### MAJOR: Two-pass inference is not independently verifiable from the archive

- Claim threatened: the short-rate factor earns one common cross-sectional price of risk.
- Econometric reason: factor strength, standardized exposure dispersion, sample intersection, and covariance corrections cannot be re-evaluated from the shipped result tables alone, because the first-pass and cross-section estimate stores are not distributed.
- Decisive diagnostic: inspect standardized exposure dispersion, weak-factor flags, GRS tests, Fama-MacBeth uncertainty, and leave-one-anomaly-family systems.
- Repair: rebuild the baseline artifacts with `make reproduce` and rerun the robustness diagnostics against the rebuilt estimate stores.

### MAJOR: Out-of-sample and shock-decomposition claims remain blocked

- Claim threatened: forecast falsification and the policy-information split of the aggregate innovation.
- Econometric reason: the decomposed shock series does not exist, because the only source separating the components begins in 1990 and reaches 287 of the 504 baseline months, so the decomposition was retired rather than run. The out-of-sample comparison no longer belongs in this paragraph: it is run.
- Decisive diagnostic: rerun the shock and out-of-sample gates once compatible event-level and forecast inputs exist.
- Repair: acquire the event-level data or retire the design, and preserve null or unstable results in the reports.
