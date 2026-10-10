# Requirements traceability

Every item of the course brief ([course-requirements.md](course-requirements.md)) mapped to the evidence that satisfies it. Generated documents always reflect the latest run.

## Format and expectations

| Requirement | Evidence |
|---|---|
| Clean, reproducible analytics pipeline | `python -m telco_retention run-all` ([README](../README.md)); run manifests with configuration, data checksum, dependency versions and code hashes; two-run reproducibility check in `scripts/verify_release.py` ([verification](verification.md)) |
| Begins with a business decision, not an algorithm | [Business case](business-case.md): decision owner, options, KPIs; the brief and deck open with the decision |
| Recommendation traceable from data, assumptions, analysis and validation | [facts.json](../reports/facts.json) maps quoted numbers to run artifacts; [assumption register](assumption-register.md) with sources; scenario IDs shared by dashboard, exports and reports; validation/test separation ([model card](model-card.md#5-validation-design)) |

## Required project package

| Requirement | Evidence |
|---|---|
| Reproducible code/notebooks with README and run instructions | [README](../README.md); `src/telco_retention`; four executed notebooks in [notebooks/](../notebooks); [architecture](implementation.md) |
| Data dictionary and source log (URL, download date, filters, joins, cleaning decisions) | [Data dictionary](data-dictionary.md), [source log](source-log.md), [cleaning log](cleaning-log.md), [data readiness review](data-readiness-review.md) |
| Executive brief, max 2 pages, for a decision-maker | [executive-brief.md](../reports/executive-brief.md), [DOCX](../reports/executive-brief.docx), [PDF](../reports/executive-brief.pdf); page count recorded in `reports/deliverables-manifest.json` and checked by `verify_release.py` |
| Small interactive dashboard: 3-5 decision KPIs and one actionable view | `app/Home.py`: five KPI cards (expected net value vs risk-only, ROI, customers contacted, precision among contacted, high-risk/high-value coverage); actionable view = action list with export on *Campaign builder*; [user guide](user-guide.md) |
| Model/analysis card: target, features, validation, assumptions, risks, ethics/bias, limitations | [Model card](model-card.md) |

## Topic 7 core tasks

| Task | Evidence |
|---|---|
| Churn EDA; segments with different risk/value profiles | Notebook 01; [analysis report section 4](../reports/analysis-report.md#4-who-churns-and-who-is-worth-saving); `eda_segments.csv`, `risk_value_matrix.csv`; figures `eda_drivers.png`, `risk_value.png`, `quadrant_selection.png` |
| Build and calibrate a churn probability model | `modeling.train` (sigmoid calibration on out-of-fold predictions); ECE, slope and intercept in `test_metrics.csv`; `calibration.png` |
| Simple customer value proxy (tenure, charges, remaining value) | `business.value_customers`; [assumption register](assumption-register.md) |
| Retention targeting rule on expected value with a fixed budget | `business.campaign`, `analysis.campaign_budget`; `targeting_*.csv`; [playbook](retention-playbook.md) |
| Sensitivity over offer cost and save rate | `sensitivity.csv` (grid, frozen and re-optimised), `tornado.csv`, `scenarios.csv`, `break_even.json`; `sensitivity_heatmap.png`, `tornado.png`; dashboard *Scenarios & budget* |

## Baseline (required)

| Requirement | Evidence |
|---|---|
| Logistic regression plus one tree-based model | Logistic regression, random forest (and XGBoost) in `validation_metrics.csv`, `test_metrics.csv` |
| Calibration and threshold analysis | Calibration: ECE/slope/intercept, reliability curve. Threshold: `threshold_analysis.csv` (F1 on validation) and `threshold_business.csv` (threshold vs expected-value rule, break-even probabilities) |
| EV simulator comparing model-based targeting with simple rules | `strategy_comparison.csv`: none, highest risk, highest risk with positive EV, highest value, random (100 seeds), EV single offer, EV segment offers; paired bootstrap in `economic_uncertainty.csv` |

## Stretch (bonus)

| Stretch goal | Evidence |
|---|---|
| Gradient boosting with SHAP | XGBoost challenger; `shap_global.csv`, `shap_local.csv`, `shap_challenger.png`; dashboard *Model & data* |
| Profit curve / budget optimisation across campaign sizes | `budget_curve.csv` (validation and test, 2% steps, marginal ROI); recommendation chosen on validation (`validation_decisions.json`, `recommended_campaign.json`); `profit_curve.png` |
| Segment-specific policies with fairness / customer-experience discussion | Offer catalog with eligibility rules, MILP with contact cap (`segment_offer_mix.csv`); `fairness.csv` with bootstrap and risk-adjusted ratios; [model card section 8](model-card.md#8-fairness-and-customer-experience); [analysis report section 9](../reports/analysis-report.md#9-fairness-and-customer-experience) |

## Success metrics

| Metric | Evidence |
|---|---|
| PR-AUC / ROC-AUC plus calibration | `test_metrics.csv`, `bootstrap_intervals.csv`, `calibration.png`, `discrimination.png` |
| Precision among contacted; coverage of high-risk/high-value customers | KPI cards; `strategy_comparison.csv` columns `precision_contacted`, `high_risk_high_value_coverage` |
| Expected net retention value under stated assumptions, with sensitivity ranges | `strategy_comparison.csv`, `scenarios.csv`, `tornado.csv`, `sensitivity.csv`; brief "How sure are we?" |

## Deliverables

| Deliverable | Evidence |
|---|---|
| Churn scorecard and customer-level targeting table | `reports/tables/scorecard.csv` (every customer, probability, risk band, origin); `reports/tables/targeting_*.csv` (EV, offer, decision, reason, scenario ID); dashboard export |
| Retention playbook (campaign size, offer assumptions, EV logic) | [Retention playbook](retention-playbook.md) |
| Management dashboard (risk, value, target segments, sensitivity) | `app/Home.py` pages *Overview*, *Campaign builder*, *Scenarios & budget*; screenshots in `artifacts/qa/` |

## Scope guardrails

| Guardrail | How it is respected |
|---|---|
| No causal uplift claims | Save rates are labelled assumptions everywhere; label-based checks reuse the assumed save rate; [pilot design](pilot-design.md) proposes how to measure uplift |
| External-validity limitations discussed | [Data readiness review](data-readiness-review.md), [model card section 10](model-card.md#10-limitations-and-external-validity), [literature review section 7](literature-review.md#7-external-validity) |
| Save rate and offer cost are visible parameters | `configs/default.yaml`; dashboard assumption strip and controls; [assumption register](assumption-register.md) |

## Six-week checkpoints

| Week | Checkpoint | Evidence |
|---|---|---|
| 1 | Problem statement + data readiness review | [Business case](business-case.md), [data readiness review](data-readiness-review.md), [source log](source-log.md), [data dictionary](data-dictionary.md), notebook 01 |
| 2 | Reproducible baseline | Pipeline steps `download`-`evaluate`; logistic and prior-only baselines; tests in `tests/` |
| 3 | Model comparison + diagnostics | `validation_metrics.csv`, `test_metrics.csv`, calibration, gains, segment errors, SHAP; notebook 02 |
| 4 | Actionable decision logic | Expected-value rule, knapsack optimiser, offer catalog, strategy comparison; notebook 03; [playbook](retention-playbook.md) |
| 5 | Draft dashboard + recommendations | Dashboard; sensitivity, profit curve, fairness; notebook 04; [analysis report](../reports/analysis-report.md) |
| 6 | Final submission package | Executive brief DOCX/PDF, deck PPTX with notes, demo script, Q&A, [verification](verification.md) |
