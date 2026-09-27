# Đề xuất thi trực tuyến, sinh đề ngẫu nhiên và chấm AI

Ngày đối chiếu: 26/09/2026. Trạng thái: đề xuất chuyên môn v0.1, chưa công bố thành quy chế hoặc thay thế rubric đang dùng.

## 1. Tài liệu và kết quả đối chiếu

Đã đọc 12 PDF, 36 trang: ba đề và ba đáp án Giao tiếp 1; ba đề và ba đáp án Ngữ âm thực hành. Trong `đề thi giấy`, các tệp `Preparing name… (15)–(17)` là đề Ngữ âm số 1–3; `(18)–(20)` là đáp án tương ứng.

Đã xem trực tiếp danh sách rubric PXU và chi tiết SPEAKING-DEFAULT v3 tại https://assessment.pxu.edu.vn/admin/rubrics/3. Những điều quan sát được trên giao diện:

- Phát âm 20%, trôi chảy 20%, ngữ pháp 20%, từ vựng 15%, mạch lạc 10%, hoàn thành nhiệm vụ 15%.
- Tiêu chí AI có mô tả mức 0–4; điểm tiêu chí được đưa về 0–100 để tính trọng số.
- Phát âm/trôi chảy lấy tín hiệu âm học/tổng hợp; các tiêu chí ngôn ngữ/nội dung dùng LLM.
- Bản công bố chỉ đọc, thay đổi phải tạo phiên bản mới. Ngưỡng đạt đang cấu hình là 60/100.

Đây là quan sát giao diện, không phải kiểm chứng mã chấm hoặc độ chính xác thực nghiệm của PXU. Không suy luận công thức hiệu chỉnh chỉ từ nhãn “composite”.

Điểm kế thừa: phân nguồn tín hiệu, tiêu chí có mức điểm, trọng số cấu hình được, phiên bản bất biến. Điểm phải điều chỉnh: dùng rubric riêng theo nhiệm vụ; không áp tiêu chí ngữ pháp/từ vựng tự sản sinh cho bài đọc văn bản có sẵn; không yêu cầu câu trả lời ngắn phải có cấu trúc diễn ngôn như bài nói dài. Mô tả ngữ pháp giới hạn vào hiện tại đơn và mô tả hoàn thành nhiệm vụ theo “nhiều câu hỏi” trên PXU cần viết lại theo từng loại câu.

Ngưỡng 60 trên PXU không tự động trở thành ngưỡng đạt của hai học phần. Điểm đạt cần lấy từ quy định học phần và được lưu trong phiên bản kỳ thi. Không tự quy điểm 0–100 thành bậc CEFR.

## 2. Nguyên tắc thiết kế

1. AI xử lý/chấm bước đầu cho mọi bài nộp. Bài đủ bằng chứng có điểm tự động; bài không đủ bằng chứng được gắn cờ, không ép tạo điểm số.
2. Random là chọn từ ngân hàng đã duyệt theo ma trận cố định. AI có thể soạn câu nháp trước kỳ thi; không sinh câu chính thức tùy hứng lúc thí sinh bắt đầu.
3. Đề mới giữ tương đương về mục tiêu, mức khó, lượng nói, số phần và điểm tối đa. Khác nội dung không đồng nghĩa khác độ khó.
4. Điểm AI, điểm công bố và quyết định phúc khảo là các bản ghi riêng. Quyết định của người có thẩm quyền có ưu tiên cuối cùng và phải có lý do.
5. Mức 0 là có bằng chứng không đáp ứng tiêu chí; thiếu tín hiệu vì lỗi kỹ thuật là `unscorable`, không phải 0. Tiêu chí không áp dụng phải được quy định từ lúc công bố rubric, không tùy tiện bỏ sau khi chấm.

## 3. Giao tiếp 1 trực tuyến: đề xuất 10 điểm

Đề giấy hiện có tỷ lệ 1:2:2, tổng 5. Đề xuất trực tuyến giữ tỷ lệ 20:40:40 trên thang 10 (2:4:4); đây là thiết kế mới đề nghị, chưa xác nhận là cách quy đổi chính thức của đề giấy.

| Phần | Nhiệm vụ | Chọn ngẫu nhiên | Chuẩn bị / trả lời | Điểm |
|---|---|---|---|---:|
| A | Giới thiệu bản thân theo ba ý rõ ràng | Một thẻ tương đương | 15 / 45 giây | 2 |
| B | Bốn câu hỏi ngắn | Hai chủ đề; mỗi chủ đề một câu mô tả/thói quen và một câu mở rộng/lý do | 10 / 40 giây mỗi câu | 4 |
| C1 | Mô tả một tranh | Một tranh trong nhóm tương đương về số đối tượng, hành động và từ vựng | 60 / 60 giây | 2 |
| C2 | Hai câu hỏi tiếp nối về tranh hoặc liên hệ quen thuộc | Gắn với tranh, đã duyệt trước | 10 / 30 giây mỗi câu | 2 |

Tổng cửa sổ chuẩn bị/trả lời là 460 giây (7 phút 40 giây). Dự kiến 8–10 phút khi cộng phát câu hỏi và chuyển phần; kiểm tra mic nằm trước đồng hồ thi. Các thời lượng là đề xuất để thử nghiệm, không trích từ đề giấy. Cho nộp sớm và không trừ điểm chỉ vì không dùng hết thời gian.

Phần C mới đo mô tả và phản hồi câu hỏi. Nó không đo đầy đủ kỹ năng tương tác với bạn thi như đề giấy. Nếu chuẩn đầu ra bắt buộc tương tác hai chiều, cần một biến thể riêng: thí sinh hỏi AI theo vai, AI đáp bằng kịch bản đã duyệt, thí sinh hỏi tiếp/phản hồi. Chỉ khi đó mới dùng tiêu chí quản lý lượt lời; không giữ tên “pair work” cho bài độc thoại.

### Câu hỏi cần sửa và cách xử lý

| Vấn đề trong nguồn | Đề xuất |
|---|---|
| “What do you do at weekend?” | Sửa thành “What do you usually do on weekends?”; lưu cả bản gốc và bản hiệu đính |
| Câu chỉ yêu cầu Yes/No | Ví dụ đổi thành “Do you like watching TV? Tell me about a programme you like, or explain why you do not watch TV.”; bản sửa phải gắn độ khó mới, không coi tương đương tự động |
| “How long does it take?” phụ thuộc câu trước | Chọn cả cụm hỏi đường đi và thời gian, hoặc viết độc lập “How long does your usual journey to school or work take?” |
| Food/Transportation trùng giữa các đề | Gộp câu cùng nội dung bằng mã họ câu hỏi; giữ nhiều trích dẫn nguồn; không chọn hai bản gần trùng trong cùng đề |
| Nhà ở/cách đi lại không đúng hoàn cảnh thí sinh | Cho mô tả tình huống thường gặp hoặc giả định; không chấm tính xác thực đời tư |
| Tranh trượt tuyết khó hơn tranh sinh hoạt | Tạm không trộn vào cùng nhóm dễ; chấp nhận “people playing in the snow” nếu đáp ứng yêu cầu; bổ sung tranh gần gũi và thử độ khó |
| Mô tả cảm xúc, nghề nghiệp hoặc quan hệ không rõ từ ảnh | Đáp án cho phép suy đoán có đánh dấu “maybe/they look…”; không bắt buộc suy đoán của người ra đề |

Ngân hàng nguồn hiện có 20 câu hỏi ngắn khác nhau, 30 lượt xuất hiện. Cần mở rộng các loại câu trong từng chủ đề trước khi cam kết sinh nhiều đề cân bằng. Ngân hàng nhỏ vẫn có thể tạo tổ hợp, nhưng không bảo đảm không lặp giữa mọi lần thi.

### Rubric theo nhiệm vụ

| Tiêu chí | A: giới thiệu | B và C2: hỏi–đáp | C1: mô tả tranh |
|---|---:|---:|---:|
| Phát âm dễ hiểu | 30% | 20% | 20% |
| Độ trôi chảy | 15% | 15% | 15% |
| Ngữ pháp | 15% | 20% | 15% |
| Từ vựng | 10% | 15% | 15% |
| Tổ chức ý | Không áp dụng | Không áp dụng | 10% |
| Hoàn thành nhiệm vụ | 30% | 30% | 25% |
| Tổng | 100% | 100% | 100% |

Các tỷ trọng này là đề xuất chuyên môn. Ưu tiên thông điệp đúng và dễ hiểu; không yêu cầu từ vựng cầu kỳ hoặc ngữ pháp phức tạp để đạt tối đa ở nhiệm vụ cơ bản. C1 chấm chất lượng mô tả, C2 chấm từng câu phản hồi; không cộng điểm C1 lần nữa khi chấm C2.

### Mô tả mức điểm 0–4 để soạn rubric chính thức

Mỗi tiêu chí chọn một mức nguyên 0–4, với bằng chứng tương ứng. Mức 4 là hoàn thành tốt yêu cầu của nhiệm vụ đã công bố, không có nghĩa C1/C2 hay giống người bản ngữ.

| Tiêu chí | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|
| Phát âm | Thông điệp dễ hiểu xuyên suốt; lỗi nhỏ không cản trở hiểu | Nhìn chung dễ hiểu; vài từ cần người nghe suy xét | Nhiều từ khó nhận ra, nhưng còn hiểu được ý chính | Phần lớn khó hiểu; chỉ nhận được một số từ/cụm | Âm thanh hợp lệ nhưng không có lời tiếng Anh hiểu được |
| Trôi chảy | Duy trì cụm nói phù hợp nhiệm vụ; ngắt nghỉ chủ yếu ở ranh giới ý | Có tìm từ/sửa lời nhưng vẫn truyền đạt liên tục phần lớn ý | Dừng và khởi động lại thường xuyên; thông điệp bị gián đoạn | Phần lớn từ rời; khó duy trì cụm nói | Không có chuỗi lời nói sử dụng được |
| Ngữ pháp | Cấu trúc đơn giản phù hợp, phần lớn chính xác; lỗi không ảnh hưởng ý | Có lỗi nhưng ý vẫn rõ | Lỗi thường xuyên, đôi lúc gây hiểu sai | Lỗi làm phần lớn ý khó hiểu | Không có bằng chứng về cấu trúc có ý nghĩa |
| Từ vựng | Đủ từ phù hợp để diễn đạt yêu cầu, có thể diễn đạt vòng | Đủ ý chính, có lặp hoặc lựa chọn chưa tự nhiên | Vốn từ hạn chế, gây thiếu một phần ý | Chủ yếu từ đơn/không phù hợp, khó truyền đạt | Không có từ vựng tiếng Anh sử dụng được |
| Tổ chức ý – C1 | Có mô tả tổng quát rồi chi tiết liên quan; theo dõi dễ dàng | Ý tương đối có thứ tự, vài chuyển ý đột ngột | Chủ yếu liệt kê, liên kết yếu nhưng còn theo dõi được | Các ý rời rạc làm người nghe khó hiểu tranh | Không có nội dung liên quan để tổ chức |
| Hoàn thành nhiệm vụ | Đáp ứng các ý cốt lõi được nêu trong câu hỏi | Đáp ứng phần lớn, thiếu một chi tiết phụ | Đáp ứng một phần; còn thiếu ý quan trọng | Chỉ đáp ứng rất ít, phần lớn lạc đề | Không đáp ứng nhiệm vụ hoặc xác nhận bỏ câu |

Rubric phải kèm neo nội dung cho từng câu: A nêu đủ ba ý yêu cầu; câu B chỉ hỏi một thông tin không buộc có ba ý; câu yêu cầu lý do cần có lý do; C1 yêu cầu người/bối cảnh/hành động nhìn thấy rõ. Không dùng chung một danh sách ý bắt buộc cho mọi câu.

Không trừ ngữ pháp/từ vựng chỉ vì quan điểm khác đáp án mẫu. Câu trả lời không liên quan nhận điểm nhiệm vụ thấp/0; các tiêu chí ngôn ngữ vẫn đánh giá trên bằng chứng thật, không tự kéo mọi tiêu chí về 0. Nếu muốn áp trần điểm cho trả lời hoàn toàn lạc đề thì phải công bố thành quy tắc riêng, kiểm chứng và áp dụng nhất quán.

## 4. Ngữ âm thực hành trực tuyến: 10 điểm

Giữ cấu trúc giấy 3 + 3 + 4. Không áp rubric giao tiếp mặc định.

| Phần | Ma trận đề xuất | Điểm | Cách chấm |
|---|---|---:|---|
| Đọc từ | 10 từ: 1 một âm tiết, 3 hai âm tiết, 3 ba âm tiết, 3 từ bốn âm tiết trở lên; cân bằng thêm âm đích/cụm phụ âm | 3 | Mỗi từ 0,3; từ nhiều âm tiết: độ chính xác âm 2/3 và trọng âm 1/3; từ một âm tiết: toàn bộ cho âm |
| Đọc câu | 10 câu: 5 trần thuật, 3 Yes/No, 2 Wh; cân bằng độ dài và âm đích | 3 | Mỗi câu 0,3; chính xác âm 30%, trọng âm câu 25%, ngữ điệu theo ngữ cảnh 30%, nhịp/ngắt cụm 15% |
| Đọc đoạn | 2 đoạn cùng nhóm độ dài/độ khó, thí dụ nhóm 40–60 từ sau khi chuẩn hóa | 4 | Mỗi đoạn 2; chính xác âm 30%, trọng âm/ngữ điệu 25%, trôi chảy 20%, ngắt cụm 15%, đọc đủ nội dung 10% |

Ma trận 1/3/3/3 là cấu hình mới đề xuất. Nếu kho hiện tại không đủ ở một nhóm thì báo thiếu, không đổi thành nhóm khác. Độ khó không suy ra chỉ từ số âm tiết.

Thời lượng thử nghiệm: phần từ 20 giây xem trước + tối đa 10 giây/từ; phần câu 20 giây xem trước + tối đa 20 giây/câu; mỗi đoạn 30 giây xem trước + tối đa 60 giây đọc. Tổng cửa sổ khoảng 8 phút 40 giây, cộng chuyển phần khoảng 10 phút. Cho nộp sớm, không bắt thí sinh chờ hết thời gian mỗi từ. Không phát audio mẫu trước câu được chấm nếu mục tiêu là đọc, vì khi đó nhiệm vụ chuyển sang bắt chước.

### Mức điểm và bằng chứng Ngữ âm

| Tiêu chí | 4 | 3 | 2 | 1 | 0 |
|---|---|---|---|---|---|
| Chính xác âm | Các âm đích rõ và từ dễ nhận ra | Một vài sai lệch, vẫn nhận từ dễ | Nhiều sai lệch, có từ khó nhận | Chỉ nhận được phần nhỏ các từ/âm | Không phát âm được mục tiêu trong bản ghi hợp lệ |
| Trọng âm từ | Đặt trọng âm chính đúng ở từ mục tiêu | Trọng âm đúng nhưng độ nổi bật chưa đều | Có dấu hiệu đúng nhưng không ổn định/khó nhận | Nhấn sai hoặc các âm tiết hầu như ngang nhau | Không có từ hoàn chỉnh để đánh giá |
| Trọng âm câu/ngữ điệu | Làm rõ ý nghĩa và kiểu câu trong ngữ cảnh đã nêu | Phần lớn phù hợp, một vài điểm chưa tự nhiên | Không ổn định, đôi lúc làm mờ ý | Phần lớn không hỗ trợ ý nghĩa/kiểu câu | Không có câu sử dụng được |
| Nhịp/ngắt cụm | Nhóm ý hợp lý, ít đứt gãy trong cụm | Vài chỗ ngắt chưa hợp lý, ý vẫn rõ | Nhiều chỗ ngắt sai, theo dõi khó | Chủ yếu tách từng từ hoặc đứt gãy | Không đủ chuỗi lời để đánh giá |
| Trôi chảy đoạn | Duy trì mạch đọc phù hợp; không cần đọc nhanh | Có ngập ngừng nhưng mạch đọc phần lớn được giữ | Ngập ngừng/sửa lời nhiều, mạch thường đứt | Rất khó duy trì đọc liên tục | Không có mạch đọc sử dụng được |

Đọc đủ nội dung được tính riêng từ tỷ lệ từ nguồn đã đọc, có đối sánh và nghe lại khi nhận dạng không chắc chắn. Cách đề xuất: điểm tiêu chí 0–100 = 100 × số từ nguồn đọc được / số từ nguồn; từ lặp không tăng số đếm. Đọc sai âm nhưng vẫn xác định được từ mục tiêu không đồng thời coi là bỏ từ. Không dùng tỷ lệ lỗi bản chép lời làm điểm phát âm.

Bổ sung mức 0 cho các tiêu chí, giải quyết thiếu sót của bảng giấy. Điểm đoạn tính bằng tổng tiêu chí có trọng số, bỏ hướng dẫn mơ hồ rằng có thể cho một điểm tổng thể khác. “Hoàn chỉnh/đọc đủ” chỉ chấm ở vị trí đã quy định; tránh phạt cùng lỗi bỏ từ thêm lần nữa ngoài chính sách.

Chấp nhận biến thể phát âm phù hợp và nhấn mạnh mức độ dễ hiểu. Không mặc định giọng Việt là lỗi. Ngữ điệu phụ thuộc ngữ cảnh; đáp án cần chỉ ra các phương án hợp lý, không bắt mọi câu hỏi chỉ có một đường lên/xuống.

## 5. Công thức điểm và nguồn tín hiệu

Với tiêu chí theo band: điểm chuẩn hóa = band / 4 × 100. Với tín hiệu âm học liên tục: qua bộ hiệu chỉnh đã đối chiếu giảng viên để ra 0–100; không tự coi điểm thô nhà cung cấp bằng điểm học phần.

Điểm câu trên thang 100 = tổng(điểm tiêu chí × trọng số tiêu chí). Điểm đóng góp = điểm câu / 100 × điểm tối đa câu. Điểm bài trên thang 10 = tổng điểm đóng góp. Chỉ làm tròn điểm cuối đến hai chữ số; lưu điểm thành phần chưa làm tròn để truy vết.

GT1: A tối đa 2; B bốn câu mỗi câu 1; C1 tối đa 2; C2 hai câu mỗi câu 1. Ngữ âm: 10 từ × 0,3 + 10 câu × 0,3 + 2 đoạn × 2. Không lấy trung bình đều giữa mọi câu khi số điểm tối đa khác nhau.

Ví dụ GT1: A đạt 80/100 → 1,6; B lần lượt 75/80/60/85 → 3,0; C1 đạt 70 → 1,4; C2 đạt 80/70 → 1,5. Tổng 7,50/10. Đây là ví dụ số học, không phải điểm của thí sinh thật.

Các nhánh chấm:

- Âm thanh gốc → kiểm tra chất lượng → nhận dạng có mốc thời gian → tín hiệu âm vị, trọng âm, ngữ điệu, ngắt nghỉ.
- Bản chép lời có kiểm soát lỗi → LLM chấm ngữ pháp, từ vựng, nhiệm vụ và tổ chức ý khi phù hợp.
- Bài đọc dùng văn bản đích đã khóa. Bài nói tự do không dùng một câu mẫu như văn bản buộc phải đọc.
- Tranh có mã ảnh/hash, phiên bản, chú giải đã duyệt về những gì thật sự quan sát được, cách diễn đạt tương đương và câu tiếp nối. AI không được bịa chi tiết ảnh làm đáp án.
- Bộ tính điểm phía máy chủ kiểm tra đủ tiêu chí/đúng dải điểm và tự cộng trọng số. Không lấy trường “total score” do LLM tự nghĩ làm điểm chính thức.

Azure Pronunciation Assessment là ứng viên kỹ thuật để thử vì có chế độ đọc và nói tự do, Accuracy/Fluency/Prosody/Completeness. Tài liệu hiện giới hạn prosody ở en-US. Điểm phát âm tổng hợp có thể đã chứa fluency/prosody: không cộng thêm chúng một lần nữa mà chưa xem thành phần. Nếu thiếu tín hiệu trọng âm hoặc ngữ điệu cần thiết, không bù bằng suy đoán từ văn bản.

Có thể dùng mô hình âm học tại chỗ nếu yêu cầu vận hành local, nhưng phải có đầu ra phù hợp và được kiểm chứng trên người học thật. Whisper + LLM văn bản hiện tại chưa đủ để chấm toàn bộ hai môn. Giọng đọc/TTS của hệ thống không được lẫn trong audio thí sinh được chấm; lưu các kênh riêng.

## 6. Sinh đề ngẫu nhiên và đáp án đi kèm

Đầu vào là phiên bản ma trận đã công bố, danh sách câu đã duyệt, rubric tương thích và quy tắc lấy mẫu. Metadata cần có môn, phần, dạng, chủ đề, mức khó, độ dài, thời lượng, họ câu trùng, nguồn, rubric, âm đích hoặc ảnh nếu có.

Trình tự: chọn nhóm chủ đề/độ khó → lấy đủ slot theo ràng buộc → kiểm tra trùng/phụ thuộc/thời lượng → chụp snapshot đề và đáp án/rubric → gắn vào lượt thi một lần. Tải lại trang hoặc retry mạng không sinh đề khác.

GT1 dùng hai chủ đề ở B, một tranh phù hợp ở C; phần giới thiệu không bị ép có cùng chủ đề. Ngữ âm chọn theo đặc điểm âm và cấu trúc câu; không dùng một “topic” chung để lọc cả từ, câu và đoạn. Các câu phụ thuộc được đóng gói thành nhóm; không tách câu trả lời thời gian khỏi câu hỏi đi lại nếu bản hỏi chưa được viết độc lập.

Lưu seed phía máy chủ, phiên bản thuật toán, danh sách ứng viên, câu đã chọn, thứ tự, mọi ràng buộc và snapshot nội dung. Chỉ seed là chưa đủ tái tạo đề khi ngân hàng đã đổi. Không đưa đáp án ẩn, tiêu chí nội bộ hoặc seed ra client trước thi.

Giới hạn tần suất xuất hiện và hạn chế lặp đề ở lần thi tiếp theo trong khả năng kho. Không hứa mỗi lượt đều duy nhất vô hạn. Nếu thiếu câu tương thích: chặn công bố đề, báo nhóm còn thiếu; không lấy câu khác mức khó để lấp chỗ.

Ví dụ đề GT1: A thẻ giới thiệu về học tập/sở thích; B chủ đề ăn uống và đi lại, mỗi chủ đề hai nhiệm vụ cân bằng; C tranh nhóm bạn dùng máy tính, mô tả rồi hai câu tiếp nối đã duyệt. Đây là minh họa cấu trúc, không phải bộ câu đã công bố.

Đáp án mỗi câu gồm: yêu cầu cốt lõi, các biến thể chấp nhận, ví dụ trả lời theo mức, rubric ID/version, và bằng chứng mà AI phải trích dẫn. Đáp án bài nói mở không phải chuỗi từ khóa bắt buộc hoặc văn mẫu duy nhất.

## 7. AI chấm trước và quyền quyết định cuối

Luồng: đã nộp → kiểm tra audio → AI chấm → đủ điều kiện công bố tự động hoặc cần rà soát → phúc khảo nếu yêu cầu → quyết định cuối.

- Chấm tự động mặc định cho mọi bài đủ điều kiện. Không bắt giảng viên duyệt từng bài sau khi đã kiểm chứng hệ thống và có chính sách công bố.
- Chuyển rà soát khi audio hỏng/thiếu, tín hiệu nhận dạng không đủ, điểm giữa các lần chấm lệch lớn, thiếu tiêu chí bắt buộc, nghi ngờ nhận dạng sai làm thay đổi nội dung, hoặc trường hợp gần ngưỡng đạt theo chính sách đã hiệu chỉnh.
- Các ngưỡng như chênh trên 1/10 giữa hai lượt chấm hoặc khoảng ±0,5 quanh ngưỡng đạt chỉ là điểm khởi đầu thử nghiệm, không phải chuẩn được xác nhận. Không coi “confidence” do LLM tự ghi là xác suất đúng.
- Giảng viên được phân công/admin xem audio, transcript và chỗ sửa transcript, điểm từng tiêu chí, đoạn bằng chứng theo thời gian, đề/rubric/model phiên bản nào, cờ chất lượng.
- Người có quyền có thể giữ điểm, sửa từng tiêu chí, yêu cầu chấm lại cùng cấu hình hoặc cho thi lại vì lỗi kỹ thuật; mọi thao tác cần lý do. Không tự kết luận gian lận từ một cờ AI.
- Giữ nguyên điểm AI gốc, toàn bộ lần chấm lại và quyết định trước; tạo bản quyết định mới thay vì ghi đè lịch sử. Đổi model/rubric không âm thầm sửa điểm các bài đã thi.

Trong thi trực tuyến, upload từng đoạn có mã câu và mã lượt thi; lưu tạm và tiếp tục truyền khi mạng phục hồi. Server quản lý thời hạn. Không cho random lại hoặc ghi lại tùy ý chỉ vì refresh. Chính sách ghi lại do sự cố phải công bố, có log và áp dụng nhất quán. Cho phép điều chỉnh tiếp cận hợp lý về thời gian/thiết bị theo quy định học phần.

## 8. Khoảng cách với mã nguồn hiện tại

Đối chiếu `core/tasks.py`, `core/blueprints.py`, `core/models.py`:

1. Luồng practice dùng Whisper rồi đưa văn bản vào LLM, bỏ mốc thời gian khi ghép transcript. Phát âm được yêu cầu null; fluency vẫn được hỏi từ văn bản. Chưa có nhánh chấm âm học.
2. Payload rubric trọng số đầu hàm chưa được gửi trong nhánh đang dùng; nhánh gọi từng câu chỉ truyền câu hỏi và transcript. Điểm tổng là trung bình các điểm câu LLM trả, chưa tính bằng rubric có phiên bản của đề.
3. Sampler có seed và snapshot là nền tảng tốt, nhưng đang ép toàn bộ đề cùng một topic, so sánh thời lượng khớp tuyệt đối và loại trùng theo ID phiên bản. Cần hỗ trợ topic/đặc điểm riêng mỗi phần, thời lượng theo slot và loại trùng theo câu/họ nội dung; nhiều phiên bản của cùng câu không được cùng vào một đề.
4. `CriterionLevelDescriptor` đang gắn descriptor với nhãn CEFR. Cần cấu trúc riêng cho band 0–4 và nguồn tín hiệu; mức điểm trong một tiêu chí khác với chuẩn đầu ra CEFR.
5. Có phần giảng viên nhập điểm cuối cho practice, nhưng để làm thi chính thức cần nhật ký quyết định bất biến, yêu cầu phúc khảo và quyền theo kỳ thi.
6. Blueprint hiện tạo bản mẫu; cần luồng cấp đề cho thí sinh, thu audio theo câu/phần, khóa bài và kết nối máy chấm rubric. Không coi việc có ngân hàng câu hỏi là đã có luồng thi hoàn chỉnh.

## 9. Hiệu chỉnh trước khi dùng điểm chính thức

Đề xuất pilot 60–100 bài cho mỗi học phần, bao phủ các phần thi, mức năng lực, thiết bị và điều kiện thu âm. Đây là quy mô khởi đầu khả thi, không bảo đảm đủ cho mọi kiểm định.

Hai giảng viên chấm độc lập, thống nhất các trường hợp lệch; tách tập hiệu chỉnh và tập kiểm chứng giữ riêng theo thí sinh để tránh rò rỉ. So AI với điểm giảng viên theo từng tiêu chí và tổng: sai lệch có hướng, sai số tuyệt đối, mức đồng thuận, quyết định đạt/trượt gần ngưỡng, ảnh hưởng thiết bị và giọng nói. Không chỉ nhìn tương quan điểm.

Một mục tiêu thử nghiệm có thể là sai số tuyệt đối trung bình tổng ≤0,5/10, ít nhất 90% bài lệch không quá 1/10 và đồng thuận đạt/trượt ≥95%; đó là ngưỡng đề xuất để thảo luận trước pilot, không phải kết quả đạt được hoặc chuẩn quốc gia. Phải xem khoảng bất định, cỡ mẫu và lỗi ở từng nhóm, không chỉ số trung bình. Môn Ngữ âm cần kiểm tra riêng trọng âm/ngữ điệu; tổng điểm tốt không bù được một tiêu chí chấm sai.

Khi chưa đạt chất lượng đã thống nhất, giữ AI ở trạng thái điểm sơ bộ và cho người chấm xác nhận. Khi đạt, bật công bố tự động cho bài hợp lệ, rà soát các cờ chất lượng và lấy mẫu kiểm tra định kỳ. Thiết lập lại hiệu chỉnh khi đổi model, ngôn ngữ, rubric hoặc thiết kế đề.

## 10. Nguồn tham khảo

- PXU, SPEAKING-DEFAULT v3, xem trực tiếp 26/09/2026: https://assessment.pxu.edu.vn/admin/rubrics/3
- Council of Europe, CEFR Companion Volume, mục Phonological control, trang in 133–135: https://rm.coe.int/16809ea0d4 . Cơ sở tham khảo về độ dễ hiểu, cấu âm và ngữ điệu; không phải phép quy đổi điểm thi sang CEFR.
- Microsoft, Use pronunciation assessment: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-pronunciation-assessment . Tham khảo các nguồn tín hiệu và giới hạn kỹ thuật, không coi điểm nhà cung cấp là điểm học phần đã được xác nhận.
- ETS, Automated Scoring of Nonnative Speech Using the SpeechRater v. 5.0 Engine: https://www.ets.org/research/policy_research_reports/publications/report/2018/jyzm.html . Tham khảo cách phối hợp nhóm đặc trưng và nhận diện câu trả lời không thể chấm.

Tất cả tỷ lệ, thời lượng và ngưỡng pilot mới trong tài liệu này là đề xuất cần chuẩn hóa/công bố trước sử dụng; không được trình bày là quy định sẵn có trong đề giấy hoặc kết quả kiểm chứng của ứng dụng.
