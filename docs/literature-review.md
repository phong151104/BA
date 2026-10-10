# Literature review: how this project relates to published work

This note explains which published methods the project uses, where its assumptions come from, and which limitations the literature warns about. Full citations are in [references.md](references.md).

## 1. From "who will churn" to "who is worth an offer"

Churn prediction started as a classification problem: rank customers by their probability of leaving and contact the top of the list. Neslin et al. [[neslin2006](references.md#neslin2006)] reported a churn-modelling tournament run on US wireless data. They wrote down the economics of a retention campaign, and that profit equation is still the reference point:

> Profit = N·α·[β·γ·(CLV − c − δ) + β·(1 − γ)·(−c) + (1 − β)·(−c − δ)] − A

Here α is the share of customers targeted, β is the share of targeted customers who would churn, γ is the share of would-be churners kept by the incentive, δ is the incentive cost, c is the contact cost and A is fixed overhead. The equation shows why accuracy alone is not enough. Every contacted non-churner still costs c + δ, and a churner who is "saved" is worth only as much as their remaining value.

Verbeke et al. [[verbeke2012](references.md#verbeke2012)] turned the equation into a model-selection criterion, the *maximum profit* (MP), using eleven telecom data sets. Selecting models by profit gave higher campaign profit than selecting them by AUC or top-decile lift, and the most profitable campaigns contacted only a few percent of customers. Verbraken et al. [[verbraken2013](references.md#verbraken2013)] made the criterion probabilistic: their expected maximum profit (EMPC) treats γ as Beta(6, 14), with mean 0.30. Höppner et al. [[hoppner2020](references.md#hoppner2020)] went further and trained decision trees that maximise EMPC directly.

**What this project takes:**
- The per-customer form of the same economics: EV = p(churn) × save rate × value − (offer cost + contact cost).
- An explicit fixed budget.
- A profit curve over campaign sizes, which mirrors MP's search over α.

**What it deliberately simplifies:**
- **The offer cost is charged to every contacted customer.** Neslin's equation does not charge the incentive to would-be churners who decline it. Our treatment is slightly conservative, and is correct for an unconditional incentive such as a bill credit [[lemmens2020](references.md#lemmens2020)].
- **The model is trained for probability quality** (average precision, then calibration), not for profit. Profit enters at the decision stage, through the expected-value rule and the budget optimiser. This keeps the model reusable when assumptions change, which is the main practical argument of decision-focused designs.

## 2. Risk is not responsiveness

The literature's biggest warning concerns the save rate. Ascarza [[ascarza2018](references.md#ascarza2018)] used randomised field experiments to show that the customers most likely to churn are not necessarily the ones an offer can keep.

- **Prepaid wireless study (N = 12,137):** targeting the 40% of customers most *sensitive* to the offer reduced churn by 6.0 percentage points, against 1.9 points when targeting the 40% at highest *risk*. In the riskiest decile, churn was 95.3% without the offer and 93.7% with it.
- **Membership study:** risk-based targeting *increased* churn.
- **Backfire evidence:** Ascarza, Iyengar & Schleicher [[ascarza2016](references.md#ascarza2016)] found that proactively recommending cheaper plans raised churn from 6% to 10%.
- **Uplift models:** Devriendt et al. [[devriendt2021](references.md#devriendt2021)] and Lemmens & Gupta [[lemmens2020](references.md#lemmens2020)] recommend targeting on predicted uplift or "profit lift" rather than risk.

**Implications for this project:**
1. **The data contain no randomised campaign, so uplift cannot be estimated.** The course brief forbids claiming it. The save rate is therefore a visible assumption, with a range of 10–30% in the tornado chart and 5–40% in the sensitivity grid.
2. **The base save rate of 20% sits below the literature convention of 30%.** The evidence above shows that 30% is not a measured average. Neslin et al. say directly that "no published data are available for acceptance rate", and test 10%, 30% and 50%.
3. **The recommendation is a randomised pilot,** not a rollout ([pilot-design.md](pilot-design.md)). A random holdout within the target list measures the real save rate. Repeated waves would eventually provide the data needed for uplift modelling.

## 3. Valuing a saved customer

Gupta, Lehmann & Stuart [[gupta2004](references.md#gupta2004)] value a customer as discounted future margin. They use a 12% annual discount rate (finance texts suggest 8–16%) and show that customer value moves roughly one-for-one with margin. Fader & Hardie [[faderhardie2014](references.md#faderhardie2014)] point out that a value cut off at a finite horizon should be called *truncated* CLV. Their 2010 paper [[faderhardie2010](references.md#faderhardie2010)] shows that retention rises with tenure because the most loyal customers remain.

The project's value proxy follows this logic:

**value = monthly charges × contribution margin × discounted months**, where months = 12 × tenure factor (0.75 / 1.0 / 1.25).

**Choices behind it:**
- **Truncated horizon.** It is a 12-month truncated value, not a lifetime value, because a saved would-be churner is likely to leave again sooner than an average customer.
- **Tenure factor.** The direction comes from Fader & Hardie; the specific factors are a team assumption, tested in sensitivity.
- **Discount rate of 10%.** US telecom cost of capital is about 5.4% [[damodaran2026wacc](references.md#damodaran2026wacc)], and Vietnam's country risk premium adds about 3.9% [[damodaran2026crp](references.md#damodaran2026crp)]. Gupta et al.'s 12% is used as a cross-check.
- **Contribution margin of 30%.** This is deliberately below US telecom EBITDA margins of 35–42% [[damodaran2026margin](references.md#damodaran2026margin)], [[verizon2026](references.md#verizon2026)], [[att2026](references.md#att2026)]. EBITDA is not contribution margin, but it bounds it from below for an incremental customer.

## 4. Offer and contact costs

Published profit studies use small, fixed costs:
- **Verbeke and Verbraken:** an incentive of EUR 10 and a contact cost of EUR 1 against a CLV of EUR 200.
- **Lemmens & Gupta:** an offer of about EUR 12 per customer; one North European telecom cited about EUR 7.
- **Neslin et al.:** a one-month rebate of $50.
- **Contact channels:** live-agent contacts average US$8.01 [[gartner2019](references.md#gartner2019)]; SMS costs cents [[twilio2026](references.md#twilio2026)].

The project's standard offer is a one-time $20 credit, about 0.3 of an average monthly bill, which falls inside the published range of 0.1 to 0.9 months of fees. The contact cost is $5, a blend of one agent call and an SMS. Both are varied in the tornado chart (offer cost 0.5–1.5×, contact cost $1–10).

## 5. Probabilities, calibration and evaluation

Expected value multiplies a probability by money, so the probability must be honest. Platt scaling [[platt1999](references.md#platt1999)] and the comparison by Niculescu-Mizil & Caruana [[niculescu2005](references.md#niculescu2005)] show that many classifiers distort probabilities and that a post-hoc calibration step fixes most of the distortion. The project therefore:
- **Calibrates every candidate** with a sigmoid fitted on out-of-fold predictions.
- **Reports calibration at three levels** [[vancalster2019](references.md#vancalster2019)]: calibration-in-the-large (intercept, target 0), weak calibration (slope, target 1) and a binned reliability curve with expected calibration error [[guo2017](references.md#guo2017)].
- **Uses average precision (PR-AUC) as the primary ranking metric.** Churners are about 27% of customers, and the precision-recall baseline equals the positive rate [[saito2015](references.md#saito2015)].

## 6. Explanation, documentation and fairness

**Explanation.** SHAP [[lundberg2017](references.md#lundberg2017)] explains the challenger gradient-boosting model, a stretch goal. The deployed model is logistic regression, whose coefficients are explained directly.

**Documentation.** The model card follows Mitchell et al. [[mitchell2019](references.md#mitchell2019)]. The data documentation follows the questions in "datasheets for datasets" [[gebru2021](references.md#gebru2021)].

**Fairness.** The audit compares selection rates between groups (demographic parity, also called independence) [[barocas2023](references.md#barocas2023)]. Ratios outside 0.8–1.25 are flagged for review, borrowing the "four-fifths" screen from US employment-selection guidance [[cfr1607](references.md#cfr1607)]. That screen is an analogy, not a legal standard for marketing.

**Retention offers are a benefit and an intrusion at the same time:**
- **Benefit:** customers who are not contacted pay full price, which regulators call the "loyalty penalty" [[cma2020](references.md#cma2020)].
- **Intrusion:** contacted customers receive calls they may not want.

For this reason the audit also reports a risk-adjusted ratio. A gap explained by churn risk is a design choice; a gap that remains after adjusting for risk needs a policy decision.

## 7. External validity

The IBM Telco sample is a fictional Californian provider [[ibm2019](references.md#ibm2019)]. Its 26.5% churn label is far above real monthly postpaid churn of about 0.9–1.0% at major US carriers in 2025 [[att2026](references.md#att2026)], [[verizon2026](references.md#verizon2026)], [[tmobile2026](references.md#tmobile2026)].

Vietnam's market is about 90% prepaid [[sggp2022](references.md#sggp2022)], and churn there is usually seen as inactivity or number porting, not contract cancellation.

The project therefore treats its numbers as a demonstration of a method on one sample. Its rollout plan starts with retraining on the operator's own data and a randomised pilot.
