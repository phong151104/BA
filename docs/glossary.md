# Glossary

Plain-language definitions of the terms used in the brief, the dashboard and the reports, in alphabetical order.

| Term | Meaning in this project |
| --- | --- |
| **Assumption register** | The list of every business assumption (save rate, offer cost, contact cost, margin, value horizon, discount rate), with its value, source, tested range and the person who should validate it. See [assumption-register.md](assumption-register.md). |
| **Average precision (AP, PR-AUC)** | Area under the precision-recall curve. It summarises how well the model puts churners at the top of the list, and it is the main ranking metric because only about 27% of customers churn. A random list scores about 0.27. |
| **Break-even save rate** | The save rate at which a list's expected value exactly pays for its offers and contacts. If the true save rate is lower, the campaign loses money. |
| **Brier score** | Mean squared difference between predicted probability and what happened (0 or 1). Lower is better. It rewards both good ranking and honest probabilities. |
| **Budget share** | Budget expressed as the share of customers that could receive the standard offer. A 10% share for 1,409 customers is 140 offers x $25. |
| **Calibration** | Whether predicted probabilities match observed frequencies: among customers scored 30%, about 30% should churn. Expected value needs calibrated probabilities. |
| **Calibration slope / intercept** | A slope of 1 and an intercept of 0 mean the probabilities are neither too extreme nor shifted. A slope below 1 means overconfident predictions. |
| **Causal uplift** | The change in churn caused by the offer itself. It can only be measured with a randomised experiment, and this dataset has none, so the project assumes a save rate instead of estimating uplift. |
| **Chance of a loss (Monte Carlo)** | Share of random draws, with every register assumption picked at once from its tested range, in which a frozen list's expected net value is below zero. It is about assumptions, not about sampling noise. |
| **Churn** | In this sample, a customer who left within the observation window (the IBM sample describes it as "within the last month"). |
| **Churn reason** | The reason a churner gave for leaving, from IBM's extended version of the same sample, grouped into five categories (competitor, dissatisfaction, attitude, price, other). Known only after a customer left, so it describes and never predicts. |
| **Contact cap** | Customer-experience guardrail: never contact more than 30% of the customers in scope in one wave. |
| **Contribution margin** | Share of a customer's monthly bill that remains after the variable cost of serving them. It turns revenue into value. |
| **Customer value (value proxy)** | Monthly charges x contribution margin x discounted remaining months. It is a planning proxy, not a validated customer lifetime value (CLV). |
| **Discount rate** | Annual rate used to value future months less than today's money. It reflects the cost of capital. |
| **ECE (expected calibration error)** | Average gap between predicted probability and observed churn rate across ten probability bins. 0.02 means predictions are off by about 2 percentage points on average. |
| **EVPI (expected value of perfect information)** | How much more a campaign would earn on average if the true assumptions were known before choosing the list. It bounds what learning (for example a pilot) is worth per wave. |
| **Expected value (EV)** | For one customer: p(churn) x save rate x customer value - (offer cost + contact cost). Positive EV means the offer is expected to pay for itself. |
| **Fixed vs re-optimised list** | Sensitivity can be read two ways. A *fixed* (frozen) list keeps today's customers when an assumption changes, as if the plan were already approved. A *re-optimised* list picks again under the new assumption. |
| **High-risk / high-value coverage** | Share of customers above both the risk and value cut-offs (75th percentiles on validation) that the plan contacts. |
| **Holdout (control group)** | Customers on the target list who are deliberately *not* contacted, chosen at random. Comparing them with contacted customers measures the real save rate. |
| **Lift** | Churn rate in a group divided by the overall churn rate. A top-decile lift of 2.5x means the riskiest 10% churn 2.5 times as often as average. |
| **Marginal ROI** | Extra net value divided by extra cost when the budget grows by one step. The budget stops growing when marginal ROI falls below the 10% hurdle. |
| **Odds ratio** | How much a characteristic multiplies the odds of churning compared with a stated reference, for example month-to-month contracts against two-year contracts. 2 means twice the odds; associations, not causes. |
| **Points scorecard** | The deployed model rewritten as whole points per attribute. 500 points means a 50% churn probability and every 40 points doubles the odds, so an agent can score a customer by hand. |
| **Precision among contacted** | Share of contacted customers who actually churned (with labels), or their average predicted churn probability (without labels). |
| **Prior shift (stress test)** | Moving every predicted probability by one constant on the log-odds scale so the average churn matches a lower rate, keeping the ranking of customers. Used to show how the answer changes at realistic churn levels. |
| **Profit curve** | Expected net value plotted against budget size. It shows where extra spending stops paying off. |
| **ROC-AUC** | Probability that a random churner is scored higher than a random non-churner. 0.5 is random and 1.0 is perfect. |
| **ROI** | Expected net value divided by campaign cost. |
| **Save rate** | Share of would-be churners that the offer keeps. It is the most important assumption and is validated by the pilot. |
| **Scenario ID** | A short code (hash) of all assumptions, the budget and the customer list. The same ID in the dashboard and the reports means the same numbers. |
| **Selection-rate ratio** | How often one group is contacted compared with a reference group. Values outside 0.8–1.25 trigger a review. A *risk-adjusted* ratio compares customers with similar churn risk. |
| **SHAP** | A method that splits one prediction into feature contributions. Here it explains the challenger XGBoost model only. |
| **Test / validation / train split** | The model learns on train (60%). Choices such as the model, thresholds, strategy and budget are made on validation (20%). Results are reported on test (20%), which no choice has seen. |
| **Tornado chart** | One-at-a-time sensitivity: each bar moves one assumption to its low or high value and shows the effect on expected net value. |
