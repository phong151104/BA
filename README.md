# Retention Lab - profit-aware telecom churn and retention targeting

Business Analytics capstone, Topic 7. **Business question:** given a limited retention budget, which customers should receive an offer when both churn risk and expected economic value are considered?

**Answer in one line:** rank customers by the expected net value of an offer (churn probability x save rate x customer value - cost), let an optimiser choose customers and offers within the budget, size the budget where the marginal return falls below a hurdle, and validate the assumed save rate with a randomised pilot. Start with the [executive brief](reports/executive-brief.md) ([PDF](reports/executive-brief.pdf)); the full write-up is the [final report](reports/final-report.pdf) and the talk is the [presentation](reports/presentation/retention-presentation.pptx) (speaker script in the notes and in [speaker-script.md](reports/presentation/speaker-script.md)).

## Quick start (Windows, Python 3.13)

Run from the project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

On macOS or Linux, install Python 3.13 (the package requires 3.13; for example `uv python install 3.13` or `pyenv install 3.13`), create the environment with `python3.13 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python` in every command (the lock file skips the Windows-only packages automatically).

Open http://127.0.0.1:8501. Data, the trained model and all results are already in the repository, so the dashboard runs offline; a network connection is only needed to install packages or download the data on a fresh run. On Windows, `run_dashboard.bat` does all of this with a double-click.

The dashboard also exists as one file that needs no installation: [reports/dashboard/retention-dashboard.html](reports/dashboard/retention-dashboard.html). Open it in any browser. It embeds the latest run's results and recomputes every campaign and scenario in the browser ([user guide](docs/user-guide.md#single-file-edition-html)).

## Reproduce everything

```powershell
.\.venv\Scripts\python.exe -m telco_retention run-all
```

`run-all` downloads the data (checksum-verified), prepares, trains, evaluates, simulates and then regenerates every table, figure, document, executed notebook, the executive brief (DOCX + PDF), the presentation on the HUST template (PPTX + PDF, with the speaker script), the final report (LaTeX + PDF) and the single-file HTML dashboard. PDF conversion of the brief and deck uses Microsoft Word and PowerPoint; without them (for example on macOS or Linux) `run-all` skips those PDFs and still writes the DOCX and PPTX (`--pdf skip` forces this, `--pdf require` fails instead). The final report needs `pdflatex` (TeX Live or MiKTeX); `--latex skip|require` works the same way. Each run is stored in `artifacts/runs/<run_id>` with its configuration, data checksum and code hashes; `artifacts/latest.json` points to the current run.

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

The four notebooks in `notebooks/` are committed with their outputs, so they can be read on GitHub or in any notebook viewer. To re-run one, open it in VS Code (Jupyter extension) and pick the `.venv` interpreter as the kernel, or install JupyterLab into the environment (`pip install jupyterlab`); `report` regenerates and re-executes all of them.

## Tests and release checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_notebooks.py
.\.venv\Scripts\python.exe scripts/verify_release.py
.\.venv\Scripts\python.exe scripts/browser_qa.py   # needs the dashboard running and Chrome or Edge
.\.venv\Scripts\python.exe scripts/html_dashboard_qa.py   # the single-file dashboard in Chrome or Edge, no server needed
```

`verify_release.py` compares the latest run with an earlier run made from the same code and configuration, so run `run-all` twice before it (then `prune --keep 2`). Without Word and PowerPoint the committed PDFs are kept and the check reports which run they came from.

Evidence of the last verification is in [docs/verification.md](docs/verification.md) and `artifacts/qa/`.

## Submission folder

`Group_1/` is the folder handed in (its README maps every course requirement to a file). It holds every required document under the names the course uses, the dashboard guide and screenshots, the scorecard and targeting tables, and a copy of this repository. Build it last, after the release checks and after committing the code, and then commit it:

```powershell
.\.venv\Scripts\python.exe scripts/build_submission.py           # needs Microsoft Word to convert the Markdown documents to PDF
.\.venv\Scripts\python.exe scripts/build_submission.py --check   # lists anything that changed in the repository since the build
```

## Assumptions

All business assumptions are visible parameters in [`configs/default.yaml`](configs/default.yaml), explained with sources in the [assumption register](docs/assumption-register.md) and adjustable in the dashboard:

`EV = p(churn) x save_rate x value - (offer_cost + contact_cost)`, `value = MonthlyCharges x margin x discounted remaining months`.

Save rates are assumptions, not estimates: the data contain no randomised campaign, so no causal uplift is claimed. The IBM sample describes a fictional US company; results demonstrate the method and must be re-estimated on real data. Money is in USD of the sample company.

## What is where

| Folder | Content |
|---|---|
| `src/telco_retention` | Data, models, decision engine, analysis, reporting and export (templates in `templates/`) |
| `configs` | All assumptions and settings |
| `app` | Streamlit dashboard (`run_dashboard.bat` starts it on Windows); its single-file HTML edition is built from `src/telco_retention/templates/dashboard` |
| `data` | Raw data (immutable, checksummed), processed data, upload template |
| `artifacts/runs` | Versioned runs (models, tables, manifests); `artifacts/qa` verification evidence |
| `reports` | Final report (PDF, LaTeX source in `reports/latex`), executive brief (MD/DOCX/PDF), analysis report, presentation (PPTX/PDF, speaker script), figures, tables, `facts.json` |
| `notebooks` | Four executed narrative notebooks |
| `docs` | Business case, data, model card, playbook, pilot, governance, assumptions, literature, guides ([index](docs/README.md)) |
| `tests`, `scripts` | Automated tests, release QA and the submission-folder builder |
| `Group_1` | The submission folder (built by `scripts/build_submission.py`) |
