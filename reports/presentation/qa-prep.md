<!-- Generated from src/telco_retention/templates/presentation/qa-prep.md.j2 for run 20261029T034118630540Z-88be4b93. Edit the template, not this file. -->
# Questions to expect, and short answers

**1. Is this causal? Do your offers actually reduce churn?**
No causal claim is made. The data have no randomised campaign, so save rates are documented assumptions (standard offer 20%). We show how the decision changes with them and propose a randomised pilot that measures them. The base-budget list breaks even at a save rate of 11.3%, the larger recommended list at 13.8%.

**2. Why logistic regression and not XGBoost?**
The rule was fixed before looking at test: best average precision within 0.01 and Brier within 0.002, then prefer the simpler model. The three families rank almost equally (PR-AUC 0.620 logistic vs 0.613 XGBoost on test), and in money they are within $194 of each other on validation. Logistic regression can be read as odds ratios and turned into a points card.

**3. Where does the 20% save rate come from?**
Profit-based churn studies use 30% as a convention (Verbeke et al. 2012; Verbraken et al. 2013); Neslin et al. (2006) state that no published acceptance-rate data exist and test 10-50%. Field experiments show risky customers can be unresponsive (Ascarza 2018). We take 20% as a judgement below the convention, not as a safe figure: only 46% of churners in the sample left for price or a competitor's offer, so 20% means keeping 43% of those an offer can reach. We test 10-30% (tornado) and 5-40% (grid), and the pilot measures it.

**4. Precision is lower than risk-only. Isn't that worse?**
Precision measures how many contacted customers would churn, not how much value is saved. Risk-only has 71% precision and an expected $1,301; the recommended rule has 60% precision and an expected $2,668, because it skips risky customers whose value cannot repay the offer.

**5. Isn't the comparison circular - you evaluate expected value with the model that ranks by it?**
Partly, so we also value the lists with actual churn: the recommended rule's gain over risk-only is $1,077 (paired bootstrap 95% interval $229 to $2,002). High-risk/high-value coverage favours expected value almost by construction, so we read it next to the money, not alone. The label check still uses the assumed save rate, which is why the pilot matters.

**6. Did you tune anything on the test set?**
No. Features were chosen by cross-validation on train; model, threshold, risk/value cut-offs, offer strategy and budget recommendation on validation; test was scored once. Validation PR-AUC was 0.672 and test 0.620; we quote test. Reproducibility checks compare two complete runs.

**7. How was the budget chosen?**
The brief asks for a fixed budget; we set it at the cost of the standard offer for 10% of customers ($3,500 for the test sample). For the stretch goal we traced the profit curve and chose, on validation, the largest budget whose last step still returns 10%: about $45,737 for the whole base, which buys 324 offers (23% of customers) on test. The hurdle is a management minimum for marketing spend, on top of the discounting already inside customer value.

**8. What if all the assumptions are wrong at once?**
We drew all of them together 5,000 times. The recommended list loses money in 17% of draws and the base-budget list in 9%; expected-value targeting beats risk-only in 100%. Who to target is robust; how much an offer saves is not.

**9. Is the 26.5% churn rate realistic?**
No. US carriers report about 1% monthly postpaid churn in 2025. At 15% average churn only 7% of customers would be worth the standard offer, so offers and contact must get cheaper; magnitudes must be re-estimated on real data.

**10. Would this work in Vietnam?**
The method transfers; the model does not. About 90% of mobile customers are prepaid, so churn shows as inactivity or porting, bills are far smaller and contact rules are strict. With Vietnamese prices and SMS contact, 18% of customers stay worth an offer at 15% churn. See the deployment note.

**11. Is targeting fair to seniors?**
Seniors are contacted 3.3x as often as others, 1.7x after adjusting for risk, so higher risk explains only part of the gap; higher bills explain more. Age is not a model input, the model is least well calibrated for seniors, and the pilot reports them separately; Legal/DPO reviews each wave.

**12. Why not use uplift modelling?**
It needs randomised treatment data, which this dataset does not have, so claiming uplift would be unsupported. The pilot creates such data; after several waves uplift targeting becomes possible.

**13. Why did you join a second dataset?**
IBM's extended version of the same 7,043 customers records why churners left. Every customer ID and seven shared fields match exactly. Reasons are known only after customers leave, so they never enter the model; they tell us what an offer can and cannot fix.

**14. What happens if assumptions change?**
Change them on the dashboard's Assumptions page or in `configs/default.yaml`; the plan re-optimises, the chance of a loss updates, and `run-all` regenerates every report.
