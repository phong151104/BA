from __future__ import annotations

import io
import json
import time
import zipfile
from copy import deepcopy
import joblib
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
from telco_retention.common import ROOT, config, latest_run, read_json, jsonable
from telco_retention.data import parse_upload, DataValidationError
from telco_retention.modeling import score_frame
from telco_retention.business import campaign
from telco_retention.analysis import default_budget, sensitivity, budget_curve, compare

st.set_page_config(page_title="Retention Lab · Telecom", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background:#f5f7fb;} .block-container {padding-top:4.5rem; max-width:1500px;}
h1,h2,h3 {color:#142c47;} [data-testid="stMetric"] {background:white;border:1px solid #e3e8ef;border-radius:14px;padding:18px;}
[data-testid="stSidebar"] {background:#edf2f8;} .eyebrow {font-size:12px;letter-spacing:2px;color:#477590;font-weight:700;}
.hero {background:linear-gradient(110deg,#12324c,#185d70);padding:25px 30px;border-radius:18px;margin-bottom:22px;color:white;}
.hero h2 {color:white;margin:0;} .hero p {color:#d3e7ed;margin:8px 0 0;}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def load_bundle(run_name):
    return joblib.load(ROOT / "artifacts/runs" / run_name / "model.joblib")


@st.cache_data
def csv_artifact(run_name, name):
    path = ROOT / "artifacts/runs" / run_name / name
    if not path.exists():
        st.error(f"Thiếu kết quả {name}. Hoàn tất pipeline run-all trước khi xem trang này.")
        st.stop()
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def calculate(scores, budget, settings, offers, strategy, policy, thresholds):
    return campaign(scores, budget, settings, offers, strategy, policy, thresholds)


@st.cache_data(show_spinner=False)
def scenario_views(scores, budget, settings, thresholds, offers, policy):
    return sensitivity(scores, budget, settings, thresholds, offers, policy), budget_curve(scores, settings, thresholds, offers, policy)


def control(key, default):
    # Native persistence keeps Python state and remounted browser widgets in sync.
    st.session_state.campaign_controls.setdefault(key, default)
    if key not in st.session_state:
        st.session_state[key] = default
    return {"key": key, "persist_state": "session"}


def metric_cards(stats):
    names = ["Khách hàng được chọn", "Chi phí · ĐVTT", "Giữ được kỳ vọng", "Giá trị ròng · ĐVTT", "ROI kỳ vọng"]
    vals = [f"{stats['selected_count']:,}", f"{stats['cost']:,.0f}", f"{stats['expected_saved']:,.1f}", f"{stats['expected_net_value']:,.1f}", "N/A" if stats["roi"] is None else f"{stats['roi']:.1%}"]
    for col, label, value in zip(st.columns(5), names, vals):
        col.metric(label, value)


def campaign_zip(target, stats):
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("targeting_all.csv", target.to_csv(index=False).encode("utf-8-sig"))
        archive.writestr("selected_customers.csv", target.loc[target.selected].to_csv(index=False).encode("utf-8-sig"))
        archive.writestr("scenario_and_summary.json", json.dumps(jsonable(stats), indent=2, ensure_ascii=False, allow_nan=False))
    return memory.getvalue()


st.sidebar.markdown("## ◈ Retention Lab")
st.sidebar.caption("BUSINESS ANALYTICS · CAPSTONE")
pages = ["Tổng quan", "Lập chiến dịch", "Kịch bản và ngân sách", "Chất lượng mô hình", "Nhập dữ liệu", "Phương pháp và hướng dẫn"]
page = st.sidebar.radio("Điều hướng", pages, key="page")
try:
    run = latest_run()
    if not (run / "simulation_manifest.json").exists():
        raise FileNotFoundError("Pipeline đang chạy hoặc chưa hoàn thành bước simulate")
    bundle = load_bundle(run.name)
    demo = csv_artifact(run.name, "scorecard.csv").query("split == 'test'").copy()
    thresholds = read_json(run / "targeting_thresholds.json")
except (FileNotFoundError, KeyError) as exc:
    st.error("Chưa đủ kết quả phân tích. Chạy `python -m telco_retention run-all` rồi mở lại ứng dụng.")
    st.caption(str(exc))
    st.stop()

if st.session_state.get("controls_run") != run.name:
    for key in st.session_state.get("campaign_controls", {}):
        st.session_state.pop(key, None)
    st.session_state.campaign_controls = {}
    st.session_state.controls_run = run.name
    st.session_state.pop("scenario_results", None)

source_names = ["Demo · tập test giữ riêng"]
if "uploaded_scores" in st.session_state:
    source_names.append("CSV đã nhập")
source = st.sidebar.selectbox("Nguồn khách hàng", source_names, key="source")
scores = demo if source == source_names[0] else st.session_state.uploaded_scores
st.sidebar.caption(f"{len(scores):,} khách hàng · {bundle['metadata']['selected_model']} calibrated")
st.sidebar.markdown("---")
st.sidebar.caption("Mọi giá trị giữ chân là mô phỏng theo giả định. Không phải lợi nhuận thực thu hoặc ước lượng tác động nhân quả.")

if page == "Nhập dữ liệu":
    st.title("Nhập khách hàng mới")
    st.write("Tải CSV cùng cấu trúc mẫu để chấm điểm bằng mô hình đã huấn luyện. Tối đa 10 MB / 50.000 dòng; UTF-8, phân cách phẩy.")
    st.download_button("Tải CSV mẫu không nhãn", (ROOT / "data/examples/customers_unlabeled.csv").read_bytes(), "customers_template.csv", "text/csv")
    uploaded = st.file_uploader("Chọn CSV khách hàng", type=["csv"])
    if uploaded is not None:
        try:
            frame, quality = parse_upload(uploaded.getvalue())
            with st.spinner("Đang kiểm tra và chấm điểm…"):
                predicted = score_frame(frame, bundle)
            st.session_state.uploaded_scores = predicted
            st.success(f"Đã chấm điểm {len(predicted):,} khách hàng. Chọn 'CSV đã nhập' ở thanh bên để lập chiến dịch.")
            if quality["ignored_columns"]:
                st.info("Cột không sử dụng: " + ", ".join(quality["ignored_columns"]))
            st.dataframe(predicted[["customer_id", "churn_probability", "risk_band", "prediction_origin"]], hide_index=True, width="stretch")
            if predicted.prediction_origin.str.contains("matches_").any():
                st.warning("CSV có ID trùng dữ liệu dự án. Xem prediction_origin; ID trùng train không phải kiểm định độc lập. So khớp ID không xác minh nội dung hay thời điểm quan sát.")
            st.download_button("Tải bảng điểm", predicted.to_csv(index=False).encode("utf-8-sig"), "scores.csv", "text/csv")
        except DataValidationError as exc:
            st.error("CSV chưa hợp lệ; chưa nhập dòng nào. Nguồn dữ liệu trước đó vẫn giữ nguyên.")
            st.dataframe(exc.errors, hide_index=True, width="stretch")
    st.info("Dữ liệu chỉ lưu trong phiên làm việc. Churn nếu có không được dùng làm đầu vào dự đoán. Bạn chịu trách nhiệm xác định khách hàng còn hoạt động và đủ điều kiện liên hệ.")
    st.stop()

if page == "Chất lượng mô hình":
    st.title("Chất lượng mô hình")
    st.caption("Các kết quả sau thuộc tập test của dự án, không phải metric của CSV đang nhập. Ngưỡng và mô hình được chọn trên validation.")
    st.dataframe(csv_artifact(run.name, "test_metrics.csv"), hide_index=True, width="stretch")
    a, b = st.columns(2)
    calibration = csv_artifact(run.name, "calibration.csv")
    fig = px.line(calibration, x="predicted", y="observed", color="model", markers=True, title="Calibration · tập test", labels={"predicted": "Xác suất dự đoán", "observed": "Tỷ lệ churn quan sát"})
    fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Lý tưởng", line={"dash": "dash", "color": "gray"})
    a.plotly_chart(fig, width="stretch")
    b.plotly_chart(px.line(csv_artifact(run.name, "pr_curve.csv"), x="recall", y="precision", title="Precision–Recall · tập test"), width="stretch")
    with st.expander("Validation, ROC, ngưỡng và khoảng bootstrap"):
        st.dataframe(csv_artifact(run.name, "validation_metrics.csv"), hide_index=True)
        st.plotly_chart(px.line(csv_artifact(run.name, "roc_curve.csv"), x="fpr", y="tpr", title="ROC · tập test"), width="stretch")
        st.dataframe(csv_artifact(run.name, "threshold_analysis.csv"), hide_index=True)
        st.dataframe(csv_artifact(run.name, "bootstrap_intervals.csv"), hide_index=True)
        st.dataframe(csv_artifact(run.name, "confusion_matrix.csv"), hide_index=True)
    st.subheader("Giải thích XGBoost · classifier gốc")
    st.caption("TreeSHAP trên validation, đơn vị log-odds. Không phân rã xác suất sau calibration và không chứng minh nguyên nhân churn.")
    shap = csv_artifact(run.name, "shap_global.csv").head(15).sort_values("mean_abs_shap")
    st.plotly_chart(px.bar(shap, x="mean_abs_shap", y="feature", orientation="h", title="Đóng góp đặc trưng trung bình |SHAP|"), width="stretch")
    local = csv_artifact(run.name, "shap_local.csv")
    customer = st.selectbox("Giải thích khách hàng mẫu", local.sort_values("raw_probability", ascending=False).customer_id.tolist())
    row = local.loc[local.customer_id.eq(customer)].iloc[0]
    values = row.drop(["customer_id", "base_value", "raw_probability"]).astype(float)
    idx = values.abs().nlargest(10).index
    st.plotly_chart(px.bar(pd.DataFrame({"feature": idx, "SHAP": values[idx].values}), x="SHAP", y="feature", orientation="h", title=f"{customer} · xác suất XGBoost gốc {row.raw_probability:.1%}"), width="stretch")
    with st.expander("Sai số theo nhóm và công bằng"):
        st.dataframe(csv_artifact(run.name, "segment_errors.csv"), hide_index=True)
        st.dataframe(csv_artifact(run.name, "fairness.csv"), hide_index=True)
        st.caption("Nhóm <50 quan sát cần thận trọng. Không sử dụng gender/SeniorCitizen làm features; vẫn có thể tồn tại proxy bias.")
    if (run / "economic_uncertainty.csv").exists():
        with st.expander("Bất định kinh tế · kịch bản chuẩn trên test"):
            st.dataframe(csv_artifact(run.name, "economic_uncertainty.csv"), hide_index=True)
            st.caption("Bootstrap ghép cặp khách hàng, giữ nguyên chính sách và giả định, dùng nhãn churn lịch sử. Chỉ phản ánh bất định lấy mẫu của mô phỏng hồi cứu; không phải khoảng tin cậy lợi nhuận thật, không bao gồm bất định save rate hay sai lệch mô hình. Không áp dụng cho CSV hoặc tham số hiện tại.")
    st.stop()

if page == "Phương pháp và hướng dẫn":
    st.title("Phương pháp và hướng dẫn")
    st.markdown("""
**Quyết định:** phân bổ ngân sách giữ chân theo giá trị kỳ vọng.

`Giá trị còn lại = MonthlyCharges × margin × min(horizon cap, base horizon × hệ số tenure)`

`EV = xác suất churn × save rate giả định × giá trị còn lại − tổng chi phí`

Save rate là giả định về khả năng giữ lại người vốn sẽ churn. Chi phí phát sinh cho mọi người được chọn. Dữ liệu lịch sử không đo tác động thực của ưu đãi.

**Quy trình demo:** xem Tổng quan → Lập chiến dịch → thay ngân sách/chi phí/save rate → xem Kịch bản → xuất danh sách. Hoặc nhập CSV mẫu và chuyển nguồn khách hàng.

**Kiểm định:** train 60%, validation 20%, test 20%; calibration từ dự đoán ngoài fold trên train. Không tối ưu bằng nhãn test. Churn mô tả trạng thái trong dữ liệu mẫu; mô hình chưa được xác thực theo thời gian trên khách hàng tương lai.

**Đọc KPI:** các kỳ vọng là số mô phỏng, số khách hàng giữ được có thể là số thập phân. ROI không xác định khi chi phí bằng 0. Precision và coverage chỉ hiển thị khi phù hợp; không thay thế ROI.

**Hai loại bộ lọc:** phân khúc đủ điều kiện áp dụng trước tối ưu; tìm kiếm trong bảng chỉ thay cách xem, không thay kết quả chiến dịch.
""")
    st.json({"run_id": run.name, "model": bundle["metadata"]["selected_model"], "threshold": bundle["metadata"]["threshold"], "high_risk_high_value_thresholds": thresholds})
    st.caption("Hồ sơ đầy đủ: reports/analysis-report.md · docs/model-card.md · docs/retention-playbook.md")
    st.stop()

cfg = deepcopy(bundle["metadata"]["config"])
st.markdown('<div class="eyebrow">RETENTION INTELLIGENCE / QUYẾT ĐỊNH THEO GIÁ TRỊ</div>', unsafe_allow_html=True)
st.markdown('<div class="hero"><h2>Đúng khách hàng. Đúng ngân sách.</h2><p>Kết hợp rủi ro rời bỏ với giá trị kinh tế để thiết kế chiến dịch giữ chân.</p></div>', unsafe_allow_html=True)
st.caption(f"Nguồn: {source} · {len(scores):,} khách hàng · đơn vị tiền tệ dữ liệu (ĐVTT)")
with st.expander("Ngân sách và giả định chiến dịch", expanded=page == "Lập chiến dịch"):
    a, b, c = st.columns(3)
    standard = cfg["offers"][1]
    budget = a.number_input("Ngân sách · ĐVTT", min_value=0.0, step=100.0, **control("budget_" + source, float(default_budget(len(scores), cfg))))
    offer_cost = b.number_input("Chi phí ưu đãi tiêu chuẩn", min_value=0.0, step=1.0, **control("offer_cost", float(standard["offer_cost"])))
    contact = c.number_input("Chi phí liên hệ tiêu chuẩn", min_value=0.0, step=1.0, **control("contact_cost", float(standard["contact_cost"])))
    a, b, c = st.columns(3)
    q = a.slider("Save rate giả định", 0.0, 1.0, step=.01, **control("save_rate", float(standard["save_rate"])))
    cfg["margin"] = b.slider("Biên đóng góp", 0.0, 1.0, step=.01, **control("margin", float(cfg["margin"])))
    cfg["base_horizon"] = c.number_input("Thời gian giá trị cơ sở (tháng)", min_value=0.0, step=1.0, **control("horizon", float(cfg["base_horizon"])))
    a, b, c = st.columns(3)
    for column, segment, label in zip([a, b, c], ["new", "developing", "loyal"], ["Hệ số tenure ≤12 tháng", "Hệ số tenure 13–24 tháng", "Hệ số tenure >24 tháng"]):
        cfg["tenure_factors"][segment] = column.number_input(label, min_value=0.0, step=.05, **control("tenure_" + segment, float(cfg["tenure_factors"][segment])))
    st.caption(f"Giới hạn thời gian giá trị: {cfg['horizon_cap']:g} tháng · Mặc định từ cấu hình run {run.name}; thay đổi được giữ trong phiên khi chuyển trang.")
    segments = st.multiselect("Phân khúc đủ điều kiện (áp dụng trước tối ưu)", ["new", "developing", "loyal"], **control("eligible_segments", ["new", "developing", "loyal"]))
    mode = st.selectbox("Chính sách ưu đãi", ["Một ưu đãi tiêu chuẩn", "Tối ưu nhiều ưu đãi", "Chính sách tenure đã khóa"], **control("offer_mode", "Một ưu đãi tiêu chuẩn"))
    cfg["offers"][1].update(offer_cost=offer_cost, contact_cost=contact, save_rate=q)
    if mode != "Một ưu đãi tiêu chuẩn":
        st.caption("Điều chỉnh thêm ưu đãi nhẹ/tăng cường; chính sách tenure giữ nguyên cách gán đã chọn trên validation.")
        for idx, name in [(0, "Nhẹ"), (2, "Tăng cường")]:
            l, r, c = st.columns(3)
            offer = cfg["offers"][idx]
            offer["offer_cost"] = l.number_input(f"Chi phí ưu đãi {name}", min_value=0.0, **control("cost_" + offer["offer_id"], float(offer["offer_cost"])))
            offer["save_rate"] = r.slider(f"Save rate {name}", 0.0, 1.0, step=.01, **control("rate_" + offer["offer_id"], float(offer["save_rate"])))
            offer["contact_cost"] = c.number_input(f"Chi phí liên hệ {name}", min_value=0.0, **control("contact_" + offer["offer_id"], float(offer["contact_cost"])))

tenure_segments = pd.cut(scores.tenure, [-np.inf, 12, 24, np.inf], labels=["new", "developing", "loyal"])
population = scores.loc[tenure_segments.isin(segments)].copy()
if population.empty:
    st.info("Không có khách hàng trong phân khúc đã chọn.")
    st.stop()
offers = [cfg["offers"][1]] if mode == "Một ưu đãi tiêu chuẩn" else cfg["offers"]
policy = read_json(run / "segment_policy.json")["policy"] if mode == "Chính sách tenure đã khóa" else None
start = time.perf_counter()
with st.spinner("Đang tính chiến dịch…"):
    target, stats = calculate(population, budget, cfg, offers, "ev", policy, thresholds)
st.session_state.last_compute_seconds = time.perf_counter() - start
metric_cards(stats)
st.caption(f"Ngân sách còn lại: {stats['remaining_budget']:,.1f} · Kịch bản {stats['scenario_id']} · Trạng thái: {stats['solver']['status']}")
if stats["solver"]["status"] in ["feasible_time_limit", "heuristic_fallback"]:
    st.warning(f"Chưa chứng minh tối ưu toàn cục. Solver gap: {stats['solver']['gap']}")
if stats["selected_count"] == 0:
    st.info("Không chọn khách hàng nào: kiểm tra EV dương và ngân sách. Không bắt buộc sử dụng hết ngân sách.")

if page == "Tổng quan":
    left, right = st.columns([1.5, 1])
    chart_data = target.assign(decision=target.selected.map({True: "Được chọn", False: "Chưa chọn"}))
    fig = px.scatter(chart_data, x="churn_probability", y="customer_value", color="decision", color_discrete_map={"Được chọn": "#0b8c88", "Chưa chọn": "#b1bdcc"}, hover_data=["customer_id", "tenure_segment", "expected_net_value"], title="Rủi ro × giá trị khách hàng", labels={"churn_probability": "Xác suất churn", "customer_value": "Giá trị còn lại · ĐVTT", "decision": "Quyết định"}, opacity=.6)
    left.plotly_chart(fig, width="stretch")
    grouped = target.groupby("tenure_segment", observed=True).agg(customers=("customer_id", "size"), selected=("selected", "sum")).reset_index()
    grouped = grouped.rename(columns={"customers": "Tổng khách hàng", "selected": "Được chọn"})
    grouped.tenure_segment = grouped.tenure_segment.map({"new": "≤12 tháng", "developing": "13–24 tháng", "loyal": ">24 tháng"})
    right.plotly_chart(px.bar(grouped, x="tenure_segment", y=["Tổng khách hàng", "Được chọn"], barmode="group", title="Phân khúc và khách hàng ưu tiên", labels={"tenure_segment": "Thời gian gắn bó", "value": "Khách hàng", "variable": ""}, color_discrete_sequence=["#bbc8d8", "#0b8c88"]), width="stretch")
    st.subheader("Hành động được đề xuất")
    st.write(f"Tiếp cận {stats['selected_count']:,} khách hàng, dùng {stats['cost']:,.0f} ĐVTT; giá trị ròng mô phỏng {stats['expected_net_value']:,.1f} ĐVTT theo giả định hiện tại. Kiểm tra độ nhạy trước khi chọn ngân sách.")
elif page == "Kịch bản và ngân sách":
    st.info(f"Độ nhạy dùng chính sách hiện tại: {mode}. Fixed giữ cả khách hàng và ưu đãi; retarget tối ưu lại theo cùng chính sách. Fixed có thể vượt ngân sách khi chi phí tăng. Đường active_policy là chính sách đang chọn; các đường khác là đối chứng.")
    st.caption("Trục save rate là mức của ưu đãi tiêu chuẩn. Với nhiều ưu đãi, cộng cùng chênh lệch điểm phần trăm vào save rate mỗi ưu đãi và chặn trong [0,1]. Hệ số chi phí áp dụng cho mọi ưu đãi, không đổi phí liên hệ.")
    if st.button("Tính độ nhạy và đường ngân sách", type="primary"):
        with st.spinner("Đang tính các kịch bản…"):
            st.session_state.scenario_results = (*scenario_views(population, budget, cfg, thresholds, offers, policy), stats["scenario_id"], mode)
    if "scenario_results" in st.session_state:
        sens, curves, sid, computed_mode = st.session_state.scenario_results
        st.caption(f"Kết quả đã tính: {computed_mode} · kịch bản {sid}")
        if sid != stats["scenario_id"]:
            st.warning("Tham số đã thay đổi. Bấm tính lại để cập nhật các biểu đồ dưới đây.")
        view = st.radio("Cách đánh giá độ nhạy", ["retarget", "fixed"], format_func=lambda x: {"retarget": "Tối ưu lại danh sách", "fixed": "Giữ nguyên khách hàng và ưu đãi"}[x], horizontal=True)
        grid = sens.query("axis == 'cost_save_rate' and mode == @view").pivot(index="parameter", columns="cost_multiplier", values="expected_net_value")
        grid.index = [f"{value:.0%}" for value in grid.index]
        grid.columns = [f"{value:g}×" for value in grid.columns]
        heatmap = px.imshow(grid, text_auto=".0f", aspect="auto", color_continuous_scale="Teal", title="Giá trị ròng kỳ vọng · ĐVTT", labels={"x": "Hệ số chi phí ưu đãi", "y": "Save rate"})
        heatmap.update_xaxes(type="category", tickmode="array", tickvals=list(grid.columns), ticktext=list(grid.columns))
        heatmap.update_yaxes(type="category", tickmode="array", tickvals=list(grid.index), ticktext=list(grid.index), autorange="reversed")
        st.plotly_chart(heatmap, width="stretch")
        st.plotly_chart(px.line(curves, x="budget", y="expected_net_value", color="strategy", title="Giá trị ròng theo ngân sách · ĐVTT", labels={"budget": "Ngân sách · ĐVTT", "expected_net_value": "Giá trị ròng · ĐVTT", "strategy": "Chiến lược"}), width="stretch")
        st.dataframe(sens, hide_index=True, width="stretch")
        st.download_button("Tải bảng độ nhạy", sens.to_csv(index=False).encode("utf-8-sig"), f"sensitivity_{sid}.csv", "text/csv")
    else:
        st.caption("Bấm nút để tính trên dữ liệu và giả định hiện tại; kết quả được lưu cache theo kịch bản.")

if page in ["Tổng quan", "Lập chiến dịch"]:
    if page == "Lập chiến dịch":
        st.subheader("So sánh trên cùng ngân sách")
        baseline_rows = []
        for strategy in ["none", "risk", "risk_positive_ev", "value", "ev"]:
            _, item = calculate(population, budget, cfg, [cfg["offers"][1]], strategy, None, thresholds)
            baseline_rows.append({"strategy": strategy, **{k: item[k] for k in ["selected_count", "cost", "expected_net_value", "precision_contacted"]}})
        comparison_table = pd.DataFrame(baseline_rows)
        comparison_table["strategy"] = comparison_table.strategy.map({"none": "Không triển khai", "risk": "Rủi ro cao nhất", "risk_positive_ev": "Rủi ro cao + EV dương", "value": "Giá trị cao nhất", "ev": "EV cao nhất"})
        st.dataframe(comparison_table, hide_index=True, width="stretch", column_config={
            "strategy": "Chiến lược", "selected_count": "Khách hàng được chọn",
            "cost": st.column_config.NumberColumn("Chi phí · ĐVTT", format="%.2f"),
            "expected_net_value": st.column_config.NumberColumn("Giá trị ròng · ĐVTT", format="%.2f"),
            "precision_contacted": st.column_config.NumberColumn("Precision nhóm chọn", format="%.3f"),
        })
        st.caption("Các đối chứng trên dùng một ưu đãi tiêu chuẩn, cùng khách hàng và ngân sách. risk/value không lọc EV; risk_positive_ev chỉ xếp rủi ro sau khi loại EV ≤0 để so sánh với một quy tắc kinh tế đơn giản hơn. KPI phía trên dùng chính sách đang chọn.")
    st.subheader("Danh sách hành động")
    a, b = st.columns([2, 1])
    query = a.text_input("Tìm ID (chỉ lọc bảng)")
    selected_only = b.checkbox("Chỉ khách hàng được chọn", value=True)
    visible = target.loc[target.selected] if selected_only else target
    if query:
        visible = visible.loc[visible.customer_id.str.contains(query, case=False, regex=False)]
    columns = ["customer_id", "churn_probability", "tenure_segment", "customer_value", "offer_id", "assumed_save_rate", "total_cost", "expected_net_value", "selected", "selection_reason"]
    st.dataframe(visible[columns], hide_index=True, width="stretch", column_config={
        "customer_id": "Mã khách hàng", "churn_probability": st.column_config.NumberColumn("Xác suất churn", format="%.3f"),
        "tenure_segment": "Nhóm tenure", "customer_value": st.column_config.NumberColumn("Giá trị · ĐVTT", format="%.2f"),
        "offer_id": "Ưu đãi", "assumed_save_rate": st.column_config.NumberColumn("Save rate", format="%.2f"),
        "total_cost": st.column_config.NumberColumn("Chi phí · ĐVTT", format="%.2f"),
        "expected_net_value": st.column_config.NumberColumn("EV ròng · ĐVTT", format="%.2f"), "selected": "Được chọn", "selection_reason": "Lý do",
    })
    st.caption("Các cột chi phí/EV là phương án tiềm năng; chỉ cộng dòng selected=True vào KPI chiến dịch. Tìm kiếm không thay đổi file xuất toàn chiến dịch.")
    if not visible.empty:
        with st.expander("Vì sao chọn hoặc không chọn khách hàng này?"):
            customer_id = st.selectbox("Khách hàng cần giải thích", visible.customer_id.tolist())
            detail = visible.loc[visible.customer_id.eq(customer_id)].iloc[0]
            st.write(detail.selection_reason)
            st.write(detail.decision_detail)
            st.caption("Đây là giải thích công thức kinh tế, không phải nguyên nhân churn hay bằng chứng ưu đãi sẽ có tác dụng. Trong bài toán nhiều ưu đãi, tổ hợp được chọn để tối đa tổng EV trong ngân sách, không nhất thiết ưu đãi có EV riêng cao nhất cho từng người.")
    st.download_button("Xuất gói chiến dịch · CSV + giả định", campaign_zip(target, stats), f"campaign_{stats['scenario_id']}.zip", "application/zip", type="primary")
    with st.expander("Precision, coverage và kết quả hồi cứu"):
        if "churn" in population:
            st.json({k: stats.get(k) for k in ["precision_contacted", "high_risk_high_value_coverage", "label_based_simulated_net"]})
            st.caption("Kết quả thay xác suất bằng nhãn lịch sử vẫn sử dụng save rate giả định, không phải tác động thực đo.")
            if source == "CSV đã nhập":
                st.warning("Chỉ là mô tả nhãn trong CSV, không được gọi là đánh giá holdout độc lập. Kiểm tra prediction_origin; nhãn hoặc ID đã dùng trong train/validation có thể làm kết quả thiên lệch.")
        else:
            st.info("CSV không có nhãn: không tính precision/recall/AUC. Coverage được định nghĩa bằng xác suất và giá trị, không phải nhãn.")
            st.write("Coverage high-risk/high-value:", stats.get("high_risk_high_value_coverage"))
