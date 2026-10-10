# Verification record

Final release checks on 2026-10-10, Windows 11, Python 3.13.9, environment installed from `requirements.lock.txt`. Machine-readable evidence is in `artifacts/qa/`.

## Runs

| Run | Role |
|---|---|
| `20261010T124155118613Z-88be4b93` | Run A: first complete `run-all` with the final code and configuration |
| `20261010T124415068764Z-88be4b93` | Run B: second complete `run-all`, current (`artifacts/latest.json`); all reports use it |

Earlier development runs were pruned with `python -m telco_retention prune --keep 2`; they remain in git history.

## Results

| Check | Command | Result |
|---|---|---|
| Dependencies | `pip check` | No broken requirements |
| Automated tests | `pytest -q --junitxml artifacts/qa/pytest.xml` | **97 passed**, 0 failed, 0 errors (77 s) |
| Notebooks | `scripts/verify_notebooks.py` | 4/4 committed notebooks executed for run B with no errors; re-executed copies in `artifacts/qa/notebooks/` ([notebooks.json](../artifacts/qa/notebooks.json)) |
| Release | `scripts/verify_release.py` | Passed ([release.json](../artifacts/qa/release.json)): 27 required artifacts, sizes derived from configuration, code hashes unchanged since training, 15 documents identical to a fresh render of the templates, no broken relative links |
| Reproducibility | part of `verify_release.py` | Run A vs run B: test metrics equal (absolute tolerance 1e-10), identical selected customers and offers for both expected-value strategies, identical scenario IDs |
| Submission files | `python -m telco_retention export --pdf require` | Executive brief 717 words, **2 pages** as PDF (Word); deck **13 slides, all with speaker notes**, deck lint clean, PDF 13 pages ([deliverables manifest](../reports/deliverables-manifest.json)) |
| Dashboard (headless) | part of `verify_release.py` | Warmed recalculation after a budget change: max 0.53 s |
| Dashboard (browser) | `scripts/browser_qa.py` with Chrome | Passed 8 checks ([browser.json](../artifacts/qa/browser.json)): five KPIs and the report's scenario ID on Overview; budget 0 and restore; ZIP export with list, assumptions and scenario ID; model page with separate challenger SHAP; custom budget survives navigation; scenario analysis computed; CSV upload scored with ID-overlap notice; contradictory and invalid CSVs rejected |
| Visual review | screenshots and rendered PDF pages | Brief, deck slides and the four dashboard pages inspected; issues found and fixed during review: money rendered as LaTeX in Streamlit markdown, money columns without thousands separators, profit-curve colours not following the strategy colours, truncated KPI labels |

Screenshots: [overview](../artifacts/qa/dashboard-overview.png), [campaign builder](../artifacts/qa/dashboard-campaign.png), [scenarios](../artifacts/qa/dashboard-scenarios.png), [model & data](../artifacts/qa/dashboard-model.png), [upload](../artifacts/qa/dashboard-upload.png).

## What the tests cover

- **Data:** schema and domain validation, service consistency, duplicates, upload limits and encodings, split integrity and proportions, ordered tenure segments.
- **Model:** artifact round trip, label not used for scoring, training-only medians, selection rule, upload origin flags, SHAP additivity, calibration statistics on synthetic calibrated and over-confident data, gains and precision@k.
- **Decision engine:** hand-calculated EV and discounted value, budget edge cases, offers found by ID, optimiser equal to brute force with eligibility rules and the contact cap, solver fallbacks, fixed vs re-optimised lists, scenario IDs stable across int/float spellings.
- **Analysis:** explicit budget rule, scenario overrides, sensitivity reference case and size, tornado directions, profit curve monotonicity and budget recommendation rule, strategy selection rule, paired bootstrap, fairness ratios, pilot sample size against the closed-form formula, break-even save rate, risk x value partition.
- **Reporting and export:** every template renders, the brief stays under 800 words and decision-first, documents follow changed facts, missing facts fail loudly, notebook generation, DOCX structure, deck notes on every slide.
- **Dashboard:** default view equals the report (KPIs, scenario ID, gap to risk-only), budget and save-rate changes, assumption strip on every page, unlabelled upload, segment-offer mode, missing-artifact messages, controls persisting across pages, defaults read from the model bundle, scenario analysis and stale-result warning.
- **Language:** no Vietnamese text in deliverables (original titles of Vietnamese sources in the reference list excepted).

## Headline results verified (run B, test split)

| Item | Value |
|---|---|
| Deployed model | Calibrated logistic regression; ROC-AUC 0.831, PR-AUC 0.619, ECE 0.020 |
| Same $3,500 budget | Risk-only $1,098; expected value (standard offer) $2,130; expected value + segment offers (recommended on validation) $2,420 |
| Recommended budget | 24% of customers (validation rule): $8,450 for $3,692 expected net value on test |
| Break-even save rate | 11.8% (assumed 20%) |

All figures are expected values under the documented assumptions; see the [assumption register](assumption-register.md) and the [analysis report](../reports/analysis-report.md).
