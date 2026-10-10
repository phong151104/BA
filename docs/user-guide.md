# Dashboard user guide

## Start

From the project folder on Windows (no need to activate the environment or change the PowerShell execution policy):

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Open http://127.0.0.1:8501. The dashboard reads the latest pipeline run; it never retrains.

## Layout

- **Sidebar:** page navigation, the customer list in use (held-out test customers, or an uploaded CSV once scored), the deployed model and run.
- **Assumption strip** (top of every page): budget, standard offer cost, contact cost, save rate, margin, value horizon, discount rate and the **scenario ID**. With default assumptions the ID equals the one in the reports.
- **Budget and assumptions** panel (expanded on *Campaign builder*): every assumption can be changed for the session; the configuration file is never modified.

## Pages

1. **Overview** - the decision page. Five KPI cards (expected net value with the difference vs risk-only targeting, ROI, customers contacted, precision among contacted, high-risk/high-value coverage), the recommended action with its break-even save rate, the risk x value map with validation cut-offs, a segment table comparing the plan with risk-only targeting, and the top 10 customers to call.
2. **Campaign builder** - all assumptions, the same-budget comparison of six rules, the full **action list** (search, contacted-only filter, per-customer explanation) and the **export** button.
3. **Scenarios & budget** - press *Run scenario analysis* to compute, for the current list and assumptions: break-even save rate and offer cost, minimum viable save rate, tornado chart, pessimistic/base/optimistic scenarios, profit curve with marginal ROI, and the save rate x offer cost grid (frozen or re-optimised list). Results are cached per scenario; if assumptions change, a warning asks to re-run.
4. **Model & data** - test metrics of the deployed calibrated logistic model with bootstrap intervals, calibration and gains charts, model drivers, all candidates, the XGBoost challenger with SHAP (clearly marked as not deployed), data source and quality, and **Score new customers** (CSV upload).

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
| PDF export fails | Microsoft Word/PowerPoint are needed for PDF; run `export --pdf skip` for DOCX/PPTX only |
