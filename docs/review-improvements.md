# Cải tiến sau review — 04/10/2026

Áp dụng skill `karpathy-guidelines`: tập trung từng điểm review, dùng chung logic tính toán và kiểm chứng bằng kiểm thử lỗi tái hiện. Không đổi quy tắc chọn mô hình, không tối ưu lại theo kết quả test. Không gửi ưu đãi thực hay kết nối CRM.

## Đối chiếu thay đổi

| Điểm review | Thay đổi | Bằng chứng |
| --- | --- | --- |
| Tham số mất khi chuyển trang | Lưu trạng thái widget theo phiên, bao gồm ngân sách, giả định, bộ lọc và ưu đãi phụ; đổi run thì khởi tạo theo cấu hình mới | AppTest và Chrome; ngân sách 1.000/KPI 45 người giữ nguyên qua trang mô hình |
| Giả định giao diện/báo cáo ghi cứng | Mặc định UI từ bundle; báo cáo, caption và notebook dùng cấu hình run; tên mô hình và ngân sách cũng đọc từ kết quả | Test cấu hình margin 45%, horizon 6, chi phí 35+4, save rate 35%; test báo cáo với Random Forest và ngân sách khác chi tiêu |
| CSV dịch vụ mâu thuẫn, gắn nhãn unseen quá mạnh | Kiểm tra quan hệ PhoneService/MultipleLines và InternetService/sáu dịch vụ; đối chiếu ID với registry của mô hình | Test từ chối theo dòng/cột; cảnh báo overlap trên Chrome; prediction_origin phân biệt train/validation/test/không thấy ID/chưa xác minh |
| Sensitivity luôn dùng ưu đãi chuẩn | Truyền đúng tập ưu đãi/chính sách hiện tại; fixed giữ cả khách hàng và ưu đãi, retarget tối ưu lại | Test campaign–sensitivity và budget curve; công khai reference_scenario_id, solver_status/gap, turnover và assignment_turnover |
| Báo cáo EDA còn chung chung | Diễn giải bằng tỷ lệ churn, cỡ mẫu, chênh lệch điểm phần trăm và hàm ý hành động; giữ cảnh báo không nhân quả | [Hồ sơ phân tích](../reports/analysis-report.md), mục 3 |
| Lý do chọn khách hàng chưa cụ thể | Hiển thị p × q × V − chi phí, EV và save rate hòa vốn; phân biệt không triển khai/EV âm/ngân sách/tổ hợp tối ưu | Test tính tay, phần giải thích trên dashboard và decision_detail trong CSV |
| Baseline chưa xét kinh tế | Thêm risk_positive_ev: bỏ EV ≤0 rồi xếp theo rủi ro, cùng ngân sách/ưu đãi | [Bảng so sánh](../reports/tables/strategy_comparison.csv) và kiểm thử baseline |
| Chưa thể hiện bất định kinh tế | Bootstrap ghép cặp 1.000 lần trên test, cố định chính sách và giả định; có chênh EV với risk_positive_ev | [Bảng kinh tế](../reports/tables/economic_uncertainty.csv), báo cáo mục 9; test tái lập và chênh bằng 0 với chính sách giống nhau |

## Kết quả chạy thật

Run `20261003T183647103688Z-88be4b93`, scenario chuẩn `765d0287b0f6`. Ngân sách 3.080 ĐVTT trên 1.409 khách hàng test:

- EV chọn 140 người, giá trị ròng kỳ vọng **2.859,22 ĐVTT**.
- Risk-only: **1.709,33 ĐVTT**; risk-only sau lọc EV dương: **1.792,56 ĐVTT**.
- Chênh EV so với đối chứng đã lọc: **1.066,65 ĐVTT** theo xác suất mô hình và giả định chuẩn.
- Đối chiếu metric mô hình và ID targeting chuẩn với lần chạy trước vẫn khớp; không thay kết quả để làm đẹp báo cáo.

Bootstrap kinh tế dùng nhãn churn lịch sử, không phải cùng đại lượng với EV dùng xác suất ở trên. Nó phản ánh biến thiên lấy mẫu khi giữ chính sách và giả định cố định, không bao gồm bất định save rate/hiệu quả can thiệp; không được trình bày là khoảng tin cậy lợi nhuận thật. Sensitivity nhiều ưu đãi thay save rate theo cùng mức dịch chuyển điểm phần trăm, có chặn [0,1]—đây cũng là giả định mô phỏng được công khai.

## Kiểm chứng và sử dụng

71 kiểm thử qua; 4 notebook chạy tuần tự; pipeline đầu cuối, kiểm tra checksum, liên kết tài liệu và Chrome local đều qua. Chi tiết, thời gian đo và ảnh giao diện tại [hồ sơ nghiệm thu](verification.md).

Chạy dashboard theo [README](../README.md); nếu đang mở giao diện cũ, tải lại trang. Tham số được giữ trong phiên, không được cam kết giữ khi đóng phiên/tải lại trình duyệt. Phiên bản Streamlit tối thiểu được nâng lên 1.65, trùng dependency lock đã nghiệm thu.

Code, tài liệu và kết quả nghiệm thu của bản cải tiến được quản lý cùng nhau trong Git; xem lịch sử commit trên nhánh `main` để truy vết phiên bản bàn giao.
