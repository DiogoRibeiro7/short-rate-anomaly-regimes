# Test Asset Assembly Prompt

Complete Milestone 4.

## Public portfolio sets

Implement parsers for the exact Kenneth French monthly archives identified in the evidence freeze. Preserve original column labels in raw and map them to canonical ordered labels in processed data.

## Author and restricted sets

For asset growth, equity duration, and inventory growth

1. prefer the article's author-supplied portfolio returns;
2. otherwise implement a WRDS reconstruction only after the exact source-paper definitions are frozen;
3. record CRSP and Compustat filters, share codes, exchange codes, delisting returns, market equity, fiscal-year alignment, accounting lag, breakpoint universe, rebalancing month, missing characteristic treatment, and value-weighting formula;
4. add a synthetic-data test for the sort and weighting engine;
5. label reconstructed results `approximately_reproduced` until author data confirm them.

## Validation

- exactly 25 portfolios per set;
- canonical 5 by 5 ordering;
- no duplicate months;
- declared sample coverage;
- plausible return units;
- extreme spread direction and descriptive-statistic checks;
- value weights sum to one within each portfolio-month when security-level data are used.

## Outputs

Create a construction manifest with every formula and breakpoint rule. Generate a matrix showing which portfolio sets are exact, author-provided, reconstructed, or missing.
