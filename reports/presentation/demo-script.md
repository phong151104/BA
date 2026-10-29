<!-- Generated from src/telco_retention/templates/presentation/demo-script.md.j2 for run 20261029T063931261171Z-88be4b93. Edit the template, not this file. -->
# Dashboard demo script (5 minutes)

**Before the session:** run `.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true` and open http://127.0.0.1:8501. Keep the browser at 100% zoom. Expected default values come from run `20261029T063931261171Z-88be4b93`.

| Time | Page / action | What to say | What the audience should see |
|---|---|---|---|
| 0:00 | **Decision** | "This page answers the business question. The strip lists every assumption behind the numbers." | Question, budget and offer policy, assumption strip |
| 0:30 | Read the five KPI cards | "With the base budget we contact 153 customers for an expected net value of $2,668, $1,368 more than calling the riskiest customers. 60% of them actually left, and we reach 98% of high-risk, high-value customers." | KPI row: $2,668, 76.2%, 153, 60.1%, 98.2% |
| 1:00 | *Who gets an offer* table and chart | "Fibre customers on monthly contracts with high bills. Low-risk customers would mostly stay anyway; risky customers with small bills cannot repay an offer, and that is where risk-only targeting spends its budget." | Profile table, segment table, risk x value chart |
| 1:45 | Open *Compare targeting rules* | "Same budget, six rules. Value-only loses money; expected value wins." | Comparison table |
| 2:00 | Action list: open *Why is a customer in or out?* | "Every decision is explained with its own numbers and break-even save rate." | Formula with probability, save rate, value, cost |
| 2:30 | Click **Export campaign** | "The export holds the list, the assumptions and the scenario ID, so anyone can trace it." | ZIP download |
| 2:45 | **Assumptions & sensitivity**: set the standard offer's save rate to 0.10 | "If the offer keeps only 10% of would-be churners, fewer customers are worth an offer and the chance of a loss jumps." | Expected net value falls; chance of a loss rises |
| 3:15 | Set it back to 0.2; *Run scenario analysis* | "The save rate and the value horizon matter most. The profit curve shows where extra budget stops paying, and the stress test shows how much thinner margins are at real churn levels." | Tornado, profit curve with recommended marker, stress-test table |
| 4:15 | **Model evidence**: *Drivers and scorecard* tab | "A calibrated logistic regression. Month-to-month contracts and fibre raise the odds of churning most; the points card lets agents score a customer by hand." | Odds-ratio chart, points table |
| 4:45 | Close on **Decision** | "We ask for a randomised pilot to measure the save rate before scaling." | Decision page |

**If something fails:** the screenshots in `artifacts/qa/` show every page with the default run; the executive brief PDF contains the same numbers.
