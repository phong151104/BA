# Hướng dẫn sử dụng

## Chạy trên Windows

Mở terminal tại thư mục BA và dùng lệnh trong [README](../README.md). Dùng trực tiếp `.venv\Scripts\python.exe`, không cần activate hoặc thay đổi chính sách PowerShell.

## Các trang

1. **Tổng quan:** dữ liệu đang xem, 5 KPI, rủi ro × giá trị và danh sách hành động.
2. **Lập chiến dịch:** ngân sách, cost, save rate, margin/horizon, hệ số tenure, phân khúc đủ điều kiện và loại chính sách. Tham số mặc định lấy từ cấu hình mô hình; thay đổi giữ nguyên khi chuyển trang trong phiên. Ngân sách lưu riêng cho demo/CSV; khi run mô hình đổi, giả định được khởi tạo lại. So sánh thêm với risk_positive_ev: lọc EV không dương rồi xếp theo rủi ro.
3. **Kịch bản và ngân sách:** bấm tính để chạy sensitivity theo đúng chính sách đang chọn, kể cả nhiều ưu đãi hoặc tenure đã khóa. Fixed giữ nguyên cả khách hàng và ưu đãi; retarget tối ưu lại. Đường active_policy biểu diễn chính sách hiện tại. Nếu tham số đổi, ứng dụng báo biểu đồ cũ và yêu cầu tính lại.
4. **Chất lượng mô hình:** luôn là kết quả test của dự án, không phải metric của CSV người dùng. Có calibration, PR/ROC, threshold, bootstrap, SHAP và fairness.
5. **Nhập dữ liệu:** tải mẫu không nhãn, chọn CSV, xem lỗi và bảng điểm. Sau khi nhập, chuyển nguồn ở thanh bên sang CSV đã nhập.
6. **Phương pháp:** công thức, kiểm định, định nghĩa và giới hạn.

## Nhập CSV

UTF-8 hoặc UTF-8 BOM, dấu phẩy; tối đa 10 MB / 50.000 dòng. Xem [mẫu](../data/examples/customers_unlabeled.csv) và [từ điển](data-dictionary.md). Cần customerID duy nhất. Không cần Churn/gender/SeniorCitizen. Nếu có Churn, nó chỉ phục vụ phân tích có nhãn, không làm feature hoặc quyết định lựa chọn.

Các cột số có thể thiếu giá trị hợp lệ và sẽ được điền bằng median train. Chuỗi số không hợp lệ, số âm/vô hạn, cột thiếu, ID trùng/rỗng hoặc phân loại ngoài miền làm toàn lần nhập bị từ chối. Không nhập một phần. Nếu nhập lỗi, nguồn dữ liệu trước đó vẫn được giữ.

Các cột dịch vụ phải nhất quán: PhoneService=No yêu cầu MultipleLines=No phone service (và ngược lại). InternetService=No yêu cầu cả sáu dịch vụ Internet là No internet service (và ngược lại). Ví dụ không có điện thoại nhưng MultipleLines=Yes sẽ bị báo lỗi theo dòng/cột.

CSV được xử lý trong phiên, không tự thêm vào dữ liệu huấn luyện. `prediction_origin` phân biệt uploaded_matches_train_do_not_evaluate, uploaded_matches_validation, uploaded_matches_test và uploaded_not_in_reference. `reference_split` lưu split của ID trong dữ liệu mô hình. Không có registry đối chiếu thì dùng uploaded_unverified. So khớp ID không xác minh nội dung/thời điểm; ID mới không đủ chứng minh mẫu độc lập. Không dùng CSV trùng train để công bố hiệu quả ngoài mẫu. Chỉ dùng test giữ riêng để báo hiệu quả kiểm định chính thức.

## Cách đọc và xuất kết quả

KPI chỉ cộng khách hàng `selected=True`. Các dòng không được chọn vẫn có EV/chi phí của phương án tiềm năng. Lọc phân khúc đủ điều kiện làm chạy lại tối ưu; tìm ID/chỉ xem selected trong bảng không thay chiến dịch.

Mở “Vì sao chọn hoặc không chọn khách hàng này?” để xem p, q, giá trị còn lại, chi phí, EV và save rate hòa vốn. Đây là giải thích kinh tế, không phải nguyên nhân gây churn.

Trong độ nhạy nhiều ưu đãi, trục save rate là mức tiêu chuẩn; các ưu đãi khác thay đổi cùng số điểm phần trăm và chặn [0,1]. Hệ số chi phí áp dụng cho mọi ưu đãi nhưng không đổi phí liên hệ. `turnover` đo thay đổi ID; `assignment_turnover` đo thay đổi cặp khách hàng–ưu đãi. Fixed có thể vượt ngân sách hoặc EV âm; đây là kiểm tra độ bền, không phải danh sách mới khả thi.

Trang chất lượng mô hình có bảng bootstrap kinh tế của kịch bản chuẩn trên test. Bảng giữ nguyên chính sách và giả định, dùng nhãn churn lịch sử; không áp dụng cho tham số/CSV hiện tại, không bao gồm bất định save rate và không phải khoảng tin cậy lợi nhuận thực.

ZIP xuất gồm toàn bảng targeting, danh sách chọn và JSON giả định/tóm tắt. Scenario ID gắn với tham số và nội dung tập khách hàng. Không có email/điện thoại hoặc chức năng gửi ưu đãi thật.

Ngân sách 0 vẫn có thể chọn ưu đãi miễn phí nếu EV dương. Không có EV dương thì không chọn; chi phí 0 thì ROI hiển thị N/A. Ưu đãi nhiều mức dùng solver; trạng thái timeout/fallback không được hiểu là đã chứng minh tối ưu.

## Khắc phục lỗi

| Hiện tượng | Cách xử lý |
| --- | --- |
| `No module named telco_retention` | Dùng đúng Python .venv và `pip install --no-deps -e .` |
| Chưa có artifact | Chạy `python -m telco_retention run-all` |
| Cổng 8501 đang dùng | Đóng tiến trình của lần chạy trước hoặc dùng `--server.port 8502` |
| CSV đọc lỗi | Xuất UTF-8 comma-separated, theo file mẫu; đọc bảng lỗi từng cột |
| Checksum raw khác | Kiểm tra nguyên nhân sửa tệp; khôi phục bản đúng hoặc lưu nguồn mới có manifest riêng; pipeline không tự ghi đè |
| Mô hình và thư viện không tương thích | Tạo venv Python 3.13, cài dependency lock; huấn luyện lại nếu đổi môi trường |
| Đang chạy sensitivity lâu | Chờ solver; hạn mỗi bài toán 30 giây, trạng thái kết quả được ghi rõ |
| Biểu đồ kịch bản cũ | Bấm tính lại khi ngân sách/giả định/nguồn thay đổi |

## Nội dung nộp

Người viết báo cáo bắt đầu từ [hồ sơ phân tích](../reports/analysis-report.md), dùng hình trong reports/figures và bảng reports/tables. Không tách con số lợi nhuận khỏi giả định. Executive brief Markdown là bản nội dung; người biên tập kiểm tra tối đa hai trang ở bản cuối.
