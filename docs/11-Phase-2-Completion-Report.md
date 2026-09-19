# Phase 2 Completion Report — Enhancement (v1.1)

Ngày cập nhật: 2026-06-17

## 1. Phạm vi

Phase 2 mở rộng MVP Phase 1 theo `docs/10-Phase-2-Plan.md`, chia nhỏ tuần tự, mỗi Part là một commit độc lập có test riêng. Giữ triết lý Phase 1: **mọi tính năng chạy được khi không có `GEMINI_API_KEY`**.

## 2. Kết quả từng Part

### Part 0 — Nền tảng & deps (`2f7d0b9`)
- Thêm deps: `pypdf`, `openpyxl`, `reportlab` (đọc PDF/XLSX, xuất PDF).
- Config: `UPLOAD_DIR`, `RAG_TOP_K`, `RAG_CHUNK_SIZE`.

### Part 1 — Upload tài liệu + trích xuất (`78582ee`)
- Model `UploadedDocument` (tự tạo bảng qua `init_db`).
- Extractors thuần: PDF (`pypdf`), DOCX (`python-docx` + bảng), XLSX (`openpyxl`).
- `DocumentService`: lưu file vào `UPLOAD_DIR`, dispatch extractor, CRUD.
- Routes: `POST /api/documents/upload` (multipart), `GET /api/documents`, `GET /api/documents/{id}`, `DELETE`.

### Part 2 — Ngân hàng câu hỏi (`0735d4a`)
- Model `BankQuestion`.
- `QuestionBankService`: add, **save-from-exam** (chỉ câu đã `accepted` hoặc theo id), list+filter (grade/subject/topic/type/difficulty/search), get, delete, bump usage.
- Routes: `/api/question-bank/*` + `POST {id}/use`.

### Part 3 — RAG knowledge base offline (`6509891`)
- `rag/chunking.py`: cắt curriculum objective + `extracted_text` thành chunk kèm metadata.
- `rag/retriever.py`: **BM25 thuần Python, tất định**; interface `BaseRetriever.retrieve(query, k)` để sau cắm `EmbeddingRetriever` (Gemini + Chroma) cùng chữ ký.
- `KnowledgeBaseService`: build index từ curriculum(grade) + doc, query.
- Gắn opt-in vào sinh đề: `FullExamRequest.use_uploaded_docs` → câu khớp tài liệu mang `source=rag_retrieval`. Không có doc → hành vi y hệt Phase 1 (`local_json`).
- Routes: `POST /api/rag/index`, `POST /api/rag/query`.

### Part 4 — PDF export (`c8a3cc4`)
- `pdf_export_service.py` (reportlab) + font Unicode **DejaVuSans** đính kèm (`app/assets/fonts`) để render dấu tiếng Việt.
- Cùng cấu trúc hồ sơ như docx, tái dùng dict từ `_to_full_response`; phần đề bài không lộ đáp án.
- Route: `POST /api/exams/{id}/export-pdf`.

### Part 5 — Quản lý lịch sử đề (`6c4114e`)
- `DELETE /api/exams/{id}`, `POST /api/exams/{id}/duplicate` (id mới, nội dung giống, review_status reset).
- `list_exams` nhận filter `grade`/`exam_type` + `limit`/`offset`.

### Part 6 — Frontend (`1a11215`)
- Trang **Tài liệu** (upload/list/delete) và **Ngân hàng câu hỏi** (browse/filter).
- CreateExam: bộ chọn "dùng tài liệu đã upload" (opt-in RAG) + lưu câu vào ngân hàng; badge nguồn trên `QuestionCard`.
- ExamDetail: nút export PDF, nhân bản, xóa, lưu câu đã duyệt vào ngân hàng.
- `api.ts` + hook `useExam` + types + route/nav + Home cards.

## 3. Kiểm thử

Backend (`backend/.venv/bin/pytest tests`): **148 passed** (123 Phase 1 + 25 Phase 2).

File test mới:
- `test_documents.py` — extractor từng loại, roundtrip upload→list→get→delete, sai loại → 400.
- `test_question_bank.py` — CRUD, filter, save-from-exam (chỉ câu accepted), usage increment.
- `test_rag.py` — chunk count, BM25 ranking, sinh đề có/không doc + validation, source metadata.
- `test_pdf_export.py` — PDF hợp lệ (`%PDF`), đề không lộ đáp án, có đáp án viết.
- `test_exam_history.py` — delete (404 sau khi xóa), duplicate (id mới/nội dung giống/reset duyệt), filter.

Frontend (`cd frontend && npm run build`): ✓ built (tsc + vite, không lỗi TypeScript).

## 4. Nâng cấp tương lai (ngoài Phase 2)

- Thay `rag/retriever.py` BM25 → Gemini `text-embedding-*` + ChromaDB embedded persistent, **giữ nguyên interface `retrieve`** (lý do tách interface ở Part 3).
