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
