from app.agents.base import BaseAgent
from app.services.exam.generation_planning import parse_learning_objective


class SpecificationAgent(BaseAgent):
    """Create a specification row for every planned question."""

    async def run(self, *, matrix, question_plan, curriculum):
        specification = []
        lesson_occurrences: dict[int, int] = {}
        bloom = {
            "nhan_biet": "remember",
            "thong_hieu": "understand",
            "van_dung": "apply",
        }
        verbs = {
            "nhan_biet": "Nêu được",
            "thong_hieu": "Giải thích được",
            "van_dung": "Vận dụng được",
        }

        for number, item in enumerate(question_plan, start=1):
            lesson = curriculum[item["lesson_index"]]
            occurrence = lesson_occurrences.get(item["lesson_index"], 0)
            lesson_occurrences[item["lesson_index"]] = occurrence + 1
            achievement = item.get("achievement") or (
                lesson.achievements[occurrence % len(lesson.achievements)]
                if lesson.achievements
                else f"{verbs[item['difficulty']]} kiến thức về {lesson.topic}"
            )
            parsed_objective = parse_learning_objective(achievement)
            knowledge_targets = parsed_objective["knowledge_objects"]
            specification.append(
                {
                    "question_number": number,
                    "topic": lesson.topic,
                    "lesson": lesson.topic,
                    "knowledge_unit": knowledge_targets[0] if knowledge_targets else lesson.topic,
                    "achievement": achievement,
                    "difficulty": item["difficulty"],
                    "question_type": item["type"],
                    "score": item["score"],
                    "bloom_level": bloom[item["difficulty"]],
                    "content_hint": (
                        f"Câu trả lời ngắn bắt buộc tính toán về {lesson.topic}; "
                        "cho đủ dữ kiện, yêu cầu một giá trị số kèm đơn vị."
                        if item.get("requires_calculation")
                        else self._hint(item["type"], item["difficulty"], lesson.topic)
                    ),
                    "question_id": item["question_id"],
                    "requires_calculation": bool(item.get("requires_calculation")),
                }
            )

        return specification

    def _hint(self, question_type: str, difficulty: str, topic: str) -> str:
        labels = {
            "multiple_choice": "Câu trắc nghiệm 4 lựa chọn",
            "true_false": "Câu đúng/sai gồm 4 phát biểu",
            "short_answer": "Câu trả lời ngắn 1-5 từ",
            "essay": "Câu tự luận có rubric",
        }
        levels = {
            "nhan_biet": "kiểm tra nhận biết khái niệm",
            "thong_hieu": "kiểm tra khả năng giải thích",
            "van_dung": "kiểm tra khả năng vận dụng",
        }
        return f"{labels[question_type]} về {topic}, {levels[difficulty]}."
