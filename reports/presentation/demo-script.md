<!-- Generated from src/telco_retention/templates/presentation/demo-script.md.j2 for run 20261010T124415068764Z-88be4b93. Edit the template, not this file. -->
# Dashboard demo script (5 minutes)

**Before the session:** run `.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true` and open http://127.0.0.1:8501. Keep the browser at 100% zoom. Expected default values come from run `20261010T124415068764Z-88be4b93`.

| Time | Page / action | What to say | What the audience should see |
|---|---|---|---|
| 0:00 | **Overview** | "This is the decision page. The strip at the top lists every assumption behind the numbers." | Assumption strip with scenario `d081da7490e0` |
| 0:30 | Read the five KPI cards | "With the base budget we contact 152.0 customers for an expected net value of $2,420, $1,322 more than calling the riskiest customers. Precision 60%; we reach 100% of high-risk, high-value customers." | KPI row: $2,420, 69.2%, 152.0, 59.9%, 100.0% |
| 1:00 | Risk x value chart and segment table | "Risk-only would spend almost everything in the high-risk, low-value corner. Our rule reaches every high-risk, high-value customer." | Scatter with threshold lines; table with contacted counts by segment |
| 1:45 | **Campaign builder** -> comparison table | "Same budget, six rules. Random and value-only lose money; expected value wins." | Comparison table |
| 2:15 | Change *Save rate* to 0.10 | "If the offer keeps only 10% of would-be churners, the plan shrinks; fewer customers are worth contacting." | KPIs drop; customers contacted falls |
| 2:45 | Set it back to 0.2; open *Why is a customer in or out?* | "Every decision is explained with its own numbers and break-even save rate." | Formula with p, save rate, value, cost |
| 3:15 | Click **Export campaign** | "The export contains the list, the assumptions and the scenario ID, so anyone can trace it." | ZIP download |
| 3:30 | **Scenarios & budget** -> *Run scenario analysis* | "Break-even save rate 11.8%. The tornado shows the save rate and horizon matter most. The profit curve shows where extra budget stops paying." | Break-even metrics, tornado, profit curve with recommended marker |
| 4:30 | **Model & data** | "Calibrated logistic regression; the XGBoost challenger with SHAP is shown separately and is not deployed. New customer files can be scored here." | Metrics with intervals, calibration, gains, SHAP |
| 5:00 | Close | "We ask for a randomised pilot to measure the save rate before scaling." | Back to Overview |

**If something fails:** the screenshots in `artifacts/qa/` show every page with the default run; the executive brief PDF contains the same numbers.
