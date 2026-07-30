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

## Rules

- Store raw source units unchanged.
- Convert units only in a named transformation step.
- Never infer percent versus decimal from magnitude alone.
- Preserve both source date and canonical month when release timing matters.
- Do not forward-fill returns or shock series.
