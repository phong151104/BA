<!-- Generated from src/telco_retention/templates/docs/data-dictionary.md.j2 for run 20261029T063931261171Z-88be4b93. Edit the template, not this file. -->
# Data dictionary

## Source fields

| Field | Meaning | Allowed values / type | Role |
|---|---|---|---|
| `customerID` | Customer identifier; key only, never a feature | unique, non-empty text | key |
| `gender` | Recorded gender; audit only, not a model input | Male; Female | audit only |
| `SeniorCitizen` | Senior-citizen flag; audit only, not a model input | 0; 1 | audit only |
| `Partner` | Has a partner | Yes; No | feature |
| `Dependents` | Has dependents | Yes; No | feature |
| `tenure` | Months with the company at the snapshot | non-negative number | feature |
| `PhoneService` | Has phone service | Yes; No | feature |
| `MultipleLines` | Has multiple phone lines | Yes; No; No phone service | feature |
| `InternetService` | Internet service type | DSL; Fiber optic; No | feature |
| `OnlineSecurity` | Online security add-on | Yes; No; No internet service | feature |
| `OnlineBackup` | Online backup add-on | Yes; No; No internet service | feature |
| `DeviceProtection` | Device protection add-on | Yes; No; No internet service | feature |
| `TechSupport` | Technical support add-on | Yes; No; No internet service | feature |
| `StreamingTV` | Streaming TV add-on | Yes; No; No internet service | feature |
| `StreamingMovies` | Streaming movies add-on | Yes; No; No internet service | feature |
| `Contract` | Contract term | Month-to-month; One year; Two year | feature |
| `PaperlessBilling` | Paperless billing | Yes; No | feature |
| `PaymentMethod` | Payment method | Electronic check; Mailed check; Bank transfer (automatic); Credit card (automatic) | feature |
| `MonthlyCharges` | Current monthly charge (USD) | non-negative number | feature |
| `TotalCharges` | Total billed to date (USD); history only, not added to future value | non-negative number | not a model input |
| `Churn` | Left within the observation window; target label, never a feature | Yes; No | target |

## Derived fields

| Field | Type / unit | Definition |
|---|---|---|
| `churn` | 0/1 | `Churn` mapped Yes=1, No=0; label only |
| `split` | train / validation / test | Role of the row in validation design |
| Service and account flags | 0/1 | Partner, Dependents, PhoneService, PaperlessBilling, MultipleLines, OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies: 1 if the field is "Yes". "No phone service" and "No internet service" count as 0, so that information is carried only by `PhoneService` and `InternetService` |
| Reference coding | 0/1 columns | `InternetService` against "No"; `Contract` against "Two year"; `PaymentMethod` against "Credit card (automatic)" (the lowest-churn level), so each coefficient compares a level with that reference |
| `tenure_band`, `tenure_segment` | new / developing / loyal | tenure <= 12, 13-24, > 24 months; business segment (tested as a model feature, not selected) |
| `churn_probability` | probability | Calibrated model output |
| `risk_band` | low / medium / high | <= 0.25, 0.25-0.5, > 0.5; descriptive only |
| `prediction_origin` | text | in_sample_do_not_evaluate (train), selection_holdout (validation), untouched_test (test), or upload status |
| `remaining_months` | months | min(cap 24, base horizon 12 x tenure factor) |
| `discounted_months` | months | Present value of `remaining_months` at 10% a year |
| `customer_value` | USD | MonthlyCharges x margin 30% x discounted_months (12-month truncated value proxy, not a validated CLV) |
| `offer_id` | text | Offer chosen (or best potential offer if not contacted); see the [offer catalog](assumption-register.md#offer-catalog) |
| `assumed_save_rate` | share | Assumed probability that the offer keeps a would-be churner |
| `offer_cost`, `contact_cost`, `total_cost` | USD | Cost per contacted customer; total = offer + contact |
| `expected_saved_probability` | probability | churn_probability x assumed_save_rate |
| `expected_retained_value` | USD | expected_saved_probability x customer_value |
| `expected_net_value` | USD | expected_retained_value - total_cost |
| `break_even_save_rate` | share | total_cost / (churn_probability x customer_value); save rate at which the offer pays for itself |
| `break_even_probability` | probability | total_cost / (save rate x customer_value); churn probability above which the offer pays |
| `selected` | bool | Customer is on the contact list |
| `selection_reason`, `decision_detail` | text | Why the customer is in or out, with the EV formula filled in |
| `scenario_id` | text | Hash of value settings, offers, budget, strategy, contact cap and customer list |
| `quadrant` | text | Risk x value segment using validation 75th-percentile cut-offs |

## Context fields from the extended sample (never model inputs)

| Field | Type / unit | Definition |
|---|---|---|
| `churn_reason` | text, churners only | The customer's stated reason for leaving (20 values), recorded after they left |
| `churn_category` | Competitor / Dissatisfaction / Attitude / Price / Other | IBM's grouping of the reasons; Competitor and Price are treated as addressable by a price or contract offer |
| `cltv` | index, 7,043 customers | IBM's predicted lifetime-value index (undocumented formula); cross-check only |

## Rules applied to every input file

- Blank `TotalCharges` with tenure 0 becomes 0; other numeric gaps are filled with training medians.
- Categorical fields must match the allowed values exactly; missing categories are rejected.
- `MultipleLines` is "No phone service" if and only if `PhoneService` is "No"; the six internet add-ons are "No internet service" if and only if `InternetService` is "No".
- A contradiction rejects the whole upload; nothing is partially imported.
- Money is in USD of the sample company (assumed; the source does not state a currency).
