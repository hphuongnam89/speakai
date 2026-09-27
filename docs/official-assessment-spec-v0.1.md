# Đặc tả thi trực tuyến và rubric — v0.1

Ngày: 26/09/2026  
Trạng thái: **bản đặc tả để phê duyệt/pilot**, chưa phải quy chế điểm chính thức.

## 1. Phạm vi và nguyên tắc khóa

- Áp dụng thử cho **Giao tiếp 1 (GT1)** và **Ngữ âm thực hành**.
- CEFR là dải mục tiêu của học phần/slot; band rubric là thang bằng chứng **0–4**, không phải CEFR.
- Chỉ câu hỏi/ảnh/đoạn đã duyệt mới được chọn vào đề.
- Mỗi lượt thi phải gắn một snapshot bất biến của blueprint, câu hỏi, rubric và đáp án.
- `0` là có bằng chứng nhưng không đáp ứng; `unscorable` là không đủ bằng chứng kỹ thuật hoặc tín hiệu không hợp lệ.
- Các tỷ lệ, thời lượng và ngưỡng trong bản này cần được phê duyệt trước khi dùng điểm chính thức.

## 2. Blueprint GT1

| Phần | Task type | Số lượng | Điểm tối đa | Chuẩn bị / trả lời đề xuất |
|---|---|---:|---:|---|
| A | Giới thiệu bản thân theo ba ý | 1 thẻ | 2 | 15 / 45 giây |
| B | Hỏi–đáp ngắn | 4 câu, thuộc 2 chủ đề | 4 | 10 / 40 giây mỗi câu |
| C1 | Mô tả tranh | 1 tranh | 2 | 60 / 60 giây |
| C2 | Câu hỏi tiếp nối | 2 câu gắn với tranh | 2 | 10 / 30 giây mỗi câu |

- Tổng điểm: 10; tỷ lệ A:B:C là 20:40:40.
- B phải chọn hai chủ đề; trong mỗi chủ đề có một câu mô tả/thói quen và một câu mở rộng/lý do.
- C1 và C2 không được gọi là `pair work`; cấu trúc hiện tại đo mô tả và phản hồi, chưa đo tương tác hai chiều với bạn thi.
- Nếu chuẩn đầu ra bắt buộc tương tác, phải thiết kế task riêng với lượt hỏi–đáp đã duyệt.

## 3. Blueprint Ngữ âm thực hành

| Phần | Nội dung | Số lượng | Điểm tối đa |
|---|---|---:|---:|
| Đọc từ | Cân bằng từ một, hai, ba và từ nhiều âm tiết; có âm đích/cụm phụ âm | 10 từ | 3 |
| Đọc câu | Câu trần thuật, Yes/No và Wh; cân bằng âm đích và độ dài | 10 câu | 3 |
| Đọc đoạn | Hai đoạn cùng nhóm độ dài/độ khó, mục tiêu thử nghiệm 40–60 từ | 2 đoạn | 4 |

- Từ nhiều âm tiết: độ chính xác âm 2/3, trọng âm từ 1/3.
- Từ một âm tiết: toàn bộ điểm cho âm đích, không chấm vị trí trọng âm.
- Đọc câu: âm 30%, trọng âm câu 25%, ngữ điệu theo ngữ cảnh 30%, nhịp/ngắt cụm 15%.
- Đọc đoạn: âm 30%, trọng âm/ngữ điệu 25%, trôi chảy 20%, ngắt cụm 15%, đọc đủ nội dung 10%.
- Không phát audio mẫu trước câu được chấm nếu mục tiêu là đọc.

## 4. Rubric band và tín hiệu

Mỗi criterion phải có đúng năm descriptor: band `0`, `1`, `2`, `3`, `4`. Mỗi criterion có `weight` dương; tổng weight trong một rubric phải bằng **100%**.

Nguồn tín hiệu được khóa bằng một trong các giá trị:

- `audio`: bằng chứng trực tiếp từ audio/tín hiệu âm học.
- `transcript`: bằng chứng từ bản chép lời được kiểm soát.
- `llm`: phân tích ngôn ngữ/nội dung do LLM thực hiện trên đầu vào đã kiểm soát.
- `combined`: kết hợp nhiều loại tín hiệu.
- `manual`: quyết định/hiệu chỉnh của giảng viên.

### GT1 — trọng số theo task

| Tiêu chí | A | B/C2 | C1 |
|---|---:|---:|---:|
| Phát âm dễ hiểu | 30% | 20% | 20% |
| Độ trôi chảy | 15% | 15% | 15% |
| Ngữ pháp | 15% | 20% | 15% |
| Từ vựng | 10% | 15% | 15% |
| Tổ chức ý | Không áp dụng | Không áp dụng | 10% |
| Hoàn thành nhiệm vụ | 30% | 30% | 25% |
| **Tổng** | **100%** | **100%** | **100%** |

### Ngữ âm — trọng số theo task

- Đọc từ: âm đích/trọng âm từ theo cấu hình từng từ.
- Đọc câu: 30/25/30/15 theo thứ tự âm, trọng âm câu, ngữ điệu, nhịp/ngắt cụm.
- Đọc đoạn: 30/25/20/15/10 theo thứ tự âm, trọng âm/ngữ điệu, trôi chảy, ngắt cụm, đọc đủ.

## 5. Công thức

- Band normalized = `band / 4 × 100`.
- Điểm task trên 100 = tổng `criterion_score × weight / 100`.
- Điểm đóng góp = `task_score / 100 × task_max_points`.
- Điểm bài trên thang 10 = tổng điểm đóng góp.
- Chỉ làm tròn điểm cuối đến hai chữ số; lưu thành phần chưa làm tròn.
- Ngưỡng đạt chưa được lấy từ PXU; phải nhập từ quy định học phần và snapshot cùng kỳ thi.

## 6. Trạng thái triển khai sau pilot slice

- Đã có official exam attempt với snapshot blueprint/question/rubric và audio answer bất biến sau khi nộp.
- Đã có sampler theo `selection_rules`, metadata và `content_family`; câu chính thức vẫn phải là câu đã duyệt, không sinh AI lúc bắt đầu thi.
- Đã có server-side scoring band 0–4, trọng số và trạng thái `unscorable`; quyết định điểm được lưu bất biến.
- Chưa có pronunciation engine hoặc acoustic calibration.
- Đã có browser preflight dùng micro/playback/network gate và timebox server-side cho official exam; bản hiện tại vẫn nhận file audio đã thu qua browser upload.
- Chưa tự động công bố điểm khi còn `unscorable`; giảng viên phải rà soát và quyết định.
- Ngưỡng đạt được cấu hình trên blueprint, snapshot vào attempt và dùng để tính `passed`; giá trị cụ thể vẫn phải được phê duyệt theo học phần.

## 7. Schema blueprint đã khóa

Blueprint có `assessment_type` gồm `custom`, `gt1` và `pronunciation`. Với `custom`, hệ thống chỉ áp dụng các validation chung. Với `gt1`, hệ thống bắt buộc đủ A/B/C1/C2, số lượng, task type, thời lượng, max points, hai topic và cấu trúc rubric theo task. Với `pronunciation`, hệ thống bắt buộc Đọc từ/Đọc câu/Đọc đoạn, số lượng, max points, phoneme targets, syllable groups, sentence types và dải 40–60 từ cho đoạn.

Schema validator chạy khi publish và được gọi lại khi sampler cấp đề, nên một blueprint sai cấu trúc không thể tạo official sample.
