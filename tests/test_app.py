import pandas as pd
from streamlit.testing.v1 import AppTest
from telco_retention.common import ROOT, latest_run, read_json
from telco_retention.data import parse_upload
from telco_retention.modeling import score_frame

PAGES = ["Overview", "Campaign builder", "Scenarios & budget", "Model & data"]
KPIS = ["Expected net value", "ROI", "Customers contacted", "Precision among contacted", "High-risk/high-value coverage"]


def app(timeout=120):
    return AppTest.from_file(str(ROOT / "app/Home.py"), default_timeout=timeout).run()


def kpi(at, label):
    return next(m for m in at.metric if m.label == label)


def strip_text(at):
    return " ".join(m.value for m in at.markdown if "Assumptions" in m.value)


def test_default_view_matches_report():
    at = app()
    assert not at.exception
    assert [m.label for m in at.metric] == KPIS
    run = latest_run()
    strategy = read_json(run / "validation_decisions.json")["strategy_selection"]["strategy"]
    scenarios = read_json(run / "campaign_scenarios.json")
    assert scenarios[strategy]["scenario_id"] in strip_text(at)
    assert kpi(at, "Customers contacted").value == f"{scenarios[strategy]['selected_count']:,}"
    delta = scenarios[strategy]["expected_net_value"] - scenarios["risk"]["expected_net_value"]
    assert kpi(at, "Expected net value").delta.startswith(f"${delta:,.0f}" if delta >= 0 else f"-${abs(delta):,.0f}")


def test_budget_and_save_rate_change_kpis():
    at = app()
    before = kpi(at, "Customers contacted").value
    at.number_input(key="budget_demo").set_value(0).run()
    assert not at.exception and kpi(at, "Customers contacted").value == "0" and before != "0"
    at.number_input(key="budget_demo").set_value(3080).run()
    at.slider(key="save_rate").set_value(0).run()
    at.selectbox(key="offer_mode").select("ev").run()
    assert kpi(at, "Customers contacted").value == "0"


def test_all_pages_show_assumption_strip():
    at = app()
    for page in PAGES:
        at.radio(key="page").set_value(page).run()
        assert not at.exception, page
        assert "Assumptions" in strip_text(at), page


def test_unlabeled_upload_state_and_filters():
    at = app()
    frame, _ = parse_upload((ROOT / "data/examples/customers_unlabeled.csv").read_bytes())
    at.session_state["uploaded_scores"] = score_frame(frame)
    at.run()
    at.selectbox(key="source").select("Uploaded CSV").run()
    assert not at.exception
    assert kpi(at, "Precision among contacted").delta == "expected (no labels)"
    at.radio(key="page").set_value("Campaign builder").run()
    previous = [m.value for m in at.metric]
    at.text_input[0].set_value("nonexistent-id").run()
    assert previous == [m.value for m in at.metric]
    at.multiselect(key="eligible_segments").set_value([]).run()
    assert not at.exception and any("No customers" in item.value for item in at.info)


def test_segment_offer_mode_runs():
    at = app()
    at.selectbox(key="offer_mode").select("segment_offers").run()
    assert not at.exception
    at.selectbox(key="offer_mode").select("ev").run()
    assert not at.exception


def test_missing_artifact_message(monkeypatch):
    def unavailable():
        raise FileNotFoundError("test missing artifact")
    monkeypatch.setattr("telco_retention.common.latest_run", unavailable)
    at = app()
    assert not at.exception
    assert any("not ready" in e.value for e in at.error)


def test_incomplete_run_message(monkeypatch, tmp_path):
    monkeypatch.setattr("telco_retention.common.latest_run", lambda: tmp_path)
    at = app()
    assert not at.exception
    assert any("not ready" in e.value for e in at.error)


def test_campaign_controls_survive_navigation():
    at = app()
    at.radio(key="page").set_value("Campaign builder").run()
    at.number_input(key="budget_demo").set_value(1000).run()
    at.slider(key="save_rate").set_value(.35).run()
    at.number_input(key="tenure_new").set_value(1.1).run()
    at.multiselect(key="eligible_segments").set_value(["new", "loyal"]).run()
    expected = [m.value for m in at.metric]
    for page in ["Model & data", "Scenarios & budget", "Campaign builder"]:
        at.radio(key="page").set_value(page).run()
        assert not at.exception
    assert at.number_input(key="budget_demo").value == 1000
    assert at.slider(key="save_rate").value == .35
    assert at.number_input(key="tenure_new").value == 1.1
    assert at.multiselect(key="eligible_segments").value == ["new", "loyal"]
    assert [m.value for m in at.metric] == expected


def test_ui_defaults_come_from_bundle(monkeypatch):
    import joblib
    from copy import deepcopy
    import streamlit as st
    original = joblib.load

    def changed(path, *args, **kwargs):
        bundle = original(path, *args, **kwargs)
        if isinstance(bundle, dict) and "metadata" in bundle:
            bundle = deepcopy(bundle)
            cfg = bundle["metadata"]["config"]
            cfg["value"].update(margin=.45, base_horizon_months=6)
            offer = next(o for o in cfg["offers"] if o["offer_id"] == cfg["campaign"]["default_offer"])
            offer.update(offer_cost=35, contact_cost=4, save_rate=.35)
        return bundle
    st.cache_resource.clear()
    monkeypatch.setattr(joblib, "load", changed)
    try:
        at = app()
        assert not at.exception
        assert at.slider(key="margin").value == .45
        assert at.slider(key="save_rate").value == .35
        assert at.number_input(key="horizon").value == 6
        assert at.number_input(key="offer_cost").value == 35
        assert at.number_input(key="contact_cost").value == 4
        n = len(pd.read_csv(latest_run() / "scorecard.csv").query("split == 'test'"))
        share = read_json(latest_run() / "manifest.json")["config"]["campaign"]["budget_share"]
        assert at.number_input(key="budget_demo").value == int(share * n) * 39
    finally:
        st.cache_resource.clear()


def test_scenario_analysis_runs_and_flags_stale_results():
    # The full scenario analysis re-solves dozens of campaigns; allow for a loaded machine.
    at = app(timeout=400)
    at.radio(key="page").set_value("Scenarios & budget").run()
    at.button[0].click().run()
    assert not at.exception
    assert {"Break-even save rate (this list)", "Minimum viable save rate"} <= {m.label for m in at.metric}
    at.slider(key="save_rate").set_value(.35).run()
    assert any("Assumptions changed" in w.value for w in at.warning)
