# Hồ sơ nghiệm thu

Nghiệm thu bản cải tiến ngày **04/10/2026** (Asia/Bangkok), trên Windows, Python **3.13.5**. Run nghiệm thu: `20261003T183647103688Z-88be4b93` (ID theo UTC). Pipeline được chạy lại trong `.venv-check`, môi trường riêng đã được cài từ `requirements.lock.txt` ở đợt nghiệm thu 03/10; đợt này tái sử dụng môi trường đó, không tạo venv mới. [Đối chiếu các điểm review](review-improvements.md).

## Kết quả

| Hạng mục | Bằng chứng | Kết quả |
| --- | --- | --- |
| Dependency lock | Cài venv mới và `pip check` | Thành công, không dependency hỏng |
| Pipeline đầu cuối | `python -m telco_retention run-all` trong venv mới | Hoàn tất từ raw đến báo cáo |
| Kiểm thử dữ liệu/mô hình/kinh doanh/giao diện/báo cáo | [pytest XML](../artifacts/qa/pytest.xml) | 71 kiểm thử qua |
| Notebook tuần tự | [notebooks.json](../artifacts/qa/notebooks.json) | Cả 4 notebook qua |
| Tái lập mô hình | [release.json](../artifacts/qa/release.json) | Các test metrics khớp lần chạy đầu ở tolerance số học; ID targeting giống nhau |
| Kiểm tra hình và báo cáo | [manifest báo cáo](../reports/report-manifest.json) | 14 hình, executive brief 535 từ; kiểm tra liên kết local không hỏng |
| Trình duyệt thực | [browser.json](../artifacts/qa/browser.json) | Chrome headless local; dashboard, thay ngân sách, sensitivity, upload hợp lệ/sai và tải ZIP đều qua |
| Scoring dòng lệnh | [example_scores.csv](../artifacts/qa/example_scores.csv) | CSV không nhãn được chấm điểm thành công |
| Hiệu năng thao tác thông thường | AppTest sau warm-up, 5 lần đổi ngân sách | Mỗi rerun dưới 2 giây; số đo chính xác của lần kiểm tra cuối trong release.json |

Số đo hiệu năng là AppTest cục bộ, không phải độ trễ mạng trình duyệt hoặc thời gian chạy toàn bộ sensitivity/MILP. MILP có giới hạn 30 giây mỗi bài toán và công khai trạng thái nghiệm.

## Các trường hợp được kiểm tra

- Missing TotalCharges, ID trùng/rỗng, miền phân loại sai, số âm/vô hạn và CSV vượt giới hạn.
- Không dùng ID/target/demographic audit làm features; median chỉ học từ train; các split không trùng ID.
- Lưu/nạp model bảo toàn dự đoán; nhãn Churn không thay đổi scoring/targeting.
- Tổng TreeSHAP và base value khôi phục xác suất XGBoost gốc trong sai số số học.
- EV tính tay, ngân sách 0/thiếu, save rate 0, margin 0, EV âm, ưu đãi miễn phí, tie-break.
- MILP đối chiếu duyệt toàn bộ bài toán nhỏ; nghiệm timeout không hợp lệ chuyển heuristic; không vượt ngân sách, không chọn hai ưu đãi cho một người.
- Fixed và retarget được phân biệt; CSV xuất khớp KPI.
- Tất cả trang Streamlit, đổi ngân sách/save rate, CSV không nhãn, lọc bảng không đổi KPI, phân khúc rỗng và artifact chưa hoàn tất.
- Kiểm tra Chrome: biểu đồ thực sự render, ngân sách 0 làm KPI chọn về 0, khôi phục ngân sách, tải ZIP và kiểm tra nội dung, upload CSV hợp lệ/sai.
- Giữ ngân sách/save rate/hệ số tenure/bộ lọc/chính sách qua các trang không có widget chiến dịch; giữ ưu đãi phụ sau khi ẩn/hiện. Chrome kiểm tra riêng ngân sách 1.000 và KPI 45 người sau khi quay lại trang.
- Giao diện và nội dung báo cáo đọc cấu hình run đã thay đổi (không ghi cứng margin, chi phí, save rate hay tên mô hình); phân biệt ngân sách với chi tiêu.
- Dịch vụ điện thoại/Internet mâu thuẫn bị từ chối; CSV trùng ID train/validation/test được gắn nguồn đúng, không tự gọi là unseen.
- Sensitivity nhiều ưu đãi và tenure policy trùng chiến dịch đang chọn; fixed giữ cặp khách hàng–ưu đãi; solver/turnover được công khai.
- Đối chứng risk_positive_ev và bootstrap kinh tế ghép cặp có kiểm thử tính đúng, tái lập và trường hợp hai chiến lược giống nhau.

Trong kiểm tra đồng thời với pipeline mới, đã phát hiện trang chất lượng mô hình có thể đọc fairness.csv trước khi simulate hoàn tất. Đã sửa để dashboard kiểm tra dấu hoàn tất simulation và hiển thị hướng dẫn khi thiếu artifact; có kiểm thử regression tương ứng.

Ở đợt cải tiến, AppTest chưa phát hiện hết khác biệt giữa giá trị Python và ô nhập khi trình duyệt dựng lại widget. Kiểm tra Chrome bắt được ô ngân sách hiển thị 0 sau khi quay lại dù phía Python giữ 1.000. Đã chuyển sang cơ chế `persist_state="session"` của Streamlit 1.65 (đã khóa trong dependencies), rồi chạy lại cả AppTest và Chrome thành công.

## Ảnh giao diện

- [Tổng quan](../artifacts/qa/dashboard-home.png)
- [Lập chiến dịch](../artifacts/qa/dashboard-campaign.png)
- [Chất lượng mô hình](../artifacts/qa/dashboard-model.png)
- [Độ nhạy](../artifacts/qa/dashboard-sensitivity.png)
- [Nhập CSV](../artifacts/qa/dashboard-upload.png)

Browser tích hợp không có kết nối khả dụng trong phiên. Kiểm tra trình duyệt được thực hiện bằng Chrome local headless qua script `scripts/browser_qa.py`; không truy cập profile hoặc session trình duyệt cá nhân.

## Đối chiếu đầu ra đề bài

| Nhóm đầu ra | Vị trí |
| --- | --- |
| Code, notebook, README tái lập | src/, notebooks/, README.md, requirements.lock.txt |
| Data dictionary và nhật ký | docs/data-dictionary.md, source-log.md, cleaning-log.md |
| Executive brief | reports/executive-brief.md |
| Dashboard 5 KPI và hành động | app/Home.py |
| Model/analysis card | docs/model-card.md |
| Scorecard và targeting | reports/tables/scorecard.csv, targeting_ev.csv |
| Playbook | docs/retention-playbook.md |
| Bonus boosting/giải thích | XGBoost, SHAP và permutation artifacts |
| Bonus profit/budget | reports/tables/budget_curve.csv và hình tương ứng |
| Bonus phân khúc/công bằng | validation_policy_search.csv, segment_policy.json, fairness.csv |
| Hồ sơ cho người viết báo cáo/slide | reports/analysis-report.md và catalog hình/bảng |

## Giới hạn bàn giao

Word/PDF/PowerPoint không được tạo theo lựa chọn của người dùng; người biên tập dùng Markdown và kiểm tra executive brief tối đa hai trang khi dàn trang. Không triển khai cloud, CRM hoặc gửi ưu đãi. Toàn bộ lợi ích giữ chân là mô phỏng, không phải lợi nhuận thực đo.
