from datetime import datetime
from typing import Any
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocumentScope = Literal["private", "school", "system"]
DocumentLibrary = Literal["all", "mine", "school", "system", "pending"]


class DocumentSharingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: DocumentScope
    version_id: int = Field(ge=1)


class DocumentReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=1000)
    version_id: int = Field(ge=1)


class DocumentResponse(BaseModel):
    """Bản ghi tài liệu kèm preview text (không trả toàn bộ extracted_text)."""

    id: int
    owner_user_id: int | None = None
    school_id: int | None = None
    sharing_scope: DocumentScope = "private"
    sharing_status: Literal["none", "pending", "approved", "rejected"] = "none"
    review_note: str = ""
    reviewed_at: datetime | None = None
    version_id: int = 1
    can_manage: bool = False
    can_share_school: bool = False
    can_review: bool = False
    filename: str
    file_type: str
    size: int
    status: str
    grade: int | None = None
    text_preview: str = ""
    text_length: int = 0
    parsed_data: dict[str, Any] | None = None
    created_at: datetime | None = None


class DocumentDetailResponse(DocumentResponse):
    """Chi tiết tài liệu kèm toàn bộ extracted_text."""

    extracted_text: str = ""


class DocumentDeleteResponse(BaseModel):
    id: int
    deleted: bool = True
    message: str = "Đã xóa tài liệu."
