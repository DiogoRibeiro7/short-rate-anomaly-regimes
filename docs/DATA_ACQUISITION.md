# Data Acquisition Guide

This repository does not redistribute copyrighted articles, publisher supplements, licensed raw data, author-supplied files, or prompt files.

## Public Processed Data Redistribution

No public processed data file is currently redistributed beyond tracked placeholders. Before adding processed data, record source licence and redistribution rights in `research/data_access_matrix.csv`.

## Source Instructions

| Source | Access | Exact Definition | Acquisition Path | Redistribution | Notes |
|---|---|---|---|---|---|
| `article_pdf` | `present_private_file` | `true` | `references/private/maio2017.pdf` | `do_not_redistribute` | Local private article PDF present at references/private/maio2017.pdf with SHA-256 recorded in artifacts/evidence/article_manifest.json |
| `article_supplement` | `present_private_zip` | `true` | `references/private/urn_cambridge.org_id_binary_20170615115101719-0272_S002210901700028X_S002210901700028Xsup001.zip` | `do_not_redistribute` | Local private supplement ZIP present with SHA-256 recorded in artifacts/evidence/article_manifest.json |
| `french_mkt_rf` | `article_source_located` | `false` | `data/raw/kenneth_french/mkt_rf.csv` | `verify_before_redistribution` | Article identifies Kenneth French online data library for RM and comparator factors; exact archive names still need supplement or source freeze |
| `french_size_bm_25` | `article_source_located` | `false` | `data/raw/kenneth_french/size_bm_25.csv` | `verify_before_redistribution` | Article main decile portfolios are from Lu Zhang; double-sorted size-BM robustness mentioned but supplement details remain missing |
| `french_size_long_term_reversal_25` | `article_source_located` | `false` | `data/raw/kenneth_french/size_long_term_reversal_25.csv` | `verify_before_redistribution` | Article main decile portfolios are from Lu Zhang; double-sorted size-reversal robustness mentioned but supplement details remain missing |
| `federal_funds_rate` | `article_source_located` | `false` | `data/raw/fred/federal_funds_rate.csv` | `verify_before_redistribution` | Article identifies St. Louis Federal Reserve Bank federal funds rate but does not state a FRED series id |
| `treasury_bill_rate` | `article_source_located` | `false` | `data/raw/rates/treasury_bill_rate.csv` | `verify_before_redistribution` | Article identifies St. Louis Federal Reserve Bank 3-month Treasury-bill rate but exact series remains ambiguous |
| `size_asset_growth_25` | `author_source_identified` | `false` | `data/raw/portfolios/size_asset_growth_25.csv` | `do_not_redistribute` | Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required |
| `size_equity_duration_25` | `author_source_identified` | `false` | `data/raw/portfolios/size_equity_duration_25.csv` | `do_not_redistribute` | Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required |
| `size_inventory_growth_25` | `author_source_identified` | `false` | `data/raw/portfolios/size_inventory_growth_25.csv` | `do_not_redistribute` | Main decile portfolios are from Lu Zhang; manual source registration or approved public retrieval still required |
| `high_frequency_monetary_surprises` | `selected_source_pending_file_and_terms` | `false` | `data/raw/monetary_shocks/high_frequency_surprises.csv` | `verify_before_redistribution` | Selected Jarocinski-Karadi updated Fed shocks for decomposition scaffold; acquire data/raw/shocks/jarocinski_karadi_fed_events.csv and verify redistribution terms before generated shock factors |

## Clean-Room Procedure

1. Clone the repository into an empty workspace.
2. Run `poetry install`.
3. Run `make check` to execute source checks, dry-run data acquisition, catalog creation, release audit generation, and tests.
4. Register restricted files with `poetry run srar register-manual-source` only when you have legal access; do not copy those files into Git.
5. Rebuild release assets with `poetry run srar release-audit`.
