<!-- Generated from src/telco_retention/templates/docs/assumption-register.md.j2 for run 20261029T034118630540Z-88be4b93. Edit the template, not this file. -->
# Assumption register

Every number below is a visible parameter in `configs/default.yaml` (version `v2`), shown in the dashboard's assumption strip, and varied in the sensitivity analysis. **None of them is estimated from the data**, because the data contain no retention campaign. Sources are listed in [references.md](references.md).

## Core economic assumptions (tornado inputs)

| ID | Assumption | Base | Tested range | Sources | Validated by |
|---|---|---:|---|---|---|
| A1 | Save rate of the standard offer | 20% | 10% to 30% | [verbraken2013](references.md#verbraken2013), [ascarza2016](references.md#ascarza2016), [ascarza2018](references.md#ascarza2018) | Randomised holdout pilot (docs/pilot-design.md) |
| A2 | Offer cost (multiplier on catalog cost) | x1 ($20 standard offer) | x0.5 to x1.5 | [verbraken2013](references.md#verbraken2013), [cma2020](references.md#cma2020) | Finance sign-off of the offer budget |
| A3 | Contact cost per customer (USD) | $5 | $1 to $10 | [gartner2019](references.md#gartner2019), [verbraken2013](references.md#verbraken2013), [twilio2026](references.md#twilio2026) | Call-centre cost per completed contact |
| A4 | Contribution margin | 30% | 20% to 40% | [damodaran2026margin](references.md#damodaran2026margin), [verizon2026](references.md#verizon2026), [att2026](references.md#att2026), [tmobile2026](references.md#tmobile2026) | Finance (product P&L) |
| A5 | Value horizon (months) | 12 months | 6 months to 18 months | [gupta2004](references.md#gupta2004) | Survival of pilot customers after 6 and 12 months |
| A6 | Annual discount rate | 10% | 5% to 15% | [damodaran2026wacc](references.md#damodaran2026wacc), [gupta2004](references.md#gupta2004) | Finance hurdle rate |
| A7 | Tenure effect on remaining months (new 1-s, loyal 1+s) | 25% | 0% to 50% | [faderhardie2010](references.md#faderhardie2010), [faderhardie2014](references.md#faderhardie2014) | Survival of pilot customers by tenure segment |

### Rationale

- **A1. Save rate of the standard offer.** Share of would-be churners kept by the offer. Profit-based churn studies use a mean acceptance of 30%; we take 20% because proactive contact can backfire and high-risk customers are not always responsive.
- **A2. Offer cost (multiplier on catalog cost).** Standard offer is a one-time $20 credit, about 30% of the $64.76 average monthly bill and about 8% of the average customer value; published loyalty discounts run around 10% of the bill per month.
- **A3. Contact cost per customer (USD).** One outbound retention call plus SMS follow-up. Live-agent contacts average US$8.01; profit-metric studies use about 0.5% of customer value; SMS costs cents.
- **A4. Contribution margin.** Share of the monthly bill kept as contribution. US telecom EBITDA margins are 35-42% and gross margins about 60%, so 30% is deliberately conservative.
- **A5. Value horizon (months).** Months of margin a saved customer is expected to stay. One contract year, scaled 0.75/1.0/1.25 by tenure, because a saved would-be churner is likely to churn again sooner than an average customer.
- **A6. Annual discount rate.** US telecom cost of capital is about 5.4%; customer-valuation studies use 8-16% (average 12%) to reflect that future margin from a customer is less certain than a bond. 10% sits inside that range.
- **A7. Tenure effect on remaining months (new 1-s, loyal 1+s).** Retention rises with tenure, so a saved loyal customer is expected to stay longer than a saved new one. The base horizon is scaled by 0.75 for new and 1.25 for loyal customers (s = 25%); 0 means no tenure effect.

**Effect on the decision:** the tornado chart ([analysis report](../reports/analysis-report.md#7-how-robust-is-the-answer)) shows save rate of the standard offer and value horizon (months) move the expected net value most. The break-even save rate is **13.8%** for the recommended list and 11.3% for the smaller base-budget list: below it a frozen list loses money, and below 7.7% no customer is worth contacting. Drawing all assumptions at once from their ranges, the recommended list loses money in 17% of 5,000 draws ([analysis report](../reports/analysis-report.md#7-how-robust-is-the-answer)).

## Offer catalog

Synthetic offer table created by the team, as permitted by the brief. Eligibility rules turn it into segment-specific policies; the optimiser chooses at most one offer per customer.

| Offer | Description | Offer cost | Contact cost | Assumed save rate | Eligible customers |
|---|---|---:|---:|---:|---|
| `standard` | One-time $20 bill credit | $20 | $5 | 20% | All customers |
| `contract_upgrade` | $35 credit for moving to a 1-year contract | $35 | $5 | 30% | Contract: Month-to-month |
| `service_bundle` | 6 months free TechSupport + OnlineSecurity | $12 | $5 | 15% | InternetService: DSL or Fiber optic; TechSupport: No |
| `loyalty_reward` | $10 loyalty reward | $10 | $5 | 10% | tenure_segment: loyal |

- **`standard`**: Simple, unconditional credit any customer can receive. About 30% of the $64.76 average monthly bill, inside the published range of 0.1-0.9 months of fees [lemmens2020, neslin2006].
- **`contract_upgrade`**: Month-to-month customers churn about four times as often as one-year customers in the training data. A larger credit tied to a 12-month commitment is assumed to keep more would-be churners; the observed churn gap is an association, so the save rate stays an assumption to test.
- **`service_bundle`**: Internet customers without TechSupport churn far more often than those with it. A free bundle costs the operator little (marginal cost of the service), with a lower assumed save rate.
- **`loyalty_reward`**: Small recognition for customers with more than 24 months of tenure, so that loyal customers are not systematically excluded from offers (the 'loyalty penalty' concern [cma2020]). Low assumed save rate.

All save rates are assumptions, deliberately at or below the 30% convention of profit-based churn studies [[verbeke2012](references.md#verbeke2012), [verbraken2013](references.md#verbraken2013)], because field experiments show offers can be ineffective or even raise churn for high-risk customers [[ascarza2018](references.md#ascarza2018), [ascarza2016](references.md#ascarza2016)]. Each offer is a separate arm in the pilot.

## Design parameters (policy choices, not estimates)

| Parameter | Value | Why |
|---|---|---|
| Default budget | 10% of customers x standard offer ($3,500 for 1,409 customers) | The business question fixes a budget; the team set it as a share of customers so a manager can scale it with the customer base. It is a starting point, not a recommendation |
| Contact cap | 30% of customers per wave | Customer-experience guardrail against over-contacting |
| Strategy selection | Segment offers only if they beat the single offer by >= 5% on validation | Prefer the simpler policy unless the gain is material |
| Budget recommendation | Largest budget whose last step earns >= 10% marginal ROI, chosen on validation | A management minimum return on marketing spend; time value is already in the discounted customer value, so the hurdle only stops spending where the next dollar barely pays |
| Value horizon cap | 24 months | Upper bound on remaining months whatever the horizon and factors |
| Tenure factors | new 0.75, developing 1.0, loyal 1.25 | Retention rises with tenure [faderhardie2010]; the factors themselves are a team assumption |
| Risk / value cut-offs | 75% percentiles on validation (risk 0.465, value $345) | Defines the high-risk/high-value segment used in coverage |
| Fairness review band | selection-rate ratio outside 0.8-1.25, group >= 50 customers | Four-fifths screen used as an analogy [cfr1607] |
| Pilot | alpha 0.05, power 80%, 50% holdout, 90-day outcome | Standard two-arm test design [kohavi2020] |

## Change control

Change values only in `configs/default.yaml`, then run `python -m telco_retention run-all`. The run manifest stores the full configuration, so every report, figure and dashboard default can be traced to the assumptions it used. Replace assumptions with measured values as soon as the pilot produces them (owner named in the first table).
