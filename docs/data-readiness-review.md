<!-- Generated from src/telco_retention/templates/docs/data-readiness-review.md.j2 for run 20261029T063931261171Z-88be4b93. Edit the template, not this file. -->
# Data readiness review

**Question:** is the IBM Telco sample fit to support the retention-targeting decision?
**Verdict:** **fit for designing and demonstrating the method; not fit, on its own, for sizing a real campaign.** It is complete and clean, but it is a fictional single-snapshot sample with a churn label that does not match a real monthly churn rate, and it contains no campaign or offer-response data.

## 1. Source and provenance

| Item | Finding |
|---|---|
| Source | IBM Telco Customer Churn sample, downloaded from Kaggle blastchar/telco-customer-churn ([dataset page](https://www.kaggle.com/datasets/blastchar/telco-customer-churn)); IBM describes it as a fictional telco serving 7,043 customers in California ([IBM, 2019](references.md#ibm2019)) |
| Downloaded | 2026-10-03T11:36:37 UTC; SHA-256 `88be4b93fbe0cc83421af1c503794c97c342eca914c1576db7c276e61d61358a` |
| Size | 7,043 customers x 21 columns, one row per customer |
| Licence | Kaggle shows "Data files © Original Authors"; the raw file is kept for reproducibility of coursework only |
| Joins | IBM extended sample joined one-to-one on customerID (7,043 of 7,043 matched; 7 shared fields agree for every customer); only churn reasons and the CLTV index are kept, in a separate file used for description, never as model inputs ([source log](source-log.md#second-source-churn-reasons-joined-for-description-only)) |

## 2. Completeness and validity

| Check | Result |
|---|---|
| Duplicate rows removed | 0 |
| Unique customer IDs | 7,043 of 7,043 |
| Blank `TotalCharges` | 11 rows, all with tenure 0 (new customers) and filled with 0 |
| Other missing values after cleaning | 0 |
| Domain checks | Every categorical field matches its documented values; numbers finite and non-negative; tenure integer |
| Consistency checks | "No phone service" / "No internet service" appear if and only if the parent service is absent |
| Label balance | 1,869 churners (26.5%) vs 5,174 non-churners |

All checks are automated (`telco_retention.data.validate`) and the same checks reject invalid uploaded CSVs in the dashboard.

## 3. Fitness for the decision

| Need | Available? | Consequence |
|---|---|---|
| Churn label | Yes, but its window is ambiguous: "within the last month" (Kaggle, IBM base sample) vs "this quarter" (IBM extended sample) | Treat probabilities as relative risk within this sample; recalibrate on own data |
| Predictors observed before churn | Partly: tenure, contract and charges are a single snapshot; `TotalCharges` is almost exactly tenure x charges and was dropped in the feature review | Random split only; no time-based validation possible; no leakage of the label itself |
| Customer value inputs | Monthly charges and tenure; no cost-to-serve or margin. IBM's CLTV index ranks customers differently (Spearman 0.18 with our proxy; it follows tenure, 0.37, more than the bill, 0.11) | Value is a documented proxy using an assumed margin; the value definition is a real source of uncertainty, tested through margin, horizon and tenure factors |
| Reasons for leaving | Yes, from the extended sample, for all 1,869 churners, recorded after they left | Descriptive only: 46% left for price or a competitor's offer, which an offer can address; 42% for staff attitude or dissatisfaction |
| Offer cost and response | **No** | Synthetic offer table with assumed save rates; causal effect must be measured in a pilot |
| Representativeness | Fictional, US, home phone + internet, 26.5% churn (real US postpaid churn is about 1% per month) | Results illustrate the method; magnitudes do not transfer |
| Protected attributes | `gender`, `SeniorCitizen` available | Excluded from the model; used only for the fairness audit |

## 4. Split and leakage controls

Stratified random split, seed 42: train 4,225, validation 1,409, test 1,409. All preprocessing (imputation, scaling, encoding) is fitted inside cross-validation on train; the model, thresholds, strategy and budget are chosen on validation; test is used only for reporting.

## 5. Actions before real deployment

1. Rebuild the label from the operator's own data with an explicit window (for example, disconnection or port-out within 90 days), and remove involuntary suspensions.
2. Use time-based validation: train on earlier months, test on later ones.
3. Add cost-to-serve and margin per plan from Finance.
4. Record every offer and contact so that the pilot produces the response data this sample lacks.
