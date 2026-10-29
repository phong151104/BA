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
from telco_retention.latex import LATEX_DIR, LATEX_DOCUMENTS, render_latex
from telco_retention.presentation import TALK_SECONDS

run = latest_run()
manifest = read_json(run / "manifest.json")
cfg = manifest["config"]
checks = {}

# 1. Completeness, with expected sizes derived from configuration.
required = ["model.joblib", "manifest.json", "validation_metrics.csv", "test_metrics.csv", "scorecard.csv", "strategy_comparison.csv", "economic_uncertainty.csv",
            "risk_value_matrix.csv", "threshold_business.csv", "break_even.json", "tornado.csv", "scenarios.csv", "sensitivity.csv", "budget_curve.csv",
            "validation_decisions.json", "recommended_campaign.json", "fairness.csv", "pilot_plan.json", "pilot_power.csv", "segment_offer_mix.csv",
            "offer_catalog.csv", "shap_global.csv", "calibration.csv", "gains_test.csv", "bootstrap_intervals.csv", "dataset_source.json", "customers.csv",
            "feature_ablation.csv", "odds_ratios.csv", "scorecard_points.csv", "scorecard_bands.csv", "scorecard_meta.json", "error_profiles.csv", "model_profit_check.csv",
            "customer_context.csv", "extended_join.json", "extended_source.json", "churn_reasons.csv", "churn_reasons_by_segment.csv", "churn_reasons_summary.json", "cltv_check.json", "stress_test.csv",
            "monte_carlo_summary.csv", "monte_carlo_drivers.csv", "monte_carlo_draws.csv", "target_profile.csv", "target_profile_summary.json", "recommended_offer_mix.csv"]
missing = [name for name in required if not (run / name).is_file()]
assert not missing, missing
grids = cfg["sensitivity"]
sensitivity_rows = 2 * (len(grids["save_rate"]) * len(grids["offer_cost_multiplier"]) + sum(len(grids[a]) for a in ["contact_cost", "value.margin", "value.base_horizon_months", "value.discount_rate_annual"]))
expected_sizes = {"random_campaigns.csv": cfg["random_campaign_iterations"], "sensitivity.csv": sensitivity_rows, "tornado.csv": len(cfg["assumption_register"]),
                  "budget_curve.csv": len(share_grid(cfg)) * 6, "scenarios.csv": len(grids["scenarios"]), "stress_test.csv": 2 * (1 + len(cfg["stress_test"]["target_churn"])),
                  "monte_carlo_draws.csv": cfg["monte_carlo"]["draws"], "monte_carlo_drivers.csv": len(cfg["assumption_register"])}
for name, size in expected_sizes.items():
    assert len(pd.read_csv(run / name)) == size, (name, size)
assert len(read_json(ROOT / "reports/figures/catalog.json")) == len(FIGURES)
assert sorted(p.stem for p in (ROOT / "reports/figures").glob("*.png")) == sorted(FIGURES), "reports/figures holds figures outside the registry"
checks["artifacts"] = {"required": len(required), "sizes": expected_sizes}

# Pilot is sized from the recommended list actually contacted, and tests that list's break-even.
pilot, reco = read_json(run / "pilot_plan.json"), read_json(run / "recommended_campaign.json")
n_test = manifest["split_counts"]["test"]
assert pilot["list_size_per_wave"] == round(reco["selected_count"] / n_test * cfg["pilot"]["base_population"]), (pilot["list_size_per_wave"], reco["selected_count"])
# The pilot measures the list's mix save rate, so its go line is the list's break-even on that scale.
assert abs(pilot["break_even_save_rate"] - reco["break_even"]["break_even_mix_save_rate"]) < 1e-12
assert abs(pilot["assumed_save_rate"] - reco["break_even"]["mix_save_rate"]) < 1e-12
checks["pilot"] = {k: pilot[k] for k in ["list_size_per_wave", "arm_size_per_wave", "break_even_save_rate"]}

# The second source joins only when every customer and every shared field matches; its fields never reach the model.
join = read_json(run / "extended_join.json")
assert join["accepted"] and join["matched"] == sum(manifest["split_counts"].values()), join
assert not {"churn_reason", "churn_category", "cltv"} & set(manifest["feature_columns"])
checks["extended_join"] = {"matched": join["matched"], "field_agreement": join["field_agreement"]}

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
    render_latex(build_facts(run), Path(tmp))
    drift += [f"{LATEX_DIR}/{src}" for src, _ in LATEX_DOCUMENTS.values() if not same_text(Path(tmp) / LATEX_DIR / src, ROOT / LATEX_DIR / src)]
assert not drift, f"Generated documents differ from templates (edited by hand or stale): {drift}"
checks["documents"] = {"rendered": len(DOCUMENTS) + len(LATEX_DOCUMENTS), "drift": drift}

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
assert deliverables["slides_with_notes"] == deliverables["slides"] and not deliverables["deck_lint"], deliverables["deck_lint"]
assert deliverables["talk_seconds"] == TALK_SECONDS, deliverables["talk_seconds"]
if deliverables.get("pdf_status") == "current":
    assert deliverables["deck_pdf_pages"] == deliverables["slides"], (deliverables["deck_pdf_pages"], deliverables["slides"])
assert deliverables.get("report_pages") and (ROOT / LATEX_DOCUMENTS["latex/report.tex.j2"][1]).exists(), "Final report PDF missing: run export with pdflatex installed"
checks["deliverables"] = {k: deliverables.get(k) for k in ["brief_words", "brief_pages", "slides", "slides_with_notes", "talk_seconds", "speaker_seconds", "deck_pdf_pages",
                                                         "pdf_status", "pdf_run_id", "report_pages", "latex_status", "latex_run_id"]}
if deliverables.get("pdf_status") != "current":
    # Without Word/PowerPoint the PDFs cannot be rebuilt; the committed ones are kept and reported.
    print(f"NOTE PDFs were not rebuilt here ({deliverables.get('pdf_status')}); they come from run {deliverables.get('pdf_run_id')}")
if deliverables.get("latex_status") != "current":
    print(f"NOTE the final report PDF was not rebuilt here ({deliverables.get('latex_status')}); it comes from run {deliverables.get('latex_run_id')}")

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
for name in ["monte_carlo_summary.csv", "stress_test.csv", "scorecard_points.csv", "model_profit_check.csv"]:
    ma, mb = pd.read_csv(other / name), pd.read_csv(run / name)
    np.testing.assert_allclose(ma.select_dtypes("number"), mb.select_dtypes("number"), rtol=1e-7, atol=1e-6, err_msg=name)
checks["reproducibility"] = {"compared_with": other.name, "current": run.name, "metrics_atol": 1e-10, "selected_customers_and_offers_equal": True, "scenario_ids_equal": True,
                             "monte_carlo_stress_scorecard_equal": True}

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
