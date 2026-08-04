# Economic Thresholds And Equivalence Bounds

These thresholds are fixed before empirical extension results are observed.

## Incremental Pricing Materiality

The primary ex ante comparator for H1 is the CAPM on the common asset-date
intersection. CAPM is chosen independently of observed RMSE because it is the
minimal non-short-rate benchmark and the direct baseline nesting comparison.
H1 is supported against the primary comparator only if the market plus
short-rate model satisfies all primary materiality gates:

- RMSE is at least 10 percent lower;
- MAE is at least 10 percent lower;
- maximum absolute cross-sectional pricing error is at least 0.25 monthly
  percentage points lower.

The strongest observed registered non-short-rate comparator by baseline
cross-sectional RMSE is retained as a secondary adversarial comparison. It does
not select the primary comparator and is reported with model-selection
uncertainty inside the secondary comparator family.

## Regime Equivalence

Risk-price equivalence is evaluated on rate-attributable fitted premia, not on
the raw short-rate risk price. For portfolio `i` and regime `s`,

`pi_rate[i, s] = beta_rate[i, s] * lambda_rate[s]`.

This object is invariant to rescaling the short-rate innovation because beta and
lambda rescale inversely while their product is unchanged.

The regime-stability claim is supported only if all primary equivalence gates
hold:

- maximum absolute change in `pi_rate[i, s]` is no more than 0.25 monthly
  percentage points for every registered portfolio;
- cross-sectional dispersion of `pi_rate[i, s]` changes by no more than 25
  percent relative to the baseline regime;
- cross-sectional RMSE deteriorates by no more than 10 percent relative to the
  baseline regime;
- maximum absolute cross-sectional pricing error deteriorates by no more than
  0.25 monthly percentage points;
- the selected fit metric deteriorates by no more than 0.10 when the fit metric
  is defined by the fit contract.

## Equivalence Decision Rule

Every equivalence bound above is evaluated with the single confirmatory rule
fixed in `research/inference_contract.md`: standard two one-sided tests at the 5
percent level, implemented as inclusion of the two-sided 90 percent
joint-bootstrap percentile interval inside the bound. The 95 percent
interval-inclusion variant is a stricter, non-standard-size procedure and is
reported only as a labelled sensitivity column.

## Factor Spanning

The numerical factor-spanning criterion is fixed in
`research/inference_contract.md`. The short-rate factor passes when the spanning
coefficient of determination against the registered non-short-rate comparator
factor set satisfies `R2_span <= 0.90`, equivalently a residual
standard-deviation ratio `s_span >= sqrt(0.10) = 0.31622776601683794`. The
residual cutoff is the exact value `sqrt(0.10)` rather than a decimal rounded
below it, so the two forms classify every boundary case identically. Both
statistics are scale free, so the criterion is unaffected by rescaling the
short-rate innovation.

## Rationale

The 0.25 monthly percentage-point pricing-error and fitted-premium bounds are
chosen because they are large enough to be economically visible in monthly
portfolio returns while still smaller than typical anomaly-spread magnitudes
studied in this literature. The 10 percent RMSE and MAE bounds require a model
comparison improvement that is not just rounding noise. The 25 percent
dispersion bound allows moderate composition changes while rejecting regime
claims driven by materially different cross-sectional exposure patterns.
