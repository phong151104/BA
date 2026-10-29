<!-- Generated from src/telco_retention/templates/docs/deployment-vietnam.md.j2 for run 20261029T063931261171Z-88be4b93. Edit the template, not this file. -->
# Deploying the method at a Vietnamese operator

Every number elsewhere in this package belongs to the IBM sample company: a fictional US telco, priced in USD. This note asks what changes if a Vietnamese operator adopts the method. No customer-level churn data from Vietnamese operators are public, so it combines public market facts with a stress test of the sample; it is a planning aid, not a forecast.

## What transfers and what does not

| Element | Transfers? | What changes in Vietnam |
|---|---|---|
| Decision rule (expected value within a budget, profit curve, randomised pilot) | Yes | Nothing: it needs only probabilities, values and costs |
| Churn model | **No, rebuild it** | About 90% of mobile subscriptions are prepaid ([sggp2022](references.md#sggp2022), [vneconomy2018](references.md#vneconomy2018)), so churn means inactivity or porting a number (possible since 2018, [tuoitre2018](references.md#tuoitre2018)), not ending a contract. Inputs should come from top-ups, usage and network quality |
| Customer value | Partly | Bills are far lower: home-fibre entry packages cost 190,000-195,000 VND a month in 2026 ([phongvu2026](references.md#phongvu2026)). A local cost of capital would add Vietnam's country risk premium of about 3.9% ([damodaran2026crp](references.md#damodaran2026crp)) |
| Contact | Partly | A branded SMS costs about 200-500 VND ([sentdm2025](references.md#sentdm2025)). Advertising contact is capped at one call and three SMS per subscriber per day, calls 08:00-17:00 and SMS 07:00-22:00, with a Do-Not-Call list and prior consent ([decree91](references.md#decree91)); breaches are fined ([decree14](references.md#decree14)) |
| Personal data | **New obligations** | Consent per purpose, consent and opt-out for advertising, and a risk assessment of automated processing under the Personal Data Protection Law 2025 ([pdpl2025](references.md#pdpl2025), [decree356](references.md#decree356)) |

## What the stress test shows

The same 1,409 test customers were priced like a Vietnamese home-fibre operator: a 250,000 VND monthly bill ($9.76 at 25,603 VND per USD, the State Bank's central rate, [sbv2026](references.md#sbv2026)), offers costing the same share of the bill as in the sample, and contact by one branded SMS (500 VND). Average churn was then shifted down with the ranking of customers unchanged.

| Average churn | Worth an offer (sample prices) | Worth an offer (Vietnam-like) | Affordable offer for the best 10%, share of a bill (Vietnam-like) | Pilot customers per arm (Vietnam-like) |
|---|---:|---:|---:|---:|
| 27% (sample) | 26% | 33% | 54% | 304 |
| 15% | 7% | 18% | 33% | 525 |
| 10% | 2% | 7% | 23% | 689 |
| 5% | 0% | 0% | 12% | 916 |

- **Money per customer is small, contact is cheap.** With a bill of about $9.76, a saved customer is worth far less than in the sample, but an SMS costs almost nothing, so more customers stay worth an offer as churn falls (18% at 15% churn against 7% with the sample's $5 call).
- **Offers must be cheap to give.** Data bonuses, speed upgrades or bundled services cost the operator little at the margin; a cash credit of a third of a bill is affordable only for the riskiest, most valuable customers once churn is realistic.
- **Pilots must be larger.** Fewer departures mean more customers per arm: 525 at 15% churn, 916 at 5%.
- The value horizon is held fixed; with lower churn saved customers stay longer, so the stress test understates value.

## First steps for a Vietnamese operator

1. **Define churn** per product: prepaid (for example no top-up and no usage for 30 days, or port-out), postpaid and home fibre (disconnection or port-out within 90 days); exclude involuntary suspensions.
2. **Rebuild and calibrate the model** on the operator's own history, with time-based validation (train on earlier months, test on later ones).
3. **Price offers and contact locally:** in-kind offers with near-zero marginal cost, SMS or app messages first, calls only for high-value customers, all within the Decree 91 limits and with recorded consent.
4. **Run the same randomised pilot,** sized from the operator's own churn rate, and replace the assumed save rates with measured ones before scaling.
