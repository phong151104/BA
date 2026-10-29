import json
import re
import shutil
import subprocess
import pandas as pd
import pytest
from telco_retention.analysis import break_even, campaign_budget, run_strategy, strategy_offers
from telco_retention.business import offer_options, value_customers
from telco_retention.common import latest_run, read_json
from telco_retention.data import SCHEMA
from telco_retention.html_dashboard import FOLDER, build_html_dashboard, dashboard_data

# Runs the browser engine under Node on the embedded data: the same campaigns, scores and analyses as the Python checks below.
HARNESS = r"""
const E = require(process.argv[2]), fs = require("fs");
const D = JSON.parse(fs.readFileSync(process.argv[3], "utf8")), records = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const cs = E.rows(D.customers), cfg = D.config, th = D.thresholds, out = { campaigns: {} };
const base = E.campaignBudget(cs.length, cfg);
for (const b of [base, D.budget_recommendation.recommended_budget, 1000]) for (const s of E.COMPARED) {
  const r = E.runStrategy(cs, b, cfg, s, th, true);
  out.campaigns[s + "|" + b] = { stats: r.stats, rows: r.table.map((x) => [x.customer_id, x.offer_id, x.selected, x.selection_reason, x.decision_detail]) };
}
const target = E.runStrategy(cs, base, cfg, D.recommended_strategy, th).table;
out.break_even = E.breakEven(target, cfg, E.offerOptions(E.valueCustomers(cs, cfg), E.strategyOffers(cfg, D.recommended_strategy)));
out.tornado = E.tornado(cs, base, cfg, D.recommended_strategy, th);
out.scenarios = E.scenarioTable(cs, base, cfg, D.recommended_strategy, th);
out.scores = E.score(records, D.model).map((r) => [r.customer_id, r.churn_probability]);
const changed = E.applyOverrides(cfg, { save_rate: 0.1, "value.margin": 0.25 });
out.frozen = [E.fixedCampaign(cs, target, base, changed, E.strategyOffers(changed, D.recommended_strategy), th).stats.expected_net_value,
  E.repriceFrozen(target, cfg, { save_rate: [0.1], "value.margin": [0.25] })[0]];
const bad = "customerID,tenure\nA,1\n";
const template = D.template_csv, broken = template.replace(/Month-to-month/, "Monthly");
out.uploads = [E.validateUpload(bad, D.model).errors, E.validateUpload(broken, D.model).errors.length, E.validateUpload(template, D.model).errors.length];
process.stdout.write(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def run():
    return latest_run()


def test_dashboard_is_one_self_contained_file(run, tmp_path):
    page = build_html_dashboard(run, tmp_path / "dashboard.html").read_text(encoding="utf-8")
    assert f"for run {run.name}." in page.splitlines()[1]
    assert not re.search(r"/\*@[A-Z]+@\*/", page) and "<!--HEADER-->" not in page
    assert not re.search(r"<script[^>]+src=|<link[^>]+href=\"http", page)  # no network needed to open it
    data = json.loads(re.search(r"const DATA = (\{.*?\});</script>", page, re.S).group(1))
    assert data["run_id"] == run.name and len(data["customers"]["customer_id"]) == read_json(run / "manifest.json")["split_counts"]["test"]
    assert data["model"]["linear"]["terms"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is needed to run the browser engine outside a browser")
def test_browser_engine_matches_python(run, tmp_path):
    data = dashboard_data(run)
    raw = pd.read_csv(run / "customers.csv", dtype=str, keep_default_na=False).query("split == 'test'")
    (tmp_path / "data.json").write_text(json.dumps(data), encoding="utf-8")
    (tmp_path / "records.json").write_text(json.dumps(raw[[c for c in SCHEMA if c in raw]].to_dict("records")), encoding="utf-8")
    (tmp_path / "harness.js").write_text(HARNESS, encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(tmp_path / "harness.js"), str(FOLDER / "engine.js"), str(tmp_path / "data.json"), str(tmp_path / "records.json")],
                                    capture_output=True, text=True, encoding="utf-8", check=True).stdout)
    cfg, thresholds = read_json(run / "manifest.json")["config"], read_json(run / "targeting_thresholds.json")
    test = pd.read_csv(run / "scorecard.csv", dtype={"SeniorCitizen": str}).query("split == 'test'")
    for key, js in out["campaigns"].items():
        strategy, budget = key.split("|")
        table, stats = run_strategy(test, float(budget), cfg, strategy, thresholds)
        # Same list, offers, reasons and explanations for every customer, and the same KPIs.
        assert table[["customer_id", "offer_id", "selected", "selection_reason", "decision_detail"]].values.tolist() == js["rows"], key
        for k in ["selected_count", "cost", "expected_net_value", "expected_saved", "roi", "precision_contacted", "high_risk_high_value_coverage"]:
            assert js["stats"][k] == pytest.approx(stats[k], rel=1e-9, abs=1e-9), (key, k)
    strategy = data["recommended_strategy"]
    budget = campaign_budget(len(test), cfg)
    target, _ = run_strategy(test, budget, cfg, strategy, thresholds)
    be = break_even(target, cfg, offer_options(value_customers(test, cfg), strategy_offers(cfg, strategy)))
    for k in ["break_even_default_save_rate", "break_even_mix_save_rate", "mix_save_rate", "minimum_viable_save_rate"]:
        assert out["break_even"][k] == pytest.approx(be[k], rel=1e-12), k
    tornado = pd.read_csv(run / "tornado.csv").set_index("parameter")
    for row in out["tornado"]:
        ref = tornado.loc[row["parameter"]]
        for k in ["base_net", "net_low_fixed", "net_high_fixed"]:
            assert row[k] == pytest.approx(ref[k], rel=1e-9), (row["parameter"], k)
        # The browser's exact dynamic programme never does worse than the integer programme (which can stop at its time limit).
        for k in ["net_low_retarget", "net_high_retarget"]:
            assert row[k] >= ref[k] - 1e-6 and row[k] == pytest.approx(ref[k], rel=1e-4), (row["parameter"], k)
    scenarios = pd.read_csv(run / "scenarios.csv").set_index("scenario")
    for row in out["scenarios"]:
        assert row["expected_net_value"] == pytest.approx(scenarios.loc[row["scenario"], "expected_net_value"], rel=1e-9)
        assert row["fixed_expected_net_value"] == pytest.approx(scenarios.loc[row["scenario"], "fixed_expected_net_value"], rel=1e-9)
    # The embedded model scores like the deployed pipeline; the vectorised repricing matches a frozen list's repricing.
    scores = dict(out["scores"])
    assert max(abs(scores[c] - p) for c, p in zip(test.customer_id, test.churn_probability)) < 1e-12
    assert out["frozen"][0] == pytest.approx(out["frozen"][1], rel=1e-12)
    missing, broken, clean = out["uploads"]
    assert any(e[2] == "Required column missing" for e in missing) and broken >= 1 and clean == 0
