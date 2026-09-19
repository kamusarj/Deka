# Phase 1 Completion Report

## Smart Exam Matrix AI

Ngày cập nhật: 2026-06-09

## 1. Phạm vi

Phase 1 tập trung hoàn thiện luồng MVP tạo đề kiểm tra KHTN THCS từ dữ liệu đã kiểm soát:

- Nạp dữ liệu chương trình từ local JSON.
- Chuẩn hóa phạm vi kiểm tra.
- Sinh ma trận, bản đặc tả, câu hỏi, đáp án, rubric.
- Duyệt câu hỏi và tạo lại câu cần sửa.
- Kiểm tra chất lượng, chống câu hỏi thiếu nguồn.
- Xem lại đề đã tạo và xuất Word.
- Sinh nhiều mã đề phục vụ in/phát đề.

Các phần upload tài liệu đầy đủ, RAG/vector DB, question bank nâng cao, PDF export và multi-user vẫn nằm ngoài Phase 1.

## 2. Backend

### 2.1 Data ingest và normalize

- Thêm API `POST /api/data/ingest` cho Step 0.
- Thêm API `POST /api/data/normalize` cho Step 1.
- `ResourceCollectorAgent` dùng dữ liệu local JSON theo khối lớp thay vì để AI tự tạo nguồn.
- Resource package trả về `data_sources`, `raw_data`, `curriculum_suggestions`, sample matrix và guideline.
- Topic/câu hỏi có metadata `source` để truy vết về `local_json`.

### 2.2 Sinh đề và validation

- Full exam generation sinh ma trận, đặc tả, câu hỏi, đáp án, rubric và validation trong một luồng.
- `QuestionAgent` fallback bổ sung `source` cho từng câu hỏi.
- `ValidatorAgent` có thêm metadata `category`, `status` và check `CHECK_NO_HALLUCINATION`.
- Validation fail khi câu hỏi thiếu source metadata hoặc source type không hợp lệ.

### 2.3 Review câu hỏi

- `ReviewQuestionsRequest` hỗ trợ đủ trạng thái `accepted`, `needs_revision`, `rejected`.
- Có `QuestionReviewItem` để lưu comment, reviewer và thời điểm duyệt.
- Thêm route `POST /api/questions/review`, đồng thời giữ route cũ `/api/exams/{exam_id}/review`.
- Review validate question id trước khi ghi trạng thái.

### 2.4 Xem lại đề đã tạo

- Sửa endpoint `GET /api/exams/{id}` trả `FullExamResponse`.
- Màn xem lại đề nhận đúng shape `exam_info`, không còn lỗi khi mở đề đã lưu.

### 2.5 Mã đề

- `FullExamRequest` có `variant_count`, giới hạn từ 1 đến 30.
- Số mã đề được lưu trong `resource_package.variant_count`.
- Response chi tiết đề có thêm `variants`.
- Mã đề sinh theo dãy `101`, `102`, ... tối đa `130`.
- Câu trắc nghiệm chỉ đổi thứ tự câu hỏi trong nhóm trắc nghiệm theo mã đề.
- Nội dung, phương án A-D và đáp án đúng của câu trắc nghiệm được giữ nguyên.
- Câu đúng/sai, trả lời ngắn và tự luận được biến thể nội dung theo từng mã đề.
- Đáp án đúng/sai được cập nhật đúng theo thứ tự phát biểu của từng mã đề.

### 2.6 Export Word

- File Word xuất ra gồm hồ sơ đề, ma trận, bản đặc tả, các mã đề và đáp án theo mã đề.
- Bản đặc tả trong Word hiển thị nhãn tiếng Việt cho mức độ và dạng câu.
- Đáp án trắc nghiệm/đúng-sai được tách theo mã đề; tự luận dùng hướng dẫn chấm/rubric.

## 3. Frontend

- Thêm ô `Số mã đề` trong form tạo đề, giới hạn 1-30.
- Màn xem chi tiết có bộ chọn mã đề.
- Khi đổi mã đề, danh sách câu hỏi và đáp án hiển thị theo mã đã chọn.
- Câu đúng/sai trong đề không hiện `[Đ]`/`[S]`, tránh lộ đáp án.
- Mức độ và dạng câu hiển thị tiếng Việt: `Nhận biết`, `Thông hiểu`, `Vận dụng`, `Trắc nghiệm`, `Đúng/Sai`, `Trả lời ngắn`, `Tự luận`.
- Bảng ma trận được căn lại bằng colgroup/table-layout để không lệch cột.

## 4. Test coverage

File mới:

- `backend/tests/test_phase1_flow.py`
- `backend/tests/test_exam_variants.py`

Các test chính:

| Test | Mục tiêu |
|---|---|
| `test_data_ingest_uses_local_json_source` | Step 0 dùng nguồn `local_json` và trả đúng source metadata |
| `test_data_normalize_returns_common_schema_from_manual_plan` | Step 1 chuẩn hóa teaching plan thủ công |
| `test_phase1_full_generation_review_answers_and_validation` | Luồng full exam, review 3 trạng thái, answer generation và validation |
| `test_validation_fails_when_question_has_no_source_metadata` | Validation fail khi câu hỏi thiếu source |
| `test_exam_variants_follow_teacher_count_and_variant_rules` | Mã đề theo số giáo viên chọn, trắc nghiệm giữ phương án/đáp án, đúng-sai/tự luận khác nhau |

## 5. Kết quả kiểm thử

Backend:

```bash
backend/.venv/bin/pytest backend/tests
```

Kết quả:

```text
117 passed, 2 warnings
```

Frontend:

```bash
cd frontend
npm run build
```

Kết quả:

```text
✓ built
```

Ghi chú:

- Hai warning còn lại là cảnh báo Pydantic deprecation của cấu hình cũ.
- `variant_count=7` được schema chấp nhận.
- `variant_count=31` bị schema từ chối đúng giới hạn.

## 6. Kết luận

Phase 1 hiện đã đủ luồng MVP tạo đề, kiểm soát nguồn dữ liệu, validation, duyệt câu hỏi, xem lại đề đã tạo, export Word và sinh nhiều mã đề theo lựa chọn của giáo viên. Các thay đổi hiện tại phù hợp để tạm chốt nhánh `Phase01`.

## 7. Bổ sung 2026-06-15: Chống trùng câu hỏi khi sinh đề

Cập nhật tập trung vào chất lượng phần **tạo đề thi** ở nhánh fallback (khi chưa cấu hình Gemini).

### 7.1 Vấn đề phát hiện

- Ma trận phân bổ câu hỏi luân phiên theo chủ đề nên nhiều câu cùng dạng rơi vào cùng một chủ đề.
- `QuestionAgent` fallback sinh nội dung chỉ dựa trên `topic` + `achievement` nên các câu cùng chủ đề có **nội dung trùng hệt nhau** (ví dụ 6/16 câu trùng).
- Check `CHECK_NO_DUPLICATES` chỉ ở mức `medium` (warning) nên đề vẫn "pass" dù bị lặp câu.
- Phát biểu đúng/sai còn hardcode "lớp 8", sai với các khối khác.

### 7.2 Cách xử lý

- Thêm hệ thống `ASPECTS` (6 khía cạnh) và `_annotate_occurrences`: mỗi câu cùng `(chủ đề, dạng câu)` được gán một khía cạnh khác nhau (khái niệm, dấu hiệu nhận biết, ví dụ, vai trò, mối liên hệ, phân loại).
- Khi số câu vượt quá số khía cạnh (đề phạm vi hẹp), `_aspect` thêm hậu tố "góc nhìn N" để đảm bảo không trùng với mọi số lượng câu.
- Khía cạnh được dùng nhất quán trong đề bài, phương án trắc nghiệm, phát biểu đúng/sai, câu trả lời ngắn và tự luận → nội dung, phương án và phát biểu đều khác nhau.
- Bỏ hardcode "lớp 8" trong phát biểu đúng/sai.
- `CHECK_NO_DUPLICATES` được làm robust (không lỗi khi thiếu `content`), giữ mức `medium` đúng theo sơ đồ flow (content validation → cảnh báo và tiếp tục).

### 7.3 Kiểm thử

- `test_question_agent_makes_same_topic_questions_distinct`: 8 câu trắc nghiệm + 2 câu đúng/sai cùng một chủ đề đều khác nội dung, khác bộ phương án, khác bộ phát biểu (phủ cả nhánh "vượt số khía cạnh").
- `test_phase1_full_generation_review_answers_and_validation`: bổ sung assertion đề không có câu trùng và `warnings == []`.
- Kiểm tra thủ công end-to-end cả 4 khối (6/7/8/9) và trường hợp đề chỉ 1 chủ đề: 16/16 câu unique, validation `passed=True`, `score=100`, export Word trả về 200.

Kết quả: `119 passed` (`backend/.venv/bin/pytest tests`).

## 8. Bổ sung 2026-06-15: Mượt hóa luồng tạo đề và sửa bug

Đợt rà soát toàn luồng (backend + API + frontend + export) và sửa các bug còn lại.

### 8.1 Phân bổ độ khó ma trận hợp lý hơn về sư phạm

- Trước: toàn bộ câu trắc nghiệm rơi vào mức "thông hiểu", còn câu tự luận 2.5đ lại bị gán mức "nhận biết".
- Nay `MatrixAgent` dùng chiến lược **hybrid**: ưu tiên gán đúng mức độ phù hợp với dạng câu khi còn hạn mức điểm (trắc nghiệm → nhận biết, tự luận → vận dụng/thông hiểu), chỉ khi buộc phải vượt hạn mức mới chọn mức ít lệch nhất để giữ tỷ lệ.
- Sweep 9 cấu hình (nhiều tỷ lệ, số câu, dạng câu): tổng luôn = 10, độ lệch tỷ lệ tối đa 5% (ngưỡng validator là 10%).
- Test mới: `test_multiple_choice_lean_easier_and_essays_avoid_recall`.

### 8.2 Export Word: bổ sung đáp án trả lời ngắn và tự luận theo mã đề

- Trước: `_variant_answers` chỉ xuất đáp án trắc nghiệm và đúng/sai; đáp án trả lời ngắn và tự luận bị bỏ qua khỏi file Word (dù UI vẫn hiển thị).
- Nay đáp án theo mã đề tách 2 mục: "Trắc nghiệm / Đúng-Sai" và "Trả lời ngắn / Tự luận", đầy đủ tất cả dạng câu.
- `_questions`/`_answers` dùng `.get()` để không vỡ nếu thiếu trường.

### 8.3 Endpoint export an toàn kiểu dữ liệu

- `POST /api/export` trước nhận `dict` thô → trả 500 khi thiếu/sai `exam_id`. Nay dùng `ExportRequest` → trả 422 đúng chuẩn.

### 8.4 Kiểm thử

- File mới `tests/test_export.py`: đáp án viết xuất hiện trong Word, đề bài không lộ đáp án, endpoint export trả 422 với input sai.
- Kiểm tra end-to-end cả 4 khối: 16/16 câu unique, trắc nghiệm nghiêng nhận biết, validation `passed=True`, `score=100`, export 200.
- Frontend `npm run build`: ✓ built, không lỗi TypeScript.

Kết quả: `123 passed` (`backend/.venv/bin/pytest tests`).

### 8.5 Ghi chú còn lại (đề xuất cho Phase 2)

- Dữ liệu đáp án (`correct_answer`, `is_true`) hiện vẫn đi kèm trong object câu hỏi gửi về client (UI không hiển thị nên chưa lộ). Nên tách hẳn view "đề cho học sinh" và loại bỏ trường đáp án khỏi payload đề bài.
- Form tạo đề chưa cho chỉnh `question_types` (số câu/điểm từng dạng); hiện dùng mặc định nhất quán 10đ. Có thể mở UI cấu hình kèm kiểm tra tổng điểm = 10 trực tiếp.
