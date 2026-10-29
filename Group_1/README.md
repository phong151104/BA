# Group 1 - Profit-Aware Telecom Churn and Retention Targeting

Capstone project, Topic 7, Introduction to Business Analytics (Assoc. Prof. Nguyễn Bình Minh), Hanoi University of Science and Technology.

| Member | Student ID | Email |
|---|---|---|
| Phạm Tuấn Kiệt | 20252751M | kiet.pt252751m@sis.hust.edu.vn |
| Nguyễn Trung Hiếu | 20261059M | Hieu.NT261059M@sis.hust.edu.vn |
| Bùi Tiến Dũng | 20261204M | Dung.BT261204M@sis.hust.edu.vn |
| Phạm Hùng Phong | 20261061M | phong.ph261061m@sis.hust.edu.vn |

**Business question.** Given a limited retention budget, which customers should receive an offer when both churn risk and expected economic value are considered?

**Where to start.** The [executive brief](03_Executive_Brief/Executive_Brief.pdf) gives the answer in two pages. The [final report](01_Final_Report/Final_Report.pdf) has the full analysis, and the [presentation](02_Presentation/Presentation.pptx) has the speaker script in its notes. The [dashboard](04_Dashboard/dashboard_html/Retention_Dashboard.html) opens in any browser with no installation.

## What is where

### Required project package

| Requirement | Where |
|---|---|
| Reproducible code/notebooks with a README and clear run instructions | [09_Code](09_Code/README.md): pipeline in `src/`, four executed notebooks in `notebooks/`, tests in `tests/`, run instructions in its README and below |
| Data dictionary and source log (source URL, download date, filters, joins, major cleaning decisions) | [Data dictionary](06_Data_Dictionary_and_Source_Log/Data_Dictionary.pdf), [source log and cleaning log](06_Data_Dictionary_and_Source_Log/Source_Log_and_Cleaning_Log.pdf) |
| Executive brief (maximum 2 pages) for a decision-maker | [PDF](03_Executive_Brief/Executive_Brief.pdf), [Word](03_Executive_Brief/Executive_Brief.docx) |
| Small interactive dashboard: 3-5 decision KPIs and one actionable view | It comes in two editions with the same pages (how to open them is below). [HTML edition](04_Dashboard/dashboard_html/Retention_Dashboard.html): one file, opened by double-click. Streamlit edition: `09_Code/app/Home.py`. The *Decision* page holds the five KPI cards and the action list (who gets which offer, with export). See the [user guide](04_Dashboard/dashboard_streamlit/Dashboard_User_Guide.pdf) and the [screenshots](04_Dashboard/dashboard_streamlit/screenshots/dashboard-decision.png) |
| Model/analysis card: target, features, validation design, assumptions, risks, ethics/bias, limitations | [Model card](05_Model_Card/Model_Card.pdf) |

### Topic 7 deliverables

| Deliverable | Where |
|---|---|
| Churn scorecard and customer-level targeting table | The [points card](07_Churn_Scorecard_and_Targeting_Table/Churn_Scorecard.pdf) scores a customer by hand. [Churn scores](07_Churn_Scorecard_and_Targeting_Table/churn_scores_all_customers.csv) gives every customer's calibrated churn probability and risk band. The [targeting table](07_Churn_Scorecard_and_Targeting_Table/customer_targeting_table.csv) covers the held-out test customers: value, best offer, expected value, decision and reason |
| Retention playbook: campaign size, offer assumptions, expected-value logic | [Retention playbook](08_Retention_Playbook/Retention_Playbook.pdf) |
| Management dashboard: risk, value, target segments, sensitivity | Same dashboard. The *Decision* page shows risk, value and target segments ([screenshot](04_Dashboard/dashboard_streamlit/screenshots/dashboard-decision.png)). The *Assumptions & sensitivity* page shows the tornado chart, scenarios, profit curve, save rate x offer cost grid and the chance of a loss ([screenshot](04_Dashboard/dashboard_streamlit/screenshots/dashboard-assumptions.png)) |

### Presentation

The [slides](02_Presentation/Presentation.pptx) are also available as a [PDF](02_Presentation/Presentation.pdf). The talk lasts 8 minutes and is given by Kiệt, Hiếu and Dũng; Phong then gives the live demo. The [speaker script](02_Presentation/Speaker_Script.pdf) has the same text as the slide notes, and the [demo script](02_Presentation/Demo_Script.pdf) has the timed steps for the demo.

## Open the dashboard

**HTML edition (no installation).** Double-click [04_Dashboard/dashboard_html/Retention_Dashboard.html](04_Dashboard/dashboard_html/Retention_Dashboard.html) to open it in Chrome, Edge or Firefox. It works offline.
- **Data.** It holds the scores of the 1,409 held-out test customers, the model evidence and the trained model from the run in [manifest.json](manifest.json).
- **What updates.** Every campaign, KPI and scenario is recomputed in the browser when you change the budget or an assumption, with the same rules as the pipeline.

**Streamlit edition.** You need Windows and Python 3.13.
- **Start.** Double-click `04_Dashboard/dashboard_streamlit/Run_Dashboard.bat`.
- **First run.** It creates the environment in `09_Code\.venv`, which takes a few minutes and needs the internet. Then it opens http://127.0.0.1:8501.
- **Where to run it.** Copy or unzip this folder to a local disk first, so the environment is not created inside a synced folder.
- **Manual start.** Run these commands in PowerShell from the `09_Code` folder. For macOS or Linux, see [09_Code/README.md](09_Code/README.md).

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

## Reproduce the analysis

`.\.venv\Scripts\python.exe -m telco_retention run-all` downloads the data (the checksum is verified) and retrains, re-evaluates and re-simulates. It then regenerates every table, figure, document and notebook, the submission files and the HTML dashboard.

- Tests: `.\.venv\Scripts\python.exe -m pytest -q`.
- Release checks: `scripts/verify_release.py`.

The evidence of the last full verification is in `09_Code/docs/verification.md`.

## Notes

- **The data.** The IBM Telco Customer Churn sample describes a fictional US company, so money is in its USD.
- **Save rates.** The save rates are stated assumptions, not estimates: the data contain no randomised campaign, so no causal uplift is claimed. The report proposes a randomised pilot to measure them.
- **One run behind every number.** Every number in these documents comes from one pipeline run, whose ID is recorded in [manifest.json](manifest.json).
- **How this folder is made.** `scripts/build_submission.py` builds this folder from the repository. The only exception is this README. `09_Code` is a copy of the repository.
