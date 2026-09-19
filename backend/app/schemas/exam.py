from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Difficulty = Literal["nhan_biet", "thong_hieu", "van_dung"]
QuestionType = Literal["multiple_choice", "true_false", "short_answer", "essay"]
ReviewStatus = Literal["accepted", "needs_revision", "rejected"]
PublicationStatus = Literal["verified", "draft"]


class ExamBase(BaseModel):
    school: str = Field(..., min_length=2, description="Tên trường")
    grade: int = Field(default=8, ge=6, le=9, description="Khối lớp")
    subject: str = Field(default="Khoa học tự nhiên", description="Môn học")
    exam_type: str = Field(..., description="Loại kiểm tra")
    duration_minutes: int = Field(default=45, ge=15, description="Thời gian làm bài")
    school_year: str = Field(..., min_length=4, description="Năm học")
    total_score: float = Field(default=10.0, description="Tổng điểm")

    @field_validator("subject")
    @classmethod
    def subject_must_be_khtn(cls, value: str):
        if " ".join(value.lower().split()) != "khoa học tự nhiên":
            raise ValueError("Hệ thống hiện chỉ hỗ trợ môn Khoa học tự nhiên THCS")
        return "Khoa học tự nhiên"


class DifficultyRatio(BaseModel):
    nhan_biet: int = Field(default=30, ge=0, le=100, description="Tỷ lệ Nhận biết")
    thong_hieu: int = Field(default=40, ge=0, le=100, description="Tỷ lệ Thông hiểu")
    van_dung: int = Field(default=30, ge=0, le=100, description="Tỷ lệ Vận dụng")

    @model_validator(mode="after")
    def total_must_be_100(self):
        total = self.nhan_biet + self.thong_hieu + self.van_dung
        if total != 100:
            raise ValueError("Tổng tỷ lệ mức độ phải bằng 100%")
        return self


class QuestionTypeConfig(BaseModel):
    enabled: bool = True
    count: int = Field(default=0, ge=0)
    score_per_question: float = Field(default=0.0, ge=0)


class QuestionTypes(BaseModel):
    multiple_choice: QuestionTypeConfig = Field(
        default_factory=lambda: QuestionTypeConfig(count=8, score_per_question=0.25)
    )
    true_false: QuestionTypeConfig = Field(
        default_factory=lambda: QuestionTypeConfig(count=4, score_per_question=1.0)
    )
    short_answer: QuestionTypeConfig = Field(
        default_factory=lambda: QuestionTypeConfig(count=2, score_per_question=0.5)
    )
    essay: QuestionTypeConfig = Field(
        default_factory=lambda: QuestionTypeConfig(count=2, score_per_question=1.5)
    )

    @model_validator(mode="after")
    def must_request_at_least_one_question(self):
        configurations = (
            self.multiple_choice,
            self.true_false,
            self.short_answer,
            self.essay,
        )
        if not any(config.enabled and config.count > 0 for config in configurations):
            raise ValueError("Đề kiểm tra phải có ít nhất một câu hỏi được bật")
        return self


class CalculationRequirement(BaseModel):
    """Required quantitative items inside the short-answer section.

    ``count=0`` is intentionally backward compatible.  When positive, these
    slots use ``score_per_question`` instead of the ordinary short-answer score.
    """

    count: int = Field(default=0, ge=0, description="Số câu tính toán bắt buộc")
    score_per_question: float = Field(
        default=0.5,
        gt=0,
        description="Điểm cho mỗi câu tính toán",
    )
    difficulties: list[Difficulty] = Field(
        default_factory=list,
        description=(
            "Mức độ của từng câu tính toán theo thứ tự. Mảng rỗng giữ hành vi "
            "tự phân bổ cho API cũ."
        ),
    )

    @model_validator(mode="after")
    def difficulties_must_match_count(self):
        if self.difficulties and len(self.difficulties) != self.count:
            raise ValueError(
                "Phải chọn đúng một mức độ cho mỗi câu tính toán"
            )
        return self


class CurriculumItem(BaseModel):
    topic: str = Field(..., min_length=2, description="Chủ đề/Bài học")
    periods: int = Field(default=1, ge=1, description="Số tiết")
    achievements: list[str] = Field(default_factory=list, description="Yêu cầu cần đạt")


class ResourceCollectRequest(BaseModel):
    grade: int = Field(default=8, ge=6, le=9)
    subject: str = Field(default="Khoa học tự nhiên")
    exam_type: str = Field(default="Giữa học kì I")


class ResourceCollectResponse(BaseModel):
    resource_package: dict[str, Any]


class CurriculumAnalyzeRequest(ResourceCollectRequest):
    teaching_plan: str = Field(default="", description="Phân phối chương trình nhập thủ công")


class CurriculumAnalyzeResponse(BaseModel):
    curriculum: list[CurriculumItem]
    total_periods: int
    resource_package: dict[str, Any] | None = None


class DataIngestRequest(ResourceCollectRequest):
    """Step 0: Load controlled data sources for Phase 1."""


class DataIngestResponse(BaseModel):
    data_sources: list[dict[str, Any]]
    raw_data: dict[str, Any]
    resource_package: dict[str, Any]


class DataNormalizeRequest(CurriculumAnalyzeRequest):
    """Step 1: Normalize local/teacher-provided data to the common schema."""


class DataNormalizeResponse(BaseModel):
    normalized_curriculum: dict[str, Any]
    curriculum: list[CurriculumItem]
    total_periods: int
    metadata: dict[str, Any]
    resource_package: dict[str, Any] | None = None


class MatrixRequest(ExamBase):
    curriculum: list[CurriculumItem] = Field(..., min_length=1)
    difficulty_ratio: DifficultyRatio = Field(default_factory=DifficultyRatio)
    question_types: QuestionTypes = Field(default_factory=QuestionTypes)
    calculation_requirement: CalculationRequirement = Field(
        default_factory=CalculationRequirement
    )
    auto_distribute_scores: bool = Field(
        default=False,
        description="Tự chia điểm từng câu theo tỷ lệ mức độ của toàn đề",
    )

    @model_validator(mode="after")
    def calculation_requirement_must_fit_exam(self):
        requirement = self.calculation_requirement
        if self.auto_distribute_scores:
            total_quarter_units = self.total_score * 4
            if abs(total_quarter_units - round(total_quarter_units)) > 1e-6:
                raise ValueError(
                    "Tổng điểm phải là bội số của 0,25 khi tự động phân bổ điểm"
                )
            minimum_units = {"multiple_choice": 1, "true_false": 4, "short_answer": 1, "essay": 2}
            required_units = sum(
                config.count * minimum_units[name]
                for name, config in (
                    ("multiple_choice", self.question_types.multiple_choice),
                    ("true_false", self.question_types.true_false),
                    ("short_answer", self.question_types.short_answer),
                    ("essay", self.question_types.essay),
                )
                if config.enabled
            )
            if required_units > round(total_quarter_units):
                raise ValueError(
                    "Cấu trúc câu hỏi vượt quỹ điểm tối thiểu 0,25 cho mỗi câu hoặc mỗi ý"
                )

        short_answer = self.question_types.short_answer
        available = short_answer.count if short_answer.enabled else 0
        if requirement.count > available:
            raise ValueError(
                "Số câu tính toán bắt buộc không được vượt quá số câu trả lời ngắn"
            )

        if self.auto_distribute_scores:
            return self

        minimum_scores = {"multiple_choice": 0.25, "true_false": 1.0, "short_answer": 0.25, "essay": 0.5}
        configured_scores = [
            (name, config.score_per_question)
            for name, config in (
                ("multiple_choice", self.question_types.multiple_choice),
                ("true_false", self.question_types.true_false),
                ("short_answer", self.question_types.short_answer),
                ("essay", self.question_types.essay),
            )
            if config.enabled and config.count > 0
        ]
        if requirement.count > 0:
            configured_scores.append(("short_answer", requirement.score_per_question))
        if any(
            score < minimum_scores[name]
            or abs(score * 4 - round(score * 4)) > 1e-6
            for name, score in configured_scores
        ):
            raise ValueError(
                "Điểm mỗi câu/mỗi ý phải từ 0,25 và là bội số của 0,25"
            )

        if requirement.count == 0:
            return self

        effective_total = 0.0
        for name in ("multiple_choice", "true_false", "short_answer", "essay"):
            config = getattr(self.question_types, name)
            if config.enabled:
                effective_total += config.count * config.score_per_question
        effective_total += requirement.count * (
            requirement.score_per_question - short_answer.score_per_question
        )
        if abs(effective_total - self.total_score) > 1e-6:
            raise ValueError(
                "Tổng điểm theo cấu hình câu hỏi, kể cả câu tính toán, "
                f"phải bằng {self.total_score:g} (hiện tại {effective_total:g})"
            )
        return self


class MatrixResponse(BaseModel):
    matrix: list[dict[str, Any]]
    summary: dict[str, Any]


class SpecificationRequest(MatrixRequest):
    pass


class SpecificationResponse(BaseModel):
    specification: list[dict[str, Any]]
    matrix: list[dict[str, Any]]
    summary: dict[str, Any]


class FullExamRequest(MatrixRequest):
    variant_count: int = Field(default=4, ge=1, le=30, description="Số mã đề cần tạo")
    allow_provider_fallback: bool = Field(
        default=True,
        description="Cho phép chuyển sang Gemini/DeepSeek nếu OpenAI lỗi",
    )
    use_uploaded_docs: list[int] = Field(
        default_factory=list,
        description="Opt-in RAG: id tài liệu đã upload dùng làm nguồn câu hỏi.",
    )


class FullExamResponse(BaseModel):
    version_id: int = 1
    id: int | None = None
    exam_number: int | None = Field(default=None, ge=1, description="Thứ tự đề hiện có của chủ sở hữu; không phải ID API")
    owner_user_id: int | None = None
    school_id: int | None = None
    publication_status: PublicationStatus = "verified"
    exam_info: dict[str, Any]
    matrix: list[dict[str, Any]]
    summary: dict[str, Any]
    specification: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    answer_key: list[dict[str, Any]]
    rubric: list[dict[str, Any]]
    validation: dict[str, Any]
    resource_package: dict[str, Any] | None = None
    review_status: dict[str, Any] = Field(default_factory=dict)
    variants: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime | None = None


class ExamCreate(ExamBase):
    matrix: list[dict[str, Any]]
    summary: dict[str, Any]
    specification: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    answer_key: list[dict[str, Any]]
    rubric: list[dict[str, Any]]
    validation: dict[str, Any]
    resource_package: dict[str, Any] | None = None
    review_status: dict[str, Any] = Field(default_factory=dict)


class QuestionsGenerateRequest(BaseModel):
    grade: int = Field(default=8, ge=6, le=9)
    specification: list[dict[str, Any]]


class QuestionsGenerateResponse(BaseModel):
    questions: list[dict[str, Any]]
    answer_key: list[dict[str, Any]]
    rubric: list[dict[str, Any]]


class RegenerateQuestionsRequest(BaseModel):
    exam_id: int
    question_ids: list[str] = Field(..., min_length=1)
    reason: str = Field(default="Giáo viên yêu cầu tạo lại")
    allow_provider_fallback: bool = Field(
        default=True,
        description="Cho phép fallback cho client cũ; sửa bản nháp bắt buộc gửi false",
    )


class RegenerateQuestionsResponse(FullExamResponse):
    regenerated_question_ids: list[str]


class QuestionReviewItem(BaseModel):
    question_id: str = Field(..., min_length=1)
    status: ReviewStatus
    comment: str | None = None
    reviewed_by: str = "teacher"


class ReviewQuestionsRequest(BaseModel):
    exam_id: int | None = Field(default=None, description="Dùng cho endpoint /api/questions/review")
    accepted_question_ids: list[str] = Field(default_factory=list)
    needs_revision_question_ids: list[str] = Field(default_factory=list)
    rejected_question_ids: list[str] = Field(default_factory=list)
    reviews: list[QuestionReviewItem] = Field(default_factory=list)


class ValidationRequest(BaseModel):
    questions: list[dict[str, Any]]
    answer_key: list[dict[str, Any]]
    rubric: list[dict[str, Any]]
    summary: dict[str, Any]
    difficulty_ratio: DifficultyRatio = Field(default_factory=DifficultyRatio)
    total_score: float = 10.0
    calculation_requirement: CalculationRequirement = Field(
        default_factory=CalculationRequirement
    )
    auto_distribute_scores: bool = False


class ValidationResponse(BaseModel):
    validation: dict[str, Any]


class GeminiTestRequest(BaseModel):
    prompt: str = Field(default="Viết một câu chào ngắn bằng tiếng Việt.")


class GeminiTestResponse(BaseModel):
    provider: str | None = None
    model: str
    text: str


class ConfirmCurriculumRequest(BaseModel):
    """Step 2: Teacher confirms the scope before generating matrix."""
    school: str = Field(..., min_length=2, description="Tên trường")
    grade: int = Field(..., ge=6, le=9, description="Khối lớp")
    subject: str = Field(default="Khoa học tự nhiên", description="Môn học")
    exam_type: str = Field(..., description="Loại kiểm tra")
    school_year: str = Field(..., description="Năm học")
    duration_minutes: int = Field(default=45, ge=15)
    total_score: float = Field(default=10.0)
    curriculum: list[CurriculumItem] = Field(..., min_length=1)
    difficulty_ratio: DifficultyRatio = Field(default_factory=DifficultyRatio)
    question_types: QuestionTypes = Field(default_factory=QuestionTypes)
    calculation_requirement: CalculationRequirement = Field(
        default_factory=CalculationRequirement
    )
    auto_distribute_scores: bool = False


class ConfirmCurriculumResponse(BaseModel):
    confirmed: bool = True
    exam_info: dict[str, Any]
    curriculum: list[CurriculumItem]
    total_periods: int
    difficulty_ratio: DifficultyRatio
    question_types: QuestionTypes
    calculation_requirement: CalculationRequirement
    auto_distribute_scores: bool = False
    message: str = "Phạm vi kiểm tra đã được xác nhận."


class AnswerGenerateRequest(BaseModel):
    """Request for standalone answer/rubric generation from accepted questions."""
    exam_id: int = Field(..., description="ID của đề kiểm tra")
    accepted_question_ids: list[str] = Field(..., min_length=1, description="Danh sách câu hỏi đã duyệt")


class AnswerGenerateResponse(BaseModel):
    answer_key: list[dict[str, Any]]
    rubric: list[dict[str, Any]]
    message: str = "Đã tạo đáp án và rubric cho các câu hỏi đã duyệt."


class ExportRequest(BaseModel):
    """Request body for the legacy POST /api/export endpoint."""
    exam_id: int = Field(..., description="ID của đề kiểm tra cần xuất Word")


class ExamDeleteResponse(BaseModel):
    id: int
    deleted: bool = True
    message: str = "Đã xóa đề kiểm tra."


class ExamResponse(ExamCreate):
    id: int
    exam_number: int | None = Field(default=None, ge=1)
    owner_user_id: int | None = None
    school_id: int | None = None
    publication_status: PublicationStatus = "verified"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamListItem(BaseModel):
    id: int
    exam_number: int | None = Field(default=None, ge=1)
    school: str
    grade: int
    subject: str
    exam_type: str
    duration_minutes: int
    school_year: str
    total_score: float
    owner_user_id: int | None = None
    owner_name: str | None = None
    school_id: int | None = None
    publication_status: PublicationStatus = "verified"
    created_at: datetime


class ExamSearchResponse(BaseModel):
    items: list[ExamListItem]
    total: int
    page: int
    page_size: int
