# Data Schema
# Smart Exam Matrix AI

## 1. Tổng quan Schema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA SCHEMA OVERVIEW                            │
│                    (Flow mới: Nạp dữ liệu + RAG)                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  DataSource │    │  Normalized │    │  ExamMatrix │    │Specification│
│  (Nhiều)    │    │  Curriculum │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                  │                  │                  │
       └──────────────────┴──────────────────┴──────────────────┘
                                │
                                ▼
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Question   │    │  Question   │    │   Answer    │    │   Rubric    │
│             │    │  Review     │    │             │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                │
                                ▼
                     ┌─────────────┐    ┌─────────────┐
                     │ Validation  │    │   Export    │
                     │   Result    │    │  Package    │
                     └─────────────┘    └─────────────┘
```

---

## 2. Root Schema

```json
{
  "data_sources": [],
  "normalized_curriculum": {},
  "exam_info": {},
  "blueprint": {},
  "matrix": [],
  "specification": [],
  "questions": [],
  "question_reviews": {},
  "answer_key": [],
  "rubric": [],
  "validation": {},
  "export_package": {}
}
```

---

## 3. Chi tiết từng Schema

### 3.1 CurriculumSource

Metadata nguồn dữ liệu.

```json
{
  "data_sources": [
    {
      "source_type": "local_json",
      "source_name": "curriculum_grade8_khtn.json",
      "source_page": null,
      "confidence_score": 1.0,
      "loaded_at": "2025-01-01T00:00:00Z"
    },
    {
      "source_type": "uploaded_file",
      "source_name": "phan_phoi_chuong_trinh.pdf",
      "source_page": 1,
      "confidence_score": 0.9,
      "loaded_at": "2025-01-01T00:00:00Z"
    },
    {
      "source_type": "question_bank",
      "source_name": "ma_tran_mau_2024.json",
      "source_page": null,
      "confidence_score": 0.85,
      "loaded_at": "2025-01-01T00:00:00Z"
    },
    {
      "source_type": "rag_retrieval",
      "source_name": "knowledge_base",
      "source_page": 45,
      "confidence_score": 0.8,
      "loaded_at": "2025-01-01T00:00:00Z"
    }
  ]
}
```

**Enum values:**
```json
{
  "source_type": [
    "local_json",
    "uploaded_file",
    "question_bank",
    "rag_retrieval",
    "manual_input"
  ]
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| source_type | string | Yes | Loại nguồn dữ liệu |
| source_name | string | Yes | Tên file/nguồn |
| source_page | integer | No | Trang (nếu là file) |
| confidence_score | number | Yes | Độ tin cậy (0-1) |
| loaded_at | datetime | Yes | Thời gian tải |

---

### 3.2 UploadedDocument

Tài liệu giáo viên upload.

```json
{
  "uploaded_document": {
    "id": "doc_uuid",
    "file_name": "phan_phoi_chuong_trinh.pdf",
    "file_type": "pdf",
    "file_size": 1024000,
    "uploaded_at": "2025-01-01T00:00:00Z",
    "uploaded_by": "user_id",
    "status": "processed",
    "extracted_text": "Phân phối chương trình KHTN lớp 8...",
    "metadata": {
      "pages": 5,
      "language": "vi"
    }
  }
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| id | string (uuid) | Yes | ID duy nhất |
| file_name | string | Yes | Tên file |
| file_type | string | Yes | Loại file (pdf, docx, xlsx) |
| file_size | integer | Yes | Kích thước (bytes) |
| uploaded_at | datetime | Yes | Thời gian upload |
| uploaded_by | string | Yes | Người upload |
| status | string | Yes | Trạng thái (pending, processed, failed) |
| extracted_text | string | No | Text đã trích xuất |
| metadata | object | No | Metadata thêm |

---

### 3.3 NormalizedCurriculum

Chương trình đã chuẩn hóa.

```json
{
  "normalized_curriculum": {
    "grade": 8,
    "subject": "Khoa học tự nhiên",
    "exam_type": "Giữa học kì I",
    "school_year": "2025-2026",
    "topics": [
      {
        "id": "topic_1",
        "name": "Hệ tuần hoàn",
        "periods": 6,
        "objectives": [
          "Mô tả được cấu tạo và chức năng của hệ tuần hoàn",
          "Trình bày được vai trò của tim và mạch máu"
        ],
        "lessons": [
          {
            "id": "lesson_1_1",
            "name": "Bài 1: Tim và mạch máu",
            "periods": 3,
            "knowledge_units": [
              {
                "id": "ku_1",
                "content": "Cấu tạo tim người",
                "achievements": [
                  "Mô tả được cấu tạo tim người",
                  "Vẽ và chú thích sơ đồ tim người"
                ],
                "bloom_level": "remember"
              }
            ]
          }
        ]
      }
    ],
    "metadata": {
      "sources": ["local_json", "uploaded_file"],
      "processed_at": "2025-01-01T00:00:00Z"
    }
  }
}
```

---

### 3.4 Topic

Chủ đề trong chương trình.

```json
{
  "topic": {
    "id": "topic_1",
    "name": "Hệ tuần hoàn",
    "periods": 6,
    "objectives": [
      "Mô tả được cấu tạo và chức năng của hệ tuần hoàn"
    ],
    "lessons": []
  }
}
```

---

### 3.5 LearningObjective

Yêu cầu cần đạt.

```json
{
  "learning_objective": {
    "id": "obj_1",
    "content": "Mô tả được cấu tạo tim người",
    "bloom_level": "remember",
    "topic_id": "topic_1",
    "lesson_id": "lesson_1_1"
  }
}
```

---

### 3.6 ExamMatrix

Ma trận đề kiểm tra theo format Công văn 7991.

```json
{
  "matrix": [
    {
      "id": "matrix_1",
      "topic_id": "topic_1",
      "topic_name": "Chủ đề 1: Hệ tuần hoàn",
      "lesson_id": "lesson_1_1",
      "lesson_name": "Bài 1: Tim và mạch máu",
      "nhan_biet": {
        "count": 1,
        "score": 0.25,
        "question_type": "multiple_choice",
        "question_ids": ["q_1"]
      },
      "thong_hieu": {
        "count": 1,
        "score": 0.5,
        "question_type": "true_false",
        "question_ids": ["q_9"]
      },
      "van_dung": {
        "count": 0,
        "score": 0,
        "question_type": null,
        "question_ids": []
      },
      "total_score": 0.75
    }
  ],
  "summary": {
    "nhan_biet": {
      "total_count": 5,
      "total_score": 1.25,
      "percentage": 30
    },
    "thong_hieu": {
      "total_count": 4,
      "total_score": 4.0,
      "percentage": 40
    },
    "van_dung": {
      "total_count": 3,
      "total_score": 4.75,
      "percentage": 30
    },
    "total_score": 10
  }
}
```

---

### 3.7 Specification

Bản đặc tả đề kiểm tra chi tiết.

```json
{
  "specification": [
    {
      "question_number": 1,
      "topic": "Chủ đề 1: Hệ tuần hoàn",
      "lesson": "Bài 1: Tim và mạch máu",
      "knowledge_unit": "Cấu tạo tim người",
      "achievement": "Mô tả được cấu tạo tim người",
      "difficulty": "nhan_biet",
      "question_type": "multiple_choice",
      "score": 0.25,
      "bloom_level": "remember",
      "content_hint": "Câu hỏi về cấu tạo tim",
      "question_id": "q_1"
    }
  ]
}
```

---

### 3.8 Question

Danh sách câu hỏi.

```json
{
  "questions": [
    {
      "id": "q_1",
      "number": 1,
      "type": "multiple_choice",
      "difficulty": "nhan_biet",
      "score": 0.25,
      "content": "Tim người có bao nhiêu ngăn?",
      "options": {
        "A": "2 ngăn",
        "B": "3 ngăn",
        "C": "4 ngăn",
        "D": "5 ngăn"
      },
      "metadata": {
        "topic": "Chủ đề 1: Hệ tuần hoàn",
        "lesson": "Bài 1: Tim và mạch máu",
        "knowledge_unit": "Cấu tạo tim người",
        "achievement": "Mô tả được cấu tạo tim người",
        "bloom_level": "remember"
      },
      "source": {
        "source_type": "local_json",
        "source_name": "curriculum_grade8_khtn.json",
        "source_page": null,
        "confidence_score": 0.95
      }
    }
  ]
}
```

---

### 3.9 QuestionReviewStatus (MỚI)

Trạng thái duyệt câu hỏi.

```json
{
  "question_reviews": {
    "q_1": {
      "status": "accepted",
      "reviewed_at": "2025-01-01T00:00:00Z",
      "reviewed_by": "teacher_id",
      "comment": null
    },
    "q_2": {
      "status": "needs_revision",
      "reviewed_at": "2025-01-01T00:00:00Z",
      "reviewed_by": "teacher_id",
      "comment": "Phương án nhiễu không hợp lý"
    },
    "q_15": {
      "status": "rejected",
      "reviewed_at": "2025-01-01T00:00:00Z",
      "reviewed_by": "teacher_id",
      "comment": "Câu hỏi quá dài"
    }
  }
}
```

**Enum values:**
```json
{
  "status": [
    "accepted",
    "needs_revision",
    "rejected"
  ]
}
```

**Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| status | string | Yes | Trạng thái duyệt |
| reviewed_at | datetime | Yes | Thời gian duyệt |
| reviewed_by | string | Yes | Người duyệt |
| comment | string | No | Ghi chú |

---

### 3.10 Answer

Đáp án chi tiết.

```json
{
  "answer_key": [
    {
      "question_id": "q_1",
      "question_number": 1,
      "type": "multiple_choice",
      "correct_answer": "C",
      "explanation": "Tim người có 4 ngăn: 2 tâm nhĩ và 2 tâm thất."
    },
    {
      "question_id": "q_9",
      "question_number": 9,
      "type": "true_false",
      "answers": [
        {
          "statement_id": "s_9_1",
          "is_true": true,
          "explanation": "Tim người có 4 ngăn."
        }
      ]
    },
    {
      "question_id": "q_13",
      "question_number": 13,
      "type": "short_answer",
      "correct_answer": "Van tim ngăn máu chảy ngược.",
      "keywords": ["ngăn", "ngược", "một chiều"],
      "accept_variations": true
    },
    {
      "question_id": "q_15",
      "question_number": 15,
      "type": "essay",
      "model_answer": "Đường đi của máu qua tim: ...",
      "key_points": [
        "Máu tĩnh mạch về tâm nhĩ phải",
        "Tâm nhĩ phải co đẩy máu xuống tâm thất phải",
        "Tâm thất phải co đẩy máu lên phổi"
      ]
    }
  ]
}
```

---

### 3.11 Rubric

Hướng dẫn chấm điểm.

```json
{
  "rubric": [
    {
      "question_id": "q_15",
      "question_number": 15,
      "type": "essay",
      "total_score": 2.0,
      "criteria": [
        {
          "id": "c_1",
          "name": "Nội dung",
          "max_score": 1.5,
          "levels": [
            {
              "score": 1.5,
              "description": "Trình bày đầy đủ, chính xác đường đi của máu qua tim",
              "criteria": "Đủ 7 key points"
            },
            {
              "score": 1.0,
              "description": "Trình bày được 5-6 key points",
              "criteria": "Đủ 5-6 key points"
            },
            {
              "score": 0.5,
              "description": "Trình bày được 3-4 key points",
              "criteria": "Đủ 3-4 key points"
            },
            {
              "score": 0,
              "description": "Trình bày dưới 3 key points hoặc sai",
              "criteria": "Dưới 3 key points"
            }
          ]
        },
        {
          "id": "c_2",
          "name": "Diễn đạt",
          "max_score": 0.5,
          "levels": [
            {
              "score": 0.5,
              "description": "Diễn đạt rõ ràng, logic, đúng thuật ngữ",
              "criteria": "Không lỗi chính tả, dùng đúng thuật ngữ"
            },
            {
              "score": 0.25,
              "description": "Diễn đạt tương đối rõ ràng, có vài lỗi nhỏ",
              "criteria": "1-2 lỗi nhỏ"
            },
            {
              "score": 0,
              "description": "Diễn đạt khó hiểu, nhiều lỗi",
              "criteria": "Trên 2 lỗi hoặc khó hiểu"
            }
          ]
        }
      ],
      "grading_guide": [
        "Chấm theo key points trước",
        "Sau đó chấm diễn đạt",
        "Không trừ điểm trùng lặp ý"
      ]
    }
  ]
}
```

---

### 3.12 ValidationResult

Kết quả kiểm tra.

```json
{
  "validation": {
    "passed": true,
    "score": 95,
    "timestamp": "2025-01-01T00:00:00Z",
    "checks": [
      {
        "id": "check_1",
        "name": "Tổng điểm",
        "category": "format",
        "status": "pass",
        "expected": 10,
        "actual": 10,
        "message": "Tổng điểm đạt yêu cầu"
      },
      {
        "id": "check_2",
        "name": "Phân bổ Nhận biết",
        "category": "format",
        "status": "pass",
        "expected": 30,
        "actual": 30,
        "message": "Phân bổ mức Nhận biết đạt yêu cầu"
      },
      {
        "id": "check_3",
        "name": "Không thiếu đáp án",
        "category": "content",
        "status": "pass",
        "message": "Tất cả câu hỏi đều có đáp án"
      },
      {
        "id": "check_4",
        "name": "Không thiếu rubric",
        "category": "rubric",
        "status": "pass",
        "message": "Tất cả câu tự luận đều có rubric"
      },
      {
        "id": "check_5",
        "name": "Không trùng lặp",
        "category": "content",
        "status": "pass",
        "message": "Không có câu hỏi trùng lặp"
      }
    ],
    "warnings": [],
    "errors": []
  }
}
```

**Enum values cho category:**
```json
{
  "category": [
    "format",
    "content",
    "matrix",
    "rubric"
  ]
}
```

---

### 3.13 ExportPackage

Gói export.

```json
{
  "export_package": {
    "id": "export_uuid",
    "exam_id": "exam_uuid",
    "created_at": "2025-01-01T00:00:00Z",
    "format": "docx",
    "files": [
      {
        "name": "Ma tran de kiem tra.docx",
        "type": "matrix",
        "size": 102400
      },
      {
        "name": "Ban dac ta de kiem tra.docx",
        "type": "specification",
        "size": 153600
      },
      {
        "name": "De kiem tra.docx",
        "type": "exam",
        "size": 204800
      },
      {
        "name": "Dap an.docx",
        "type": "answer_key",
        "size": 128000
      },
      {
        "name": "Rubric.docx",
        "type": "rubric",
        "size": 102400
      }
    ],
    "status": "completed"
  }
}
```

---

## 4. Relationships

```
data_sources (N) ──────────────── normalized_curriculum (1)
                                         │
                                         │
                                         ▼
                              specification (N) ◀──── matrix (N)
                                         │
                                         │
                                         ▼
                              questions (N) ◀──── question_reviews (N)
                                         │
                                         │
                              ┌──────────┴──────────┐
                              ▼                     ▼
                        answer_key (N)         rubric (N)
                              │                     │
                              └──────────┬──────────┘
                                         │
                                         ▼
                                    validation (1)
                                         │
                                         ▼
                                  export_package (1)
```

---

## 5. Database Tables (SQL)

### 5.1 data_sources
```sql
CREATE TABLE data_sources (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    source_type VARCHAR(50) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    source_page INT,
    confidence_score DECIMAL(3,2) NOT NULL,
    loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_data_sources_exam_id ON data_sources(exam_id);
CREATE INDEX idx_data_sources_source_type ON data_sources(source_type);
```

### 5.2 uploaded_documents
```sql
CREATE TABLE uploaded_documents (
    id UUID PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,
    file_size INT NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_by UUID REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'pending',
    extracted_text TEXT,
    metadata JSONB
);
```

### 5.3 normalized_curriculum
```sql
CREATE TABLE normalized_curriculum (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    grade INT NOT NULL,
    subject VARCHAR(100) NOT NULL,
    exam_type VARCHAR(50) NOT NULL,
    school_year VARCHAR(20) NOT NULL,
    topics JSONB NOT NULL,
    metadata JSONB,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.4 exams
```sql
CREATE TABLE exams (
    id UUID PRIMARY KEY,
    school VARCHAR(255) NOT NULL,
    grade INT NOT NULL,
    subject VARCHAR(100) NOT NULL,
    exam_type VARCHAR(50) NOT NULL,
    duration_minutes INT NOT NULL,
    school_year VARCHAR(20) NOT NULL,
    total_score DECIMAL(3,1) DEFAULT 10,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by UUID REFERENCES users(id)
);
```

### 5.5 blueprints
```sql
CREATE TABLE blueprints (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    difficulty_ratio JSONB NOT NULL,
    question_types JSONB NOT NULL,
    total_questions INT NOT NULL
);
```

### 5.6 matrix
```sql
CREATE TABLE matrix (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    topic_id VARCHAR(50) NOT NULL,
    lesson_id VARCHAR(50) NOT NULL,
    nhan_biet JSONB,
    thong_hieu JSONB,
    van_dung JSONB,
    total_score DECIMAL(3,1)
);
```

### 5.7 specification
```sql
CREATE TABLE specification (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    question_number INT NOT NULL,
    topic VARCHAR(255) NOT NULL,
    lesson VARCHAR(255) NOT NULL,
    knowledge_unit VARCHAR(255) NOT NULL,
    achievement VARCHAR(255) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    question_type VARCHAR(20) NOT NULL,
    score DECIMAL(3,2) NOT NULL,
    bloom_level VARCHAR(20) NOT NULL,
    question_id UUID
);
```

### 5.8 questions
```sql
CREATE TABLE questions (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    number INT NOT NULL,
    type VARCHAR(20) NOT NULL,
    difficulty VARCHAR(20) NOT NULL,
    score DECIMAL(3,2) NOT NULL,
    content TEXT NOT NULL,
    options JSONB,
    statements JSONB,
    metadata JSONB,
    source JSONB
);
```

### 5.9 question_reviews (MỚI)
```sql
CREATE TABLE question_reviews (
    id UUID PRIMARY KEY,
    question_id UUID REFERENCES questions(id),
    exam_id UUID REFERENCES exams(id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    reviewed_by UUID REFERENCES users(id),
    comment TEXT
);

CREATE INDEX idx_question_reviews_exam_id ON question_reviews(exam_id);
CREATE INDEX idx_question_reviews_status ON question_reviews(status);
```

### 5.10 answer_key
```sql
CREATE TABLE answer_key (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    question_id UUID REFERENCES questions(id),
    correct_answer TEXT,
    explanation TEXT,
    keywords JSONB,
    model_answer TEXT,
    key_points JSONB
);
```

### 5.11 rubric
```sql
CREATE TABLE rubric (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    question_id UUID REFERENCES questions(id),
    total_score DECIMAL(3,1),
    criteria JSONB NOT NULL,
    grading_guide JSONB
);
```

### 5.12 validation_results
```sql
CREATE TABLE validation_results (
    id UUID PRIMARY KEY,
    exam_id UUID REFERENCES exams(id),
    passed BOOLEAN NOT NULL,
    score INT NOT NULL,
    checks JSONB NOT NULL,
    warnings JSONB,
    errors JSONB,
    validated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 6. Validation Rules Schema

```json
{
  "validation_rules": {
    "total_score": {
      "type": "equals",
      "value": 10,
      "error_message": "Tổng điểm phải bằng 10"
    },
    "difficulty_ratio_sum": {
      "type": "equals",
      "value": 100,
      "fields": ["nhan_biet", "thong_hieu", "van_dung"],
      "error_message": "Tổng tỷ lệ phân bổ phải bằng 100%"
    },
    "min_questions": {
      "type": "greater_than",
      "value": 9,
      "error_message": "Số câu hỏi tối thiểu là 10"
    },
    "no_missing_answers": {
      "type": "all_have",
      "field": "answer_key",
      "error_message": "Không được thiếu đáp án cho bất kỳ câu hỏi nào"
    },
    "no_missing_rubric": {
      "type": "all_essay_have",
      "field": "rubric",
      "error_message": "Câu tự luận phải có rubric"
    },
    "no_duplicates": {
      "type": "unique",
      "field": "content",
      "error_message": "Không được có câu hỏi trùng lặp"
    }
  }
}
```

---

## 7. Local Curriculum JSON (Seed Data)

### 7.1 Tổng quan

Local Curriculum JSON là **seed data chuẩn hóa** cho môn Khoa học tự nhiên cấp THCS (khối 6-9). Dữ liệu này được tạo từ tài liệu chương trình giáo dục, **không phải nguồn kiến thức tuyệt đối**.

**Lưu ý quan trọng:**
- Tất cả dữ liệu có `status = "draft"`
- Tất cả có `requires_teacher_review = true`
- Giáo viên phải luôn xác nhận trước khi tạo ma trận
- Đây là seed data, không phải nguồn kiến thức tuyệt đối

### 7.2 Cấu trúc thư mục

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

### 7.3 Curriculum Schema

```json
{
  "metadata": {
    "subject": "Khoa học tự nhiên",
    "grade": 6,
    "curriculum_version": "GDPT 2018",
    "school_year": "2025-2026",
    "source_type": "local_json",
    "source_name": "Local curriculum seed data",
    "status": "draft",
    "requires_teacher_review": true,
    "last_updated": "2026-06-02"
  },
  "cognitive_levels": {
    "recognition": "Nhận biết",
    "understanding": "Thông hiểu",
    "application": "Vận dụng",
    "high_application": "Vận dụng cao"
  },
  "question_types": {
    "multiple_choice": "Trắc nghiệm nhiều lựa chọn",
    "true_false": "Đúng/Sai",
    "short_answer": "Trả lời ngắn",
    "essay": "Tự luận"
  },
  "exam_scopes": [],
  "topics": []
}
```

### 7.4 Topic Schema

```json
{
  "id": "khtn6_topic_01",
  "name": "Mở đầu về Khoa học tự nhiên",
  "unit": "Chủ đề 1",
  "periods": 5,
  "summary": "Giới thiệu về khoa học tự nhiên...",
  "learning_objectives": [
    {
      "id": "khtn6_obj_001",
      "text": "Trình bày được khái niệm khoa học tự nhiên...",
      "level": "recognition",
      "keywords": ["khoa học tự nhiên", "ngành khoa học"],
      "source": {
        "source_type": "local_json",
        "source_name": "Local curriculum seed data",
        "source_page": null,
        "confidence_score": 0.7
      }
    }
  ],
  "suggested_question_types": [
    "multiple_choice",
    "true_false",
    "short_answer"
  ]
}
```

### 7.5 Exam Scope Schema

```json
{
  "exam_type": "midterm_1",
  "display_name": "Giữa học kì I",
  "included_topic_ids": [
    "khtn6_topic_01",
    "khtn6_topic_02",
    "khtn6_topic_03"
  ],
  "default_duration_minutes": 45,
  "default_total_score": 10,
  "suggested_distribution": {
    "recognition": 40,
    "understanding": 30,
    "application": 20,
    "high_application": 10
  },
  "requires_teacher_review": true
}
```

### 7.6 API Endpoints

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
| GET | `/api/curriculum/templates/{type}` | Liệt kê templates |
| GET | `/api/curriculum/templates/{type}/{id}` | Lấy template cụ thể |

### 7.7 Service Functions

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
load_template(template_type: str, template_id: str) -> Optional[dict]
list_templates(template_type: str) -> list[dict]
```
