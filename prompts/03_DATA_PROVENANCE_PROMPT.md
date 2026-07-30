# Data Provenance Prompt

Complete Milestone 2. Do not estimate asset-pricing models.

## Public downloaders

Implement resilient, source-specific clients for the exact FRED and Kenneth French inputs frozen in Milestone 0.

Each client must

- use explicit timeouts and bounded retries;
- validate status code, content type, archive structure, and nonempty payload;
- save the exact downloaded bytes once under `data/raw`;
- refuse to overwrite an existing raw file unless the checksum is identical;
- write source URL, retrieval UTC, provider metadata, licence note, ETag or last-modified value when available, and SHA-256;
- parse into a separate interim file;
- never modify the raw file.

## Manual and restricted ingestion

Implement a command that registers a manually supplied author or licensed file. It must verify expected columns, sample coverage, file checksum, and redistribution status. It must never copy restricted files into release artefacts.

## Data catalogue

Create DuckDB tables for sources, raw files, transformations, schemas, validation results, and run artefacts. Add migrations or idempotent creation scripts.

## Validation

Check date uniqueness, month continuity, units, missingness, numeric bounds, portfolio count, factor names, and sample endpoints. Fail loudly on percent-versus-decimal ambiguity.

## Tests

Use local HTTP fixtures or mocked responses. Do not require internet access in unit tests. Add an opt-in integration marker for live public sources.

## Deliverable

Implement `srar acquire-data`, `srar register-manual-source`, `srar validate-data`, and `srar build-catalog`.
