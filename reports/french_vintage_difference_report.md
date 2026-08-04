# Kenneth French Vintage Difference Report

Milestone: Empirical Input Acquisition and Baseline Reconstruction, Task 6.
Date: 2026-08-01.

This report compares the closest publication-era Kenneth French archives with
the current archives over their common sample. It records no empirical
conclusion about the paper.

Generated artifacts:

- `artifacts/provenance/kenneth_french/{DATASET}_{VINTAGE}.json`
- `artifacts/provenance/french_freeze_summary.csv`
- `artifacts/data_quality/french_vintage_summary.csv`
- `artifacts/data_quality/french_vintage_differences.csv`

## 1. Vintages acquired

The Kenneth French Data Library publishes only the current file; it does not
maintain a public archive of past vintages. The publication-era vintage was
therefore obtained from the Internet Archive, using the raw-content modifier so
that the stored bytes are the original ZIP rather than a rewritten page.

The article was published in *JFQA* 52(3), June 2017, and the local article PDF
carries a 30 June 2017 download stamp. The closest available snapshots are dated
**9 July 2017**, nine days after that stamp.

| Dataset | Vintage | Archive date | File | Monthly range | Obs. | Columns | Raw SHA-256 (first 12) |
|---|---|---|---|---|---|---|---|
| `F-F_Research_Data_Factors` | publication era | 2017-07-09 | `F-F_Research_Data_Factors_CSV.zip` | 1926-07 to 2017-05 | 1091 | Mkt-RF, SMB, HML, RF | `cb60eb74fa06…` |
| `F-F_Research_Data_Factors` | current | 2026-08-01 | `F-F_Research_Data_Factors_CSV.zip` | 1926-07 to 2026-05 | 1199 | Mkt-RF, SMB, HML, RF | `80b88699a18a…` |
| `F-F_Momentum_Factor` | publication era | 2017-07-09 | `F-F_Momentum_Factor_CSV.zip` | 1927-01 to 2017-05 | 1085 | Mom | `138a951385ae…` |
| `F-F_Momentum_Factor` | current | 2026-08-01 | `F-F_Momentum_Factor_CSV.zip` | 1927-01 to 2026-05 | 1193 | Mom | `37baf72ae4ea…` |
| `F-F_Research_Data_5_Factors_2x3` | publication era | 2017-07-09 | `F-F_Research_Data_5_Factors_2x3_CSV.zip` | 1963-07 to 2017-05 | 647 | Mkt-RF, SMB, HML, RMW, CMA, RF | `24553b6d6b93…` |
| `F-F_Research_Data_5_Factors_2x3` | current | 2026-08-01 | `F-F_Research_Data_5_Factors_2x3_CSV.zip` | 1963-07 to 2026-05 | 755 | Mkt-RF, SMB, HML, RMW, CMA, RF | `ddc0280b2bb8…` |

Both publication-era files cover the whole baseline window, so both are
compatible with the 2013-12 baseline endpoint.

Recorded per vintage in each manifest: archive date, file name, source URL,
provider, retrieval timestamp, raw ZIP checksum, extracted member name and
checksum, normalized checksum, column list, monthly date range, units, the
missing-value codes `-99.99` and `-999`, the observed missing-value count, the
descriptive header lines from the archive itself, HTTP validators, and the
redistribution status.

Units are `percent_per_month` for every column, taken from the archive's own
descriptive header rather than declared by this project. No missing values occur
in any monthly panel of any vintage.

Redistribution: raw archive bytes are retained locally under `data/raw/` and are
excluded from version control. This repository does not redistribute them.

## 2. Revision comparison

Tolerance: 0.005 percent per month, half of the smallest published increment,
since the archives are published to two decimals. A consequence worth stating
plainly is that **any genuine revision is at least 0.01 and therefore always
exceeds this tolerance.** The tolerance separates "identical" from "revised"; it
cannot separate "revised a little" from "revised a lot". The magnitude columns
do that.

### 2.1 Baseline window, 1972-01 to 2013-12 (504 months)

| Dataset | Column | Months differing | Share | Max abs. difference | Mean abs. difference |
|---|---|---|---|---|---|
| `F-F_Research_Data_Factors` | RF | 2 | 0.004 | 0.01 | 0.00004 |
| `F-F_Research_Data_Factors` | Mkt-RF | 318 | 0.631 | 0.15 | 0.0124 |
| `F-F_Research_Data_Factors` | SMB | 488 | 0.968 | 1.77 | 0.1081 |
| `F-F_Research_Data_Factors` | HML | 496 | 0.984 | 2.20 | 0.2007 |
| `F-F_Momentum_Factor` | Mom | 487 | 0.966 | 1.78 | 0.0923 |
| `F-F_Research_Data_5_Factors_2x3` | Mkt-RF | 322 | 0.639 | 0.15 | 0.0128 |
| `F-F_Research_Data_5_Factors_2x3` | SMB | 478 | 0.948 | 0.85 | 0.0741 |
| `F-F_Research_Data_5_Factors_2x3` | HML | 496 | 0.984 | 2.20 | 0.2007 |
| `F-F_Research_Data_5_Factors_2x3` | RMW | 485 | 0.962 | 1.18 | 0.1706 |
| `F-F_Research_Data_5_Factors_2x3` | CMA | 484 | 0.960 | 1.34 | 0.1159 |
| `F-F_Research_Data_5_Factors_2x3` | RF | 2 | 0.004 | 0.01 | 0.00004 |

### 2.2 Full common sample

The full-sample picture is the same in character. Over 1926-07 to 2017-05 the
three-factor file shows 649 of 1091 months revised for Mkt-RF (max 0.39), 1050
for SMB (max 2.50), 1036 for HML (max 3.65), and 7 for RF (max 0.01). Every row
is in `artifacts/data_quality/french_vintage_summary.csv` and every differing
month is in `artifacts/data_quality/french_vintage_differences.csv`.

### 2.3 Shared factors across the two archives

A review asked why `Mkt-RF` shows 318 differing months in the three-factor file
but 322 in the five-factor file over the identical baseline window, and why
`SMB` shows 488 against 478. The two archives publish overlapping factor names,
so the question is whether the shared columns are actually the same series.

They were checked directly. Artifact:
`artifacts/data_quality/french_shared_factor_consistency.csv`.

| Vintage | Factor | Months differing between the two archives | Max abs. | Verdict |
|---|---|---|---|---|
| `publication_era_20170709` | `Mkt-RF` | 0 | 0.00 | identical |
| `publication_era_20170709` | `HML` | 0 | 0.00 | identical |
| `publication_era_20170709` | `RF` | 0 | 0.00 | identical |
| `publication_era_20170709` | `SMB` | 499 | 3.48 | differs by construction, expected |
| `current_20260801` | `Mkt-RF` | **99** | **0.08** | **unexpected divergence** |
| `current_20260801` | `HML` | 0 | 0.00 | identical |
| `current_20260801` | `RF` | 0 | 0.00 | identical |
| `current_20260801` | `SMB` | 492 | 3.52 | differs by construction, expected |

Two distinct answers.

**`SMB` is not the same series in the two files and is not expected to be.** The
five-factor archive builds `SMB` from the three 2x3 sorts on size crossed with
book-to-market, operating profitability, and investment, averaged; the
three-factor archive builds it from the size and book-to-market sort alone. The
488 against 478 gap is therefore expected and carries no information about
vintage handling.

**`Mkt-RF` is the same series by definition, and in the publication-era vintage
the two files agree exactly.** In the current vintage they disagree in 99 of 504
baseline months, by at most 0.08. That is a property of the downloaded files,
not of the normalization in this repository: both were parsed by the same code
path, `RF` and `HML` agree exactly in the same comparison, and the
publication-era pair agrees exactly. The most likely explanation is that the two
current archives were regenerated by the library on different dates, so the
"current" five-factor file embeds a slightly older market series than the
"current" three-factor file.

Consequence for the design. The revision statistics in section 2.1 are computed
within each archive, comparing that archive's historical vintage with that
archive's current vintage, so they remain internally valid. But the market
factor must be taken from **one** named archive rather than assumed
interchangeable across files. The canonical panel takes `Mkt-RF` and `RF` from
`F-F_Research_Data_Factors` at `publication_era_20170709`, which is recorded per
column in `artifacts/provenance/baseline_panel_column_metadata.csv`. Any later
analysis that draws the market factor from the five-factor archive instead would
not be using the same series, and must say so.

## 3. Interpretation for the replication design

Three facts follow directly, and only these three.

**The risk-free return is stable.** `RF` differs in 2 of 504 baseline months,
each by exactly one reporting increment. This is the article's one rate input
with an unambiguous mapping to a single public series
(`research/publication_evidence_freeze.md`, RATE_EV_08), and it is also the input
least exposed to vintage risk. Portfolio excess returns can be formed from either
vintage without material consequence.

**The market factor is mildly revised.** `Mkt-RF` differs in about 63 percent of
baseline months, but the mean absolute revision is 0.012 percent per month
against a factor whose monthly standard deviation is above 4 percent. The largest
single revision is 0.15.

**The other comparator factors are substantially revised.** `SMB`, `HML`, `Mom`,
`RMW`, and `CMA` are revised in 95 to 98 percent of baseline months, with maximum
revisions between 0.85 and 2.20 percent per month and mean absolute revisions
between 0.07 and 0.20. These are the factors that enter the comparator models in
R1e and the secondary comparator family in H1.

Consequently the current file is **not** a substitute for the publication-era
file when auditing a published 1972-2013 comparator result. The design records
the following vintage assignment.

| Use | Vintage |
|---|---|
| Baseline replication targets R1b to R1f | `publication_era_20170709` |
| Baseline market excess return and risk-free return | `publication_era_20170709` |
| Post-2013 temporal extension | `current_20260801` |
| Regime analysis after 2013-12 | `current_20260801` |
| Revision analysis | both, compared as in this report |

The baseline panel built in Task 8 uses the publication-era vintage. Any later
result that uses the current file inside the baseline window must be labelled a
revised-history check, not a replication.

## 4. Limitation

The Internet Archive snapshot is dated nine days after the article's download
stamp and an unknown interval after the authors actually retrieved their data.
It is the closest publicly recoverable vintage, not a certified copy of the
authors' input. This vintage is therefore recorded as
`closest_recoverable_publication_era_vintage`, and it does not convert any
comparator target into an exact-replication target on its own.

## 5. Note on how this report is maintained

The figures in sections 1 and 2 are transcribed from the committed artifacts
`artifacts/provenance/french_freeze_summary.csv`,
`artifacts/data_quality/french_vintage_summary.csv`, and
`artifacts/data_quality/french_shared_factor_consistency.csv`. They are not
generated into this document, so a re-run of `scripts/acquire_french_factors.py`
against a different snapshot would leave the prose stale until it is updated by
hand. The artifacts are authoritative; where this report and an artifact
disagree, the artifact wins.
