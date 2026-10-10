<!-- Generated from src/telco_retention/templates/docs/business-case.md.j2 for run 20261010T155849068129Z-88be4b93. Edit the template, not this file. -->
# Business case and problem statement

## The decision

**Who decides:** the Head of Customer Retention (decision owner), with Finance approving the budget.

**The decision:** each campaign wave, *which customers receive a retention offer, which offer they get, and how much budget to commit*.

**Today's rule (baseline):** call the customers with the highest churn risk until the budget runs out.

**Why it matters:** retention budgets are limited, and an offer costs money whether or not it changes the customer's mind. A customer who is very likely to leave but brings little margin may not be worth an offer. A valuable customer at moderate risk may be. The business question is:

> *Given a limited retention budget, which customers should receive an offer when both churn risk and expected economic value are considered?*

## Problem statement

On the IBM Telco sample (7,043 customers of a fictional US telco, 26.5% labelled as churners), churn puts about **$468,468** of twelve-month customer margin at risk (expected value lost with churners, valued with the documented proxy). A base budget of $3,500 per 1,409 customers, set by the team as a starting point, covers the standard offer for 10% of them. The team must:

1. Estimate each customer's churn probability honestly (well calibrated).
2. Turn it into money: expected value = probability x save rate x customer value - offer and contact costs.
3. Choose the list (and offer per customer) that maximises expected net value within the budget and a customer-contact cap.
4. Show how the answer changes when the uncertain assumptions change, and how to measure the true effect.

## Stakeholders

| Stakeholder | Interest | Role in the decision |
|---|---|---|
| Head of Customer Retention | Fewer valuable customers lost per dollar spent | Owner: approves list rule, offers and pilot |
| Finance | Return on retention budget, margin assumptions | Approves budget, validates margin and offer cost |
| Call centre / CRM operations | Feasible daily contact volume, scripts | Executes contacts, reports cost per contact |
| Marketing / Product | Offer design, brand and loyalty perception | Designs offers, owns customer experience |
| Legal / Data Protection Officer | Consent, anti-spam rules, profiling risk | Signs off consent basis, DPIA, contact rules |
| Analytics team | Model quality, monitoring, documentation | Builds and maintains the scoring and decision logic |
| Customers | Fair, relevant and non-intrusive contact | Represented through guardrails and complaint monitoring |

## Options considered

| Option | Rule | Strength | Weakness |
|---|---|---|---|
| A. Do nothing | No campaign | No cost, no contact fatigue | Forgoes all retention value |
| B. Highest churn risk (today) | Rank by churn probability | Simple, highest precision | Ignores value and cost; spends on low-value customers |
| C. Expected value, standard offer | Rank by expected net value | Puts money where value at risk is highest | Depends on save-rate and value assumptions |
| D. Expected value + segment offers | Optimiser picks customer and offer | Matches offers to churn drivers | Adds offer assumptions that must be tested |
| E. Option C or D with a larger budget | Grow budget while marginal ROI > hurdle | Captures more value | More spend at a lower marginal return |

The analysis compares all five on the same customers and budget. On validation data, option D was preferred, and option E sets its size ([analysis report](../reports/analysis-report.md)).

## Success criteria and KPI definitions

| KPI | Definition | Target / reading |
|---|---|---|
| Expected net value | Sum over contacted customers of p x save rate x value - (offer + contact cost) | Higher than risk-only at the same budget |
| ROI | Expected net value / campaign cost | Positive; marginal ROI of the last budget step above 10% |
| Customers contacted | Number of offers within budget and contact cap | Within call-centre capacity |
| Precision among contacted | Share of contacted customers who churn (labels) or mean predicted probability (no labels) | Read with value: high precision on low-value customers is not the goal |
| High-risk/high-value coverage | Share of customers above both 75th percentiles (validation) that are contacted | As close to 100% as the budget allows |
| Model quality | PR-AUC, ROC-AUC, Brier, calibration slope/ECE on untouched test data | PR-AUC well above the 0.27 random baseline; ECE below 0.05 |
| Pilot outcome | Measured save rate = 1 - churn(offered) / churn(holdout) | Effect significant (95% interval above 0) and measured save rate at least the recommended list's break-even, 13.8% ([pilot design](pilot-design.md)) |

## Roadmap

| Phase | Weeks | Owner | Work |
|---|---:|---|---|
| Set-up | 4 | Retention, Legal/DPO, IT | consent and Do-Not-Call checks, data-protection impact assessment, CRM list export, call script and agent training |
| Pilot wave | 13 | Call centre, Retention | contact the offered half once; follow both halves for the 90-day outcome window |
| Read-out | 2 | Retention analytics | save rate with its interval, net value per customer, guardrail metrics; go, extend or stop |
| Scale or stop | 4 | Head of Retention, Finance | retrain and recalibrate on own data, replace assumed save rates, roll out the recommended budget |

A go/extend/stop decision is due about 19 weeks after approval; each extension adds one wave and is allowed at most 2 times.

**One-off effort (team assumption, to be confirmed by the owners):** analytics 4 person-weeks, CRM and IT 2 person-weeks, Legal and DPO 1 person-week, agent training 1 person-week, mostly the data-protection assessment, the CRM list export and agent training. Offer and contact costs of the pilot are in the [pilot design](pilot-design.md#4-cost-value-and-timeline-of-the-pilot).

**If the pilot says stop:** keep today's budget, move it from risk-only to the expected-value list with the cheapest offer the pilot did not rule out, and act on the service reasons customers give for leaving (staff attitude, network and support account for 42% of churners in the sample). The scored list and the dashboard still tell agents who is worth a call.

**Outside this sample:** a Vietnamese operator would rebuild the model on its own prepaid and fibre data and price offers and contact locally ([deployment note](deployment-vietnam.md)).

## Scope and non-goals

- **In scope:** churn probability model, customer value proxy, expected-value targeting with a fixed budget, offer-mix optimisation, sensitivity, fairness and experience review, pilot design, dashboard and executive brief.
- **Out of scope:** causal uplift estimation (no randomised campaign in the data), real customer contact, pricing changes, network or service-quality fixes, and any claim about real profit.
- **Data:** the public IBM Telco sample only; any synthetic element (the offer table) is documented in the [assumption register](assumption-register.md).

## Where each answer lives

- Data readiness: [data-readiness-review.md](data-readiness-review.md)
- Assumptions and sources: [assumption-register.md](assumption-register.md)
- Recommendation for managers: [executive brief](../reports/executive-brief.md)
- How to run the campaign: [retention-playbook.md](retention-playbook.md)
- How to measure it: [pilot-design.md](pilot-design.md)
- Risks and controls: [governance-and-risks.md](governance-and-risks.md)
