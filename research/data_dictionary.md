# Data Dictionary

## Canonical monthly panel

| Column | Type | Unit | Meaning |
|---|---|---|---|
| `date` | month-end timestamp | calendar month | Canonical observation month |
| `mkt_rf` | float | percentage points per month | Market excess return |
| `rf` | float | percentage points per month | One-month risk-free return used for excess returns |
| `fed_funds_rate` | float | annual percentage rate | Verified monthly federal funds rate definition |
| `tbill_rate` | float | annual percentage rate | Verified article Treasury-bill rate definition |
| `fed_funds_innovation` | float | rate units | AR residual or verified alternative |
| `tbill_innovation` | float | rate units | AR residual or verified alternative |
| `regime` | string | category | Deterministic monetary regime |
| portfolio columns | float | percentage points per month | Value- or equal-weighted portfolio returns |

## Source Status Classes

| Class | Meaning |
|---|---|
| exact | The article definition, source, vintage, transformation, and estimator input have been verified and frozen. |
| approximate | A documented public or reconstructed substitute is used with its own label and cannot support strict replication by itself. |
| unavailable | The source is required or planned, but the file, legal terms, vintage, or transformation remains unresolved. |

## Portfolio Families

| Family | Baseline role | Construction status |
|---|---|---|
| book-to-market deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |
| equity-duration deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |
| earnings-to-price deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |
| long-term reversal deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |
| investment-to-assets deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |
| property-plant-and-equipment investment deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |
| inventory-growth deciles | Article main anomaly family | Source provider verified; exact file and vintage still require freeze. |

## Rules

- Store raw source units unchanged.
- Convert units only in a named transformation step.
- Never infer percent versus decimal from magnitude alone.
- Preserve both source date and canonical month when release timing matters.
- Do not forward-fill returns or shock series.
- Align comparator models on the same asset-date intersection within each
  comparison.
- Preserve delisting and survivorship treatment from the verified source when
  the source documentation specifies it; otherwise label the treatment
  unavailable rather than inferring it.
