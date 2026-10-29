"""Headless Chrome/Edge check of the running dashboard (start it first on http://127.0.0.1:8501, or pass its URL)."""
import json
import shutil
import sys
import zipfile
from pathlib import Path
import pandas as pd
from playwright.sync_api import expect, sync_playwright
from telco_retention.analysis import campaign_budget, run_strategy
from telco_retention.common import ROOT, latest_run, now, read_json, write_json

output = ROOT / "artifacts/qa"
output.mkdir(parents=True, exist_ok=True)
for old in output.glob("dashboard-*.png"):
    old.unlink()
candidates = [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
              Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
candidates += [Path(p) for p in [shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chrome")] if p]
executable = next((p for p in candidates if p.exists()), None)
if executable is None:
    raise RuntimeError("Chrome, Chromium or Edge is required for browser QA")

run = latest_run()
cfg = read_json(run / "manifest.json")["config"]
strategy = read_json(run / "validation_decisions.json")["strategy_selection"]["strategy"]
thresholds = read_json(run / "targeting_thresholds.json")
test = pd.read_csv(run / "scorecard.csv").query("split == 'test'")
default_budget = campaign_budget(len(test), cfg)
expected = {b: run_strategy(test, b, cfg, strategy, thresholds)[1]["selected_count"] for b in [default_budget, 1000.0]}
scenario_id = read_json(run / "campaign_scenarios.json")[strategy]["scenario_id"]
result = {"browser": executable.name, "run_id": run.name, "checked_at_utc": now(), "checks": []}


def contacted(page):
    return page.locator('[data-testid="stMetric"]').filter(has_text="Customers contacted").locator('[data-testid="stMetricValue"]')


def settle(page, tables=0, charts=0):
    """Wait until the app is idle and the expected tables/charts are drawn before a screenshot."""
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180000)
    if tables:
        page.locator('[data-testid="stDataFrame"]').nth(tables - 1).wait_for(timeout=60000)
    if charts:
        page.locator(".js-plotly-plot .main-svg").nth(charts - 1).wait_for(timeout=60000)
    page.wait_for_timeout(1500)


def set_budget(page, value):
    field = page.get_by_role("spinbutton", name="Budget (USD)")
    field.fill(f"{value:.0f}")
    field.press("Enter")
    # Wait for the rerun to finish so stale copies of the KPI cards are gone.
    page.wait_for_timeout(800)
    page.wait_for_function("!document.querySelector('[data-testid=\"stStatusWidget\"]')", timeout=180000)
    page.wait_for_timeout(500)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(executable), headless=True)
    # A tall window lets each screenshot hold the whole page (Streamlit scrolls inside its own container).
    page = browser.new_page(viewport={"width": 1440, "height": 4200})
    page.goto(sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8501", wait_until="domcontentloaded")
    page.get_by_text("Which customers should get a retention offer?", exact=True).wait_for(timeout=90000)
    settle(page, tables=2, charts=1)
    page.locator('[data-testid="stDataFrame"]').last.wait_for(timeout=60000)
    assert page.locator('[data-testid="stMetric"]').count() == 5
    expect(contacted(page)).to_have_text(f"{expected[default_budget]:,}")
    assert scenario_id not in page.locator(".strip").inner_text()
    page.screenshot(path=str(output / "dashboard-decision.png"), full_page=True)
    result["checks"].append("decision page: five KPIs, recommendation, who gets an offer, risk x value chart and action list")

    set_budget(page, 0)
    expect(contacted(page)).to_have_text("0")
    set_budget(page, default_budget)
    expect(contacted(page)).to_have_text(f"{expected[default_budget]:,}")
    result["checks"].append("budget 0 and restore update the KPIs")
    settle(page, tables=2)
    with page.expect_download() as download:
        page.get_by_text("Export campaign (CSV + assumptions)", exact=True).click()
    download.value.save_as(str(output / "campaign-export.zip"))
    with zipfile.ZipFile(output / "campaign-export.zip") as archive:
        assert set(archive.namelist()) == {"targeting_all.csv", "selected_customers.csv", "assumptions.json", "summary.json"}
        assumptions = json.loads(archive.read("assumptions.json"))
        assert assumptions["scenario_id"] == scenario_id and json.loads(archive.read("summary.json"))["cost"] <= assumptions["budget"]
    result["checks"].append("campaign ZIP contains the list, the assumptions and the report scenario ID")
    set_budget(page, 1000)
    expect(contacted(page)).to_have_text(f"{expected[1000.0]:,}")

    page.get_by_text("Assumptions & sensitivity", exact=True).click()
    page.get_by_text("Chance this list loses money", exact=True).wait_for(timeout=60000)
    expect(page.get_by_role("spinbutton", name="Budget (USD)")).to_have_value("1000.00")
    result["checks"].append("custom budget survives navigation; live loss probability shown")
    set_budget(page, default_budget)
    page.get_by_text("Run scenario analysis", exact=True).click()
    page.get_by_text("Download the full sensitivity table", exact=True).wait_for(timeout=300000)
    settle(page, tables=2, charts=6)
    page.screenshot(path=str(output / "dashboard-assumptions.png"), full_page=True)
    result["checks"].append("assumptions page: loss probability, tornado, scenarios, profit curve, marginal ROI, grid and stress test")

    page.get_by_text("Model evidence", exact=True).click()
    page.get_by_text("Can we trust the scores?", exact=True).wait_for(timeout=60000)
    settle(page, charts=2)
    page.screenshot(path=str(output / "dashboard-model.png"), full_page=True)
    page.get_by_role("tab", name="Drivers and scorecard").click()
    page.get_by_text("Points scorecard for the call centre", exact=True).wait_for()
    settle(page, tables=2)
    page.screenshot(path=str(output / "dashboard-scorecard.png"), full_page=True)
    result["checks"].append("model page: deployed model metrics, odds ratios, points scorecard and separate challenger SHAP")

    page.get_by_role("tab", name="Data and new customers").click()
    page.locator('input[type="file"]').set_input_files(str(ROOT / "data/examples/customers_unlabeled.csv"))
    page.get_by_text("Scored 20 customers", exact=False).wait_for(timeout=60000)
    assert page.get_by_text("Some IDs match the project's own data", exact=False).count() == 0
    settle(page)
    page.screenshot(path=str(output / "dashboard-upload.png"), full_page=True)
    known = pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv").head(3)
    known.loc[0, "customerID"] = pd.read_csv(ROOT / "data/processed/splits.csv").query("split == 'test'").customerID.iloc[0]
    page.locator('input[type="file"]').set_input_files({"name": "known.csv", "mimeType": "text/csv", "buffer": known.to_csv(index=False).encode()})
    page.get_by_text("Some IDs match the project's own data", exact=False).wait_for()
    result["checks"].append("valid CSV scored without warnings; a known ID is disclosed")
    contradictory = pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv")
    contradictory.loc[0, ["PhoneService", "MultipleLines"]] = ["No", "Yes"]
    page.locator('input[type="file"]').set_input_files({"name": "contradictory.csv", "mimeType": "text/csv", "buffer": contradictory.to_csv(index=False).encode()})
    page.get_by_text("The CSV is not valid", exact=False).wait_for()
    page.locator('input[type="file"]').set_input_files({"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"customerID,tenure\na,-1\n"})
    page.get_by_text("The CSV is not valid", exact=False).wait_for()
    result["checks"].append("contradictory and invalid CSVs rejected with errors")
    page.get_by_text("Decision", exact=True).click()
    page.get_by_text("Who gets an offer, and who does not", exact=True).wait_for()
    expect(contacted(page)).to_have_text(f"{expected[default_budget]:,}")
    assert page.locator('[data-testid="stException"]').count() == 0
    result["status"] = "passed"
    browser.close()
write_json(output / "browser.json", result)
print(json.dumps(result, indent=2))
