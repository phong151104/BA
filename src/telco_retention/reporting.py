from __future__ import annotations

import shutil
import textwrap
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import nbformat
from .common import ROOT, config, latest_run, read_json, table, write_json
from .data import SCHEMA, DOMAINS, NUMERIC


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def figures(run):
    dest = ROOT / "reports/figures"
    dest.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.spines.top": False, "axes.spines.right": False, "axes.titleweight": "bold", "figure.facecolor": "white", "axes.prop_cycle": plt.cycler(color=["#167e85", "#df9850", "#576f92", "#bd5b63", "#49734c", "#896aaa", "#687981"])})
    catalog = []

    def finish(name, title, caption, population="test", scenario="baseline"):
        plt.title(title, loc="left", pad=16)
        plt.figtext(.01, .01, f"Population: {population} | run: {run.name}\n{caption}", fontsize=8, color="#536276")
        plt.tight_layout(rect=(0, .075, 1, 1))
        plt.savefig(dest / f"{name}.png", dpi=160, bbox_inches="tight")
        plt.close()
        catalog.append({"file": name + ".png", "title": title, "population": population, "caption": caption, "run_id": run.name, "scenario": scenario})

    eda = pd.read_csv(run / "eda_segments.csv")
    for col, name in [("Contract", "eda_contract"), ("tenure_segment", "eda_tenure"), ("PaymentMethod", "eda_payment")]:
        df = eda.loc[eda.attribute.eq(col)]
        plt.figure(figsize=(9, 5))
        plt.barh(df.group.astype(str), df.churn_rate, color="#167e85")
        plt.xlabel("Tỷ lệ churn quan sát")
        finish(name, "Churn theo " + col, "Phân tích mô tả; không chứng minh quan hệ nhân quả.", "train", "not applicable")
    calibration = pd.read_csv(run / "calibration.csv")
    plt.figure(figsize=(9, 6))
    for name, part in calibration.groupby("model"):
        plt.plot(part.predicted, part.observed, marker="o", markersize=3, label=name)
    plt.plot([0, 1], [0, 1], "--", color="gray")
    plt.xlabel("Xác suất dự đoán"); plt.ylabel("Tỷ lệ churn quan sát"); plt.legend(fontsize=8)
    finish("calibration", "Hiệu chỉnh xác suất", "10 bins quantile; mô hình chọn trên validation.", scenario="not applicable")
    for name, x, y, title in [("pr_curve", "recall", "precision", "Precision–Recall"), ("roc_curve", "fpr", "tpr", "ROC")]:
        df = pd.read_csv(run / f"{name}.csv")
        plt.figure(figsize=(8, 5)); plt.plot(df[x], df[y]); plt.xlabel(x); plt.ylabel(y)
        finish(name, title + " · mô hình được chọn", "Đánh giá holdout; không dùng test để chọn mô hình.", scenario="not applicable")
    comparison = pd.read_csv(run / "strategy_comparison.csv")
    plt.figure(figsize=(10, 5)); plt.barh(comparison.strategy, comparison.expected_net_value); plt.axvline(0, color="gray", linewidth=1); plt.xlabel("Giá trị ròng kỳ vọng · ĐVTT")
    finish("strategy_comparison", "So sánh chiến lược giữ chân", "Cùng ngân sách; save rate/chi phí là giả định; không phải lợi nhuận thực thu.")
    curves = pd.read_csv(run / "budget_curve.csv")
    plt.figure(figsize=(10, 5))
    for strategy, part in curves.groupby("strategy"):
        plt.plot(part.budget, part.expected_net_value, label=strategy)
    plt.legend(); plt.xlabel("Ngân sách · ĐVTT"); plt.ylabel("Giá trị ròng kỳ vọng · ĐVTT")
    finish("budget_curve", "Ngân sách và giá trị giữ chân", "21 mức ngân sách; ưu đãi/giá trị theo cấu hình chuẩn.", scenario="budget sweep")
    sensitivity = pd.read_csv(run / "sensitivity.csv")
    for mode in ["fixed", "retarget"]:
        grid = sensitivity.query("axis == 'cost_save_rate' and mode == @mode").pivot(index="parameter", columns="cost_multiplier", values="expected_net_value")
        plt.figure(figsize=(9, 6)); plt.imshow(grid, aspect="auto", cmap="BrBG")
        plt.xticks(range(len(grid.columns)), grid.columns); plt.yticks(range(len(grid.index)), [f"{x:.0%}" for x in grid.index]); plt.xlabel("Hệ số chi phí ưu đãi"); plt.ylabel("Save rate giả định")
        for i in range(len(grid)):
            for j in range(len(grid.columns)):
                plt.text(j, i, f"{grid.iloc[i,j]:,.0f}", ha="center", va="center", fontsize=9)
        plt.colorbar(label="Giá trị ròng · ĐVTT")
        finish("sensitivity_" + mode, "Độ nhạy · " + mode, "Fixed giữ danh sách, có thể vượt ngân sách; retarget chọn lại trong ngân sách.", scenario="cost/save sweep")
    shap = pd.read_csv(run / "shap_global.csv").head(15).sort_values("mean_abs_shap")
    plt.figure(figsize=(10, 7)); plt.barh(shap.feature, shap.mean_abs_shap); plt.xlabel("Mean |TreeSHAP| · log-odds")
    finish("shap_global", "Giải thích XGBoost gốc", "Mẫu 200 khách hàng; không phân rã xác suất calibrated, không nhân quả.", "validation", "not applicable")
    target = pd.read_csv(run / "targeting_ev.csv")
    plt.figure(figsize=(9, 6))
    for selected, part in target.groupby("selected"):
        plt.scatter(part.churn_probability, part.customer_value, s=14, alpha=.5, label="Được chọn" if selected else "Không chọn")
    plt.legend(); plt.xlabel("Xác suất churn"); plt.ylabel("Giá trị còn lại · ĐVTT")
    finish("risk_value", "Rủi ro và giá trị khách hàng", "Margin 30%, horizon cơ sở 12 tháng; ngưỡng high/high khóa trên validation.")
    plt.figure(figsize=(9, 5)); plt.hist(target.churn_probability, bins=25); plt.xlabel("Xác suất churn"); plt.ylabel("Số khách hàng")
    finish("probability_distribution", "Phân bố xác suất churn", "Mô hình được chọn trước khi đánh giá test.", scenario="not applicable")
    fair = pd.read_csv(run / "fairness.csv").query("strategy == 'ev' and attribute == 'gender'")
    plt.figure(figsize=(8, 5)); plt.bar(fair.group.astype(str), fair.selection_rate); plt.ylabel("Tỷ lệ được chọn")
    finish("fairness_selection", "Kiểm tra phân bổ theo gender", "Mô tả chênh lệch; không kết luận chính sách công bằng chỉ từ biểu đồ này.")
    write_json(dest / "catalog.json", catalog)
    return catalog


def dictionary():
    descriptions = {
        "customerID": "Mã định danh khách hàng; khóa, không làm feature", "gender": "Giới tính ghi nhận; chỉ dùng audit", "SeniorCitizen": "Cờ khách hàng cao tuổi; chỉ dùng audit", "Partner": "Có bạn đời", "Dependents": "Có người phụ thuộc", "tenure": "Số tháng đã gắn bó", "PhoneService": "Đăng ký dịch vụ điện thoại", "MultipleLines": "Nhiều đường dây điện thoại", "InternetService": "Loại dịch vụ Internet", "OnlineSecurity": "Bảo mật trực tuyến", "OnlineBackup": "Sao lưu trực tuyến", "DeviceProtection": "Bảo vệ thiết bị", "TechSupport": "Hỗ trợ kỹ thuật", "StreamingTV": "Xem TV trực tuyến", "StreamingMovies": "Xem phim trực tuyến", "Contract": "Thời hạn hợp đồng", "PaperlessBilling": "Hóa đơn điện tử", "PaymentMethod": "Phương thức thanh toán", "MonthlyCharges": "Phí hàng tháng", "TotalCharges": "Tổng phí lịch sử; không cộng vào giá trị tương lai", "Churn": "Nhãn rời bỏ trong dữ liệu mẫu; không làm feature",
    }
    rows = []
    for col in SCHEMA:
        rows.append({"Trường": col, "Ý nghĩa": descriptions[col], "Kiểu/đơn vị": "số/tháng" if col == "tenure" else "số/ĐVTT" if col in ["MonthlyCharges", "TotalCharges"] else "chuỗi/nhóm", "Miền/missing": "; ".join(DOMAINS[col]) if col in DOMAINS else "không âm; missing → median train" if col in NUMERIC else "duy nhất, không rỗng", "Vai trò": "target" if col == "Churn" else "audit" if col in ["gender", "SeniorCitizen"] else "khóa" if col == "customerID" else "feature"})
    derived = [
        ("churn", "int 0/1", "Nhãn ánh xạ từ Churn; không làm feature"), ("split", "train/validation/test", "Vai trò dòng trong kiểm định"),
        ("tenure_band / tenure_segment", "new/developing/loyal", "≤12; 13–24; >24 tháng. Feature và phân khúc"),
        ("addon_count", "int 0–6", "Tổng dịch vụ thêm có giá trị Yes"), ("monthly_contract", "0/1", "Hợp đồng Month-to-month"), ("autopay", "0/1", "Thanh toán automatic"),
        ("customer_id", "string", "Bí danh customerID trong bảng kết quả"), ("churn_probability", "float [0,1]", "Xác suất calibrated"),
        ("risk_band", "low/medium/high", "≤0.25; (0.25,0.5]; >0.5; chỉ mô tả, khác ngưỡng high/high"),
        ("prediction_origin", "string", "in_sample_do_not_evaluate / selection_holdout / untouched_test / uploaded_unseen"),
        ("model_version", "string", "Run ID gắn artifact mô hình"), ("remaining_months", "tháng", "min(cap, horizon × hệ số tenure)"),
        ("customer_value", "ĐVTT", "MonthlyCharges × margin × remaining_months"), ("offer_id", "string", "light/standard/intensive"),
        ("assumed_save_rate", "[0,1]", "Giả định giữ lại một người vốn sẽ churn"), ("offer_cost / contact_cost / total_cost", "ĐVTT", "Chi phí cố định mỗi người được chọn; total là tổng hai thành phần"),
        ("expected_saved_probability", "[0,1]", "churn_probability × assumed_save_rate"), ("expected_retained_value", "ĐVTT", "expected_saved_probability × customer_value"),
        ("expected_net_value", "ĐVTT", "expected_retained_value − total_cost"), ("selected", "bool", "Quyết định chọn; chỉ tổng hợp KPI cho selected=True"),
        ("selection_reason", "string", "Lý do lựa chọn/không chọn"), ("scenario_id", "string", "Hash cấu hình, ngân sách và tập khách hàng"),
        ("break_even_save_rate", "tỷ lệ hoặc NA", "cost/(p × V); NA khi p × V = 0; >1 nghĩa không hòa vốn được"), ("break_even_total_cost", "ĐVTT", "p × q × V"),
        ("customer_index", "int nội bộ", "Vị trí khách hàng để ràng buộc tối đa một ưu đãi"),
    ]
    write(ROOT / "docs/data-dictionary.md", "# Từ điển dữ liệu\n\n" + table(pd.DataFrame(rows)) + "\n\n## Trường phát sinh\n\n" + table(pd.DataFrame(derived, columns=["Trường", "Kiểu/đơn vị", "Ý nghĩa"])) + "\n\nChuỗi rỗng TotalCharges → missing; tenure=0 → điền 0. Các số thiếu khác dùng median train, cả khi tính giá trị kinh doanh. Các trường phân loại bắt buộc không nhận missing. Các trạng thái không có dịch vụ là giá trị hợp lệ. Tiền dùng ĐVTT, không quy đổi VND.")


def notebooks(run):
    setup = "from telco_retention.common import ROOT, latest_run, read_json\nimport pandas as pd\nfrom IPython.display import display, Image\nrun = latest_run()\nprint('Run:', run.name)"
    specs = [
        ("01-data-eda", "Dữ liệu và EDA", "EDA thiết kế trên train. Các bảng và hình do pipeline chung tạo; không fit thêm trên test.", ["display(read_json(ROOT / 'data/raw/source.json'))\ndisplay(read_json(ROOT / 'data/processed/quality.json'))", "display(pd.read_csv(run / 'eda_segments.csv'))\ndisplay(pd.read_csv(run / 'correlations.csv'))", "display(Image(filename=str(ROOT / 'reports/figures/eda_contract.png')))\ndisplay(Image(filename=str(ROOT / 'reports/figures/eda_tenure.png')))"]),
        ("02-models-validation", "Mô hình và kiểm định", "Các mô hình được fit trong package modeling. Xem CV results, lựa chọn trên validation và kết quả test; không chọn lại theo test.", ["display(pd.read_csv(run / 'validation_metrics.csv'))\ndisplay(read_json(run / 'manifest.json')['best_parameters'])", "display(pd.read_csv(run / 'test_metrics.csv'))\ndisplay(pd.read_csv(run / 'bootstrap_intervals.csv'))", "display(Image(filename=str(ROOT / 'reports/figures/calibration.png')))\ndisplay(Image(filename=str(ROOT / 'reports/figures/shap_global.png')))"]),
        ("03-targeting", "Giá trị và chiến dịch", "Tính lại chiến dịch bằng cùng hàm dashboard. Save rate là giả định; kết quả không nhân quả.", ["from telco_retention.business import campaign\nfrom telco_retention.analysis import default_budget\nscores = pd.read_csv(run / 'scorecard.csv').query(\"split == 'test'\")\ntarget, summary = campaign(scores, default_budget(len(scores)), thresholds=read_json(run / 'targeting_thresholds.json'))\ndisplay({k:v for k,v in summary.items() if k != 'scenario'})\ndisplay(target.loc[target.selected].head(10))", "display(pd.read_csv(run / 'strategy_comparison.csv'))\ndisplay(read_json(run / 'segment_policy.json'))", "display(Image(filename=str(ROOT / 'reports/figures/risk_value.png')))"]),
        ("04-sensitivity-fairness", "Độ nhạy và công bằng", "Fixed và retarget có ý nghĩa khác nhau. Nhóm mẫu nhỏ không đủ cho kết luận chắc chắn.", ["display(pd.read_csv(run / 'sensitivity.csv'))\ndisplay(pd.read_csv(run / 'budget_curve.csv'))", "display(pd.read_csv(run / 'fairness.csv'))", "display(Image(filename=str(ROOT / 'reports/figures/sensitivity_fixed.png')))\ndisplay(Image(filename=str(ROOT / 'reports/figures/sensitivity_retarget.png')))\ndisplay(Image(filename=str(ROOT / 'reports/figures/budget_curve.png')))"]),
    ]
    for name, title, intro, cells in specs:
        nb = nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell(f"# {title}\n\n{intro}\n\nChạy `python -m telco_retention run-all` trước. Notebook sử dụng artifacts và logic của package, không có mô hình thứ hai độc lập."), nbformat.v4.new_code_cell(setup)] + [nbformat.v4.new_code_cell(c) for c in cells])
        nb.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
        nbformat.write(nb, ROOT / "notebooks" / f"{name}.ipynb")


def report(run=None):
    run = run or latest_run()
    manifest = read_json(run / "manifest.json")
    cfg = manifest["config"]
    source = read_json(run / "dataset_source.json")
    quality = read_json(run / "data_quality.json")
    source_metadata = read_json(run / "dataset_metadata.json")
    summary = read_json(run / "campaign_scenarios.json")
    ev, risk = summary["ev"], summary["risk"]
    metrics = pd.read_csv(run / "test_metrics.csv")
    selected = metrics.loc[metrics.model.eq(manifest["selected_model"] + "_calibrated")].iloc[0]
    comparison = pd.read_csv(run / "strategy_comparison.csv")
    sens = pd.read_csv(run / "sensitivity.csv")
    grid = sens.query("axis == 'cost_save_rate' and mode == 'retarget'")
    fixed = sens.query("axis == 'cost_save_rate' and mode == 'fixed'")
    eda = pd.read_csv(run / "eda_segments.csv")
    policy = read_json(run / "segment_policy.json")
    curves = pd.read_csv(run / "budget_curve.csv")
    best_curve = curves.query("strategy == 'ev'").sort_values(["expected_net_value", "budget"], ascending=[False, True]).iloc[0]
    fair = pd.read_csv(run / "fairness.csv")
    catalog = figures(run)
    for folder in ["reports/tables", "notebooks"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    for path in run.glob("*.csv"):
        shutil.copy2(path, ROOT / "reports/tables" / path.name)
    dictionary()
    write(ROOT / "docs/source-log.md", f"""# Nhật ký nguồn

Nguồn tải thực tế: **{source['source']}**. [Trang dataset]({source['dataset_page']}).

- URL tải: {source['url']}
- Tệp gốc: `{source['original_filename']}`.
- Thời điểm tải UTC: {source['downloaded_at_utc']}.
- Phiên bản: {source['version']}.
- SHA-256: `{source['sha256']}`.
- Số dòng: {source['rows']}; số cột: {len(source['columns'])}.
- Điều kiện sử dụng: {source['license_note']}
- Nhãn giấy phép trong metadata Kaggle: **{source_metadata.get('license')}**; phiên bản được metadata công bố: {source_metadata.get('version', 'không có')}. [Metadata API]({source_metadata['metadata_url']}). Metadata được quan sát riêng; checksum raw mới là định danh chính xác tệp phân tích. Không mặc định dữ liệu là CC0 hoặc giấy phép mở.
- Join: {quality['joins']}.
- Bộ lọc: {quality['filters']}.

Ưu đãi tổng hợp: `{cfg['assumptions_version']}`; do dự án đặt để mô phỏng. Không có dữ liệu chiến dịch ngẫu nhiên. Xem [bảng ưu đãi](../reports/tables/synthetic_offers.csv).

Dữ liệu raw không được sửa. Download tái sử dụng nếu checksum đúng; nếu sai sẽ dừng, không ghi đè. Xem metadata đầy đủ trong `data/raw/source.json`.
""")
    write(ROOT / "docs/cleaning-log.md", f"""# Nhật ký làm sạch

{table(pd.DataFrame([{'Chỉ tiêu': k, 'Giá trị': quality[k]} for k in ['rows_before','rows_after','duplicates_removed','total_charges_missing_before','total_charges_filled_zero','unique_ids']]))}

Trim khoảng trắng; Churn Yes/No ánh xạ 1/0. TotalCharges trống đổi thành missing; trường hợp tenure=0 điền 0. Các số thiếu khác được median-impute trong pipeline fit trên train; giá trị kinh doanh dùng cùng median train lưu trong manifest. Giữ No internet service/No phone service. Không cắt bỏ outlier hợp lệ.

{table(pd.DataFrame({'Trường': list(quality['missing_after']), 'Missing sau làm sạch': list(quality['missing_after'].values())}))}

Phân bố nhãn: {quality['churn_counts']}. Chia stratified seed {cfg['seed']}, kích thước {manifest['split_counts']}. Các ID split lưu tại `data/processed/splits.csv`. Không nối nguồn khách hàng khác.
""")
    write(ROOT / "docs/model-card.md", f"""# Model / Analysis Card

## Nhận diện và mục đích

Run `{run.name}`; mô hình `{manifest['selected_model']}` + sigmoid calibration. Hỗ trợ phân loại churn và ưu tiên mô phỏng giữ chân trong một capstone. Không tự động liên hệ khách hàng.

## Target và dữ liệu

Target Churn Yes/No của IBM Telco sample; dữ liệu mô tả churn trong giai đoạn lịch sử gần nhất, không có chuỗi thời gian để xác nhận dự báo tương lai. Nguồn thực tế Kaggle, {source['rows']} khách hàng; checksum `{source['sha256']}`.

## Features

{', '.join(manifest['feature_columns'])}.

customerID và Churn không là features. gender/SeniorCitizen chỉ dùng audit. Numeric median + scaling, categorical imputation + one-hot. Tất cả bộ biến đổi được học trong fold train.

## Validation và chọn mô hình

Train/validation/test: {manifest['split_counts']}. Stratified random split, seed 42. CV 5 fold trên train, AP làm mục tiêu; calibration dùng OOF. Chọn calibrated AP trong 0.01 của tốt nhất, Brier trong 0.002 của tốt nhất trong nhóm đó, ưu tiên Logistic → Random Forest → XGBoost. Không chọn theo test và không refit toàn dataset.

Ngưỡng F1 validation: {manifest['threshold']:.2f}, chỉ cho metric phân loại. Targeting dùng EV và ngân sách. Các metric theo ngưỡng của mô hình khác trong bảng test dùng chung ngưỡng này, không phải ngưỡng tối ưu riêng của từng model.

## Kết quả test

{table(metrics)}

[Khoảng bootstrap 95%](../reports/tables/bootstrap_intervals.csv), 1.000 lần. Chất lượng calibration không được giả định luôn cải thiện; so sánh raw/calibrated được công bố đầy đủ.

## Giả định và giới hạn

Save rate, margin, horizon, hệ số tenure và chi phí là giả định có thể chỉnh. Không dùng uplift nhân quả vì không có chiến dịch ngẫu nhiên. Giá trị mô phỏng không chứng minh tác động thực của ưu đãi. Dữ liệu mẫu không đại diện cho mọi doanh nghiệp; random split chưa kiểm định temporal drift. Proxy giá trị không phải CLV được xác thực. Không dùng kết quả in-sample để báo hiệu quả.

## Đạo đức, thiên lệch và trải nghiệm

[Fairness audit](../reports/tables/fairness.csv) báo selection rate, recall, calibration và lỗi theo nhóm. Loại gender/SeniorCitizen khỏi features không loại bỏ proxy bias. Nhóm <50 được gắn nhãn mẫu nhỏ. Chính sách theo EV có thể ít tiếp cận khách hàng giá trị thấp; quản lý phải cân nhắc cam kết dịch vụ, tính nhất quán ưu đãi và quyền từ chối liên hệ.

## Giải thích

SHAP thuộc XGBoost gốc, log-odds, mẫu validation 200 người. Không phân rã xác suất calibrated và không giải thích nhân quả. Có hệ số Logistic và permutation importance của hai mô hình cây.

## Vận hành

Chỉ nạp artifact do dự án tạo; joblib không dùng cho tệp mô hình người dùng upload. CSV mới không huấn luyện lại mô hình. Khi có dữ liệu thật, cần đánh giá theo thời gian và thử nghiệm chiến dịch phù hợp trước ứng dụng thực tế. Phiên bản dependency và checksum code lưu trong run manifest.
""")
    write(ROOT / "docs/retention-playbook.md", f"""# Retention playbook

## Quyết định chuẩn

Ngân sách {ev['scenario']['budget']:,.0f} ĐVTT trên {manifest['split_counts']['test']} khách hàng test. Ưu đãi tiêu chuẩn: cost 20 + contact 2; save rate 20%. Margin 30%; horizon cơ sở 12 tháng; hệ số tenure 0.75/1/1.25, cap 24.

`V = MonthlyCharges × margin × min(cap, horizon × tenure factor)`

`EV = p(churn) × save rate × V − offer cost − contact cost`

Chi phí phát sinh cho tất cả người được chọn. Không cộng TotalCharges lịch sử vào V. Không dùng nhãn Churn để chọn người.

## Kết quả đề xuất

Chọn {ev['selected_count']} người, chi phí {ev['cost']:,.0f}, giá trị ròng kỳ vọng {ev['expected_net_value']:,.2f} ĐVTT. Scenario `{ev['scenario_id']}`, run `{run.name}`. Xem [targeting](../reports/tables/targeting_ev.csv).

## Thực hiện demo

1. Chọn dữ liệu demo test hoặc CSV đã được kiểm tra.
2. Xác định khách hàng đủ điều kiện và ngân sách.
3. Nhập các giả định chi phí, save rate, margin, horizon.
4. Kiểm tra danh sách, số tiền còn lại và trạng thái solver.
5. So sánh risk-only/value-only với EV dưới cùng ngân sách.
6. Kiểm tra độ nhạy fixed và retarget. Fixed vượt ngân sách là tình huống kiểm tra rủi ro, không phải chiến dịch khả thi mới.
7. Xuất ZIP chứa toàn bảng, danh sách chọn và JSON giả định.

## Quy tắc không chọn

EV ≤0 không được chiến lược EV chọn. Không ép dùng hết ngân sách. Baseline risk/value/random chỉ thực hiện quy tắc đơn giản nên có thể chọn EV âm; mục tiêu là làm rõ giá trị của việc tính kinh tế.

## Chính sách phân khúc

Chọn trong 27 cấu hình trên validation: {policy['policy']}. Việc cả ba nhóm nhận cùng ưu đãi là một kết quả hợp lệ, không ép tạo khác biệt khi mô phỏng không hỗ trợ. Multi-offer và segment-policy được so sánh riêng trong báo cáo.

## Ngân sách và độ nhạy

Trong 21 điểm khảo sát, chiến lược EV đạt cực đại lần đầu ở ngân sách {best_curve.budget:,.0f} ĐVTT với net {best_curve.expected_net_value:,.2f}; đây là kết quả của lưới, không tuyên bố cực trị liên tục. Phạm vi net retarget trong lưới cost/save: {grid.expected_net_value.min():,.2f} đến {grid.expected_net_value.max():,.2f}. Fixed: {fixed.expected_net_value.min():,.2f} đến {fixed.expected_net_value.max():,.2f}.

## Giới hạn áp dụng

Chỉ là mô phỏng học thuật. Nên xác thực chi phí và save rate bằng dữ liệu phù hợp, xem xét quyền liên hệ và trải nghiệm, rồi thiết kế đánh giá thực tế. Không diễn giải churn cao là bằng chứng khách hàng chắc chắn phản hồi tốt với ưu đãi.
""")
    # Keep this executive brief compact for later two-page typesetting.
    brief = f"""# Executive brief — Giữ chân khách hàng theo giá trị

## Quyết định cần hỗ trợ

Doanh nghiệp cần lựa chọn khách hàng nhận ưu đãi trong một ngân sách cố định. Dự án kết hợp xác suất rời bỏ với giá trị đóng góp còn lại để tạo danh sách ưu tiên, thay vì chỉ xếp theo mức rủi ro. Phạm vi là mô phỏng học thuật trên dữ liệu IBM Telco tải từ Kaggle; không triển khai liên hệ thực tế.

## Dữ liệu và độ tin cậy

Bộ dữ liệu có {source['rows']:,} khách hàng. Dữ liệu được làm sạch và chia train, validation, test theo tỷ lệ 60/20/20. Mô hình Logistic Regression hiệu chỉnh sigmoid được chọn trên validation theo quy tắc đã định trước. Trên test, ROC-AUC đạt {selected.roc_auc:.3f}, Average Precision đạt {selected.average_precision:.3f} và Brier score đạt {selected.brier:.3f}. Chỉ số phản ánh chất lượng phân loại lịch sử, chưa xác nhận khả năng dự báo trong tương lai.

## Kết quả kinh doanh mô phỏng

Kịch bản chuẩn có ngân sách {ev['cost']:,.0f} ĐVTT. Mỗi người nhận ưu đãi tiêu chuẩn phát sinh chi phí 22 ĐVTT; save rate giả định 20%. Giá trị khách hàng dùng phí tháng, biên đóng góp 30% và horizon cơ sở 12 tháng có điều chỉnh tenure. Chiến lược EV chọn {ev['selected_count']} khách hàng và tạo net kỳ vọng {ev['expected_net_value']:,.0f} ĐVTT, so với {risk['expected_net_value']:,.0f} ĐVTT của risk-only. Chênh lệch {ev['expected_net_value']-risk['expected_net_value']:,.0f} ĐVTT xuất phát từ việc ưu tiên đồng thời rủi ro và giá trị.

Precision của nhóm EV là {ev['precision_contacted']:.1%}, thấp hơn hoặc khác chiến lược chỉ ưu tiên rủi ro nhưng cần đọc cùng giá trị kinh tế. Xác suất churn cao không đồng nghĩa mọi khách hàng đều đáng nhận ưu đãi như nhau. Tối ưu nhiều ưu đãi và chính sách tenure cũng được kiểm tra; báo cáo giữ nguyên kết quả khi chúng không cải thiện so với một ưu đãi chung.

## Khuyến nghị quản lý

Sử dụng danh sách EV làm phương án tham khảo, kiểm tra khả năng liên hệ và chất lượng dữ liệu trước khi áp dụng. Chỉnh save rate, chi phí và giá trị còn lại theo bối cảnh cụ thể. Không ép tiêu hết ngân sách nếu các khách hàng còn lại có EV không dương. Dashboard cho phép kiểm tra kịch bản và xuất danh sách kèm giả định để người khác rà soát.

## Độ nhạy và giới hạn

Trong lưới chi phí và save rate, net retarget thay đổi từ {grid.expected_net_value.min():,.0f} đến {grid.expected_net_value.max():,.0f} ĐVTT. Đây là khoảng kịch bản, không phải khoảng tin cậy của lợi nhuận. Save rate không được ước lượng từ chiến dịch ngẫu nhiên; giá trị khách hàng là proxy. Vì vậy không thể tuyên bố tác động nhân quả hay lợi nhuận thực thu. Dữ liệu mẫu và phép chia ngẫu nhiên còn hạn chế khả năng khái quát. Cần xem xét chênh lệch phân bổ ưu đãi giữa các nhóm và xác thực bằng dữ liệu thực tế.

Run `{run.name}`; scenario `{ev['scenario_id']}`. Nguồn số liệu: analysis-report.md và các bảng kèm theo. Người biên tập kiểm tra giới hạn hai trang sau khi dàn trang.
"""
    write(ROOT / "reports/executive-brief.md", brief)
    report_text = f"""# Hồ sơ phân tích Telecom Churn & Retention Targeting

Run `{run.name}` · nguồn `{source['source']}` · scenario chuẩn `{ev['scenario_id']}`.

Tài liệu này là nguồn nội dung cho báo cáo và slide. Tất cả số liệu bên dưới được sinh từ pipeline đã chạy; không phải số mẫu. Tiền là ĐVTT. Save rate, chi phí, margin và horizon là giả định.

## Mục lục

1. [Bối cảnh](#1-bối-cảnh-và-quyết-định)
2. [Dữ liệu](#2-dữ-liệu-và-chất-lượng)
3. [EDA](#3-khám-phá-dữ-liệu)
4. [Kiểm định](#4-thiết-kế-kiểm-định)
5. [Mô hình](#5-kết-quả-mô-hình)
6. [Giải thích](#6-giải-thích-đặc-trưng)
7. [Giá trị](#7-giá-trị-khách-hàng-và-ưu-đãi)
8. [Targeting](#8-so-sánh-chiến-lược)
9. [Độ nhạy](#9-độ-nhạy-và-ngân-sách)
10. [Phân khúc và công bằng](#10-chính-sách-phân-khúc-và-công-bằng)
11. [Khuyến nghị](#11-khuyến-nghị-quản-lý)
12. [Giới hạn](#12-giới-hạn)
13. [Demo](#13-kịch-bản-demo)
14. [Dàn ý slide](#14-dàn-ý-slide-và-danh-mục-bằng-chứng)

## 1. Bối cảnh và quyết định

Doanh nghiệp viễn thông có ngân sách giữ chân hữu hạn. Quyết định là chọn ai và ưu đãi nào để tạo giá trị giữ chân ròng kỳ vọng tốt nhất. Dự đoán churn là đầu vào, không phải đích cuối. Người sử dụng chính là quản lý chiến dịch và người phân tích hỗ trợ ra quyết định.

Thành công được đánh giá ở ba mức: phân biệt và hiệu chỉnh xác suất; chất lượng danh sách targeting; giá trị kinh tế dưới giả định minh bạch. Không đặt KPI mô hình tùy ý để buộc kết quả đạt một con số mong muốn.

## 2. Dữ liệu và chất lượng

Nguồn thực tế: [{source['source']}]({source['dataset_page']}). Có {source['rows']:,} dòng, {len(source['columns'])} cột. Checksum `{source['sha256']}`. [Source log](../docs/source-log.md), [data dictionary](../docs/data-dictionary.md), [cleaning log](../docs/cleaning-log.md).

Có {quality['total_charges_missing_before']} TotalCharges trống; {quality['total_charges_filled_zero']} trường hợp tenure=0 được điền 0. Loại {quality['duplicates_removed']} dòng trùng hoàn toàn. Không nối nguồn khách hàng ngoài; không loại outlier hợp lệ. Ưu đãi là dữ liệu tổng hợp có nguồn gốc riêng và các giá trị công khai.

## 3. Khám phá dữ liệu

EDA thiết kế trên tập train; không sử dụng test để tạo features hoặc sửa giả định.

{table(eda.loc[eda.attribute.isin(['Contract','tenure_segment'])])}

![Churn theo hợp đồng](figures/eda_contract.png)

Biểu đồ đối chiếu churn giữa các loại hợp đồng. Nhóm có tỷ lệ cao chỉ cho thấy liên hệ trong mẫu; không chứng minh đổi hợp đồng sẽ làm giảm churn. Cần xem cả số lượng nhóm để tránh đánh giá một nhóm nhỏ như nhóm lớn.

![Churn theo tenure](figures/eda_tenure.png)

Tenure giúp xem rủi ro thay đổi theo giai đoạn quan hệ khách hàng, đồng thời tham gia proxy giá trị qua các hệ số giả định. Đây là hai vai trò khác nhau; hệ số giá trị không được suy ra như một kết luận nhân quả từ biểu đồ churn.

![Thanh toán](figures/eda_payment.png)

Khác biệt theo cách thanh toán có thể liên quan đặc điểm khách hàng và dịch vụ. Không kết luận phương thức thanh toán tự nó gây churn. Xem thêm [bảng EDA đầy đủ](tables/eda_segments.csv), [thống kê](tables/eda_descriptive.csv), [tương quan](tables/correlations.csv).

## 4. Thiết kế kiểm định

Kích thước: {manifest['split_counts']}. Seed 42; stratify Churn; fit median/scaler/encoder trong train fold. Calibration sigmoid dùng dự đoán OOF qua 5 fold. Validation chọn mô hình, ngưỡng và chính sách; test dùng đánh giá cuối. Không refit lại mô hình bằng toàn dataset sau test.

Loại customerID và Churn khỏi features. gender/SeniorCitizen phục vụ audit. Thêm tenure band, số dịch vụ, cờ hợp đồng tháng và autopay. [Model card](../docs/model-card.md) liệt kê toàn bộ features và giới hạn. Điểm train trong scorecard được gắn `in_sample_do_not_evaluate`.

## 5. Kết quả mô hình

### Validation và lựa chọn

{table(pd.read_csv(run / 'validation_metrics.csv'))}

Chọn `{manifest['selected_model']}` calibrated theo quy tắc AP trong 0.01 của tốt nhất, Brier trong 0.002 của tốt nhất trong nhóm và ưu tiên đơn giản. Không chọn lại khi mô hình khác có test AP cao hơn.

### Test

{table(metrics)}

AP ở đây là Average Precision của scikit-learn, không phải tích phân hình thang đường PR. Ngưỡng phân loại {manifest['threshold']:.2f} chọn theo F1 validation của mô hình bàn giao; được dùng chung để so sánh các metric thresholded. Precision/recall/F1 không mô tả tối ưu kinh doanh.

{table(pd.read_csv(run / 'bootstrap_intervals.csv'))}

Khoảng bootstrap 95% từ 1.000 lần lấy mẫu test phản ánh bất định lấy mẫu của metric, không bao gồm mọi sai lệch nguồn dữ liệu hay chứng minh tác động ưu đãi.

![Calibration](figures/calibration.png)

Calibration cần xem cả Brier/log loss và biểu đồ. Trong lần chạy này, một số mô hình calibrated không cải thiện so với raw; kết quả được giữ nguyên. Việc yêu cầu calibration không đồng nghĩa đảm bảo nó luôn làm mô hình tốt hơn.

![PR](figures/pr_curve.png)

PR cho thấy đánh đổi precision–recall khi đổi ngưỡng. [ROC](figures/roc_curve.png), [confusion matrix](tables/confusion_matrix.csv), [threshold analysis](tables/threshold_analysis.csv) và [sai số phân khúc](tables/segment_errors.csv) cung cấp chẩn đoán bổ sung.

## 6. Giải thích đặc trưng

![SHAP](figures/shap_global.png)

Đây là TreeSHAP của XGBoost gốc trên 200 khách hàng validation, đơn vị log-odds. Mô hình bàn giao có thể khác XGBoost. Mean absolute SHAP đo độ lớn đóng góp, không cho biết chiều tác động trung bình. Bảng local chứa giá trị có dấu và base value để giải thích từng người.

Nguồn bổ sung: [hệ số Logistic](tables/logistic_coefficients.csv), [permutation RF](tables/permutation_random_forest.csv), [permutation XGBoost](tables/permutation_xgboost.csv), [SHAP local](tables/shap_local.csv). Các kết quả không là giải thích nhân quả và không phân rã xác suất sau calibration.

## 7. Giá trị khách hàng và ưu đãi

`V = MonthlyCharges × margin × min(24, base_horizon × tenure_factor)`.

Mặc định margin 30%, base horizon 12 tháng; new/developing/loyal có hệ số 0.75/1/1.25. Mọi giá trị đều có thể chỉnh; kịch bản hệ số tenure bằng 1 được kiểm tra riêng. TotalCharges là thông tin lịch sử, không được cộng như lợi ích tương lai.

{table(pd.read_csv(run / 'synthetic_offers.csv'))}

`EV = p × q × V − offer_cost − contact_cost`. q là save rate giả định có điều kiện khách hàng vốn sẽ churn; không phải xác suất phản hồi được học từ dữ liệu. Chi phí được tính trên mọi người được chọn. EV có thể âm; chiến lược EV được phép không dùng hết ngân sách.

## 8. So sánh chiến lược

Ngân sách chuẩn {ev['scenario']['budget']:,.0f} ĐVTT. Mỗi chiến lược dùng cùng tập test. Single-offer so sánh cùng mức chi phí; multi-offer trình bày riêng. Random là trung bình {cfg['random_campaign_iterations']} lần chọn ngẫu nhiên với seed cố định.

{table(comparison[['strategy','selected_count','cost','expected_saved','expected_net_value','roi','precision_contacted','high_risk_high_value_coverage','label_based_simulated_net']])}

![So sánh targeting](figures/strategy_comparison.png)

EV tạo net kỳ vọng {ev['expected_net_value']:,.2f} so với risk-only {risk['expected_net_value']:,.2f}; chênh {ev['expected_net_value']-risk['expected_net_value']:,.2f} ĐVTT trong kịch bản này. Precision targeting đo mức tập trung churn, không trực tiếp đo giá trị kinh tế. Risk-only có thể precision cao hơn nhưng bỏ qua giá trị khách hàng.

`label_based_simulated_net` thay p bằng nhãn test, vẫn dùng q giả định. Đây là mô phỏng hồi cứu, không phải lợi nhuận quan sát được. Nhãn test không tham gia chọn khách hàng.

![Risk value](figures/risk_value.png)

Ngưỡng high-risk/high-value dùng percentile 75 trên validation và khóa cho test. Không nhầm nhóm này với risk_band low/medium/high phục vụ hiển thị. [Danh sách chọn](tables/targeting_ev.csv) có chi phí, EV, lý do, model_version và scenario_id.

## 9. Độ nhạy và ngân sách

![Fixed](figures/sensitivity_fixed.png)

Fixed giữ danh sách của kịch bản chuẩn, cho phép thấy quyết định ban đầu nhạy thế nào khi giả định sai. Net dao động {fixed.expected_net_value.min():,.2f}–{fixed.expected_net_value.max():,.2f} ĐVTT. Khi chi phí tăng, danh sách có thể vượt ngân sách; cột budget_feasible thể hiện điều này.

![Retarget](figures/sensitivity_retarget.png)

Retarget chọn lại danh sách dưới ngân sách cho mỗi giả định; net dao động {grid.expected_net_value.min():,.2f}–{grid.expected_net_value.max():,.2f} ĐVTT. Đây là khoảng kịch bản, không phải khoảng tin cậy. Cột turnover dùng chênh lệch đối xứng chia hợp hai danh sách, bằng 0 khi danh sách không đổi.

![Budget](figures/budget_curve.png)

Trong lưới 21 điểm, EV đạt net lớn nhất lần đầu tại ngân sách {best_curve.budget:,.0f} ĐVTT, giá trị {best_curve.expected_net_value:,.2f}. Không gọi đây là cực trị liên tục. Khi không còn EV dương, thêm ngân sách không bắt buộc tăng chi tiêu. Điểm hòa vốn cấp khách hàng nằm trong bảng targeting: q*=cost/(p×V), c*=p×q×V; q*>1 không khả thi, mẫu số 0 trả NA.

Xem [sensitivity đầy đủ](tables/sensitivity.csv) cho margin 20/30/40%, horizon 6/12/18 tháng và hệ số tenure đồng nhất; [budget curve](tables/budget_curve.csv) có chi phí thực và số người chọn.

## 10. Chính sách phân khúc và công bằng

27 chính sách gán ưu đãi theo tenure được so sánh trên validation; lựa chọn khóa là `{policy['policy']}`. Nếu cả ba nhóm cùng ưu đãi hoặc multi-offer không tăng net, đó là kết quả hợp lệ; không sửa giả định để tạo câu chuyện tốt hơn.

{table(fair.loc[fair.strategy.eq('ev'), ['attribute','group','n','small_sample','selection_rate','recall','brier','calibration_gap']])}

![Phân bổ](figures/fairness_selection.png)

Các nhóm có thể khác nhau về chọn ưu đãi, recall và calibration. Chênh lệch không tự chứng minh phân biệt đối xử, nhưng loại bỏ demographic khỏi features cũng không bảo đảm công bằng. Chính sách ưu tiên giá trị có thể ít phục vụ khách hàng giá trị thấp. Doanh nghiệp cần cân nhắc cam kết dịch vụ, trải nghiệm nhất quán và quyền từ chối liên hệ.

## 11. Khuyến nghị quản lý

Ưu tiên xem EV dưới ngân sách cùng với độ nhạy, thay vì chỉ chọn khách hàng churn cao. Với cấu hình chuẩn, danh sách {ev['selected_count']} người là phương án tham khảo có thể xuất và kiểm tra. Không coi save rate 20% là điều đã biết; cần xác thực trước khi dự báo lợi ích cho chiến dịch thật. Khi tham số thay đổi, kiểm tra cả fixed và retarget để hiểu rủi ro của quyết định cũ và phương án điều chỉnh.

Không ép tiêu hết ngân sách. So sánh ngân sách tăng thêm với giá trị tăng thêm. Nếu không có EV dương, kết quả phù hợp là không triển khai theo các giả định hiện tại. [Executive brief](executive-brief.md) và [playbook](../docs/retention-playbook.md) phục vụ người ra quyết định.

## 12. Giới hạn

Dữ liệu mô phỏng học thuật; không có phân bổ ưu đãi ngẫu nhiên nên không thực hiện hoặc tuyên bố causal uplift. Random split không kiểm định khả năng dự báo tương lai. Thời điểm quan sát một số đặc trưng có thể không tương ứng thời điểm lập chiến dịch thực. Proxy giá trị và save rate cần kiểm chứng; chưa mô hình hóa tác dụng phụ, hành vi lặp lại hay chi phí vận hành toàn chiến dịch. Khoảng bootstrap không bao gồm mọi bất định mô hình/kinh doanh. CSV mới cần tuân schema và điều kiện sử dụng mô hình.

## 13. Kịch bản demo

1. Mở dashboard; giới thiệu câu hỏi kinh doanh và 5 KPI.
2. Giải thích dữ liệu demo là test giữ riêng và mọi giá trị tiền là mô phỏng.
3. Mở Lập chiến dịch; so EV với risk-only trên cùng ngân sách.
4. Đổi save rate từ 20% xuống 10%; đọc thay đổi danh sách và net.
5. Đổi chi phí hoặc ngân sách; chỉ ra trường hợp không dùng hết ngân sách.
6. Mở Kịch bản; tính fixed/retarget và xem profit curve.
7. Xem quality/calibration và SHAP, nêu giới hạn giải thích.
8. Nhập CSV mẫu không nhãn; chuyển nguồn, chấm điểm và xuất ZIP.
9. Kết thúc bằng khuyến nghị cần xác thực giả định trên dữ liệu thực tế.

## 14. Dàn ý slide và danh mục bằng chứng

| Slide | Thông điệp | Bằng chứng |
| --- | --- | --- |
| 1 | Quyết định giữ chân dưới ngân sách | Câu hỏi kinh doanh |
| 2 | Nguồn và chất lượng dữ liệu | Source/cleaning log |
| 3 | Nhóm rủi ro khác nhau | EDA contract/tenure |
| 4 | Thiết kế kiểm định đáng tin | Split, CV, calibration |
| 5 | So sánh mô hình, chọn mô hình | Validation/test metrics |
| 6 | Cách diễn giải đặc trưng | SHAP, coefficients |
| 7 | Từ xác suất sang giá trị | Công thức V và EV, bảng giả định |
| 8 | EV so với quy tắc đơn giản | Strategy comparison |
| 9 | Thay đổi khi giả định thay đổi | Sensitivity fixed/retarget |
| 10 | Ngân sách và phân khúc | Budget curve, policy search |
| 11 | Công bằng và giới hạn | Fairness, model card |
| 12 | Đề xuất và demo sản phẩm | Dashboard, targeting, playbook |

Mỗi hình PNG có nhãn tập dữ liệu và run. [Catalog hình](figures/catalog.json) chứa metadata. Toàn bộ bảng gốc ở `reports/tables/`; các scenario đầy đủ ở run artifacts. Khi viết slide, giữ phân biệt kỳ vọng, mô phỏng dùng nhãn và kết quả thực tế. Không bỏ dòng giả định khỏi biểu đồ tiền.
"""
    write(ROOT / "reports/analysis-report.md", report_text)
    notebooks(run)
    write_json(ROOT / "reports/report-manifest.json", {"run_id": run.name, "scenario_id": ev["scenario_id"], "figure_count": len(catalog), "executive_brief_words": len(brief.split()), "report_source": str(run.relative_to(ROOT))})
    return ROOT / "reports/analysis-report.md"
