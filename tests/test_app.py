import json
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from telco_retention.common import ROOT
from telco_retention.data import parse_upload
from telco_retention.modeling import score_frame


def app():
    return AppTest.from_file(str(ROOT / "app/Home.py"), default_timeout=60).run()


def test_home_and_budget_changes():
    at = app()
    assert not at.exception
    assert len(at.metric) == 5
    before = at.metric[0].value
    at.number_input(key="budget_Demo · tập test giữ riêng").set_value(0).run()
    assert not at.exception and at.metric[0].value == "0" and before != "0"
    at.number_input(key="budget_Demo · tập test giữ riêng").set_value(3080).run()
    at.slider(key="save_rate").set_value(0).run()
    assert at.metric[0].value == "0"


def test_all_pages():
    at = app()
    for page in ["Lập chiến dịch", "Kịch bản và ngân sách", "Chất lượng mô hình", "Nhập dữ liệu", "Phương pháp và hướng dẫn", "Tổng quan"]:
        at.radio(key="page").set_value(page).run()
        assert not at.exception, page


def test_unlabeled_upload_state_and_filters():
    at = app()
    frame, _ = parse_upload((ROOT / "data/examples/customers_unlabeled.csv").read_bytes())
    at.session_state["uploaded_scores"] = score_frame(frame)
    at.run()
    at.selectbox(key="source").select("CSV đã nhập").run()
    assert not at.exception
    assert any("CSV không có nhãn" in item.value for item in at.info)
    previous = [m.value for m in at.metric]
    at.text_input[0].set_value("nonexistent-id").run()
    assert previous == [m.value for m in at.metric]
    at.multiselect[0].set_value([]).run()
    assert not at.exception and any("Không có khách hàng" in item.value for item in at.info)


def test_multi_offer_and_policy():
    at = app()
    policy_control = next(x for x in at.selectbox if x.label == "Chính sách ưu đãi")
    policy_control.select("Tối ưu nhiều ưu đãi").run()
    assert not at.exception
    policy_control = next(x for x in at.selectbox if x.label == "Chính sách ưu đãi")
    policy_control.select("Chính sách tenure đã khóa").run()
    assert not at.exception


def test_missing_artifact_message(monkeypatch):
    def unavailable():
        raise FileNotFoundError("test missing artifact")
    monkeypatch.setattr("telco_retention.common.latest_run", unavailable)
    at = app()
    assert not at.exception
    assert any("Chưa đủ kết quả" in e.value for e in at.error)


def test_incomplete_run_message(monkeypatch, tmp_path):
    monkeypatch.setattr("telco_retention.common.latest_run", lambda: tmp_path)
    at = app()
    assert not at.exception
    assert any("Chưa đủ kết quả" in e.value for e in at.error)


def test_campaign_controls_survive_navigation():
    at = app()
    at.number_input(key="budget_Demo · tập test giữ riêng").set_value(1000).run()
    at.slider(key="save_rate").set_value(.35).run()
    at.number_input(key="tenure_new").set_value(1.1).run()
    at.multiselect(key="eligible_segments").set_value(["new", "loyal"]).run()
    at.selectbox(key="offer_mode").select("Tối ưu nhiều ưu đãi").run()
    at.number_input(key="cost_light").set_value(7.).run()
    expected = [m.value for m in at.metric]
    for page in ["Chất lượng mô hình", "Nhập dữ liệu", "Phương pháp và hướng dẫn", "Lập chiến dịch"]:
        at.radio(key="page").set_value(page).run()
        assert not at.exception
    assert at.number_input(key="budget_Demo · tập test giữ riêng").value == 1000
    assert at.slider(key="save_rate").value == .35
    assert at.number_input(key="tenure_new").value == 1.1
    assert at.multiselect(key="eligible_segments").value == ["new", "loyal"]
    assert at.number_input(key="cost_light").value == 7.
    assert [m.value for m in at.metric] == expected
    at.selectbox(key="offer_mode").select("Một ưu đãi tiêu chuẩn").run()
    at.selectbox(key="offer_mode").select("Tối ưu nhiều ưu đãi").run()
    assert at.number_input(key="cost_light").value == 7.


def test_ui_defaults_come_from_bundle(monkeypatch):
    import joblib
    from copy import deepcopy
    original = joblib.load
    def changed(path, *args, **kwargs):
        bundle = original(path, *args, **kwargs)
        if isinstance(bundle, dict) and "metadata" in bundle:
            bundle = deepcopy(bundle)
            cfg = bundle["metadata"]["config"]
            cfg.update(margin=.45, base_horizon=6)
            cfg["offers"][1].update(offer_cost=35, contact_cost=4, save_rate=.35)
        return bundle
    import streamlit as st
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
        assert at.number_input(key="budget_Demo · tập test giữ riêng").value == 140 * 39
    finally:
        st.cache_resource.clear()


def test_sensitivity_ui_passes_active_offers_and_policy(monkeypatch):
    import pandas as pd
    import streamlit as st
    calls = []
    def fake_sensitivity(scores, budget, cfg, thresholds, offers, policy):
        calls.append((offers, policy))
        return pd.DataFrame([{"axis": "cost_save_rate", "parameter": .2, "cost_multiplier": 1,
                              "mode": mode, "expected_net_value": 1} for mode in ["fixed", "retarget"]])
    def fake_curves(*args):
        return pd.DataFrame({"budget": [0, 100], "expected_net_value": [0, 1], "strategy": ["active_policy"] * 2})
    monkeypatch.setattr("telco_retention.analysis.sensitivity", fake_sensitivity)
    monkeypatch.setattr("telco_retention.analysis.budget_curve", fake_curves)
    st.cache_data.clear()
    try:
        at = app()
        at.selectbox(key="offer_mode").select("Chính sách tenure đã khóa").run()
        at.radio(key="page").set_value("Kịch bản và ngân sách").run()
        at.button[0].click().run()
        assert not at.exception
        assert len(calls[-1][0]) == 3
        assert set(calls[-1][1]) == {"new", "developing", "loyal"}
        at.slider(key="save_rate").set_value(.35).run()
        assert any("Tham số đã thay đổi" in warning.value for warning in at.warning)
    finally:
        st.cache_data.clear()
