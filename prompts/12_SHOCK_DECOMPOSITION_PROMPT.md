# Shock Decomposition Prompt

Complete Milestone 11.

## Dataset selection

Review candidate high-frequency monetary surprise datasets. Select one based on documentation, event coverage, reproducibility, redistribution terms, and compatibility with the post-1990 sample. Record rejected candidates and reasons.

## Reproduction before use

Reproduce the selected source study's summary statistics and core decomposition. Freeze event windows, rate instruments, equity response, rotations or sign restrictions, normalization, treatment of ambiguous events, and aggregation.

## Monthly factors

- preserve event-level policy and information components;
- aggregate to months using only contemporaneous events;
- represent months without meetings explicitly rather than forward filling;
- test alternative aggregation rules as secondary specifications;
- document whether multiple meetings occur in a month.

## Asset pricing

Estimate models with

1. aggregate AR short-rate innovation;
2. high-frequency total rate surprise;
3. policy component;
4. information component;
5. both components jointly.

Run spanning tests, compare beta patterns, risk prices, pricing errors, weak-factor diagnostics, and regime interactions.

## Language rule

Only the identified high-frequency component may be called a policy shock. The AR residual remains a rate innovation.
