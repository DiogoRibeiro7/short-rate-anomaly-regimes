# Final Design Consistency Gate Change Log

Verdict: `BLOCKED`.

> Superseded in part. The Empirical Input Acquisition and Baseline
> Reconstruction milestone applied eight further design corrections and acquired
> the rate, market, and portfolio inputs. See
> `reports/design_correction_changelog.md` and
> `reports/baseline_input_readiness.md`, whose verdict is `PARTIAL`.

The design gate is internally consistent after this pass, but empirical
execution remains blocked at the data-acquisition and post-2013 extension stages
because source-compatible anomaly portfolios, CRSP/Compustat access, exact source
vintages, and generated baseline artifacts are unavailable.

## Changes

- Separated current affiliation, former affiliation, present address, ORCID, and
  corresponding-author metadata on the manuscript title page.
- Expanded the short-rate registry so FEDFUNDS, TB3MS, and DTB3 carry exact
  article, documented reconstruction, sensitivity, download, vintage,
  transformation, and replication-eligibility statuses.
- Replaced scale-dependent raw beta comparison rules with standardized exposure
  dispersion and fitted-premium diagnostics.
- Froze CAPM as the primary ex ante comparator and moved strongest-observed
  comparator analysis to a secondary adversarial check.
- Added an executable bootstrap contract with selector failure conditions and a
  fixed 12-month fallback.
- Added a data-access feasibility report that does not assume CRSP, Compustat,
  or WRDS access.
- Added a citation-support audit and narrowed the French Data Library revision
  claim.

## Author Metadata Decisions Requiring Confirmation

- Confirm whether the School of Media Arts and Design, Polytechnic of Porto is
  the current affiliation.
- Confirm whether MySense should be retained only as a former affiliation.
- Confirm whether the Polytechnic of Porto address should also be the present
  address for correspondence.
- Confirm the ORCID `0009-0001-2022-7072`.
- Confirm the corresponding email `dfr@esmad.ipp.pt`.
