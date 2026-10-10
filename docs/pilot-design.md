<!-- Generated from src/telco_retention/templates/docs/pilot-design.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
# Pilot design: measuring the real save rate

The data contain no randomised campaign, so the save rate behind every expected value is an assumption (20% for the standard offer). The literature shows why it must be measured, not assumed: risk is not responsiveness [[ascarza2018](references.md#ascarza2018)], and proactive contact can even raise churn [[ascarza2016](references.md#ascarza2016)]. This pilot turns the recommendation into a controlled experiment [[kohavi2020](references.md#kohavi2020)].

## 1. Hypothesis and decision

- **H1:** among customers selected by the recommended rule, receiving the offer lowers 90-day churn compared with not receiving it.
- **Decision metric:** measured save rate q = 1 - churn(offered) / churn(holdout).
- **Go rule:** scale to the recommended budget if the lower 95% bound of q is above the break-even save rate of **11.8%**; extend if the interval straddles it; stop if q is below it or negative.

## 2. Design

| Element | Choice |
|---|---|
| Population | Customers on the recommended list for the wave (positive expected value, within budget and contact cap), after consent and Do-Not-Call suppression |
| Randomisation unit | Customer; random assignment with a fixed seed, stratified by churn-risk decile and assigned offer |
| Arms | Offered (each offer type is its own sub-arm) vs holdout (50%, not contacted) |
| Wave size | 1,690 customers (24% of 7,043): 845 offered, 845 held out |
| Outcome window | 90 days after first contact attempt |
| Primary outcome | Churn (disconnection or port-out) within the window |
| Secondary outcomes | Offer acceptance; net value per customer (realised margin - offer and contact cost); complaints, opt-outs, Do-Not-Call registrations |
| Guardrail metrics | Contacted churn must not exceed holdout churn; complaint and opt-out rates; sample-ratio check between arms |

## 3. Sample size

Two-sided two-proportion test, alpha 0.05, power 80%, equal arms. Expected holdout churn on the list is 59.8% (mean predicted probability; observed 56.8% on the test list).

| True save rate | Churn offered | Customers per arm | Total | Waves of 845 per arm |
|---:|---:|---:|---:|---:|
| 5% | 56.8% | 4,266 | 8,532 | 6 |
| 10% | 53.8% | 1,076 | 2,152 | 2 |
| 15% | 50.8% | 481 | 962 | 1 |
| 20% | 47.8% | 272 | 544 | 1 |
| 30% | 41.9% | 121 | 242 | 1 |

- To detect a save rate equal to the break-even (11.8%) needs about **772 customers per arm**; one wave provides 845.
- With one wave, the smallest detectable save rate is about **11.3%**.
- Detecting the assumed 20% needs 272 per arm.
- Per-offer sub-arms are smaller; offer-level comparisons may need two to three waves, so the first decision is about the list rule as a whole.

## 4. Cost and value of the pilot

Offer and contact cost of the offered arm: about **$23,033** (845 x $27.26 average cost per contact under the recommended mix). The holdout costs nothing directly; its opportunity cost is the expected value not captured from 845 customers, the price of learning the true save rate before committing the full budget.

## 5. Analysis plan

1. Check the sample ratio (offered vs holdout) and balance of risk deciles.
2. Estimate churn by arm and q with a 95% interval (bootstrap or delta method); report by offer and by risk decile.
3. Estimate realised net value per offered customer vs holdout.
4. Update `configs/default.yaml` with measured save rates (by offer) and re-run `python -m telco_retention run-all`; the dashboard and reports then reflect evidence instead of assumptions.
5. After several waves, use the randomised data to fit an uplift model and target by responsiveness rather than risk [[devriendt2021](references.md#devriendt2021), [lemmens2020](references.md#lemmens2020)].

## 6. Ethics and compliance

- Holding out customers from an offer is acceptable because it is a discretionary marketing benefit, not an essential service; the holdout is temporary and random.
- Only consented, non-suppressed customers are eligible; contact windows and frequency follow Decree 91/2020 (calls 08:00-17:00, at most one advertising call per 24 hours) [[decree91](references.md#decree91)].
- The pilot is covered by the data-protection impact assessment for the churn-scoring model [[pdpl2025](references.md#pdpl2025)].
