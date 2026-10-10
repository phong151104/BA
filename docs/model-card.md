<!-- Generated from src/telco_retention/templates/docs/model-card.md.j2 for run 20261010T131542424757Z-88be4b93. Edit the template, not this file. -->
# Model and analysis card

Structure follows *Model Cards for Model Reporting* [[mitchell2019](references.md#mitchell2019)].

## 1. Model details

| Item | Value |
|---|---|
| Name / version | Retention Lab churn scorer, run `20261010T131542424757Z-88be4b93` |
| Deployed model | Calibrated Logistic Regression (sigmoid / Platt scaling on out-of-fold predictions) |
| Challengers | Random Forest and XGBoost (gradient boosting), each raw and calibrated; prior-only baseline |
| Decision layer | Expected-value targeting with a fixed budget and offer optimisation (`telco_retention.business`) |
| Owner | Retention analytics team; business owner: Head of Customer Retention |
| Created | 2026-10-10T13:16:04 UTC, Python 3.13.9; code and dependency hashes in the run manifest |

## 2. Intended use

- **Use:** rank customers by churn probability and, combined with documented value and offer assumptions, propose a retention contact list within a budget for a pilot wave.
- **Users:** retention managers and analysts who can read the assumption register and the dashboard.
- **Out of scope:** automatic contact without human review; credit, pricing or service-eligibility decisions; estimating the causal effect of offers; any use on populations other than the one it was trained on without retraining and recalibration.

## 3. Target and data

- **Target:** `Churn` = Yes (26.5% of 7,043 customers), defined by the source as leaving "within the last month" (an extended IBM version says "this quarter"; see [data readiness](data-readiness-review.md)).
- **Data:** IBM Telco Customer Churn sample, fictional US company, single snapshot ([source log](source-log.md)).
- **Split:** stratified random 60/20/20, seed 42 - train 4,225, validation 1,409, test 1,409.

## 4. Features

Partner, Dependents, tenure, PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies, Contract, PaperlessBilling, PaymentMethod, MonthlyCharges, TotalCharges, tenure_band, addon_count, monthly_contract, autopay.

`customerID` and `Churn` are excluded. `gender` and `SeniorCitizen` are excluded from the model and used only in the fairness audit. Numeric fields are median-imputed and scaled; categorical fields are one-hot encoded; all transformations are fitted inside training folds.

## 5. Validation design

1. 5-fold stratified cross-validation on train tunes each model family, optimising average precision.
2. Each tuned model is calibrated with a sigmoid fitted on out-of-fold predictions.
3. The model is chosen on validation by a rule fixed in advance: AP within 0.01 of best calibrated candidate; Brier within 0.002 of best; prefer simpler.
4. The classification threshold (0.35) maximises F1 on validation and is used only for threshold metrics; targeting uses expected value, not a threshold.
5. Risk/value cut-offs, the offer strategy and the budget recommendation are chosen on validation.
6. Test is scored once, with 1,000-sample bootstrap intervals.

## 6. Performance on the untouched test split

| Metric | Deployed model | 95% bootstrap interval | Reading |
|---|---:|---|---|
| PR-AUC (average precision) | 0.619 | 0.568 - 0.669 | Random contact scores 0.265 [[saito2015](references.md#saito2015)] |
| ROC-AUC | 0.831 | 0.808 - 0.852 | Probability a churner outranks a non-churner |
| Brier score | 0.142 | 0.131 - 0.153 | Prior-only baseline: 0.195 |
| Expected calibration error | 0.020 | 0.017 - 0.047 | Average gap between predicted and observed churn (10 bins) [[guo2017](references.md#guo2017)]. ECE is biased upward in small resamples, so its bootstrap interval sits mostly above the point estimate |
| Calibration slope | 0.93 | 0.82 - 1.05 | Target 1 [[vancalster2019](references.md#vancalster2019)] |
| Calibration intercept | -0.022 | -0.164 - 0.127 | Target 0 |
| Precision / recall at 0.35 | 54.4% / 70.9% | | Threshold metrics, for comparison only |
| Top-decile lift | 2.65x | | Riskiest 10% churn 70% |

All candidates on test (same threshold):

| Model | PR-AUC | ROC-AUC | Brier | ECE | Slope |
| --- | ---: | ---: | ---: | ---: | ---: |
| dummy_raw | 0.265 | 0.500 | 0.195 | 0.022 | n/a |
| logistic_raw | 0.619 | 0.831 | 0.142 | 0.020 | 0.93 |
| logistic_calibrated | 0.619 | 0.831 | 0.142 | 0.020 | 0.93 |
| random_forest_raw | 0.629 | 0.831 | 0.141 | 0.017 | 0.99 |
| random_forest_calibrated | 0.629 | 0.831 | 0.143 | 0.035 | 0.92 |
| xgboost_raw | 0.633 | 0.831 | 0.141 | 0.019 | 0.92 |
| xgboost_calibrated | 0.633 | 0.831 | 0.143 | 0.048 | 0.94 |

The challengers rank about as well as logistic regression; the selection rule prefers the simpler, well-calibrated model. Calibration changed the logistic model little; it worsened the tree models' ECE on test, which is reported rather than hidden.

## 7. Explanations

- **Deployed model:** the largest logistic coefficients (associations, not causes) raise risk for tenure_band_new, monthly_contract, InternetService_Fiber optic and lower it for tenure, Contract_Two year, InternetService_DSL.
- **Challenger:** TreeSHAP [[lundberg2017](references.md#lundberg2017)] on 200 validation customers for the raw XGBoost model; top features monthly_contract, tenure, MonthlyCharges, OnlineSecurity_No. It explains the challenger, not the deployed calibrated model.
- **Customer-level:** each row of the targeting table states the expected-value formula with its numbers and the customer's break-even save rate.

## 8. Fairness and customer experience

The audit compares how often groups are contacted (selection rate) under the recommended rule and under risk-only targeting, with bootstrap intervals and a risk-adjusted ratio ([fairness table](../reports/tables/fairness.csv)).

- **Senior customers** are contacted 3.66x as often as non-seniors (95% interval 2.73-4.89); after adjusting for churn-risk decile the ratio is 1.74x. Seniors are more likely to churn (43% vs 23%) and are worth more on average ($302 vs $224), so expected value favours them. This is flagged for review: the gap is not fully explained by risk.
- **Gender:** ratio 1.14x for women vs men (interval 0.83-1.55), within the review band.
- **Contract and tenure:** one- and two-year contract customers are almost never contacted because their churn risk is low; loyal customers receive fewer offers than new ones. Offers are benefits as well as contacts, so the team added a loyalty reward to the catalog and recommends monitoring complaints about a "loyalty penalty" [[cma2020](references.md#cma2020)].
- **Error parity:** recall and calibration by segment are in [segment errors](../reports/tables/segment_errors.csv); groups under 50 customers are marked as small samples.

Policy: protected attributes are never model inputs or eligibility rules; any review flag goes to the Retention owner and the DPO before a wave is launched.

## 9. Assumptions

Save rate, offer and contact cost, margin, value horizon and discount rate are documented in the [assumption register](assumption-register.md) with sources and tested ranges. The value is a 12-month truncated proxy, not a validated lifetime value [[faderhardie2014](references.md#faderhardie2014)].

## 10. Limitations and external validity

- **No causal effect:** the data contain no randomised campaign. Expected values assume a save rate; high-risk customers may not be the most responsive [[ascarza2018](references.md#ascarza2018)] and contact can raise churn [[ascarza2016](references.md#ascarza2016)].
- **Sample data:** fictional US company; the churn label (26.5%) is about 27 times real US monthly postpaid churn of about 1% [[verizon2026](references.md#verizon2026)]. Probabilities would need recalibration on real data.
- **Single snapshot, random split:** no test of performance over time; tenure and charges are measured at the snapshot.
- **Vietnam:** the market is about 90% prepaid, where churn means inactivity or porting, not contract cancellation [[sggp2022](references.md#sggp2022)]; features such as contract type have no direct equivalent.
- **Value proxy:** no cost-to-serve, no plan-level margin, no re-churn after a save.

## 11. Monitoring and maintenance

See [governance-and-risks.md](governance-and-risks.md): monthly drift (PSI) and calibration (ECE, slope) checks, retraining at least every six months or when a trigger fires, and replacement of assumed save rates with pilot measurements.
