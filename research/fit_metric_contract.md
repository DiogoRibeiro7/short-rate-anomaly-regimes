# Cross-Sectional Fit Metric Contract

This contract fixes how fit is reported before empirical results are generated.

## Primary Fit Metric

The primary fit statistic is the article's exact cross-sectional fit definition
when it can be verified from the article, supplement, or author code.

### Status: verified

The article states the definition explicitly, so the primary metric applies and
the fallback below is not used for the baseline targets.

`article_cross_sectional_fit = 1 - var_N(alpha_cs[i]) / var_N(mean_excess_return[i])`

where `var_N` is the cross-sectional variance across test assets. Source:
article page 933, equation (6). The article notes at page 933 footnote 13 that
the metric can be negative because the second pass has no intercept.

A second, constrained variant applies only to comparator models whose factors
are traded excess returns:

`article_constrained_fit = 1 - var_N(alpha_constrained[i]) / var_N(mean_excess_return[i])`

where the constrained pricing errors restrict each risk price to the sample mean
of the corresponding factor. Source: article page 934, equations (7) and (8).
The article states that this restriction does not apply to the ICAPM because the
hedging factors are not traded returns, so the constrained variant may never be
used for the short-rate model.

Because `var_N` is a centred cross-sectional variance, the article metric and the
uncentred fallback below are not interchangeable and must never share a label.

## Mechanical Fallback

If the article's exact definition cannot be verified, the manuscript reports a
pricing-error pseudo-fit:

`pseudo_R2 = 1 - sum(alpha_cs[i]^2) / sum(mean_return[i]^2)`.

This fallback is mechanically compatible with the no-intercept second pass
because it compares squared pricing errors with squared average returns around
zero rather than around the cross-sectional mean.

## Reporting Rule

- Never mix centred and uncentred fit statistics under one label.
- If the article fit definition is used, label it `article_cross_sectional_fit`.
- If the constrained variant is used, label it `article_constrained_fit`, never
  `article_cross_sectional_fit`. Both are centred and share a denominator, but
  their numerators are different statistics: the unconstrained metric uses the
  estimated cross-sectional risk prices while the constrained metric restricts
  each risk price to the corresponding factor's sample mean. Reporting them
  under one label would mix two estimands and would breach the rule above. The
  constrained label may be applied only to comparator models whose factors are
  traded excess returns, and never to the short-rate ICAPM.
- If the fallback is used, label it `pricing_error_pseudo_R2`.
- A table or figure that shows more than one of these three metrics must label
  each column separately and must not rank models across labels.
- The phrase "fit is interpretable" means exactly that the denominator in the
  selected fit statistic is positive and the same asset-date intersection is
  used for every model in the comparison.
- If the denominator is zero or model intersections differ, suppress the fit
  comparison and report pricing-error metrics only.
