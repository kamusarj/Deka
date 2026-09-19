from app.agents.base import BaseAgent


class ValidatorAgent(BaseAgent):
    """Rule-based checks from docs/06-Validation-Checklist.md."""

    async def run(self, *, questions, answer_key, rubric, summary, request):
        checks = [
            self._check_total_score(questions, request.total_score),
            self._check_score_increment(questions),
            self._check_question_count(questions, summary["total_questions"]),
            self._check_difficulty_ratio(summary, request.difficulty_ratio.model_dump()),
            self._check_answer_key(questions, answer_key),
            self._check_rubric(questions, rubric),
            self._check_no_duplicates(questions),
            self._check_no_hallucination(questions),
            self._check_curriculum_scope(questions),
            self._check_calculation_requirement(
                questions,
                getattr(request, "calculation_requirement", None),
                auto_distribute_scores=bool(
                    getattr(request, "auto_distribute_scores", False)
                ),
            ),
        ]
        errors = [check["message"] for check in checks if not check["passed"] and check["severity"] in {"critical", "major"}]
        warnings = [check["message"] for check in checks if not check["passed"] and check["severity"] == "medium"]
        passed = not errors
        return {
            "passed": passed,
            "score": max(0, 100 - (len(errors) * 20) - (len(warnings) * 5)),
            "checks": checks,
            "warnings": warnings,
            "errors": errors,
        }

    def _check_total_score(self, questions, expected):
        actual = round(sum(question["score"] for question in questions), 2)
        return {
            "name": "CHECK_TOTAL_SCORE",
            "category": "format",
            "severity": "critical",
            "passed": actual == expected,
            "status": "pass" if actual == expected else "fail",
            "expected": expected,
            "actual": actual,
            "message": f"Tổng điểm: {actual}/{expected}",
        }

    def _check_question_count(self, questions, expected):
        actual = len(questions)
        return {
            "name": "CHECK_QUESTION_COUNT",
            "category": "format",
            "severity": "major",
            "passed": actual == expected,
            "status": "pass" if actual == expected else "fail",
            "expected": expected,
            "actual": actual,
            "message": f"Số câu hỏi: {actual}/{expected}",
        }

    def _check_score_increment(self, questions):
        invalid_ids = []
        for question in questions:
            score = float(question.get("score", 0))
            parts = question.get("statements") or question.get("sub_questions") or []
            part_count = max(1, len(parts))
            invalid_part_scores = [
                item.get("id")
                for item in question.get("sub_questions") or []
                if float(item.get("score", 0)) < 0.25
                or abs(float(item.get("score", 0)) * 4 - round(float(item.get("score", 0)) * 4)) > 1e-6
            ]
            sub_score_total = sum(
                float(item.get("score", 0))
                for item in question.get("sub_questions") or []
            )
            if (
                score < part_count * 0.25
                or abs(score * 4 - round(score * 4)) > 1e-6
                or invalid_part_scores
                or (
                    question.get("sub_questions")
                    and abs(sub_score_total - score) > 1e-6
                )
            ):
                invalid_ids.append(question.get("id"))
        passed = not invalid_ids
        return {
            "name": "CHECK_SCORE_INCREMENT",
            "category": "format",
            "severity": "critical",
            "passed": passed,
            "status": "pass" if passed else "fail",
            "expected": "Mỗi câu từ 0,25 điểm và là bội số của 0,25",
            "actual": {"invalid_question_ids": invalid_ids},
            "message": (
                "Điểm mọi câu hợp lệ theo nấc 0,25"
                if passed
                else f"Câu có điểm không hợp lệ: {invalid_ids}"
            ),
        }

    def _check_difficulty_ratio(self, summary, expected):
        actual = {
            "nhan_biet": summary["nhan_biet"]["percentage"],
            "thong_hieu": summary["thong_hieu"]["percentage"],
            "van_dung": summary["van_dung"]["percentage"],
        }
        passed = all(abs(actual[key] - expected[key]) <= 10 for key in expected)
        return {
            "name": "CHECK_DIFFICULTY_RATIO",
            "category": "format",
            "severity": "major",
            "passed": passed,
            "status": "pass" if passed else "fail",
            "expected": expected,
            "actual": actual,
            "message": f"Phân bổ mức độ: {actual}",
        }

    def _check_answer_key(self, questions, answer_key):
        expected_ids = {question["id"] for question in questions}
        actual_ids = {answer["question_id"] for answer in answer_key}
        return {
            "name": "CHECK_ANSWER_KEY_COMPLETE",
            "category": "content",
            "severity": "critical",
            "passed": expected_ids <= actual_ids,
            "status": "pass" if expected_ids <= actual_ids else "fail",
            "expected": len(expected_ids),
            "actual": len(actual_ids),
            "message": "Đáp án đầy đủ cho tất cả câu hỏi",
        }

    def _check_rubric(self, questions, rubric):
        essay_ids = {question["id"] for question in questions if question["type"] == "essay"}
        rubric_ids = {item["question_id"] for item in rubric}
        return {
            "name": "CHECK_RUBRIC_COMPLETE",
            "category": "rubric",
            "severity": "major",
            "passed": essay_ids <= rubric_ids,
            "status": "pass" if essay_ids <= rubric_ids else "fail",
            "expected": len(essay_ids),
            "actual": len(rubric_ids),
            "message": "Rubric đầy đủ cho câu tự luận",
        }

    def _check_no_duplicates(self, questions):
        seen = set()
        duplicates = []
        for question in questions:
            content = (question.get("content") or "").strip().lower()
            if content and content in seen:
                duplicates.append(question["id"])
            seen.add(content)
        return {
            "name": "CHECK_NO_DUPLICATES",
            "category": "content",
            "severity": "medium",
            "passed": not duplicates,
            "status": "pass" if not duplicates else "warn",
            "expected": [],
            "actual": duplicates,
            "message": "Không có câu hỏi trùng lặp" if not duplicates else f"Câu hỏi trùng: {duplicates}",
        }

    def _check_no_hallucination(self, questions):
        allowed_sources = {"local_json", "uploaded_file", "question_bank", "rag_retrieval", "manual_input"}
        missing = []
        invalid = []
        for question in questions:
            source = question.get("source") or question.get("metadata", {}).get("source")
            if not source:
                missing.append(question["id"])
                continue
            if source.get("source_type") not in allowed_sources:
                invalid.append(question["id"])
        passed = not missing and not invalid
        return {
            "name": "CHECK_NO_HALLUCINATION",
            "category": "content",
            "severity": "critical",
            "passed": passed,
            "status": "pass" if passed else "fail",
            "expected": "valid source metadata on every question",
            "actual": {"missing": missing, "invalid": invalid},
            "message": (
                "Tất cả câu hỏi có nguồn dữ liệu hợp lệ"
                if passed
                else f"Câu hỏi thiếu/không hợp lệ nguồn: missing={missing}, invalid={invalid}"
            ),
        }

    def _check_calculation_requirement(
        self,
        questions,
        requirement,
        *,
        auto_distribute_scores=False,
    ):
        if requirement is None:
            expected_count = 0
            expected_score = None
            expected_difficulties = []
        elif isinstance(requirement, dict):
            expected_count = int(requirement.get("count", 0) or 0)
            expected_score = requirement.get("score_per_question")
            expected_difficulties = list(requirement.get("difficulties") or [])
        else:
            expected_count = int(getattr(requirement, "count", 0) or 0)
            expected_score = getattr(requirement, "score_per_question", None)
            expected_difficulties = list(
                getattr(requirement, "difficulties", None) or []
            )

        marked = [
            question
            for question in questions
            if bool((question.get("metadata") or {}).get("is_calculation"))
        ]
        ids = [question.get("id") for question in marked]
        invalid_type_ids = [
            question.get("id")
            for question in marked
            if question.get("type") != "short_answer"
        ]
        invalid_score_ids = []
        if expected_count and auto_distribute_scores:
            invalid_score_ids = [
                question.get("id")
                for question in marked
                if float(question.get("score", 0)) < 0.25
                or abs(
                    float(question.get("score", 0)) * 4
                    - round(float(question.get("score", 0)) * 4)
                ) > 1e-6
            ]
        elif expected_count and expected_score is not None:
            invalid_score_ids = [
                question.get("id")
                for question in marked
                if abs(float(question.get("score", 0)) - float(expected_score)) > 1e-6
            ]
        unverified_ids = [
            question.get("id")
            for question in marked
            if not bool((question.get("metadata") or {}).get("calculation_verified"))
        ]
        invalid_difficulty_ids = []
        if expected_difficulties:
            invalid_difficulty_ids = [
                question.get("id")
                for index, question in enumerate(marked)
                if index >= len(expected_difficulties)
                or question.get("difficulty") != expected_difficulties[index]
            ]
        passed = (
            len(marked) == expected_count
            and not invalid_type_ids
            and not invalid_score_ids
            and not unverified_ids
            and not invalid_difficulty_ids
        )
        return {
            "name": "CHECK_CALCULATION_REQUIREMENT",
            "category": "content",
            "severity": "critical",
            "passed": passed,
            "status": "pass" if passed else "fail",
            "expected": {
                "count": expected_count,
                "score_per_question": expected_score if expected_count else None,
                "auto_distribute_scores": auto_distribute_scores,
                "difficulties": expected_difficulties,
            },
            "actual": {
                "count": len(marked),
                "question_ids": ids,
                "invalid_type_ids": invalid_type_ids,
                "invalid_score_ids": invalid_score_ids,
                "invalid_difficulty_ids": invalid_difficulty_ids,
                "unverified_ids": unverified_ids,
            },
            "message": (
                f"Đủ {expected_count} câu tính toán bắt buộc"
                if passed
                else "Số lượng, dạng câu, điểm hoặc mức độ câu tính toán không đúng cấu hình"
            ),
        }

    def _check_curriculum_scope(self, questions):
        """Guard against questions that cannot be traced to their specification."""
        missing_scope = []
        guard_replaced = []
        for question in questions:
            metadata = question.get("metadata") or {}
            if not metadata.get("topic") or not metadata.get("achievement"):
                missing_scope.append(question.get("id"))
            # `replaced` = scope guard đã loại output AI và thay bằng câu
            # deterministic; `failed` giữ lại cho dữ liệu cũ. Cả hai đều cần
            # giáo viên rà lại thay vì lặng lẽ vượt kiểm tra.
            if (metadata.get("scope_guard") or {}).get("status") in {"failed", "replaced"}:
                guard_replaced.append(question.get("id"))
        passed = not missing_scope and not guard_replaced
        severity = "major" if guard_replaced else "medium"
        return {
            "name": "CHECK_CURRICULUM_SCOPE",
            "category": "content",
            "severity": severity,
            "passed": passed,
            "status": "pass" if passed else ("fail" if guard_replaced else "warn"),
            "expected": "topic, achievement và scope guard hợp lệ cho mọi câu hỏi",
            "actual": {"missing_scope": missing_scope, "guard_replaced": guard_replaced},
            "message": (
                "Tất cả câu hỏi nằm trong phạm vi bản đặc tả"
                if passed
                else f"Câu hỏi thiếu/lệch phạm vi: {missing_scope + guard_replaced}"
            ),
        }
