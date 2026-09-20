# MVP Scope
# Deka

## 1. MVP Definition

### 1.1 MVP Goal
Xây dựng phiên bản đầu tiên có thể sử dụng được, giúp giáo viên THCS tạo đề kiểm tra Khoa học tự nhiên với đầy đủ hồ sơ (ma trận, bản đặc tả, đề, đáp án, rubric). **Hệ thống ưu tiên dùng dữ liệu chương trình đã kiểm soát, tài liệu giáo viên upload và RAG thay vì để AI tự crawl dữ liệu từ web.**

Cập nhật capability hiện tại (US-168): xem [authoring-capabilities](product/authoring-capabilities.md).
Các mốc/thời gian dưới đây là kế hoạch MVP ban đầu, không phải số đo chất lượng đã xác nhận.

### 1.2 MVP Timeline
**4 tuần** (28 ngày)

### 1.3 MVP Success Criteria
- Giáo viên có thể tạo 1 bộ đề kiểm tra hoàn chỉnh trong < 5 phút
- Format tuân thủ 100% theo quy định
- Export được file Word ready-to-print
- **100% dữ liệu từ nguồn đã kiểm soát (không dùng AI tự bịa)**

---

## 2. Features In Scope (MVP)

### 2.1 Core Features

| ID | Feature | Priority | Description |
|----|---------|----------|-------------|
| F0 | Nạp nguồn dữ liệu | P0 | Local JSON curriculum, teacher upload |
| F1 | Chuẩn hóa dữ liệu | P0 | Chuyển đổi về schema chung |
| F2 | Giáo viên xác nhận phạm vi | P0 | Xác nhận trường, năm học, khối, chủ đề |
| F3 | Tạo ma trận | P0 | AI sinh ma trận theo format |
| F4 | Tạo bản đặc tả | P0 | AI sinh bản đặc tả chi tiết |
| F5 | Sinh câu hỏi | P0 | AI sinh câu hỏi theo ma trận |
| F6 | Giáo viên duyệt và sửa câu hỏi | P0 | Direct edit MCQ/TF/short/essay, Save/Cancel và regenerate |
| F7 | Sinh đáp án & rubric | P0 | AI sinh đáp án và rubric |
| F8 | Kiểm tra format + validation | P0 | Validation tự động |
| F9 | Xác nhận cuối cùng | P0 | Giáo viên preview trước khi export |
| F10 | Export Word/PDF | P0 | Công thức OMML/ảnh, bảng và diagram; tài liệu xuất riêng |

### 2.2 Question Types (MVP)

| Type | Support | Notes |
|------|---------|-------|
| TNKQ nhiều lựa chọn | Full | 4 options (A, B, C, D) |
| Đúng/Sai | Full | 4 statements |
| Trả lời ngắn | Full | 1-5 words |
| Tự luận | Full | With rubric |

### 2.3 Subject & Grade (MVP)

| Item | Support |
|------|---------|
| Môn | Khoa học tự nhiên |
| Khối | 6, 7, 8, 9 |
| Học kì | Giữa kì I, Cuối kì I, Giữa kì II, Cuối kì II |

**Dữ liệu curriculum đã seed:**

| Khối | Số topic | Số objective | File |
|------|----------|--------------|------|
| Lớp 6 | 11 | 53 | `khtn_grade_6.json` |
| Lớp 7 | 12 | 51 | `khtn_grade_7.json` |
| Lớp 8 | 12 | 55 | `khtn_grade_8.json` |
| Lớp 9 | 12 | 54 | `khtn_grade_9.json` |
| **Tổng** | **47** | **213** | |

### 2.4 Data Sources (MVP)

| Source | Support | Notes |
|--------|---------|-------|
| Local JSON curriculum | Full | Chương trình chuẩn SGK |
| Teacher upload (PDF/PNG/JPEG) | Implemented | Native-first PDF, OCR chọn lọc bằng Gemini/Tesseract nếu được cấu hình |
| Teacher upload (DOCX) | Basic | Text extraction |
| Teacher upload (XLSX) | Basic | Table parsing |
| Question bank | Implemented | Lưu câu/đáp án/rubric/rich content, kiểm tra trùng, semantic search và reuse trong editor |
| RAG retrieval | Implemented / optional | BM25 + vector, RRF, rerank nội bộ và context budget; không cần nguồn upload vẫn sinh đề |
| Web crawling | None | Không hỗ trợ |

---

## 3. Features Out of Scope (MVP)

### 3.1 Not in MVP

| ID | Feature | Reason | Target Version |
|----|---------|--------|----------------|
| F11 | Full web crawling | Không ưu tiên | N/A |
| F13 | Multi-school user management | Not essential | v1.1 |
| F14 | Payment | Not essential | v2.0 |
| F15 | Complex analytics | Not essential | v2.0 |
| F16 | Real-time collaboration | Complex | v2.0 |
| F17 | Môn khác | Extend later | v2.0 |
| F18 | Khối khác | Extend later | v2.0 |
| F20 | Lưu lịch sử đề | Database setup | v1.1 |

---

## 4. Technical Scope (MVP)

### 4.1 Tech Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    MVP TECH STACK                           │
└─────────────────────────────────────────────────────────────┘

Frontend:
├── React.js
├── Vite
├── TypeScript
└── Tailwind CSS

Backend:
├── FastAPI (Python)
├── uv (package manager)
└── API endpoints

AI:
├── Google Gemini API
└── Prompt templates

Data:
├── Local JSON curriculum
└── PostgreSQL + JSONB

Export:
├── python-docx
└── Word templates

Hosting:
├── Docker Compose
└── Local / Cloud
```

### 4.2 Architecture (MVP)

```
┌─────────────────────────────────────────────────────────────┐
│                    MVP ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────┘

┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │────▶│ Frontend│────▶│ Backend │────▶│   AI    │
│ Browser │     │ (React) │     │ (FastAPI)│    │ (Gemini)│
└─────────┘     └─────────┘     └─────────┘     └─────────┘
                     │               │
                     │               ▼
                     │          ┌─────────┐
                     │          │PostgreSQL│
                     │          │   DB    │
                     │          └─────────┘
                     │               │
                     │               ▼
                     │          ┌─────────┐
                     └──────────│ Export  │
                                │ (Word)  │
                                └─────────┘
```

### 4.3 API Endpoints (MVP)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/data/ingest | Nạp dữ liệu từ nhiều nguồn |
| POST | /api/data/normalize | Chuẩn hóa dữ liệu |
| POST | /api/curriculum/confirm | Giáo viên xác nhận phạm vi |
| POST | /api/matrix/generate | Tạo ma trận |
| POST | /api/specification/generate | Tạo bản đặc tả |
| POST | /api/questions/generate | Sinh câu hỏi |
| POST | /api/questions/review | Giáo viên duyệt câu hỏi |
| POST | /api/answers/generate | Sinh đáp án & rubric |
| POST | /api/validate | Kiểm tra format |
| POST | /api/export | Export Word |

---

## 5. User Stories (MVP)

### 5.1 Epic: Tạo đề kiểm tra

#### Story 0: Nạp nguồn dữ liệu
```
As a giáo viên,
I want to hệ thống nạp dữ liệu chương trình từ local JSON và tài liệu tôi upload
So that tôi có dữ liệu chính xác để tạo đề
```
**Acceptance Criteria:**
- [ ] Hệ thống tải curriculum từ local JSON
- [x] Giáo viên có thể upload PDF/DOCX/XLSX và ảnh PNG/JPEG; OCR tùy cấu hình
- [ ] Dữ liệu được chuẩn hóa về schema chung
- [ ] Hiển thị nguồn dữ liệu đã nạp

#### Story 1: Giáo viên xác nhận phạm vi
```
As a giáo viên,
I want to xác nhận phạm vi kiểm tra
So that hệ thống tạo đề đúng với nội dung tôi đã dạy
```
**Acceptance Criteria:**
- [ ] Hiển thị thông tin trường, năm học, khối
- [ ] Hiển thị danh sách chủ đề từ dữ liệu đã nạp
- [ ] Giáo viên có thể chỉnh sửa chủ đề/số tiết
- [ ] Giáo viên xác nhận tỉ lệ N/V/Vd

#### Story 2: Xem và chỉnh sửa ma trận
```
As a giáo viên,
I want to xem ma trận đề kiểm tra do AI tạo
So that tôi có thể kiểm tra và chỉnh sửa trước khi tạo đề
```
**Acceptance Criteria:**
- [ ] Hiển thị dạng bảng
- [ ] Chỉnh sửa số câu/điểm từng ô
- [ ] Tính tổng tự động

#### Story 3: Xem bản đặc tả
```
As a giáo viên,
I want to xem bản đặc tả chi tiết
So that tôi biết mỗi câu hỏi đánh giá gì
```
**Acceptance Criteria:**
- [ ] Hiển thị bảng đặc tả
- [ ] Mapping với ma trận
- [ ] Chỉnh sửa được

#### Story 4: Xem đề kiểm tra & Duyệt câu hỏi
```
As a giáo viên,
I want to xem đề kiểm tra do AI tạo và duyệt từng câu
So that tôi có thể chấp nhận câu tốt và yêu cầu tạo lại câu chưa đạt
```
**Acceptance Criteria:**
- [ ] Hiển thị đầy đủ 4 phần
- [ ] Có nút ✅ accepted, 🔄 needs_revision, ❌ rejected
- [ ] Chỉ tạo lại câu cần sửa
- [ ] Câu đã duyệt giữ nguyên

#### Story 5: Xem đáp án và rubric
```
As a giáo viên,
I want to xem đáp án và hướng dẫn chấm
So that tôi có thể sử dụng để chấm bài
```
**Acceptance Criteria:**
- [ ] Đáp án đầy đủ
- [ ] Giải thích chi tiết
- [ ] Rubric cho câu tự luận

#### Story 6: Kiểm tra format
```
As a giáo viên,
I want to hệ thống tự kiểm tra format
So that tôi yên tâm đề đúng quy định
```
**Acceptance Criteria:**
- [ ] Tự động validate
- [ ] Hiển thị kết quả
- [ ] Cảnh báo lỗi

#### Story 7: Export Word
```
As a giáo viên,
I want to xuất file Word
So that tôi có thể in và sử dụng
```
**Acceptance Criteria:**
- [ ] Export 5 file
- [ ] Format đẹp
- [ ] Tải về được

---

## 6. Milestones

### Week 1: Foundation
- [ ] Setup project structure
- [ ] Setup frontend (React + Vite)
- [ ] Setup backend (FastAPI + uv)
- [ ] Setup Gemini API integration
- [ ] Create local JSON curriculum data
- [ ] Create basic UI components

### Week 2: Core Logic
- [ ] Implement Data Ingestion Agent
- [ ] Implement Document Processing Agent
- [ ] Implement Matrix Generation Agent
- [ ] Implement Specification Generation Agent
- [ ] Create prompt templates
- [ ] Test AI integration

### Week 3: Features
- [ ] Implement Question Generation Agent
- [ ] Implement Teacher Review flow
- [ ] Implement Answer & Rubric Agent
- [ ] Implement Validation Agent
- [ ] Create Word templates
- [ ] Build complete UI flow

### Week 4: Polish
- [ ] UI/UX improvements
- [ ] Error handling
- [ ] Performance optimization
- [ ] User testing
- [ ] Bug fixes

---

## 7. Deliverables

### 7.1 Software
- [ ] Web application (deployed)
- [ ] API documentation
- [ ] Source code (GitHub)

### 7.2 Documentation
- [ ] User guide
- [ ] Technical documentation
- [ ] API documentation

### 7.3 Testing
- [ ] Unit tests
- [ ] Integration tests
- [ ] User acceptance tests

---

## 8. Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| AI sinh câu hỏi sai | Medium | High | Validation layer + human review |
| Format không đúng | Low | High | Template-based + validation |
| Performance chậm | Medium | Medium | Caching + optimization |
| User không adopt | Low | Medium | Simple UI + training |
| Thiếu dữ liệu chương trình | Low | High | Local JSON + teacher upload |

---

## 9. Definition of Done

### 9.1 Feature Done
- [ ] Code complete
- [ ] Tests pass
- [ ] Code reviewed
- [ ] Documentation updated

### 9.2 MVP Done
- [ ] All P0 features complete
- [ ] All user stories accepted
- [ ] Performance targets met
- [ ] No critical bugs
- [ ] Deployed to production

---

## 10. Resource Requirements

### 10.1 Team
- 1 Full-stack Developer
- 1 AI/ML Engineer (part-time)

### 10.2 Infrastructure
- Gemini API key
- Docker Compose
- PostgreSQL

### 10.3 Budget
| Item | Cost/month |
|------|------------|
| AI API | $50-100 |
| Hosting | $20 |
| Total | $70-120 |

---

## 11. Local Curriculum JSON (Seed Data)

### 11.1 Tổng quan

Local Curriculum JSON là **seed data chuẩn hóa** cho môn Khoa học tự nhiên cấp THCS (khối 6-9). Dữ liệu này được tạo từ tài liệu chương trình giáo dục, **không phải nguồn kiến thức tuyệt đối**.

**Lưu ý quan trọng:**
- Tất cả dữ liệu có `status = "draft"`
- Tất cả có `requires_teacher_review = true`
- Giáo viên phải luôn xác nhận trước khi tạo ma trận
- Đây là seed data, không phải nguồn kiến thức tuyệt đối
- Không dùng web crawling hay Gemini API để tạo dữ liệu

### 11.2 Cấu trúc thư mục

```
backend/
  data/
    curriculum/
      khtn_grade_6.json    # KHTN lớp 6 (11 topics, 53 objectives)
      khtn_grade_7.json    # KHTN lớp 7 (12 topics, 51 objectives)
      khtn_grade_8.json    # KHTN lớp 8 (12 topics, 55 objectives)
      khtn_grade_9.json    # KHTN lớp 9 (12 topics, 54 objectives)
    templates/
      exam_structure_templates.json
      matrix_templates.json
      rubric_templates.json
```

### 11.3 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/curriculum/grades` | Liệt kê khối lớp có sẵn |
| GET | `/api/curriculum/{grade}` | Lấy toàn bộ curriculum |
| GET | `/api/curriculum/{grade}/exam-scopes` | Lấy danh sách exam scopes |
| GET | `/api/curriculum/{grade}/exam-scopes/{exam_type}` | Lấy exam scope cụ thể |
| GET | `/api/curriculum/{grade}/exam-scopes/{exam_type}/topics` | Lấy topic theo exam scope |
| GET | `/api/curriculum/{grade}/topics` | Lấy tất cả topic |
| GET | `/api/curriculum/{grade}/topics/{topic_id}` | Lấy topic theo ID |
| GET | `/api/curriculum/{grade}/topics/{topic_id}/objectives` | Lấy objectives |
| GET | `/api/curriculum/validate/all` | Validate tất cả file |

### 11.4 Service Functions

```python
# backend/app/services/curriculum_service.py

load_curriculum(grade: int) -> dict
list_available_grades() -> list[int]
get_exam_scope(grade: int, exam_type: str) -> dict
get_topics_by_exam_scope(grade: int, exam_type: str) -> list[dict]
get_all_topics(grade: int) -> list[dict]
get_topic_by_id(grade: int, topic_id: str) -> Optional[dict]
get_learning_objectives(grade: int, topic_id: str) -> list[dict]
validate_curriculum_schema(curriculum: dict) -> list[str]
validate_all_curriculum_files() -> dict[int, list[str]]
```

### 11.5 Test nhanh

```bash
# Test JSON validity
python -m json.tool backend/data/curriculum/khtn_grade_6.json
python -m json.tool backend/data/curriculum/khtn_grade_7.json
python -m json.tool backend/data/curriculum/khtn_grade_8.json
python -m json.tool backend/data/curriculum/khtn_grade_9.json

# Test curriculum service
cd backend && python -c "
import sys
sys.path.insert(0, '.')
from app.services.curriculum_service import validate_all_curriculum_files
print(validate_all_curriculum_files())
"
```
