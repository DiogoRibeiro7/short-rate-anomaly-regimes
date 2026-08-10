# Data Acquisition Guide

This repository does not redistribute copyrighted articles, publisher supplements, licensed raw data, author-supplied files, or prompt files.

## Public Processed Data Redistribution

No public processed data file is currently redistributed beyond tracked placeholders. Before adding processed data, record source licence and redistribution rights in `research/data_access_matrix.csv`.

## Source Instructions

| Source | Access | Exact Definition | Acquisition Path | Redistribution | Notes |
|---|---|---|---|---|---|
| `article_pdf` | `present_private_file` | `true` | `references/private/maio2017.pdf` | `do_not_redistribute` | Local private article PDF present at references/private/maio2017.pdf with SHA-256 recorded in artifacts/evidence/article_manifest.json |
| `article_supplement` | `present_private_zip` | `true` | `references/private/urn_cambridge.org_id_binary_20170615115101719-0272_S002210901700028X_S002210901700028Xsup001.zip` | `do_not_redistribute` | Local private supplement ZIP present with SHA-256 recorded in artifacts/evidence/article_manifest.json |
| `french_mkt_rf` | `acquired_at_two_vintages_exact_file_not_named_by_the_article` | `false` | `data/raw/kenneth_french/mkt_rf.csv` | `verify_before_redistribution` | Publication-era vintage obtained from the Internet Archive snapshot of 2017-07-09; both vintages frozen with checksums in artifacts/provenance/kenneth_french and compared in reports/french_vintage_difference_report.md |
| `french_rf` | `acquired_at_two_vintages_closest_to_an_exact_input` | `false` | `manual_registration` | `verify_before_redistribution` | The RF column of the same archive; the article names the one-month Treasury-bill return from this library and it maps to a single public column. Revised in only 2 of 504 baseline months |
| `french_momentum` | `acquired_at_two_vintages` | `false` | `manual_registration` | `verify_before_redistribution` | Carhart comparator factor; revised in 487 of 504 baseline months with a maximum revision of 1.78 |
| `french_five_factor` | `acquired_at_two_vintages` | `false` | `manual_registration` | `verify_before_redistribution` | Fama-French five-factor comparator; RMW and CMA revised in more than 96 percent of baseline months |
| `federal_funds_rate` | `acquired_documented_reconstruction_series_frozen` | `false` | `data/raw/fred/federal_funds_rate.csv` | `verify_before_redistribution` | FRED FEDFUNDS frozen with raw and normalized checksums; monthly aggregation verified as the calendar-day mean of DFF rounded half-up to two decimals in 864 of 864 complete months |
| `treasury_bill_rate` | `acquired_documented_reconstruction_series_frozen` | `false` | `data/raw/rates/treasury_bill_rate.csv` | `verify_before_redistribution` | FRED TB3MS frozen with raw and normalized checksums; monthly aggregation verified as the mean of available business-day DTB3 observations rounded half-up to two decimals in 869 of 869 complete months |
| `treasury_bill_rate_daily` | `acquired_sensitivity_only` | `false` | `manual_registration` | `verify_before_redistribution` | FRED DTB3; no daily source or aggregation rule appears in the article or supplement so it can never carry an exact-replication label |
| `federal_funds_rate_daily` | `acquired_audit_input_only` | `false` | `manual_registration` | `verify_before_redistribution` | FRED DFF acquired solely to verify the FEDFUNDS monthly aggregation; it enters no replication or extension estimate |
| `anomaly_deciles_seven_families` | `acquired_from_the_named_original_source_at_a_post_publication_vintage` | `false` | `manual_registration` | `verify_before_redistribution` | All seven families obtained from global-q.org which is the article's named Lu Zhang source; no publication-era vintage is recoverable because the earliest Internet Archive snapshot of the testing-portfolio page is 2019-11-24 |
| `anomaly_deciles_equal_weighted` | `not_located` | `false` | `manual_registration` | `verify_before_redistribution` | Every archive member exposes only a ret_vw column. Article Table 7 cannot be attempted and no substitute is used |
| `anomaly_deciles_cfp_and_ig` | `acquired_from_the_named_original_source_at_a_post_publication_vintage` | `false` | `manual_registration` | `verify_before_redistribution` | Supplement Table A.4 families; the equal-weighted variants that table also requires are unavailable |
| `size_double_sorted_25` | `named_source_located_not_acquired` | `false` | `manual_registration` | `verify_before_redistribution` | SBM25 SIA25 and SREV25 are attributed to Kenneth French's website without a file name; the archive must be matched by definition rather than by name before acquisition |
| `stambaugh_liquidity` | `acquired_at_two_vintages_column_and_scale_identified_empirically` | `false` | `manual_registration` | `verify_before_redistribution` | Footnote 18 resolves; the earlier dead-URL record was a PDF text-extraction artifact. LIQ is identified as the traded liquidity factor times 100 from the published mean standard deviation and autocorrelation; the published minimum and maximum are not reproduced by any recoverable vintage and are recorded as an open incompatibility |
| `hou_xue_zhang_factors` | `acquired_from_the_named_original_source_at_a_post_publication_vintage` | `false` | `manual_registration` | `verify_before_redistribution` | R_ME R_IA and R_ROE from the q5 monthly file; no publication-era vintage exists because global-q.org was a parked domain in June 2017 which is consistent with the article stating that these factors were provided by Lu Zhang directly |
| `high_frequency_monetary_surprises` | `selected_source_pending_file_and_terms` | `false` | `data/raw/monetary_shocks/high_frequency_surprises.csv` | `verify_before_redistribution` | Selected Jarocinski-Karadi updated Fed shocks for the decomposition scaffold; acquire data/raw/shocks/jarocinski_karadi_fed_events.csv and verify redistribution terms before generated shock factors |
| `crsp_compustat` | `not_confirmed_and_not_assumed` | `false` | `manual_registration` | `verify_before_redistribution` | No licensed database access is assumed and no security-level portfolio construction was attempted |

## Frozen-Vintage Verification

None of the URLs above is a vintage. FRED's `fredgraph.csv?id=<series>` endpoint returns the latest revision of the series, and the Kenneth French, global-q, and Wharton files are replaced in place whenever those libraries are rebuilt. The checksums recorded in the shipped manifests under `artifacts/provenance` are therefore treated as **expected** hashes, not as a description of whatever arrived.

Each acquisition script downloads the file, computes its SHA-256, and compares it with the recorded value. Only on a match does it normalise the payload and let the rebuild continue. On a mismatch it aborts, naming the series, the expected hash, the received hash, and the two ways forward; it writes no file and rewrites no manifest. When the immutable raw file is already present and already matches, the provider is not contacted at all.

| Acquisition | Verifies | Expected hash read from |
|---|---|---|
| `scripts/acquire_short_rates.py` | FEDFUNDS, TB3MS, DFF, DTB3 raw CSV bytes | `artifacts/provenance/short_rate/<SERIES>_<vintage>.json` |
| `scripts/acquire_french_factors.py` | both vintages of each three-factor, momentum, and five-factor ZIP | `artifacts/provenance/kenneth_french/<dataset>_<vintage>.json` |
| `scripts/acquire_anomaly_portfolios.py` | the `vvg_monthly` and `inv_monthly` testing-portfolio ZIPs | `artifacts/provenance/portfolios/<archive>_<vintage>.json` |
| `scripts/acquire_comparator_factors.py` | the q-factor CSV and both Pastor-Stambaugh liquidity files | `artifacts/provenance/comparators/<dataset>_<vintage>.json` |
| `srar acquire-data --live` | every registry-driven public source | `artifacts/provenance/<source_id>.json` |

### Preferred immutable sources

Where a provider offers an addressable vintage, it is the better place to obtain the frozen bytes, and the place to look first when verification fails because the current file has been revised. The frozen vintage recorded in this archive is **not** switched to these endpoints here: which vintage the results rest on is a data decision, made and reported deliberately, not a side effect of changing an acquisition URL.

- **FRED short rates.** ALFRED serves archival vintages of the same series (`alfredgraph.csv?id=<series>&vintage_date=<YYYY-MM-DD>`), and the FRED API exposes `vintage_dates`. A vintage-dated request is reproducible in a way that `fredgraph.csv` is not.
- **Kenneth French publication-era archives.** Internet Archive snapshots (`https://web.archive.org/web/<timestamp>id_/<original URL>`) are content-addressed by capture time and are already the source of the `publication_era_20170709` vintage. The current-vintage archives have no immutable counterpart.
- **Pastor-Stambaugh liquidity.** The publication-era file is likewise taken from an Internet Archive snapshot; the current file is served from a live Wharton path that is extended in place.
- **global-q testing portfolios and q-factors.** No immutable endpoint is published, and the earliest usable snapshot post-dates the article, so the recorded checksum is the only vintage pin available for these files.

### Changing the frozen vintage

`make update-vintage` and its per-source targets (`update-vintage-short-rates`, `update-vintage-french`, `update-vintage-portfolios`, `update-vintage-comparators`) pass `--update-vintage`. That flag is the only way to overwrite a recorded expected hash, and no `make reproduce` stage passes it. Running one of these targets replaces the raw bytes and the provenance manifests, which changes the inputs of every downstream estimate: re-run `make reproduce` in full afterwards and report the new vintage. A verification failure is not a reason to run it.

## Clean-Room Procedure

1. Clone the repository into an empty workspace.
2. Run `poetry install`.
3. Run `make check` to execute source checks, dry-run data acquisition, catalog creation, release audit generation, and tests. This stage needs no network access and no rebuilt data.
4. Run `make reproduce` to rebuild the empirical artifacts from the frozen public sources listed above. The acquisition stage needs network access unless the frozen raw bytes are already under `data/raw`, and it verifies every download against the recorded hash before anything downstream runs; the bootstrap and simulation stages take hours. Individual stages are available as `make reproduce-acquire`, `reproduce-panels`, `reproduce-estimates`, `reproduce-extension`, `reproduce-regimes`, and `reproduce-reports`.
5. Register restricted files with `poetry run srar register-manual-source` only when you have legal access; do not copy those files into Git.
6. Rebuild release assets with `poetry run srar release-audit`.
