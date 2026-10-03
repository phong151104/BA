"""Local headless Chrome/Edge QA, used when in-app Browser is unavailable."""
import io
import json
import time
import zipfile
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from telco_retention.common import ROOT, write_json, latest_run, now

output = ROOT / "artifacts/qa"
output.mkdir(parents=True, exist_ok=True)
executables = [Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"), Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]
executable = next((p for p in executables if p.exists()), None)
if executable is None:
    raise RuntimeError("Cần Chrome hoặc Edge local để chạy browser QA")
result = {"browser": str(executable), "mode": "local headless fallback; no in-app browser connection", "run_id": latest_run().name, "checked_at_utc": now(), "checks": []}
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=str(executable), headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 1800}, device_scale_factor=1)
    page.goto("http://127.0.0.1:8501", wait_until="domcontentloaded")
    page.get_by_text("Đúng khách hàng. Đúng ngân sách.", exact=True).wait_for(timeout=60000)
    page.get_by_text("Danh sách hành động", exact=True).wait_for()
    page.locator('.js-plotly-plot .main-svg').first.wait_for(timeout=30000)
    page.wait_for_function("document.fonts.status === 'loaded'")
    page.screenshot(path=str(output / "dashboard-home.png"), full_page=True)
    assert page.locator('[data-testid="stMetric"]').count() == 5
    result["checks"].append("home: five KPIs and targeting table")
    page.get_by_text("Lập chiến dịch", exact=True).click()
    page.get_by_text("So sánh trên cùng ngân sách", exact=True).wait_for()
    budget_input = page.get_by_role("spinbutton", name="Ngân sách · ĐVTT")
    budget_input.fill("0")
    budget_input.press("Enter")
    expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("0")
    budget_input.fill("3080")
    budget_input.press("Enter")
    expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("140")
    result["checks"].append("budget 0 and restore update KPI correctly")
    page.screenshot(path=str(output / "dashboard-campaign.png"), full_page=True)
    with page.expect_download() as download_info:
        page.get_by_text("Xuất gói chiến dịch · CSV + giả định", exact=True).click()
    download = download_info.value
    download.save_as(str(output / "campaign-export.zip"))
    with zipfile.ZipFile(output / "campaign-export.zip") as archive:
        assert set(archive.namelist()) == {"targeting_all.csv", "selected_customers.csv", "scenario_and_summary.json"}
        summary = json.loads(archive.read("scenario_and_summary.json"))
        assert summary["cost"] <= summary["scenario"]["budget"]
    result["checks"].append("campaign ZIP downloaded and budget validated")
    budget_input.fill("1000")
    budget_input.press("Enter")
    expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("45")
    page.get_by_text("Chất lượng mô hình", exact=True).first.click()
    page.get_by_text("Giải thích XGBoost · classifier gốc", exact=True).wait_for()
    page.locator('.js-plotly-plot .main-svg').first.wait_for(timeout=30000)
    page.screenshot(path=str(output / "dashboard-model.png"), full_page=True)
    result["checks"].append("model quality and SHAP visible")
    page.get_by_text("Lập chiến dịch", exact=True).click()
    expect(page.get_by_role("spinbutton", name="Ngân sách · ĐVTT")).to_have_value("1000.00")
    expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("45")
    result["checks"].append("custom budget and KPI survive navigation through model page")
    page.get_by_role("spinbutton", name="Ngân sách · ĐVTT").fill("3080")
    page.get_by_role("spinbutton", name="Ngân sách · ĐVTT").press("Enter")
    expect(page.locator('[data-testid="stMetricValue"]').first).to_have_text("140")
    page.get_by_text("Kịch bản và ngân sách", exact=True).click()
    page.get_by_text("Tính độ nhạy và đường ngân sách", exact=True).click()
    page.get_by_text("Cách đánh giá độ nhạy", exact=True).wait_for(timeout=180000)
    page.locator('.js-plotly-plot .main-svg').first.wait_for(timeout=30000)
    page.screenshot(path=str(output / "dashboard-sensitivity.png"), full_page=True)
    result["checks"].append("sensitivity and budget curves calculated interactively")
    page.get_by_text("Nhập dữ liệu", exact=True).click()
    page.locator('input[type="file"]').set_input_files(str(ROOT / "data/examples/customers_unlabeled.csv"))
    page.get_by_text("Đã chấm điểm 20 khách hàng.", exact=False).wait_for(timeout=30000)
    page.screenshot(path=str(output / "dashboard-upload.png"), full_page=True)
    result["checks"].append("valid CSV uploaded and scored in browser")
    page.get_by_text("CSV có ID trùng dữ liệu dự án.", exact=False).wait_for()
    result["checks"].append("known dataset ID overlap is disclosed on upload")
    contradictory = pd.read_csv(ROOT / "data/examples/customers_unlabeled.csv")
    contradictory.loc[0, ["PhoneService", "MultipleLines"]] = ["No", "Yes"]
    page.locator('input[type="file"]').set_input_files({"name": "contradictory.csv", "mimeType": "text/csv", "buffer": contradictory.to_csv(index=False).encode()})
    page.get_by_text("CSV chưa hợp lệ", exact=False).wait_for()
    result["checks"].append("contradictory service CSV rejected in browser")
    page.locator('input[type="file"]').set_input_files({"name": "invalid.csv", "mimeType": "text/csv", "buffer": b"customerID,tenure\na,-1\n"})
    page.get_by_text("CSV chưa hợp lệ", exact=False).wait_for()
    result["checks"].append("invalid CSV rejected with errors")
    page.get_by_text("Tổng quan", exact=True).click()
    page.get_by_text("Danh sách hành động", exact=True).wait_for()
    assert page.locator('[data-testid="stException"]').count() == 0
    result["status"] = "passed"
    browser.close()
write_json(output / "browser.json", result)
print(json.dumps(result, ensure_ascii=True, indent=2))
