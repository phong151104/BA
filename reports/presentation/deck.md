<!-- Generated from src/telco_retention/templates/presentation/deck.md.j2 for run 20261010T131542424757Z-88be4b93. Edit the template, not this file. -->
# Who should get a retention offer?
## Profit-aware churn and retention targeting - Business Analytics capstone, Topic 7

- Decision: which customers receive an offer, with which offer, and how much budget to commit
- Data: IBM Telco Customer Churn sample (7,043 customers)
- Recommendation: expected-value targeting, tested in a randomised pilot

Notes: Open with the decision, not the algorithm. We were asked how to spend a limited retention budget when both churn risk and customer value matter. In twelve minutes: the problem, the data, the model, the decision rule, the money, how robust it is, risks, and what we ask management to approve.

---

# Today's rule wastes part of the budget
## Calling the riskiest customers ignores what they are worth and what the offer costs

- Budget covers an offer for only 10% of customers ($3,500 per 1,409)
- Every offer costs money even if the customer would have stayed
- A very risky customer with a small bill may not repay the offer
- Decision owner: Head of Retention; Finance approves budget; Legal/DPO approves contact

Notes: The status quo is "highest churn risk first". Three things are missing: customer value, the cost of the offer, and whether the offer actually changes behaviour. Our KPIs are expected net value, ROI, customers contacted, precision among contacted, and coverage of high-risk, high-value customers.

---

# The data: clean, but a teaching sample
![](../figures/eda_drivers.png)

- 26.5% churn; month-to-month, new, fibre and e-cheque customers churn most
- No offer or campaign data: save rates must be assumed
- Fictional US company; real US postpaid churn is about 1% a month

Notes: Data readiness verdict: fit to design and demonstrate the method, not to size a real campaign. Cleaning was minor: eleven blank total charges for brand-new customers. Split 60/20/20; every choice made on validation, test touched once.

---

# A calibrated model ranks churners well
![](../figures/calibration.png)

- Logistic regression chosen over random forest and XGBoost by a pre-set rule
- PR-AUC 0.62 vs 0.27 random; ROC-AUC 0.83
- Probabilities off by 2.0% on average (ECE)
- Predicts who leaves, not who an offer keeps

Notes: All three model families rank about equally well, so the simpler and well-calibrated model wins. Calibration matters because we multiply probabilities by money. SHAP on the gradient-boosting challenger agrees on the drivers: tenure, contract, fibre, missing tech support.

---

# Risk and value only partly overlap
![](../figures/risk_value.png)

- Risk-only spends almost the whole budget on high-risk, low-value customers
- The recommended rule reaches all 51 high-risk, high-value customers
- It adds valuable customers at moderate risk

Notes: Value equals monthly charges times a 30% margin times about a year of discounted months, scaled by tenure. The dashed lines are the 75th percentiles, fixed on validation. The coloured points are who the recommended rule contacts.

---

# The decision rule
## Expected value = p(churn) x save rate x value - (offer + contact cost)

- Contact only customers with positive expected value
- Optimiser picks customer and offer within budget, one offer each, max 30% contacted
- Four offers with eligibility rules: credit, contract upgrade, service bundle, loyalty reward
- All costs and save rates are visible, sourced assumptions

Notes: Worked example: a customer paying 70 dollars a month is worth about $239; at 60% risk the standard offer is worth $3.73. Save rates are deliberately below the 30% literature convention because risky customers are not always responsive.

---

# Same budget, more value
| Rule | Customers | Net value | ROI | Precision | HR/HV coverage |
|---|---|---|---|---|---|
| Highest churn risk | 140 | $1,098 | 31% | 70% | 4% |
| Expected value | 140 | $2,130 | 61% | 62% | 96% |
| EV + segment offers | 152 | $2,420 | 69% | 60% | 100% |

- Better targeting: +$1,032; with actual outcomes +$1,308 (95% CI $509 to $2,153)

Notes: Same customers, same budget, same assumptions. Precision is the share of contacted customers who actually churned; HR/HV coverage is the share of high-risk, high-value customers reached. Risk-only has higher precision but lower value. Segment offers add $290 only under assumed save rates; with actual outcomes that extra gain is not distinguishable from zero, so the pilot must test offers.

---

# How much to spend
![](../figures/profit_curve.png)

- Recommended budget: $6.00 per customer in the base (chosen on validation)
- Test: 310 offers (22% of customers), $8,450, net $3,692 (ROI 44%)
- Stop adding budget when the next step earns less than 10%

Notes: The x-axis is the budget as the share of customers the standard offer could reach; the recommended budget equals the standard offer for 24% of customers, about $42,238 for the whole base. Each extra step reaches customers with lower expected value. Beyond 27% of customers contacted nobody has positive expected value, so spending more destroys value.

---

# How robust is it?
![](../figures/tornado.png)

- Break-even save rate 11.8% at the base budget, 13.9% at the recommended budget (assumed 20%)
- Pessimistic $0 (no campaign) / base $2,420 / optimistic $18,525
- Below 8.9% save rate: run no campaign

Notes: The save rate and the value horizon dominate. A re-optimised plan never loses money because it drops customers whose value turns negative; a list frozen under pessimistic assumptions would lose $2,797. This is why we recommend measuring the save rate before scaling.

---

# Fairness and customer experience
![](../figures/fairness.png)

- Seniors contacted 3.7x as often - mostly higher risk, partly higher value
- No protected attribute is a model input; every wave is audited
- Loyal low-risk customers rarely get offers: add a loyalty benefit

Notes: An offer is both a benefit (discount) and a burden (a call). We flag the senior gap for review rather than hide it. Contact cap, one retention contact per 30 days, and the Vietnamese legal call window protect experience.

---

# Risks and limits
- No causal evidence: save rates are assumptions; contact can even raise churn
- Teaching sample: fictional US data, 26.5% churn vs about 1% a month in reality
- Vietnam: about 90% prepaid; rebuild the model on our own data
- Compliance: consent, Do-Not-Call, calls 08:00-17:00, one call per 24 hours, DPIA

Notes: We are explicit about what the analysis cannot claim. The course forbids causal uplift claims from this data, and the literature shows high-risk customers can be the least responsive. That is the reason for the pilot.

---

# The pilot measures what we assumed
- One wave: 1,550 customers, 775 offered, 775 held out at random
- Outcome: churn after 90 days; save rate = 1 - churn(offered) / churn(holdout)
- Detects a save rate of about 12% or more in one wave; break-even is 13.9%
- Offer and contact cost about $21,125

Notes: The wave is the recommended list scaled to the 7,043-customer base (22% of customers). Randomising inside the target list gives the causal effect we could not estimate from the data. Each offer is its own arm. Measured save rates replace assumptions in the configuration and the whole analysis re-runs.

---

# Decisions requested
- Approve one pilot wave: 1,550 customers, half held out, about $21,125
- Name owners: Retention, Call centre, Finance, Legal/DPO
- Agree the rule now: go if the effect is significant and at least 13.9%; else stop or extend
- Live demo: dashboard - KPIs, action list, scenarios

Notes: Close with the ask. If the true save rate is 20%, the rule says go after one wave 94% of the time; the significance test protects against acting on noise, the break-even test protects the budget. Then switch to the dashboard demo: change the save rate and budget, show the KPIs and the action list update, export the campaign file with its scenario ID.
