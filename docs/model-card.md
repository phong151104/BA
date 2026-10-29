<!-- Generated from src/telco_retention/templates/docs/model-card.md.j2 for run 20261029T034118630540Z-88be4b93. Edit the template, not this file. -->
# Model and analysis card

Structure follows *Model Cards for Model Reporting* [[mitchell2019](references.md#mitchell2019)].

## 1. Model details

| Item | Value |
|---|---|
| Name / version | Retention Lab churn scorer, run `20261029T034118630540Z-88be4b93` |
| Deployed model | Calibrated Logistic Regression (sigmoid / Platt scaling on out-of-fold predictions) |
| Challengers | Random Forest and XGBoost (gradient boosting), each raw and calibrated; prior-only baseline |
| Decision layer | Expected-value targeting with a fixed budget and offer optimisation (`telco_retention.business`) |
| Owner | Retention analytics team; business owner: Head of Customer Retention |
| Created | 2026-10-29T03:42:47 UTC, Python 3.13.17; code and dependency hashes in the run manifest |

## 2. Intended use

- **Use:** rank customers by churn probability and, combined with documented value and offer assumptions, propose a retention contact list within a budget for a pilot wave.
- **Users:** retention managers and analysts who can read the assumption register and the dashboard.
- **Out of scope:** automatic contact without human review; credit, pricing or service-eligibility decisions; estimating the causal effect of offers; any use on populations other than the one it was trained on without retraining and recalibration.

## 3. Target and data

- **Target:** `Churn` = Yes (26.5% of 7,043 customers), defined by the source as leaving "within the last month" (an extended IBM version says "this quarter"; see [data readiness](data-readiness-review.md)).
- **Data:** IBM Telco Customer Churn sample, fictional US company, single snapshot ([source log](source-log.md)).
- **Split:** stratified random 60/20/20, seed 42 - train 4,225, validation 1,409, test 1,409.

## 4. Features and feature design

- **Continuous (median-imputed, scaled):** tenure, MonthlyCharges.
- **0/1 flags (1 = has it):** Partner, Dependents, PhoneService, PaperlessBilling, MultipleLines, OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies.
- **Categories, coded against their lowest-churn level:** InternetService (reference: No), Contract (reference: Two year), PaymentMethod (reference: Credit card (automatic)).
- **Excluded:** `customerID` and `Churn`; `gender` and `SeniorCitizen` are used only in the fairness audit. All transformations are fitted inside training folds.

**Feature review (week 2).** The first design one-hot coded every level of every field next to derived copies (month-to-month flag, automatic-payment flag, add-on count). Its 48 columns had rank 24, so the logistic coefficients could not be read one by one. Candidate sets were compared with 5-fold cross-validated logistic regression on train only. Rule fixed in advance: Full-rank sets only; cross-validated AP within one standard error of the best full-rank candidate; then the fewest encoded columns.

| Feature set | CV PR-AUC | SE | Columns | Rank | Eligible | Chosen |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| all inputs | 0.664 | 0.014 | 21 | 21 | True | False |
| without TotalCharges | 0.661 | 0.013 | 20 | 20 | True | True |
| without TotalCharges, with tenure band | 0.664 | 0.013 | 22 | 22 | True | False |
| all inputs with tenure band | 0.665 | 0.014 | 23 | 23 | True | False |
| previous design (reference) | 0.665 | 0.013 | 48 | 24 | False | False |

Chosen: **without TotalCharges**. Every candidate ranks churners about equally well, so the simplest full-rank design wins; it also makes each coefficient an odds ratio against a stated reference.

## 5. Validation design

1. 5-fold stratified cross-validation on train tunes each model family, optimising average precision.
2. Each tuned model is calibrated with a sigmoid fitted on out-of-fold predictions.
3. The model is chosen on validation by a rule fixed in advance: AP within 0.01 of best calibrated candidate; Brier within 0.002 of best; prefer simpler.
4. The classification threshold (0.40) maximises F1 on validation and is used only for threshold metrics; targeting uses expected value, not a threshold.
5. Risk/value cut-offs, the offer strategy and the budget recommendation are chosen on validation.
6. Test is scored once, with 1,000-sample bootstrap intervals.

## 6. Performance on the untouched test split

| Metric | Deployed model | 95% bootstrap interval | Reading |
|---|---:|---|---|
| PR-AUC (average precision) | 0.620 | 0.567 - 0.671 | Random contact scores 0.265 [[saito2015](references.md#saito2015)] |
| ROC-AUC | 0.830 | 0.807 - 0.851 | Probability a churner outranks a non-churner |
| Brier score | 0.142 | 0.132 - 0.153 | Prior-only baseline: 0.195 |
| Expected calibration error | 0.019 | 0.017 - 0.046 | Average gap between predicted and observed churn (10 bins) [[guo2017](references.md#guo2017)]. ECE is biased upward in small resamples, so its bootstrap interval sits mostly above the point estimate |
| Calibration slope | 0.94 | 0.83 - 1.06 | Target 1 [[vancalster2019](references.md#vancalster2019)] |
| Calibration intercept | -0.032 | -0.172 - 0.116 | Target 0 |
| Precision / recall at 0.40 | 55.9% / 64.7% | | Threshold metrics, for comparison only |
| Top-decile lift | 2.67x | | Riskiest 10% churn 71% |

All candidates on test (same threshold):

| Model | PR-AUC | ROC-AUC | Brier | ECE | Slope |
| --- | ---: | ---: | ---: | ---: | ---: |
| dummy_raw | 0.265 | 0.500 | 0.195 | 0.022 | n/a |
| logistic_raw | 0.620 | 0.830 | 0.142 | 0.021 | 0.92 |
| logistic_calibrated | 0.620 | 0.830 | 0.142 | 0.019 | 0.94 |
| random_forest_raw | 0.621 | 0.832 | 0.141 | 0.020 | 1.05 |
| random_forest_calibrated | 0.621 | 0.832 | 0.144 | 0.045 | 0.91 |
| xgboost_raw | 0.613 | 0.826 | 0.144 | 0.026 | 0.84 |
| xgboost_calibrated | 0.613 | 0.826 | 0.145 | 0.044 | 0.93 |

The challengers rank about as well as logistic regression, so the selection rule prefers the simpler model.

### Diagnostics and error analysis

- **Validation to test:** PR-AUC 0.672 on validation and 0.620 on test (test 95% interval 0.567-0.671). The validation figure lies outside the test interval; validation also served to choose the model and threshold, so the test figure is the one to quote.
- **By segment** (test, threshold 0.40):

| Segment | Group | Customers | PR-AUC | ROC-AUC | ECE | Slope |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| tenure_segment | developing | 204 | 0.533 | 0.788 | 0.092 | 1.09 |
| tenure_segment | loyal | 774 | 0.435 | 0.821 | 0.025 | 0.90 |
| tenure_segment | new | 431 | 0.717 | 0.757 | 0.048 | 0.93 |
| Contract | Month-to-month | 786 | 0.651 | 0.737 | 0.037 | 0.98 |
| Contract | One year | 284 | 0.343 | 0.746 | 0.029 | 1.05 |
| Contract | Two year | 339 | 0.167 | 0.743 | 0.018 | 1.11 |
| InternetService | DSL | 482 | 0.494 | 0.804 | 0.028 | 0.96 |
| InternetService | Fiber optic | 624 | 0.671 | 0.748 | 0.038 | 0.82 |
| InternetService | No | 303 | 0.221 | 0.822 | 0.028 | 1.29 |
| PaymentMethod | Bank transfer (automatic) | 303 | 0.658 | 0.874 | 0.067 | 1.16 |
| PaymentMethod | Credit card (automatic) | 307 | 0.547 | 0.819 | 0.029 | 0.86 |
| PaymentMethod | Electronic check | 494 | 0.678 | 0.743 | 0.045 | 0.88 |
| PaymentMethod | Mailed check | 305 | 0.462 | 0.826 | 0.051 | 1.14 |
| SeniorCitizen | 0 | 1,170 | 0.605 | 0.838 | 0.019 | 0.97 |
| SeniorCitizen | 1 | 239 | 0.662 | 0.746 | 0.049 | 0.74 |

  Ranking inside a segment is weaker than overall (lowest: Contract = Month-to-month, ROC-AUC 0.737), because contract, tenure and internet type are themselves the strongest signals; much of the model's power comes from telling these segments apart. Calibration is weakest for senior customers (ECE 0.049 vs 0.019, slope 0.74): the model under-predicts their churn on average and its predictions for them are too spread out. Seniors are also the group the targeting contacts most often ([section 8](#8-fairness-and-customer-experience)), so their outcomes should be read separately in the pilot.

- **Who the model gets wrong** at the 0.40 threshold:

| Outcome | Customers | Mean probability | Mean tenure (months) | Median bill | Month-to-month | Fibre |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Flagged and left (true positive) | 242 | 62% | 11.6 | $81 | 99% | 86% |
| Flagged but stayed (false positive) | 191 | 56% | 17.2 | $81 | 99% | 80% |
| Missed and left (false negative) | 132 | 23% | 30.9 | $67 | 64% | 44% |
| Not flagged and stayed (true negative) | 844 | 11% | 42.1 | $56 | 32% | 24% |

  Flagged customers who stayed look like those who left (mean tenure 17 vs 12 months; 99% vs 99% month-to-month): the snapshot cannot separate them. Missed churners have longer tenure (31 months) and only 64% are month-to-month. Targeting does not use this threshold: an offer to a customer who would have stayed costs the offer, a missed churner costs their value, and both enter the expected-value formula through the probability.

- **Model choice checked in money** (profit-based model selection, [verbraken2013](references.md#verbraken2013)): each calibrated candidate picks customers for the same budget and standard offer; "label-based" values the list with the customers' actual churn.

| Population | Model | Contacted | Expected net | Label-based net | Precision |
| --- | --- | ---: | ---: | ---: | ---: |
| validation | logistic | 140 | $2,342 | $2,247 | 64% |
| validation | random_forest | 140 | $2,343 | $2,383 | 69% |
| validation | xgboost | 140 | $2,451 | $2,189 | 66% |
| test | logistic | 140 | $2,340 | $1,977 | 60% |
| test | random_forest | 140 | $2,407 | $1,591 | 61% |
| test | xgboost | 140 | $2,426 | $1,468 | 60% |

  On validation the label-based values are within $194 of each other and the deployed model ranks 2 of 3, so choosing the simpler model costs little in money. Test values are reported, not used for the choice.

## 7. Explanations

- **Deployed model, as odds ratios** (calibration folded in; associations, not causes): the odds of churning are higher for Contract Month-to-month vs Two year (3.66x), InternetService Fiber optic vs No (2.90x), Contract One year vs Two year (1.79x), and lower for PhoneService Yes vs No (0.52x), OnlineSecurity Yes vs No (0.65x), TechSupport Yes vs No (0.65x). The full table and a points version for the call centre are in the [churn scorecard](churn-scorecard.md).
- **Challenger:** TreeSHAP [[lundberg2017](references.md#lundberg2017)] on 200 validation customers for the raw XGBoost model; top features Contract_Month-to-month, tenure, MonthlyCharges, InternetService_Fiber optic. It explains the challenger, not the deployed calibrated model.
- **Customer-level:** each row of the targeting table states the expected-value formula with its numbers and the customer's break-even save rate.

## 8. Fairness and customer experience

The audit compares how often groups are contacted (selection rate) under the recommended rule and under risk-only targeting, with bootstrap intervals and a risk-adjusted ratio ([fairness table](../reports/tables/fairness.csv)).

- **Senior customers** are contacted 3.34x as often as non-seniors (95% interval 2.41-4.43); after adjusting for churn-risk decile the ratio is 1.65x. Seniors are more likely to churn (43% vs 23%) and are worth more on average ($302 vs $224), so expected value favours them. This is flagged for review: the gap is not fully explained by risk.
- **Gender:** ratio 1.15x for women vs men (interval 0.85-1.58), within the review band.
- **Contract and tenure:** one- and two-year contract customers are almost never contacted because their churn risk is low; loyal customers receive fewer offers than new ones. Offers are benefits as well as contacts, so the catalog includes a loyalty reward, which the optimiser does not choose under current assumptions; the playbook adds a non-targeted loyalty benefit and complaint monitoring for a "loyalty penalty" [[cma2020](references.md#cma2020)].
- **Error parity:** recall and calibration by segment are in [segment errors](../reports/tables/segment_errors.csv); groups under 50 customers are marked as small samples.

Policy: protected attributes are never model inputs or eligibility rules; any review flag goes to the Retention owner and the DPO before a wave is launched.

## 9. Assumptions

Save rate, offer and contact cost, margin, value horizon and discount rate are documented in the [assumption register](assumption-register.md) with sources and tested ranges. The value is a 12-month truncated proxy, not a validated lifetime value [[faderhardie2014](references.md#faderhardie2014)].

## 10. Limitations and external validity

- **No causal effect:** the data contain no randomised campaign. Expected values assume a save rate; high-risk customers may not be the most responsive [[ascarza2018](references.md#ascarza2018)] and contact can raise churn [[ascarza2016](references.md#ascarza2016)].
- **Sample data:** fictional US company; the churn label (26.5%) is about 27 times real US monthly postpaid churn of about 1% [[verizon2026](references.md#verizon2026)]. Probabilities would need recalibration on real data; at 15% average churn only 7% of customers would be worth the standard offer ([stress test](../reports/analysis-report.md#outside-the-sample-lower-churn-and-vietnamese-prices)).
- **Single snapshot, random split:** no test of performance over time; tenure and charges are measured at the snapshot.
- **Vietnam:** the market is about 90% prepaid, where churn means inactivity or porting, not contract cancellation [[sggp2022](references.md#sggp2022)]; features such as contract type have no direct equivalent ([deployment note](deployment-vietnam.md)).
- **Value proxy:** no cost-to-serve, no plan-level margin, no re-churn after a save.

## 11. Monitoring and maintenance

See [governance-and-risks.md](governance-and-risks.md): monthly drift (PSI) and calibration (ECE, slope) checks, retraining at least every six months or when a trigger fires, and replacement of assumed save rates with pilot measurements.
