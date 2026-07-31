# Data Access Feasibility

Verdict for the post-2013 extension: `BLOCKED`.

The extension cannot proceed as an exact continuation until CRSP, Compustat, and
the CRSP/Compustat linking table are confirmed. The current repository does not
assume WRDS access. Public substitute portfolios may support documented
reconstruction analyses, but they do not support exact continuation labels.

| Family | Required CRSP Variables | Required Compustat Variables | Required Linking Table | First Feasible Formation Date | Original Rule Available | Current Database Access | Redistribution | Complexity | Exact Continuation Feasible | Documented Reconstruction Feasible | Public Substitute Available | Blocked If Access Unavailable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| book_to_market | PERMNO, date, return, delisting return, shares, price, exchange code | book equity inputs, fiscal year-end dates | CCM link table with valid link dates and link types | 1972-01 after accounting lag and baseline filters | unavailable in executable form | unconfirmed | prohibited for licensed extracts | medium | no | yes after WRDS access or verified public file | yes, French size-BM portfolios for robustness only | yes |
| equity_duration | PERMNO, date, return, delisting return, shares, price, exchange code | earnings, book equity, payout and forecast inputs required by the source formula | CCM link table with valid link dates and link types | 1972-01 after accounting lag and source formula freeze | unavailable in executable form | unconfirmed | prohibited for licensed extracts | high | no | yes after formula and WRDS access are frozen | no exact public substitute registered | yes |
| earnings_to_price | PERMNO, date, return, delisting return, shares, price, exchange code | earnings, common equity, fiscal year-end dates | CCM link table with valid link dates and link types | 1972-01 after accounting lag and positive-price filters | unavailable in executable form | unconfirmed | prohibited for licensed extracts | medium | no | yes after WRDS access and rule freeze | yes, documented public E/P portfolios if source-compatible | yes |
| long_term_reversal | PERMNO, date, return, delisting return, shares, price, exchange code | none unless accounting filters are required | CCM link table only if Compustat filters are used | 1972-01 after return-history window and skip-month rule | unavailable in executable form | unconfirmed | prohibited for licensed extracts | medium | no | yes after CRSP access and rule freeze | yes, French long-term reversal portfolios for robustness only | yes |
| investment_to_assets | PERMNO, date, return, delisting return, shares, price, exchange code | total assets and fiscal year-end dates | CCM link table with valid link dates and link types | 1972-01 after accounting lag | unavailable in executable form | unconfirmed | prohibited for licensed extracts | medium | no | yes after WRDS access and rule freeze | yes, q-factor or public investment portfolios for robustness only | yes |
| ppe_investment | PERMNO, date, return, delisting return, shares, price, exchange code | property plant and equipment, investment inputs, fiscal year-end dates | CCM link table with valid link dates and link types | 1972-01 after accounting lag | unavailable in executable form | unconfirmed | prohibited for licensed extracts | high | no | yes after WRDS access and rule freeze | no exact public substitute registered | yes |
| inventory_growth | PERMNO, date, return, delisting return, shares, price, exchange code | inventory, total assets or sales controls if required, fiscal year-end dates | CCM link table with valid link dates and link types | 1972-01 after accounting lag | unavailable in executable form | unconfirmed | prohibited for licensed extracts | high | no | yes after WRDS access and rule freeze | no exact public substitute registered | yes |

PASS conditions: database access must be confirmed, source rules must be frozen,
licensed extracts must remain unredistributed, and every generated continuation
artifact must carry a reconstruction or exact-continuation label.
