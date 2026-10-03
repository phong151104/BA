# Retention playbook

## Quyết định chuẩn

Ngân sách 3,080 ĐVTT trên 1409 khách hàng test. Ưu đãi tiêu chuẩn: chi phí 20 + liên hệ 2 ĐVTT; save rate 20.0%. Biên đóng góp 30.0%; horizon cơ sở 12 tháng; hệ số new/developing/loyal 0.75/1/1.25; cap 24 tháng.

`V = MonthlyCharges × margin × min(cap, horizon × tenure factor)`

`EV = p(churn) × save rate × V − offer cost − contact cost`

Chi phí phát sinh cho tất cả người được chọn. Không cộng TotalCharges lịch sử vào V. Không dùng nhãn Churn để chọn người.

## Kết quả đề xuất

Chọn 140 người, chi phí 3,080, giá trị ròng kỳ vọng 2,859.22 ĐVTT. Scenario `765d0287b0f6`, run `20261003T183647103688Z-88be4b93`. Xem [targeting](../reports/tables/targeting_ev.csv).

## Thực hiện demo

1. Chọn dữ liệu demo test hoặc CSV đã được kiểm tra.
2. Xác định khách hàng đủ điều kiện và ngân sách.
3. Nhập các giả định chi phí, save rate, margin, horizon.
4. Kiểm tra danh sách, số tiền còn lại và trạng thái solver.
5. So sánh risk-only/value-only với EV dưới cùng ngân sách.
6. Kiểm tra độ nhạy fixed và retarget. Fixed vượt ngân sách là tình huống kiểm tra rủi ro, không phải chiến dịch khả thi mới.
7. Xuất ZIP chứa toàn bảng, danh sách chọn và JSON giả định.

## Quy tắc không chọn

EV ≤0 không được chiến lược EV chọn. Không ép dùng hết ngân sách. Baseline risk/value/random chỉ thực hiện quy tắc đơn giản nên có thể chọn EV âm. Đối chứng bổ sung risk_positive_ev loại EV ≤0 trước khi xếp theo rủi ro để tránh chỉ so với một quy tắc chưa xét kinh tế.

## Chính sách phân khúc

Chọn trong 27 cấu hình trên validation: {'new': 'standard', 'developing': 'standard', 'loyal': 'standard'}. Việc cả ba nhóm nhận cùng ưu đãi là một kết quả hợp lệ, không ép tạo khác biệt khi mô phỏng không hỗ trợ. Multi-offer và segment-policy được so sánh riêng trong báo cáo.

## Ngân sách và độ nhạy

Trong 21 điểm khảo sát, chiến lược EV đạt cực đại lần đầu ở ngân sách 11,836 ĐVTT với net 4,701.59; đây là kết quả của lưới, không tuyên bố cực trị liên tục. Phạm vi net retarget trong lưới cost/save: 0.00 đến 21,167.31. Fixed: -2,995.20 đến 13,168.04.

## Giới hạn áp dụng

Chỉ là mô phỏng học thuật. Nên xác thực chi phí và save rate bằng dữ liệu phù hợp, xem xét quyền liên hệ và trải nghiệm, rồi thiết kế đánh giá thực tế. Không diễn giải churn cao là bằng chứng khách hàng chắc chắn phản hồi tốt với ưu đãi.
