<!-- Generated from src/telco_retention/templates/presentation/qa-prep.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
# Questions to expect, and short answers

**1. Is this causal? Do your offers actually reduce churn?**
No causal claim is made. The data have no randomised campaign, so save rates are documented assumptions (standard offer 20%). We show how the decision changes with them and propose a randomised pilot that measures them. Break-even is 11.8%.

**2. Why logistic regression and not XGBoost?**
The rule was fixed before looking at test: best average precision within 0.01 and Brier within 0.002, then prefer the simpler model. The three families rank almost equally (PR-AUC 0.619 logistic vs 0.633 XGBoost on test), and logistic regression is better calibrated (ECE 0.020) and easier to explain.

**3. Where does the 20% save rate come from?**
Profit-based churn studies use 30% as a convention (Verbeke et al. 2012; Verbraken et al. 2013); Neslin et al. (2006) state that no published acceptance-rate data exist and test 10-50%. Field experiments show risky customers can be unresponsive (Ascarza 2018). We take a conservative 20% and test 10-30% (tornado) and 5-40% (grid).

**4. Precision is lower than risk-only. Isn't that worse?**
Precision measures how many contacted customers would churn, not how much value is saved. Risk-only has 70% precision but earns $1,098; the recommended rule has 60% precision and earns $2,420, because it skips risky customers whose value cannot repay the offer.

**5. Isn't the comparison circular - you evaluate expected value with the model that ranks by it?**
Partly, so we also evaluate with actual churn labels: the targeting gain over risk-only is $1,308 (paired bootstrap 95% interval $509 to $2,153). The label check still uses the assumed save rate, which is why the pilot matters.

**6. Did you tune anything on the test set?**
No. Model, threshold, risk/value cut-offs, offer strategy and budget recommendation were all chosen on validation; test was scored once. Reproducibility checks compare two complete runs.

**7. How was the budget chosen?**
The course fixes a budget (10% of customers x standard offer). For the stretch goal we traced the profit curve and chose, on validation, the largest budget whose last step still returns 10%: 24% of customers.

**8. Is the 26.5% churn rate realistic?**
No. US carriers report about 1% monthly postpaid churn in 2025. The IBM sample is fictional and describes its churn window inconsistently. Our numbers demonstrate the method; magnitudes must be re-estimated on real data.

**9. Would this work in Vietnam?**
Not as-is: the market is about 90% prepaid, churn shows as inactivity or porting, and contract features do not exist. The method transfers; the model and assumptions must be rebuilt on operator data, under the PDP Law 2025 and Decree 91/2020 contact rules.

**10. Is targeting fair to seniors?**
Seniors are contacted 3.7x as often as others, mostly because they are higher risk and partly because they pay more. Age is not a model input. Offers are a benefit and a contact burden, so we flag the gap for review each wave and cap contact frequency.

**11. Why not use uplift modelling?**
It needs randomised treatment data, which this dataset does not have; the brief forbids claiming uplift. The pilot creates such data; after several waves uplift targeting becomes possible.

**12. What happens if assumptions change?**
Change them in the dashboard or in `configs/default.yaml`; the plan re-optimises, the scenario ID changes, and `run-all` regenerates every report.
