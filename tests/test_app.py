import pandas as pd
from streamlit.testing.v1 import AppTest
from telco_retention.common import ROOT, latest_run, read_json
from telco_retention.data import parse_upload
from telco_retention.modeling import score_frame

PAGES = ["Decision", "Assumptions & sensitivity", "Model evidence"]
KPIS = ["Expected net value", "ROI", "Customers contacted", "Precision among contacted", "High-risk/high-value coverage"]
ASSUMPTIONS = "Assumptions & sensitivity"


def app(timeout=120):
    return AppTest.from_file(str(ROOT / "app/Home.py"), default_timeout=timeout).run()


def kpi(at, label):
    return next(m for m in at.metric if m.label == label)


def strip_text(at):
    return " ".join(m.value for m in at.markdown if "Assumptions" in m.value)


def go(at, page):
    at.radio(key="page").set_value(page).run()
    assert not at.exception, page
    return at


def test_default_view_matches_report():
    at = app()
    assert not at.exception
    assert [m.label for m in at.metric] == KPIS
    run = latest_run()
    strategy = read_json(run / "validation_decisions.json")["strategy_selection"]["strategy"]
    scenarios = read_json(run / "campaign_scenarios.json")
    # The scenario ID is kept out of the manager view but stays traceable under technical details.
    assert scenarios[strategy]["scenario_id"] not in strip_text(at)
    assert any(scenarios[strategy]["scenario_id"] in m.value for m in at.markdown)
    assert kpi(at, "Customers contacted").value == f"{scenarios[strategy]['selected_count']:,}"
    delta = scenarios[strategy]["expected_net_value"] - scenarios["risk"]["expected_net_value"]
    assert kpi(at, "Expected net value").delta.startswith(f"${delta:,.0f}" if delta >= 0 else f"-${abs(delta):,.0f}")


def test_budget_and_save_rate_change_kpis():
    at = app()
    before = kpi(at, "Customers contacted").value
    at.number_input(key="budget_demo").set_value(0).run()
    assert not at.exception and kpi(at, "Customers contacted").value == "0" and before != "0"
    at.number_input(key="budget_demo").set_value(3080).run()
    go(at, ASSUMPTIONS)
    at.slider(key="save_rate").set_value(0).run()
    at.selectbox(key="offer_mode").select("ev").run()
    go(at, "Decision")
    assert kpi(at, "Customers contacted").value == "0"


def test_strip_on_decision_pages_and_model_page_is_static():
    at = app()
    for page in PAGES[:2]:
        go(at, page)
        assert "Assumptions" in strip_text(at), page
    go(at, "Model evidence")
    assert "Assumptions" not in strip_text(at)
    assert not {m.label for m in at.metric} & set(KPIS[1:])
    assert {"ROC-AUC", "Calibration slope"} <= {m.label for m in at.metric}
    assert any("Points scorecard" in s.value for s in at.subheader)


def test_live_monte_carlo_reports_a_loss_probability():
    at = go(app(), ASSUMPTIONS)
    value = kpi(at, "Chance this list loses money").value
    assert value.endswith("%") and 0 <= float(value.rstrip("%")) <= 100


def test_unlabeled_upload_state_and_filters():
    at = app()
    frame, _ = parse_upload((ROOT / "data/examples/customers_unlabeled.csv").read_bytes())
    at.session_state["uploaded_scores"] = score_frame(frame)
    at.run()
    at.selectbox(key="source").select("Uploaded CSV").run()
    assert not at.exception
    assert kpi(at, "Precision among contacted").delta == "expected (no labels)"
    previous = [m.value for m in at.metric]
    at.text_input(key="search").set_value("nonexistent-id").run()
    assert previous == [m.value for m in at.metric]
    go(at, ASSUMPTIONS)
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
    at = go(app(), ASSUMPTIONS)
    at.number_input(key="budget_demo").set_value(1000).run()
    at.slider(key="save_rate").set_value(.35).run()
    at.number_input(key="tenure_new").set_value(1.1).run()
    at.multiselect(key="eligible_segments").set_value(["new", "loyal"]).run()
    expected = [m.value for m in at.metric]
    for page in ["Model evidence", "Decision", ASSUMPTIONS]:
        go(at, page)
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
        n = len(pd.read_csv(latest_run() / "scorecard.csv").query("split == 'test'"))
        share = read_json(latest_run() / "manifest.json")["config"]["campaign"]["budget_share"]
        assert at.number_input(key="budget_demo").value == int(share * n) * 39
        go(at, ASSUMPTIONS)
        assert at.slider(key="margin").value == .45
        assert at.slider(key="save_rate").value == .35
        assert at.number_input(key="horizon").value == 6
        assert at.number_input(key="offer_cost").value == 35
        assert at.number_input(key="contact_cost").value == 4
    finally:
        st.cache_resource.clear()


def test_scenario_analysis_runs_and_flags_stale_results():
    # The full scenario analysis re-solves dozens of campaigns; allow for a loaded machine.
    at = go(app(timeout=400), ASSUMPTIONS)
    next(b for b in at.button if b.label == "Run scenario analysis").click().run()
    assert not at.exception
    assert any("Pessimistic" in str(df.value.to_dict()) for df in at.dataframe)
    at.slider(key="save_rate").set_value(.35).run()
    assert any("Assumptions changed" in w.value for w in at.warning)
