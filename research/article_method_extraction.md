# Article Method Extraction

## Milestone 0 Status

Status: `BLOCKED_ARTICLE_EXTRACTION`

The final article PDF and publisher supplement are not present under `references/private`, so the line-by-line method extraction required by Milestone 0 cannot be completed yet.

## Located Public Records

- Official article page: Cambridge Core, `https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/shortterm-interest-rates-and-stock-market-anomalies/C45C802016F615FA5FB6D79A2FF445CC`
- DOI: `10.1017/S002210901700028X`
- Published online: 15 June 2017
- Journal: `Journal of Financial and Quantitative Analysis`
- Volume and issue: `52(3)`
- Pages: `927-961`
- Publisher page lists supplementary material of 303.8 KB.
- Paulo Maio's article page links both the article entry and an appendix entry for the same publication.

## Public Abstract-Level Extraction

The Cambridge page identifies the article as a two-factor asset-pricing study of CAPM anomalies including value, return reversal, equity duration, asset growth, and inventory growth. It identifies the key additional factor as an innovation in a short-term interest rate, using the federal funds rate or a Treasury-bill rate.

This abstract-level information is not sufficient to freeze estimator definitions, table targets, covariance rules, or exact data definitions.

## Required Private Inputs

Place legally obtained files at:

- `references/private/article.pdf`
- `references/private/supplement.pdf`

Then generate `artifacts/evidence/article_manifest.json` or YAML-compatible JSON with:

- title, authors, DOI, journal, volume, issue, pages, and publication date;
- local path for each private evidence file;
- SHA-256 checksum for each file;
- access note describing the legal basis for private research use.

## Blocking Ambiguities

- `BLOCKED_ARTICLE_EXTRACTION`: final article PDF unavailable locally.
- `BLOCKED_ARTICLE_EXTRACTION`: publisher supplement unavailable locally.
- `BLOCKED_ARTICLE_EXTRACTION`: table, panel, row, and column locators cannot be extracted.
- `BLOCKED_ARTICLE_EXTRACTION`: exact sample endpoints, rate definitions, portfolio definitions, weighting rules, covariance estimators, and lag rules cannot be frozen.
- `BLOCKED_ARTICLE_EXTRACTION`: working-paper versus final-article differences cannot be audited.

## Consequence

Strict replication remains blocked. The repository may continue only in documented reconstruction mode until the private evidence files are available and this extraction is completed.
