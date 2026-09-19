from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    role: str
    scope_label: str
    exams: int = 0
    questions: int = 0
    documents: int = 0
    bank_questions: int = 0
    schools: int | None = None
    users: int | None = None
    teachers: int | None = None
    recent_exam_ids: list[int] = Field(default_factory=list)
