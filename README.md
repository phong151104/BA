# Retention Lab - profit-aware telecom churn and retention targeting

Business Analytics capstone, Topic 7. **Business question:** given a limited retention budget, which customers should receive an offer when both churn risk and expected economic value are considered?

**Answer in one line:** rank customers by the expected net value of an offer (churn probability x save rate x customer value - cost), let an optimiser choose customers and offers within the budget, size the budget where the marginal return falls below a hurdle, and validate the assumed save rate with a randomised pilot. Start with the [executive brief](reports/executive-brief.md) ([PDF](reports/executive-brief.pdf)).

## Quick start (Windows, Python 3.13)

Run from the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

On macOS or Linux, use `python3 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` in every command (the lock file skips the Windows-only packages automatically).

Open http://127.0.0.1:8501. Data, the trained model and all results are already in the repository, so the dashboard runs offline; a network connection is only needed to install packages or download the data on a fresh run.

## Reproduce everything

```powershell
.\.venv\Scripts\python.exe -m telco_retention run-all
```

`run-all` downloads the data (checksum-verified), prepares, trains, evaluates, simulates and then regenerates every table, figure, document, executed notebook, the executive brief (DOCX + PDF) and the slide deck (PPTX + PDF). PDF conversion uses Microsoft Word and PowerPoint; without them (for example on macOS or Linux) `run-all` skips the PDFs and still writes the DOCX and PPTX (`--pdf skip` forces this, `--pdf require` fails instead). Each run is stored in `artifacts/runs/<run_id>` with its configuration, data checksum and code hashes; `artifacts/latest.json` points to the current run.

Individual steps, in order:

```powershell
.\.venv\Scripts\python.exe -m telco_retention download
.\.venv\Scripts\python.exe -m telco_retention prepare
.\.venv\Scripts\python.exe -m telco_retention train
.\.venv\Scripts\python.exe -m telco_retention evaluate
.\.venv\Scripts\python.exe -m telco_retention simulate
.\.venv\Scripts\python.exe -m telco_retention report
.\.venv\Scripts\python.exe -m telco_retention export --pdf auto
.\.venv\Scripts\python.exe -m telco_retention score --input data/examples/customers_unlabeled.csv --output artifacts/example_scores.csv
.\.venv\Scripts\python.exe -m telco_retention prune --keep 2
```

## Tests and release checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_notebooks.py
.\.venv\Scripts\python.exe scripts/verify_release.py
.\.venv\Scripts\python.exe scripts/browser_qa.py   # needs the dashboard running and Chrome or Edge
```

Evidence of the last verification is in [docs/verification.md](docs/verification.md) and `artifacts/qa/`.

## Assumptions

All business assumptions are visible parameters in [`configs/default.yaml`](configs/default.yaml), explained with sources in the [assumption register](docs/assumption-register.md) and adjustable in the dashboard:

`EV = p(churn) x save_rate x value - (offer_cost + contact_cost)`, `value = MonthlyCharges x margin x discounted remaining months`.

Save rates are assumptions, not estimates: the data contain no randomised campaign, so no causal uplift is claimed. The IBM sample describes a fictional US company; results demonstrate the method and must be re-estimated on real data. Money is in USD of the sample company.

## What is where

| Folder | Content |
|---|---|
| `src/telco_retention` | Data, models, decision engine, analysis, reporting and export (templates in `templates/`) |
| `configs` | All assumptions and settings |
| `app` | Streamlit dashboard |
| `data` | Raw data (immutable, checksummed), processed data, upload template |
| `artifacts/runs` | Versioned runs (models, tables, manifests); `artifacts/qa` verification evidence |
| `reports` | Executive brief (MD/DOCX/PDF), analysis report, presentation, figures, tables, `facts.json` |
| `notebooks` | Four executed narrative notebooks |
| `docs` | Business case, data, model card, playbook, pilot, governance, assumptions, literature, guides ([index](docs/README.md)) |
| `tests`, `scripts` | Automated tests and release QA |
