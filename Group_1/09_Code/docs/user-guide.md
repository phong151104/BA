# Dashboard user guide

## Start

From the project folder on Windows (no need to activate the environment or change the PowerShell execution policy):

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. The dashboard reads the latest pipeline run; it never retrains. On Windows, double-clicking `run_dashboard.bat` in the project folder does the same. On first use it also creates the environment, which needs Python 3.13 and an internet connection.

## Single-file edition (HTML)

The same dashboard also comes as one file: `reports/dashboard/retention-dashboard.html`, which is `04_Dashboard/dashboard_html/Retention_Dashboard.html` in the submission folder.

- **Opening it.** Double-click the file to open it in Chrome, Edge or Firefox. It needs no Python, no server and no internet connection.
- **What it contains.** It embeds the results of the pipeline run named in its sidebar: the scores of the held-out test customers, the model evidence and the deployed model.
- **What it computes.** It computes every campaign, KPI, rule comparison, break-even, chance of a loss and scenario analysis in the browser, with the same rules as the pipeline. `tests/test_html_dashboard.py` checks that it produces the same lists and numbers.
- **How it differs from the Streamlit dashboard:**
  - The chance of a loss uses the browser's own random draws, so it can differ by about a percentage point.
  - There is no scenario ID.
  - The export is a set of CSV and JSON files instead of a ZIP.
- **Scoring new customers.** An uploaded CSV is scored in the browser by the same model, and nothing is sent anywhere.

## Layout

- **Sidebar:** page navigation, the customer list in use (held-out test customers, or an uploaded CSV once scored) and the deployed model.
- **Assumption strip** (top of the *Decision* and *Assumptions & sensitivity* pages): budget, standard offer and its cost, contact cost, save rate, margin, value horizon and discount rate. The run and **scenario ID** are under *Technical details* on the Decision page and in every export; with default assumptions the ID equals the one in the reports.
- Budget and offer policy can be changed on the Decision page; every other assumption on the *Assumptions & sensitivity* page. Changes last for the session and carry across pages; the configuration file is never modified.

## Pages

1. **Decision** - answers the business question. Five KPI cards (expected net value with the difference vs risk-only targeting, ROI, customers contacted, precision among contacted, high-risk/high-value coverage), the recommended action with its break-even save rate, **who gets an offer and who does not** (profile of the list, risk x value segments compared with risk-only targeting, and the risk x value map), a same-budget comparison of six rules, the **action list** (search, contacted-only filter, per-customer explanation) and the **export** button.
2. **Assumptions & sensitivity** - every assumption, the expected net value and break-even save rate of the current list, and the **chance this list loses money** when all register assumptions are drawn at once (live, 2,000 draws). Press *Run scenario analysis* to compute the tornado chart, pessimistic/base/optimistic scenarios, profit curve with marginal ROI and the save rate x offer cost grid (frozen or re-optimised list); results are cached per scenario and a warning asks to re-run after changes. The page ends with the pipeline's stress test (lower churn, Vietnamese prices).
3. **Model evidence** - four tabs: *Performance* (test metrics of the deployed calibrated logistic model with bootstrap intervals, calibration and gains, all candidates), *Drivers and scorecard* (odds ratios, the points card with score bands, and the XGBoost challenger with SHAP, clearly marked as not deployed), *Errors and money check* (each candidate valued in money, who the model gets wrong, performance by segment) and *Data and new customers* (source, quality and join, why churners left, **Score new customers**). This page computes no campaign.

## Offer policy

- **Single standard offer:** every customer can only receive the standard credit.
- **Segment-specific offers:** each customer may receive one offer whose eligibility rule they meet (contract upgrade for month-to-month, service bundle for internet customers without TechSupport, loyalty reward for tenure > 24 months, standard credit for everyone). The optimiser chooses the mix that maximises total expected value within the budget and the contact cap. This is the default when it won on validation.

## Uploading customers

- UTF-8 (with or without BOM), comma-separated, up to 10 MB / 50,000 rows; use the [template](../data/examples/customers_unlabeled.csv) and the [data dictionary](data-dictionary.md).
- `customerID` must be unique; `Churn`, `gender` and `SeniorCitizen` are optional and never used for scoring or selection.
- Missing numbers are filled with training medians. Invalid numbers, unknown categories, missing columns, duplicate or empty IDs, or service contradictions (for example `PhoneService = No` with `MultipleLines = Yes`) reject the whole file with a row/column error table; the previous customer list stays in place.
- `Origin` shows whether an uploaded ID matches the project's train, validation or test customers; results on IDs seen in training are not an independent evaluation.
- After scoring, choose *Uploaded CSV* in the sidebar. Without labels, precision among contacted is shown as the expected value (mean predicted probability).

## Reading the results

- KPIs add up contacted customers only; other rows show the best potential offer for reference.
- The per-customer explanation shows p, save rate, value, cost, EV and break-even save rate - an economic explanation, not a cause of churn.
- In the grid, the save-rate axis is the standard offer's rate; other offers move by the same percentage points. The cost multiplier applies to offer costs, not contact cost.
- A frozen list can exceed the budget or lose money when costs rise or save rates fall; that is a robustness check, not a feasible new list.
- The export ZIP contains the full targeting table, the contact list, `assumptions.json` (with scenario ID) and `summary.json`. It contains no contact details and sends nothing.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named telco_retention` | Use the `.venv` interpreter and run `pip install --no-deps -e .` |
| "Analysis results are not ready" | Run `python -m telco_retention run-all` |
| Port 8501 in use | Close the previous session or add `--server.port 8502` |
| CSV rejected | Export UTF-8 comma-separated, follow the template, read the error table |
| Raw checksum mismatch | The raw file changed; restore it - the pipeline never overwrites raw data |
| Scenario charts out of date | Press *Run scenario analysis* again after changing assumptions |
| Chance of a loss shows 0% with nobody selected | No customer has positive expected value under these assumptions: not running the campaign is the right decision |
| PDF export fails | Microsoft Word/PowerPoint are needed for PDF; run `export --pdf skip` for DOCX/PPTX only |
