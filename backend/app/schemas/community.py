import json
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.schemas.bank_question import BankQuestionCreate

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class CommunityQuestion(BankQuestionCreate):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    content: str = Field(min_length=1, max_length=20000)
    subject: str = Field(default="Khoa học tự nhiên", min_length=1, max_length=100)
    topic: str | None = Field(default=None, max_length=200)
    tags: list[Annotated[str, StringConstraints(min_length=1, max_length=50)]] = Field(default_factory=list, max_length=20)
    source: None = None

    @model_validator(mode="after")
    def bound_payload(self):
        if len(json.dumps(self.model_dump(), ensure_ascii=False)) > 40000:
            raise ValueError("Nội dung câu hỏi quá dài (tối đa 40.000 ký tự)")
        return self


class TopicCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    question: CommunityQuestion


class TopicFromBank(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title
    question_id: int = Field(ge=1)


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: Body
    parent_id: int | None = Field(default=None, ge=1)
