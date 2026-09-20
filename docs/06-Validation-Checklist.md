# Validation Checklist
# Deka

## 1. Tổng quan

Tài liệu này định nghĩa tất cả các kiểm tra (validation checks) cần thực hiện trước khi export đề kiểm tra. Mỗi check có tiêu chí pass/fail rõ ràng.

**Flow mới:** Validation được tách rõ thành 4 loại:
1. **Format validation** - Kiểm tra format, tổng điểm, số câu
2. **Content validation** - Kiểm tra nội dung, trùng lặp
3. **Matrix validation** - Kiểm tra mapping với ma trận
4. **Rubric validation** - Kiểm tra đáp án, rubric đầy đủ

---

## 2. Format Validation Checks

### 2.1 Tổng điểm

| Check ID | CHECK_TOTAL_SCORE |
|----------|-------------------|
| Category | format |
| Severity | critical |
| Description | Tổng điểm của toàn bộ đề phải bằng 10 |
| Expected | 10 |
| Actual | Sum of all question scores |
| Pass condition | actual == expected |
| Fail message | "Tổng điểm phải bằng 10, hiện tại là {actual}" |
| Fix suggestion | "Kiểm tra lại điểm từng câu hỏi" |

**Code:**
```python
def check_total_score(questions):
    total = sum(q['score'] for q in questions)
    return {
        'passed': total == 10,
        'expected': 10,
        'actual': total,
        'message': f'Tổng điểm: {total}/10'
    }
```

---

### 2.2 Phân bổ mức độ nhận thức

| Check ID | CHECK_DIFFICULTY_RATIO |
|----------|------------------------|
| Category | format |
| Severity | critical |
| Description | Phân bổ điểm theo 3 mức độ phải đúng tỷ lệ |
| Expected | {nhan_biet}%, {thong_hieu}%, {van_dung}% |
| Actual | Calculated from questions |
| Pass condition | |expected - actual| <= 2% |
| Fail message | "Phân bổ mức độ không đúng tỷ lệ" |
| Fix suggestion | "Điều chỉnh số câu hoặc điểm từng mức độ" |

**Code:**
```python
def check_difficulty_ratio(questions, blueprint):
    scores = {'nhan_biet': 0, 'thong_hieu': 0, 'van_dung': 0}
    for q in questions:
        scores[q['difficulty']] += q['score']
    
    total = sum(scores.values())
    actual = {k: round(v/total*100) for k, v in scores.items()}
    
    passed = all(
        abs(actual[k] - blueprint['difficulty_ratio'][k]) <= 2
        for k in actual
    )
    
    return {
        'passed': passed,
        'expected': blueprint['difficulty_ratio'],
        'actual': actual
    }
```

---

### 2.3 Số lượng câu hỏi

| Check ID | CHECK_QUESTION_COUNT |
|----------|----------------------|
| Category | format |
| Severity | major |
| Description | Số câu hỏi phải khớp với bản đặc tả |
| Expected | blueprint['total_questions'] |
| Actual | len(questions) |
| Pass condition | actual == expected |
| Fail message | "Số câu hỏi không khớp" |

---

### 2.4 Điểm từng dạng câu hỏi

| Check ID | CHECK_QUESTION_TYPE_SCORES |
|----------|---------------------------|
| Category | format |
| Severity | major |
| Description | Điểm từng dạng câu hỏi phải đúng quy định |
| Expected | {multiple_choice: 0.25, true_false: 0.5, ...} |
| Actual | Calculated from questions |

**Score rules:**
| Type | Score per question |
|------|-------------------|
| multiple_choice | 0.25 |
| true_false | 0.5 (4 statements) |
| short_answer | 0.5 |
| essay | 1.0 - 2.0 |

---

### 2.5 Mapping với bản đặc tả

| Check ID | CHECK_SPECIFICATION_MAPPING |
|----------|----------------------------|
| Category | format |
| Severity | critical |
| Description | Mỗi câu hỏi phải mapping đúng với bản đặc tả |
| Expected | specification data |
| Actual | questions metadata |
| Pass condition | All fields match |

**Fields to check:**
- topic
- lesson
- knowledge_unit
- achievement
- difficulty
- question_type
- score

---

## 3. Content Validation Checks

### 3.1 Không trùng câu hỏi

| Check ID | CHECK_NO_DUPLICATES |
|----------|---------------------|
| Category | content |
| Severity | major |
| Description | Không được có câu hỏi trùng lặp |
| Pass condition | No duplicate content found |
| Fail message | "Phát hiện câu hỏi trùng lặp: {question_ids}" |

**Code:**
```python
def check_no_duplicates(questions):
    seen = set()
    duplicates = []
    
    for q in questions:
        content = q['content'].strip().lower()
        if content in seen:
            duplicates.append(q['id'])
        seen.add(content)
    
    return {
        'passed': len(duplicates) == 0,
        'duplicates': duplicates
    }
```

---

### 3.2 Đáp án đầy đủ

| Check ID | CHECK_ANSWER_KEY_COMPLETE |
|----------|--------------------------|
| Category | content |
| Severity | critical |
| Description | Phải có đáp án cho tất cả câu hỏi |
| Expected | len(questions) |
| Actual | len(answer_key) |
| Pass condition | actual >= expected |

---

### 3.3 Nội dung phù hợp khối lớp

| Check ID | CHECK_GRADE_APPROPRIATE |
|----------|------------------------|
| Category | content |
| Severity | major |
| Description | Nội dung phải phù hợp với khối lớp |
| Check | Language complexity, concept difficulty |
| Pass condition | AI quality check passes |

---

### 3.4 Thuật ngữ khoa học chính xác

| Check ID | CHECK_SCIENTIFIC_TERMS |
|----------|------------------------|
| Category | content |
| Severity | major |
| Description | Thuật ngữ khoa học phải chính xác |
| Check | Terminology validation |
| Pass condition | All terms are correct |

---

### 3.5 Không dùng kiến thức ngoài context (MỚI)

| Check ID | CHECK_NO_HALLUCINATION |
|----------|------------------------|
| Category | content |
| Severity | critical |
| Description | Không được dùng kiến thức ngoài dữ liệu đã nạp |
| Check | Verify all content traces back to source |
| Pass condition | All content has valid source |

---

## 4. Matrix Validation Checks

### 4.1 Mapping với ma trận

| Check ID | CHECK_MATRIX_MAPPING |
|----------|---------------------|
| Category | matrix |
| Severity | critical |
| Description | Mỗi câu hỏi phải map về một topic/objective/mức độ |
| Check | Verify mapping consistency |
| Pass condition | All questions have valid mapping |

---

### 4.2 Phân bổ đều theo bài

| Check ID | CHECK_EVEN_DISTRIBUTION |
|----------|------------------------|
| Category | matrix |
| Severity | major |
| Description | Câu hỏi phải phân bổ đều theo các bài đã dạy |
| Check | Verify distribution matches periods |
| Pass condition | Distribution is reasonable |

---

## 5. Rubric Validation Checks

### 5.1 Rubric đầy đủ cho câu tự luận

| Check ID | CHECK_RUBRIC_COMPLETE |
|----------|----------------------|
| Category | rubric |
| Severity | critical |
| Description | Câu tự luận phải có rubric chấm điểm |
| Expected | All essay questions have rubric |
| Actual | Check rubric coverage |
| Pass condition | 100% essay questions covered |

---

### 5.2 Rubric chấm điểm rõ ràng

| Check ID | CHECK_RUBRIC_CLARITY |
|----------|---------------------|
| Category | rubric |
| Severity | major |
| Description | Rubric phải có tiêu chí rõ ràng |
| Check | Criteria are specific and measurable |
| Pass condition | All levels are distinct |

---

## 6. Quality Validation Checks

### 6.1 Đúng mức độ nhận thức

| Check ID | CHECK_DIFFICULTY_LEVEL |
|----------|------------------------|
| Category | quality |
| Severity | major |
| Description | Câu hỏi phải đúng mức độ nhận thức đã chỉ định |
| Check | AI-based difficulty assessment |
| Pass condition | AI confirms difficulty matches |

**Difficulty guidelines:**

| Level | Characteristics |
|-------|-----------------|
| Nhận biết | Nhớ lại sự kiện, khái niệm cơ bản |
| Thông hiểu | Giải thích, so sánh, phân loại |
| Vận dụng | Áp dụng vào tình huống mới |

---

### 6.2 Phương án nhiễu hợp lý (MC)

| Check ID | CHECK_MC_DISTRACTORS |
|----------|---------------------|
| Category | quality |
| Severity | medium |
| Description | Phương án sai phải hợp lý, dễ nhầm |
| Check | Distractors are plausible |
| Pass condition | All distractors are reasonable |

**Rules:**
- Không có "Tất cả các ý trên"
- Không có "Không có ý nào đúng"
- Các phương án cùng độ dài
- Phương án sai phải có lý do sai

---

### 6.3 Phát biểu rõ ràng (TF)

| Check ID | CHECK_TF_CLARITY |
|----------|------------------|
| Category | quality |
| Severity | medium |
| Description | Phát biểu phải rõ ràng, không mơ hồ |
| Check | No ambiguous statements |
| Pass condition | All statements are clear |

**Rules:**
- Không dùng phủ định kép
- Không dùng từ mơ hồ ("có thể", "thường")
- Mỗi phát biểu chỉ nói một vấn đề

---

## 7. Validation Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      VALIDATION FLOW                                    │
│                      (Flow mới: 4 loại validation)                       │
└─────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   START     │
                              └──────┬──────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │  Format Validation    │
                         │  (Checks 2.1 - 2.5)   │
                         └───────────┬───────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                    ┌──────────┐          ┌──────────┐
                    │   PASS   │          │   FAIL   │
                    └────┬─────┘          └────┬─────┘
                         │                     │
                         ▼                     ▼
                         │              ┌──────────────┐
                         │              │ Return errors│
                         │              │ & stop       │
                         │              └──────────────┘
                         │
                         ▼
                         ┌───────────────────────┐
                         │  Content Validation   │
                         │  (Checks 3.1 - 3.5)   │
                         └───────────┬───────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                    ┌──────────┐          ┌──────────┐
                    │   PASS   │          │   WARN   │
                    └────┬─────┘          └────┬─────┘
                         │                     │
                         ▼                     ▼
                         │              ┌──────────────┐
                         │              │ Return warns │
                         │              │ & continue   │
                         │              └──────────────┘
                         │
                         ▼
                         ┌───────────────────────┐
                         │  Matrix Validation    │
                         │  (Checks 4.1 - 4.2)   │
                         └───────────┬───────────┘
                                     │
                          ┌──────────┴──────────┐
                          ▼                     ▼
                    ┌──────────┐          ┌──────────┐
                    │   PASS   │          │   FAIL   │
                    └────┬─────┘          └────┬─────┘
                         │                     │
                         ▼                     ▼
                         │              ┌──────────────┐
                         │              │ Return errors│
                         │              └──────────────┘
                         │
                         ▼
                         ┌───────────────────────┐
                         │  Rubric Validation    │
                         │  (Checks 5.1 - 5.2)   │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │  Quality Validation   │
                         │  (Checks 6.1 - 6.3)   │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │  Generate Report      │
                         └───────────┬───────────┘
                                     │
                                     ▼
                         ┌───────────────────────┐
                         │        END            │
                         └───────────────────────┘
```

---

## 8. Validation Report Template

```json
{
  "validation_report": {
    "timestamp": "2025-01-01T00:00:00Z",
    "exam_id": "exam_123",
    "overall_status": "pass|warn|fail",
    "score": 95,
    "summary": {
      "total_checks": 15,
      "passed": 13,
      "warnings": 2,
      "failed": 0
    },
    "details": {
      "format": {
        "status": "pass",
        "checks": [...]
      },
      "content": {
        "status": "warn",
        "checks": [...]
      },
      "matrix": {
        "status": "pass",
        "checks": [...]
      },
      "rubric": {
        "status": "pass",
        "checks": [...]
      },
      "quality": {
        "status": "pass",
        "checks": [...]
      }
    },
    "action_required": [
      {
        "priority": "high",
        "check_id": "CHECK_TOTAL_SCORE",
        "message": "Tổng điểm phải bằng 10",
        "fix": "Điều chỉnh điểm câu 15 từ 1.5 thành 2.0"
      }
    ]
  }
}
```

---

## 9. Severity Levels

| Level | Description | Action |
|-------|-------------|--------|
| critical | Lỗi nghiêm trọng, không thể export | Phải sửa trước khi tiếp tục |
| major | Lỗi lớn, ảnh hưởng chất lượng | Nên sửa, có thể export với warning |
| medium | Lỗi trung bình | Cảnh báo, có thể bỏ qua |
| low | Lỗi nhỏ | Thông tin, không cần sửa |

---

## 10. Validation Rules Configuration

```json
{
  "validation_config": {
    "total_score": {
      "value": 10,
      "tolerance": 0
    },
    "difficulty_ratio": {
      "nhan_biet": {"target": 30, "tolerance": 2},
      "thong_hieu": {"target": 40, "tolerance": 2},
      "van_dung": {"target": 30, "tolerance": 2}
    },
    "question_scores": {
      "multiple_choice": {"min": 0.25, "max": 0.25},
      "true_false": {"min": 0.5, "max": 0.5},
      "short_answer": {"min": 0.5, "max": 0.5},
      "essay": {"min": 1.0, "max": 2.0}
    },
    "min_questions": 10,
    "max_questions": 20,
    "required_fields": [
      "topic",
      "lesson", 
      "knowledge_unit",
      "achievement",
      "difficulty",
      "question_type",
      "score"
    ],
    "no_hallucination": {
      "enabled": true,
      "check_source": true
    }
  }
}
```
