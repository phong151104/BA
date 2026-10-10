<!-- Generated from src/telco_retention/templates/docs/retention-playbook.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
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

| Plan | Customers (test sample of 1,409) | Budget | Expected net value | ROI |
|---|---:|---:|---:|---:|
| Base budget (10% of customers) | 152 | $3,499 | $2,420 | 69% |
| **Recommended (24%, validation rule)** | **310** | **$8,450** | **$3,692** | **44%** |
| All positive-EV customers | 383 | $11,378 | see profit curve | lower marginal return |

Scaled to the full base of 7,043 customers (linear, indicative): about 1,550 offers, $42,238 budget and $18,454 expected net value per wave.

**Budget tranches.** Release budget in steps and stop when the marginal ROI of the next step falls below 10%:

| Budget share | Customers | Cumulative cost | Cumulative expected net value | Marginal ROI of the step |
|---:|---:|---:|---:|---:|
| 4% | 71 | $1,400 | $1,283 | 75% |
| 8% | 128 | $2,799 | $2,097 | 54% |
| 12% | 182 | $4,225 | $2,709 | 40% |
| 16% | 235 | $5,625 | $3,155 | 29% |
| 20% | 273 | $7,024 | $3,465 | 21% |
| 24% | 310 | $8,450 | $3,692 | 14% |
| 28% | 349 | $9,849 | $3,813 | 7% |
| 32% | 380 | $11,250 | $3,848 | 1% |

## 3. What to offer

| Offer | Cost + contact | Assumed save rate | Eligible | Contacted in the base wave |
|---|---:|---:|---|---:|
| One-time $20 bill credit | $25 | 20% | All customers | 8 |
| $35 credit for moving to a 1-year contract | $40 | 30% | Contract in ['Month-to-month'] | 37 |
| 6 months free TechSupport + OnlineSecurity | $17 | 15% | InternetService in ['DSL', 'Fiber optic']; TechSupport in ['No'] | 107 |
| $10 loyalty reward | $15 | 10% | tenure_segment in ['loyal'] | 0 |

Offer mix of the base wave by segment:

| Tenure segment | Contract | Offer | Customers |
| --- | --- | --- | ---: |
| new | Month-to-month | contract_upgrade | 5 |
| new | Month-to-month | service_bundle | 45 |
| new | Month-to-month | standard | 2 |
| developing | Month-to-month | contract_upgrade | 10 |
| developing | Month-to-month | service_bundle | 18 |
| loyal | Month-to-month | contract_upgrade | 22 |
| loyal | Month-to-month | service_bundle | 44 |
| loyal | Month-to-month | standard | 6 |

## 4. How and when to contact (Vietnam deployment rules)

1. **Consent and suppression first.** Contact only customers with recorded, purpose-specific consent for marketing; scrub every list against the national Do-Not-Call register and internal opt-outs before each wave ([Decree 91/2020](references.md#decree91), [PDP Law 2025](references.md#pdpl2025)).
2. **Channel:** one outbound call by a trained retention agent, followed by an SMS confirming the offer with a clear opt-out. Calls only **08:00-17:00**, SMS only 08:00-20:00 (stricter than the 07:00-22:00 legal window because aggregators block evening promotions).
3. **Frequency:** at most **one advertising call per customer per 24 hours** by law; internal rule: one retention contact per customer per 30 days, and no new offer within 90 days of a previous one.
4. **Script:** acknowledge the relationship, present one offer (the assigned one), no pressure, record acceptance, refusal or "do not contact".
5. **Brand name** on every SMS; stop immediately on refusal; keep consent and refusal logs for at least one year.

## 5. Measurement

Every wave keeps a **random holdout** inside the target list ([pilot design](pilot-design.md)):
- 50% of eligible customers in the pilot wave are not contacted;
- primary outcome: churn within 90 days, contacted vs holdout;
- measured save rate = 1 - churn(contacted) / churn(holdout), per offer;
- update `configs/default.yaml` with the measured save rates and re-run the plan.

## 6. Stop / go rules

| Signal | Action |
|---|---|
| Measured save rate: lower 95% bound > 11.8% (break-even) | Go: scale to the recommended budget |
| Point estimate above break-even but interval includes it | Extend the pilot (another wave) |
| Point estimate below break-even, or contacted churn > holdout churn | Stop; redesign offers and targeting (consider uplift modelling) |
| Opt-out or complaint rate > 2x the normal campaign rate | Pause and review script and frequency |
| Fairness review flag on the wave list | DPO and Retention owner review before launch |

## 7. Customer-experience and fairness guardrails

- Protected attributes (gender, age) are never used to choose customers or offers; their selection rates are audited every wave.
- Senior customers are currently contacted 3.7x as often as others, driven by higher risk and value; agents follow accessible-communication guidance and no high-pressure tactics.
- Low-risk loyal customers rarely qualify for retention offers; pair the campaign with a non-targeted loyalty benefit to avoid a perceived "loyalty penalty".
- Customers who decline are suppressed from retention offers for 90 days.

## 8. Operating checklist per wave

1. Score the current customer base with the deployed model (dashboard: *Model & data -> Score new customers*, or `python -m telco_retention score`).
2. Confirm assumptions with Finance (margin, offer cost) and Operations (contact cost, capacity).
3. Build the list in *Campaign builder*, review *Scenarios & budget*, export the campaign ZIP (list + assumptions + scenario ID).
4. Apply consent / DNC suppression; randomise the holdout; freeze and archive the list.
5. Execute contacts within the legal windows; log outcomes daily.
6. After 90 days, measure churn by arm and offer, update the assumption register, decide go / extend / stop.
