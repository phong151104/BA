<!-- Generated from src/telco_retention/templates/docs/retention-playbook.md.j2 for run 20261029T063931261171Z-88be4b93. Edit the template, not this file. -->
# Retention playbook

How to run one retention wave with the recommended rule: who to contact, with which offer, through which channel, at what budget, and how to know whether it worked.

## 1. Objective and rule

**Objective:** maximise expected net retention value from a fixed budget while keeping contact fair, lawful and measurable.

**Rule:** Expected value + segment offers. For every customer and every eligible offer:

> Expected net value (EV) = p(churn) x save rate x customer value - (offer cost + contact cost)
>
> Customer value = monthly charges x margin 30% x discounted months (base 12 months x tenure factor 0.75/1.0/1.25, 10% a year)

The optimiser picks at most one offer per customer to maximise total EV within the budget, never contacts a customer with EV <= 0, and never contacts more than 30% of customers in a wave.

**Worked example:** a month-to-month customer paying $70 a month with 20 months of tenure (factor 1.0) is worth $70 x 30% x 11.40 discounted months = **$239**. With a churn probability of 60% and the standard offer (save rate 20%, cost $25), EV = 0.6 x 0.2 x $239 - $25 = **$3.73**. At this risk level the offer pays only for customers worth more than $208.

## 2. Who to contact (campaign size)

| Plan | Customers contacted (test sample of 1,409) | Budget | Expected net value | ROI |
|---|---:|---:|---:|---:|
| Base budget (standard offer for 10% of customers) | 153 (11%) | $3,500 | $2,668 | 76% |
| **Recommended (standard offer for 26% of customers, validation rule)** | **324 (23%)** | **$9,150** | **$4,145** | **45%** |
| All positive-EV customers | 371 (26%) | $11,318 | see profit curve | lower marginal return |

Scaled to the full base of 7,043 customers (linear, indicative): a full wave is about 1,620 offers, $45,737 budget and $20,721 expected net value. The pilot uses a list of the same size but makes offers to only half of it (810 customers); the other half is the control group.

**Budget tranches.** Release budget in steps and stop when the marginal ROI of the next step falls below 10%. The budget share is the share of customers the standard offer ($25) could reach; the optimiser mixes offers, so the number contacted differs:

| Budget share | Customers contacted | Cumulative cost | Cumulative expected net value | Marginal ROI of the step |
|---:|---:|---:|---:|---:|
| 4% | 71 | $1,400 | $1,417 | 83% |
| 8% | 124 | $2,800 | $2,308 | 59% |
| 12% | 178 | $4,225 | $2,976 | 42% |
| 16% | 226 | $5,625 | $3,457 | 32% |
| 20% | 269 | $7,025 | $3,810 | 23% |
| 24% | 300 | $8,450 | $4,057 | 15% |
| 28% | 340 | $9,849 | $4,210 | 9% |
| 32% | 369 | $11,246 | $4,256 | 2% |

## 3. What to offer

| Offer | Cost + contact | Assumed save rate | Eligible | Recommended wave (test) | Pilot wave, offered half (about) | Base-budget wave (test) |
|---|---:|---:|---|---:|---:|---:|
| One-time $20 bill credit | $25 | 20% | All customers | 24 | 60 | 6 |
| $35 credit for moving to a 1-year contract | $40 | 30% | Contract: Month-to-month | 150 | 375 | 37 |
| 6 months free TechSupport + OnlineSecurity | $17 | 15% | InternetService: DSL or Fiber optic; TechSupport: No | 150 | 375 | 110 |
| $10 loyalty reward | $15 | 10% | tenure_segment: loyal | 0 | 0 | 0 |

The pilot column scales the recommended wave to the pilot's offered half; each offer is its own sub-arm, and the first decision is about the list rule as a whole ([pilot design](pilot-design.md)).

## 4. How and when to contact

The rules below are those a Vietnamese operator would apply; the [deployment note](deployment-vietnam.md) explains the legal and price context. A US operator would apply the equivalent national rules.

1. **Consent and suppression first.** Contact only customers with recorded, purpose-specific consent for marketing; scrub every list against the national Do-Not-Call register and internal opt-outs before each wave ([Decree 91/2020](references.md#decree91), [PDP Law 2025](references.md#pdpl2025)).
2. **Channel:** one outbound call by a trained retention agent, followed by an SMS confirming the offer with a clear opt-out. Calls only **08:00-17:00**, SMS only 08:00-20:00 (stricter than the 07:00-22:00 legal window because aggregators block evening promotions).
3. **Frequency:** at most **one advertising call per customer per 24 hours** by law; internal rule: one retention contact per customer per 30 days, and no new offer within 90 days of a previous one.
4. **Script:** acknowledge the relationship, ask what would make the customer stay, present one offer (the assigned one), no pressure, record acceptance, refusal or "do not contact".
5. **Log the reason and route service problems.** In the sample only 46% of churners left for price or a competitor's offer; 42% left over staff attitude or dissatisfaction with the network, product or support ([analysis report](../reports/analysis-report.md#why-customers-leave)). Agents record the customer's reason with a fixed code list and pass service complaints to the responsible team instead of answering them with a discount.
6. **Brand name** on every SMS; stop immediately on refusal; keep consent and refusal logs for at least one year.

## 5. Measurement

Every wave keeps a **random holdout** inside the target list ([pilot design](pilot-design.md)):
- 50% of eligible customers in the pilot wave are not contacted;
- primary outcome: churn within 90 days, contacted vs holdout;
- measured save rate = 1 - churn(offered) / churn(holdout), for the list and per offer;
- update `configs/default.yaml` with the measured save rates and re-run the plan.

## 6. Stop / go rules

| Signal | Action |
|---|---|
| Measured save rate: 95% interval above 0 and estimate at least 15.6% (break-even of the recommended list) | Go: scale to the recommended budget |
| Estimate at or below 0 (contacted churn >= holdout churn), or whole interval below break-even | Stop; redesign offers and targeting (consider uplift modelling) |
| Anything else | Extend the pilot (another wave, pooled), at most 2 times; then stop |
| Stop decided | Keep the base budget on the expected-value list with the cheapest offer that the pilot did not rule out, or return it to Finance; fix the service reasons customers give for leaving |
| Opt-out or complaint rate > 2x the normal campaign rate | Pause and review script and frequency |
| Fairness review flag on the wave list | DPO and Retention owner review before launch |

## 7. Customer-experience and fairness guardrails

- Protected attributes (gender, age) are never used to choose customers or offers; their selection rates are audited every wave.
- Senior customers are contacted 3.3x as often as others (2.6x under risk-only targeting) and 1.7x after adjusting for churn risk, so higher risk explains only part of the gap; the rest comes from higher bills. Agents follow accessible-communication guidance and use no high-pressure tactics, and the pilot reports seniors separately.
- Low-risk loyal customers rarely qualify for retention offers, and the loyalty reward in the catalog is not chosen by the optimiser under current assumptions. To avoid a perceived "loyalty penalty", pair the campaign with a non-targeted loyalty benefit funded outside the retention budget.
- Customers who decline are suppressed from retention offers for 90 days.

## 8. Operating checklist per wave

1. Score the current customer base with the deployed model (dashboard: *Model evidence -> Data and new customers*, or `python -m telco_retention score`).
2. Confirm assumptions with Finance (margin, offer cost) and Operations (contact cost, capacity) on the *Assumptions & sensitivity* page; check the chance of a loss.
3. Review the list on the *Decision* page and export the campaign ZIP (list + assumptions + scenario ID).
4. Apply consent / DNC suppression; randomise the holdout; freeze and archive the list.
5. Execute contacts within the legal windows; log outcomes daily.
6. After 90 days, measure churn by arm and offer, update the assumption register, decide go / extend / stop.
