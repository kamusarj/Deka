"""Strict output contracts for AI-generated exam JSON.

These models are passed to OpenAI's Responses API structured parsing helper.
Gemini and DeepSeek JSON is validated against the same contracts before
agent-level normalization, whether used in legacy failover or mandatory dual
verification.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.rich_content import RichBlock


QuestionType = Literal["multiple_choice", "true_false", "short_answer", "essay"]
Difficulty = Literal["nhan_biet", "thong_hieu", "van_dung"]


class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class OptionSet(StrictOutputModel):
    A: str
    B: str
    C: str
    D: str


class GeneratedStatement(StrictOutputModel):
    id: str
    content: str
    is_true: bool


class GeneratedSubQuestion(StrictOutputModel):
    id: str
    content: str
    score: float


class CalculationValue(StrictOutputModel):
    symbol: str
    value: float
    unit: str


class CalculationResult(StrictOutputModel):
    value: float
    unit: str


class GeneratedCalculation(StrictOutputModel):
    formula_id: Literal[
        "RELATIVE_MOLECULAR_MASS",
        "SPEED",
        "MASS_MOLES",
        "MOLAR_MASS_FROM_COMPOSITION",
        "MOLAR_GAS_VOLUME_STP",
        "GAS_RELATIVE_DENSITY_H2",
        "CONCENTRATION_PERCENT",
        "DENSITY",
        "PRESSURE",
        "MOMENT",
        "OHM",
        "HEAT",
        "KINETIC_ENERGY",
        "POTENTIAL_ENERGY",
        "MECHANICAL_ENERGY",
        "ELECTRIC_POWER",
        "ELECTRIC_ENERGY",
        "SERIES_RESISTANCE",
        "PARALLEL_RESISTANCE_TWO",
        "DATA_DIFFERENCE",
        "PERCENT_CHANGE",
    ]
    known_values: list[CalculationValue]
    target_symbol: str
    calculation_steps: list[str]
    result: CalculationResult
    rounding_decimals: int | None = Field(default=None, ge=0, le=6)


class GeneratedQuestion(StrictOutputModel):
    rich_content: list[RichBlock] | None = Field(default=None, max_length=32)
    id: str
    number: int
    type: QuestionType
    difficulty: Difficulty
    score: float
    content: str
    options: OptionSet | None = None
    statements: list[GeneratedStatement] | None = None
    sub_questions: list[GeneratedSubQuestion] | None = None
    correct_answer: str | None = None
    calculation: GeneratedCalculation | None = None


class TrueFalseAnswer(StrictOutputModel):
    statement_id: str
    is_true: bool
    explanation: str


class GeneratedAnswer(StrictOutputModel):
    question_id: str
    question_number: int
    type: QuestionType
    correct_answer: str | None = None
    explanation: str | None = None
    option_explanations: OptionSet | None = None
    answers: list[TrueFalseAnswer] | None = None
    keywords: list[str] | None = None
    accept_variations: bool | None = None
    model_answer: str | None = None
    key_points: list[str] | None = None


class RubricLevel(StrictOutputModel):
    score: float
    description: str
    criteria: str


class RubricCriterion(StrictOutputModel):
    id: str
    name: str
    max_score: float
    levels: list[RubricLevel]


class GeneratedRubric(StrictOutputModel):
    question_id: str
    question_number: int
    type: Literal["essay"]
    total_score: float
    criteria: list[RubricCriterion]
    grading_guide: list[str]


class QuestionGenerationOutput(StrictOutputModel):
    questions: list[GeneratedQuestion]
    answer_key: list[GeneratedAnswer]
    rubric: list[GeneratedRubric]


class AnswerGenerationOutput(StrictOutputModel):
    answer_key: list[GeneratedAnswer]
    rubric: list[GeneratedRubric]


class SolvedStatement(StrictOutputModel):
    statement_id: str
    is_true: bool


class SolveVerificationOutput(StrictOutputModel):
    your_answer: str | None = None
    statement_answers: list[SolvedStatement]
    multiple_correct: bool = Field(description="Only for multiple_choice: more than one option is scientifically correct. False for true_false, short_answer and essay.")
    confidence: float = Field(ge=0, le=1)
    reasoning: str
    detected_issues: list[str]


class QualityIssue(StrictOutputModel):
    severity: Literal["critical", "major", "medium"]
    description: str
    suggestion: str


class DistractorReview(StrictOutputModel):
    option: str
    plausibility: float = Field(ge=0, le=1)
    reason: str


class StatementReview(StrictOutputModel):
    id: str
    is_clear: bool
    ambiguity_type: Literal[
        "none", "vague_term", "double_negative", "multiple_interpretations"
    ]
    suggestion: str


class QualityVerificationOutput(StrictOutputModel):
    is_valid: bool
    knowledge_target: str
    source_grounded: bool
    objective_copied: bool = Field(description="True only if actual answer prose replaces scientific content with a pedagogical objective such as 'Nêu được...'. Matching the curriculum, scientific terminology, or scope/citation metadata is not objective copying.")
    answer_correct: bool
    single_correct_answer: bool = Field(description="For multiple_choice, exactly one option is correct. True for other types: multiple true statements or equivalent open answers are allowed.")
    explanation_scientific: bool
    required_context_present: bool
    issues_found: list[QualityIssue]
    distractors: list[DistractorReview]
    overall_distractor_quality: Literal["good", "acceptable", "poor"]
    statements: list[StatementReview]
    assessed_difficulty: Difficulty
    difficulty_matches: bool
    reasoning: str


class IndependentVerificationOutput(StrictOutputModel):
    """One paid reviewer call covers both independent solve and quality review."""

    solve: SolveVerificationOutput
    quality: QualityVerificationOutput
