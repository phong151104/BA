# Change log

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

## 1.0.0

Initial pipeline, dashboard, notebooks and reports.
