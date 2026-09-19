# Future Features
# Smart Exam Matrix AI

Trạng thái tính năng hiện tại được mô tả ở [authoring capabilities](product/authoring-capabilities.md).
Các roadmap mở rộng môn/khối trong tài liệu lịch sử này không thuộc phạm vi triển khai hiện tại.

## 1. Feature Roadmap

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FEATURE ROADMAP                                 │
│                    (Flow mới: Nạp dữ liệu + RAG)                        │
└─────────────────────────────────────────────────────────────────────────┘

Phase 1 (MVP)          Phase 2              Phase 3              Phase 4
4 weeks                4 weeks              4 weeks              Ongoing
─────────────────────────────────────────────────────────────────────────
│                      │                    │                    │
▼                      ▼                    ▼                    ▼
Core Features          Enhancement          Scale                Advanced
• Nạp dữ liệu local   • Upload PDF/DOCX    • Môn khác           • Analytics
• 4 dạng câu hỏi      • RAG pipeline       • Khối khác          • AI training
• Export Word          • Vector DB          • Template           • Integration
• Validation           • Question bank      • Collaboration      • Mobile app
```

---

## 2. Phase 2: Enhancement (v1.1)

### 2.1 Upload PDF/DOCX/XLSX — đã triển khai, bổ sung OCR PDF/ảnh ở US-168

**Description:** Giáo viên upload tài liệu để bổ sung dữ liệu

**Features:**
- Upload PDF phân phối chương trình
- Upload DOCX bài giảng
- Upload XLSX bảng điểm
- Auto-extract text
- Parse tables

**Data Schema:**
```json
{
  "uploaded_file": {
    "id": "uuid",
    "file_name": "string",
    "file_type": "pdf|docx|xlsx",
    "file_size": "integer",
    "extracted_text": "string",
    "parsed_data": {},
    "status": "pending|processed|failed"
  }
}
```

---

### 2.2 RAG Knowledge Base — đã triển khai, hybrid/RRF/rerank ở US-168

**Description:** Hệ thống RAG retrieval từ kho tài liệu nội bộ

**Luồng RAG:**
```
Teacher Upload / Local JSON
        ↓
Document Processor
        ↓
Text Extraction
        ↓
Chunking
        ↓
Embedding
        ↓
Vector Database (ChromaDB)
        ↓
Retriever
        ↓
Prompt Builder
        ↓
LLM Generator
        ↓
Matrix / Specification / Questions / Rubric
```

**Lý do RAG tốt hơn tự crawl data:**
- Bám chương trình hơn
- Kiểm soát nguồn tốt hơn
- Ít hallucination hơn
- Không phụ thuộc quota API quá nhiều
- Phù hợp giáo viên vì có thể dùng tài liệu trường cung cấp
- Dễ audit nguồn dữ liệu

---

### 2.3 Vector Database

**Description:** Lưu trữ embeddings để tìm kiếm semantic

**Features:**
- ChromaDB integration
- Document embedding
- Semantic search
- Context retrieval

**Data Schema:**
```json
{
  "vector_document": {
    "id": "uuid",
    "content": "string",
    "embedding": [],
    "metadata": {
      "source": "string",
      "page": "integer",
      "topic": "string"
    }
  }
}
```

---

### 2.4 Question Bank

**Description:** Ngân hàng câu hỏi tái sử dụng

**Features:**
- Lưu câu hỏi yêu thích
- Phân loại theo chủ đề
- Tìm kiếm câu hỏi
- Import/Export câu hỏi
- Reuse câu hỏi đã duyệt

**Data Schema:**
```json
{
  "question_bank": {
    "id": "uuid",
    "questions": [
      {
        "id": "uuid",
        "content": "string",
        "type": "string",
        "difficulty": "string",
        "topic": "string",
        "tags": ["string"],
        "usage_count": "integer",
        "rating": "number"
      }
    ]
  }
}
```

---

### 2.5 PDF Export — đã triển khai

**Hiện tại:** PDF xuất trực tiếp bằng ReportLab; công thức và rich content được render. Các ý bên dưới là kế hoạch lịch sử.

**Features:**
- Export PDF trực tiếp từ dữ liệu đề, không cần Word
- PDF preview
- Batch export

---

### 2.6 Lưu lịch sử đề

**Description:** Lưu và quản lý đề đã tạo

**Features:**
- Lưu đề vào database
- Tải lại đề đã lưu
- Xem lịch sử tạo đề
- Duplicate đề

---

## 3. Phase 3: Scale (v2.0)

### 3.1 Multi-Subject Support

**Description:** Mở rộng sang các môn khác

**Subjects:**
| Subject | Priority | Complexity |
|---------|----------|------------|
| Toán học | High | Medium |
| Ngữ văn | High | High |
| Tiếng Anh | High | Medium |
| Lịch sử | Medium | Medium |
| Địa lí | Medium | Medium |
| Vật lí | Medium | Medium |
| Hóa học | Medium | Medium |
| Sinh học | Medium | Medium |

---

### 3.2 Multi-Grade Support

**Description:** Mở rộng sang các khối lớp khác

**Grades:**
| Grade | Priority | Notes |
|-------|----------|-------|
| 6 | High | Similar to 8 |
| 7 | High | Similar to 8 |
| 9 | High | Similar to 8 |
| 10 | Medium | THPT curriculum |
| 11 | Medium | THPT curriculum |
| 12 | Medium | THPT curriculum |

---

### 3.3 Admin/Teacher Roles

**Description:** Phân quyền giáo viên/admin

**Features:**
- Admin quản lý hệ thống
- Giáo viên tạo đề
- Tổ trưởng duyệt đề
- Phân quyền theo trường

---

### 3.4 Multi-School Support

**Description:** Hỗ trợ nhiều trường

**Features:**
- Mỗi trường có workspace riêng
- Chia sẻ đề trong trường
- Thống kê theo trường

---

### 3.5 Template System

**Description:** Hệ thống template tùy chỉnh

**Features:**
- Template mặc định
- Tạo template mới
- Chia sẻ template
- Import/Export template

---

## 4. Phase 4: Advanced (v3.0)

### 4.1 Analytics Dashboard

**Description:** Dashboard phân tích

**Features:**
- Thống kê số đề đã tạo
- Phân tích chất lượng đề
- Xu hướng sử dụng
- Báo cáo hiệu quả

---

### 4.2 AI Training & Customization

**Description:** Training AI theo phong cách giáo viên

**Features:**
- Học từ đề đã tạo
- Phong cách câu hỏi
- Ngân hàng câu hỏi cá nhân
- Fine-tuning model

---

### 4.3 Plagiarism/Duplicate Detection

**Description:** Phát hiện câu hỏi trùng lặp

**Features:**
- So sánh với question bank
- Phát hiện câu hỏi tương tự
- Cảnh báo trùng lặp

---

### 4.4 Difficulty Calibration

**Description:** Hiệu chỉnh độ khó câu hỏi

**Features:**
- Phân tích độ khó thực tế
- Hiệu chỉnh dựa trên dữ liệu
- Đề xuất điều chỉnh

---

### 4.5 Integration Features

**Description:** Tích hợp với hệ thống khác

**Integrations:**
| System | Type | Priority |
|--------|------|----------|
| Google Classroom | LMS | High |
| Microsoft Teams | LMS | Medium |
| Moodle | LMS | Medium |

---

### 4.6 Mobile App

**Description:** Ứng dụng di động

**Features:**
- Tạo đề trên điện thoại
- Xem lại đề đã tạo
- Export từ điện thoại

---

## 5. Data Schema Evolution

### 5.1 Schema Versioning

```json
{
  "schema_version": "1.0.0",
  "migrations": [
    {
      "version": "1.0.0",
      "description": "Initial schema (MVP)",
      "changes": []
    },
    {
      "version": "1.1.0",
      "description": "Add RAG, question bank",
      "changes": [
        "Add vector_documents table",
        "Add question_bank table",
        "Add uploaded_documents table"
      ]
    },
    {
      "version": "2.0.0",
      "description": "Multi-subject, multi-school",
      "changes": [
        "Add subjects table",
        "Add schools table",
        "Add templates table"
      ]
    }
  ]
}
```

---

## 6. Performance Improvements

### 6.1 Current Performance (MVP)

| Metric | Target | Current |
|--------|--------|---------|
| Generation time | < 60s | TBD |
| Export time | < 10s | TBD |
| API response | < 500ms | TBD |

### 6.2 Future Performance Targets

| Metric | Phase 2 | Phase 3 |
|--------|---------|---------|
| Generation time | < 30s | < 15s |
| Export time | < 5s | < 2s |
| API response | < 200ms | < 100ms |
| Concurrent users | 100 | 1000 |

---

## 7. Success Metrics (Future)

| Metric | Phase 2 | Phase 3 | Phase 4 |
|--------|---------|---------|---------|
| Registered users | 500 | 5,000 | 50,000 |
| Daily active users | 100 | 1,000 | 10,000 |
| Exams created/day | 200 | 2,000 | 20,000 |
| User satisfaction | 4.5/5 | 4.7/5 | 4.8/5 |
| Retention rate | 60% | 70% | 80% |
