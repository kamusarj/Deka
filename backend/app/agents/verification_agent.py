"""AI-assisted content verification for generated KHTN questions.

Legacy verification remains advisory. Interactive full-exam authoring requires
the independent reviewers selected by deployment policy and fails closed on
material defects or missing review capacity. Deterministic checks always remain
authoritative.
"""

import asyncio
import json
import logging
import re
from collections import Counter
from typing import Any, AsyncGenerator

from app.agents.base import BaseAgent
from app.schemas.ai_outputs import (
    IndependentVerificationOutput,
    QualityVerificationOutput,
    SolveVerificationOutput,
)
from app.services.exam.generation_planning import build_generation_plan
from app.services.ai_provider_chain import (
    provider_fallback_allowed,
    provider_operation_timeout_seconds,
)
from app.services.dual_verification_service import (
    DualVerificationService,
    MandatoryReviewUnavailable,
)

logger = logging.getLogger("deka")


class VerificationAgent(BaseAgent):
    AMBIGUOUS_TERMS = ("thường", "có thể", "hầu hết", "nhiều khi", "đôi khi")
    BANNED_OPTIONS = ("tất cả các ý trên", "tất cả đáp án trên", "không có ý nào đúng")
    DIFFICULTY_TO_BLOOM = {
        "nhan_biet": "remember",
        "thong_hieu": "understand",
        "van_dung": "apply",
    }

    def __init__(self):
        super().__init__()
        self.dual_reviewers = DualVerificationService()

    async def run(
        self,
        *,
        questions: list[dict[str, Any]],
        answer_key: list[dict[str, Any]],
        curriculum: list[Any] | None = None,
        specification: list[dict[str, Any]] | None = None,
        grade: int = 8,
    ) -> dict[str, Any]:
        """Return a teacher-facing verification report for all questions."""
        answers = {item.get("question_id"): item for item in answer_key}
        specs = {item.get("question_id"): item for item in (specification or [])}
        reports = []
        provider_error = None
        for question in questions:
            report = self._base_report(question)
            answer = answers.get(question.get("id"), {})
            report["checks"]["grounding"] = self._grounding_check(question, curriculum)
            report["checks"]["structural_quality"] = self._structural_quality(question)

            provider_error = await self._apply_ai_checks(
                report, question, answer, provider_error, specs.get(question.get("id")), grade
            )

            self._finalize_report(report)
            reports.append(report)

        counts = Counter(report["status"] for report in reports)
        scored_reports = [report["verification_score"] for report in reports if report["verification_score"] is not None]
        overall_score = round(sum(scored_reports) / len(scored_reports), 1) if scored_reports else None
        result = {
            "overall_score": overall_score,
            "overall_status": self._overall_status(overall_score, counts),
            "summary": {
                "total_questions": len(reports),
                "auto_approved": counts["approved"],
                "needs_review": counts["needs_review"],
                "auto_rejected": 0,
                "not_verified": counts["not_verified"],
            },
            "question_reports": reports,
            "action_required": [
                action
                for report in reports
                if report["status"] == "needs_review"
                for action in [{
                    "priority": "high" if any(issue["severity"] in {"critical", "major"} for issue in report["issues"]) else "medium",
                    "question_id": report["question_id"],
                    "message": report["issues"][0]["description"],
                    "fix": report["issues"][0]["suggestion"],
                }]
            ],
        }
        reviewer_summary = self.reviewer_summary(reports)
        if reviewer_summary:
            result["reviewer_summary"] = reviewer_summary
        return result

    async def run_with_progress(
        self,
        *,
        questions: list[dict[str, Any]],
        answer_key: list[dict[str, Any]],
        curriculum: list[Any] | None = None,
        specification: list[dict[str, Any]] | None = None,
        grade: int = 8,
    ) -> AsyncGenerator[tuple[str, dict[str, Any] | None], None]:
        """Async generator that yields (progress_message, None) for each question
        and finally (None, result_dict) when done.

        Use this in SSE streams so the client receives keep-alive events while
        verification is in progress.
        """
        answers = {item.get("question_id"): item for item in answer_key}
        specs = {item.get("question_id"): item for item in (specification or [])}
        reports = []
        provider_error = None
        total = len(questions)
        for idx, question in enumerate(questions, 1):
            report = self._base_report(question)
            answer = answers.get(question.get("id"), {})
            report["checks"]["grounding"] = self._grounding_check(question, curriculum)
            report["checks"]["structural_quality"] = self._structural_quality(question)

            provider_error = await self._apply_ai_checks(
                report, question, answer, provider_error, specs.get(question.get("id")), grade
            )

            self._finalize_report(report)
            reports.append(report)

            # Yield progress so the SSE connection stays alive
            q_label = question.get("number") or question.get("id") or idx
            yield (f"Đã kiểm chứng {idx}/{total} câu (câu {q_label})", None)
            # Let the event loop flush the SSE buffer
            await asyncio.sleep(0)

        counts = Counter(report["status"] for report in reports)
        scored_reports = [report["verification_score"] for report in reports if report["verification_score"] is not None]
        overall_score = round(sum(scored_reports) / len(scored_reports), 1) if scored_reports else None
        result = {
            "overall_score": overall_score,
            "overall_status": self._overall_status(overall_score, counts),
            "summary": {
                "total_questions": len(reports),
                "auto_approved": counts["approved"],
                "needs_review": counts["needs_review"],
                "auto_rejected": 0,
                "not_verified": counts["not_verified"],
            },
            "question_reports": reports,
            "action_required": [
                action
                for report in reports
                if report["status"] == "needs_review"
                for action in [{
                    "priority": "high" if any(issue["severity"] in {"critical", "major"} for issue in report["issues"]) else "medium",
                    "question_id": report["question_id"],
                    "message": report["issues"][0]["description"],
                    "fix": report["issues"][0]["suggestion"],
                }]
            ],
        }
        reviewer_summary = self.reviewer_summary(reports)
        if reviewer_summary:
            result["reviewer_summary"] = reviewer_summary
        yield (None, result)

    async def _apply_ai_checks(self, report, question, answer, provider_error, spec=None, grade=8):
        if not provider_fallback_allowed():
            return await self._apply_dual_reviewer_checks(
                report, question, answer, provider_error, spec, grade
            )

        if not self.has_ai:
            reason = "No AI provider configured"
            report["checks"]["solve_compare"] = self._skipped(reason)
            report["checks"]["ai_quality_review"] = self._skipped(reason)
            return provider_error

        if provider_error:
            reason = "AI verification unavailable after an earlier provider failure"
            report["checks"]["solve_compare"] = self._skipped(reason)
            report["checks"]["ai_quality_review"] = self._skipped(reason)
            report["verification_error"] = provider_error
            return provider_error

        try:
            report["checks"]["solve_compare"] = await self._run_ai_check(
                self._solve_and_compare, question, answer, spec, grade
            )
            report["checks"].update(
                await self._run_ai_check(self._ai_quality_review, question, answer, spec, grade)
            )
            return None
        except Exception as exc:
            error_msg = (
                f"AI verification error: {type(exc).__name__}: {str(exc)[:200]}"
            )
            logger.warning(error_msg)
            report["checks"]["solve_compare"] = self._skipped(error_msg)
            report["checks"]["ai_quality_review"] = self._skipped(error_msg)
            report["verification_error"] = error_msg
            return error_msg

    async def _apply_dual_reviewer_checks(
        self, report, question, answer, provider_error, spec=None, grade=8
    ):
        mode = self._active_review_mode()
        required_reviewers = self._required_reviewer_labels()
        if provider_error:
            reason = "Required semantic verification unavailable after an earlier reviewer failure"
            report["checks"]["solve_compare"] = self._skipped(reason)
            report["checks"]["ai_quality_review"] = self._skipped(reason)
            report["checks"]["dual_review"] = {
                "status": "unavailable",
                "mode": mode,
                "required_reviewers": required_reviewers,
            }
            report["verification_error"] = provider_error
            return provider_error

        if not self.dual_reviewers.available():
            reason = f"Cần cấu hình đủ {' và '.join(required_reviewers)} để kiểm định."
            report["checks"]["solve_compare"] = self._skipped(reason)
            report["checks"]["ai_quality_review"] = self._skipped(reason)
            report["checks"]["dual_review"] = {
                "status": "unavailable",
                "mode": mode,
                "required_reviewers": required_reviewers,
            }
            report["verification_error"] = reason
            return reason

        try:
            prompt = self._combined_review_prompt(question, answer, spec, grade)
            reviews = await self.dual_reviewers.review(
                prompt,
                response_model=IndependentVerificationOutput,
            )
            self._apply_reviewer_consensus(report, question, answer, reviews)
            return None
        except MandatoryReviewUnavailable as exc:
            reason = str(exc)
            report["checks"]["solve_compare"] = self._skipped(reason)
            report["checks"]["ai_quality_review"] = self._skipped(reason)
            report["checks"]["dual_review"] = {
                "status": "unavailable",
                "mode": mode,
                "required_reviewers": required_reviewers,
            }
            report["verification_error"] = reason
            return reason

    def _active_review_mode(self):
        return getattr(self.dual_reviewers, "mode", "dual")

    def _required_reviewer_labels(self):
        labels = getattr(self.dual_reviewers, "required_reviewer_labels", None)
        if callable(labels):
            return labels()
        if self._active_review_mode() == "deepseek_only":
            return ["DeepSeek V4 Pro"]
        return ["DeepSeek V4 Pro", "Gemini 3.7 Flash"]

    def _combined_review_prompt(self, question, answer, spec=None, grade=8):
        plan = build_generation_plan(spec, grade=grade).as_prompt_dict() if spec else None
        return f"""Bạn là giám khảo độc lập cho câu hỏi KHTN THCS. Không tin đáp án gốc.
Hãy tự giải trước, sau đó kiểm định chất lượng. Chỉ trả về một JSON đúng schema.
Câu hỏi: {json.dumps(self._question_payload(question), ensure_ascii=False)}
Đáp án/lời giải gốc cần đối chiếu: {json.dumps(self._answer_payload(answer), ensure_ascii=False)}
Mức độ được gán: {question.get('difficulty')}; lớp: {grade}.
Kế hoạch kiến thức và nguồn kiểm soát: {json.dumps(plan, ensure_ascii=False)}

Quy tắc solve: short_answer chỉ đặt đáp án cuối cùng trong your_answer; essay phải
trả lời đầy đủ; true_false phải trả đủ statement_answers. Mọi lập luận đặt trong reasoning.
Quy tắc quality: kiểm tra đúng lớp và nguồn, đáp án, tính duy nhất, nhiễu, lời giải
khoa học, dữ liệu/bảng/hình cần thiết và mức độ nhận thức.
{self._review_contract()}

JSON gồm đúng hai object `solve` và `quality`. Bắt buộc điền đủ mọi trường theo
JSON Schema được cung cấp, không thêm trường ngoài schema."""

    def _apply_reviewer_consensus(self, report, question, answer, reviews):
        normalized = {}
        for key, review in reviews.items():
            payload = review["result"]
            solve = self._normalize_solve(question, answer, payload["solve"])
            quality = dict(payload["quality"])
            if question.get("type") != "multiple_choice":
                # This flag concerns competing MCQ options, not several true
                # statements or equivalent ways to phrase an open response.
                quality["single_correct_answer"] = True
            normalized[key] = {
                **{name: review[name] for name in ("label", "provider", "model")},
                "solve": solve,
                "quality": quality,
            }

        if len(normalized) == 1:
            self._apply_single_reviewer_result(report, normalized)
            return

        first, second = normalized.values()
        answer_agreement = self._reviewer_answers_agree(question, first["solve"], second["solve"])
        material_fields = (
            "is_valid",
            "source_grounded",
            "objective_copied",
            "answer_correct",
            "single_correct_answer",
            "explanation_scientific",
            "required_context_present",
        )
        field_agreement = {
            field: first["quality"].get(field) == second["quality"].get(field)
            for field in material_fields
        }
        material_disagreement = not answer_agreement or not all(field_agreement.values())
        difficulty_agreement = (
            first["quality"].get("assessed_difficulty")
            == second["quality"].get("assessed_difficulty")
        )

        compact_reviewers = {}
        for key, item in normalized.items():
            compact_reviewers[key] = {
                "label": item["label"],
                "provider": item["provider"],
                "model": item["model"],
                "solve_status": item["solve"]["status"],
                "answer": item["solve"]["ai_answer"],
                "confidence": item["solve"]["confidence"],
                "is_valid": item["quality"].get("is_valid"),
                "answer_correct": item["quality"].get("answer_correct"),
                "assessed_difficulty": item["quality"].get("assessed_difficulty"),
                "issues_found": item["quality"].get("issues_found", []),
            }

        report["checks"]["dual_review"] = {
            "status": "disagreement" if material_disagreement else "consensus",
            "mode": "dual_mandatory",
            "material_disagreement": material_disagreement,
            "answer_agreement": answer_agreement,
            "difficulty_agreement": difficulty_agreement,
            "quality_field_agreement": field_agreement,
            "reviewers": compact_reviewers,
        }

        solves = [item["solve"] for item in normalized.values()]
        report["checks"]["solve_compare"] = {
            "status": "match" if all(item["status"] == "match" for item in solves) and answer_agreement else "mismatch",
            "ai_answer": {key: item["solve"]["ai_answer"] for key, item in normalized.items()},
            "original_answer": solves[0]["original_answer"],
            "confidence": min(item["confidence"] for item in solves),
            "reasoning": "Đã đối chiếu hai lời giải độc lập.",
            "multiple_correct": any(item["multiple_correct"] for item in solves),
            "detected_issues": list(dict.fromkeys(
                issue for item in solves for issue in item.get("detected_issues", [])
            )),
        }

        qualities = [item["quality"] for item in normalized.values()]
        issues = [
            {**issue, "description": f"[{item['label']}] {issue['description']}"}
            for item in normalized.values()
            for issue in item["quality"].get("issues_found", [])
        ]
        if material_disagreement:
            issues.append({
                "severity": "major",
                "type": "reviewer_disagreement",
                "description": "DeepSeek và Gemini bất đồng ở một tiêu chí kiểm định trọng yếu.",
                "suggestion": "Tạo lại câu hỏi rồi kiểm định lại bằng đủ hai model.",
            })
        combined_quality = {
            "status": "completed",
            "is_valid": all(item.get("is_valid", False) for item in qualities),
            "knowledge_target": " | ".join(dict.fromkeys(item.get("knowledge_target", "") for item in qualities)),
            "source_grounded": all(item.get("source_grounded", False) for item in qualities),
            "objective_copied": any(item.get("objective_copied", False) for item in qualities),
            "answer_correct": all(item.get("answer_correct", False) for item in qualities),
            "single_correct_answer": all(item.get("single_correct_answer", False) for item in qualities),
            "explanation_scientific": all(item.get("explanation_scientific", False) for item in qualities),
            "required_context_present": all(item.get("required_context_present", False) for item in qualities),
            "issues_found": issues,
            "distractors": [],
            "overall_distractor_quality": "poor" if any(item.get("overall_distractor_quality") == "poor" for item in qualities) else "acceptable",
            "statements": [],
            "assessed_difficulty": qualities[0].get("assessed_difficulty", question.get("difficulty")),
            "difficulty_matches": difficulty_agreement and all(item.get("difficulty_matches", False) for item in qualities),
            "reasoning": "Kết quả tổng hợp bảo thủ từ hai giám khảo độc lập.",
        }
        report["checks"]["ai_quality_review"] = combined_quality

    def _apply_single_reviewer_result(self, report, normalized):
        key, item = next(iter(normalized.items()))
        solve = item["solve"]
        quality = item["quality"]
        compact_reviewer = {
            "label": item["label"],
            "provider": item["provider"],
            "model": item["model"],
            "solve_status": solve["status"],
            "answer": solve["ai_answer"],
            "confidence": solve["confidence"],
            "is_valid": quality.get("is_valid"),
            "answer_correct": quality.get("answer_correct"),
            "assessed_difficulty": quality.get("assessed_difficulty"),
            "issues_found": quality.get("issues_found", []),
        }
        report["checks"]["dual_review"] = {
            "status": "reviewed",
            "mode": "deepseek_only",
            "material_disagreement": False,
            "reviewers": {key: compact_reviewer},
        }
        report["checks"]["solve_compare"] = {
            "status": solve["status"],
            "ai_answer": {key: solve["ai_answer"]},
            "original_answer": solve["original_answer"],
            "confidence": solve["confidence"],
            "reasoning": f"Đã đối chiếu lời giải độc lập từ {item['label']}.",
            "multiple_correct": solve["multiple_correct"],
            "detected_issues": solve.get("detected_issues", []),
        }
        issues = [
            {**issue, "description": f"[{item['label']}] {issue['description']}"}
            for issue in quality.get("issues_found", [])
        ]
        report["checks"]["ai_quality_review"] = {
            "status": "completed",
            **quality,
            "issues_found": issues,
            "reasoning": f"Kết quả kiểm định độc lập từ {item['label']}.",
        }

    def _normalize_solve(self, question, answer, result):
        original = self._original_answer(question, answer)
        matched = self._answers_match(question, answer, original, result)
        multiple_correct = question.get("type") == "multiple_choice" and bool(result.get("multiple_correct"))
        return {
            "status": "match" if matched and not multiple_correct else "mismatch",
            "ai_answer": result.get("statement_answers", []) if question.get("type") == "true_false" else result.get("your_answer"),
            "original_answer": original,
            "confidence": self._score(result.get("confidence"), default=0.5),
            "multiple_correct": multiple_correct,
            "detected_issues": result.get("detected_issues", []),
        }

    def _reviewer_answers_agree(self, question, first, second):
        if question.get("type") == "essay":
            return first["status"] == second["status"]
        if question.get("type") == "true_false":
            def as_map(value):
                return {
                    item.get("statement_id"): item.get("is_true")
                    for item in value or []
                    if isinstance(item, dict)
                }
            return as_map(first["ai_answer"]) == as_map(second["ai_answer"])
        canonical = self._canonical_short_answer if question.get("type") == "short_answer" else self._normalise
        return canonical(first["ai_answer"]) == canonical(second["ai_answer"])

    @staticmethod
    def reviewer_summary(reports):
        dual = [
            (item.get("checks") or {}).get("dual_review")
            for item in reports
            if (item.get("checks") or {}).get("dual_review")
        ]
        if not dual:
            return None
        modes = [item.get("mode") for item in dual if item.get("mode")]
        mode = modes[0] if modes else "dual_mandatory"
        reviewers = []
        for review in dual:
            for item in (review.get("reviewers") or {}).values():
                identity = {
                    "label": item.get("label"),
                    "provider": item.get("provider"),
                    "model": item.get("model"),
                }
                if identity not in reviewers:
                    reviewers.append(identity)
        return {
            "mode": mode,
            "reviewers": reviewers,
            "consensus_questions": sum(item.get("status") == "consensus" for item in dual),
            "reviewed_questions": sum(item.get("status") in {"consensus", "disagreement", "reviewed"} for item in dual),
            "disagreement_questions": sum(item.get("status") == "disagreement" for item in dual),
            "unavailable_questions": sum(item.get("status") == "unavailable" for item in dual),
            "total_questions": len(dual),
        }

    def _base_report(self, question):
        return {
            "question_id": question.get("id"),
            "question_number": question.get("number"),
            "type": question.get("type"),
            "verification_score": 100.0,
            "status": "approved",
            "checks": {},
            "issues": [],
            "suggestions": [],
        }

    async def _run_ai_check(self, check, question, answer, *extra):
        """Bound synchronous SDK calls so one provider outage cannot block FastAPI."""
        return await asyncio.wait_for(
            asyncio.to_thread(check, question, answer, *extra),
            timeout=provider_operation_timeout_seconds(),
        )

    def _solve_and_compare(self, question, answer, spec=None, grade=8):
        plan = build_generation_plan(spec, grade=grade).as_prompt_dict() if spec else None
        prompt = f"""Bạn là giáo viên KHTN THCS. Tự giải câu hỏi sau, KHÔNG tin đáp án gốc.
Đọc chính xác từng từ; chỉ với multiple_choice, nếu có hơn một phương án đúng phải nêu rõ.
{self._review_contract()}
	Câu hỏi: {json.dumps(self._question_payload(question), ensure_ascii=False)}
	Kế hoạch kiến thức và nguồn kiểm soát: {json.dumps(plan, ensure_ascii=False)}
		Nếu type là short_answer, trường your_answer CHỈ chứa đáp án cuối cùng dạng thuật ngữ,
		số kèm đơn vị hoặc cụm từ 1-5 từ; không viết câu giải thích trong your_answer. Đặt mọi
		lập luận vào reasoning.
		Nếu type là essay, trường your_answer phải là một bài trả lời độc lập đầy đủ, bao phủ
		các luận điểm khoa học chính; không rút gọn thành nhãn hoặc cụm vài từ. reasoning nêu
		cách đối chiếu các luận điểm và bằng chứng khoa học.
		Trả về JSON duy nhất: {{"your_answer":"A hoặc đáp án ngắn", "statement_answers":[{{"statement_id":"...","is_true":true}}], "multiple_correct":false, "confidence":0.0, "reasoning":"...", "detected_issues":["..."]}}"""
        result = self.llm.generate_verification_json(
            prompt,
            response_model=SolveVerificationOutput,
        )
        return {
            **self._normalize_solve(question, answer, result),
            "reasoning": result.get("reasoning", ""),
        }

    def _ai_quality_review(self, question, answer, spec=None, grade=8):
        plan = build_generation_plan(spec, grade=grade).as_prompt_dict() if spec else None
        prompt = f"""Bạn phản biện chất lượng câu hỏi KHTN lớp 6-9. Trả về JSON duy nhất.
Câu hỏi: {json.dumps(self._question_payload(question), ensure_ascii=False)}
Đáp án và lời giải cần kiểm tra: {json.dumps(self._answer_payload(answer), ensure_ascii=False)}
Mức độ được gán: {question.get("difficulty")}; yêu cầu cần đạt: {question.get("metadata", {}).get("achievement", "")}.
Kế hoạch kiến thức và ngữ cảnh nguồn: {json.dumps(plan, ensure_ascii=False)}
Hãy tự xác định tri thức được hỏi và tự giải. Kiểm tra riêng: đúng lớp; bám nguồn/phạm vi;
không sao chép yêu cầu cần đạt làm đáp án; intent và mức độ khớp; đáp án thực sự đúng;
không có đáp án đúng thứ hai; nhiễu hợp lý nhưng sai; lời giải nêu WHY bằng khoa học;
không thiếu bảng/hình/dữ liệu/thí nghiệm được nhắc tới.
{self._review_contract()}
Schema: {{"is_valid":true,"knowledge_target":"...","source_grounded":true,"objective_copied":false,"answer_correct":true,"single_correct_answer":true,"explanation_scientific":true,"required_context_present":true,"issues_found":[{{"severity":"critical|major|medium","description":"...","suggestion":"..."}}],"distractors":[{{"option":"A","plausibility":0.0,"reason":"..."}}],"overall_distractor_quality":"good|acceptable|poor","statements":[{{"id":"...","is_clear":true,"ambiguity_type":"none|vague_term|double_negative|multiple_interpretations","suggestion":"..."}}],"assessed_difficulty":"nhan_biet|thong_hieu|van_dung","difficulty_matches":true,"reasoning":"..."}}"""
        result = self.llm.generate_verification_json(
            prompt,
            response_model=QualityVerificationOutput,
        )
        return {"ai_quality_review": {"status": "completed", **result}}

    def _structural_quality(self, question):
        issues = []
        if question.get("type") == "multiple_choice":
            for label, option in (question.get("options") or {}).items():
                if str(option).strip().lower() in self.BANNED_OPTIONS:
                    issues.append(self._issue("major", "banned_option", f"Phương án {label} không được dùng: {option}", "Thay bằng phương án nhiễu dựa trên ngộ nhận thường gặp."))
        if question.get("type") == "true_false":
            for statement in question.get("statements") or []:
                content = str(statement.get("content", "")).lower()
                term = next((term for term in self.AMBIGUOUS_TERMS if term in content), None)
                if term:
                    issues.append(self._issue("medium", "ambiguous_statement", f"Phát biểu {statement.get('id')} dùng từ mơ hồ '{term}'.", "Viết lại bằng điều kiện hoặc phạm vi định lượng rõ ràng."))
                if content.count("không") >= 2:
                    issues.append(self._issue("medium", "double_negative", f"Phát biểu {statement.get('id')} có phủ định kép.", "Viết lại ở dạng khẳng định hoặc chỉ dùng một phủ định."))
        return {"status": "pass" if not issues else "warning", "issues": issues}

    def _grounding_check(self, question, curriculum):
        if not curriculum:
            return self._skipped("No curriculum supplied")
        metadata = question.get("metadata") or {}
        topic = self._normalise(metadata.get("topic"))
        achievement = self._normalise(metadata.get("achievement"))
        if not topic or not achievement:
            return self._skipped("Question scope metadata incomplete")
        matches = []
        for item in curriculum:
            data = item.model_dump() if hasattr(item, "model_dump") else item
            item_topic = self._normalise(data.get("topic"))
            if topic and (topic in item_topic or item_topic in topic):
                matches.append({"topic": data.get("topic"), "achievements": data.get("achievements", [])})
        objective_match = bool(achievement) and any(
            any(
                normalized_objective
                and (
                    achievement in normalized_objective
                    or normalized_objective in achievement
                )
                for objective in (item["achievements"] or [])
                if (normalized_objective := self._normalise(objective))
            )
            for item in matches
        )
        grounded = bool(matches) and objective_match
        return {"status": "grounded" if grounded else "needs_review", "grounded": grounded, "grounding_score": 1.0 if objective_match else (0.7 if matches else 0.0), "matched_topics": matches, "matched_objectives": [item["topic"] for item in matches] if objective_match else []}

    def _finalize_report(self, report):
        checks = report["checks"]
        verification_unavailable = checks.get("solve_compare", {}).get("status") == "skipped"
        issues = list(checks.get("structural_quality", {}).get("issues", []))
        solve = checks.get("solve_compare", {})
        if solve.get("status") == "mismatch":
            issues.append(self._issue("major" if solve.get("multiple_correct") else "medium", "answer_mismatch", "Đáp án AI tự giải khác đáp án gốc.", "Giáo viên kiểm tra lại đáp án và cách diễn đạt câu hỏi."))
        grounding = checks.get("grounding", {})
        if grounding.get("status") == "needs_review":
            issues.append(self._issue("medium", "curriculum_grounding", "Không khớp rõ ràng với chủ đề/yêu cầu cần đạt đã chọn.", "Kiểm tra metadata hoặc phạm vi kiến thức của câu hỏi."))
        quality = checks.get("ai_quality_review", {})
        if quality.get("status") == "completed":
            for item in quality.get("issues_found", []):
                if not isinstance(item, dict):
                    continue
                issues.append(self._issue(
                    item.get("severity", "medium"),
                    item.get("type", "ai_quality_issue"),
                    item.get("description", "AI phát hiện vấn đề chất lượng câu hỏi."),
                    item.get("suggestion", "Giáo viên kiểm tra lại câu hỏi."),
                ))
            deterministic_quality_flags = (
                (not quality.get("source_grounded", True), "source_not_grounded", "Câu hỏi không bám ngữ cảnh nguồn/phạm vi đã chọn.", "Chỉ dùng tri thức được hỗ trợ bởi nguồn và đúng lớp."),
                (quality.get("objective_copied", False), "learning_objective_copy", "Yêu cầu cần đạt bị dùng như nội dung đáp án.", "Tách mục tiêu năng lực khỏi tri thức khoa học được hỏi."),
                (not quality.get("answer_correct", True), "answer_incorrect", "Đáp án gốc không đúng theo lời giải độc lập.", "Giải lại câu hỏi rồi sửa đáp án."),
                (report.get("type") == "multiple_choice" and not quality.get("single_correct_answer", True), "multiple_correct_answers", "Câu một lựa chọn có thể có nhiều đáp án đúng.", "Sửa stem hoặc phương án để chỉ còn một đáp án đúng."),
                (not quality.get("explanation_scientific", True), "explanation_not_scientific", "Lời giải không nêu lý do khoa học cụ thể.", "Nêu cơ chế, quan hệ, dữ liệu hoặc phép tính chứng minh đáp án."),
                (not quality.get("required_context_present", True), "required_context_missing", "Thiếu dữ liệu/bảng/hình/ngữ cảnh cần để trả lời.", "Đưa đầy đủ dữ liệu được tham chiếu vào payload câu hỏi."),
            )
            existing_descriptions = {item.get("description") for item in issues}
            for failed, issue_type, description, suggestion in deterministic_quality_flags:
                if failed and description not in existing_descriptions:
                    issues.append(self._issue("major", issue_type, description, suggestion))
        if quality.get("status") == "completed" and not quality.get("difficulty_matches", True):
            issues.append(self._issue("medium", "difficulty_mismatch", "Mức độ nhận thức AI đánh giá khác mức độ được gán.", "Điều chỉnh mức độ hoặc tăng/giảm yêu cầu tư duy của câu hỏi."))
        report["issues"] = issues
        report["suggestions"] = list(dict.fromkeys(issue.get("suggestion", "") for issue in issues if issue.get("suggestion")))
        if verification_unavailable:
            # Structural checks still matter, but a missing model must never look
            # like a successful semantic/answer verification.
            report["verification_score"] = None
            report["status"] = "needs_review" if issues else "not_verified"
            if not issues:
                report["suggestions"].append("Cấu hình AI provider để thực hiện kiểm chứng nội dung.")
            return
        penalties = {"critical": 35, "major": 20, "medium": 8}
        report["verification_score"] = max(0.0, 100.0 - sum(penalties.get(issue.get("severity"), 8) for issue in issues))
        report["status"] = "needs_review" if issues else "approved"

    @staticmethod
    def _skipped(reason):
        return {"status": "skipped", "reason": reason}

    @staticmethod
    def _issue(severity, issue_type, description, suggestion):
        return {"severity": severity, "type": issue_type, "description": description, "suggestion": suggestion}

    @staticmethod
    def _score(value, default):
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    def _question_payload(self, question):
        payload = {key: question.get(key) for key in ("type", "content", "options", "sub_questions", "rich_content") if question.get(key) is not None}
        if payload.get("rich_content"):
            # Text reviewers receive captions, never megabytes of base64. A
            # question requiring visual interpretation still needs teacher review.
            payload["rich_content"] = [{k: v for k, v in block.items() if k != "src"} if block.get("type") == "image" else block for block in payload["rich_content"]]
        if question.get("statements") is not None:
            payload["statements"] = [
                {key: statement.get(key) for key in ("id", "content")}
                for statement in question["statements"]
            ]
        return payload

    @staticmethod
    def _answer_payload(answer):
        # Server-added curriculum quotations describe scope, not the answer.
        return {
            key: answer[key]
            for key in ("type", "correct_answer", "explanation", "option_explanations", "model_answer", "key_points", "answers")
            if answer.get(key) is not None
        }

    @staticmethod
    def _review_contract():
        return """Quy ước theo type:
- multiple_correct và single_correct_answer chỉ xét các phương án của multiple_choice.
  true_false có nhiều ý đúng là bình thường: đánh giá từng id độc lập, trả đủ bốn
  statement_answers; đặt multiple_correct=false và single_correct_answer=true.
  Với short_answer/essay, các cách diễn đạt tương đương không phải nhiều đáp án sai quy cách.
- objective_copied=true CHỈ khi phương án/đáp án/lời giải dùng câu mục tiêu sư phạm
  như 'Nêu được...', 'Sử dụng được...' THAY CHO tri thức khoa học. Việc câu hỏi kiểm tra
  đúng mục tiêu, lặp thuật ngữ khoa học hoặc kế hoạch nguồn chứa achievement KHÔNG phải
  sao chép mục tiêu. Khi gắn cờ phải chỉ rõ đoạn đáp án bị lỗi trong issues_found.
- Lời giải ngắn có công thức, phép thế số và kết luận vẫn là lời giải khoa học;
  không đánh giá bằng số ký tự. Thông báo thiếu lời giải không phải nội dung khoa học.
- Đánh giá mức độ theo thao tác thực tế: nhận biết là nhớ/nhận ra trực tiếp; thông hiểu
  là diễn giải quan hệ; vận dụng là dùng kiến thức để xử lý tình huống. Không mặc định
  mọi câu có số đều là vận dụng, cũng không chấp nhận câu chỉ hỏi định nghĩa được gán vận dụng.
- Giữ reasoning ngắn gọn, nêu phép tính/kết luận và bằng chứng lỗi cần thiết; không
  chép lại đề, schema hay thảo luận cách định dạng JSON."""

    @staticmethod
    def _original_answer(question, answer):
        if question.get("type") == "true_false":
            return answer.get("answers") or [{"statement_id": s.get("id"), "is_true": s.get("is_true")} for s in question.get("statements", [])]
        return answer.get("correct_answer") or answer.get("model_answer") or question.get("correct_answer")

    def _answers_match(self, question, answer, original, result):
        question_type = question.get("type")
        solved = result.get("your_answer")
        if question_type == "short_answer":
            return self._canonical_short_answer(original) == self._canonical_short_answer(
                solved
            )
        if question_type == "essay":
            # Some providers correctly put the complete worked essay in
            # `reasoning` while keeping `your_answer` as a short conclusion.
            # Both fields are part of the independent solve, so compare the
            # official key points against their combined scientific content.
            essay_solution = " ".join(
                str(value or "")
                for value in (solved, result.get("reasoning"))
                if value
            )
            return self._essay_answer_matches(answer, original, essay_solution)
        if question_type != "true_false":
            return self._normalise(original) == self._normalise(solved)
        expected_items = original or []
        actual_items = result.get("statement_answers") or []
        ids = [item.get("id") for item in question.get("statements") or []]
        expected = {item.get("statement_id"): item.get("is_true") for item in expected_items}
        actual = {item.get("statement_id"): item.get("is_true") for item in actual_items}
        return (
            len(ids) == 4 and len(set(ids)) == 4 and all(ids)
            and len(expected_items) == len(actual_items) == 4
            and set(expected) == set(actual) == set(ids)
            and all(type(value) is bool for value in [*expected.values(), *actual.values()])
            and expected == actual
        )

    @classmethod
    def _canonical_short_answer(cls, value):
        text = cls._normalise(value)
        number_words = {
            "không": "0",
            "một": "1",
            "hai": "2",
            "ba": "3",
            "bốn": "4",
            "tư": "4",
            "năm": "5",
            "sáu": "6",
            "bảy": "7",
            "tám": "8",
            "chín": "9",
            "mười": "10",
        }
        for word, number in number_words.items():
            text = re.sub(rf"\b{word}\b", number, text)
        return text.strip(" .,!?:;")

    @classmethod
    def _essay_answer_matches(cls, answer, original, solved):
        solved_tokens = cls._meaningful_tokens(solved)
        if not solved_tokens:
            return False

        key_points = [
            point for point in (answer.get("key_points") or []) if cls._normalise(point)
        ]
        if not key_points:
            return cls._normalise(original) == cls._normalise(solved)

        matched_points = 0
        for point in key_points:
            point_tokens = cls._meaningful_tokens(point)
            if not point_tokens:
                continue
            coverage = len(point_tokens & solved_tokens) / len(point_tokens)
            if coverage >= 0.5:
                matched_points += 1
        return matched_points / len(key_points) >= 0.6

    @classmethod
    def _meaningful_tokens(cls, value):
        text = cls._normalise(value)
        replacements = {
            "oxygen": "oxy",
            "o₂": "oxy",
            "o2": "oxy",
            "carbon dioxide": "co2",
            "cacbon dioxide": "co2",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        stop_words = {
            "và",
            "là",
            "của",
            "cho",
            "được",
            "với",
            "để",
            "trong",
            "có",
            "các",
            "một",
            "những",
            "thì",
            "mà",
        }
        return {
            token
            for token in re.findall(r"\w+", text, flags=re.UNICODE)
            if token not in stop_words
        }

    @staticmethod
    def _normalise(value):
        return " ".join(str(value or "").lower().split())

    @staticmethod
    def _overall_status(score, counts):
        if counts["not_verified"]:
            return "not_verified"
        if counts["needs_review"]:
            return "passed_with_warnings"
        if score is None:
            return "not_verified"
        return "passed" if score >= 85 else "needs_review"

    @staticmethod
    def hard_failure_reasons(
        report: dict[str, Any], *, require_independent: bool = False
    ) -> dict[str, list[str]]:
        """Return only failures that must block persistence/regenerate."""
        failures: dict[str, list[str]] = {}
        for item in report.get("question_reports") or []:
            reasons = []
            solve = (item.get("checks") or {}).get("solve_compare") or {}
            if require_independent and (
                solve.get("status") == "skipped" or item.get("status") == "not_verified"
            ):
                reasons.append("semantic_review_unavailable")
            if solve.get("status") == "mismatch" or solve.get("multiple_correct"):
                reasons.append("independent_answer_mismatch")
            reasons.extend(
                issue.get("type", "semantic_review_failure")
                for issue in item.get("issues") or []
                if issue.get("severity") in {"critical", "major"}
            )
            if reasons:
                failures[str(item.get("question_id"))] = list(dict.fromkeys(reasons))
        return failures
