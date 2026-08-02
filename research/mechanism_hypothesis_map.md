# Mechanism And Hypothesis Map

This file records how the economic mechanisms map to falsifiable tests. It is a
design artifact, not a result artifact.

## Mechanism Channels

| Channel | Economic interpretation | Relevant anomaly families | Evidence status |
|---|---|---|---|
| Discount-rate and equity-duration exposure | A short-rate innovation can change the discount rate applied to future cash flows, so portfolios with different equity duration may load differently on the rate factor. | Equity duration, value, earnings-to-price | Mechanism is theoretically motivated; family-specific signs require generated betas and article-cell verification. |
| Cash-flow news | A rate innovation may contain news about future cash flows or expected macro conditions, not only discount-rate news. | Book-to-market, earnings-to-price, reversal | Interpretation requires separating aggregate innovations from identified announcement components. |
| Financing constraints and balance-sheet sensitivity | Rate news can change financing costs and external-finance constraints, so firms with different investment or balance-sheet profiles may have different exposures. | Investment-to-assets, property-plant-and-equipment investment | Direction is not predeclared without verified family-level evidence. |
| Inventory and working-capital channel | Rate changes can affect inventory financing and working-capital demand. | Inventory growth | Direction is not predeclared without verified family-level evidence. |
| Monetary-policy information | Announcement surprises can mix policy-rate news with central-bank information about growth or inflation. | All registered anomaly families | Appendix-only unless event data, component labels, monthly aggregation, and component-strength diagnostics are available. |
| Intertemporal hedging demand | If the short rate forecasts investment opportunities, investors may pay premia for assets that hedge adverse rate-state news. | Joint anomaly system | Baseline ICAPM mechanism; requires weak-factor diagnostics before interpretation. |

## Hypothesis Links

| Claim | Mechanism link | Primary test | Interpretation boundary |
|---|---|---|---|
| R1a--R1f | Numerical replication of registered article statistics by layer | Innovation, beta, risk-price, pricing-error, comparator, and supplement tolerance audits | Numerical recovery is not an economic mechanism test. |
| H1 | ICAPM hedging demand and cross-sectional beta differences | Incremental pricing performance relative to the ex ante CAPM comparator, with strongest-observed comparator reported as secondary adversarial analysis | A pricing improvement is not a causal policy interpretation. |
| H2 | Persistence of the state-variable price of risk | Post-publication compatibility classification | A nonzero risk price is insufficient without sign, magnitude, and pricing-error compatibility. |
| H3 | Monetary-regime dependence of factor construction, beta, fitted-premium, and pricing-error mappings | Separate beta-interaction tests and regime-specific fitted-premium tests | Ordinary non-rejection of equality cannot support invariance. |
| H4a | Cross-sectional identification strength of the short-rate factor | Beta-matrix rank, standardized exposure dispersion, and the numerical spanning criterion | Weak identification limits interpretation even when pricing errors look small. |
| H4b | Influence stability of the fitted-premium conclusion | Leave-one-anomaly-family refits and standardized influence diagnostics | A conclusion carried by one family or one portfolio is fragile rather than general. |
| H4c | Precision of the rate-attributable fitted premium | Joint moving-block bootstrap interval for the fitted-premium spread | An interval spanning both economic directions cannot support a sign claim. |
| E1 | Unregistered structural instability | Exploratory unknown-break tests | Break alignment is hypothesis-generating only. |
| O1 | Aggregate innovation versus decomposed announcement information | Optional component spanning, pricing, and strength diagnostics | Appendix-only until the component factors have usable evidence. |

## Sign Discipline

The manuscript does not predeclare family-level signs unless the article or a
verified literature source supports the direction and the generated beta
artifacts confirm that the family definition matches the target. Directional
language for book-to-market, equity duration, earnings-to-price, reversal,
investment-to-assets, property-plant-and-equipment investment, and inventory
growth is therefore restricted to relative exposure diagnostics until the
baseline artifacts exist.
