<!-- Generated from src/telco_retention/templates/reports/executive-brief.md.j2 for run 20261010T155849068129Z-88be4b93. Edit the template, not this file. -->
# Executive brief: profit-aware retention targeting

**To:** Head of Customer Retention | **From:** Retention analytics team | **Decision requested:** approve a 90-day retention pilot

**The issue.** Churn puts about **$468,468** of 12-month customer margin at risk across the 7,043 customers of the sample company (IBM's fictional US telco; USD). Today's rule spends the budget on the customers most likely to leave, ignoring what they are worth and what an offer costs.

## Recommendation

1. **Target by expected value, not by risk alone.** Make an offer only where churn risk x customer value x the offer's *save rate* (the share of would-be leavers it keeps) exceeds its cost. Here that means **fibre customers on month-to-month contracts with high bills**: 100% of the recommended list have fibre and 97% a monthly contract, with a median bill of $89 against $70 overall. Low-risk and low-bill customers are left out.
2. **Match the offer to the segment:** $35 credit for moving to a 1-year contract (150), 6 months free TechSupport + OnlineSecurity (150), One-time $20 bill credit (24).
3. **Test before scaling:** one randomised pilot wave of 1,620 customers, half held out, and scale up only if the measured save rate clears that list's **13.8% break-even**.

## Why: the same budget returns more

1,409 test customers (held out from every choice), fixed $3,500 budget:

| Option | Customers contacted | Expected net value | ROI | Precision among contacted | High-risk/high-value coverage |
|---|---:|---:|---:|---:|---:|
| Do nothing | 0 | $0 | n/a | n/a | 0% |
| Call highest churn risk (today) | 140 | $1,301 | 37% | 71% | 12% |
| Call highest value | 140 | -$1,037 | -30% | 29% | 30% |
| Expected value, one standard offer | 140 | $2,340 | 67% | 60% | 96% |
| **Expected value + segment offers (recommended)** | **153** | **$2,668** | **76%** | **60%** | **98%** |

- **The recommended rule is expected to add $1,368 for the same spend**: $1,039 from choosing customers by expected value and $328 from matching offers. Valued with actual churn (at the assumed save rates), the gain is $1,077 (95% interval $229 to $2,002); the part from matching offers is not proven.
- Risk-only is more precise but spends on risky customers whose value cannot repay an offer. Calling the most valuable customers loses money: risk and value are needed together.

## How much to spend

Each extra budget step returns less (figure). Keeping only steps that still return at least 10% (decided on validation data) gives about **$45,737 for the whole base** ($6.49 per customer). On the test customers this buys 324 offers for $9,150: expected net value $4,145, ROI 45%. Beyond 26% of customers nobody has positive expected value.

![Profit curve](figures/profit_curve.png)

## How sure are we?

- **Who to target is robust.** The model ranks churners well (ROC-AUC 0.83) and its probabilities are within 1.9 points of observed churn. With all assumptions drawn at once, expected-value targeting beats risk-only in 100% of draws.
- **How much an offer saves is not.** Lists break even at a save rate of 11.3% (base budget) and 13.8% (recommended); we assume 20%. Only 46% of churners left for price or a competitor's offer, so 20% means keeping 43% of those an offer can reach.
- **Downside:** the recommended list loses money in 17% of draws, and in the worst 5% it loses more than $12,217 across the base; the smaller base-budget list loses in 9%.

## Risks and guardrails

- **No causal evidence yet.** Save rates are assumptions and contact can even raise churn, so the pilot keeps a random control group.
- **Sample data.** Real operators lose far fewer customers than this sample's 27%. At 15% average churn only 7% of customers would be worth this offer, so offers and contact must get cheaper (for example SMS); retrain on our own data ([Vietnam deployment note](../docs/deployment-vietnam.md)).
- **Fairness.** Seniors are contacted 3.3x as often as others (2.6x under today's rule), 1.7x after adjusting for risk. Age and gender are not model inputs; Legal/DPO reviews each wave.
- **Compliance.** Consent, Do-Not-Call checks, contact limits and a data-protection impact assessment.

## Decisions requested

1. **Approve one pilot wave:** 810 customers offered, 810 held out; offer and contact cost about $22,875, expected net value of the offered half $10,363, worst case (no one saved) -$22,875.
2. **Name owners:** Retention (offers), Call centre (capacity), Finance (margin, offer cost), Legal/DPO (consent, DPIA).
3. **Agree the rule now:** after 90 days, **go** if the effect is statistically significant and at least 13.8%; **stop** if clearly below; otherwise extend, at most 2 more waves. At a true save rate of 20% the rule says go 95% of the time. Decision about 19 weeks after approval.
