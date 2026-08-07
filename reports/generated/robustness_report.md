# Robustness Report

Verdict: `unsupported`

Verdict source: `asset_sets.all_seven_families_joint.h1_primary_classification` in `artifacts/diagnostics/h1_materiality.json`
Hypothesis: `H1`
Replication status: `documented_reconstruction`
Primary comparator: `capm`, selected after observing RMSE: `false`

Decision rule: H1 is supported against the primary comparator only if all three primary gates hold jointly on the identical asset-date intersection.

Multiplicity: The registered secondary comparator family uses Holm adjustment for secondary p-values. The materiality gates executed here are deterministic threshold comparisons on point estimates, so no p-value is generated in this pass and Holm adjustment therefore does not yet apply. No p-value is invented to fill the slot.

## H1 Primary Gates On The Headline Asset Set `all_seven_families_joint`

Treatment model `market_plus_fedfunds_innovation`, comparator `capm`, `70` assets, `504` months, `2` of `3` gates passed, classification `unsupported`

| Gate | Comparison | Threshold | Comparator | Treatment | Observed | Passed |
|---|---|---|---|---|---|---|
| mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.146575 | 0.0816409 | 0.443008 | true |
| max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.475246 | 0.238831 | 0.236415 | false |
| rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.100393 | 0.469737 | true |

Treatment model `market_plus_tbill_innovation`, comparator `capm`, `70` assets, `504` months, `2` of `3` gates passed, classification `unsupported`

| Gate | Comparison | Threshold | Comparator | Treatment | Observed | Passed |
|---|---|---|---|---|---|---|
| mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.146575 | 0.0858156 | 0.414526 | true |
| max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.475246 | 0.278117 | 0.19713 | false |
| rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.108418 | 0.427352 | true |

## H1 Classification By Asset Set

| Asset Set | Treatment Model | Primary Comparator | Primary Classification | Secondary Comparator | Secondary Classification |
|---|---|---|---|---|---|
| all_seven_families_joint | market_plus_fedfunds_innovation | capm | unsupported | carhart_4 | unsupported |
| all_seven_families_joint | market_plus_tbill_innovation | capm | unsupported | carhart_4 | unsupported |
| book_to_market | market_plus_fedfunds_innovation | capm | unsupported | fama_french_5 | unsupported |
| book_to_market | market_plus_tbill_innovation | capm | unsupported | fama_french_5 | unsupported |
| earnings_to_price | market_plus_fedfunds_innovation | capm | unsupported | fama_french_5 | unsupported |
| earnings_to_price | market_plus_tbill_innovation | capm | unsupported | fama_french_5 | unsupported |
| equity_duration | market_plus_fedfunds_innovation | capm | supported | fama_french_5 | unsupported |
| equity_duration | market_plus_tbill_innovation | capm | supported | fama_french_5 | unsupported |
| inventory_growth | market_plus_fedfunds_innovation | capm | unsupported | fama_french_5 | unsupported |
| inventory_growth | market_plus_tbill_innovation | capm | unsupported | fama_french_5 | unsupported |
| investment_to_assets | market_plus_fedfunds_innovation | capm | supported | liquidity | unsupported |
| investment_to_assets | market_plus_tbill_innovation | capm | supported | liquidity | unsupported |
| long_term_reversal | market_plus_fedfunds_innovation | capm | unsupported | carhart_4 | unsupported |
| long_term_reversal | market_plus_tbill_innovation | capm | unsupported | carhart_4 | unsupported |
| ppe_investment | market_plus_fedfunds_innovation | capm | unsupported | liquidity | unsupported |
| ppe_investment | market_plus_tbill_innovation | capm | unsupported | liquidity | unsupported |

## H1 Gate Values By Asset Set And Comparison

Every classification in the table above is derived from the gate values below; no asset set is classified from evidence that is not displayed.

| Asset Set | Treatment Model | Comparison Role | Comparator Model | Gate | Comparison | Threshold | Comparator Value | Treatment Value | Observed | Passed |
|---|---|---|---|---|---|---|---|---|---|---|
| all_seven_families_joint | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.146575 | 0.0816409 | 0.443008 | true |
| all_seven_families_joint | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.475246 | 0.238831 | 0.236415 | false |
| all_seven_families_joint | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.100393 | 0.469737 | true |
| all_seven_families_joint | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.146575 | 0.0858156 | 0.414526 | true |
| all_seven_families_joint | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.475246 | 0.278117 | 0.19713 | false |
| all_seven_families_joint | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.189327 | 0.108418 | 0.427352 | true |
| all_seven_families_joint | market_plus_fedfunds_innovation | secondary_adversarial | carhart_4 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0559756 | 0.0816409 | -0.458509 | false |
| all_seven_families_joint | market_plus_fedfunds_innovation | secondary_adversarial | carhart_4 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.242704 | 0.238831 | 0.00387202 | false |
| all_seven_families_joint | market_plus_fedfunds_innovation | secondary_adversarial | carhart_4 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0720363 | 0.100393 | -0.393646 | false |
| all_seven_families_joint | market_plus_tbill_innovation | secondary_adversarial | carhart_4 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0559756 | 0.0858156 | -0.533089 | false |
| all_seven_families_joint | market_plus_tbill_innovation | secondary_adversarial | carhart_4 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.242704 | 0.278117 | -0.035413 | false |
| all_seven_families_joint | market_plus_tbill_innovation | secondary_adversarial | carhart_4 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0720363 | 0.108418 | -0.505043 | false |
| book_to_market | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.153845 | 0.0776153 | 0.495496 | true |
| book_to_market | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.375112 | 0.162337 | 0.212775 | false |
| book_to_market | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.193039 | 0.087972 | 0.54428 | true |
| book_to_market | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.153845 | 0.0579849 | 0.623094 | true |
| book_to_market | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.375112 | 0.163371 | 0.211741 | false |
| book_to_market | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.193039 | 0.0797232 | 0.587011 | true |
| book_to_market | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0244315 | 0.0776153 | -2.17686 | false |
| book_to_market | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0417272 | 0.162337 | -0.12061 | false |
| book_to_market | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0282052 | 0.087972 | -2.119 | false |
| book_to_market | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0244315 | 0.0579849 | -1.37337 | false |
| book_to_market | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0417272 | 0.163371 | -0.121644 | false |
| book_to_market | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0282052 | 0.0797232 | -1.82655 | false |
| earnings_to_price | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.183188 | 0.0981973 | 0.463953 | true |
| earnings_to_price | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.41178 | 0.168147 | 0.243633 | false |
| earnings_to_price | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.213086 | 0.110043 | 0.483575 | true |
| earnings_to_price | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.183188 | 0.105526 | 0.423948 | true |
| earnings_to_price | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.41178 | 0.271341 | 0.140439 | false |
| earnings_to_price | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.213086 | 0.131667 | 0.382092 | true |
| earnings_to_price | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0191365 | 0.0981973 | -4.13142 | false |
| earnings_to_price | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0589309 | 0.168147 | -0.109216 | false |
| earnings_to_price | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0273215 | 0.110043 | -3.0277 | false |
| earnings_to_price | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0191365 | 0.105526 | -4.51437 | false |
| earnings_to_price | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0589309 | 0.271341 | -0.21241 | false |
| earnings_to_price | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0273215 | 0.131667 | -3.81918 | false |
| equity_duration | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.179337 | 0.0839755 | 0.531743 | true |
| equity_duration | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.515002 | 0.151638 | 0.363364 | true |
| equity_duration | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.228682 | 0.0961507 | 0.579544 | true |
| equity_duration | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.179337 | 0.0752392 | 0.580458 | true |
| equity_duration | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.515002 | 0.187029 | 0.327973 | true |
| equity_duration | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.228682 | 0.0946587 | 0.586068 | true |
| equity_duration | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0248696 | 0.0839755 | -2.37663 | false |
| equity_duration | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.078347 | 0.151638 | -0.0732909 | false |
| equity_duration | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.033818 | 0.0961507 | -1.84318 | false |
| equity_duration | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0248696 | 0.0752392 | -2.02535 | false |
| equity_duration | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.078347 | 0.187029 | -0.108682 | false |
| equity_duration | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.033818 | 0.0946587 | -1.79906 | false |
| inventory_growth | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.109746 | 0.0707197 | 0.355606 | true |
| inventory_growth | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.287735 | 0.190195 | 0.0975397 | false |
| inventory_growth | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.131985 | 0.0949075 | 0.280921 | true |
| inventory_growth | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.109746 | 0.0754501 | 0.312503 | true |
| inventory_growth | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.287735 | 0.210754 | 0.076981 | false |
| inventory_growth | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.131985 | 0.0973444 | 0.262457 | true |
| inventory_growth | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0379528 | 0.0707197 | -0.863361 | false |
| inventory_growth | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0804733 | 0.190195 | -0.109722 | false |
| inventory_growth | market_plus_fedfunds_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0476195 | 0.0949075 | -0.99304 | false |
| inventory_growth | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0379528 | 0.0754501 | -0.988 | false |
| inventory_growth | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0804733 | 0.210754 | -0.130281 | false |
| inventory_growth | market_plus_tbill_innovation | secondary_adversarial | fama_french_5 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0476195 | 0.0973444 | -1.04421 | false |
| investment_to_assets | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.138733 | 0.0578945 | 0.582692 | true |
| investment_to_assets | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.421425 | 0.113035 | 0.308389 | true |
| investment_to_assets | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.177716 | 0.0674916 | 0.620227 | true |
| investment_to_assets | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.138733 | 0.0679412 | 0.510275 | true |
| investment_to_assets | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.421425 | 0.141188 | 0.280237 | true |
| investment_to_assets | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.177716 | 0.07891 | 0.555976 | true |
| investment_to_assets | market_plus_fedfunds_innovation | secondary_adversarial | liquidity | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0408626 | 0.0578945 | -0.416811 | false |
| investment_to_assets | market_plus_fedfunds_innovation | secondary_adversarial | liquidity | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.132579 | 0.113035 | 0.0195435 | false |
| investment_to_assets | market_plus_fedfunds_innovation | secondary_adversarial | liquidity | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0563985 | 0.0674916 | -0.196692 | false |
| investment_to_assets | market_plus_tbill_innovation | secondary_adversarial | liquidity | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0408626 | 0.0679412 | -0.662677 | false |
| investment_to_assets | market_plus_tbill_innovation | secondary_adversarial | liquidity | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.132579 | 0.141188 | -0.00860941 | false |
| investment_to_assets | market_plus_tbill_innovation | secondary_adversarial | liquidity | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0563985 | 0.07891 | -0.39915 | false |
| long_term_reversal | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.126264 | 0.0912611 | 0.277218 | true |
| long_term_reversal | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.325087 | 0.18424 | 0.140847 | false |
| long_term_reversal | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.154327 | 0.0993372 | 0.356318 | true |
| long_term_reversal | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.126264 | 0.0846413 | 0.329646 | true |
| long_term_reversal | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.325087 | 0.171359 | 0.153728 | false |
| long_term_reversal | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.154327 | 0.0987073 | 0.3604 | true |
| long_term_reversal | market_plus_fedfunds_innovation | secondary_adversarial | carhart_4 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.036563 | 0.0912611 | -1.49599 | false |
| long_term_reversal | market_plus_fedfunds_innovation | secondary_adversarial | carhart_4 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0828647 | 0.18424 | -0.101376 | false |
| long_term_reversal | market_plus_fedfunds_innovation | secondary_adversarial | carhart_4 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0424742 | 0.0993372 | -1.33877 | false |
| long_term_reversal | market_plus_tbill_innovation | secondary_adversarial | carhart_4 | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.036563 | 0.0846413 | -1.31494 | false |
| long_term_reversal | market_plus_tbill_innovation | secondary_adversarial | carhart_4 | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.0828647 | 0.171359 | -0.0884948 | false |
| long_term_reversal | market_plus_tbill_innovation | secondary_adversarial | carhart_4 | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0424742 | 0.0987073 | -1.32394 | false |
| ppe_investment | market_plus_fedfunds_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.129246 | 0.075906 | 0.412703 | true |
| ppe_investment | market_plus_fedfunds_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.320397 | 0.157915 | 0.162482 | false |
| ppe_investment | market_plus_fedfunds_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.163619 | 0.0913362 | 0.441774 | true |
| ppe_investment | market_plus_tbill_innovation | primary | capm | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.129246 | 0.0944886 | 0.268926 | true |
| ppe_investment | market_plus_tbill_innovation | primary | capm | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.320397 | 0.17908 | 0.141317 | false |
| ppe_investment | market_plus_tbill_innovation | primary | capm | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.163619 | 0.106795 | 0.347295 | true |
| ppe_investment | market_plus_fedfunds_innovation | secondary_adversarial | liquidity | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0585636 | 0.075906 | -0.296131 | false |
| ppe_investment | market_plus_fedfunds_innovation | secondary_adversarial | liquidity | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.122492 | 0.157915 | -0.0354229 | false |
| ppe_investment | market_plus_fedfunds_innovation | secondary_adversarial | liquidity | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0718909 | 0.0913362 | -0.270484 | false |
| ppe_investment | market_plus_tbill_innovation | secondary_adversarial | liquidity | mae_relative_reduction | relative_reduction_at_least | 0.1 | 0.0585636 | 0.0944886 | -0.613437 | false |
| ppe_investment | market_plus_tbill_innovation | secondary_adversarial | liquidity | max_absolute_error_reduction | absolute_reduction_at_least | 0.25 | 0.122492 | 0.17908 | -0.0565886 | false |
| ppe_investment | market_plus_tbill_innovation | secondary_adversarial | liquidity | rmse_relative_reduction | relative_reduction_at_least | 0.1 | 0.0718909 | 0.106795 | -0.48551 | false |

## Weak-Factor Gate Outcomes

| Hypothesis | Outcome | Gate Failures |
|---|---|---|
| H4a | true | none |
| H4b | true | none |
| H4c | h4c_passed_interval_excludes_at_least_one_economic_direction | none |

### H4a Identification Strength

- Confirmatory system: `all_seven_families_joint`, rank `2` of `2` priced factors, condition number `4.15902`
- Standardized rate-exposure dispersion share: `0.253972` against a floor of `0.1`
- Spanning R squared: `0.0559645` against a ceiling of `0.9`; residual ratio `0.971615` against a floor of `0.316228`
- Spanning regressors: `Mkt-RF`, `SMB`, `HML`, `UMD`, `RMW`, `CMA`, `LIQ`, `ME`, `IA`, `ROE`, over `504` months

### H4b Influence Stability

- Maximum absolute standardized DFBETA: `0.0896452` at `inventory_growth__decile_05`, against a bound of `1`
- Assets reaching the bound: `0` of `70`
- Leave-one-family refits pass: `true` across `7` refits
- Baseline rate risk price: `-0.698465`, Shanken standard error `0.244258`, t `-2.85954`

### H4c Fitted-Premium Precision

- Estimand: `rate_attributable_fitted_premium_spread_decile_10_minus_decile_01`
- Economic direction bound: `0.25`, `10000` draws, block length `6` selected by `politis_white`

The registered H4c gate is evaluated on the 95 percent bootstrap interval, so the interval displayed here is the one the gate reads.

| Family | Point Estimate | Lower 95 | Upper 95 | Spans Both Directions | Gate |
|---|---|---|---|---|---|
| book_to_market | 0.535266 | 0.0222764 | 0.832065 | false | pass |
| earnings_to_price | 0.407112 | -0.00644138 | 0.695257 | false | pass |
| equity_duration | -0.461739 | -0.726505 | 0.00630204 | false | pass |
| long_term_reversal | -0.299183 | -0.707933 | 0.158802 | false | pass |
| investment_to_assets | -0.328348 | -0.53424 | -0.0238567 | false | pass |
| ppe_investment | -0.298081 | -0.482857 | 0.00123755 | false | pass |
| inventory_growth | -0.190763 | -0.452421 | 0.0931099 | false | pass |

All registered gates are reported above, whether they passed or failed; significant-only robustness reporting is prohibited.

## Artifacts Read

- `artifacts/diagnostics/h1_materiality.json`
- `artifacts/diagnostics/weak_factor/h4a_identification_strength.json`
- `artifacts/diagnostics/weak_factor/h4b_influence_stability.json`
- `artifacts/diagnostics/weak_factor/h4c_fitted_premium_precision.json`
