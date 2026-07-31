# Cross-Sectional Fit Metric Contract

This contract fixes how fit is reported before empirical results are generated.

## Primary Fit Metric

The primary fit statistic is the article's exact cross-sectional fit definition
when it can be verified from the article, supplement, or author code.

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
- If the fallback is used, label it `pricing_error_pseudo_R2`.
- The phrase "fit is interpretable" means exactly that the denominator in the
  selected fit statistic is positive and the same asset-date intersection is
  used for every model in the comparison.
- If the denominator is zero or model intersections differ, suppress the fit
  comparison and report pricing-error metrics only.
