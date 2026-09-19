"""Allowlisted teacher-edit payloads; provenance and domain fields are immutable."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.rich_content import RichBlock


class EditModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EditedStatement(EditModel):
    id: str
    content: str = Field(min_length=1, max_length=10000)
    is_true: bool
    explanation: str = Field(min_length=1, max_length=10000)


class EditedSubQuestion(EditModel):
    id: str
    content: str = Field(min_length=1, max_length=10000)
    score: float = Field(gt=0, multiple_of=0.25, allow_inf_nan=False)


class EditedRubricLevel(EditModel):
    score: float = Field(ge=0, multiple_of=0.25, allow_inf_nan=False)
    description: str = Field(min_length=1, max_length=10000)
    criteria: str = Field(default="", max_length=10000)


class EditedRubricCriterion(EditModel):
    id: str
    name: str = Field(min_length=1, max_length=1000)
    max_score: float = Field(gt=0, multiple_of=0.25, allow_inf_nan=False)
    levels: list[EditedRubricLevel] = Field(min_length=1, max_length=30)


class QuestionEditRequest(EditModel):
    bank_question_id: int | None = Field(default=None, ge=1)
    rich_content: list[RichBlock] | None = Field(default=None, max_length=32)
    version_id: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=20000)
    options: dict[Literal["A", "B", "C", "D"], str] | None = None
    correct_answer: str | None = Field(default=None, max_length=10000)
    explanation: str = Field(default="", max_length=20000)
    option_explanations: dict[Literal["A", "B", "C", "D"], str] | None = None
    statements: list[EditedStatement] | None = Field(default=None, min_length=4, max_length=4)
    sub_questions: list[EditedSubQuestion] | None = Field(default=None, max_length=20)
    model_answer: str | None = Field(default=None, max_length=20000)
    rubric_criteria: list[EditedRubricCriterion] | None = Field(default=None, max_length=30)
