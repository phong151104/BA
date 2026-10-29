<!-- Generated from src/telco_retention/templates/docs/churn-scorecard.md.j2 for run 20261029T073854762519Z-88be4b93. Edit the template, not this file. -->
# Churn scorecard

The "churn scorecard" deliverable has two forms in this project:

1. **Customer scores:** every customer's calibrated churn probability and risk band ([scorecard table](../reports/tables/scorecard.csv)); the targeting tables add value, offer, expected value and the reason for each decision.
2. **Points card (this page):** the deployed model rewritten as whole points, so a call-centre agent or CRM rule can score a customer without the model and see why the score is high.

## How to read it

- Start from **133 points** and add the points for each of the customer's attributes.
- **500 points = 50% churn probability.** Every **40 points doubles the odds** of churning; 40 points fewer halves them.
- Higher means riskier. The points come from the calibrated Logistic Regression (calibration folded in); tenure and monthly charges are banded.
- On the 1,409 test customers the card's probability is within **1.0 percentage points** of the model's on average (largest gap 6.4 points; validation 1.0). It ranks customers as well as the model (ROC-AUC 0.831 vs 0.830).

Points measure churn risk only. Whether to make an offer also depends on the customer's value and the offer's cost; use the targeting list for that.

## Points

| Characteristic | Attribute | Points |
|---|---|---:|
| tenure | 0-3 months | 120 |
| tenure | 4-6 months | 113 |
| tenure | 7-12 months | 106 |
| tenure | 13-18 months | 95 |
| tenure | 19-24 months | 83 |
| tenure | 25-36 months | 69 |
| tenure | 37-48 months | 46 |
| tenure | 49-60 months | 26 |
| tenure | 61+ months | 0 |
| MonthlyCharges | up to $30 | 0 |
| MonthlyCharges | $30-45 | 14 |
| MonthlyCharges | $45-60 | 23 |
| MonthlyCharges | $60-75 | 34 |
| MonthlyCharges | $75-90 | 43 |
| MonthlyCharges | $90-105 | 53 |
| MonthlyCharges | over $105 | 62 |
| Partner | Yes | 1 |
| Partner | No | 0 |
| Dependents | Yes | 0 |
| Dependents | No | 17 |
| PhoneService | Yes | 0 |
| PhoneService | No | 38 |
| PaperlessBilling | Yes | 22 |
| PaperlessBilling | No | 0 |
| MultipleLines | Yes | 15 |
| MultipleLines | No | 0 |
| OnlineSecurity | Yes | 0 |
| OnlineSecurity | No | 25 |
| OnlineBackup | Yes | 0 |
| OnlineBackup | No | 10 |
| DeviceProtection | Yes | 0 |
| DeviceProtection | No | 1 |
| TechSupport | Yes | 0 |
| TechSupport | No | 25 |
| StreamingTV | Yes | 6 |
| StreamingTV | No | 0 |
| StreamingMovies | Yes | 9 |
| StreamingMovies | No | 0 |
| InternetService | DSL | 30 |
| InternetService | Fiber optic | 61 |
| InternetService | No | 0 |
| Contract | Month-to-month | 75 |
| Contract | One year | 34 |
| Contract | Two year | 0 |
| PaymentMethod | Electronic check | 25 |
| PaymentMethod | Mailed check | 8 |
| PaymentMethod | Bank transfer (automatic) | 0 |
| PaymentMethod | Credit card (automatic) | 0 |

## Score bands on test customers

| Points | Customers | Card probability | Model probability | Observed churn |
| --- | ---: | ---: | ---: | ---: |
| up to 380 | 552 | 4.2% | 4.3% | 4.5% |
| 381-420 | 173 | 15.8% | 15.9% | 16.2% |
| 421-460 | 192 | 26.5% | 26.8% | 26.6% |
| 461-500 | 178 | 42.2% | 42.3% | 44.9% |
| 501-540 | 185 | 58.3% | 58.3% | 52.4% |
| 541-580 | 115 | 72.3% | 72.1% | 70.4% |
| over 580 | 14 | 82.1% | 81.7% | 85.7% |

## What drives the points

Odds ratios of the deployed model; each category is compared with its lowest-churn level and each flag with not having the service. These are associations in a snapshot, not causes: a customer who signs a two-year contract does not acquire a two-year customer's risk.

| Field | Comparison | Odds ratio |
| --- | --- | ---: |
| Contract | Month-to-month vs Two year | 3.66 |
| InternetService | Fiber optic vs No | 2.90 |
| Contract | One year vs Two year | 1.79 |
| InternetService | DSL vs No | 1.67 |
| PaymentMethod | Electronic check vs Credit card (automatic) | 1.53 |
| PaperlessBilling | Yes vs No | 1.46 |
| MultipleLines | Yes vs No | 1.29 |
| StreamingMovies | Yes vs No | 1.17 |
| PaymentMethod | Mailed check vs Credit card (automatic) | 1.15 |
| MonthlyCharges | +10 USD a month | 1.13 |
| StreamingTV | Yes vs No | 1.10 |
| Partner | Yes vs No | 1.01 |
| PaymentMethod | Bank transfer (automatic) vs Credit card (automatic) | 1.01 |
| DeviceProtection | Yes vs No | 0.98 |
| OnlineBackup | Yes vs No | 0.84 |
| Dependents | Yes vs No | 0.74 |
| tenure | +12 months | 0.69 |
| TechSupport | Yes vs No | 0.65 |
| OnlineSecurity | Yes vs No | 0.65 |
| PhoneService | Yes vs No | 0.52 |

## Use and limits

- Recompute the card whenever the model is retrained; points from different runs are not comparable.
- Do not add age or gender: they are not model inputs and are audited separately ([model card](model-card.md#8-fairness-and-customer-experience)).
- The points are fitted on the IBM sample; a real operator needs its own card ([data readiness](data-readiness-review.md)).
