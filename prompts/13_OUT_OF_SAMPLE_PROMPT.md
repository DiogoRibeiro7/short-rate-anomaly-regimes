# Out of Sample Falsification Prompt

Complete Milestone 12.

## Design

1. Freeze the initial training endpoint and annual refit schedule before evaluation.
2. At each refit date, estimate factors, betas, and risk prices using available history only.
3. Forecast the next block's cross-sectional mean returns or pricing relation.
4. Store every forecast with model vintage, training dates, factor definition, and asset universe.
5. Never tune the window, factor, or regime after viewing test errors.

## Benchmarks

- CAPM;
- historical mean return by asset;
- zero expected excess return;
- article comparator models that are reproducible on the same universe.

## Metrics

Report cross-sectional RMSE, MAE, maximum error, out-of-sample R-squared, rank correlation, top-minus-bottom rank accuracy, and model confidence sets. Add Diebold-Mariano style comparisons only when the loss series assumptions are justified.

## Negative results

If the two-factor model performs worse out of sample, preserve the result and investigate mechanics without changing the confirmatory specification.
