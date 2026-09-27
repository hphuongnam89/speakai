# Audit sau giai đoạn 4–6 — 26/09/2026

## Kết luận ngắn

Code hiện đã có vertical slice cho blueprint sampler, official attempt và server-side rubric scoring, nhưng **chưa đủ điều kiện pilot thi thật**. Lý do chính là official exam hiện mới nhận file audio, chưa có browser recorder/preflight/timebox, chưa có test chuyên biệt và chưa có ngưỡng đạt/queue chấm chính thức.

## Đã phát hiện và sửa trong lần audit này

1. Blueprint publication còn kiểm descriptor theo CEFR thay vì band `0–4`.
2. Blueprint form không chấp nhận các field mở rộng `selection_rules`/`max_points` dù model đã có.
3. Selected snapshot chưa giữ `max_points` thực tế của slot.
4. Sinh viên chưa có đường vào blueprint official đã publish trên dashboard.
5. `required_tags` dùng giao của tập tag thay vì yêu cầu đủ tất cả tag.
6. Official attempt/audio chưa khóa hoàn toàn ở model layer:
   - snapshot/owner có thể bị sửa trực tiếp;
   - audio có thể bị xóa.
7. Official scorer cho phép payload thiếu/thừa criterion và có thể chấm lại attempt đã final.
8. Rubric draft thiếu descriptor được phép lưu; chỉ chặn khi publish, đúng với workflow draft hiện tại.
9. Đặc tả đã được cập nhật để phản ánh trạng thái triển khai thực tế.

## Gap còn lại — ưu tiên P0

### P0. Bổ sung test chuyên biệt cho official flow

Hiện test suite có 39 test và pass bằng SQLite, nhưng **chưa có test nào chứa `ExamAttempt`, `exam_start`, `exam_submit` hoặc `score_official_attempt`**.

Cần thêm test cho:

- student chỉ bắt đầu blueprint thuộc course đã ghi danh;
- blueprint retired/draft không được cấp đề;
- attempt lưu snapshot và không sửa được owner/question snapshot;
- câu hỏi chỉ lấy từ version approved;
- upload audio đúng MIME/signature và chặn audio giả;
- không upload lại/không xóa answer;
- không submit thiếu câu;
- sau submit không upload/sửa/mở lại;
- student/teacher/admin phân quyền nghe audio;
- scorer tính đúng band, weight, task max;
- scorer phân biệt band `0` với `unscorable`;
- scorer từ chối criterion thiếu/thừa và chấm lại attempt final.

### P0. Official recording chưa phải luồng thu âm trực tuyến

`exam_detail.html` hiện dùng file picker. Trường `duration_seconds` được gửi từ client và UI đang gửi giá trị mặc định `1`.

Cần:

- tái sử dụng recorder WebM hiện có của practice;
- thêm preflight microphone/playback/network cho official;
- lưu server-side `started_at`, `submitted_at`, deadline từng câu và deadline toàn bài;
- kiểm tra duration thực tế từ audio/container thay vì tin hidden input;
- xử lý refresh, mất mạng, resume và chống submit sau deadline.

### P0. Chưa có threshold/pass-fail chính thức

`ExamAttempt.threshold` đã tồn tại nhưng:

- chưa được nhập từ cấu hình blueprint/course;
- chưa snapshot một quy định ngưỡng cụ thể;
- chưa tính `passed`/`failed`;
- chưa hiển thị kết quả đạt/không đạt.

Không được công bố điểm chính thức trước khi chốt quy định học phần và cách làm tròn.

## Gap còn lại — ưu tiên P1

### P1. Blueprint chưa enforce cấu trúc GT1/Ngữ âm theo đặc tả

Sampler đã hỗ trợ rule và metadata, nhưng chưa có schema validator cho các rule chính thức. Chưa enforce tự động:

- GT1: A=1, B=4 thuộc 2 topic, C1=1, C2=2;
- B: mỗi topic có đúng một câu mô tả/thói quen và một câu mở rộng/lý do;
- Ngữ âm: 10 từ, 10 câu, 2 đoạn;
- cân bằng âm đích, loại câu, độ dài, trọng âm;
- các trọng số rubric riêng của từng task theo bảng đặc tả.

Nên tạo `BlueprintType`/`selection_rules_schema` và validator theo loại blueprint thay vì để JSON tự do.

### P1. Chấm điểm nên dùng criterion key ổn định

Scorer hiện map criterion bằng `name`. Tên hiển thị không nên là khóa dữ liệu. Nên thêm `criterion_key` bất biến, ví dụ `pronunciation`, `fluency`, `task_achievement`, rồi dùng key trong payload và snapshot.

### P1. Chưa có queue review chính thức

Đã có URL review theo `attempt_id`, nhưng chưa có:

- danh sách bài chờ chấm;
- lọc theo course/status/date;
- hiển thị rubric/answer evidence thuận tiện;
- lịch sử quyết định và hiệu chỉnh;
- cơ chế một giảng viên claim/lock attempt khi nhiều người cùng chấm.

### P1. Chưa có audit event cho official attempt

Rubric và blueprint có audit event, nhưng official attempt chưa ghi event cho:

- issued;
- answer uploaded;
- submitted;
- review started;
- scored;
- correction/appeal.

Nên thêm `ExamAuditEvent` bất biến trước pilot.

### P1. Cần quyết định policy chấm lại

Hiện attempt final bị chặn chấm lại. Nếu cần appeal/correction, phải tạo model quyết định hiệu chỉnh mới thay vì sửa record cũ; giữ điểm cũ, actor, reason và diff.

## Gap còn lại — ưu tiên P2

- Acoustic/pronunciation engine và calibration chưa có.
- Chưa có kiểm tra quality audio, silence/clipping và transcript provenance.
- Chưa có retention/deletion policy cho audio official.
- Chưa có chống upload file độc hại ngoài MIME/signature cơ bản.
- Chưa có PostgreSQL integration test/migration rehearsal trong môi trường gần production.
- Nhiều file working tree có thay đổi chưa commit và có một số thư mục untracked tên bất thường; cần lập commit/checkpoint sạch trước khi tiếp tục.

## Verification

- `python3 manage.py check`: pass.
- `python3 manage.py makemigrations --check --dry-run`: `No changes detected`.
- `python3 -m py_compile core/*.py core/migrations/*.py`: pass.
- `python3 manage.py test core` với settings tạm SQLite: **39 tests, OK**.
- PostgreSQL thật tại `127.0.0.1:55433` chưa chạy nên chưa xác nhận được migration history và behavior PostgreSQL.
- `git diff --check` hiện báo nhiều trailing whitespace ở các file đã tồn tại trong working tree; đây là vấn đề hygiene/line-ending của diff hiện tại, không phải Django system check.

## Thứ tự làm tiếp theo đề xuất

1. Viết test official flow và scoring.
2. Hoàn thiện official recorder + preflight + timebox.
3. Chốt threshold/pass-fail và snapshot policy.
4. Enforce GT1/Ngữ âm blueprint schema.
5. Thêm review queue và ExamAuditEvent.
6. Chạy migration/test trên PostgreSQL thật rồi mới pilot.
