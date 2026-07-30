# Data Policy

This repository is designed to be reproducible without committing restricted data, licensed source extracts, or generated empirical outputs.

## Tracked

- source schemas, manifests, and registry metadata;
- checksums and provenance records that do not reveal restricted content;
- configuration files;
- code, tests, manuscript scaffold, and documentation;
- placeholder files that preserve required output directories.

## Not Tracked

- `.env` files and credentials;
- raw data in `data/raw/`;
- interim data in `data/interim/`;
- processed data in `data/processed/`;
- generated reports in `reports/generated/`;
- build artifacts in `paper/build/`;
- private references in `references/private/`, except the directory README.

## Source Admission Rules

A source can be used in strict replication only after its entry in `research/data_access_matrix.csv` records:

- exact definition verification;
- access status;
- licence check;
- role in strict replication;
- whether a substitute is allowed;
- required replication label for any substitute.

If an original source is unavailable, the repository must use a documented reconstruction label and must not describe the result as reproduced.

## Derived Artifacts

Every derived dataset must have:

- a deterministic construction script or command;
- a schema;
- a checksum;
- a provenance record;
- a transformation log or equivalent audit trail.

Generated artifacts should remain outside version control unless they are small metadata records that can be redistributed under the repository license.
