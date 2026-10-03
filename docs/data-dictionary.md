# Từ điển dữ liệu

| Trường           | Ý nghĩa                                            | Kiểu/đơn vị   | Miền/missing                                                                       | Vai trò   |
|:-----------------|:---------------------------------------------------|:--------------|:-----------------------------------------------------------------------------------|:----------|
| customerID       | Mã định danh khách hàng; khóa, không làm feature   | chuỗi/nhóm    | duy nhất, không rỗng                                                               | khóa      |
| gender           | Giới tính ghi nhận; chỉ dùng audit                 | chuỗi/nhóm    | Male; Female                                                                       | audit     |
| SeniorCitizen    | Cờ khách hàng cao tuổi; chỉ dùng audit             | chuỗi/nhóm    | 0; 1                                                                               | audit     |
| Partner          | Có bạn đời                                         | chuỗi/nhóm    | Yes; No                                                                            | feature   |
| Dependents       | Có người phụ thuộc                                 | chuỗi/nhóm    | Yes; No                                                                            | feature   |
| tenure           | Số tháng đã gắn bó                                 | số/tháng      | không âm; missing → median train                                                   | feature   |
| PhoneService     | Đăng ký dịch vụ điện thoại                         | chuỗi/nhóm    | Yes; No                                                                            | feature   |
| MultipleLines    | Nhiều đường dây điện thoại                         | chuỗi/nhóm    | Yes; No; No phone service                                                          | feature   |
| InternetService  | Loại dịch vụ Internet                              | chuỗi/nhóm    | DSL; Fiber optic; No                                                               | feature   |
| OnlineSecurity   | Bảo mật trực tuyến                                 | chuỗi/nhóm    | Yes; No; No internet service                                                       | feature   |
| OnlineBackup     | Sao lưu trực tuyến                                 | chuỗi/nhóm    | Yes; No; No internet service                                                       | feature   |
| DeviceProtection | Bảo vệ thiết bị                                    | chuỗi/nhóm    | Yes; No; No internet service                                                       | feature   |
| TechSupport      | Hỗ trợ kỹ thuật                                    | chuỗi/nhóm    | Yes; No; No internet service                                                       | feature   |
| StreamingTV      | Xem TV trực tuyến                                  | chuỗi/nhóm    | Yes; No; No internet service                                                       | feature   |
| StreamingMovies  | Xem phim trực tuyến                                | chuỗi/nhóm    | Yes; No; No internet service                                                       | feature   |
| Contract         | Thời hạn hợp đồng                                  | chuỗi/nhóm    | Month-to-month; One year; Two year                                                 | feature   |
| PaperlessBilling | Hóa đơn điện tử                                    | chuỗi/nhóm    | Yes; No                                                                            | feature   |
| PaymentMethod    | Phương thức thanh toán                             | chuỗi/nhóm    | Electronic check; Mailed check; Bank transfer (automatic); Credit card (automatic) | feature   |
| MonthlyCharges   | Phí hàng tháng                                     | số/ĐVTT       | không âm; missing → median train                                                   | feature   |
| TotalCharges     | Tổng phí lịch sử; không cộng vào giá trị tương lai | số/ĐVTT       | không âm; missing → median train                                                   | feature   |
| Churn            | Nhãn rời bỏ trong dữ liệu mẫu; không làm feature   | chuỗi/nhóm    | Yes; No                                                                            | target    |

## Trường phát sinh

| Trường                                 | Kiểu/đơn vị           | Ý nghĩa                                                                          |
|:---------------------------------------|:----------------------|:---------------------------------------------------------------------------------|
| churn                                  | int 0/1               | Nhãn ánh xạ từ Churn; không làm feature                                          |
| split                                  | train/validation/test | Vai trò dòng trong kiểm định                                                     |
| tenure_band / tenure_segment           | new/developing/loyal  | ≤12; 13–24; >24 tháng. Feature và phân khúc                                      |
| addon_count                            | int 0–6               | Tổng dịch vụ thêm có giá trị Yes                                                 |
| monthly_contract                       | 0/1                   | Hợp đồng Month-to-month                                                          |
| autopay                                | 0/1                   | Thanh toán automatic                                                             |
| customer_id                            | string                | Bí danh customerID trong bảng kết quả                                            |
| churn_probability                      | float [0,1]           | Xác suất calibrated                                                              |
| risk_band                              | low/medium/high       | ≤0.25; (0.25,0.5]; >0.5; chỉ mô tả, khác ngưỡng high/high                        |
| prediction_origin                      | string                | in_sample_do_not_evaluate / selection_holdout / untouched_test / uploaded_unseen |
| model_version                          | string                | Run ID gắn artifact mô hình                                                      |
| remaining_months                       | tháng                 | min(cap, horizon × hệ số tenure)                                                 |
| customer_value                         | ĐVTT                  | MonthlyCharges × margin × remaining_months                                       |
| offer_id                               | string                | light/standard/intensive                                                         |
| assumed_save_rate                      | [0,1]                 | Giả định giữ lại một người vốn sẽ churn                                          |
| offer_cost / contact_cost / total_cost | ĐVTT                  | Chi phí cố định mỗi người được chọn; total là tổng hai thành phần                |
| expected_saved_probability             | [0,1]                 | churn_probability × assumed_save_rate                                            |
| expected_retained_value                | ĐVTT                  | expected_saved_probability × customer_value                                      |
| expected_net_value                     | ĐVTT                  | expected_retained_value − total_cost                                             |
| selected                               | bool                  | Quyết định chọn; chỉ tổng hợp KPI cho selected=True                              |
| selection_reason                       | string                | Lý do lựa chọn/không chọn                                                        |
| scenario_id                            | string                | Hash cấu hình, ngân sách và tập khách hàng                                       |
| break_even_save_rate                   | tỷ lệ hoặc NA         | cost/(p × V); NA khi p × V = 0; >1 nghĩa không hòa vốn được                      |
| break_even_total_cost                  | ĐVTT                  | p × q × V                                                                        |
| customer_index                         | int nội bộ            | Vị trí khách hàng để ràng buộc tối đa một ưu đãi                                 |

Chuỗi rỗng TotalCharges → missing; tenure=0 → điền 0. Các số thiếu khác dùng median train, cả khi tính giá trị kinh doanh. Các trường phân loại bắt buộc không nhận missing. Các trạng thái không có dịch vụ là giá trị hợp lệ. Tiền dùng ĐVTT, không quy đổi VND.
