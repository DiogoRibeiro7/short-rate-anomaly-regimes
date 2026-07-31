# Data Flow Diagram Source

This text source is the canonical data-flow figure contract for the manuscript.

```text
Private article and supplement
        |
        v
Table targets and estimator definitions
        |
        v
Source registry and data-access matrix
        |
        +--> Short-rate series --> AR innovation factors
        |
        +--> Market and risk-free series --> excess-return factors
        |
        +--> Anomaly portfolio sources --> aligned portfolio panels
        |
        v
Common monthly asset-date intersections
        |
        +--> Baseline replication tables
        +--> Weak-factor diagnostics
        +--> Temporal and regime extension panels
        +--> High-frequency component aggregation
        |
        v
Audited manuscript tables, figures, and release artifacts
```

The figure intentionally separates source access from generated empirical
artifacts. Public substitutes enter only through documented reconstruction
branches and cannot overwrite the strict replication label.
