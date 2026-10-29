# Architecture and reproducibility

## Pipeline

```
raw CSV (checksum) -> validate/clean -> stratified 60/20/20 split -> features
  extended IBM file (checksum) -> join on customer ID, all shared fields must agree -> churn reasons, CLTV (context only)
  -> feature review on train (CV ablation) -> CV search per model family -> out-of-fold sigmoid calibration -> select on validation
  -> score all customers -> test metrics, bootstrap, calibration, gains, segment errors, error profiles, odds ratios, points card, SHAP
  -> value proxy + expected value + budget optimiser
       validation: risk/value cut-offs, strategy choice, budget recommendation
       test: strategy comparison, uncertainty, risk x value matrix, break-even, tornado,
             scenarios, sensitivity grid, profit curve, fairness audit, pilot sizing,
             model choice in money, churn reasons, stress test, Monte Carlo, target profile
  -> facts.json -> figures, Markdown documents, LaTeX report, notebooks -> DOCX/PDF brief, PPTX deck with speaker script, PDF report
```

| Module | Responsibility |
|---|---|
| `data.py` | Download with checksum, validation rules, cleaning, split, candidate features (0/1 flags, reference-coded categories), shared `tenure_segment` |
| `extended.py` | IBM extended sample: download with checksum, standard-library `.xlsx` reader, join checked field by field; keeps only churn reasons and CLTV in `customer_context.csv` |
| `modeling.py` | Feature review, model search, calibration, selection rule, metrics (incl. ECE, calibration slope/intercept), gains, error profiles, odds ratios and points card from the deployed model, scoring, SHAP |
| `business.py` | Value proxy, offer options with eligibility, knapsack selection (HiGHS via scipy `milp`), campaign summary and explanations, canonical scenario IDs |
| `analysis.py` | Validation-phase decisions, test-phase experiments (comparison, bootstrap, matrix, tornado, scenarios, sensitivity, profit curve, fairness, pilot, model money check, churn reasons, prior-shift stress test, vectorised Monte Carlo, target profile) |
| `facts.py` | Loads a run's artifacts once and derives every number the documents quote, with a source map |
| `templating.py` + `templates/` | Jinja2 templates (StrictUndefined) for every document that quotes a number |
| `figures.py` | Report figures with a fixed, colour-blind-checked palette |
| `notebooks.py` | Narrative notebooks generated from templates and executed in place |
| `presentation.py` | Presentation on the HUST template (`templates/presentation/hust-template.pptx`): slides drawn from the facts, speaker script with speaker and timing in the notes, rehearsal script, timing and pace lint |
| `latex.py` + `templates/latex/` | Final report as LaTeX (Jinja2 with `<< >>` / `<% %>` delimiters and LaTeX escaping), compiled with pdflatex |
| `export.py` | Executive brief DOCX/PDF (Word), presentation PPTX/PDF (PowerPoint) and the final report PDF (pdflatex); page, slide and timing checks |
| `reporting.py` | Orchestrates figures, tables, facts, documents, the LaTeX source and notebooks for one run |
| `app/Home.py` | Streamlit dashboard; calls the same package functions, never re-implements formulas |

## Validation boundaries

- Imputation, scaling and encoding are fitted inside training folds.
- `RandomizedSearchCV` tunes on train; `CalibratedClassifierCV(ensemble=False)` learns the sigmoid from out-of-fold predictions.
- Validation chooses the model (pre-set rule), the F1 threshold (classification metrics only), the risk/value cut-offs, the offer strategy and the budget recommendation.
- Test is scored once; bootstrap intervals resample test customers with frozen models and policies.
- SHAP uses XGBoost's native TreeSHAP (`pred_contribs`); contributions plus base value reproduce the challenger's logit exactly.

## Decision engine

- Value: `MonthlyCharges x margin x annuity(min(cap, base x tenure factor), monthly rate)`.
- EV per customer and offer: `p x save_rate x value - (offer_cost + contact_cost)`.
- One offer with equal costs: sorting by EV is exactly optimal and used directly ("optimal_sort").
- Several offers, eligibility rules or a contact cap: binary MILP with one offer per customer, the budget row and the cap row; the incumbent is checked for integrality, budget and cap before use, with a labelled greedy fallback.
- Baselines (risk, value, random) do not look at EV by design; "risk, positive EV only" filters first.
- Fixed sensitivity keeps the reference list and may exceed the budget (`budget_feasible = False`); retarget re-optimises within budget.
- Monte Carlo: every register assumption drawn at once (triangular low/base/high); frozen lists are repriced by a vectorised calculation that a test checks against `fixed_campaign`; the first draws are also re-optimised with a 0.1% solver gap.
- Stress test: probabilities are shifted by one logit constant to a lower average churn (ranks unchanged); the Vietnam-like rows scale bills and offers and use SMS contact cost.

## Parameters and traceability

- Every assumption lives in `configs/default.yaml` and is copied into the run manifest at training time; later steps read the manifest, so a run is self-contained.
- Offers are referenced by `offer_id` (`campaign.default_offer`), never by list position.
- Scenario IDs hash the value settings, offers, budget, strategy, contact cap and customer list after canonicalising numbers (12 and 12.0 hash alike); the dashboard's default scenario equals the report's.
- `reports/facts.json` maps each section of quoted numbers to its run artifact; generated documents start with a comment naming their template and run.

## Reproducibility and artifact lifecycle

- Python 3.13 with `requirements.lock.txt`; the project is installed with `pip install --no-deps -e .`.
- Each training run writes `artifacts/runs/<UTC time>-<data hash>` and points `artifacts/latest.json` at it; the manifest records configuration, dependency versions, data checksum and code hashes.
- Seeds fix splits, searches, bootstrap and random baselines; two full runs reproduce metrics and selected customers (checked by `scripts/verify_release.py`).
- `python -m telco_retention prune --keep 2` keeps the latest two runs (older ones remain in git history).
- Joblib artifacts are loaded only from the project's own runs; the dashboard never accepts uploaded models.

## Out of scope

No API server, database, authentication, CRM integration or real customer contact. Uploaded CSVs live only in the dashboard session.
