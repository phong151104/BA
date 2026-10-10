"""Headless Chrome/Edge check of the running dashboard (start it first on http://127.0.0.1:8501)."""
import json
import zipfile
from pathlib import Path
import pandas as pd
from playwright.sync_api import expect, sync_playwright
from telco_retention.analysis import campaign_budget, run_strategy
from telco_retention.common import ROOT, latest_run, now, read_json, write_json

output = ROOT / "artifacts/qa"
output.mkdir(parents=True, exist_ok=True)
executables = [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]
executable = next((p for p in executables if p.exists()), None)
if executable is None:
    raise RuntimeError("Chrome or Edge is required for browser QA")

run = latest_run()
cfg = read_json(run / "manifest.json")["config"]
strategy = read_json(run / "validation_decisions.json")["strategy_selection"]["strategy"]
thresholds = read_json(run / "targeting_thresholds.json")
test = pd.read_csv(run / "scorecard.csv").query("split == 'test'")
default_budget = campaign_budget(len(test), cfg)
expected = {b: run_strategy(test, b, cfg, strategy, thresholds)[1]["selected_count"] for b in [default_budget, 1000.0]}
scenario_id = read_json(run / "campaign_scenarios.json")[strategy]["scenario_id"]
result = {"browser": str(executable), "run_id": run.name, "checked_at_utc": now(), "checks": []}


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


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(executable), headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1800})
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
    page.get_by_text("Which customers should get a retention offer?", exact=True).wait_for(timeout=90000)
    settle(page, tables=2, charts=1)
    assert page.locator('[data-testid="stMetric"]').count() == 5
    expect(contacted(page)).to_have_text(f"{expected[default_budget]:,}")
    assert scenario_id in page.locator(".strip").inner_text()
    page.screenshot(path=str(output / "dashboard-overview.png"), full_page=True)
    result["checks"].append("overview: five KPIs, report scenario ID, risk x value chart and segment table")

    page.get_by_text("Campaign builder", exact=True).click()
    page.get_by_text("Same budget, different rules", exact=True).wait_for()
    budget = page.get_by_role("spinbutton", name="Budget (USD)")
    budget.fill("0"); budget.press("Enter")
    expect(contacted(page)).to_have_text("0")
    budget.fill(f"{default_budget:.0f}"); budget.press("Enter")
    expect(contacted(page)).to_have_text(f"{expected[default_budget]:,}")
    result["checks"].append("budget 0 and restore update the KPIs")
    settle(page, tables=2)
    page.screenshot(path=str(output / "dashboard-campaign.png"), full_page=True)
    with page.expect_download() as download:
        page.get_by_text("Export campaign (CSV + assumptions)", exact=True).click()
    download.value.save_as(str(output / "campaign-export.zip"))
    with zipfile.ZipFile(output / "campaign-export.zip") as archive:
        assert set(archive.namelist()) == {"targeting_all.csv", "selected_customers.csv", "assumptions.json", "summary.json"}
        assumptions = json.loads(archive.read("assumptions.json"))
        assert assumptions["scenario_id"] == scenario_id and json.loads(archive.read("summary.json"))["cost"] <= assumptions["budget"]
    result["checks"].append("campaign ZIP contains list, assumptions and the report scenario ID")
    budget.fill("1000"); budget.press("Enter")
    expect(contacted(page)).to_have_text(f"{expected[1000.0]:,}")

    page.get_by_text("Model & data", exact=True).click()
    page.get_by_text("Challenger: XGBoost (not deployed) - SHAP attribution", exact=True).wait_for(timeout=60000)
    settle(page, charts=4)
    page.screenshot(path=str(output / "dashboard-model.png"), full_page=True)
    result["checks"].append("model page: deployed model metrics and separate challenger SHAP")
    page.get_by_text("Campaign builder", exact=True).click()
    expect(page.get_by_role("spinbutton", name="Budget (USD)")).to_have_value("1000.00")
    expect(contacted(page)).to_have_text(f"{expected[1000.0]:,}")
    result["checks"].append("custom budget survives navigation")
    page.get_by_role("spinbutton", name="Budget (USD)").fill(f"{default_budget:.0f}")
    page.get_by_role("spinbutton", name="Budget (USD)").press("Enter")
    expect(contacted(page)).to_have_text(f"{expected[default_budget]:,}")

    page.get_by_text("Scenarios & budget", exact=True).click()
    page.get_by_text("Run scenario analysis", exact=True).click()
    page.get_by_text("Break-even save rate (this list)", exact=True).wait_for(timeout=300000)
    settle(page, charts=4)
    page.screenshot(path=str(output / "dashboard-scenarios.png"), full_page=True)
    result["checks"].append("scenario page: break-even, tornado, scenarios, profit curve and grid computed")

    page.get_by_text("Model & data", exact=True).click()
    page.locator('input[type="file"]').set_input_files(str(ROOT / "data/examples/customers_unlabeled.csv"))
    page.get_by_text("Scored 20 customers", exact=False).wait_for(timeout=60000)
    page.get_by_text("Some IDs match the project's own data", exact=False).wait_for()
    settle(page)
    page.get_by_text("Score new customers", exact=True).scroll_into_view_if_needed()
    page.screenshot(path=str(output / "dashboard-upload.png"), full_page=True)
    result["checks"].append("valid CSV scored; ID overlap disclosed")
    contradictory = pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv")
    contradictory.loc[0, ["PhoneService", "MultipleLines"]] = ["No", "Yes"]
    page.locator('input[type="file"]').set_input_files({"name": "contradictory.csv", "mimeType": "text/csv", "buffer": contradictory.to_csv(index=False).encode()})
    page.get_by_text("The CSV is not valid", exact=False).wait_for()
    page.locator('input[type="file"]').set_input_files({"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"customerID,tenure\na,-1\n"})
    page.get_by_text("The CSV is not valid", exact=False).wait_for()
    result["checks"].append("contradictory and invalid CSVs rejected with errors")
    page.get_by_text("Overview", exact=True).click()
    page.get_by_text("Top 10 customers to call first", exact=True).wait_for()
    assert page.locator('[data-testid="stException"]').count() == 0
    result["status"] = "passed"
    browser.close()
write_json(output / "browser.json", result)
print(json.dumps(result, indent=2))
