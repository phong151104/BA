"""Verify reproducibility, documents and warmed UI timings against real artifacts."""
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote
import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest
from telco_retention.common import ROOT, latest_run, read_json, write_json, digest

run = latest_run()
required = ["model.joblib", "manifest.json", "validation_metrics.csv", "test_metrics.csv", "scorecard.csv", "targeting_ev.csv", "strategy_comparison.csv", "sensitivity.csv", "budget_curve.csv", "fairness.csv", "segment_policy.json", "validation_policy_search.csv", "shap_global.csv", "shap_local.csv", "calibration.csv", "bootstrap_intervals.csv", "dataset_source.json", "dataset_metadata.json", "customers.csv"]
assert all((run / name).is_file() for name in required)
assert len(pd.read_csv(run / "validation_policy_search.csv")) == 27
assert len(pd.read_csv(run / "random_campaigns.csv")) == 100
assert len(pd.read_csv(run / "sensitivity.csv")) == 74
assert len(pd.read_csv(run / "budget_curve.csv")) == 84
assert len(read_json(ROOT / "reports/figures/catalog.json")) == 14
assert len((ROOT / "reports/executive-brief.md").read_text(encoding="utf-8").split()) <= 700
assert read_json(ROOT / "reports/report-manifest.json")["run_id"] == run.name
manifest = read_json(run / "manifest.json")
assert all(digest((ROOT / p).read_bytes()) == expected for p, expected in manifest["code_sha256"].items()), "Source changed since training: run pipeline again"

broken = []
for path in [ROOT / "README.md", *(ROOT / "docs").glob("*.md"), *(ROOT / "reports").glob("*.md")]:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)", text):
        if target.startswith(("http:", "https:", "#")):
            continue
        local = unquote(target.split("#")[0])
        if not (path.parent / local).exists():
            broken.append({"file": str(path.relative_to(ROOT)), "link": target})
assert not broken, broken

runs = sorted((ROOT / "artifacts/runs").iterdir())
previous = [p for p in runs if p != run and (p / "test_metrics.csv").exists() and (p / "targeting_ev.csv").exists()]
comparison = None
if previous:
    old = previous[0]
    a, b = pd.read_csv(old / "test_metrics.csv"), pd.read_csv(run / "test_metrics.csv")
    np.testing.assert_allclose(a.select_dtypes("number"), b.select_dtypes("number"), rtol=1e-10, atol=1e-12)
    ta, tb = pd.read_csv(old / "targeting_ev.csv"), pd.read_csv(run / "targeting_ev.csv")
    assert ta.loc[ta.selected, "customer_id"].tolist() == tb.loc[tb.selected, "customer_id"].tolist()
    comparison = {"previous": old.name, "current": run.name, "metrics_equal_atol": 1e-12, "selected_ids_equal": True}

app = AppTest.from_file(str(ROOT / "app/Home.py"), default_timeout=60).run()
assert not app.exception
timings = []
for budget in [3080., 3000., 2900., 2800., 2700.]:
    start = time.perf_counter()
    app.number_input[0].set_value(budget).run()
    assert not app.exception
    timings.append(time.perf_counter() - start)
assert np.max(timings) < 2.0, timings
write_json(ROOT / "artifacts/qa/release.json", {"status": "passed", "python": sys.version, "environment": sys.prefix, "run_id": run.name, "required_artifact_count": len(required), "broken_links": broken, "reproducibility": comparison, "warmed_app_seconds": timings, "mean_seconds": float(np.mean(timings)), "max_seconds": float(np.max(timings))})
print("PASS release validation", run.name, "UI seconds", timings)
