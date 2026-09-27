# Chuyển đổi đề giấy sang ngân hàng câu hỏi online — v0.1

Ngày: 27/09/2026  
Trạng thái: **draft để giảng viên rà soát; chưa phải ngân hàng chính thức**

## 1. Nguồn đã đối chiếu

- GT1: `đề thi giấy/2. Giao tiếp 1 NNA - Đề 1 (VĐ).pdf`, Đề 2, Đề 3.
- GT1 đáp án: ba file tương ứng trong `đáp án/`.
- Ngữ âm: `đề thi giấy/Preparing name… (15).pdf` đến `(17).pdf`; `(18)`–`(20)` là các bản đáp án/biên bản tương ứng.
- Các file scan được đối chiếu trực quan; text extraction tự động không đáng tin cậy cho nhóm PDF này.

## 2. Quyết định chuyển đổi

### GT1

Đề giấy có:

- Task 1A: giới thiệu bản thân.
- Task 1B: câu hỏi ngắn theo chủ đề.
- Task 2: làm việc theo cặp với tranh.

Bản online giữ Task 1A và Task 1B nhưng chuyển thành từng lượt ghi âm cá nhân. Câu hỏi Yes/No được mở rộng bằng yêu cầu chi tiết/lý do để AI có đủ bằng chứng; câu phụ thuộc ngữ cảnh được viết thành câu độc lập.

Task 2 không nhập nguyên trạng dưới tên `pair work`, vì trình duyệt hiện chưa có lượt đối thoại hai chiều được kiểm soát. Bản v0.1 chưa tự sinh prompt từ tranh; các tranh cần được cấp phép/lưu thành asset, gắn `image_group`, rồi mới đưa vào C1/C2. Đây là gap cần rà soát riêng.

### Ngữ âm

Giữ ba nhóm của đề giấy:

- 10 từ đọc aloud;
- 10 câu đọc với ngữ điệu;
- 2 đoạn đọc.

Mỗi mục trở thành một recording unit độc lập để dễ căn chỉnh âm thanh, nhận dạng lời đọc và chấm theo criterion riêng. Không phát audio mẫu trước khi chấm. Metadata lưu loại câu, nhóm âm tiết, số từ và paper set để sampler cân bằng.

## 3. Các thay đổi ngôn ngữ có chủ ý

- `What do you do at the weekend?` → `What do you usually do on weekends?`
- `How long does it take?` → `How long does your usual journey to school or work take?`
- Các câu Yes/No được bổ sung một chi tiết/lý do nhưng vẫn giữ chủ đề và trình độ mục tiêu.
- Không ép câu trả lời phải giống đáp án mẫu; đáp án mẫu chỉ là evidence anchor.

## 4. Kết quả draft

- 21 mục GT1: 1 self-introduction + 20 short Q&A.
- 66 mục Ngữ âm: 30 từ + 30 câu + 6 đoạn.
- Tất cả item có `source_reference`, `source_notes`, `criterion_refs` và `exam_metadata`.
- Không item nào được tự động chuyển `Approved`.

## 5. Quy trình nhập an toàn

```text
JSON draft
  → import command
  → QuestionVersion = draft
  → giảng viên kiểm tra nội dung/nguồn/metadata
  → gửi duyệt
  → reviewer độc lập duyệt
  → Approved
  → blueprint sampler mới được dùng
```

Lệnh GT1:

```bash
python manage.py import_gt1_paper_questions
```

Lệnh Ngữ âm:

```bash
python manage.py import_paper_question_drafts \
  --path data/question_bank/pronunciation_online_drafts.json \
  --course PRONUNCIATION
```

Nếu mã học phần Ngữ âm trong database khác `PRONUNCIATION`, thay giá trị `--course` tương ứng. Chạy `seed_demo` hoặc tạo user/course trước khi import.

## 6. Việc chưa được phép tự động hóa

- Chưa đưa tranh giấy vào hệ thống vì cần kiểm tra quyền sử dụng và chất lượng ảnh.
- Chưa tạo đáp án âm vị/neo acoustic tự động từ chữ viết.
- Chưa coi đáp án PDF là ground truth duy nhất cho mọi biến thể phát âm.
- Chưa nhập `Approved`; giảng viên phải rà soát trước khi dùng official exam.
