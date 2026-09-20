# AI Agents Architecture
# Deka

## 1. Tổng quan kiến trúc

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DEKA                             │
│                      AI Agents Architecture                             │
│                      (Flow mới: Nạp dữ liệu + RAG)                      │
└─────────────────────────────────────────────────────────────────────────┘

                               ┌─────────────┐
                               │   USER      │
                               │  INTERFACE  │
                               └──────┬──────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR AGENT                              │
│                    (Điều phối toàn bộ luồng)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 0: DATA INGESTION AGENT                        │
│              (Nạp dữ liệu từ nhiều nguồn, KHÔNG tự crawl web)           │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 1: DOCUMENT PROCESSING AGENT                   │
│              (Trích xuất, chuẩn hóa dữ liệu về schema chung)            │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 2: RETRIEVER AGENT                             │
│              (Tìm kiếm từ knowledge base / RAG)                          │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 3: MATRIX GENERATION AGENT                     │
│              (Tạo ma trận đề kiểm tra)                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 4: SPECIFICATION GENERATION AGENT              │
│              (Tạo bản đặc tả đề kiểm tra)                              │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 5: QUESTION GENERATION AGENT                   │
│              (Sinh câu hỏi theo ma trận, KHÔNG tự bịa chương trình)     │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 6: TEACHER REVIEW AGENT                        │
│              (Xử lý duyệt câu hỏi: accepted/needs_revision/rejected)    │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 7: ANSWER & RUBRIC AGENT                       │
│              (Sinh đáp án & rubric cho câu hỏi đã duyệt)                │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 8: VALIDATION AGENT                            │
│              (Kiểm tra logic, format, điểm số, đáp án, rubric)           │
└─────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AGENT 9: EXPORT AGENT                                │
│              (Xuất file Word/PDF)                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Chi tiết từng Agent

### 2.1 Orchestrator Agent

**Vai trò:** Điều phối toàn bộ luồng xử lý

**Trách nhiệm:**
- Nhận input từ user
- Quản lý trạng thái (state management)
- Gọi các agent theo đúng thứ tự
- Xử lý lỗi và retry
- Trả kết quả cho user

**Flow điều phối:**

```
User Input
    │
    ▼
Orchestrator
    │
    ├─▶ Agent 0: Data Ingestion
    │       │
    │       ▼
    │   [Raw data from multiple sources]
    │
    ├─▶ Agent 1: Document Processing
    │       │
    │       ▼
    │   [Normalized curriculum data]
    │
    ├─▶ Agent 2: Retriever
    │       │
    │       ▼
    │   [Relevant context from knowledge base]
    │
    ├─▶ Agent 3: Matrix Generation
    │       │
    │       ▼
    │   [Exam matrix]
    │
    ├─▶ Agent 4: Specification Generation
    │       │
    │       ▼
    │   [Specification]
    │
    ├─▶ Agent 5: Question Generation
    │       │
    │       ▼
    │   [Questions]
    │
    ├─▶ Agent 6: Teacher Review
    │       │
    │       ▼
    │   [Reviewed questions]
    │
    ├─▶ Agent 7: Answer & Rubric
    │       │
    │       ▼
    │   [Answers & Rubric]
    │
    ├─▶ Agent 8: Validation
    │       │
    │       ▼
    │   [Validation report]
    │
    └─▶ Agent 9: Export
            │
            ▼
        [Word/PDF files]
```

---

### 2.2 Agent 0: Data Ingestion Agent

**Vai trò:** Nạp dữ liệu từ nhiều nguồn, **KHÔNG tự crawl web**

**Nguyên tắc cốt lõi:**
- AI không phải nguồn kiến thức chính
- AI chỉ là công cụ xử lý dữ liệu đã kiểm soát
- Ưu tiên local JSON > teacher upload > question bank > RAG > AI API

**Thứ tự ưu tiên nguồn dữ liệu:**

| Ưu tiên | Nguồn | Mô tả |
|---------|-------|-------|
| 1 | Local curriculum JSON | Chương trình chuẩn SGK đã chuẩn hóa |
| 2 | Teacher upload | PDF, DOCX, XLSX giáo viên cung cấp |
| 3 | Question bank | Ma trận mẫu, đặc tả mẫu, đề cũ |
| 4 | RAG retrieval | Tìm kiếm từ kho tài liệu nội bộ |
| 5 | AI API | Chỉ tóm tắt/chuyển đổi, không làm nguồn chính |

**Input:**
- Grade (khối lớp)
- Subject (môn học)
- Exam type (loại kiểm tra)
- Teacher uploads (nếu có)

**Output:**
```json
{
  "data_sources": [
    {
      "source_type": "local_json",
      "source_name": "curriculum_grade8_khtn.json",
      "source_page": null,
      "confidence_score": 1.0,
      "data": {}
    },
    {
      "source_type": "uploaded_file",
      "source_name": "phan_phoi_chuong_trinh.pdf",
      "source_page": 1,
      "confidence_score": 0.9,
      "data": {}
    }
  ],
  "raw_data": {}
}
```

**AI Model:** Không dùng AI cho bước này (rule-based)
**Thời gian xử lý:** < 5 giây

---

### 2.3 Agent 1: Document Processing Agent

**Vai trò:** Trích xuất, chuẩn hóa dữ liệu về schema chung

**Trách nhiệm:**
- Parse JSON curriculum files
- Extract text from PDF/DOCX
- Parse XLSX tables
- Normalize all data to common schema

**Input:**
- Raw data from Agent 0

**Output:**
```json
{
  "normalized_data": {
    "grade": 8,
    "subject": "Khoa học tự nhiên",
    "exam_type": "Giữa học kì I",
    "school_year": "2025-2026",
    "topics": [
      {
        "name": "Hệ tuần hoàn",
        "periods": 6,
        "objectives": [
          "Mô tả được cấu tạo và chức năng của hệ tuần hoàn",
          "Trình bày được vai trò của tim và mạch máu"
        ]
      }
    ]
  },
  "metadata": {
    "sources": ["local_json", "uploaded_file"],
    "processed_at": "2025-01-01T00:00:00Z"
  }
}
```

**AI Model:** Không dùng AI cho bước này (rule-based parsing)
**Thời gian xử lý:** < 10 giây

---

### 2.4 Agent 2: Retriever Agent

**Vai trò:** Tìm kiếm từ knowledge base / RAG

**Trách nhiệm:**
- Tìm kiếm tài liệu liên quan từ knowledge base
- Retrieve context cho question generation
- Ranking kết quả theo relevance

**Input:**
- Normalized curriculum data từ Agent 1
- Query terms (chủ đề, bài học, kiến thức)

**Output:**
```json
{
  "retrieved_context": [
    {
      "content": "Tim người có 4 ngăn...",
      "source": "SGK Trang 45",
      "relevance_score": 0.95
    }
  ],
  "total_results": 10
}
```

**AI Model:** Embedding model (future phase)
**MVP:** Chưa cần RAG phức tạp, dùng local JSON trực tiếp

---

### 2.5 Agent 3: Matrix Generation Agent

**Vai trò:** Tạo ma trận đề kiểm tra

**Input:**
- Normalized curriculum data
- Exam info (grade, subject, exam_type)
- Blueprint (difficulty_ratio, question_types)

**Output:**
```json
{
  "matrix": [
    {
      "topic_id": "topic_1",
      "topic_name": "Chủ đề 1: Hệ tuần hoàn",
      "lesson_id": "lesson_1_1",
      "lesson_name": "Bài 1: Tim và mạch máu",
      "nhan_biet": {
        "count": 1,
        "score": 0.25,
        "question_type": "multiple_choice"
      },
      "thong_hieu": {
        "count": 1,
        "score": 0.5,
        "question_type": "true_false"
      },
      "van_dung": {
        "count": 0,
        "score": 0,
        "question_type": null
      }
    }
  ],
  "summary": {
    "nhan_biet": { "total_count": 5, "total_score": 1.25, "percentage": 30 },
    "thong_hieu": { "total_count": 4, "total_score": 4.0, "percentage": 40 },
    "van_dung": { "total_count": 3, "total_score": 4.75, "percentage": 30 }
  }
}
```

**Constraints:**
- Tổng điểm = 10
- Phân bổ: 30% Nhận biết, 40% Thông hiểu, 30% Vận dụng

**AI Model:** Gemini API
**Temperature:** 0.2 (cần chính xác cao)

---

### 2.6 Agent 4: Specification Generation Agent

**Vai trò:** Tạo bản đặc tả đề kiểm tra

**Input:**
- Matrix từ Agent 3
- Normalized curriculum data

**Output:**
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
      "bloom_level": "remember"
    }
  ]
}
```

**AI Model:** Gemini API
**Temperature:** 0.3

---

### 2.7 Agent 5: Question Generation Agent

**Vai trò:** Sinh câu hỏi theo ma trận, **KHÔNG tự bịa chương trình**

**Nguyên tắc cốt lõi:**
- Chỉ sử dụng dữ liệu đã chuẩn hóa
- Không tự nghĩ chương trình ngoài dữ liệu đã nạp
- Nếu thiếu dữ liệu, trả về "insufficient_context"

**Input:**
- Specification từ Agent 4
- Normalized curriculum data
- Retrieved context từ Agent 2 (nếu có)

**Output:**
```json
{
  "questions": [
    {
      "id": "q_1",
      "type": "multiple_choice",
      "difficulty": "nhan_biet",
      "topic": "Chủ đề 1: Hệ tuần hoàn",
      "lesson": "Bài 1: Tim và mạch máu",
      "knowledge_unit": "Cấu tạo tim",
      "achievement": "Mô tả được cấu tạo tim",
      "content": "Tim người có bao nhiêu ngăn?",
      "options": {
        "A": "2 ngăn",
        "B": "3 ngăn",
        "C": "4 ngăn",
        "D": "5 ngăn"
      },
      "correct_answer": "C",
      "score": 0.25,
      "metadata": {
        "source_type": "local_json",
        "source_name": "curriculum_grade8_khtn.json",
        "confidence_score": 0.95
      }
    }
  ]
}
```

**AI Model:** Gemini API
**Temperature:** 0.7 (cần sáng tạo)

---

### 2.8 Agent 6: Teacher Review Agent

**Vai trò:** Xử lý duyệt câu hỏi từ giáo viên

**Trạng thái câu hỏi:**
- `accepted`: Câu đạt, giữ nguyên
- `needs_revision`: Câu chưa đạt, cần sửa
- `rejected`: Câu không đạt, loại bỏ

**Input:**
- Questions từ Agent 5
- Teacher feedback (review status, comments)

**Output:**
```json
{
  "review_result": {
    "accepted": ["q_1", "q_3", "q_4"],
    "needs_revision": ["q_2", "q_9"],
    "rejected": ["q_15"],
    "feedback": {
      "q_2": "Phương án nhiễu không hợp lý",
      "q_9": "Quá dễ, cần khó hơn",
      "q_15": "Câu hỏi quá dài"
    }
  }
}
```

**AI Model:** Không dùng AI (rule-based)
**Thời gian xử lý:** < 1 giây

---

### 2.9 Agent 7: Answer & Rubric Agent

**Vai trò:** Sinh đáp án & rubric cho câu hỏi đã duyệt

**Nguyên tắc:**
- Chỉ sinh đáp án/rubric sau khi câu hỏi đã được duyệt
- Câu đã duyệt trước đó giữ nguyên đáp án

**Input:**
- Accepted questions từ Agent 6
- Specification

**Output:**
```json
{
  "answer_key": [
    {
      "question_id": "q_1",
      "correct_answer": "C",
      "explanation": "Tim người có 4 ngăn: 2 tâm nhĩ và 2 tâm thất."
    }
  ],
  "rubric": [
    {
      "question_id": "q_15",
      "total_score": 2.0,
      "criteria": [
        {
          "name": "Nội dung",
          "max_score": 1.5,
          "levels": [
            {"score": 1.5, "description": "Đủ 7 key points, chính xác"},
            {"score": 1.0, "description": "Đủ 5-6 key points"},
            {"score": 0.5, "description": "Đủ 3-4 key points"},
            {"score": 0, "description": "Dưới 3 key points"}
          ]
        }
      ]
    }
  ]
}
```

**AI Model:** Gemini API
**Temperature:** 0.3

---

### 2.10 Agent 8: Validation Agent

**Vai trò:** Kiểm tra logic, format, điểm số, đáp án, rubric

**Các loại validation:**

| Loại | Kiểm tra |
|------|----------|
| Format validation | Tổng điểm = 10, số câu, format |
| Content validation | Nội dung, trùng lặp |
| Matrix validation | Mapping với ma trận |
| Rubric validation | Đáp án, rubric đầy đủ |

**Checks:**

#### Format Checks:
1. Tổng điểm = 10
2. Phân bổ mức độ đúng tỷ lệ
3. Số câu hỏi đúng yêu cầu
4. Format câu hỏi đúng chuẩn

#### Content Checks:
1. Không trùng câu hỏi
2. Nội dung chính xác
3. Mỗi câu map về topic/objective/mức độ
4. Không câu nào thiếu đáp án
5. Không câu tự luận nào thiếu rubric

#### Matrix Checks:
1. Mapping đúng với bản đặc tả
2. Phân bổ đều theo các bài đã dạy

#### Rubric Checks:
1. Rubric có tiêu chí rõ ràng
2. Thang điểm đầy đủ

**Output:**
```json
{
  "validation_result": {
    "passed": true,
    "score": 95,
    "checks": [
      {
        "name": "total_score",
        "status": "pass",
        "expected": 10,
        "actual": 10
      },
      {
        "name": "difficulty_ratio",
        "status": "pass",
        "expected": { "nhan_biet": 30, "thong_hieu": 40, "van_dung": 30 },
        "actual": { "nhan_biet": 30, "thong_hieu": 40, "van_dung": 30 }
      },
      {
        "name": "no_missing_answers",
        "status": "pass",
        "message": "Tất cả câu hỏi đều có đáp án"
      },
      {
        "name": "no_missing_rubric",
        "status": "pass",
        "message": "Tất cả câu tự luận đều có rubric"
      },
      {
        "name": "no_duplicates",
        "status": "pass",
        "message": "Không có câu hỏi trùng lặp"
      }
    ],
    "warnings": [],
    "errors": []
  }
}
```

**AI Model:** Rule-based + Gemini API cho quality check
**Temperature:** 0.1

---

### 2.11 Agent 9: Export Agent

**Vai trò:** Xuất file Word/PDF

**Input:**
- Full data từ các agents

**Output:**
- 5 file Word:
  1. Ma trận đề kiểm tra.docx
  2. Bản đặc tả đề kiểm tra.docx
  3. Đề kiểm tra.docx
  4. Đáp án.docx
  5. Rubric.docx

**Technology:** python-docx

---

## 3. Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            DATA FLOW                                    │
│                    (Flow mới: Nạp dữ liệu + RAG)                        │
└─────────────────────────────────────────────────────────────────────────┘

User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent 0: Data Ingestion                                                │
│  - Local JSON curriculum                                                │
│  - Teacher uploads (PDF/DOCX/XLSX)                                      │
│  - Question bank                                                        │
│  - RAG retrieval (future)                                               │
└─────────────────────────────────────────────────────────────────────────┘
    │
    │ raw_data
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent 1: Document Processing                                           │
│  - Parse JSON                                                           │
│  - Extract text                                                         │
│  - Normalize to schema                                                  │
└─────────────────────────────────────────────────────────────────────────┘
    │
    │ normalized_data
    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  Agent 2: Retriever (optional)                                          │
│  - Search knowledge base                                                │
│  - Retrieve relevant context                                            │
└─────────────────────────────────────────────────────────────────────────┘
    │
    │ retrieved_context
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Agent 3    │────▶│  Agent 4    │────▶│  Agent 5    │
│  Matrix     │     │  Spec       │     │  Question   │
│  Generation │     │  Generation │     │  Generation │
└─────────────┘     └─────────────┘     └─────────────┘
    │                    │                    │
    │   matrix[]         │   specification[]  │   questions[]
    │                    │                    │
    └────────────────────┴────────────────────┘
                         │
                         ▼
              ┌─────────────────┐
              │    Agent 6      │
              │  Teacher Review │
              └────────┬────────┘
                       │
                       │ reviewed_questions
                       ▼
              ┌─────────────────┐
              │    Agent 7      │
              │  Answer & Rubric│
              └────────┬────────┘
                       │
                       │ answers[], rubric[]
                       ▼
              ┌─────────────────┐
              │    Agent 8      │
              │   Validation    │
              └────────┬────────┘
                       │
                       │ validation_report
                       ▼
              ┌─────────────────┐
              │    Agent 9      │
              │     Export      │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   Word/PDF      │
              │   Files         │
              └─────────────────┘
```

---

## 4. State Management

### 4.1 State Schema

```json
{
  "session_id": "uuid",
  "current_step": 0,
  "status": "in_progress",
  "data": {
    "data_sources": [],
    "normalized_data": {},
    "exam_info": {},
    "blueprint": {},
    "matrix": {},
    "specification": {},
    "questions": [],
    "question_reviews": {},
    "answer_key": [],
    "rubric": [],
    "validation": {}
  },
  "history": [
    {
      "step": 0,
      "action": "data_ingestion",
      "timestamp": "2025-01-01T00:00:00Z",
      "data": {}
    }
  ],
  "errors": []
}
```

### 4.2 State Transitions

```
INIT ──▶ DATA_INGESTION ──▶ NORMALIZE ──▶ RETRIEVE ──▶ MATRIX ──▶ SPEC ──▶ QUESTIONS ──▶ REVIEW ──▶ ANSWERS ──▶ VALIDATE ──▶ EXPORT
  │              │                │            │          │         │          │            │          │            │            │
  │              │                │            │          │         │          │            │          │            │            │
  └──────────────┴────────────────┴────────────┴──────────┴─────────┴──────────┴────────────┴──────────┴────────────┴────────────┘
                                    (Error states can transition back)
```

---

## 5. Error Handling

### 5.1 Retry Strategy

```python
MAX_RETRIES = 3
RETRY_DELAY = 1000  # ms

async function callAgent(agent, input, retry=0):
    try:
        return await agent.process(input)
    except Exception as e:
        if retry < MAX_RETRIES:
            await delay(RETRY_DELAY * (retry + 1))
            return callAgent(agent, input, retry + 1)
        else:
            raise AgentError(agent.name, e)
```

### 5.2 Fallback Strategy

| Agent | Fallback |
|-------|----------|
| Data Ingestion | Chuyển sang nhập thủ công |
| Document Processing | Yêu cầu user nhập lại |
| Retriever | Skip (dùng local JSON trực tiếp) |
| Matrix Generation | Template mặc định |
| Specification Generation | Template mặc định |
| Question Generation | Question bank |
| Teacher Review | Manual review |
| Answer & Rubric | Template mặc định |
| Validation | Skip với warning |
| Export | Error message |

---

## 6. Luồng RAG đề xuất (Future Phase)

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

## 7. Security Considerations

### 7.1 API Key Management
- Store API keys in environment variables
- Never expose in frontend
- Rotate keys periodically

### 7.2 Data Privacy
- No student data stored
- Exam data encrypted at rest
- Session data auto-expire

### 7.3 Rate Limiting
- Max 10 requests/minute per user
- Max 100 requests/hour per IP

---

## 8. Monitoring & Logging

### 8.1 Metrics to Track

| Metric | Description |
|--------|-------------|
| Agent latency | Time per agent |
| Error rate | % of failed requests |
| Validation pass rate | % passing validation |
| Token usage | AI API costs |
| Data source usage | Which sources are used most |

### 8.2 Logging Schema

```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "session_id": "uuid",
  "agent": "data_ingestion",
  "action": "collect",
  "source_type": "local_json",
  "source_name": "curriculum_grade8_khtn.json",
  "latency_ms": 1500,
  "status": "success"
}
```
