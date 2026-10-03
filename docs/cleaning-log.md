# Nhật ký làm sạch

| Chỉ tiêu                     |   Giá trị |
|:-----------------------------|----------:|
| rows_before                  |      7043 |
| rows_after                   |      7043 |
| duplicates_removed           |         0 |
| total_charges_missing_before |        11 |
| total_charges_filled_zero    |        11 |
| unique_ids                   |      7043 |

Trim khoảng trắng; Churn Yes/No ánh xạ 1/0. TotalCharges trống đổi thành missing; trường hợp tenure=0 điền 0. Các số thiếu khác được median-impute trong pipeline fit trên train; giá trị kinh doanh dùng cùng median train lưu trong manifest. Giữ No internet service/No phone service. Không cắt bỏ outlier hợp lệ.

| Trường           |   Missing sau làm sạch |
|:-----------------|-----------------------:|
| customerID       |                      0 |
| gender           |                      0 |
| SeniorCitizen    |                      0 |
| Partner          |                      0 |
| Dependents       |                      0 |
| tenure           |                      0 |
| PhoneService     |                      0 |
| MultipleLines    |                      0 |
| InternetService  |                      0 |
| OnlineSecurity   |                      0 |
| OnlineBackup     |                      0 |
| DeviceProtection |                      0 |
| TechSupport      |                      0 |
| StreamingTV      |                      0 |
| StreamingMovies  |                      0 |
| Contract         |                      0 |
| PaperlessBilling |                      0 |
| PaymentMethod    |                      0 |
| MonthlyCharges   |                      0 |
| TotalCharges     |                      0 |
| Churn            |                      0 |
| churn            |                      0 |

Phân bố nhãn: {'0': 5174, '1': 1869}. Chia stratified seed 42, kích thước {'train': 4225, 'validation': 1409, 'test': 1409}. Các ID split lưu tại `data/processed/splits.csv`. Không nối nguồn khách hàng khác.
