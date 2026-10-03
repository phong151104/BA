# Profit-Aware Telecom Churn & Retention Targeting

## 1. Câu hỏi kinh doanh

> Với ngân sách giữ chân khách hàng có hạn, nên gửi ưu đãi cho những khách hàng nào khi đồng thời xem xét cả rủi ro rời bỏ và giá trị kinh tế kỳ vọng?

Mục tiêu không chỉ là dự đoán khách hàng nào có khả năng rời bỏ, mà còn phải xác định **ai nên được ưu tiên tiếp cận để tối đa hóa giá trị giữ chân ròng trong phạm vi ngân sách**.

## 2. Dữ liệu chính

- Sử dụng bộ dữ liệu mẫu **IBM Telco Customer Churn**, thường được phân phối qua Kaggle.
- Đây là dữ liệu của một doanh nghiệp viễn thông giả lập, phù hợp cho mục đích giảng dạy và thực hành phân tích churn.
- Nhóm có thể tự tạo một bảng dữ liệu tổng hợp minh bạch về:
  - chi phí ưu đãi;
  - khả năng khách hàng phản hồi với ưu đãi;
  - các tham số cần thiết cho mô phỏng kinh doanh.
- Mọi giá trị giả định phải được ghi rõ, giải thích và đưa ra dưới dạng tham số có thể thay đổi.

> Lưu ý: URL chính xác của bộ dữ liệu, ngày tải và phiên bản/tệp đã sử dụng phải được ghi vào nhật ký nguồn dữ liệu của dự án.

## 3. Các nhiệm vụ cốt lõi

1. Thực hiện EDA về churn và xác định các phân khúc khách hàng có hồ sơ rủi ro/giá trị khác nhau.
2. Xây dựng và hiệu chỉnh xác suất một khách hàng sẽ rời bỏ.
3. Xây dựng chỉ số đại diện đơn giản cho giá trị khách hàng dựa trên:
   - thời gian gắn bó (`tenure`);
   - mức phí (`charges`);
   - các giả định về giá trị còn lại của khách hàng.
4. Thiết kế quy tắc lựa chọn khách hàng cho chiến dịch giữ chân dựa trên giá trị kỳ vọng và ngân sách cố định.
5. Phân tích độ nhạy theo:
   - chi phí ưu đãi;
   - xác suất giả định rằng ưu đãi sẽ giữ lại được một khách hàng vốn có khả năng rời bỏ.

## 4. Phạm vi tối thiểu bắt buộc (baseline)

### 4.1. Mô hình dự đoán

- Logistic Regression.
- Ít nhất một mô hình dựa trên cây.
- So sánh hiệu quả giữa các mô hình bằng cùng một thiết kế kiểm định.

### 4.2. Hiệu chỉnh và ngưỡng quyết định

- Đánh giá mức độ hiệu chỉnh của xác suất dự đoán.
- Phân tích các ngưỡng phân loại/ra quyết định thay vì mặc định sử dụng một ngưỡng cố định.

### 4.3. Bộ mô phỏng lựa chọn khách hàng theo giá trị kỳ vọng

Xây dựng bộ mô phỏng so sánh ít nhất hai chiến lược:

1. lựa chọn dựa trên mô hình và giá trị kinh tế kỳ vọng;
2. lựa chọn theo một quy tắc đơn giản, ví dụ chỉ ưu tiên khách hàng có rủi ro churn cao nhất.

Việc so sánh phải được thực hiện dưới cùng ngân sách hoặc cùng quy mô chiến dịch.

## 5. Hạng mục mở rộng (không bắt buộc/điểm cộng)

- Sử dụng gradient boosting kết hợp SHAP hoặc phương pháp giải thích đóng góp của đặc trưng.
- Xây dựng đường cong lợi nhuận và/hoặc tối ưu ngân sách cho nhiều quy mô chiến dịch.
- Thiết kế chính sách giữ chân riêng theo từng phân khúc, kèm thảo luận về tính công bằng hoặc trải nghiệm khách hàng.

## 6. Chỉ số thành công

### 6.1. Hiệu quả dự đoán

- PR-AUC.
- ROC-AUC.
- Chất lượng hiệu chỉnh xác suất.

### 6.2. Hiệu quả lựa chọn khách hàng

- Precision trong nhóm khách hàng được liên hệ.
- Mức độ bao phủ nhóm khách hàng vừa có rủi ro cao vừa có giá trị cao.

### 6.3. Hiệu quả kinh doanh

- Giá trị giữ chân ròng hoặc khoản tiết kiệm kỳ vọng theo các giả định đã công bố.
- Khoảng kết quả trong các kịch bản độ nhạy, thay vì chỉ báo cáo một con số duy nhất.

## 7. Sản phẩm bàn giao

### 7.1. Churn scorecard và bảng targeting cấp khách hàng

Bảng kết quả tối thiểu nên cho biết, ở cấp khách hàng:

- xác suất churn dự đoán;
- giá trị khách hàng ước tính;
- giá trị giữ chân kỳ vọng;
- chi phí ưu đãi giả định;
- quyết định có/không đưa vào chiến dịch;
- lý do hoặc nhóm ưu tiên.

### 7.2. Retention playbook

Tài liệu hướng dẫn triển khai chiến dịch phải mô tả:

- quy mô chiến dịch;
- ngân sách;
- giả định về ưu đãi;
- logic tính giá trị kỳ vọng;
- quy tắc ưu tiên khách hàng;
- cách diễn giải kết quả phân tích độ nhạy.

### 7.3. Management dashboard

Dashboard phục vụ quản lý cần thể hiện:

- rủi ro churn;
- giá trị khách hàng;
- các phân khúc mục tiêu;
- kết quả phân tích độ nhạy;
- một góc nhìn cho phép ra quyết định về quy mô hoặc ngân sách chiến dịch.

## 8. Giới hạn phạm vi bắt buộc

1. **Không tuyên bố quan hệ nhân quả hoặc thực hiện uplift modeling nhân quả từ bộ dữ liệu này.** Dữ liệu không chứa một chiến dịch giữ chân được phân bổ ngẫu nhiên.
2. Đây là dữ liệu mẫu phục vụ giảng dạy. Báo cáo phải thảo luận giới hạn về khả năng khái quát kết quả sang doanh nghiệp hoặc khách hàng thực tế.
3. Tỷ lệ giữ chân thành công giả định (`save rate`) và chi phí ưu đãi phải là các tham số hiển thị rõ ràng, không được ẩn dưới dạng hằng số cố định trong code.

## 9. Tiêu chí hoàn thành đề tài

- [ ] Đã xác định rõ quyết định kinh doanh và giới hạn ngân sách.
- [ ] Đã hoàn thành EDA theo rủi ro và giá trị khách hàng.
- [ ] Đã xây dựng Logistic Regression và ít nhất một mô hình cây.
- [ ] Đã đánh giá PR-AUC, ROC-AUC và calibration.
- [ ] Đã xây dựng proxy cho giá trị khách hàng và ghi rõ giả định.
- [ ] Đã so sánh targeting theo giá trị kỳ vọng với quy tắc đơn giản.
- [ ] Đã chạy sensitivity analysis cho chi phí ưu đãi và save rate.
- [ ] Đã tạo churn scorecard/bảng targeting cấp khách hàng.
- [ ] Đã hoàn thiện retention playbook và management dashboard.
- [ ] Không có tuyên bố nhân quả không được dữ liệu hỗ trợ.
- [ ] Đã thảo luận giới hạn về external validity.

