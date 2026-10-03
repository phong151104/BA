# Kiến trúc và quy trình tái lập

## Luồng dữ liệu

Raw CSV + source manifest → validation/cleaning → stratified split cố định → features/preprocessing trong train fold → CV search → OOF calibration → chọn trên validation → test → scorecard → value/EV/optimizer → sensitivity/fairness → dashboard/báo cáo.

`data.py` kiểm tra đầu vào và tạo features; `modeling.py` huấn luyện, calibration, scoring và giải thích; `business.py` giữ toàn bộ công thức/solver; `analysis.py` tạo các thí nghiệm; `reporting.py` tạo tài liệu, hình và notebook. Dashboard gọi lại các hàm này, không sao chép công thức sang giao diện.

## Ranh giới kiểm định

Median/scaler/encoder fit trong fold train. RandomizedSearchCV chọn siêu tham số trên train, CalibratedClassifierCV ensemble=False học calibrator từ dự đoán OOF. Validation chọn candidate, ngưỡng F1, high/high cutoff và chính sách tenure. Test chỉ đánh giá. Bootstrap lấy mẫu lại test với mô hình cố định; không là nested model uncertainty.

SHAP dùng native XGBoost TreeSHAP (`pred_contribs`) và đóng gói `shap.Explanation`; tổng các đóng góp cùng base value khôi phục logit dự đoán của XGBoost gốc. Cách này tránh phụ thuộc bộ đọc JSON của SHAP với các phiên bản XGBoost mới. Giải thích không nhân quả.

## Tối ưu và baseline

EV đơn ưu đãi, chi phí bằng nhau: greedy theo EV là tối ưu. Chi phí khác nhau/nhiều ưu đãi: MILP binary, tối đa một ưu đãi mỗi người và tổng cost ≤budget. Chỉ EV dương là ứng viên. MILP có hạn 30 giây; kiểm tra nghiệm nguyên/ngân sách trước dùng; không có nghiệm hợp lệ thì ratio greedy có nhãn heuristic.

Baseline risk/value/random không lọc EV dương vì quy tắc của chúng không xét kinh tế. Đây là lựa chọn có chủ ý để so sánh. Random gồm 100 seed; kết quả lưu từng lần để kiểm tra độ biến thiên.

Fixed sensitivity giữ ID được chọn của baseline. Khi tăng cost, chiến dịch fixed có thể vượt ngân sách; `budget_feasible=False` phản ánh điều này. Retarget tối ưu lại và luôn nằm trong ngân sách. Turnover là Jaccard distance giữa hai danh sách. Lưới budget không được gọi là tìm cực trị liên tục.

## Giao diện dữ liệu và tham số

Đầu vào scoring là dataframe sau `validate` hoặc `parse_upload`. `score_frame` chỉ `predict_proba`; missing số dùng median train để tính giá trị. `campaign` trả `(targeting_dataframe, summary_dict)` chứa scenario và solver status. `fixed_campaign`, `sensitivity`, `budget_curve` dùng cùng công thức.

Tham số ở configs/default.yaml. Dashboard sửa bản sao trong phiên; không thay file cấu hình. Currency ĐVTT chỉ là đơn vị dữ liệu, không chuyển đổi. Source/manifest checksum truy vết raw và code; run ID phân biệt lần chạy. Artifact pickle/joblib chỉ từ pipeline được tin cậy, không nhận model upload.

## Tái lập và vòng đời artifact

Python 3.13 và requirements.lock.txt khóa môi trường. Run mới lưu riêng dưới artifacts/runs. latest.json chỉ trỏ tới run được train gần nhất. `evaluate`, `simulate`, `report` cần chạy theo thứ tự trên run đó; nếu thiếu bước, dashboard báo thiếu kết quả thay vì giả dữ liệu.

Run ID/thời điểm thay đổi mỗi lần, còn split, metrics và quyết định lặp lại theo seed. Sai số float được kiểm tra bằng tolerance, không yêu cầu checksum model nhị phân giống hệt. Các báo cáo hiển thị run hiện tại; artifacts các run trước được giữ. Các script QA không tự huấn luyện lại.

## Phạm vi thực hiện

Không có API server riêng, DB, authentication, CRM, gửi campaign thật hoặc hosting. Dữ liệu upload nằm trong session. Bộ reports là Markdown, CSV, PNG và notebook; Word/PDF/slide do người biên tập sử dụng kết quả để hoàn thiện.
