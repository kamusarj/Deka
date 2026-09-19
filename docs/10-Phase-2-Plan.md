# Phase 2 Plan — Enhancement (v1.1)

Ngày lập: 2026-06-16

## Bối cảnh

Phase 1 đã hoàn thiện luồng MVP tạo đề từ curriculum JSON đã kiểm soát. Phase 2 (v1.1 "Enhancement") theo roadmap (`docs/08-Future-Features.md`) bổ sung: upload tài liệu giáo viên, RAG knowledge base, Vector DB, Question Bank, PDF export và quản lý lịch sử đề.

**Quyết định định hướng (đã chốt với người dùng):**
- Làm **toàn bộ** Phase 2, **chia nhỏ tuần tự**, mỗi phần debug độc lập.
- RAG **chạy offline trước** (BM25/từ khóa thuần Python, tất định, chạy được khi không có API key) — thiết kế interface để **sau này nâng cấp** lên Gemini embeddings + ChromaDB mà không phá vỡ cấu trúc.
- Giữ triết lý Phase 1: mọi tính năng chạy được khi không có `GEMINI_API_KEY`.

## Hiện trạng nền tảng

- DB: SQLAlchemy, SQLite fallback, **không Alembic** — bảng mới tự tạo qua `Base.metadata.create_all()` (chỉ cần định nghĩa model + import trong `init_db`).
- AI: điểm hội tụ duy nhất là `GeminiService`; **chưa có** hàm embedding. `chromadb`/`langchain` đã cài nhưng **chưa dùng**.
- `ValidatorAgent` đã whitelist source: `local_json`, `uploaded_file`, `question_bank`, `rag_retrieval`, `manual_input` → data model đã lường trước Phase 2.
- Lịch sử đề: đã có list/get/create + trang `ExamList`. Còn thiếu delete/duplicate.

## Nguyên tắc chia nhỏ để dễ debug

Mỗi Part = 1 commit/PR độc lập, có test riêng, chạy & verify được mà không cần các Part sau. Trong mỗi Part backend: model/service/extractor là hàm thuần, unit-test trước, rồi mới gắn route.

## Lộ trình

### Part 0 — Nền tảng & deps
- Nhánh `Phase02` (tách khỏi PR #4 đang mở).
- Thêm deps: `pypdf` (đọc PDF), `openpyxl` (XLSX), `reportlab` (xuất PDF). `python-docx` đã có (đọc DOCX). BM25 viết thuần Python (không thêm dep nặng).
- Config: `UPLOAD_DIR`, `RAG_TOP_K`, `RAG_CHUNK_SIZE`.
- Verify: 123 test cũ vẫn pass + app import được.

### Part 1 — Upload tài liệu + trích xuất (không AI)
- Model `UploadedDocument` (filename, file_type, size, extracted_text, parsed_data, status, grade, created_at).
- `DocumentService`: lưu file vào `UPLOAD_DIR`, dispatch extractor theo loại.
- Extractors thuần: PDF (`pypdf`), DOCX (`python-docx`), XLSX (`openpyxl` → bảng).
- Routes: `POST /api/documents/upload` (multipart), `GET /api/documents`, `GET /api/documents/{id}`, `DELETE`.
- Tests: trích xuất từng loại từ fixture nhỏ; roundtrip upload→list→get→delete; sai loại → 400.

### Part 2 — Question Bank (không AI)
- Model `BankQuestion` (content, type, difficulty, topic, grade, subject, tags, options/statements/sub_questions, answer, source, usage_count, rating).
- `QuestionBankService`: add, **save-from-exam** (lấy câu đã accepted từ Exam), list+filter (grade/subject/topic/type/difficulty/search), get, delete, bump usage.
- Routes: `/api/question-bank/*`.
- Tests: CRUD, filter, save-from-exam, usage increment.

### Part 3 — RAG knowledge base (offline BM25)
- `rag/chunking.py`: cắt objective curriculum + `extracted_text` thành chunk kèm metadata (source_type, source_name, topic, doc_id).
- `rag/retriever.py`: BM25/từ khóa thuần Python (tất định). **Interface `retrieve(query, k)`** thiết kế để sau cắm `EmbeddingRetriever` (Gemini + Chroma) phía sau cùng chữ ký.
- `KnowledgeBaseService`: build index từ curriculum(grade) + doc đã chọn; retrieve theo topic/objective.
- Gắn vào sinh đề: `QuestionAgent`/`ResourceCollectorAgent` nhận context truy xuất (opt-in `use_uploaded_docs: [doc_ids]`); câu sinh từ tài liệu mang `source = rag_retrieval`/`uploaded_file`. Không có doc → hành vi y hệt Phase 1 (`local_json`).
- Routes: `POST /api/rag/index`, `POST /api/rag/query` (debug), flag trên generate-full-exam.
- Tests: số chunk, retriever xếp đúng chunk liên quan lên đầu, sinh đề vẫn pass validation có/không doc, source metadata đúng.

### Part 4 — PDF export (không AI)
- `pdf_export_service.py` (reportlab) + font Unicode đính kèm (DejaVuSans) để render dấu tiếng Việt. Cùng cấu trúc hồ sơ như docx, tái dùng dict từ `_to_full_response`.
- Route: `POST /api/exams/{id}/export-pdf` (StreamingResponse, application/pdf).
- Tests: PDF hợp lệ (header `%PDF`), đề bài không lộ đáp án, có đáp án viết.

### Part 5 — Quản lý lịch sử đề
- Thêm `DELETE /api/exams/{id}`, `POST /api/exams/{id}/duplicate`; tham số filter/paginate cho list.
- Tests: delete, duplicate (id mới, nội dung giống, review_status reset), filter.

### Part 6 — Frontend
- Trang Documents (upload/list/delete), trang Question Bank (browse/filter + nút "Lưu câu vào ngân hàng" ở ExamDetail), badge nguồn trên QuestionCard, bộ chọn "dùng tài liệu đã upload" ở CreateExam, nút export PDF + delete/duplicate.
- `api.ts` + hooks + types + route/nav. Build phải pass.

## Nâng cấp tương lai (ngoài Phase 2 đợt này)
- Swap `retriever.py` BM25 → Gemini `text-embedding-*` + ChromaDB embedded persistent (giữ nguyên interface `retrieve`).
- Đây là lý do tách rõ interface ở Part 3.

## Cách verify mỗi Part
- Backend: `backend/.venv/bin/pytest backend/tests -q` (xanh, không hồi quy 123 test cũ).
- Thủ công: `uvicorn app.main:app` + curl endpoint mới.
- Frontend: `cd frontend && npm run build`.
- Mỗi Part xong: chạy test → e2e nhanh → commit.
