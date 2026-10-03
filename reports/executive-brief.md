# Executive brief — Giữ chân khách hàng theo giá trị

## Quyết định cần hỗ trợ

Doanh nghiệp cần lựa chọn khách hàng nhận ưu đãi trong một ngân sách cố định. Dự án kết hợp xác suất rời bỏ với giá trị đóng góp còn lại để tạo danh sách ưu tiên, thay vì chỉ xếp theo mức rủi ro. Phạm vi là mô phỏng học thuật trên dữ liệu IBM Telco tải từ Kaggle; không triển khai liên hệ thực tế.

## Dữ liệu và độ tin cậy

Bộ dữ liệu có 7,043 khách hàng. Dữ liệu được làm sạch và chia train, validation, test theo tỷ lệ 60/20/20. Mô hình Logistic Regression hiệu chỉnh sigmoid được chọn trên validation theo quy tắc đã định trước. Trên test, ROC-AUC đạt 0.831, Average Precision đạt 0.619 và Brier score đạt 0.142. Chỉ số phản ánh chất lượng phân loại lịch sử, chưa xác nhận khả năng dự báo trong tương lai.

## Kết quả kinh doanh mô phỏng

Kịch bản chuẩn có ngân sách 3,080 ĐVTT. Mỗi người nhận ưu đãi tiêu chuẩn phát sinh chi phí 22 ĐVTT; save rate giả định 20%. Giá trị khách hàng dùng phí tháng, biên đóng góp 30% và horizon cơ sở 12 tháng có điều chỉnh tenure. Chiến lược EV chọn 140 khách hàng và tạo net kỳ vọng 2,859 ĐVTT, so với 1,709 ĐVTT của risk-only. Chênh lệch 1,150 ĐVTT xuất phát từ việc ưu tiên đồng thời rủi ro và giá trị.

Precision của nhóm EV là 60.7%, thấp hơn hoặc khác chiến lược chỉ ưu tiên rủi ro nhưng cần đọc cùng giá trị kinh tế. Xác suất churn cao không đồng nghĩa mọi khách hàng đều đáng nhận ưu đãi như nhau. Tối ưu nhiều ưu đãi và chính sách tenure cũng được kiểm tra; báo cáo giữ nguyên kết quả khi chúng không cải thiện so với một ưu đãi chung.

## Khuyến nghị quản lý

Sử dụng danh sách EV làm phương án tham khảo, kiểm tra khả năng liên hệ và chất lượng dữ liệu trước khi áp dụng. Chỉnh save rate, chi phí và giá trị còn lại theo bối cảnh cụ thể. Không ép tiêu hết ngân sách nếu các khách hàng còn lại có EV không dương. Dashboard cho phép kiểm tra kịch bản và xuất danh sách kèm giả định để người khác rà soát.

## Độ nhạy và giới hạn

Trong lưới chi phí và save rate, net retarget thay đổi từ 0 đến 21,167 ĐVTT. Đây là khoảng kịch bản, không phải khoảng tin cậy của lợi nhuận. Save rate không được ước lượng từ chiến dịch ngẫu nhiên; giá trị khách hàng là proxy. Vì vậy không thể tuyên bố tác động nhân quả hay lợi nhuận thực thu. Dữ liệu mẫu và phép chia ngẫu nhiên còn hạn chế khả năng khái quát. Cần xem xét chênh lệch phân bổ ưu đãi giữa các nhóm và xác thực bằng dữ liệu thực tế.

Run `20261003T133607624165Z-88be4b93`; scenario `765d0287b0f6`. Nguồn số liệu: analysis-report.md và các bảng kèm theo. Người biên tập kiểm tra giới hạn hai trang sau khi dàn trang.
