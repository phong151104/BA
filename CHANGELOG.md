# Change log

## 2.2.0

**Submission package**
- Final report: a full written report (CRISP-DM structure, Decision-Options-Criteria framing, KPI tree, data quality scorecard, leakage audit, model, decision rule with the optimisation model, results, robustness, fairness, dashboard and pilot, limitations, references, submission checklist, team contributions) rendered from the run's facts as LaTeX and compiled to `reports/final-report.pdf`.
- Presentation rebuilt on the HUST seminar template: 16 slides drawn from the facts, with each speaker's script, speaker and timing in the notes; an 8-minute talk shared by three speakers, followed by a live dashboard demo. A rehearsal copy is written to `reports/presentation/speaker-script.md`. Replaces the generic 14-slide deck and its Markdown outline.
- `export` compiles the report (`--latex auto|require|skip`) and records report pages, slide count, talk length and per-speaker time in the deliverables manifest; the release check verifies them and that the LaTeX source matches a fresh render.

## 2.1.0

**Business answer**
- The executive brief opens with the money at stake and a plain answer to "who": fibre customers on month-to-month contracts with high bills; low-risk and low-bill customers are left out. One gain figure (recommended rule vs risk-only, split into targeting and offer design) is used in every document and on the dashboard.
- New: Vietnam deployment note (what transfers, local prices, prepaid churn, Decree 91/2020, Personal Data Protection Law 2025); roadmap with phases, owners and effort; failure path if the pilot says stop; at most two pilot extensions; pilot value and price of learning.
- Deck rebuilt to 14 slides with an executive summary, action titles, a "who we target" slide, a downside slide, an outside-the-sample slide and a separate demo slide.
- Overclaims removed ("earns", "the method works", "conservative 20%", "never loses money", pessimistic "$0"); fairness stated with the risk-only comparison and the risk-adjusted ratio; loyalty claims shown only when the loyalty offer is used.

**Analysis**
- Feature review on train: the first design one-hot coded every level next to derived copies (48 columns, rank 24); categories are now coded against their lowest-churn level, services are 0/1 flags, and a rule fixed in advance chose the smallest full-rank set within one standard error.
- Odds ratios of the deployed model (calibration folded in) and a points scorecard for the call centre, checked against the model.
- Diagnostics: tenure slice in segment errors, true/false positive and negative profiles, every candidate valued in money at the same budget, validation-to-test gap; all candidates reported at the chosen threshold.
- Second source: IBM's extended sample of the same customers, joined only after every ID and seven shared fields matched; churn reasons and the CLTV index are kept apart from the model data and used to bound what an offer can achieve and to cross-check the value proxy.
- Stress test: probabilities shifted to 15%, 10% and 5% average churn (ranking unchanged) and Vietnamese price levels with SMS contact.
- Monte Carlo of all register assumptions at once (5,000 draws): chance of a loss for frozen lists, drivers, and the value of knowing the assumptions; tenure factors added to the register (A7).
- Discount-rate and hurdle rationales made consistent with a US sample company.

**Dashboard and engineering**
- Dashboard rebuilt as three pages: Decision (KPIs, who gets an offer, action list, export), Assumptions & sensitivity (all inputs, live chance of a loss, scenario analysis, stress test) and Model evidence (metrics, odds ratios, points card, errors, data, upload). Technical IDs moved to an expander.
- Release checks run on macOS and Linux (forward-slash code hashes, line-ending-neutral document comparison, committed PDFs kept and reported when Word is missing); generated files use LF endings.
- The upload template uses new customer IDs; DOCX export keeps list numbering and shows links as text.

## 2.0.0

**Business deliverables**
- Executive brief rewritten decision-first (recommendation, options table, budget size, break-even, risks, decisions requested) and exported to DOCX and PDF (checked at two pages).
- New: business case and problem statement, data readiness review, assumption register with sources, pilot design with sample sizes, governance and risk register, literature review and references, glossary, requirements traceability.
- Retention playbook expanded with budget tranches, offer mix, Vietnamese contact rules, stop/go rules and an operating checklist.
- Slide deck (13 slides with speaker notes, PPTX and PDF), demo script and Q&A preparation.
- All documents, notebooks, figures and the dashboard are in English; money is labelled USD.

**Analysis**
- Assumptions moved to explicit configuration: budget share, default offer by ID, contact cap, value discount rate, sensitivity grids, scenarios, assumption register; research-based values (assumptions v2).
- Value proxy discounted at an annual rate; segment-specific offers through eligibility rules, solved as a knapsack with a contact cap.
- Validation phase now chooses risk/value cut-offs, strategy and budget recommendation; test is used for reporting only.
- New analyses: ECE and calibration slope/intercept, gains and precision@k, threshold vs expected-value rules, risk x value matrix, break-even save rate and offer cost, tornado, pessimistic/base/optimistic scenarios, profit curve with marginal ROI, fairness audit with bootstrap and risk-adjusted ratios, pilot power analysis.
- Scenario IDs are canonical (int and float spellings hash alike), so the dashboard and reports show the same ID.

**Engineering**
- Reports rendered from Jinja2 templates and a single `facts.json`; notebooks generated from templates and executed in place.
- Dashboard redesigned: four pages, five decision KPIs, assumption strip on every page, risk x value segment table, manager-oriented scenario page; challenger SHAP separated from the deployed model.
- Tests extended (calibration statistics, eligibility and cap solver checks, analysis functions, templates, exports, language).
- Release checks derive expected counts from configuration, compare two complete runs, and check documents, notebooks, PDF page count and deck notes; old runs pruned.

**Requirements review fixes**
- Pilot sized from the customers the recommended budget actually contacts (it was sized from the budget share), and judged against the recommended list's own break-even save rate.
- Pilot decision rule (go / extend / stop) aligned with the power calculation; its probabilities of each decision are simulated and reported.
- Budget wording clarified everywhere: budget per customer in the base and share contacted, not "share of customers".
- Readable scenario and tornado assumptions in the analysis report; precision column in the deck's comparison slide; ECE interval note.
- Obsolete figures from pruned runs removed; figure generation and the release check now reject files outside the figure registry.
- README run instructions for macOS and Linux.

## 1.0.0

Initial pipeline, dashboard, notebooks and reports.
