# Verification record

Final release checks on 2026-10-10, Windows 11, Python 3.13.9, environment installed from `requirements.lock.txt`. Machine-readable evidence is in `artifacts/qa/`.

## Runs

| Run | Role |
|---|---|
| `20261010T155515972611Z-88be4b93` | Run A: first complete `run-all --pdf require` with the final code and configuration |
| `20261010T155849068129Z-88be4b93` | Run B: second complete `run-all --pdf require`, current (`artifacts/latest.json`); all reports use it |

Earlier development runs were pruned with `python -m telco_retention prune --keep 2`; they remain in git history.

## Results

| Check | Command | Result |
|---|---|---|
| Dependencies | `pip check` | No broken requirements |
| Automated tests | `pytest -q --junitxml artifacts/qa/pytest.xml` | **116 passed**, 0 failed, 0 errors (133 s) |
| Notebooks | `scripts/verify_notebooks.py` | 4/4 committed notebooks executed for run B with no errors; re-executed copies in `artifacts/qa/notebooks/` ([notebooks.json](../artifacts/qa/notebooks.json)) |
| Release | `scripts/verify_release.py` | Passed ([release.json](../artifacts/qa/release.json)): 48 required artifacts, sizes derived from configuration (including 5,000 Monte Carlo draws and 8 stress-test rows), only registered figures in `reports/figures`, pilot sized from the recommended list and tested against its break-even, extended-data join accepted for all 7,043 customers with no context field among the model inputs, code hashes unchanged since training, 17 documents identical to a fresh render of the templates (line endings ignored), no broken relative links |
| Reproducibility | part of `verify_release.py` | Run A vs run B: test metrics equal (absolute tolerance 1e-10), identical selected customers and offers for both expected-value strategies, identical scenario IDs, and equal Monte Carlo summary, stress test, points card and model money check |
| Submission files | `python -m telco_retention export --pdf require` | Executive brief 796 words, **2 pages** as PDF (Word); deck **14 slides, all with speaker notes**, deck lint clean, PDF 14 pages; PDFs made from run B ([deliverables manifest](../reports/deliverables-manifest.json)) |
| Dashboard (headless) | part of `verify_release.py` | Warmed recalculation after a budget change: max 0.70 s |
| Dashboard (browser) | `scripts/browser_qa.py` with Chrome | Passed 8 checks ([browser.json](../artifacts/qa/browser.json)): Decision page with five KPIs, recommendation, who gets an offer and the action list; budget 0 and restore; ZIP export with list, assumptions and the report's scenario ID; custom budget survives navigation and the live chance of a loss is shown; scenario analysis and stress test computed; model page with odds ratios, points card and separate challenger SHAP; template upload scored without warnings and a known ID disclosed; contradictory and invalid CSVs rejected |
| Visual review | full-page screenshots and rendered PDF pages | Brief, deck slides and the three dashboard pages inspected. Fixed during review: Markdown italics and links shown raw in the DOCX, numbered lists continuing across sections, clipped action-list columns, hidden tenure chip, histogram tails piled at the edges, overlapping log-scale tick labels |
| Requirements review (second round) | course brief and a grader's reading of every deliverable | Fixed: rank-deficient feature design (48 columns, rank 24), validation metrics at a different threshold from test, uninterpreted segment errors, break-even mislabelled in the assumption register and notebook 04, two different "gain" figures, overclaims, course wording in manager documents, Vietnamese law applied to a US sample without saying so, release check failing on macOS and Linux |

Screenshots: [decision](../artifacts/qa/dashboard-decision.png), [assumptions & sensitivity](../artifacts/qa/dashboard-assumptions.png), [model evidence](../artifacts/qa/dashboard-model.png), [scorecard](../artifacts/qa/dashboard-scorecard.png), [upload](../artifacts/qa/dashboard-upload.png).

## What the tests cover

- **Data:** schema and domain validation, service consistency, duplicates, upload limits and encodings, split integrity and proportions, ordered tenure segments, 0/1 flags and no derived duplicates among the features, upload template with new IDs.
- **Extended data:** standard-library `.xlsx` reader with sparse cells, join accepted only when fields agree, churn score never kept, context fields never in the model data.
- **Model:** artifact round trip, label not used for scoring, training-only medians, full-rank reference coding, feature-review rule, all candidates reported at the chosen threshold, the deployed model as one linear score, the points card adding up and tracking the model, error profiles matching the confusion matrix, selection rule, upload origin flags, SHAP additivity, calibration statistics, gains and precision@k.
- **Decision engine:** hand-calculated EV and discounted value, budget edge cases, offers found by ID, optimiser equal to brute force with eligibility rules and the contact cap, solver fallbacks, fixed vs re-optimised lists, scenario IDs stable across int/float spellings.
- **Analysis:** explicit budget rule, scenario overrides including the tenure effect, sensitivity reference case and size, tornado directions, profit curve and budget recommendation rule, strategy selection rule, paired bootstrap, fairness ratios, pilot sample size and decision rule, break-even save rate, risk x value partition, prior shift keeping the ranking, stress-test rows, vectorised Monte Carlo repricing equal to the campaign code.
- **Reporting and export:** every template renders, the brief stays under 800 words and decision-first with the issue before the recommendation, one headline gain in brief, deck, demo and report, no overclaiming phrases in manager documents, documents follow changed facts, missing facts fail loudly, notebook generation, DOCX structure, deck notes on every slide.
- **Dashboard:** default view equals the report (KPIs, scenario ID under technical details, gap to risk-only), budget and save-rate changes, assumption strip on the decision pages and none on the model page, live chance of a loss, unlabelled upload, segment-offer mode, missing-artifact messages, controls persisting across pages, defaults read from the model bundle, scenario analysis and stale-result warning.
- **Language:** no Vietnamese text in deliverables (original titles of Vietnamese sources in the reference list excepted).

## Headline results verified (run B, test split)

| Item | Value |
|---|---|
| Feature design | Smallest full-rank set within one standard error: without TotalCharges (20 encoded columns) |
| Deployed model | Calibrated logistic regression; ROC-AUC 0.830, PR-AUC 0.620, ECE 0.019; points card within 1.0 percentage point of the model on average |
| Same $3,500 budget | Risk-only $1,301; expected value (standard offer) $2,340; expected value + segment offers (recommended on validation) $2,668, i.e. +$1,368 vs risk-only |
| Recommended budget | Standard offer for 26% of customers (validation rule): $9,150 buys 324 offers (23% of test customers) for $4,145 expected net value; about $45,737 for the 7,043-customer base |
| Break-even save rate | 11.3% for the base-budget list, 13.8% for the recommended list (assumed 20%) |
| All assumptions at once | Recommended list loses money in 17.4% of 5,000 draws, base-budget list in 9.0%; expected-value targeting beats risk-only in 99.96% of draws |
| Pilot | 1,620 customers (810 offered, 810 held out), about $22,875; go after one wave with probability 95% if the true save rate is 20% |
| Churn reasons | 46% of churners left for price or a competitor's offer |

All figures are expected values under the documented assumptions; see the [assumption register](assumption-register.md) and the [analysis report](../reports/analysis-report.md).
