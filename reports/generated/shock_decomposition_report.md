# Shock Decomposition Report

Verdict: `retired_from_design`

Selected dataset: `jarocinski_karadi_fed_shocks_update_202401`
Reason: `source_cannot_cover_baseline_and_components_are_sparse`

The policy-information decomposition has been withdrawn from the design. It is not blocked and is not awaiting data: the selected source was obtained and examined, and it cannot support the question the design was written to ask. Coverage begins in 1990, so the source reaches 287 of the 504 baseline months and cannot speak to the period that supplies most of the short-rate variation being priced. Under the primary identification its central-bank-information component is nonzero in 99 of 408 months, and the design states in advance that a sparse monthly factor must not enter the pricing argument.

Both facts are properties of the source rather than of any estimate, and both were read before any pricing regression used these data. Nothing was tried and found wanting; the design is withdrawn because the data cannot answer it. The AR residual remains labelled a rate innovation, not a policy shock, which is the labelling this decomposition would have been needed to revise.

See `reports/shock_decomposition_feasibility.md` for the counts and `reports/design_correction_changelog.md` correction 16 for the record.
