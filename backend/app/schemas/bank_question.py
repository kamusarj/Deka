from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.exam import Difficulty, QuestionType
from app.schemas.rich_content import RichBlock


class BankQuestionCreate(BaseModel):
    rich_content: list[RichBlock] | None = Field(default=None, max_length=32)
    content: str = Field(..., min_length=1)
    type: QuestionType
    difficulty: Difficulty = "thong_hieu"
    topic: str | None = None
    grade: int | None = Field(default=None, ge=6, le=9)
    subject: str = "Khoa học tự nhiên"
    tags: list[str] = Field(default_factory=list)
    options: Any | None = None
    statements: Any | None = None
    sub_questions: Any | None = None
    answer: dict[str, Any] | None = None
    source: dict[str, Any] | None = None


class BankQuestionResponse(BaseModel):
    rich_content: list[dict[str, Any]] | None = None
    content_metadata: dict[str, Any] | None = None
    duplicate_findings: list[dict[str, Any]] = Field(default_factory=list)
    can_publish: bool = False
    id: int
    content: str
    type: str
    difficulty: str
    topic: str | None = None
    grade: int | None = None
    subject: str
    tags: list[str] = Field(default_factory=list)
    options: Any | None = None
    statements: Any | None = None
    sub_questions: Any | None = None
    answer: dict[str, Any] | None = None
    source: dict[str, Any] | None = None
    usage_count: int = 0
    rating: float | None = None
    created_at: datetime | None = None


class SaveFromExamRequest(BaseModel):
    exam_id: int
    question_ids: list[str] = Field(
        default_factory=list,
        description="Để trống = lấy tất cả câu đã 'accepted' trong đề.",
    )
    tags: list[str] = Field(default_factory=list)


class SaveFromExamResponse(BaseModel):
    saved: list[BankQuestionResponse]
    count: int
    message: str = "Đã lưu câu hỏi vào ngân hàng."
    duplicate_findings: list[dict[str, Any]] = Field(default_factory=list)


class BankQuestionDeleteResponse(BaseModel):
    id: int
    deleted: bool = True
    message: str = "Đã xóa câu hỏi khỏi ngân hàng."
