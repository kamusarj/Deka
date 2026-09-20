# Brainstorm: Kiểm tra Câu hỏi KHTN do AI sinh ra
# Deka

## 1. Bài toán cốt lõi

KHTN (Vật lý, Hóa học, Sinh học) là môn **logic cứng** — có đáp án đúng/sai rõ ràng, không mơ hồ như Văn hay Sử. Nếu AI sinh câu hỏi sai kiến thức → **nghiêm trọng hơn nhiều** so với sai format.

### 1.1 Tình trạng hiện tại

| Đã có | Chưa có |
|-------|---------|
| ✅ Format validation (điểm, số câu, trùng lặp) | ❌ Kiểm tra kiến thức khoa học có đúng không |
| ✅ Source tracking (local_json, uploaded_file) | ❌ Kiểm tra đáp án có thực sự đúng không |
| ✅ Teacher review (accepted/needs_revision) | ❌ Kiểm tra distractors có hợp lý không |
| ❌ | ❌ Kiểm tra câu hỏi có phù hợp mức độ nhận thức không |
| ❌ | ❌ Kiểm tra phát biểu Đ/S có mơ hồ không |

### 1.2 Các file liên quan hiện tại

| File | Vai trò |
|------|---------|
| `backend/app/agents/validator_agent.py` | Rule-based validation (format, score, duplicates, sources) |
| `backend/app/agents/question_agent.py` | Sinh câu hỏi (deterministic + Gemini) |
| `backend/app/agents/answer_agent.py` | Sinh đáp án & rubric |
| `backend/app/services/gemini_service.py` | Gemini API wrapper (generate_text, generate_json) |
| `docs/06-Validation-Checklist.md` | Định nghĩa validation checks (chưa implement hết) |
| `docs/05-Prompt-Design.md` | Prompt templates cho các agent |

---

## 2. Các Chiến lược Kiểm tra

### 2.1 Chiến lược 1: "Solve & Compare" — Gemini tự giải lại

**Nguyên lý:** Không hỏi "câu này đúng không?" mà bắt AI **tự giải bài** từ đầu.

```
┌─────────────────────────────────────────────────────┐
│  QuestionAgent sinh câu hỏi + đáp án                │
│         ↓                                           │
│  VerificationAgent:                                  │
│    - Đọc câu hỏi (KHÔNG cho xem đáp án)             │
│    - Tự suy luận, chọn đáp án                       │
│    - So sánh đáp án tự giải vs đáp án gốc           │
│    - Nếu KHÁC → flag "confidence_low"               │
│    - Nếu GIỐNG → flag "confidence_high"             │
└─────────────────────────────────────────────────────┘
```

**Chi tiết cho từng dạng câu:**

| Dạng câu | Verification approach |
|----------|----------------------|
| **MCQ** | Gemini đọc câu + 4 options → chọn đáp án → so với `correct_answer` |
| **Đúng/Sai** | Gemini đọc từng phát biểu → đánh giá T/F riêng → so với `is_true` |
| **Trả lời ngắn** | Gemini đọc câu hỏi → tự trả lời → so với `correct_answer` |
| **Tự luận** | Gemini đọc câu hỏi + rubric → tự giải → so với `key_points` |

**Prompt mẫu:**

```
Bạn là giáo viên KHTN lớp 8. Hãy đọc câu hỏi sau và tự trả lời
(trả lời bằng cách suy luận khoa học, KHÔNG nhìn đáp án).

Câu hỏi: {question.content}
{question.options hoặc question.statements}

Trả về JSON:
{
  "your_answer": "A" | [{statement_id, your_true_false}],
  "reasoning": "Giải thích bước suy luận",
  "confidence": 0.0-1.0,
  "detected_issues": ["nếu phát hiện vấn đề gì"]
}
```

**Ưu điểm:** Bắt được đáp án sai (lỗi nghiêm trọng nhất)
**Nhược điểm:** Tốn 1 API call/câu (20 câu = 20 calls thêm)

---

### 2.2 Chiến lược 2: "Cross-Model Adversarial" — Model khác phản biện

**Nguyên lý:** Dùng **model khác** (hoặc cùng model nhưng role khác) để adversarial review.

```
Gemini 2.0 Flash  ──sinh câu──→  Câu hỏi
                                       ↓
Gemini 2.5 Pro    ──phản biện──→  Review Report
                                       ↓
                              ┌────────┴────────┐
                              ↓                 ↓
                         Đồng thuận        Bất đồng
                         (✅ Tin cậy)      (⚠️ Giáo viên xem kỹ)
```

**Tại sao dùng 2 model khác nhau:**

- Gemini 2.0 Flash: nhanh, rẻ, dùng để sinh câu hỏi
- Gemini 2.5 Pro: reasoning mạnh hơn, dùng để verify
- Nếu cùng 1 model sinh + verify → có thể mắc **cùng 1 lỗi systematic** (model bias)
- 2 model khác nhau → ít khả năng cùng sai 1 chỗ

**Prompt cho Gemini 2.5 Pro:**

```
Bạn là chuyên gia KHTN, nhiệm vụ: PHẢN BIỆN câu hỏi kiểm tra.
Hãy tìm mọi lý do câu hỏi này có thể SAI hoặc KÉM CHẤT LƯỢNG.

Câu hỏi: {question}
Đáp án được chọn: {correct_answer}
Kiến thức tham chiếu: {curriculum_context}

Kiểm tra:
1. Đáp án đúng có THỰC SỰ đúng về mặt khoa học không?
2. Có đáp án nào cũng đúng không (trường hợp nhiều đáp án đúng)?
3. Phát biểu Đ/S có mơ hồ, dùng phủ định kép không?
4. Distractors có hợp lý hay quá dễ loại?
5. Câu hỏi có phù hợp mức độ {difficulty} không?

Trả về JSON:
{
  "is_valid": true/false,
  "issues_found": [
    {"severity": "critical|major|medium", "description": "...", "suggestion": "..."}
  ],
  "correct_answer_verification": "confirmed|disputed|uncertain",
  "difficulty_assessment": "nhan_biet|thong_hieu|van_dung",
  "difficulty_matches": true/false
}
```

---

### 2.3 Chiến lược 3: "Curriculum Grounding Check" — Đối chiếu với nguồn

**Nguyên lý:** Mọi câu hỏi phải **trace về curriculum JSON gốc**. Không có trong curriculum = có thể hallucination.

```
Câu hỏi: "Tim người có bao nhiêu ngăn?"
         ↓
Search curriculum JSON:
  - topic: "Hệ tuần hoàn"
  - knowledge_unit: "Cấu tạo tim"
  - learning_objective: "Mô tả được cấu tạo tim"
  - facts: ["Tim có 4 ngăn", "2 tâm nhĩ", "2 tâm thất"]
         ↓
So sánh: Câu hỏi có khớp facts không?
  → Nếu khớp → ✅ Grounded
  → Nếu không khớp → ⚠️ Có thể hallucination
```

**Implementation approach:**

```python
class CurriculumGroundingCheck:
    """Kiểm tra câu hỏi có grounded trong curriculum không."""

    async def verify(self, question, curriculum_data):
        # 1. Tìm topic/lesson trong curriculum khớp với question.metadata
        matching_topics = self._find_matching_topics(
            question["metadata"]["topic"],
            curriculum_data
        )

        # 2. Tìm learning_objective khớp
        matching_objectives = self._find_matching_objectives(
            question["metadata"]["achievement"],
            matching_topics
        )

        # 3. Dùng Gemini verify: câu hỏi có nằm trong scope kiến thức không?
        grounding_score = await self._gemini_grounding_check(
            question, matching_objectives
        )

        return {
            "grounded": grounding_score > 0.7,
            "grounding_score": grounding_score,
            "matched_topics": matching_topics,
            "matched_objectives": matching_objectives
        }
```

**Lưu ý:** Cần RAG pipeline (ChromaDB) để hoạt động tốt → Phase 2.

---

### 2.4 Chiến lược 4: "Distractor Quality Analysis" — Phân tích phương án nhiễu

**Nguyên lý:** Câu MCQ tốt phải có distractors **hợp lý nhưng sai** — không quá hiển nhiên sai.

```
Câu hỏi: "Tim người có bao nhiêu ngăn?"

Phân tích từng option:
  A: "2 ngăn"  → Quá dễ loại (ai cũng biết tim > 2 ngăn) → ⚠️ distractor kém
  B: "3 ngăn"  → Hợp lý (nhầm với tim ếch) → ✅ distractor tốt
  C: "4 ngăn"  → Đáp án đúng → ✅
  D: "5 ngăn"  → Quá hiển nhiên sai → ⚠️ distractor kém
```

**Gemini prompt cho distractor analysis:**

```
Phân tích chất lượng phương án nhiễu của câu MCQ sau:

Câu hỏi: {content}
Options: {options}
Đáp án đúng: {correct_answer}

Với mỗi phương án sai, đánh giá:
1. Có phải lỗi thường gặp của học sinh không? (misconception-based)
2. Có quá dễ loại không? (too obviously wrong)
3. Có thể nhầm với kiến thức liên quan không? (plausible confusion)

Trả về JSON:
{
  "distractors": [
    {"option": "A", "plausibility": 0.8, "reason": "Học sinh hay nhầm với..."},
    {"option": "B", "plausibility": 0.3, "reason": "Quá dễ loại vì..."}
  ],
  "overall_distractor_quality": "good|acceptable|poor",
  "suggestion": "Nếu poor, gợi ý cải thiện"
}
```

**Quy tắc distractor (từ docs/06-Validation-Checklist.md):**

- Không có "Tất cả các ý trên"
- Không có "Không có ý nào đúng"
- Các phương án cùng độ dài
- Phương án sai phải có lý do sai (misconception-based)

---

### 2.5 Chiến lược 5: "Statement Ambiguity Detector" — Phát hiện câu Đ/S mơ hồ

**Nguyên lý:** Câu Đ/S thường bị AI sinh ra với phát biểu mơ hồ, dùng phủ định kép, hoặc quá chung chung.

```
❌ Câu mơ hồ: "Sinh vật thường có tế bào."
   → "thường" là bao nhiêu? 51%? 99%? → AMBIGUOUS

❌ Câu phủ định kép: "Không phải tất cả sinh vật đều không có tế bào nhân sơ."
   → Rất khó hiểu → AMBIGUOUS

✅ Câu rõ ràng: "Tất cả sinh vật đều được cấu tạo từ tế bào."
   → Rõ ràng, đúng/sai xác định được → CLEAR
```

**Gemini prompt:**

```
Kiểm tra tính rõ ràng của các phát biểu Đ/S sau:
{statements}

Với mỗi phát biểu, kiểm tra:
1. Có dùng từ mơ hồ không? (thường, có thể, hầu hết, nhiều khi...)
2. Có phủ định kép không?
3. Có thể hiểu theo nhiều cách không?
4. Phát biểu có đúng/sai xác định được không?

Trả về JSON:
{
  "statements": [
    {
      "id": "s_1_1",
      "is_clear": true/false,
      "ambiguity_type": "vague_term|double_negative|multiple_interpretations|none",
      "suggestion": "Cách viết lại cho rõ ràng"
    }
  ]
}
```

**Quy tắc từ docs/06-Validation-Checklist.md:**

- Không dùng phủ định kép
- Không dùng từ mơ hồ ("có thể", "thường")
- Mỗi phát biểu chỉ nói một vấn đề

---

### 2.6 Chiến lược 6: "Difficulty Calibration" — Kiểm tra mức độ nhận thức

**Nguyên lý:** Câu đánh dấu "nhan_biet" nhưng nội dung thực tế là "van_dung" → cần flag.

```
Câu hỏi: "Một vật có khối lượng 5kg, chịu lực 10N. Tính gia tốc vật."
Đánh dấu: nhan_biet (Nhận biết)
Thực tế: van_dung (Vận dụng - phải áp dụng F=ma)

→ ⚠️ MISMATCH: Câu này phải là "van_dung" hoặc "thong_hieu"
```

**Gemini prompt:**

```
Đánh giá mức độ nhận thức thực tế của câu hỏi KHTN sau:

Câu hỏi: {content}
Mức độ được gán: {difficulty} (nhan_biet/thong_hieu/van_dung)
Yêu cầu cần đạt: {achievement}

Phân loại theo Bloom:
- Nhận biết (Remember): Nhớ lại sự kiện, khái niệm cơ bản
- Thông hiểu (Understand): Giải thích, so sánh, phân loại
- Vận dụng (Apply): Áp dụng vào tình huống mới, tính toán

Trả về JSON:
{
  "assessed_difficulty": "nhan_biet|thong_hieu|van_dung",
  "matches_assigned": true/false,
  "reasoning": "Giải thích tại sao đánh giá mức độ này",
  "bloom_level": "remember|understand|apply|analyze"
}
```

---

### 2.7 Chiến lược 7: "Batch Self-Consistency Check" — Kiểm tra tính nhất quán

**Nguyên lý:** Sinh cùng 1 câu hỏi **NHIỀU LẦN** (với temperature khác nhau), kiểm tra đáp án có ổn định không.

```
Câu hỏi: "Phản ứng nào sau đây là phản ứng oxi-hoá khử?"

Lần 1 (temp=0.2): Đáp án → A (confidence: 0.95)
Lần 2 (temp=0.5): Đáp án → A (confidence: 0.88)
Lần 3 (temp=0.7): Đáp án → A (confidence: 0.72)

→ 3/3 lần đều chọn A → ✅ Đáp án ổn định, tin cậy cao
```

Nếu:

```
Lần 1: Đáp án → A (0.6)
Lần 2: Đáp án → B (0.5)
Lần 3: Đáp án → A (0.4)

→ 2/3 chọn A nhưng confidence thấp → ⚠️ Câu hỏi có vấn đề
```

**Ưu điểm:** Rất mạnh cho câu hỏi logic
**Nhược điểm:** Tốn nhiều API calls (3x chi phí)

---

## 3. Kiến trúc tổng hợp đề xuất

```
┌─────────────────────────────────────────────────────────────────────┐
│                    QUESTION VERIFICATION PIPELINE                    │
│                    (VerificationAgent - Agent mới)                    │
└─────────────────────────────────────────────────────────────────────┘

QuestionAgent sinh câu hỏi
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 1: RULE-BASED (ĐÃ CÓ - nhanh, miễn phí)               │
│  ├── CHECK_TOTAL_SCORE          ✅                              │
│  ├── CHECK_QUESTION_COUNT       ✅                              │
│  ├── CHECK_DIFFICULTY_RATIO     ✅                              │
│  ├── CHECK_ANSWER_KEY_COMPLETE  ✅                              │
│  ├── CHECK_RUBRIC_COMPLETE      ✅                              │
│  ├── CHECK_NO_DUPLICATES        ✅                              │
│  └── CHECK_NO_HALLUCINATION     ✅                              │
└───────────────────────────────┬───────────────────────────────┘
                                │ PASS
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 2: SOLVE & COMPARE (MỚI - 1 API call/câu)              │
│  ├── Gemini đọc câu hỏi → tự giải → so đáp án                │
│  ├── Nếu mismatch → flag "answer_uncertain"                   │
│  └── Confidence score: 0.0 - 1.0                              │
└───────────────────────────────┬───────────────────────────────┘
                                │ MATCH
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 3: CROSS-MODEL REVIEW (MỚI - Gemini 2.5 Pro)           │
│  ├── Adversarial review: tìm lý do câu hỏi SAI               │
│  ├── Kiểm tra distractor quality (MCQ)                        │
│  ├── Kiểm tra statement ambiguity (Đ/S)                       │
│  └── Kiểm tra difficulty calibration                          │
└───────────────────────────────┬───────────────────────────────┘
                                │ PASS
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 4: CURRICULUM GROUNDING (MỚI - khi có RAG)             │
│  ├── So câu hỏi với curriculum facts                         │
│  ├── Kiểm tra achievement mapping                             │
│  └── Confidence: grounded vs possibly_hallucinated            │
└───────────────────────────────┬───────────────────────────────┘
                                │ PASS
                                ▼
┌───────────────────────────────────────────────────────────────┐
│  Layer 5: SELF-CONSISTENCY (OPTIONAL - 3x API calls)          │
│  ├── Sinh lại câu hỏi 3 lần                                  │
│  ├── So sánh đáp án giữa các lần                             │
│  └── Nếu bất ổn định → flag "unstable_question"              │
└───────────────────────────────┬───────────────────────────────┘
                                │ ALL PASS
                                ▼
                    ✅ Câu hỏi đáng tin cậy
                    → Gửi giáo viên review cuối cùng
```

---

## 4. Scoring System đề xuất

```python
VERIFICATION_SCORES = {
    "layer1_rule_based": {
        "weight": 0.15,  # Format checks
        "max": 100,
    },
    "layer2_solve_compare": {
        "weight": 0.35,  # Đáp án đúng/sai - QUAN TRỌNG NHẤT
        "max": 100,
    },
    "layer3_cross_model": {
        "weight": 0.30,  # Chất lượng câu hỏi
        "max": 100,
    },
    "layer4_grounding": {
        "weight": 0.15,  # Nguồn gốc kiến thức
        "max": 100,
    },
    "layer5_consistency": {
        "weight": 0.05,  # Ổn định (optional)
        "max": 100,
    },
}

# Final score = weighted sum
# >= 85: ✅ Auto-approve (vẫn gửi giáo viên xem)
# 60-84: ⚠️ Cần giáo viên review kỹ
# < 60:  ❌ Tự động reject, tạo lại
```

---

## 5. Implementation Priority

| # | Chiến lược | Complexity | Impact | MVP? |
|---|-----------|-----------|--------|------|
| 1 | **Solve & Compare** | Thấp | 🔥🔥🔥 Cao nhất | ✅ **Làm trước** |
| 2 | **Distractor Analysis** | Trung bình | 🔥🔥 Cao | ✅ **Làm luôn** |
| 3 | **Statement Ambiguity** | Trung bình | 🔥🔥 Cao | ✅ **Làm luôn** |
| 4 | **Difficulty Calibration** | Thấp | 🔥 Trung bình | ✅ **Làm luôn** |
| 5 | **Cross-Model Review** | Trung bình | 🔥🔥 Cao | ⏳ Phase 2 |
| 6 | **Curriculum Grounding** | Cao (cần RAG) | 🔥🔥🔥 Cao nhất | ⏳ Phase 2 |
| 7 | **Self-Consistency** | Cao (3x cost) | 🔥 Trung bình | ⏳ Phase 3 |

---

## 6. Kiến trúc File đề xuất

```
backend/app/agents/
├── base.py                    # BaseAgent (ĐÃ CÓ)
├── question_agent.py          # Agent 5: Sinh câu hỏi (ĐÃ CÓ)
├── answer_agent.py            # Agent 7: Sinh đáp án (ĐÃ CÓ)
├── validator_agent.py         # Agent 8: Format validation (ĐÃ CÓ)
├── verification_agent.py      # Agent 8b: Content verification (MỚI)
│   ├── SolveAndCompareCheck   # Layer 2
│   ├── DistractorAnalysis     # Layer 3 (MCQ)
│   ├── AmbiguityDetector      # Layer 3 (Đ/S)
│   ├── DifficultyCalibration   # Layer 3
│   ├── CurriculumGrounding    # Layer 4 (Phase 2)
│   └── SelfConsistencyCheck   # Layer 5 (Phase 3)
└── ...
```

---

## 7. Gemini Models sử dụng

| Model | Dùng cho | Lý do |
|-------|----------|-------|
| **Gemini 2.0 Flash** | Sinh câu hỏi (QuestionAgent) | Nhanh, rẻ, sáng tạo |
| **Gemini 2.0 Flash** | Solve & Compare (Layer 2) | Nhanh, đủ chính xác cho solve |
| **Gemini 2.5 Pro** | Cross-Model Review (Layer 3) | Reasoning mạnh, adversarial tốt |
| **Gemini 2.5 Pro** | Curriculum Grounding (Layer 4) | Hiểu context phức tạp |

**Cấu hình đề xuất trong `.env`:**

```env
# Model chính để sinh câu hỏi
GEMINI_MODEL=gemini-2.0-flash

# Model mạnh để verify (cross-model)
GEMINI_VERIFY_MODEL=gemini-2.5-pro
```

---

## 8. Chi phí ước tính (cho 20 câu)

| Layer | API calls | Model | Ước tính |
|-------|-----------|-------|----------|
| Layer 1 | 0 | Rule-based | Miễn phí |
| Layer 2 | 20 | Gemini 2.0 Flash | ~$0.01 |
| Layer 3 | 4 (batch) | Gemini 2.5 Pro | ~$0.05 |
| Layer 4 | 20 | Gemini 2.0 Flash | ~$0.01 |
| Layer 5 | 60 | Gemini 2.0 Flash | ~$0.03 |
| **Tổng MVP (Layer 1-4)** | **~24** | | **~$0.07** |
| **Tổng đầy đủ (Layer 1-5)** | **~84** | | **~$0.10** |

---

## 9. Output Format của Verification Report

```json
{
  "verification_report": {
    "exam_id": "exam_123",
    "timestamp": "2025-01-01T00:00:00Z",
    "overall_score": 87,
    "overall_status": "passed_with_warnings",
    "summary": {
      "total_questions": 20,
      "auto_approved": 18,
      "needs_review": 2,
      "auto_rejected": 0
    },
    "question_reports": [
      {
        "question_id": "q_1",
        "question_number": 1,
        "type": "multiple_choice",
        "verification_score": 92,
        "status": "approved",
        "checks": {
          "solve_compare": {
            "status": "match",
            "ai_answer": "A",
            "original_answer": "A",
            "confidence": 0.95,
            "reasoning": "Tim người có 4 ngăn..."
          },
          "distractor_quality": {
            "status": "acceptable",
            "quality": "good",
            "details": [
              {"option": "B", "plausibility": 0.7, "reason": "Nhầm với tim ếch"},
              {"option": "D", "plausibility": 0.2, "reason": "Quá dễ loại"}
            ]
          },
          "difficulty_calibration": {
            "status": "match",
            "assigned": "nhan_biet",
            "assessed": "nhan_biet",
            "reasoning": "Câu hỏi yêu cầu nhớ lại kiến thức cơ bản"
          }
        },
        "issues": [],
        "suggestions": []
      },
      {
        "question_id": "q_5",
        "question_number": 5,
        "type": "true_false",
        "verification_score": 45,
        "status": "needs_review",
        "checks": {
          "solve_compare": {
            "status": "mismatch",
            "ai_assessment": [
              {"statement_id": "s_5_1", "ai_says": true, "original": true},
              {"statement_id": "s_5_2", "ai_says": true, "original": false}
            ],
            "confidence": 0.6,
            "reasoning": "Phát biểu thứ 2 có thể hiểu theo nhiều cách..."
          },
          "ambiguity_detection": {
            "status": "ambiguous",
            "ambiguous_statements": [
              {
                "id": "s_5_2",
                "ambiguity_type": "vague_term",
                "term": "thường",
                "suggestion": "Viết lại: 'Tất cả sinh vật đều...' hoặc 'Hầu hết sinh vật...'"
              }
            ]
          }
        },
        "issues": [
          {
            "severity": "major",
            "type": "answer_mismatch",
            "description": "Phát biểu s_5_2: AI verify chọn TRUE nhưng đáp án gốc là FALSE",
            "suggestion": "Kiểm tra lại phát biểu, có thể mơ hồ"
          }
        ],
        "suggestions": [
          "Viết lại phát biểu s_5_2 cho rõ ràng hơn"
        ]
      }
    ],
    "action_required": [
      {
        "priority": "high",
        "question_id": "q_5",
        "message": "Phát biểu Đ/S mơ hồ, cần giáo viên review",
        "fix": "Viết lại phát biểu s_5_2"
      }
    ]
  }
}
```

---

## 10. Tóm tắt cho MVP

### Scope MVP (Layer 1-4):

1. **Layer 1: Rule-based** → Đã có, giữ nguyên
2. **Layer 2: Solve & Compare** → Gemini tự giải lại, so đáp án
3. **Layer 3: Distractor + Ambiguity + Difficulty** → Gemini review chất lượng
4. **Layer 4: Curriculum Grounding** → Đối chiếu với curriculum JSON (đơn giản, chưa cần RAG)

### Không làm trong MVP:

- Layer 5: Self-Consistency (tốn 3x chi phí, Phase 3)
- Cross-model với Gemini 2.5 Pro (dùng tạm Gemini 2.0 Flash cho cả verify, Phase 2)
- RAG-based grounding với ChromaDB (Phase 2)

### Files cần tạo mới:

```
backend/app/agents/verification_agent.py   # VerificationAgent chính
backend/tests/test_verification.py         # Unit tests
docs/09-Question-Verification-Brainstorm.md # Tài liệu này
```

### Files cần sửa:

```
backend/app/agents/base.py                 # Thêm verify model config
backend/app/services/gemini_service.py     # Thêm method cho verify prompts
backend/app/core/config.py                 # Thêm GEMINI_VERIFY_MODEL setting
```

---

## 11. Edge Cases & Failure Modes

### 11.1 Gemini verify bị sai (False Negative / False Positive)

**Vấn đề:** Gemini verify chọn đáp án khác → nhưng đáp án GỐC mới là đúng.

```
Ví dụ:
  Câu hỏi: "Phản ứng nào sau đây là phản ứng thu nhiệt?"
  Đáp án gốc: C (Nung CaCO₃)
  Gemini verify chọn: A (Đốt cháy nhiên liệu)

  → Gemini verify SAI (A là phản ứng tỏa nhiệt)
  → Nhưng nếu tin Gemini → reject câu hỏi đúng!
```

**Giải pháp:**

| Tình huống | Hành động |
|-----------|-----------|
| Solve & Compare: match | ✅ Tăng confidence |
| Solve & Compare: mismatch | ⚠️ Không auto-reject, gửi giáo viên review |
| Solve & Compare: mismatch + confidence < 0.3 | ⚠️ Gemini không chắc → vẫn gửi giáo viên |
| Cả 2 model đều mismatch với nhau | 🔴 Không tin ai → giáo viên quyết định cuối |

**Nguyên tắc cốt lõi:** NEVER auto-reject chỉ vì Gemini verify khác. Luôn có giáo viên là "final judge".

### 11.2 Câu hỏi đúng nhưng Gemini hiểu sai ngữ nghĩa

```
Ví dụ:
  Câu Đ/S: "Phản ứng phân hủy là phản ứng có nhiều chất phản ứng
            cho một sản phẩm."  → FALSE (đúng là 1 chất → nhiều sản phẩm)

  Gemini verify: "TRUE" → vì hiểu nhầm "nhiều chất phản ứng" = "nhiều nguyên tử"
  → Gemini sai do hiểu ngữ pháp tiếng Việt
```

**Giải pháp:**
- Prompt phải rõ ràng: "Đọc chính xác từng từ, không suy diễn thêm"
- Nếu confidence < 0.5 → flag "uncertain" thay vì "mismatch"
- Ưu tiên dùng Gemini 2.5 Pro cho verify (reasoning tốt hơn)

### 11.3 Câu hỏi có nhiều đáp án đúng

```
Ví dụ:
  "Chất nào sau đây là oxit bazơ?"
  A: Na₂O ✅
  B: CaO ✅
  C: CO₂ ❌
  D: SO₃ ❌

  → Câu hỏi LỖI: có 2 đáp án đúng
  → Gemini verify chọn A, đáp án gốc là B → MISMATCH nhưng câu hỏi mới sai
```

**Giải pháp:**
- Prompt verify phải hỏi: "Có đáp án nào khác cũng đúng không?"
- Nếu phát hiện multiple correct answers → flag "question_defect" (critical)
- Đây là lỗi **QuestionAgent** chứ không phải verify sai

### 11.4 Câu hỏi vận dụng có nhiều cách giải

```
Ví dụ:
  "Tính lực tác dụng lên vật 5kg khi gia tốc 2m/s²"
  → F = ma = 10N (đáp án duy nhất)

  Nhưng câu tự luận: "Trình bày cách xác định gia tốc trọng trường"
  → Nhiều cách: lò xo, con lắc, rơi tự do...
  → Không thể solve & compare đơn giản
```

**Giải pháp:**
- MCQ/ĐS/Short Answer: Solve & Compare hoạt động tốt
- Essay: Chỉ dùng **key_points coverage check** (đếm số ý chính rubric có đủ không)
- Essay không适合 solve & compare → skip Layer 2, chỉ dùng Layer 3

---

## 12. Từng môn KHTN: Thách thức riêng biệt

### 12.1 Vật lý (Physics)

| Thách thức | Ví dụ | Cách xử lý |
|-----------|-------|------------|
| **Công thức tính toán** | F=ma, V=IR, P=F/A | Gemini solve tốt, nhưng cần verify đơn vị |
| **Đơn vị đo lường** | N, Pa, A, V, W | Kiểm tra đơn vị có khớp không |
| **Đồ thị biểu đồ** | Đồ thị V-t, P-T | Khó verify tự động → giáo viên review |
| **Nhiều cách giải** | Điện trở song song/series | Kiểm tra phương pháp có hợp lệ không |

**Prompt bổ sung cho Vật lý:**
```
Khi verify câu Vật lý:
1. Kiểm tra công thức sử dụng có đúng không
2. Kiểm tra đơn vị đầu ra có hợp lệ không (N, Pa, J, W...)
3. Kiểm tra có bỏ qua lực nào không (trọng lực, ma sát...)
4. Kiểm tra điều kiện bài cho (không ma sát? không trọng lực?)
```

### 12.2 Hóa học (Chemistry)

| Thách thức | Ví dụ | Cách xử lý |
|-----------|-------|------------|
| **Phương trình hóa học** | 2H₂ + O₂ → 2H₂O | Kiểm tra cân bằng PT, số mol |
| **Hiện tượng phản ứng** | Tạo kết tủa, đổi màu | Gemini có thể sai về hiện tượng cụ thể |
| **Loại phản ứng** | Oxi-hoá khử, trao đổi, phân hủy, hợp nhất | Kiểm tra phân loại đúng không |
| **Chuỗi phản ứng** | A → B → C | Nhiều bước, dễ sai ở bước trung gian |

**Prompt bổ sung cho Hóa học:**
```
Khi verify câu Hóa học:
1. Kiểm tra phương trình hóa học có cân bằng chưa
2. Kiểm tra số mol, khối lượng mol có đúng không
3. Kiểm tra loại phản ứng có phân loại đúng không
4. Kiểm tra hiện tượng mô tả có khớp thực tế không
5. Kiểm tra điều kiện phản ứng (nhiệt độ, xúc tác, áp suất)
```

### 12.3 Sinh học (Biology)

| Thách thức | Ví dụ | Cách xử lý |
|-----------|-------|------------|
| **Khái niệm trừu trượng** | Gen, NST, ADN | Gemini hay nhầm lẫn các khái niệm liên quan |
| **Quá trình sinh học** | Quang hợp, hô hấp, nguyên phân | Nhiều bước, dễ bỏ sót hoặc nhầm thứ tự |
| **Phân loại sinh vật** | Giới, Ngành, Lớp, Bộ, Họ, Chi, Loài | Gemini hay nhầm phân loại |
| **Số liệu thống kê** | Số nhiễm sắc thể, số gen | Cần verify chính xác con số |

**Prompt bổ sung cho Sinh học:**
```
Khi verify câu Sinh học:
1. Kiểm tra tên khoa học (tiếng Latin) có đúng chính tả không
2. Kiểm tra phân loại sinh vật có đúng cấp bậc không
3. Kiểm tra số liệu (số NST, số gen) có chính xác không
4. Kiểm tra thứ tự các bước trong quá trình sinh học
5. Kiểm tra cơ quan nào thực hiện chức năng nào
```

---

## 13. Tích hợp vào Orchestrator hiện tại

### 13.1 Vị trí trong pipeline

```
Flow hiện tại:
  Matrix → Spec → Questions → Teacher Review → Answers → Validator → Export

Flow mới (thêm Verification):
  Matrix → Spec → Questions → [VERIFICATION] → Teacher Review → Answers → Validator → Export
                                    ↑
                              Chèn vào ĐÂY
                              (sau sinh câu, trước review)
```

**Tại sao chèn TRƯỚC Teacher Review:**
- Giáo viên sẽ thấy ngay câu nào flagged → review nhanh hơn
- Không lãng phí thời gian review câu đã bị AI reject
- Giáo viên có thể override quyết định của AI

### 13.2 Thay đổi trong Orchestrator

```python
# Trong orchestrator.py (hoặc exam_flow.py)

async def run_exam_flow(request):
    # ... existing steps ...
    matrix_result = await matrix_agent.run(request=request)
    spec = await spec_agent.run(...)
    question_result = await question_agent.run(specification=spec)

    # MỚI: Verification trước khi gửi giáo viên
    verification_result = await verification_agent.run(
        questions=question_result["questions"],
        answer_key=question_result["answer_key"],
        curriculum=normalized_curriculum,
        spec=spec,
    )

    # Gửi cả câu hỏi + kết quả verify cho giáo viên
    return {
        **question_result,
        "verification": verification_result,  # MỚI
    }
```

### 13.3 API endpoint mới

```
POST /api/questions/verify
  - Input: questions, answer_key, curriculum, spec
  - Output: verification_report

POST /api/questions/verify/{question_id}
  - Input: single question + answer_key
  - Output: single question verification report
```

---

## 14. UI/UX cho Giáo viên Review

### 14.1 Hiển thị kết quả Verify trong Teacher Review

```
┌─────────────────────────────────────────────────────────────────┐
│  Câu hỏi 5 (Đúng/Sai) - ⚠️ CẦN REVIEW                        │
│─────────────────────────────────────────────────────────────────│
│  Nội dung: "Sinh vật thường có tế bào."                        │
│                                                                  │
│  ┌─ Kết quả Verify ──────────────────────────────────────────┐  │
│  │  🔴 Solve & Compare: MISMATCH (confidence: 0.6)           │  │
│  │     AI verify chọn: TRUE | Đáp án gốc: FALSE             │  │
│  │     Lý do: "Phát biểu mơ hồ, 'thường' không xác định"    │  │
│  │                                                            │  │
│  │  🟡 Ambiguity: AMBIGUOUS                                  │  │
│  │     Từ mơ hồ: "thường"                                   │  │
│  │     Gợi ý: "Tất cả sinh vật đều được cấu tạo từ tế bào" │  │
│  │                                                            │  │
│  │  🟢 Difficulty: MATCH (nhan_biet)                         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
│  [✅ Chấp nhận]  [🔄 Tạo lại]  [✏️ Chỉnh sửa]                │
└─────────────────────────────────────────────────────────────────┘
```

### 14.2 Màu sắc theo severity

| Màu | Ý nghĩa | Hành động |
|-----|----------|-----------|
| 🟢 Xanh lá | Verify pass, không vấn đề | Giáo viên có thể approve nhanh |
| 🟡 Vàng | Có warning (ambiguity, distractor kém) | Giáo viên nên đọc kỹ |
| 🔴 Đỏ | Critical (answer mismatch, multiple correct) | Giáo viên PHẢI review |

### 14.3 Thống kê tổng quan

```
┌─────────────────────────────────────────────────────┐
│  Verification Summary - Đề kiểm tra giữa kì I      │
│─────────────────────────────────────────────────────│
│  Tổng câu hỏi: 20                                   │
│  🟢 Auto-approved: 16 (80%)                         │
│  🟡 Cần review: 3 (15%)                             │
│  🔴 Có vấn đề: 1 (5%)                               │
│                                                      │
│  Verification Score: 87/100                          │
│  Confidence trung bình: 0.82                         │
│                                                      │
│  [Xem chi tiết]  [Export report]  [Tạo lại câu đỏ] │
└─────────────────────────────────────────────────────┘
```

---

## 15. Tối ưu hóa Performance

### 15.1 Batch API calls thay vì gọi từng câu

**Vấn đề:** 20 câu = 20 API calls riêng lẻ → chậm, tốn quota.

**Giải pháp:** Gộp nhiều câu vào 1 prompt (batch).

```python
# Thay vì:
for question in questions:
    result = await verify_single(question)  # 20 calls

# Thì:
batch_result = await verify_batch(questions[:5])  # 4 calls (5 câu/lần)
batch_result = await verify_batch(questions[5:10])
batch_result = await verify_batch(questions[10:15])
batch_result = await verify_batch(questions[15:20])
```

**Batch prompt:**
```
Bạn là giáo viên KHTN. Hãy giải 5 câu hỏi sau và trả lời JSON array.

Câu 1: {q1.content}
Options: {q1.options}

Câu 2: {q2.content}
Options: {q2.options}

...

Trả về JSON:
[
  {"question_id": "q_1", "your_answer": "A", "confidence": 0.9, "reasoning": "..."},
  {"question_id": "q_2", "your_answer": "B", "confidence": 0.8, "reasoning": "..."},
  ...
]
```

### 15.2 Chạy song song (asyncio.gather)

```python
async def verify_all_layers(questions, answer_key, curriculum):
    # Chạy song song các layer
    layer2_task = solve_and_compare(questions, answer_key)
    layer3_task = cross_model_review(questions, curriculum)
    layer4_task = curriculum_grounding(questions, curriculum)

    # Đợi tất cả hoàn thành
    layer2, layer3, layer4 = await asyncio.gather(
        layer2_task, layer3_task, layer4_task
    )

    return merge_results(layer2, layer3, layer4)
```

### 15.3 Cache kết quả verify

```python
# Cache key = hash(question_content + answer)
# Nếu cùng câu hỏi đã verify trước đó → dùng lại kết quả

import hashlib

def cache_key(question, answer):
    content = f"{question['content']}:{answer}"
    return hashlib.md5(content.encode()).hexdigest()
```

### 15.4 Chỉ verify câu mới/chỉnh sửa

```
Giáo viên sửa câu 5 → chỉ verify lại câu 5
Không cần verify lại 19 câu còn lại (đã approve trước đó)
```

---

## 16. Confidence Threshold Tuning

### 16.1 Ngưỡng confidence đề xuất

| Confidence | Trạng thái | Hành động |
|-----------|-----------|-----------|
| >= 0.9 | ✅ Rất tin cậy | Auto-approve |
| 0.7 - 0.89 | ✅ Tin cậy | Auto-approve, hiện verify info |
| 0.5 - 0.69 | ⚠️ Không chắc | Gửi giáo viên review |
| 0.3 - 0.49 | ⚠️ Rất không chắc | Gửi giáo viên review + highlight |
| < 0.3 | 🔴 Không tin cậy | Auto-reject, tạo lại |

### 16.2 Điều chỉnh theo loại câu hỏi

```python
CONFIDENCE_THRESHOLDS = {
    "multiple_choice": {
        "auto_approve": 0.8,   # MCQ: confidence >= 0.8 → approve
        "auto_reject": 0.3,
    },
    "true_false": {
        "auto_approve": 0.7,   # Đ/S: khó hơn, threshold thấp hơn
        "auto_reject": 0.25,
    },
    "short_answer": {
        "auto_approve": 0.75,
        "auto_reject": 0.3,
    },
    "essay": {
        "auto_approve": None,  # Essay: KHÔNG auto-approve
        "auto_reject": None,   # Essay: KHÔNG auto-reject
        # Luôn gửi giáo viên review
    },
}
```

### 16.3 Điều chỉnh theo mức độ nhận thức

```python
DIFFICULTY_CONFIDENCE_BONUS = {
    "nhan_biet": +0.1,    # Câu dễ → confidence cao hơn
    "thong_hieu": 0.0,    # Câu trung bình → giữ nguyên
    "van_dung": -0.1,     # Câu khó → confidence thấp hơn
}
```

---

## 17. Feedback Loop: Học từ Giáo viên

### 17.1 Thu thập feedback

```
Giáo viên approve câu mà AI flagged "mismatch"
  → Ghi nhận: AI verify sai lần này
  → Lưu vào DB: {question_id, ai_verdict, teacher_verdict, was_correct}

Giáo viên reject câu mà AI approve
  → Ghi nhận: AI verify miss lỗi
  → Lưu vào DB: {question_id, ai_verdict, teacher_verdict, was_correct}
```

### 17.2 Dùng feedback để cải thiện

```python
# Thống kê accuracy của verify
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN ai_verdict = teacher_verdict THEN 1 ELSE 0 END) as correct,
    AVG(confidence) as avg_confidence
FROM verification_feedback
WHERE created_at > NOW() - INTERVAL '30 days';

# Nếu accuracy < 80% → cần tune prompt hoặc threshold
```

### 17.3 Fine-tune prompt dựa trên feedback

```
Nếu AI hay sai ở câu Hóa học:
  → Thêm rule vào prompt: "Kiểm tra kỹ phương trình hóa học có cân bằng chưa"

Nếu AI hay nhầm mức độ nhận thức:
  → Thêm few-shot examples vào prompt difficulty calibration
```

---

## 18. Pseudocode: VerificationAgent class

```python
class VerificationAgent(BaseAgent):
    """Agent 8b: Content Verification - Kiểm tra câu hỏi có đúng không."""

    # Confidence thresholds
    AUTO_APPROVE_THRESHOLD = 0.8
    AUTO_REJECT_THRESHOLD = 0.3

    async def run(self, *, questions, answer_key, curriculum=None, spec=None):
        """Chạy verification pipeline cho tất cả câu hỏi."""

        # Layer 1: Rule-based (đã có trong ValidatorAgent)
        # Ở đây chỉ cần các check liên quan đến content

        # Layer 2: Solve & Compare
        solve_results = await self._solve_and_compare(questions, answer_key)

        # Layer 3: Quality checks (batch)
        quality_results = await self._quality_review(questions, curriculum)

        # Layer 4: Curriculum grounding (nếu có curriculum)
        grounding_results = None
        if curriculum:
            grounding_results = await self._curriculum_grounding(questions, curriculum)

        # Merge results
        question_reports = self._merge_results(
            questions, solve_results, quality_results, grounding_results
        )

        # Tính verification score
        overall_score = self._calculate_overall_score(question_reports)

        return {
            "overall_score": overall_score,
            "overall_status": self._status_from_score(overall_score),
            "summary": self._build_summary(question_reports),
            "question_reports": question_reports,
            "action_required": self._extract_actions(question_reports),
        }

    async def _solve_and_compare(self, questions, answer_key):
        """Layer 2: Gemini tự giải lại câu hỏi."""
        answer_map = {a["question_id"]: a for a in answer_key}
        results = []

        for question in questions:
            answer = answer_map.get(question["id"])
            if not answer:
                continue

            # Build verify prompt (không cho xem đáp án)
            prompt = self._build_solve_prompt(question)

            # Call Gemini
            ai_response = await self._call_gemini(prompt)

            # So sánh
            match, confidence = self._compare_answers(
                question, ai_response, answer
            )

            results.append({
                "question_id": question["id"],
                "match": match,
                "ai_answer": ai_response.get("your_answer"),
                "original_answer": self._extract_answer(question, answer),
                "confidence": confidence,
                "reasoning": ai_response.get("reasoning", ""),
            })

        return results

    async def _quality_review(self, questions, curriculum):
        """Layer 3: Kiểm tra distractor, ambiguity, difficulty."""
        results = []

        # Group questions by type
        mcq_questions = [q for q in questions if q["type"] == "multiple_choice"]
        tf_questions = [q for q in questions if q["type"] == "true_false"]

        # MCQ: Distractor analysis (batch)
        if mcq_questions:
            distractor_results = await self._distractor_analysis(mcq_questions)
            results.extend(distractor_results)

        # Đ/S: Ambiguity detection (batch)
        if tf_questions:
            ambiguity_results = await self._ambiguity_detection(tf_questions)
            results.extend(ambiguity_results)

        # All: Difficulty calibration
        difficulty_results = await self._difficulty_calibration(questions)
        results.extend(difficulty_results)

        return results

    async def _curriculum_grounding(self, questions, curriculum):
        """Layer 4: Đối chiếu với curriculum JSON."""
        results = []

        for question in questions:
            # Tìm topic/lesson khớp trong curriculum
            matched = self._find_curriculum_match(question, curriculum)

            # Tính grounding score
            score = self._calculate_grounding_score(question, matched)

            results.append({
                "question_id": question["id"],
                "grounded": score > 0.7,
                "grounding_score": score,
                "matched_topics": matched.get("topics", []),
                "matched_objectives": matched.get("objectives", []),
            })

        return results

    def _build_solve_prompt(self, question):
        """Tạo prompt cho Gemini solve lại."""
        base = f"""Bạn là giáo viên KHTN lớp 8.
Hãy đọc câu hỏi sau và tự trả lời bằng cách suy luận khoa học.
KHÔNG nhìn đáp án. Trả lời dựa trên kiến thức của bạn.

Câu hỏi: {question['content']}
"""

        if question["type"] == "multiple_choice":
            options = question.get("options", {})
            options_text = "\n".join(f"  {k}: {v}" for k, v in options.items())
            base += f"\nPhương án:\n{options_text}\n"
            base += '\nTrả về JSON: {"your_answer": "A|B|C|D", "reasoning": "...", "confidence": 0.0-1.0}'

        elif question["type"] == "true_false":
            statements = question.get("statements", [])
            stmt_text = "\n".join(
                f"  {s['id']}: {s['content']}" for s in statements
            )
            base += f"\nPhát biểu:\n{stmt_text}\n"
            base += '\nTrả về JSON: {"your_assessment": [{"id": "s_1_1", "is_true": true/false}], "reasoning": "...", "confidence": 0.0-1.0}'

        elif question["type"] == "short_answer":
            base += '\nTrả về JSON: {"your_answer": "câu trả lời", "reasoning": "...", "confidence": 0.0-1.0}'

        return base

    def _compare_answers(self, question, ai_response, original_answer):
        """So sánh đáp án AI verify vs đáp án gốc."""
        if question["type"] == "multiple_choice":
            ai_ans = ai_response.get("your_answer", "").strip().upper()
            orig_ans = original_answer.get("correct_answer", "").strip().upper()
            match = ai_ans == orig_ans
            confidence = ai_response.get("confidence", 0.5)
            return match, confidence

        elif question["type"] == "true_false":
            ai_assessment = ai_response.get("your_assessment", [])
            original_statements = question.get("statements", [])
            match_count = 0
            total = len(original_statements)

            for stmt in original_statements:
                ai_stmt = next(
                    (a for a in ai_assessment if a.get("id") == stmt["id"]),
                    None
                )
                if ai_stmt and ai_stmt.get("is_true") == stmt.get("is_true"):
                    match_count += 1

            match = match_count == total
            confidence = match_count / total if total > 0 else 0.5
            return match, confidence

        # short_answer, essay: so sánh fuzzy
        confidence = ai_response.get("confidence", 0.5)
        return True, confidence  # Tạm thời accept, cần logic phức tạp hơn

    def _calculate_overall_score(self, question_reports):
        """Tính verification score tổng thể."""
        if not question_reports:
            return 100

        scores = [r.get("verification_score", 50) for r in question_reports]
        return round(sum(scores) / len(scores))

    def _status_from_score(self, score):
        if score >= 85:
            return "passed"
        elif score >= 60:
            return "passed_with_warnings"
        else:
            return "failed"

    def _build_summary(self, question_reports):
        auto_approved = sum(1 for r in question_reports if r.get("status") == "approved")
        needs_review = sum(1 for r in question_reports if r.get("status") == "needs_review")
        auto_rejected = sum(1 for r in question_reports if r.get("status") == "rejected")

        return {
            "total_questions": len(question_reports),
            "auto_approved": auto_approved,
            "needs_review": needs_review,
            "auto_rejected": auto_rejected,
        }

    def _extract_actions(self, question_reports):
        actions = []
        for report in question_reports:
            if report.get("status") in ("needs_review", "rejected"):
                actions.append({
                    "priority": "high" if report.get("status") == "rejected" else "medium",
                    "question_id": report["question_id"],
                    "issues": report.get("issues", []),
                    "suggestions": report.get("suggestions", []),
                })
        return actions
```

---

## 19. Monitoring & Logging

### 19.1 Metrics cần track

| Metric | Mô tả | Alert khi |
|--------|-------|-----------|
| `verify_avg_score` | Verification score trung bình | < 70 |
| `verify_mismatch_rate` | % câu mismatch | > 20% |
| `verify_auto_reject_rate` | % câu auto-reject | > 10% |
| `verify_api_latency_ms` | Thời gian verify | > 30s |
| `verify_api_cost` | Chi phí API verify | > $0.20/đề |
| `teacher_override_rate` | % giáo viên override AI | > 30% → tune prompt |

### 19.2 Logging schema

```json
{
  "timestamp": "2025-01-01T00:00:00Z",
  "exam_id": "exam_123",
  "agent": "verification_agent",
  "action": "verify_question",
  "question_id": "q_5",
  "question_type": "true_false",
  "layer": "solve_compare",
  "ai_answer": true,
  "original_answer": false,
  "match": false,
  "confidence": 0.6,
  "latency_ms": 1200,
  "model_used": "gemini-2.0-flash",
  "tokens_used": 450
}
```

---

## 20. Roadmap chi tiết

### Phase 1 (MVP - Tuần 1-2)

- [ ] Tạo `VerificationAgent` với Layer 2 (Solve & Compare)
- [ ] Thêm Layer 3 cơ bản (Distractor + Ambiguity + Difficulty)
- [ ] Thêm Layer 4 đơn giản (curriculum matching, chưa cần RAG)
- [ ] Cập nhật config.py thêm GEMINI_VERIFY_MODEL
- [ ] Tạo API endpoint `/api/questions/verify`
- [ ] Unit tests cho VerificationAgent
- [ ] Cập nhật frontend Teacher Review hiển thị verify results

### Phase 2 (Tuần 3-4)

- [ ] Cross-model verify với Gemini 2.5 Pro
- [ ] RAG-based curriculum grounding với ChromaDB
- [ ] Batch API calls tối ưu
- [ ] Cache kết quả verify
- [ ] Teacher feedback collection
- [ ] Monitoring dashboard

### Phase 3 (Tuần 5+)

- [ ] Self-consistency check (sinh lại nhiều lần)
- [ ] Fine-tune prompt dựa trên teacher feedback
- [ ] Confidence threshold auto-tuning
- [ ] Support thêm môn khác (Toán, Hóa, Sinh riêng)
- [ ] Export verification report (PDF/Word)

---

## 21. Tham chiếu

- [06-Validation-Checklist.md](./06-Validation-Checklist.md) — Các validation checks đã định nghĩa
- [05-Prompt-Design.md](./05-Prompt-Design.md) — Prompt templates hiện tại
- [03-AI-Agents-Architecture.md](./03-AI-Agents-Architecture.md) — Kiến trúc agents
- `backend/app/agents/question_agent.py` — Question generation logic
- `backend/app/agents/validator_agent.py` — Current validation logic
- `backend/data/curriculum/khtn_grade_*.json` — Curriculum data (nguồn kiến thức)
- [Google Gemini API Docs](https://ai.google.dev/docs) — Gemini model capabilities
- [Bloom's Taxonomy](https://cft.vanderbilt.edu/guides-sub-pages/blooms-taxonomy/) — Mức độ nhận thức
