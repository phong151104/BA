import shutil
from telco_retention.common import latest_run, read_json, write_json
from telco_retention import reporting


def test_generated_documents_use_run_assumptions_and_budget(tmp_path, monkeypatch):
    run = tmp_path / "test-run"
    run.mkdir()
    for path in latest_run().iterdir():
        if path.suffix in [".csv", ".json"]:
            shutil.copy2(path, run / path.name)
    scenarios = read_json(run / "campaign_scenarios.json")
    cfg = scenarios["ev"]["scenario"]["settings"]
    cfg.update(margin=.45, base_horizon=6, horizon_cap=18)
    cfg["offers"][1].update(offer_cost=35, contact_cost=4, save_rate=.35)
    scenarios["ev"]["scenario"]["budget"] = 9999
    write_json(run / "campaign_scenarios.json", scenarios)
    manifest = read_json(run / "manifest.json")
    manifest["selected_model"] = "random_forest"
    write_json(run / "manifest.json", manifest)
    monkeypatch.setattr(reporting, "ROOT", tmp_path)
    monkeypatch.setattr(reporting, "figures", lambda run: [])
    monkeypatch.setattr(reporting, "notebooks", lambda run: None)
    reporting.report(run)
    for name in ["reports/executive-brief.md", "reports/analysis-report.md", "docs/retention-playbook.md"]:
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert reporting.assumption_summary(cfg) in text
        assert "9,999" in text
    brief = (tmp_path / "reports/executive-brief.md").read_text(encoding="utf-8")
    assert "Random Forest" in brief
    assert len(brief.split()) <= 700
