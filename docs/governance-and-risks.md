<!-- Generated from src/telco_retention/templates/docs/governance-and-risks.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
# Governance, monitoring and risk register

## 1. Roles (RACI)

| Activity | Retention lead | Analytics | Finance | Call centre | Legal / DPO |
|---|---|---|---|---|---|
| Approve campaign rule, budget and offers | A | R | C | C | C |
| Maintain model, value logic and reports | I | A/R | C | I | I |
| Validate margin, offer and contact cost | C | R | A | C | I |
| Consent basis, DPIA, contact rules | C | C | I | C | A/R |
| Execute contacts and log outcomes | A | I | I | R | I |
| Pilot analysis and go/no-go | A | R | C | I | C |
| Fairness review of each wave | A | R | I | I | C |

R = responsible, A = accountable, C = consulted, I = informed.

## 2. Monitoring

| What | Measure | Frequency | Trigger | Action |
|---|---|---|---|---|
| Input drift | Population stability index (PSI) per feature vs training data | Monthly | PSI > 0.2 on any key feature | Investigate; retrain if confirmed |
| Calibration | ECE and calibration slope on newly labelled customers | Monthly | ECE > 0.05 or slope outside 0.8-1.2 | Recalibrate; review value logic |
| Ranking | PR-AUC vs base churn rate | Quarterly | PR-AUC falls below 2x the churn rate | Retrain and re-select model |
| Campaign | Measured save rate by offer, realised net value | Every wave | Lower bound below break-even (11.8%) | Stop or redesign offers |
| Fairness | Selection-rate ratios with intervals | Every wave | Ratio outside 0.8-1.25 and not explained by risk | Review before launch |
| Experience | Complaints, opt-outs, DNC registrations per 1,000 contacts | Every wave | 2x the normal rate | Pause wave; review script and frequency |
| Reproducibility | Run manifest, code and data hashes, scenario ID on every list | Every run | Mismatch | Block release |

**Retraining:** at least every six months, on any trigger above, or when the pilot provides measured save rates. Every run is versioned in `artifacts/runs/<run_id>` with its configuration, data checksum and code hashes.

## 3. Data protection and contact compliance (Vietnam)

- **Lawful basis and consent:** consent must be specific to the purpose, clear and recorded; silence is not consent ([PDP Law 91/2025/QH15, Art. 9](references.md#pdpl2025)). Advertising requires consent that states content, method and frequency, plus an opt-out (Art. 28).
- **Profiling / AI:** churn scoring is large-scale processing by an AI model; classify its risk (Art. 30) and complete a data-protection impact assessment before deployment.
- **Data-subject requests:** acknowledge withdrawal, objection or restriction requests quickly (Decree 356/2025 sets short response deadlines) and propagate opt-outs to the next list build [[decree356](references.md#decree356)].
- **Anti-spam rules:** prior consent, Do-Not-Call scrub, at most 3 advertising SMS and 1 advertising call per subscriber per 24 hours, SMS 07:00-22:00 and calls 08:00-17:00, registered brand name, logs kept at least one year ([Decree 91/2020](references.md#decree91)); fines of VND 20-30 million per breach ([Decree 14/2022](references.md#decree14)).
- **Data minimisation:** the model uses no protected attributes; customer lists exported from the dashboard contain only what the call centre needs; analysis files stay in the project environment.

## 4. Risk register

| # | Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | True save rate below break-even (11.8%), so the campaign loses money | Medium | High | Randomised pilot with go/no-go rule; budget in tranches | Retention lead |
| R2 | Contact raises churn for some customers (backfire) | Low-medium | High | Holdout comparison by risk decile; stop rule; soft script | Retention lead |
| R3 | Sample data do not represent the operator's customers (churn level, prepaid market) | High | High | Retrain and recalibrate on own data; time-based validation | Analytics |
| R4 | Value proxy wrong (margin, horizon) | Medium | Medium | Finance validation; tornado shows impact; update register | Finance |
| R5 | Model drift after launch | Medium | Medium | Monthly PSI and calibration monitoring; retraining triggers | Analytics |
| R6 | Unequal treatment of groups (seniors over-contacted, loyal customers excluded) | Medium | Medium | Wave-level fairness audit; loyalty benefit; accessible scripts | Retention lead / DPO |
| R7 | Breach of consent or anti-spam rules | Low | High | Consent and DNC suppression built into list export; contact windows enforced by dialer | DPO / Call centre |
| R8 | Call-centre capacity below list size | Medium | Medium | Contact cap; budget tranches; schedule waves | Call centre |
| R9 | Offer gaming (customers threaten to leave to obtain offers) | Medium | Low-medium | One offer per 90 days; offers not advertised publicly | Marketing |
| R10 | Results not reproducible or numbers inconsistent across reports | Low | Medium | Single pipeline, run manifests, scenario IDs, automated release checks | Analytics |
