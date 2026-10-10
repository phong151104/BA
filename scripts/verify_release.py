"""Release checks against real artifacts: completeness, traceability, reproducibility, documents and UI speed."""
import re
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import unquote
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
from telco_retention.common import ROOT, digest, latest_run, read_json, write_json
from telco_retention.analysis import share_grid
from telco_retention.facts import build_facts
from telco_retention.figures import FIGURES
from telco_retention.templating import DOCUMENTS, render_documents

run = latest_run()
manifest = read_json(run / "manifest.json")
cfg = manifest["config"]
checks = {}

# 1. Completeness, with expected sizes derived from configuration.
required = ["model.joblib", "manifest.json", "validation_metrics.csv", "test_metrics.csv", "scorecard.csv", "strategy_comparison.csv", "economic_uncertainty.csv",
            "risk_value_matrix.csv", "threshold_business.csv", "break_even.json", "tornado.csv", "scenarios.csv", "sensitivity.csv", "budget_curve.csv",
            "validation_decisions.json", "recommended_campaign.json", "fairness.csv", "pilot_plan.json", "pilot_power.csv", "segment_offer_mix.csv",
            "offer_catalog.csv", "shap_global.csv", "calibration.csv", "gains_test.csv", "bootstrap_intervals.csv", "dataset_source.json", "customers.csv"]
missing = [name for name in required if not (run / name).is_file()]
assert not missing, missing
grids = cfg["sensitivity"]
sensitivity_rows = 2 * (len(grids["save_rate"]) * len(grids["offer_cost_multiplier"]) + sum(len(grids[a]) for a in ["contact_cost", "value.margin", "value.base_horizon_months", "value.discount_rate_annual"]))
expected_sizes = {"random_campaigns.csv": cfg["random_campaign_iterations"], "sensitivity.csv": sensitivity_rows, "tornado.csv": len(cfg["assumption_register"]),
                  "budget_curve.csv": len(share_grid(cfg)) * 6, "scenarios.csv": len(grids["scenarios"])}
for name, size in expected_sizes.items():
    assert len(pd.read_csv(run / name)) == size, (name, size)
assert len(read_json(ROOT / "reports/figures/catalog.json")) == len(FIGURES)
assert sorted(p.stem for p in (ROOT / "reports/figures").glob("*.png")) == sorted(FIGURES), "reports/figures holds figures outside the registry"
checks["artifacts"] = {"required": len(required), "sizes": expected_sizes}

# Pilot is sized from the recommended list actually contacted, and tests that list's break-even.
pilot, reco = read_json(run / "pilot_plan.json"), read_json(run / "recommended_campaign.json")
n_test = manifest["split_counts"]["test"]
assert pilot["list_size_per_wave"] == round(reco["selected_count"] / n_test * cfg["pilot"]["base_population"]), (pilot["list_size_per_wave"], reco["selected_count"])
assert abs(pilot["break_even_save_rate"] - reco["break_even"]["break_even_default_save_rate"]) < 1e-12
checks["pilot"] = {k: pilot[k] for k in ["list_size_per_wave", "arm_size_per_wave", "break_even_save_rate"]}

# 2. Code and report traceability.
def same_text(a, b):
    """Byte-identical apart from line endings, so a checkout on any platform compares equal."""
    return a.read_bytes().replace(b"\r\n", b"\n") == b.read_bytes().replace(b"\r\n", b"\n")


# Older runs stored Windows-style keys; read both.
assert all(digest((ROOT / p.replace("\\", "/")).read_bytes()) == h for p, h in manifest["code_sha256"].items()), "Source changed since training: run the pipeline again"
report_manifest = read_json(ROOT / "reports/report-manifest.json")
assert report_manifest["run_id"] == run.name and read_json(ROOT / "reports/facts.json")["run"]["id"] == run.name
with tempfile.TemporaryDirectory() as tmp:
    render_documents(build_facts(run), Path(tmp))
    drift = [out for out in DOCUMENTS.values() if not same_text(Path(tmp) / out, ROOT / out)]
assert not drift, f"Generated documents differ from templates (edited by hand or stale): {drift}"
checks["documents"] = {"rendered": len(DOCUMENTS), "drift": drift}

broken = []
for path in [ROOT / "README.md", ROOT / "CHANGELOG.md", *(ROOT / "docs").glob("*.md"), *(ROOT / "reports").glob("*.md"), *(ROOT / "reports/presentation").glob("*.md")]:
    for target in re.findall(r"\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
        if target.startswith(("http:", "https:", "#", "mailto:")):
            continue
        if not (path.parent / unquote(target.split("#")[0])).exists():
            broken.append({"file": str(path.relative_to(ROOT)), "link": target})
assert not broken, broken
checks["links"] = "no broken relative links"

# 3. Submission files.
deliverables = read_json(ROOT / "reports/deliverables-manifest.json")
assert deliverables["run_id"] == run.name
assert deliverables["brief_pages"] <= 2, deliverables
assert 12 <= deliverables["slides"] <= 15 and deliverables["slides_with_notes"] == deliverables["slides"] and not deliverables["deck_lint"]
checks["deliverables"] = {k: deliverables.get(k) for k in ["brief_words", "brief_pages", "slides", "slides_with_notes", "deck_pdf_pages", "pdf_status", "pdf_run_id"]}
if deliverables.get("pdf_status") != "current":
    # Without Word/PowerPoint the PDFs cannot be rebuilt; the committed ones are kept and reported.
    print(f"NOTE PDFs were not rebuilt here ({deliverables.get('pdf_status')}); they come from run {deliverables.get('pdf_run_id')}")

# 4. Reproducibility: the other kept run must reproduce metrics and decisions.
others = [p for p in sorted((ROOT / "artifacts/runs").iterdir()) if p != run and (p / "simulation_manifest.json").exists()
          and read_json(p / "manifest.json")["config"] == cfg and read_json(p / "manifest.json")["code_sha256"] == manifest["code_sha256"]]
assert others, "No second run with the same code and configuration to compare"
other = others[-1]
a, b = pd.read_csv(other / "test_metrics.csv"), pd.read_csv(run / "test_metrics.csv")
np.testing.assert_allclose(a.select_dtypes("number"), b.select_dtypes("number"), rtol=1e-9, atol=1e-10)
for strategy in ["ev", "segment_offers"]:
    ta, tb = pd.read_csv(other / f"targeting_{strategy}.csv"), pd.read_csv(run / f"targeting_{strategy}.csv")
    assert ta.loc[ta.selected, ["customer_id", "offer_id"]].values.tolist() == tb.loc[tb.selected, ["customer_id", "offer_id"]].values.tolist()
sa, sb = read_json(other / "campaign_scenarios.json"), read_json(run / "campaign_scenarios.json")
assert {k: v["scenario_id"] for k, v in sa.items()} == {k: v["scenario_id"] for k, v in sb.items()}
checks["reproducibility"] = {"compared_with": other.name, "current": run.name, "metrics_atol": 1e-10, "selected_customers_and_offers_equal": True, "scenario_ids_equal": True}

# 5. Warmed dashboard response time.
app = AppTest.from_file(str(ROOT / "app/Home.py"), default_timeout=120).run()
assert not app.exception
base_budget = app.number_input(key="budget_demo").value
timings = []
for budget in [base_budget, base_budget - 100, base_budget - 200, base_budget - 300, base_budget]:
    start = time.perf_counter()
    app.number_input(key="budget_demo").set_value(budget).run()
    assert not app.exception
    timings.append(time.perf_counter() - start)
assert np.max(timings) < 5.0, timings
checks["ui_seconds"] = {"warmed": timings, "max": float(np.max(timings))}

write_json(ROOT / "artifacts/qa/release.json", {"status": "passed", "python": sys.version.split()[0], "run_id": run.name, **checks})
print("PASS release validation", run.name, checks["deliverables"], "UI max", round(float(np.max(timings)), 2))
