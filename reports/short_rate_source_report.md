# Short-Rate Source Report

Milestone: Empirical Input Acquisition and Baseline Reconstruction, Tasks 3 and 4.
Retrieval date: 2026-08-01. Vintage label: `fred_current_retrieved_2026-08-01`.

This report describes acquisition, provenance, and the monthly-aggregation audit
of the short-rate inputs. It records no empirical conclusion about the paper.

Generated artifacts:

- `artifacts/provenance/short_rate/{SERIES}_2026-08-01.json` — per-series freeze manifests
- `artifacts/provenance/short_rate_freeze_summary.csv`
- `artifacts/data_quality/aggregation_audit.csv`
- `artifacts/data_quality/aggregation_differences.csv`
- `artifacts/data_quality/aggregation_decimal_check.csv`

## 1. Frozen series

| Series | Role | Observations | Range | Observed frequency | Missing | Raw SHA-256 (first 16) |
|---|---|---|---|---|---|---|
| `FEDFUNDS` | Documented reconstruction of the article federal funds rate | 864 | 1954-07-01 to 2026-06-01 | monthly, first-of-month stamped | 0 | `0e4652172489…` |
| `TB3MS` | Documented reconstruction of the article 3-month Treasury-bill rate | 1110 | 1934-01-01 to 2026-06-01 | monthly, first-of-month stamped | 0 | `ac6c866c6e9f…` |
| `DTB3` | Sensitivity input only | 18934 | 1954-01-04 to 2026-07-30 | business daily | 799 | `6d764a1a12b6…` |
| `DFF` | Aggregation-audit input only; not a replication input | 26328 | 1954-07-01 to 2026-07-30 | daily including weekends | 0 | `c85aa2518db6…` |

Full checksums, retrieval timestamps, normalized checksums, HTTP validators, and
declared metadata are in the per-series manifests. Raw provider bytes are written
once under `data/raw/fred/{SERIES}/` and the writer refuses to overwrite an
existing file whose bytes differ.

Every series carries two checksums:

- the **raw** SHA-256 of the provider payload exactly as delivered;
- the **normalized** SHA-256 of a canonical `date,value` serialization with ISO
  dates, fixed decimal formatting, sorted rows, and the provider missing-value
  code `.` rendered as an empty field. The normalized checksum is what later
  vintage comparisons use, so a pure formatting change on the provider side does
  not masquerade as a data revision.

Redistribution status for all four series: `public_domain_us_government_work`.
The underlying rates are Federal Reserve H.15 publications redistributed by the
Federal Reserve Bank of St. Louis.

## 2. Metadata provenance limitation

Units, frequency, seasonal adjustment, aggregation description, and source notes
are **declared by this project**, not retrieved from a provider metadata
endpoint. The FRED series pages (`fred.stlouisfed.org/series/*`) and the plain
text metadata endpoint (`fred.stlouisfed.org/data/*.txt`) both refuse automated
requests from this environment, and no `FRED_API_KEY` is configured. Only the
graph CSV endpoint is reachable.

Every declared field is therefore audited against the payload and the audit
result is stored in each manifest under `declared_metadata_audit`:

| Declared field | Audit performed | Result |
|---|---|---|
| Frequency | Classified from the observation dates themselves | Consistent for all four series |
| Units | Magnitude range check against percent-per-annum | Consistent for all four series |
| Seasonal adjustment | Not verifiable from the payload | Recorded as unconfirmed |
| Source notes | Not verifiable from the payload | Recorded as unconfirmed |

Open item: supplying a `FRED_API_KEY` would allow the units, seasonal
adjustment, and notes fields to be retrieved rather than declared. This does not
block the milestone because the aggregation audit in section 3 establishes the
units and the aggregation rule directly from the data.

## 3. Monthly-aggregation audit

The audit does not assume that a provider monthly series equals an arithmetic
aggregation of the corresponding daily series. Four candidate rules were
computed explicitly and compared month by month.

Declared tolerances, fixed before the comparison:

- primary: 0.005 percentage points, half of the smallest published increment,
  since both the monthly and the daily series are published to two decimals;
- secondary: 0.01 percentage points, one full increment.

Only months in which the daily series covers the whole calendar month enter the
comparison.

### 3.1 Results

| Monthly | Daily | Rule | Complete months | Max abs. difference | Share within primary tolerance | Verdict |
|---|---|---|---|---|---|---|
| `FEDFUNDS` | `DFF` | calendar-day mean | 864 | 0.005000 | 1.0000 | reproduced within primary tolerance |
| `FEDFUNDS` | `DFF` | business-day mean | 864 | 0.285714 | 0.3831 | **not** reproduced |
| `TB3MS` | `DTB3` | mean of available observations | 869 | 0.005000 | 1.0000 | reproduced within primary tolerance |
| `TB3MS` | `DTB3` | month-end last observation | 869 | 2.810000 | 0.0725 | **not** reproduced |

### 3.2 Exact-decimal confirmation

The tolerance test above leaves open whether the residual differences are
rounding or something else. A second test parses both payloads as decimal
strings rather than binary floats and asks whether the published monthly value
equals the daily mean rounded half-up to two decimals.

| Monthly | Daily | Rule | Exact decimal matches | Verdict |
|---|---|---|---|---|
| `FEDFUNDS` | `DFF` | calendar-day mean | 864 / 864 | monthly series is the rounded daily mean for every complete month |
| `FEDFUNDS` | `DFF` | business-day mean | 329 / 864 | not the rounded daily mean |
| `TB3MS` | `DTB3` | mean of available observations | 869 / 869 | monthly series is the rounded daily mean for every complete month |

This confirms both required statements exactly, not approximately:

- **FEDFUNDS monthly observations are averages of daily figures.** The rule is a
  calendar-day mean over all `DFF` observations in the month, rounded half-up to
  two decimals. The business-day-only mean is decisively rejected: `DFF`
  publishes an observation for every calendar day, and excluding weekends
  reproduces the published value in only 38 percent of months with a maximum
  error of 0.29 percentage points.
- **TB3MS is a monthly average of business-day observations.** The rule is the
  mean of the available (non-missing) `DTB3` observations in the month, rounded
  half-up to two decimals. Holidays are absent from `DTB3` and are simply not
  averaged; no imputation is required or performed.

### 3.3 DTB3 versus TB3MS

The instruction not to assume that `TB3MS` and an arithmetic aggregation of
`DTB3` are identical is respected and the result is stated precisely.

They are **not identical**. The published `TB3MS` value equals the `DTB3` monthly
mean only after rounding to the published two decimals. Before rounding, the two
differ in 840 of 869 complete months, with a mean absolute difference of 0.0025
and a maximum of 0.0050 percentage points. The differences are bounded exactly by
half a reporting increment and are fully explained by publication rounding.

The declared tolerance under which `DTB3` aggregation is treated as reproducing
`TB3MS` is therefore **0.005 percentage points**, and the relationship is
recorded as "equal after publication rounding", not "equal".

The rejected alternative matters: taking the month-end `DTB3` observation instead
of the monthly mean reproduces `TB3MS` in only 7 percent of months and reaches a
maximum error of 2.81 percentage points. A month-end convention would be a
materially different series.

### 3.4 Coverage note

`TB3MS` begins 1934-01 while `DTB3` begins 1954-01, so 241 months of `TB3MS` have
no daily counterpart and cannot be audited. Those months lie entirely before the
1972-01 baseline start and do not affect any replication target.

## 4. Replication-eligibility consequences

The aggregation audit establishes what the monthly series *are*. It does not
establish which series the article used, because the article names only "the St.
Louis Federal Reserve Bank" with no series code, vintage, or aggregation rule
(see `research/publication_evidence_freeze.md`, section 2.1).

Consequently:

- `FEDFUNDS` remains a **documented reconstruction** of the article's federal
  funds rate concept, not a verified exact input.
- `TB3MS` remains a **documented reconstruction** of the article's 3-month
  Treasury-bill rate concept. The article's phrase "3-month TB rate" does not
  distinguish the secondary-market, auction-based, and constant-maturity
  variants; `TB3MS` is the secondary-market discount-basis rate.
- `DTB3` is a **sensitivity input only**. Neither the article nor the supplement
  names a daily source or a daily-to-monthly aggregation rule, so no daily
  construction can carry an exact-replication label.
- `DFF` is an **audit input only** and enters no replication or extension
  estimate.

A successful numerical match against the article's published AR(1) coefficients
would not change these labels. Source identity, not numerical proximity, decides
the replication mode.
