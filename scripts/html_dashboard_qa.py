"""Headless Chrome/Edge check of the single-file HTML dashboard (no server needed): every page renders without script
errors, the KPIs equal the Python engine's, controls recompute, the scenario analysis runs and an upload is scored."""
import json
import shutil
import sys
from pathlib import Path
import pandas as pd
from playwright.sync_api import sync_playwright
from telco_retention.analysis import campaign_budget, run_strategy
from telco_retention.common import ROOT, latest_run, now, read_json, write_json
from telco_retention.html_dashboard import HTML_DASHBOARD

page_file = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / HTML_DASHBOARD
output = ROOT / "artifacts/qa"
candidates = [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
              Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
candidates += [Path(p) for p in [shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chrome")] if p]
executable = next((p for p in candidates if p.exists()), None)
if executable is None:
    raise RuntimeError("Chrome, Chromium or Edge is required for the HTML dashboard check")

run = latest_run()
cfg = read_json(run / "manifest.json")["config"]
strategy = read_json(run / "validation_decisions.json")["strategy_selection"]["strategy"]
thresholds = read_json(run / "targeting_thresholds.json")
test = pd.read_csv(run / "scorecard.csv").query("split == 'test'")
budget = campaign_budget(len(test), cfg)
expected = {b: run_strategy(test, b, cfg, strategy, thresholds)[1] for b in [budget, 1000.0]}
usd = lambda x: f"-${abs(x):,.0f}" if x < 0 else f"${x:,.0f}"  # noqa: E731
result = {"browser": executable.name, "run_id": run.name, "file": str(page_file.relative_to(ROOT)) if page_file.is_relative_to(ROOT) else str(page_file),
          "checked_at_utc": now(), "checks": []}


def card(page, label):
    return page.locator(".metric").filter(has_text=label).locator(".value").first.inner_text()


def check(name, ok, detail=""):
    result["checks"].append({"check": name, "passed": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name, detail, flush=True)
    assert ok, (name, detail)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(executable), headless=True)
    page = browser.new_page(viewport={"width": 1500, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(page_file.resolve().as_uri())
    page.wait_for_selector(".metric", timeout=60000)
    page.wait_for_selector("#riskValue .main-svg", timeout=60000)
    s = expected[budget]
    check("Decision KPIs equal the Python engine", card(page, "Customers contacted") == f"{s['selected_count']:,}" and card(page, "Expected net value") == usd(s["expected_net_value"]),
          f"{card(page, 'Customers contacted')} / {card(page, 'Expected net value')}")
    page.screenshot(path=str(output / "html-dashboard-decision.png"), full_page=False)
    page.locator("#compare summary").click()
    page.wait_for_selector("#compareBody table")
    check("Rule comparison lists six rules", page.locator("#compareBody tbody tr").count() == 6)
    page.fill("#f_budget_demo", "1000")
    page.locator("#f_budget_demo").dispatch_event("change")
    page.wait_for_function(f"document.querySelector('.metric .value') && [...document.querySelectorAll('.metric')].some(m => m.innerText.includes('Customers contacted') && m.innerText.includes('{expected[1000.0]['selected_count']:,}'))", timeout=30000)
    check("Budget change recomputes the list", card(page, "Customers contacted") == f"{expected[1000.0]['selected_count']:,}", card(page, "Customers contacted"))
    page.fill("#f_budget_demo", str(budget))
    page.locator("#f_budget_demo").dispatch_event("change")
    page.locator("#sidebar button", has_text="Assumptions & sensitivity").click()
    page.wait_for_selector("#mc .main-svg", timeout=60000)
    page.click("#runScenarios")
    page.wait_for_selector("#grid .main-svg", timeout=180000)
    check("Scenario analysis draws tornado, profit curve and grid", all(page.locator(f"#{i} .main-svg").count() for i in ["tornado", "curve", "marginal", "grid"]))
    page.screenshot(path=str(output / "html-dashboard-assumptions.png"), full_page=False)
    page.locator("#sidebar button", has_text="Model evidence").click()
    for tab in ["Performance", "Drivers and scorecard", "Errors and money check", "Data and new customers"]:
        page.locator(".tabs button", has_text=tab).click()
        page.wait_for_selector("#tab table, #tab .main-svg", timeout=60000)
    check("Model evidence tabs render", True)
    page.locator(".tabs button", has_text="Performance").click()
    page.wait_for_selector("#calibration .main-svg")
    page.screenshot(path=str(output / "html-dashboard-model.png"), full_page=False)
    page.locator(".tabs button", has_text="Data and new customers").click()
    page.set_input_files("#upload", str(ROOT / "data/examples/customers_unlabeled.csv"))
    page.wait_for_selector("#uploadResult .box.ok", timeout=30000)
    rows = page.locator("#uploadResult tbody tr").count()
    check("Template upload is scored", rows == len(pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv")), f"{rows} rows")
    page.select_option("#source", "upload")
    page.locator("#sidebar button", has_text="Decision").click()
    page.wait_for_selector(".metric")
    check("Uploaded customers drive the Decision page", "expected (no labels)" in page.locator(".metric").filter(has_text="Precision among contacted").inner_text())
    check("No script errors", not errors, "; ".join(errors[:3]))
    browser.close()

write_json(output / "html-dashboard.json", {**result, "status": "passed"})
print("PASS HTML dashboard", len(result["checks"]), "checks")
