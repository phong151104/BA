# Course requirements (Business Analytics capstone, Topic 7)

This is a transcription of the course brief (`class_materials/BA_Instruction_1-3.jpg`), kept so that every requirement can be traced. [requirements-traceability.md](requirements-traceability.md) maps each item to the evidence in this repository.

## Format and expectations

Each team completes one capstone project using a clean and reproducible analytics pipeline. The project must begin with a business decision, not with a preferred algorithm. The final recommendation must be traceable from data, assumptions, analysis and validation.

### Required project package

- Reproducible code/notebook(s) with a README and clear run instructions.
- Data dictionary and source log: source URL, download date, filters, joins and major cleaning decisions.
- Executive brief (maximum 2 pages) written for a manager or decision-maker.
- Small interactive dashboard focused on 3–5 decision-relevant KPIs and one actionable view.
- Model/analysis card summarising target, features, validation design, assumptions, risks, ethics/bias considerations and limitations.

### Suggested 6-week work plan

| Week | Primary focus | Expected checkpoint |
| --- | --- | --- |
| 1 | Business framing, data acquisition, data dictionary, initial EDA | Problem statement + data readiness review |
| 2 | Cleaning, feature design, validation plan, baseline model/analysis | Reproducible baseline |
| 3 | Advanced model/analysis and error analysis | Model comparison + diagnostics |
| 4 | Decision rules, scenario simulation, business impact analysis | Actionable decision logic |
| 5 | Robustness/sensitivity checks, dashboard, executive interpretation | Draft dashboard + recommendations |
| 6 | Final QA, reproducibility check, executive brief, presentation/demo preparation | Final submission package |

## Topic 7: Profit-aware telecom churn and retention targeting

**Business question.** Given a limited retention budget, which customers should receive an offer when both churn risk and expected economic value are considered?

**Primary dataset.**
- IBM Telco Customer Churn sample dataset, commonly distributed through Kaggle. It represents a fictional telco and is suited to teaching churn analytics.
- The team may create a transparent synthetic offer-cost/retention-response table for business simulation; the assumptions must be documented.

**Core tasks.**
- Perform churn EDA and identify customer segments with different risk/value profiles.
- Build and calibrate a churn probability model.
- Construct a simple customer value proxy using tenure, charges and remaining-value assumptions.
- Design a retention targeting rule based on expected value and a fixed campaign budget.
- Run sensitivity analysis over offer cost and the assumed probability that an offer saves a would-be churner.

**Baseline (required).**
- Logistic regression plus one tree-based model.
- Calibration and threshold analysis.
- An expected-value targeting simulator comparing model-based targeting with simple rules (for example, highest churn risk only).

**Stretch (optional / bonus).**
- Gradient boosting with SHAP/feature attribution.
- Profit curve / budget optimisation across multiple campaign sizes.
- Segment-specific retention policies with a fairness or customer-experience discussion.

**Success metrics.**
- Predictive: PR-AUC/ROC-AUC plus calibration.
- Targeting: precision among contacted customers and coverage of high-risk/high-value customers.
- Business: expected net retention value/savings under stated assumptions, with sensitivity ranges.

**Deliverables.**
- Churn scorecard and customer-level targeting table.
- Retention playbook with campaign size, offer assumptions and expected-value logic.
- Management dashboard with risk, value, target segments and sensitivity analysis.

**Scope guardrails.**
- The dataset contains no randomised retention campaign. Do not perform or claim causal uplift modelling from these data.
- The dataset is a teaching/sample dataset; teams must discuss external-validity limitations.
- The assumed save rate and offer cost must be visible parameters rather than hidden constants.
