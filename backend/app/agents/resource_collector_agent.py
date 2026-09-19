from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.agents.base import BaseAgent
from app.services.curriculum import get_topics_by_exam_scope, load_curriculum


class ResourceCollectorAgent(BaseAgent):
    """Agent 0: load controlled Phase 1 resources from local curriculum JSON."""

    async def run(self, *, grade: int, subject: str, exam_type: str):
        topics = self._topics_for(grade, exam_type)
        source_name = f"khtn_grade_{grade}.json"
        data_sources = [
            {
                "source_type": "local_json",
                "source_name": source_name,
                "source_page": None,
                "confidence_score": 1.0,
                "loaded_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        return {
            "id": f"res_{uuid4().hex[:12]}",
            "grade": grade,
            "subject": subject,
            "exam_type": exam_type,
            "collected_at": datetime.now(timezone.utc).isoformat(),
            "data_sources": data_sources,
            "raw_data": {
                "curriculum_file": source_name,
                "topics": topics,
            },
            "curriculum_suggestions": topics,
            "sample_questions": self._sample_questions(topics),
            "sample_matrix": {
                "format": "Công văn 7991",
                "difficulty_ratio": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
                "total_score": 10,
            },
            "sample_specification": {
                "fields": ["Câu", "Chủ đề", "Nội dung kiến thức", "Yêu cầu cần đạt", "Mức độ", "Dạng", "Điểm"]
            },
            "difficulty_guidelines": {
                "nhan_biet": "Nhớ lại khái niệm, sự kiện, thuật ngữ cơ bản.",
                "thong_hieu": "Giải thích, so sánh, phân loại, nêu ví dụ.",
                "van_dung": "Áp dụng kiến thức vào tình huống thực tiễn hoặc bài toán mới.",
            },
            "question_type_examples": {
                "multiple_choice": "4 lựa chọn A, B, C, D; chỉ có 1 đáp án đúng.",
                "true_false": "4 phát biểu, mỗi phát biểu được xác định đúng/sai.",
                "short_answer": "Trả lời ngắn bằng từ khóa hoặc cụm 1-5 từ.",
                "essay": "Câu tự luận kèm thang điểm/rubric.",
            },
        }

    def _topics_for(self, grade: int, exam_type: str):
        curriculum = load_curriculum(grade)
        exam_scope = self._resolve_exam_scope(curriculum, exam_type)
        scoped_topics = get_topics_by_exam_scope(grade, exam_scope["exam_type"])
        return [self._topic_suggestion(topic) for topic in scoped_topics]

    def _resolve_exam_scope(self, curriculum: dict, exam_type: str):
        for scope in curriculum.get("exam_scopes", []):
            if exam_type == scope.get("exam_type") or exam_type == scope.get("display_name"):
                return scope
        raise HTTPException(
            status_code=400,
            detail=f"Loại kiểm tra không tồn tại trong chương trình: {exam_type}",
        )

    def _topic_suggestion(self, topic: dict):
        objectives = topic.get("learning_objectives", [])
        return {
            "topic": topic["name"],
            "topic_id": topic["id"],
            "periods": topic.get("periods", 1),
            "knowledge_units": [
                keyword
                for objective in objectives
                for keyword in objective.get("keywords", [])[:2]
            ][:6],
            "achievements": [objective["text"] for objective in objectives],
            "sample_questions_count": max(3, len(objectives) * 2),
            "source": {
                "source_type": "local_json",
                "source_name": "Local curriculum seed data",
                "source_page": None,
                "confidence_score": 1.0,
            },
        }

    def _sample_questions(self, topics):
        by_topic = {}
        for index, topic in enumerate(topics, start=1):
            key = f"topic_{index}"
            by_topic[key] = {
                "nhan_biet": [
                    {
                        "content": f"Nêu một khái niệm cơ bản thuộc {topic['topic']}.",
                        "difficulty": "nhan_biet",
                        "source": "Bộ dữ liệu MVP",
                    }
                ],
                "thong_hieu": [
                    {
                        "content": f"Giải thích vai trò của một kiến thức trọng tâm trong {topic['topic']}.",
                        "difficulty": "thong_hieu",
                        "source": "Bộ dữ liệu MVP",
                    }
                ],
                "van_dung": [
                    {
                        "content": f"Vận dụng kiến thức về {topic['topic']} để giải thích một tình huống thực tiễn.",
                        "difficulty": "van_dung",
                        "source": "Bộ dữ liệu MVP",
                    }
                ],
            }
        return {
            "by_topic": by_topic,
            "total_questions": sum(topic["sample_questions_count"] for topic in topics),
            "by_difficulty": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
        }
