import asyncio
import json
import logging

from fastapi import HTTPException

from app.agents.base import BaseAgent
from app.core.config import settings
from app.schemas.ai_outputs import AnswerGenerationOutput
from app.services.exam.answer_content import normalize_answer
from app.services.ai_provider_chain import provider_operation_timeout_seconds

logger = logging.getLogger("smart-exam-ai")


class AnswerAgent(BaseAgent):
    """Agent 7: Answer & Rubric Agent.

    Generates detailed answer keys and grading rubrics for accepted questions.
    Only generates after questions have been approved by teacher review.
    Follows the architecture from docs/03-AI-Agents-Architecture.md.
    """

    OPTION_LABELS = ("A", "B", "C", "D")

    async def run(self, *, questions, specification):
        """Generate answers and rubrics for the given questions.

        Args:
            questions: List of accepted question dicts.
            specification: The exam specification.

        Returns:
            dict with "answer_key" and "rubric" lists.
        """
        if self.has_ai:
            try:
                generated = await asyncio.wait_for(
                    asyncio.to_thread(self._run_gemini, questions, specification),
                    timeout=provider_operation_timeout_seconds(),
                )
                self._validate_generated_result(generated, questions)
                return self._normalize_generated_answers(generated, questions, specification)
            except Exception as exc:
                logger.warning(
                    "AnswerAgent AI generation failed: %s: %s",
                    type(exc).__name__,
                    str(exc)[:200],
                )
                if settings.ENV.strip().lower() not in {"test", "testing"}:
                    raise HTTPException(
                        status_code=502,
                        detail="Không thể tạo đáp án khoa học đã kiểm chứng từ provider.",
                    ) from exc

        if not self.has_ai and settings.ENV.strip().lower() not in {"test", "testing"}:
            raise HTTPException(
                status_code=503,
                detail="Cần cấu hình OpenAI, Gemini hoặc DeepSeek để tạo đáp án khoa học.",
            )

        # Deterministic MVP fallback
        answer_key = []
        rubric = []

        for question in questions:
            spec = self._find_spec(question, specification)
            answer_key.append(self._answer(question, spec))
            if question.get("type") == "essay":
                rubric.append(self._rubric(question, spec))

        return {"answer_key": answer_key, "rubric": rubric}

    def _find_spec(self, question, specification):
        """Find the matching specification row for a question."""
        question_id = question.get("id", "")
        for spec in specification:
            if spec.get("question_id") == question_id:
                return spec
        # Fallback: build minimal spec from question metadata
        return {
            "topic": question.get("metadata", {}).get("topic", ""),
            "knowledge_unit": question.get("metadata", {}).get("knowledge_unit", ""),
            "achievement": question.get("metadata", {}).get("achievement", ""),
            "score": question.get("score", 0),
            "question_type": question.get("type", ""),
            "difficulty": question.get("difficulty", ""),
            "question_id": question_id,
            "question_number": question.get("number", 0),
        }

    def _run_gemini(self, questions, specification):
        prompt = f"""
Bạn là giáo viên THCS môn Khoa học tự nhiên, chuyên ra đáp án và rubric chấm điểm.
Hãy tạo đáp án chi tiết và rubric cho các câu hỏi sau.

CHỈ TRẢ VỀ JSON HỢP LỆ, KHÔNG MARKDOWN, KHÔNG THÊM GIẢI THÍCH.

Câu hỏi:
{json.dumps(questions, ensure_ascii=False)}

Bản đặc tả:
{json.dumps(specification, ensure_ascii=False)}

Schema bắt buộc:
{{
  "answer_key": [
    {{
      "question_id": "q_1",
      "question_number": 1,
      "type": "multiple_choice",
      "correct_answer": "C",
      "explanation": "Kết luận, căn cứ kiến thức và giải thích chi tiết bằng tiếng Việt",
      "option_explanations": {{"A": "Vì sao đúng/sai", "B": "Vì sao đúng/sai", "C": "Vì sao đúng/sai", "D": "Vì sao đúng/sai"}}
    }}
  ],
  "rubric": [
    {{
      "question_id": "q_15",
      "question_number": 15,
      "type": "essay",
      "total_score": 2.0,
      "criteria": [
        {{
          "id": "c_1",
          "name": "Nội dung",
          "max_score": 1.5,
          "levels": [
            {{"score": 1.5, "description": "...", "criteria": "..."}},
            {{"score": 1.0, "description": "...", "criteria": "..."}},
            {{"score": 0.5, "description": "...", "criteria": "..."}},
            {{"score": 0, "description": "...", "criteria": "..."}}
          ]
        }}
      ],
      "grading_guide": ["Hướng dẫn chấm"]
    }}
  ]
}}

Quy tắc đáp án:
- multiple_choice: ghi rõ đáp án đúng (A/B/C/D), kèm giải thích.
- true_false: liệt kê từng phát biểu với is_true và giải thích.
- short_answer: ghi đáp án đúng, từ khóa chấp nhận, có cho phép biến thể.
- essay: ghi model_answer (bài giải mẫu), key_points (ý chính cần có).
- Lời giải phải gắn với nội dung cụ thể của câu hỏi, nêu căn cứ và lý do loại từng phương án/phát biểu; không viết chung chung “đối chiếu kiến thức đã học”.
- Yêu cầu cần đạt chỉ mô tả năng lực học sinh, không được dùng làm đáp án hoặc bằng chứng.
- Lời giải phải nêu kiến thức, cơ chế, quan hệ, dữ liệu hoặc phép tính trả lời WHY.
- Với phát biểu sai, chỉ rõ phần sai rồi viết lại mệnh đề khoa học đúng.
- Với câu tính toán, ghi công thức, đổi đơn vị, thay số, kết quả và đơn vị.
- Cấm các câu “phù hợp/không phù hợp với yêu cầu”, “căn cứ kiến thức cho biết”,
  “có thể bỏ qua”, “chỉ cần ghi nhớ”, “không cần hiểu”.
- Không tự tạo tên tài liệu, số trang, mục hay trích dẫn. Hệ thống sẽ gắn minh chứng nguồn từ dữ liệu đã kiểm soát.

Quy tắc rubric (chỉ cho essay):
- Có ít nhất 2 tiêu chí (vd: Nội dung, Diễn đạt).
- Mỗi tiêu chí có 3-4 mức điểm rõ ràng.
- Tổng điểm rubric bằng điểm câu hỏi.
- Có grading_guide hướng dẫn cách chấm.
"""
        generated = self.gemini.generate_json(
            prompt,
            response_model=AnswerGenerationOutput,
        )
        return {
            "answer_key": generated.get("answer_key", []),
            "rubric": generated.get("rubric", []),
        }

    @staticmethod
    def _validate_generated_result(generated, questions):
        """Reject incomplete model output before it can be persisted.

        The deterministic fallback is preferable to a partially generated answer
        key: a missing answer or essay rubric makes an otherwise printable exam
        unsafe to use.  Detailed content-quality verification remains the job of
        the verification and validator agents.
        """
        if not isinstance(generated, dict):
            raise ValueError("AI answer output must be an object")

        answer_key = generated.get("answer_key")
        rubric = generated.get("rubric")
        if not isinstance(answer_key, list) or not isinstance(rubric, list):
            raise ValueError("AI answer output must contain answer_key and rubric lists")

        expected_answer_ids = {question.get("id") for question in questions}
        actual_answer_ids = {
            answer.get("question_id") for answer in answer_key if isinstance(answer, dict)
        }
        if actual_answer_ids != expected_answer_ids or len(answer_key) != len(expected_answer_ids):
            raise ValueError("AI answer output is missing, duplicating, or adding answers")

        expected_rubric_ids = {
            question.get("id") for question in questions if question.get("type") == "essay"
        }
        actual_rubric_ids = {
            item.get("question_id") for item in rubric if isinstance(item, dict)
        }
        if actual_rubric_ids != expected_rubric_ids or len(rubric) != len(expected_rubric_ids):
            raise ValueError("AI answer output is missing, duplicating, or adding essay rubrics")

    def _normalize_generated_answers(self, generated, questions, specification):
        answer_by_id = {
            answer.get("question_id"): answer
            for answer in generated["answer_key"]
            if isinstance(answer, dict)
        }
        normalized = []
        for question in questions:
            spec = self._find_spec(question, specification)
            normalized.append(
                normalize_answer(answer_by_id.get(question.get("id")), question, spec)
            )
        return {"answer_key": normalized, "rubric": generated["rubric"]}

    # ── Deterministic MVP fallback methods ──────────────────────────────

    def _answer(self, question, spec):
        prepared = dict(question)
        if prepared.get("type") == "multiple_choice" and not prepared.get("correct_answer"):
            prepared["correct_answer"] = self._fallback_correct_answer(question)
        return normalize_answer(None, prepared, spec)

    def _fallback_correct_answer(self, question):
        question_number = int(question.get("number", 1) or 1)
        return self.OPTION_LABELS[(question_number - 1) % len(self.OPTION_LABELS)]

    def _rubric(self, question, spec):
        score = spec.get("score", 2.0)
        content_score = round(score * 0.7, 2)
        expression_score = round(score * 0.3, 2)

        return {
            "question_id": question["id"],
            "question_number": question["number"],
            "type": "essay",
            "total_score": score,
            "criteria": [
                {
                    "id": f"c_{question['number']}_1",
                    "name": "Nội dung",
                    "max_score": content_score,
                    "levels": [
                        {
                            "score": content_score,
                            "description": "Trình bày đầy đủ, chính xác các ý chính.",
                            "criteria": "Đủ tất cả key points, không sai kiến thức",
                        },
                        {
                            "score": round(content_score * 0.67, 2),
                            "description": "Trình bày được phần lớn nội dung, có 1-2 ý thiếu.",
                            "criteria": "Đủ 60-80% key points",
                        },
                        {
                            "score": round(content_score * 0.33, 2),
                            "description": "Trình bày được một phần nội dung, nhiều ý thiếu.",
                            "criteria": "Đủ 30-60% key points",
                        },
                        {
                            "score": 0,
                            "description": "Sai hoàn toàn hoặc không trả lời.",
                            "criteria": "Dưới 30% key points hoặc sai kiến thức",
                        },
                    ],
                },
                {
                    "id": f"c_{question['number']}_2",
                    "name": "Diễn đạt",
                    "max_score": expression_score,
                    "levels": [
                        {
                            "score": expression_score,
                            "description": "Diễn đạt rõ ràng, logic, đúng thuật ngữ khoa học.",
                            "criteria": "Không lỗi chính tả, dùng đúng thuật ngữ",
                        },
                        {
                            "score": round(expression_score * 0.5, 2),
                            "description": "Diễn đạt tương đối rõ, có vài lỗi nhỏ.",
                            "criteria": "1-2 lỗi nhỏ về chính tả hoặc thuật ngữ",
                        },
                        {
                            "score": 0,
                            "description": "Diễn đạt khó hiểu, nhiều lỗi.",
                            "criteria": "Trên 2 lỗi hoặc khó hiểu",
                        },
                    ],
                },
            ],
            "grading_guide": [
                "Chấm theo key points trước, sau đó xét cách diễn đạt.",
                "Không trừ điểm nếu học sinh diễn đạt khác nhưng đúng ý.",
                "Khuyến khích các cách trình bày sáng tạo.",
            ],
        }
