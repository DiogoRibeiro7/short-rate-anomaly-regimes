# Policy-Information Decomposition: Feasibility and Retirement

Date: 2026-08-11.
Verdict: **retired from the design**, on the pre-registered factor-strength
condition, before any pricing estimate using these data was produced.

## Why this record exists

The decomposition was carried as an appendix design from the beginning, and its
generated report said `blocked_missing_input` against event-level
high-frequency data the repository did not hold. Three other gates in this
project turned out not to be blocked at all once someone checked, so the claim
was tested rather than inherited. The data are obtainable. The design is still
not viable, and the reason is one the manuscript fixed in advance.

## What was checked

The frozen selection in `research/shock_dataset_selection.csv` names
`jarocinski_karadi_fed_shocks_update_202401`, served from a public GitHub
repository. It exists, is 54 KB, and carries the files the design needs: an
event-level surprise file and a monthly aggregation of the decomposed policy and
central-bank-information components.

Two properties were then read off the monthly file itself rather than from its
documentation, which understated the start date by two years.

### 1. It cannot reach the baseline

Coverage runs from 1990-02 to 2024-01, 408 months.

| Window | Months covered |
|---|---|
| Baseline, 1972-01 to 2013-12 | 287 of 504, 57 percent |
| Extension, 2014-01 to 2025-12 | 121 of 144, 84 percent |

The uncovered 217 baseline months are the first eighteen years, which contain
the Volcker disinflation and the largest short-rate movements in the sample.
A decomposition estimated on what remains cannot be a check on the baseline
pricing result, because it does not see the period that supplies most of the
factor's variation.

### 2. The components are sparse, which the design already forbids

`configs/extensions.yaml` names `poor_mans_sign_restriction` as the primary
identification. Under it, on the 408 covered months:

| Component | Months with a nonzero value | Standard deviation |
|---|---|---|
| `MP_pm`, policy | 188 of 408, 46 percent | 0.0550 |
| `CBI_pm`, information | 99 of 408, 24 percent | 0.0159 |

The manuscript's appendix design states the disqualifying condition in advance:
the monthly aggregation "can create sparse factors with many no-event months, so
the decomposition must pass factor-strength diagnostics before entering the main
pricing argument." An information component that is exactly zero in three
quarters of months is that case.

The project's own power evidence sharpens it. Estimated rate betas carry a
reliability ratio of 0.386 over 648 dense months, so 61.4 percent of their
cross-sectional dispersion is first-pass estimation error. A factor that is zero
in 76 percent of a 408-month window would be identified from far less variation
than that, and the registered equivalence work has already shown that
regime-length samples cannot resolve fitted-premium differences at all.

## Why this is not an outcome-dependent retirement

Both facts are properties of the **source**, not of any estimate. Coverage and
sparsity were read from the published data file before a single pricing
regression was run on it, and neither depends on what the decomposition would
have found. The condition being applied, factor strength before entry into the
pricing argument, was written into the manuscript's appendix design and is not
introduced here.

Retiring a design element after estimation is still a design change, and it is
recorded as design correction 16 with this date. What is not claimed is that the
decomposition was tried and failed. It was not tried. It is withdrawn because
the data cannot support the question it was written to answer.

## Licence, recorded for completeness

The source repository states no licence. It is publicly downloadable and asks to
be cited as Jarocinski, M. and Karadi, P. (2020), "Deconstructing Monetary Policy
Surprises: The Role of Information Shocks", *American Economic Journal:
Macroeconomics*, DOI `10.1257/mac.20180090`. No file from it is redistributed
here, and none is committed to this repository. This record contains only
summary counts computed from it.

## What would reopen the question

A source with pre-1990 coverage and a policy-information split, or an
identification whose components are populated in most months rather than a
minority of them. Neither exists in the candidate set frozen in
`research/shock_dataset_selection.csv`, whose three rejected alternatives were
rejected for reasons that do not include coverage and would not repair it.
