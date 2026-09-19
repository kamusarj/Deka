from app.agents.base import BaseAgent
from app.schemas.exam import MatrixRequest
from app.services.exam.formula_registry import local_calculation_candidates
from fastapi import HTTPException
import re
import unicodedata

DIFFICULTIES = ("nhan_biet", "thong_hieu", "van_dung")
MINIMUM_SCORE_UNITS = {
    "multiple_choice": 1,
    "true_false": 4,
    "short_answer": 1,
    "essay": 2,
}


class MatrixAgent(BaseAgent):
    """Rule-based MVP matrix generator following the documented schema."""

    async def run(self, request: MatrixRequest):
        question_plan = self._build_question_plan(request)
        lessons = self._weighted_lessons(request)
        rows = []
        # `lessons` được sort theo số tiết (thứ tự hiển thị), còn question plan
        # tham chiếu chủ đề qua `lesson_index` — vị trí GỐC trong curriculum.
        # Map theo index gốc để câu hỏi luôn rơi đúng dòng chủ đề của nó.
        row_by_curriculum_index: dict[int, dict] = {}
        lesson_by_curriculum_index = {
            lesson["index"]: lesson for lesson in lessons
        }
        non_calculation_lessons = [
            lesson for lesson in lessons if self._non_calculation_achievements(lesson)
        ]
        non_calculation_occurrences: dict[int, int] = {}
        if request.calculation_requirement.count and not non_calculation_lessons:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Phạm vi kiến thức chỉ có yêu cầu tính toán nên không thể tạo "
                    "đúng số câu đã chọn. Hãy bổ sung yêu cầu cần đạt không định lượng."
                ),
            )

        for index, lesson in enumerate(lessons, start=1):
            row = {
                "id": f"matrix_{index}",
                "topic_id": f"topic_{index}",
                "topic_name": lesson["topic"],
                "lesson_id": f"lesson_{index}",
                "lesson_name": lesson["topic"],
                "nhan_biet": self._empty_cell(),
                "thong_hieu": self._empty_cell(),
                "van_dung": self._empty_cell(),
                "total_score": 0,
            }
            rows.append(row)
            row_by_curriculum_index[lesson["index"]] = row

        for number, item in enumerate(question_plan, start=1):
            lesson = (
                lesson_by_curriculum_index[item["lesson_index"]]
                if "lesson_index" in item
                else non_calculation_lessons[(number - 1) % len(non_calculation_lessons)]
                if request.calculation_requirement.count
                else lessons[(number - 1) % len(lessons)]
            )
            if request.calculation_requirement.count and not item.get(
                "requires_calculation"
            ):
                choices = self._non_calculation_achievements(lesson)
                occurrence = non_calculation_occurrences.get(lesson["index"], 0)
                non_calculation_occurrences[lesson["index"]] = occurrence + 1
                item["achievement"] = choices[occurrence % len(choices)]
            row = row_by_curriculum_index[lesson["index"]]
            cell = row[item["difficulty"]]
            question_id = f"q_{number}"
            cell["count"] += 1
            cell["score"] = round(cell["score"] + item["score"], 2)
            cell["question_type"] = item["type"]
            cell["question_ids"].append(question_id)
            row["total_score"] = round(row["total_score"] + item["score"], 2)
            item["question_id"] = question_id
            item["lesson_index"] = lesson["index"]

        summary = self._summary(rows, request, question_plan)
        return {"matrix": rows, "summary": summary, "question_plan": question_plan}

    def _weighted_lessons(self, request: MatrixRequest):
        sorted_lessons = sorted(
            enumerate(request.curriculum),
            key=lambda item: (-item[1].periods, item[0]),
        )
        return [
            {
                "index": original_index,
                "topic": lesson.topic,
                "periods": lesson.periods,
                "achievements": lesson.achievements,
            }
            for original_index, lesson in sorted_lessons
        ]

    @classmethod
    def _non_calculation_achievements(cls, lesson: dict) -> list[str]:
        return [
            achievement
            for achievement in lesson.get("achievements", [])
            if not cls._is_explicit_calculation_objective(achievement)
        ]

    @staticmethod
    def _is_explicit_calculation_objective(achievement: object) -> bool:
        text = unicodedata.normalize("NFD", str(achievement or "").lower())
        text = "".join(
            character
            for character in text
            if unicodedata.category(character) != "Mn"
        ).replace("đ", "d")
        text = re.sub(r"\s+", " ", text).strip()
        return (
            text.startswith("tinh duoc ")
            or " cong thuc tinh" in f" {text}"
            or " thay so" in f" {text}"
        )

    def _build_question_plan(self, request: MatrixRequest):
        types = request.question_types
        plan = []
        for question_type in ("multiple_choice", "true_false", "short_answer", "essay"):
            config = getattr(types, question_type)
            if not config.enabled:
                continue
            for _ in range(config.count):
                plan.append({"type": question_type, "score": config.score_per_question})

        calculation_count = request.calculation_requirement.count
        if calculation_count:
            calculation_slots = [
                item for item in plan if item["type"] == "short_answer"
            ][:calculation_count]
            candidates = local_calculation_candidates(
                grade=request.grade,
                curriculum=request.curriculum,
            )
            if not candidates:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Phạm vi kiến thức đã chọn không có yêu cầu cần đạt hỗ trợ "
                        "phép tính được kiểm chứng. Hãy chọn thêm nội dung định lượng "
                        "phù hợp với khối lớp."
                    ),
                )
            for index, item in enumerate(calculation_slots):
                candidate = candidates[index % len(candidates)]
                item.update(
                    {
                        "score": request.calculation_requirement.score_per_question,
                        "requires_calculation": True,
                        "lesson_index": candidate["lesson_index"],
                        "achievement": candidate["achievement"],
                        "objective_id": candidate["objective_id"],
                        "allowed_formula_ids": candidate["formula_ids"],
                    }
                )
                if request.calculation_requirement.difficulties:
                    item["difficulty"] = request.calculation_requirement.difficulties[
                        index
                    ]

        targets = {
            "nhan_biet": request.total_score * request.difficulty_ratio.nhan_biet / 100,
            "thong_hieu": request.total_score * request.difficulty_ratio.thong_hieu / 100,
            "van_dung": request.total_score * request.difficulty_ratio.van_dung / 100,
        }
        scores = {key: 0.0 for key in DIFFICULTIES}
        preferred = {
            "multiple_choice": ("nhan_biet", "thong_hieu", "van_dung"),
            "true_false": ("thong_hieu", "van_dung", "nhan_biet"),
            "short_answer": ("nhan_biet", "thong_hieu", "van_dung"),
            "essay": ("van_dung", "thong_hieu", "nhan_biet"),
        }

        allocation_order = sorted(
            (index for index, item in enumerate(plan) if "difficulty" not in item),
            key=lambda index: (-plan[index]["score"], preferred[plan[index]["type"]]),
        )
        if request.auto_distribute_scores:
            target_score_units = self._target_score_units(request)
            total_weight = sum(max(float(item["score"]), 0.01) for item in plan)
            allocation_units = {
                index: max(
                    1,
                    round(max(float(item["score"]), 0.01) / total_weight * 10_000),
                )
                for index, item in enumerate(plan)
            }
            remaining = {
                key: int(round(getattr(request.difficulty_ratio, key) * 100))
                for key in DIFFICULTIES
            }
            assigned_score_units = {
                key: sum(
                    MINIMUM_SCORE_UNITS[item["type"]]
                    for item in plan
                    if item.get("difficulty") == key
                )
                for key in DIFFICULTIES
            }
            over_capacity = [
                key
                for key in DIFFICULTIES
                if assigned_score_units[key] > target_score_units[key]
            ]
            if over_capacity:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Số câu tính toán cố định ở một mức độ vượt quỹ điểm "
                        "tối thiểu 0,25 điểm/câu. Hãy giảm số câu ở mức độ đó "
                        "hoặc tăng tỷ lệ điểm tương ứng."
                    ),
                )
        else:
            allocation_units = {
                index: int(round(item["score"] * 4))
                for index, item in enumerate(plan)
            }
            remaining = {
                key: int(round(value * 4)) for key, value in targets.items()
            }

        # Mức độ giáo viên chọn cho câu tính toán là ràng buộc cố định. Trừ
        # trước phần điểm đó khỏi chỉ tiêu để các câu còn lại bù quanh tỷ lệ
        # mức độ toàn đề thay vì ghi đè lựa chọn sau khi đã phân bổ.
        for index, item in enumerate(plan):
            difficulty = item.get("difficulty")
            if difficulty is None:
                continue
            score_units = allocation_units[index]
            scores[difficulty] = round(scores[difficulty] + item["score"], 2)
            remaining[difficulty] -= score_units

        for index in allocation_order:
            item = plan[index]
            score_units = allocation_units[index]
            item_preferred = (
                ("van_dung", "thong_hieu", "nhan_biet")
                if item.get("requires_calculation")
                else preferred[item["type"]]
            )
            if request.auto_distribute_scores:
                minimum_units = MINIMUM_SCORE_UNITS[item["type"]]
                item_preferred = tuple(
                    key
                    for key in item_preferred
                    if getattr(request.difficulty_ratio, key) > 0
                    and assigned_score_units[key] + minimum_units
                    <= target_score_units[key]
                )
                if not item_preferred:
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Không thể phân mức độ mà vẫn bảo đảm mỗi câu tối thiểu "
                            "0,25 điểm. Hãy giảm số câu hoặc điều chỉnh tỷ lệ mức độ."
                        ),
                    )
            under_target = [
                key for key in item_preferred if remaining[key] >= score_units
            ]
            if under_target:
                # Còn hạn mức: chọn mức độ phù hợp nhất với dạng câu (ưu tiên sư phạm).
                difficulty = min(
                    under_target,
                    key=lambda key: (
                        item_preferred.index(key),
                        abs(remaining[key] - score_units),
                        -remaining[key],
                    ),
                )
            else:
                # Buộc phải vượt hạn mức: chọn mức ít lệch nhất để giữ đúng tỷ lệ.
                difficulty = min(
                    item_preferred,
                    key=lambda key: (
                        abs(remaining[key] - score_units),
                        -remaining[key],
                        item_preferred.index(key),
                    ),
                )
            item["difficulty"] = difficulty
            if request.auto_distribute_scores:
                assigned_score_units[difficulty] += minimum_units
            scores[difficulty] = round(scores[difficulty] + item["score"], 2)
            remaining[difficulty] -= score_units

        if request.auto_distribute_scores:
            self._ensure_positive_ratio_levels(
                plan,
                request,
                preferred,
                target_score_units,
            )
            self._auto_distribute_scores(plan, request)
        elif request.calculation_requirement.difficulties:
            actual_percentages = {
                key: round(value / request.total_score * 100)
                for key, value in scores.items()
            }
            incompatible = [
                key
                for key in DIFFICULTIES
                if abs(
                    actual_percentages[key]
                    - getattr(request.difficulty_ratio, key)
                )
                > 10
            ]
            if incompatible:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Mức độ đã chọn cho từng câu tính toán không thể cân đối "
                        "với tỷ lệ mức độ toàn đề. Hãy điều chỉnh mức độ câu tính "
                        "toán hoặc tỷ lệ Nhận biết/Thông hiểu/Vận dụng."
                    ),
                )

        return plan

    @staticmethod
    def _ensure_positive_ratio_levels(
        plan,
        request: MatrixRequest,
        preferred,
        target_score_units,
    ):
        counts = {
            key: sum(item.get("difficulty") == key for item in plan)
            for key in DIFFICULTIES
        }
        used_units = {
            key: sum(
                MINIMUM_SCORE_UNITS[item["type"]]
                for item in plan
                if item.get("difficulty") == key
            )
            for key in DIFFICULTIES
        }
        for missing in DIFFICULTIES:
            if getattr(request.difficulty_ratio, missing) <= 0 or counts[missing] > 0:
                continue
            movable = [
                item
                for item in plan
                if not item.get("requires_calculation")
                and counts[item["difficulty"]] > 1
                and used_units[missing] + MINIMUM_SCORE_UNITS[item["type"]]
                <= target_score_units[missing]
            ]
            if not movable:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Không đủ câu hỏi để mỗi mức độ có tỷ lệ lớn hơn 0% "
                        "nhận ít nhất một câu. Hãy tăng số câu hoặc đặt tỷ lệ "
                        "của mức không có câu về 0%."
                    ),
                )
            item = min(
                movable,
                key=lambda candidate: (
                    preferred[candidate["type"]].index(missing),
                    -counts[candidate["difficulty"]],
                ),
            )
            previous = item["difficulty"]
            item_units = MINIMUM_SCORE_UNITS[item["type"]]
            counts[previous] -= 1
            used_units[previous] -= item_units
            item["difficulty"] = missing
            counts[missing] += 1
            used_units[missing] += item_units

    @staticmethod
    def _target_score_units(request: MatrixRequest) -> dict[str, int]:
        """Round requested ratios to exact 0.25-point budgets.

        Largest remainders keep the declared total exact while producing the
        closest feasible difficulty split in quarter-point units.
        """
        total_units = int(round(request.total_score * 4))
        raw = {
            key: total_units * getattr(request.difficulty_ratio, key) / 100
            for key in DIFFICULTIES
        }
        targets = {key: int(raw[key]) for key in DIFFICULTIES}
        remainder = total_units - sum(targets.values())
        order = sorted(
            DIFFICULTIES,
            key=lambda key: (-(raw[key] - targets[key]), DIFFICULTIES.index(key)),
        )
        for key in order[:remainder]:
            targets[key] += 1
        for key in DIFFICULTIES:
            if getattr(request.difficulty_ratio, key) <= 0 or targets[key] > 0:
                continue
            donors = [
                donor
                for donor in DIFFICULTIES
                if targets[donor] > (1 if getattr(request.difficulty_ratio, donor) > 0 else 0)
            ]
            if not donors:
                raise HTTPException(
                    status_code=422,
                    detail="Tổng điểm không đủ để cấp tối thiểu 0,25 cho mỗi mức độ có tỷ lệ dương.",
                )
            donor = max(donors, key=lambda candidate: targets[candidate] - raw[candidate])
            targets[donor] -= 1
            targets[key] += 1
        return targets

    @classmethod
    def _auto_distribute_scores(cls, plan, request: MatrixRequest):
        targets = cls._target_score_units(request)
        for difficulty in DIFFICULTIES:
            indexed_items = [
                (index, item)
                for index, item in enumerate(plan)
                if item["difficulty"] == difficulty
            ]
            target_units = targets[difficulty]
            if not indexed_items:
                if target_units:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Mức độ {difficulty} có điểm nhưng chưa có câu hỏi.",
                    )
                continue
            minimum_units = [
                MINIMUM_SCORE_UNITS[item["type"]]
                for _, item in indexed_items
            ]
            required_units = sum(minimum_units)
            if target_units < required_units:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "Tỷ lệ mức độ quá thấp so với số câu hỏi nên không thể "
                        "giữ điểm dương cho mọi câu. Hãy giảm số câu hoặc tăng tỷ lệ."
                    ),
                )

            weights = [max(float(item["score"]), 0.01) for _, item in indexed_items]
            distributable = target_units - required_units
            weight_total = sum(weights)
            raw_extras = [distributable * weight / weight_total for weight in weights]
            extras = [int(value) for value in raw_extras]
            remainder = distributable - sum(extras)
            order = sorted(
                range(len(indexed_items)),
                key=lambda index: (-(raw_extras[index] - extras[index]), index),
            )
            for index in order[:remainder]:
                extras[index] += 1
            for local_index, (_, item) in enumerate(indexed_items):
                item["score"] = (minimum_units[local_index] + extras[local_index]) * 0.25

    def _empty_cell(self):
        return {"count": 0, "score": 0.0, "question_type": None, "question_ids": []}

    def _summary(self, rows, request: MatrixRequest, question_plan):
        totals = {
            key: {
                "total_count": sum(row[key]["count"] for row in rows),
                "total_score": round(sum(row[key]["score"] for row in rows), 2),
            }
            for key in DIFFICULTIES
        }
        total_score = round(sum(item["total_score"] for item in rows), 2)
        for value in totals.values():
            value["percentage"] = round(value["total_score"] / total_score * 100, 2) if total_score else 0
        calculation_items = [
            item for item in question_plan if item.get("requires_calculation")
        ]
        return {
            **totals,
            "total_questions": sum(value["total_count"] for value in totals.values()),
            "total_score": total_score,
            "expected_ratio": request.difficulty_ratio.model_dump(),
            "auto_distribute_scores": request.auto_distribute_scores,
            "score_increment": 0.25 if request.auto_distribute_scores else None,
            "calculation_requirement": {
                "required_count": request.calculation_requirement.count,
                "actual_count": len(calculation_items),
                "score_per_question": request.calculation_requirement.score_per_question,
                "requested_difficulties": list(
                    request.calculation_requirement.difficulties
                ),
                "actual_difficulties": [
                    item["difficulty"] for item in calculation_items
                ],
                "actual_scores": [item["score"] for item in calculation_items],
                "total_score": round(
                    sum(item["score"] for item in calculation_items), 2
                ),
                "question_ids": [item["question_id"] for item in calculation_items],
            },
        }
