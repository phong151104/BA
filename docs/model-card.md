# Model / Analysis Card

## Nhận diện và mục đích

Run `20261003T183647103688Z-88be4b93`; mô hình `logistic` + sigmoid calibration. Hỗ trợ phân loại churn và ưu tiên mô phỏng giữ chân trong một capstone. Không tự động liên hệ khách hàng.

## Target và dữ liệu

Target Churn Yes/No của IBM Telco sample; dữ liệu mô tả churn trong giai đoạn lịch sử gần nhất, không có chuỗi thời gian để xác nhận dự báo tương lai. Nguồn thực tế Kaggle, 7043 khách hàng; checksum `88be4b93fbe0cc83421af1c503794c97c342eca914c1576db7c276e61d61358a`.

## Features

Partner, Dependents, tenure, PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies, Contract, PaperlessBilling, PaymentMethod, MonthlyCharges, TotalCharges, tenure_band, addon_count, monthly_contract, autopay.

customerID và Churn không là features. gender/SeniorCitizen chỉ dùng audit. Numeric median + scaling, categorical imputation + one-hot. Tất cả bộ biến đổi được học trong fold train.

## Validation và chọn mô hình

Train/validation/test: {'train': 4225, 'validation': 1409, 'test': 1409}. Stratified random split, seed 42. CV 5 fold trên train, AP làm mục tiêu; calibration dùng OOF. Chọn calibrated AP trong 0.01 của tốt nhất, Brier trong 0.002 của tốt nhất trong nhóm đó, ưu tiên Logistic → Random Forest → XGBoost. Không chọn theo test và không refit toàn dataset.

Ngưỡng F1 validation: 0.35, chỉ cho metric phân loại. Targeting dùng EV và ngân sách. Các metric theo ngưỡng của mô hình khác trong bảng test dùng chung ngưỡng này, không phải ngưỡng tối ưu riêng của từng model.

## Kết quả test

| model                    |   average_precision |   roc_auc |   brier |   log_loss |   precision |   recall |    f1 |
|:-------------------------|--------------------:|----------:|--------:|-----------:|------------:|---------:|------:|
| dummy_raw                |               0.265 |     0.500 |   0.195 |      0.579 |       0.000 |    0.000 | 0.000 |
| logistic_raw             |               0.619 |     0.831 |   0.142 |      0.432 |       0.545 |    0.709 | 0.616 |
| logistic_calibrated      |               0.619 |     0.831 |   0.142 |      0.432 |       0.544 |    0.709 | 0.616 |
| random_forest_raw        |               0.629 |     0.831 |   0.141 |      0.433 |       0.552 |    0.687 | 0.612 |
| random_forest_calibrated |               0.629 |     0.831 |   0.143 |      0.439 |       0.587 |    0.652 | 0.618 |
| xgboost_raw              |               0.633 |     0.831 |   0.141 |      0.432 |       0.545 |    0.706 | 0.615 |
| xgboost_calibrated       |               0.633 |     0.831 |   0.143 |      0.440 |       0.576 |    0.615 | 0.595 |

[Khoảng bootstrap 95%](../reports/tables/bootstrap_intervals.csv), 1,000 lần. Chất lượng calibration không được giả định luôn cải thiện; so sánh raw/calibrated được công bố đầy đủ.

## Giả định và giới hạn

Save rate, margin, horizon, hệ số tenure và chi phí là giả định có thể chỉnh. Không dùng uplift nhân quả vì không có chiến dịch ngẫu nhiên. Giá trị mô phỏng không chứng minh tác động thực của ưu đãi. Dữ liệu mẫu không đại diện cho mọi doanh nghiệp; random split chưa kiểm định temporal drift. Proxy giá trị không phải CLV được xác thực. Không dùng kết quả in-sample để báo hiệu quả.

## Đạo đức, thiên lệch và trải nghiệm

[Fairness audit](../reports/tables/fairness.csv) báo selection rate, recall, calibration và lỗi theo nhóm. Loại gender/SeniorCitizen khỏi features không loại bỏ proxy bias. Nhóm <50 được gắn nhãn mẫu nhỏ. Chính sách theo EV có thể ít tiếp cận khách hàng giá trị thấp; quản lý phải cân nhắc cam kết dịch vụ, tính nhất quán ưu đãi và quyền từ chối liên hệ.

## Giải thích

SHAP thuộc XGBoost gốc, log-odds, mẫu validation 200 người. Không phân rã xác suất calibrated và không giải thích nhân quả. Có hệ số Logistic và permutation importance của hai mô hình cây.

## Vận hành

Chỉ nạp artifact do dự án tạo; joblib không dùng cho tệp mô hình người dùng upload. CSV mới không huấn luyện lại mô hình. Khi có dữ liệu thật, cần đánh giá theo thời gian và thử nghiệm chiến dịch phù hợp trước ứng dụng thực tế. Phiên bản dependency và checksum code lưu trong run manifest.
