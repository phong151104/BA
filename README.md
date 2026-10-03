# Retention Lab — Telecom Churn & Retention Targeting

Sản phẩm Business Analytics capstone: dự báo churn, hiệu chỉnh xác suất, mô phỏng ưu đãi theo giá trị kỳ vọng và tối ưu ngân sách. Dashboard tiếng Việt chạy local trên Windows, có nhập CSV và xuất chiến dịch.

## Bắt đầu nhanh

Đã có dữ liệu Kaggle, mô hình huấn luyện, kết quả phân tích và báo cáo trong thư mục dự án. Python **3.13**; chạy các lệnh sau tại thư mục gốc.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false
```

Mở **http://127.0.0.1:8501**. Nếu môi trường `.venv` đã được cài sẵn, chỉ cần chạy lệnh Streamlit cuối. Không cần activate môi trường hoặc đổi Execution Policy PowerShell.

## Tài liệu đọc trước

- [Hồ sơ phân tích đầy đủ cho người viết báo cáo/slide](reports/analysis-report.md)
- [Executive brief Markdown](reports/executive-brief.md)
- [Mục lục tài liệu](docs/README.md)
- [Model/analysis card](docs/model-card.md)
- [Retention playbook](docs/retention-playbook.md)
- [Hướng dẫn sử dụng và xử lý lỗi](docs/user-guide.md)
- [Kiến trúc và khả năng tái lập](docs/implementation.md)
- [Hồ sơ nghiệm thu](docs/verification.md)

## Chạy lại toàn bộ phân tích

```powershell
.\.venv\Scripts\python.exe -m telco_retention run-all
```

Quy trình: download/checksum → làm sạch/split → EDA và huấn luyện → calibration và chọn mô hình trên validation → đánh giá test → giải thích → mô phỏng/sensitivity → báo cáo/biểu đồ/notebook. Mỗi lần train tạo một run mới; `artifacts/latest.json` trỏ tới run hiện tại. Không xóa các run trước.

Có thể chạy riêng từng bước, theo thứ tự:

```powershell
.\.venv\Scripts\python.exe -m telco_retention download
.\.venv\Scripts\python.exe -m telco_retention prepare
.\.venv\Scripts\python.exe -m telco_retention train
.\.venv\Scripts\python.exe -m telco_retention evaluate
.\.venv\Scripts\python.exe -m telco_retention simulate
.\.venv\Scripts\python.exe -m telco_retention report
.\.venv\Scripts\python.exe -m telco_retention score --input data/examples/customers_unlabeled.csv --output artifacts/example_scores.csv
```

Dashboard nạp artifact, không huấn luyện trong mỗi lần thao tác. Sau `run-all`, báo cáo và hình cập nhật theo run mới. Kết nối mạng chỉ cần cho cài package và tải dữ liệu lần đầu; khi có dữ liệu/artifact, phân tích và demo có thể chạy offline.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/verify_notebooks.py
```

Kiểm tra trình duyệt cục bộ (tùy chọn, cần Chrome/Edge và dashboard đang chạy):

```powershell
.\.venv\Scripts\python.exe scripts/browser_qa.py
```

`requirements.lock.txt` bao gồm công cụ QA để tái lập môi trường đã nghiệm thu. Nếu cài từ pyproject không có lock, dùng `pip install -e ".[browser]"` cho kiểm thử trình duyệt. Kết quả QA và ảnh giao diện ở `artifacts/qa/`.

## Cấu hình và giả định

`configs/default.yaml` chứa seed, số fold/bootstrap, giới hạn solver, margin, horizon, hệ số tenure và ưu đãi. Giá trị tiền dùng ĐVTT của dữ liệu, không quy đổi VND.

`EV = p(churn) × save_rate × customer_value − offer_cost − contact_cost`.

Save rate và giá trị còn lại là giả định. Không có chiến dịch ngẫu nhiên nên không ước lượng causal uplift. Dữ liệu là sample, không bảo đảm khái quát cho doanh nghiệp thật. Mọi bảng so sánh chính dùng test giữ riêng; điểm in-sample được gắn nhãn riêng.

## Cấu trúc

| Thư mục | Vai trò |
| --- | --- |
| `src/telco_retention` | Dữ liệu, mô hình, tối ưu, mô phỏng và báo cáo |
| `configs` | Giả định và cấu hình dùng chung |
| `data` | Raw bất biến, processed và CSV mẫu |
| `app` | Dashboard Streamlit |
| `artifacts/runs` | Các phiên bản mô hình/kết quả và manifest |
| `reports` | Hồ sơ Markdown, bảng CSV và hình PNG |
| `notebooks` | 4 notebook diễn giải và kiểm tra kết quả |
| `docs` | Yêu cầu, phương pháp, hướng dẫn và nghiệm thu |
| `tests`, `scripts` | Kiểm thử tự động và QA |

Báo cáo Word/PDF và slide do người biên tập hoàn thiện từ Markdown. Executive brief cần kiểm tra lại giới hạn hai trang sau khi dàn trang.
