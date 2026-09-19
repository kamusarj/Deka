import asyncio
import json
import logging
from contextlib import asynccontextmanager
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from threading import Lock
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm.exc import StaleDataError

from app.agents import (
    AnswerAgent,
    MatrixAgent,
    QuestionAgent,
    ResourceCollectorAgent,
    SpecificationAgent,
    ValidatorAgent,
    VerificationAgent,
)
from app.core.config import settings
from app.core.database import get_session_factory, init_db
from app.models.exam import Exam
from app.models.user import User
from app.schemas.exam import (
    AnswerGenerateResponse,
    ConfirmCurriculumResponse,
    CurriculumAnalyzeRequest,
    CurriculumAnalyzeResponse,
    CurriculumItem,
    DataIngestRequest,
    DataIngestResponse,
    DataNormalizeRequest,
    DataNormalizeResponse,
    ExamDeleteResponse,
    ExamListItem,
    ExamSearchResponse,
    FullExamRequest,
    FullExamResponse,
    MatrixRequest,
    MatrixResponse,
    QuestionsGenerateRequest,
    QuestionsGenerateResponse,
    RegenerateQuestionsRequest,
    RegenerateQuestionsResponse,
    ResourceCollectRequest,
    ResourceCollectResponse,
    ReviewQuestionsRequest,
    SpecificationRequest,
    SpecificationResponse,
    ValidationRequest,
    ValidationResponse,
)
from app.services.authorization import (
    ownership_values,
    require_resource_access,
    require_resource_mutation,
    scope_query,
)
from app.services.exam import grounding, review, serializers, variants
from app.services.export_service import ExportService
from app.services.knowledge_base_service import KnowledgeBaseService
from app.services.pdf_export_service import PdfExportService
from app.services.question_duplicates import bank_candidates, exam_duplicate_report
from app.services.exam.editing import merge_edit, validate_revision
from app.schemas.question_edit import QuestionEditRequest

logger = logging.getLogger("app.exam")
_exam_locks_guard = Lock()


class _ExamLockEntry:
    def __init__(self):
        self.lock = asyncio.Lock()
        self.users = 0


_exam_locks: dict[int, _ExamLockEntry] = {}


class _QualityGateRejection(HTTPException):
    """Expected post-generation rejection carrying the latest real payload."""

    def __init__(
        self,
        *,
        status_code: int,
        detail: dict,
        generated: dict,
        verification: dict,
        repaired_ids: list[str],
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.generated = generated
        self.verification = verification
        self.repaired_ids = repaired_ids


@asynccontextmanager
async def _exam_lock(exam_id: int):
    with _exam_locks_guard:
        entry = _exam_locks.setdefault(exam_id, _ExamLockEntry())
        entry.users += 1
    try:
        async with entry.lock:
            yield
    finally:
        with _exam_locks_guard:
            entry.users -= 1
            if entry.users == 0 and _exam_locks.get(exam_id) is entry:
                _exam_locks.pop(exam_id, None)


class ExamService:
    # Kept as class attributes for backwards compatibility; the values live in
    # app.services.exam.variants alongside the code that uses them.
    DEFAULT_VARIANT_COUNT = variants.DEFAULT_VARIANT_COUNT
    MAX_VARIANT_COUNT = variants.MAX_VARIANT_COUNT
    VERIFIED_STATUS = "verified"
    DRAFT_STATUS = "draft"

    def __init__(self):
        init_db()
        self.SessionLocal = get_session_factory()
        self.resource_agent = ResourceCollectorAgent()
        self.matrix_agent = MatrixAgent()
        self.spec_agent = SpecificationAgent()
        self.question_agent = QuestionAgent()
        self.answer_agent = AnswerAgent()
        self.validator_agent = ValidatorAgent()
        self.verification_agent = VerificationAgent()
        self.export_service = ExportService()
        self.pdf_export_service = PdfExportService()
        self.knowledge_base = KnowledgeBaseService()

    async def collect_resources(self, request: ResourceCollectRequest) -> ResourceCollectResponse:
        resource_package = await self.resource_agent.run(
            grade=request.grade,
            subject=request.subject,
            exam_type=request.exam_type,
        )
        return ResourceCollectResponse(resource_package=resource_package)

    async def ingest_data(self, request: DataIngestRequest) -> DataIngestResponse:
        resource_package = await self.resource_agent.run(
            grade=request.grade,
            subject=request.subject,
            exam_type=request.exam_type,
        )
        return DataIngestResponse(
            data_sources=resource_package["data_sources"],
            raw_data=resource_package["raw_data"],
            resource_package=resource_package,
        )

    async def analyze_curriculum(self, request: CurriculumAnalyzeRequest) -> CurriculumAnalyzeResponse:
        resources = await self.resource_agent.run(
            grade=request.grade,
            subject=request.subject,
            exam_type=request.exam_type,
        )
        curriculum = self._curriculum_from_text(request.teaching_plan)
        if not curriculum:
            curriculum = [
                CurriculumItem(
                    topic=item["topic"],
                    periods=item["periods"],
                    achievements=item["achievements"],
                )
                for item in resources["curriculum_suggestions"]
            ]
        return CurriculumAnalyzeResponse(
            curriculum=curriculum,
            total_periods=sum(item.periods for item in curriculum),
            resource_package=resources,
        )

    async def normalize_data(self, request: DataNormalizeRequest) -> DataNormalizeResponse:
        analyzed = await self.analyze_curriculum(request)
        normalized = {
            "grade": request.grade,
            "subject": request.subject,
            "exam_type": request.exam_type,
            "topics": [
                {
                    "name": item.topic,
                    "periods": item.periods,
                    "objectives": item.achievements,
                }
                for item in analyzed.curriculum
            ],
        }
        return DataNormalizeResponse(
            normalized_curriculum=normalized,
            curriculum=analyzed.curriculum,
            total_periods=analyzed.total_periods,
            metadata={
                "sources": [
                    source["source_type"]
                    for source in (analyzed.resource_package or {}).get("data_sources", [])
                ],
                "processed_at": datetime.now(timezone.utc).isoformat(),
            },
            resource_package=analyzed.resource_package,
        )

    async def generate_matrix(self, request: MatrixRequest) -> MatrixResponse:
        result = await self.matrix_agent.run(request=request)
        return MatrixResponse(matrix=result["matrix"], summary=result["summary"])

    async def generate_specification(self, request: SpecificationRequest) -> SpecificationResponse:
        matrix_result = await self.matrix_agent.run(request=request)
        specification = await self.spec_agent.run(
            matrix=matrix_result["matrix"],
            question_plan=matrix_result["question_plan"],
            curriculum=request.curriculum,
        )
        return SpecificationResponse(
            specification=specification,
            matrix=matrix_result["matrix"],
            summary=matrix_result["summary"],
        )

    async def generate_questions(self, request: QuestionsGenerateRequest) -> QuestionsGenerateResponse:
        specification = grounding.apply_local_sources(
            request.specification, grade=request.grade
        )
        generated = await self.question_agent.run(
            specification=specification,
            grade=request.grade,
        )
        return QuestionsGenerateResponse(**generated)

    async def validate_exam(self, request: ValidationRequest) -> ValidationResponse:
        validation = await self.validator_agent.run(
            questions=request.questions,
            answer_key=request.answer_key,
            rubric=request.rubric,
            summary=request.summary,
            request=SimpleNamespace(
                total_score=request.total_score,
                difficulty_ratio=request.difficulty_ratio,
                calculation_requirement=request.calculation_requirement,
                auto_distribute_scores=request.auto_distribute_scores,
            ),
        )
        verification = await self.verification_agent.run(
            questions=request.questions,
            answer_key=request.answer_key,
        )
        validation["verification_report"] = verification
        return ValidationResponse(validation=validation)

    async def confirm_curriculum(self, request) -> ConfirmCurriculumResponse:
        """Step 2: Teacher confirms the scope before generating matrix."""
        total_periods = sum(item.periods for item in request.curriculum)
        return ConfirmCurriculumResponse(
            confirmed=True,
            exam_info={
                "school": request.school,
                "grade": request.grade,
                "subject": request.subject,
                "exam_type": request.exam_type,
                "duration_minutes": request.duration_minutes,
                "school_year": request.school_year,
                "total_score": request.total_score,
            },
            curriculum=request.curriculum,
            total_periods=total_periods,
            difficulty_ratio=request.difficulty_ratio,
            question_types=request.question_types,
            calculation_requirement=request.calculation_requirement,
            auto_distribute_scores=request.auto_distribute_scores,
            message="Phạm vi kiểm tra đã được xác nhận. Sẵn sàng tạo ma trận.",
        )

    async def generate_answers(self, request, actor=None) -> AnswerGenerateResponse:
        """Step 7: Generate answers and rubrics for accepted/specified questions."""
        async with _exam_lock(request.exam_id):
            with self.SessionLocal() as db:
                exam = self._get_model(db, request.exam_id, actor)
                require_resource_mutation(exam, actor)
                accepted_questions = [
                    deepcopy(q)
                    for q in exam.questions
                    if q.get("id") in request.accepted_question_ids
                ]
                specification = deepcopy(exam.specification)
                expected_version = int(exam.version_id or 1)
                if not accepted_questions:
                    raise HTTPException(
                        status_code=400,
                        detail="Không có câu hỏi nào để tạo đáp án",
                    )

            # The provider await happens after the session has been closed.
            generated = await self.answer_agent.run(
                questions=accepted_questions,
                specification=specification,
            )

            with self.SessionLocal() as db:
                exam = self._get_model(db, request.exam_id, actor)
                require_resource_mutation(exam, actor)
                if int(exam.version_id or 1) != expected_version:
                    raise HTTPException(
                        status_code=409,
                        detail="Đề đã được cập nhật ở nơi khác. Vui lòng tải lại và thử lại.",
                    )
                exam.answer_key = self._replace_by_id(
                    exam.answer_key or [], generated["answer_key"], "question_id"
                )
                exam.rubric = self._replace_by_id(
                    exam.rubric or [], generated["rubric"], "question_id"
                )
                self._commit_exam(db)

            return AnswerGenerateResponse(
                answer_key=generated["answer_key"],
                rubric=generated["rubric"],
                message=f"Đã tạo đáp án cho {len(accepted_questions)} câu hỏi đã duyệt.",
            )

    async def generate_full_exam(self, request: FullExamRequest, actor=None) -> FullExamResponse:
        resource_package = await self.resource_agent.run(
            grade=request.grade,
            subject=request.subject,
            exam_type=request.exam_type,
        )
        resource_package = {
            **resource_package,
            "variant_count": request.variant_count,
            "use_uploaded_docs": getattr(request, "use_uploaded_docs", None) or [],
            "calculation_requirement": request.calculation_requirement.model_dump(),
            "auto_distribute_scores": request.auto_distribute_scores,
        }
        matrix_result = await self.matrix_agent.run(request=request)
        specification = await self.spec_agent.run(
            matrix=matrix_result["matrix"],
            question_plan=matrix_result["question_plan"],
            curriculum=request.curriculum,
        )
        specification = grounding.apply_local_sources(specification, grade=request.grade)
        specification = await asyncio.to_thread(
            self._apply_rag_sources,
            specification,
            grade=request.grade,
            document_ids=getattr(request, "use_uploaded_docs", None) or [],
            actor=actor,
        )
        generated = await self.question_agent.run(
            specification=specification,
            grade=request.grade,
        )
        validation = {}
        try:
            validation = await self.validator_agent.run(
                questions=generated["questions"],
                answer_key=generated["answer_key"],
                rubric=generated["rubric"],
                summary=matrix_result["summary"],
                request=request,
            )
            validation["verification_report"] = await self.verification_agent.run(
                questions=generated["questions"],
                answer_key=generated["answer_key"],
                curriculum=request.curriculum,
                specification=specification,
                grade=request.grade,
            )
            generated, verification_report, repaired_ids = await self._repair_hard_failures(
                generated=generated,
                verification=validation["verification_report"],
                specification=specification,
                grade=request.grade,
                curriculum=request.curriculum,
            )
            if repaired_ids:
                validation = await self.validator_agent.run(
                    questions=generated["questions"],
                    answer_key=generated["answer_key"],
                    rubric=generated["rubric"],
                    summary=matrix_result["summary"],
                    request=request,
                )
            validation["verification_report"] = verification_report
            self._require_persistable(validation)
        except HTTPException as error:
            draft = self._persist_failed_draft(
                error=error,
                request=request,
                matrix=matrix_result["matrix"],
                summary=matrix_result["summary"],
                specification=specification,
                generated=generated,
                validation=validation,
                resource_package=resource_package,
                actor=actor,
            )
            return self._to_full_exam_with_variants(draft)

        await self._add_duplicate_findings(validation, generated, request.grade, actor)
        validation = self._verified_validation(validation)
        review_status = {
            question["id"]: {"status": "pending", "regenerated": False, "reason": ""}
            for question in generated["questions"]
        }
        exam = self._create_exam(
            request=request,
            matrix=matrix_result["matrix"],
            summary=matrix_result["summary"],
            specification=specification,
            questions=generated["questions"],
            answer_key=generated["answer_key"],
            rubric=generated["rubric"],
            validation=validation,
            resource_package=resource_package,
            review_status=review_status,
            publication_status=self.VERIFIED_STATUS,
            actor=actor,
        )
        return self._to_full_exam_with_variants(exam)

    async def generate_full_exam_stream(self, request: FullExamRequest, actor=None):
        """SSE generator: yields JSON events for each pipeline stage."""

        def _event(stage: str, status: str, message: str, data: dict | None = None):
            payload = {"stage": stage, "status": status, "message": message}
            if data:
                payload["data"] = data
            return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        try:
            # ── Stage 1: Collect Resources ──
            yield _event("collect_resources", "running", "Đang thu thập tài liệu tham khảo...")
            resource_package = await self.resource_agent.run(
                grade=request.grade,
                subject=request.subject,
                exam_type=request.exam_type,
            )
            resource_package = {
                **resource_package,
                "variant_count": request.variant_count,
                "use_uploaded_docs": getattr(request, "use_uploaded_docs", None) or [],
                "calculation_requirement": request.calculation_requirement.model_dump(),
                "auto_distribute_scores": request.auto_distribute_scores,
            }
            yield _event("collect_resources", "completed", "Đã thu thập tài liệu tham khảo")

            # ── Stage 2: Generate Matrix ──
            yield _event("generate_matrix", "running", "Đang tạo ma trận đề...")
            matrix_result = await self.matrix_agent.run(request=request)
            yield _event("generate_matrix", "completed", "Đã tạo ma trận đề",
                         {
                             "total_questions": matrix_result["summary"].get("total_questions", 0),
                             "calculation_count": matrix_result["summary"].get(
                                 "calculation_requirement", {}
                             ).get("actual_count", 0),
                         })

            # ── Stage 3: Generate Specification ──
            yield _event("generate_specification", "running", "Đang tạo bản đặc tả...")
            specification = await self.spec_agent.run(
                matrix=matrix_result["matrix"],
                question_plan=matrix_result["question_plan"],
                curriculum=request.curriculum,
            )
            specification = grounding.apply_local_sources(specification, grade=request.grade)
            yield _event("generate_specification", "completed", "Đã tạo bản đặc tả")

            # ── Stage 4: Apply RAG Sources ──
            doc_ids = getattr(request, "use_uploaded_docs", None) or []
            if doc_ids:
                yield _event("apply_rag", "running", "Đang truy xuất tài liệu RAG...")
                specification = await asyncio.to_thread(
                    self._apply_rag_sources,
                    specification,
                    grade=request.grade,
                    document_ids=doc_ids,
                    actor=actor,
                )
                yield _event("apply_rag", "completed", "Đã truy xuất tài liệu RAG")
            else:
                yield _event("apply_rag", "skipped", "Bỏ qua RAG (không có tài liệu)")

            # ── Stage 5: Generate Questions ──
            yield _event("generate_questions", "running", "Đang sinh câu hỏi bằng AI...")
            generated = await self.question_agent.run(
                specification=specification,
                grade=request.grade,
            )
            yield _event("generate_questions", "completed", f"Đã sinh {len(generated['questions'])} câu hỏi",
                         {"question_count": len(generated["questions"])})

            # ── Stage 6: Validate ──
            yield _event("validate", "running", "Đang kiểm tra đề...")
            validation = await self.validator_agent.run(
                questions=generated["questions"],
                answer_key=generated["answer_key"],
                rubric=generated["rubric"],
                summary=matrix_result["summary"],
                request=request,
            )
            yield _event("validate", "completed", "Đã kiểm tra đề",
                         {"passed": validation.get("passed", False), "score": validation.get("score", 0)})

            # ── Stage 7: Verify (AI verification) ──
            yield _event("verify", "running", "AI đang kiểm chứng nội dung...")

            verification_result = None
            try:
                async for progress_msg, result in self.verification_agent.run_with_progress(
                    questions=generated["questions"],
                    answer_key=generated["answer_key"],
                    curriculum=request.curriculum,
                    specification=specification,
                    grade=request.grade,
                ):
                    if progress_msg:
                        # Intermediate progress — yield to keep SSE alive
                        yield _event("verify", "running", progress_msg)
                    if result:
                        verification_result = result
                validation["verification_report"] = verification_result
                generated, verification_result, repaired_ids = await self._repair_hard_failures(
                    generated=generated,
                    verification=verification_result,
                    specification=specification,
                    grade=request.grade,
                    curriculum=request.curriculum,
                )
                if repaired_ids:
                    yield _event(
                        "verify",
                        "running",
                        f"Đã tạo lại {len(repaired_ids)} câu không qua cổng chất lượng",
                        {"question_ids": repaired_ids},
                    )
                    validation = await self.validator_agent.run(
                        questions=generated["questions"],
                        answer_key=generated["answer_key"],
                        rubric=generated["rubric"],
                        summary=matrix_result["summary"],
                        request=request,
                    )
                validation["verification_report"] = verification_result
                self._require_persistable(validation)
            except HTTPException as error:
                draft = self._persist_failed_draft(
                    error=error,
                    request=request,
                    matrix=matrix_result["matrix"],
                    summary=matrix_result["summary"],
                    specification=specification,
                    generated=generated,
                    validation=validation,
                    resource_package=resource_package,
                    actor=actor,
                )
                failures = draft.validation.get("persistence", {}).get(
                    "question_failures", {}
                )
                yield _event(
                    "verify",
                    "completed",
                    "Kiểm định chưa đạt; đã dừng gọi AI và giữ lại kết quả thật.",
                    {"passed": False, "question_ids": sorted(failures)},
                )
                yield _event("persist", "running", "Đang lưu bản nháp...")
                yield _event(
                    "persist",
                    "completed",
                    "Đã lưu bản nháp để sửa các câu chưa đạt.",
                    {
                        "exam_id": draft.id,
                        "publication_status": self.DRAFT_STATUS,
                        "question_ids": sorted(failures),
                    },
                )
                yield _event(
                    "build_variants",
                    "skipped",
                    "Bản nháp chưa tạo mã đề.",
                )
                result = self._to_full_response(draft)
                yield _event(
                    "done",
                    "completed",
                    "Đã lưu bản nháp chưa qua kiểm định.",
                    {
                        "exam_id": draft.id,
                        "publication_status": self.DRAFT_STATUS,
                    },
                )
                yield f"data: {json.dumps({'type': 'result', 'payload': result.model_dump()}, ensure_ascii=False, default=str)}\n\n"
                return

            await self._add_duplicate_findings(validation, generated, request.grade, actor)
            validation = self._verified_validation(validation)
            yield _event("verify", "completed", "Đã kiểm chứng nội dung")

            # ── Stage 8: Persist ──
            yield _event("persist", "running", "Đang lưu đề...")
            review_status = {
                question["id"]: {"status": "pending", "regenerated": False, "reason": ""}
                for question in generated["questions"]
            }
            exam = self._create_exam(
                request=request,
                matrix=matrix_result["matrix"],
                summary=matrix_result["summary"],
                specification=specification,
                questions=generated["questions"],
                answer_key=generated["answer_key"],
                rubric=generated["rubric"],
                validation=validation,
                resource_package=resource_package,
                review_status=review_status,
                publication_status=self.VERIFIED_STATUS,
                actor=actor,
            )

            # ── Stage 9: Build Variants ──
            yield _event("build_variants", "running", "Đang tạo mã đề...")
            result = self._to_full_response(exam)
            yield _event("build_variants", "completed", f"Đã tạo {len(result.variants)} mã đề")

            # ── Done ──
            yield _event("done", "completed", "Hoàn thành!", {"exam_id": exam.id})
            yield f"data: {json.dumps({'type': 'result', 'payload': result.model_dump()}, ensure_ascii=False, default=str)}\n\n"

        except HTTPException as error:
            logger.warning("Full-exam SSE generation rejected status=%s", error.status_code)
            detail = error.detail
            message = (
                detail.get("message", "Không thể tạo đề kiểm tra.")
                if isinstance(detail, dict)
                else str(detail)
            )
            yield _event("error", "error", message)
        except Exception:
            logger.error("Full-exam SSE generation failed")
            yield _event(
                "error",
                "error",
                "Không thể tạo đề kiểm tra. Vui lòng thử lại hoặc liên hệ quản trị viên.",
            )

    def _to_full_exam_with_variants(self, exam: Exam) -> FullExamResponse:
        return self._to_full_response(exam)

    async def _repair_hard_failures(
        self,
        *,
        generated,
        verification,
        specification,
        grade,
        curriculum,
    ):
        """Regenerate independently rejected items once before persistence."""
        failures = self.verification_agent.hard_failure_reasons(
            verification,
            require_independent=self.question_agent.has_ai,
        )
        if not failures:
            return generated, verification, []

        if any(
            "semantic_review_unavailable" in reasons
            for reasons in failures.values()
        ):
            raise _QualityGateRejection(
                status_code=503,
                detail=self._semantic_review_unavailable_detail(failures),
                generated=generated,
                verification=verification,
                repaired_ids=[],
            )

        failed_ids = set(failures)
        failed_specs = [
            spec for spec in specification if spec.get("question_id") in failed_ids
        ]
        try:
            regenerated = await self.question_agent.run(
                specification=failed_specs,
                grade=grade,
                failure_reasons=self._repair_feedback(verification, failures),
            )
        except HTTPException as error:
            provider_detail = (
                error.detail if isinstance(error.detail, dict) else {}
            )
            raise _QualityGateRejection(
                status_code=error.status_code,
                detail={
                    "message": provider_detail.get(
                        "message",
                        str(error.detail),
                    ),
                    "question_failures": failures,
                },
                generated=generated,
                verification=verification,
                repaired_ids=[],
            ) from error
        generated = {
            "questions": self._replace_by_id(
                generated["questions"], regenerated["questions"], "id"
            ),
            "answer_key": self._replace_by_id(
                generated["answer_key"], regenerated["answer_key"], "question_id"
            ),
            "rubric": self._replace_by_id(
                generated["rubric"], regenerated["rubric"], "question_id"
            ),
        }
        retry_verification = await self.verification_agent.run(
            questions=regenerated["questions"],
            answer_key=regenerated["answer_key"],
            curriculum=curriculum,
            specification=failed_specs,
            grade=grade,
        )
        retry_failures = self.verification_agent.hard_failure_reasons(
            retry_verification,
            require_independent=self.question_agent.has_ai,
        )
        merged_verification = self._merge_verification_reports(
            verification, retry_verification
        )
        if retry_failures:
            if any(
                "semantic_review_unavailable" in reasons
                for reasons in retry_failures.values()
            ):
                raise _QualityGateRejection(
                    status_code=503,
                    detail=self._semantic_review_unavailable_detail(retry_failures),
                    generated=generated,
                    verification=merged_verification,
                    repaired_ids=sorted(failed_ids),
                )
            raise _QualityGateRejection(
                status_code=422,
                detail={
                    "message": "Một số câu vẫn sai sau lần tạo lại kiểm chứng.",
                    "question_failures": retry_failures,
                },
                generated=generated,
                verification=merged_verification,
                repaired_ids=sorted(failed_ids),
            )
        return (
            generated,
            merged_verification,
            sorted(failed_ids),
        )

    @staticmethod
    def _semantic_review_unavailable_detail(failures):
        required = (
            "DeepSeek V4 Pro"
            if settings.AI_INTERACTIVE_REVIEW_MODE == "deepseek_only"
            else "DeepSeek V4 Pro và Gemini 3.7 Flash"
        )
        return {
            "message": (
                f"Chưa thể hoàn tất kiểm định bắt buộc bằng {required}. "
                "Đề chưa được lưu."
            ),
            "question_failures": failures,
        }

    @staticmethod
    def _repair_feedback(verification, failures):
        reports = {
            item.get("question_id"): item
            for item in (verification or {}).get("question_reports") or []
        }
        return {
            question_id: list(reasons) + [
                f"{issue.get('description', '')} Cách sửa: {issue.get('suggestion', '')}"
                for issue in reports.get(question_id, {}).get("issues") or []
            ]
            for question_id, reasons in failures.items()
        }

    def _merge_verification_reports(self, original, replacement):
        replacements = {
            item.get("question_id"): item
            for item in replacement.get("question_reports") or []
        }
        reports = [
            replacements.get(item.get("question_id"), item)
            for item in original.get("question_reports") or []
        ]
        original_ids = {item.get("question_id") for item in reports}
        reports.extend(
            item
            for question_id, item in replacements.items()
            if question_id not in original_ids
        )
        counts = {
            status: sum(1 for item in reports if item.get("status") == status)
            for status in ("approved", "needs_review", "not_verified")
        }
        scores = [
            item.get("verification_score")
            for item in reports
            if item.get("verification_score") is not None
        ]
        action_required = []
        for report in reports:
            if report.get("status") != "needs_review" or not report.get("issues"):
                continue
            issue = report["issues"][0]
            action_required.append(
                {
                    "priority": "high" if issue.get("severity") in {"critical", "major"} else "medium",
                    "question_id": report.get("question_id"),
                    "message": issue.get("description"),
                    "fix": issue.get("suggestion"),
                }
            )
        merged = {
            **original,
            "question_reports": reports,
            "overall_score": round(sum(scores) / len(scores), 1) if scores else None,
            "overall_status": (
                "not_verified" if counts["not_verified"]
                else "passed_with_warnings" if counts["needs_review"]
                else "passed"
            ),
            "summary": {
                "total_questions": len(reports),
                "auto_approved": counts["approved"],
                "needs_review": counts["needs_review"],
                "auto_rejected": 0,
                "not_verified": counts["not_verified"],
            },
            "action_required": action_required,
        }
        reviewer_summary = self.verification_agent.reviewer_summary(reports)
        if reviewer_summary:
            merged["reviewer_summary"] = reviewer_summary
        return merged

    def _can_persist_failed_draft(self, request, actor) -> bool:
        """Drafts are only for authenticated, real-AI, no-fallback authoring."""
        return bool(
            actor is not None
            and getattr(actor, "id", None)
            and getattr(request, "allow_provider_fallback", True) is False
            and self.question_agent.has_ai
        )

    @classmethod
    def _verified_validation(cls, validation: dict) -> dict:
        verified = deepcopy(validation)
        verified["persistence"] = {
            "status": cls.VERIFIED_STATUS,
            "publishable": True,
        }
        return verified

    @classmethod
    def _draft_validation(
        cls,
        validation: dict,
        *,
        error: HTTPException,
        verification: dict | None = None,
    ) -> dict:
        draft = deepcopy(validation)
        deterministic_passed = bool(draft.get("passed", False))
        if verification is not None:
            draft["verification_report"] = verification
        detail = error.detail if isinstance(error.detail, dict) else {
            "message": str(error.detail)
        }
        draft["deterministic_passed"] = deterministic_passed
        draft["passed"] = False
        gate_message = detail.get(
            "message", "Đề chưa qua cổng chất lượng bắt buộc."
        )
        saved_message = gate_message.replace("Đề chưa được lưu.", "").strip()
        saved_message = (
            f"{saved_message} Nội dung AI đã được lưu dưới dạng bản nháp."
        )
        draft["persistence"] = {
            "status": cls.DRAFT_STATUS,
            "publishable": False,
            "failure_stage": (
                "semantic_verification"
                if isinstance(error, _QualityGateRejection)
                else "post_generation_quality"
            ),
            "message": saved_message,
            "gate_message": gate_message,
            "question_failures": detail.get("question_failures", {}),
            "errors": detail.get("errors", []),
        }
        return draft

    def _persist_failed_draft(
        self,
        *,
        error: HTTPException,
        request,
        matrix,
        summary,
        specification,
        generated,
        validation,
        resource_package,
        actor,
    ) -> Exam:
        if not self._can_persist_failed_draft(request, actor):
            raise error

        latest_generated = getattr(error, "generated", generated)
        latest_verification = getattr(
            error, "verification", validation.get("verification_report")
        )
        draft_validation = self._draft_validation(
            validation,
            error=error,
            verification=latest_verification,
        )
        failures = draft_validation["persistence"]["question_failures"]
        review_status = {
            question["id"]: {
                "status": (
                    "needs_revision" if question["id"] in failures else "pending"
                ),
                "regenerated": question["id"] in getattr(error, "repaired_ids", []),
                "reason": ", ".join(failures.get(question["id"], [])),
            }
            for question in latest_generated["questions"]
        }
        exam = self._create_exam(
            request=request,
            matrix=matrix,
            summary=summary,
            specification=specification,
            questions=latest_generated["questions"],
            answer_key=latest_generated["answer_key"],
            rubric=latest_generated["rubric"],
            validation=draft_validation,
            resource_package=resource_package,
            review_status=review_status,
            publication_status=self.DRAFT_STATUS,
            actor=actor,
        )
        logger.warning(
            "exam_draft_persisted exam_id=%s owner_user_id=%s failure_stage=%s question_ids=%s",
            exam.id,
            exam.owner_user_id,
            draft_validation["persistence"]["failure_stage"],
            sorted(failures),
        )
        return exam

    @classmethod
    def _require_publishable(cls, exam: Exam) -> None:
        if (exam.publication_status or cls.VERIFIED_STATUS) != cls.VERIFIED_STATUS:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Bản nháp chưa qua kiểm định bắt buộc nên chưa thể xuất bản. "
                    "Hãy tạo lại các câu bị lỗi trước."
                ),
            )

    @staticmethod
    def _require_persistable(validation):
        if validation.get("errors"):
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "Đề chưa qua kiểm tra bắt buộc nên không được lưu.",
                    "errors": validation["errors"],
                },
            )

    def _apply_rag_sources(self, specification, *, grade, document_ids, actor=None) -> list[dict]:
        return grounding.apply_rag_sources(
            self.knowledge_base,
            specification,
            document_ids=document_ids,
            actor=actor,
        )

    async def _add_duplicate_findings(self, validation, generated, grade, actor=None):
        if not settings.DUPLICATE_DETECTION_ENABLED:
            return

        def check():
            with self.SessionLocal() as db:
                candidates = bank_candidates(db, actor)
            return exam_duplicate_report(generated["questions"], generated["answer_key"], candidates)

        report = await asyncio.to_thread(check)
        validation["duplicate_report"] = report
        if report["findings"]:
            validation.setdefault("warnings", []).append("Có câu hỏi tương tự trong đề hoặc ngân hàng; hãy xem cảnh báo trùng lặp.")

    async def review_questions(self, exam_id: int, request: ReviewQuestionsRequest, actor=None) -> FullExamResponse:
        async with _exam_lock(exam_id):
            with self.SessionLocal() as db:
                exam = self._get_model(db, exam_id, actor)
                require_resource_mutation(exam, actor)
                review_status = dict(exam.review_status or {})
                valid_question_ids = {question["id"] for question in exam.questions}

                self._apply_review_ids(
                    review_status,
                    request.accepted_question_ids,
                    valid_question_ids,
                    status="accepted",
                )
                self._apply_review_ids(
                    review_status,
                    request.needs_revision_question_ids,
                    valid_question_ids,
                    status="needs_revision",
                )
                self._apply_review_ids(
                    review_status,
                    request.rejected_question_ids,
                    valid_question_ids,
                    status="rejected",
                )
                for review_item in request.reviews:
                    if review_item.question_id not in valid_question_ids:
                        raise HTTPException(status_code=400, detail=f"Không tìm thấy câu hỏi {review_item.question_id}")
                    review_status[review_item.question_id] = {
                        **review_status.get(review_item.question_id, {}),
                        "status": review_item.status,
                        "comment": review_item.comment,
                        "reviewed_by": review_item.reviewed_by,
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    }
                exam.review_status = review_status
                self._commit_exam(db)
                return self._to_full_response(exam)

    def bank_edit_template(self, exam_id, question_id, bank_id, *, version_id, actor):
        from app.services.question_bank_service import QuestionBankService
        from app.services.exam.bank_reuse import bank_edit_template
        with self.SessionLocal() as db:
            exam = self._get_model(db, exam_id, actor)
            require_resource_mutation(exam, actor)
            if exam.version_id != version_id:
                raise HTTPException(409, "Đề đã thay đổi. Hãy tải lại trước khi chọn câu ngân hàng.")
            question = next((q for q in exam.questions if q["id"] == question_id), None)
            bank = QuestionBankService()._get_model(db, bank_id, actor)
            if question is None or bank.grade not in {None, exam.grade} or bank.subject != exam.subject:
                raise HTTPException(422, "Câu ngân hàng không cùng phạm vi KHTN/khối lớp.")
            return bank_edit_template(bank, question, exam.version_id)

    async def edit_question(self, exam_id: int, question_id: str, request: QuestionEditRequest, actor=None):
        async with _exam_lock(exam_id):
            with self.SessionLocal() as db:
                exam = self._get_model(db, exam_id, actor)
                require_resource_mutation(exam, actor)
                if int(exam.version_id or 1) != request.version_id:
                    raise HTTPException(409, "Đề đã được cập nhật ở nơi khác. Vui lòng tải lại trước khi lưu.")
                original = next((item for item in exam.questions if item["id"] == question_id), None)
                if original is None:
                    raise HTTPException(404, "Không tìm thấy câu hỏi trong bản gốc.")
                spec = next((item for item in exam.specification if item["question_id"] == question_id), None)
                if spec is None or not 6 <= exam.grade <= 9 or exam.subject != "Khoa học tự nhiên":
                    raise HTTPException(422, "Câu hỏi thiếu đặc tả KHTN hợp lệ.")
                canonical = self._to_full_response(exam)
                old_answer = next((item for item in canonical.answer_key if item["question_id"] == question_id), {})
                old_rubric = next((item for item in exam.rubric if item["question_id"] == question_id), None)
                question, answer, rubric_item = merge_edit(original, old_answer, old_rubric, request)
                reused_bank_id = request.bank_question_id
                if reused_bank_id is not None:
                    # Read through the same authorized boundary used for preview.
                    self.bank_edit_template(exam_id, question_id, reused_bank_id, version_id=request.version_id, actor=actor)
                    question.setdefault("metadata", {})["reused_from_bank_id"] = reused_bank_id
                score_check = self.validator_agent._check_score_increment([question])
                if not score_check["passed"]:
                    raise HTTPException(422, score_check["message"])
                questions = self._replace_by_id(deepcopy(exam.questions), [question], "id")
                answers = self._replace_by_id(deepcopy(exam.answer_key), [answer], "question_id")
                rubrics = self._replace_by_id(deepcopy(exam.rubric), [rubric_item] if rubric_item else [], "question_id")
                previous_validation = deepcopy(exam.validation or {})
                spec = deepcopy(spec)
                grade = exam.grade
                validation_request = ValidationRequest(
                    questions=questions, answer_key=answers, rubric=rubrics,
                    summary=deepcopy(exam.summary), total_score=exam.total_score,
                    difficulty_ratio=exam.summary.get("expected_ratio", {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30}),
                    calculation_requirement=(exam.resource_package or {}).get("calculation_requirement") or {},
                    auto_distribute_scores=(exam.resource_package or {}).get("auto_distribute_scores", False),
                )

            revision_issues = await validate_revision(question, answer, rubric_item, spec, grade=grade, llm=self.question_agent.llm)
            validation = await self.validator_agent.run(
                questions=questions, answer_key=answers, rubric=rubrics,
                summary=validation_request.summary, request=validation_request,
            )
            verification = await self.verification_agent.run(
                questions=[question], answer_key=[answer], specification=[spec], grade=grade,
                curriculum=[{"topic": spec.get("topic"), "achievements": [spec.get("achievement")]}],
            )
            validation["verification_report"] = self._merge_verification_reports(
                previous_validation.get("verification_report") or {"question_reports": []}, verification,
            )
            failures = self.verification_agent.hard_failure_reasons(validation["verification_report"], require_independent=True)
            validation.setdefault("warnings", []).extend(issue.message for issue in revision_issues)
            validation["teacher_edit_issues"] = [{**issue.as_dict(), "question_id": question_id} for issue in revision_issues]
            for issue in revision_issues:
                if issue.severity in {"critical", "major"}:
                    failures.setdefault(question_id, []).append(issue.code)
            edited_report = next((item for item in verification.get("question_reports", []) if item.get("question_id") == question_id), {})
            if (edited_report.get("checks", {}).get("solve_compare") or {}).get("status") != "match":
                failures.setdefault(question_id, []).append("teacher_edit_requires_independent_review")
            if question.get("metadata", {}).get("is_calculation") and not question["metadata"].get("calculation_verified"):
                failures.setdefault(question_id, []).append("teacher_calculation_requires_revalidation")
            await self._add_duplicate_findings(validation, {"questions": questions, "answer_key": answers}, grade, actor)
            if failures or validation.get("errors"):
                error = HTTPException(422, {"message": "Đã lưu chỉnh sửa dưới dạng bản nháp; cần xử lý các câu chưa qua kiểm định.", "question_failures": failures, "errors": validation.get("errors", [])})
                validation = self._draft_validation(validation, error=error, verification=validation["verification_report"])
                publication_status = self.DRAFT_STATUS
            else:
                validation = self._verified_validation(validation)
                publication_status = self.VERIFIED_STATUS
            with self.SessionLocal() as db:
                exam = self._get_model(db, exam_id, actor)
                require_resource_mutation(exam, actor)
                if int(exam.version_id or 1) != request.version_id:
                    raise HTTPException(409, "Đề đã thay đổi trong lúc kiểm định. Nội dung trên máy bạn vẫn được giữ để thử lại.")
                if reused_bank_id is not None:
                    from app.services.question_bank_service import QuestionBankService
                    bank = QuestionBankService()._get_model(db, reused_bank_id, actor)
                    bank.usage_count = (bank.usage_count or 0) + 1
                exam.questions, exam.answer_key, exam.rubric = questions, answers, rubrics
                exam.validation, exam.publication_status = validation, publication_status
                exam.review_status = {**(exam.review_status or {}), question_id: {"status": "needs_revision" if question_id in failures else "pending", "regenerated": False, "reason": "Giáo viên vừa chỉnh sửa"}}
                self._commit_exam(db)
                return self._to_full_response(exam)

    async def review_questions_from_payload(self, request: ReviewQuestionsRequest, actor=None) -> FullExamResponse:
        if request.exam_id is None:
            raise HTTPException(status_code=400, detail="Thiếu exam_id")
        return await self.review_questions(request.exam_id, request, actor)

    async def regenerate_questions(self, request: RegenerateQuestionsRequest, actor=None) -> RegenerateQuestionsResponse:
        async with _exam_lock(request.exam_id):
            with self.SessionLocal() as db:
                exam = self._get_model(db, request.exam_id, actor)
                require_resource_mutation(exam, actor)
                question_ids = set(request.question_ids)
                available_ids = {question["id"] for question in exam.questions}
                specified_ids = {spec["question_id"] for spec in exam.specification}
                if not question_ids.issubset(available_ids & specified_ids):
                    raise HTTPException(
                        status_code=400,
                        detail="Có câu hỏi không tồn tại hoặc thiếu bản đặc tả. Vui lòng tải lại đề và chọn lại câu cần tạo.",
                    )
                specs = []
                for spec in exam.specification:
                    if spec["question_id"] in question_ids:
                        next_spec = dict(spec)
                        next_spec["variant_note"] = request.reason
                        specs.append(next_spec)

                if not specs:
                    raise HTTPException(status_code=400, detail="Không tìm thấy câu hỏi cần tạo lại")

                questions = deepcopy(exam.questions)
                answer_key = deepcopy(exam.answer_key)
                rubric = deepcopy(exam.rubric)
                summary = deepcopy(exam.summary)
                previous_validation = deepcopy(exam.validation or {})
                publication_status = (
                    exam.publication_status or self.VERIFIED_STATUS
                )
                total_score = exam.total_score
                grade = exam.grade
                expected_version = int(exam.version_id or 1)

                stored_failures = (
                    previous_validation.get("persistence", {}).get(
                        "question_failures", {}
                    )
                )
                if (
                    publication_status == self.DRAFT_STATUS
                    and stored_failures
                    and not question_ids.issubset(stored_failures)
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Bản nháp chỉ được tạo lại các câu đang có lỗi kiểm định."
                        ),
                    )
                if (
                    publication_status == self.DRAFT_STATUS
                    and getattr(request, "allow_provider_fallback", True) is not False
                ):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            "Tạo lại câu lỗi của bản nháp bắt buộc tắt provider fallback."
                        ),
                    )

            # All provider work happens without holding a database connection.
            generated = await self.question_agent.run(
                specification=specs,
                grade=grade,
                failure_reasons=self._repair_feedback(previous_validation.get("verification_report"), {
                    question_id: stored_failures.get(
                        question_id, ["teacher_requested_regeneration"]
                    )
                    for question_id in question_ids
                }),
            )
            questions = self._replace_by_id(questions, generated["questions"], "id")
            answer_key = self._replace_by_id(answer_key, generated["answer_key"], "question_id")
            rubric = self._replace_by_id(rubric, generated["rubric"], "question_id")

            ratio = summary.get("expected_ratio", {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30})
            validation = await self.validator_agent.run(
                questions=questions,
                answer_key=answer_key,
                rubric=rubric,
                summary=summary,
                request=SimpleNamespace(
                    total_score=total_score,
                    difficulty_ratio=SimpleNamespace(model_dump=lambda: ratio),
                    auto_distribute_scores=bool(
                        summary.get("auto_distribute_scores", False)
                    ),
                    calculation_requirement={
                        "count": (
                            summary.get("calculation_requirement", {}).get(
                                "required_count", 0
                            )
                        ),
                        "score_per_question": (
                            summary.get("calculation_requirement", {}).get(
                                "score_per_question", 0.5
                            )
                        ),
                        "difficulties": (
                            summary.get("calculation_requirement", {}).get(
                                "requested_difficulties", []
                            )
                        ),
                    },
                ),
            )
            retry_verification = await self.verification_agent.run(
                questions=generated["questions"],
                answer_key=generated["answer_key"],
                curriculum=[
                    {
                        "topic": item.get("topic"),
                        "achievements": [item.get("achievement")],
                    }
                    for item in specs
                ],
                specification=specs,
                grade=grade,
            )
            previous_verification = previous_validation.get("verification_report") or {
                "question_reports": []
            }
            validation["verification_report"] = self._merge_verification_reports(
                previous_verification, retry_verification
            )
            hard_failures = self.verification_agent.hard_failure_reasons(
                validation["verification_report"],
                require_independent=self.question_agent.has_ai,
            )
            deterministic_errors = validation.get("errors") or []
            if (hard_failures or deterministic_errors) and (
                publication_status != self.DRAFT_STATUS
            ):
                raise HTTPException(
                    status_code=422,
                    detail={
                        "message": "Câu tạo lại chưa qua kiểm chứng độc lập nên chưa được lưu.",
                        "question_failures": hard_failures,
                        "errors": deterministic_errors,
                    },
                )

            if hard_failures or deterministic_errors:
                detail = {
                    "message": (
                        "Bản nháp vẫn còn câu chưa qua kiểm định bắt buộc."
                    ),
                    "question_failures": hard_failures,
                    "errors": deterministic_errors,
                }
                if any(
                    "semantic_review_unavailable" in reasons
                    for reasons in hard_failures.values()
                ):
                    detail["message"] = self._semantic_review_unavailable_detail(
                        hard_failures
                    )["message"]
                draft_error = _QualityGateRejection(
                    status_code=422,
                    detail=detail,
                    generated={
                        "questions": questions,
                        "answer_key": answer_key,
                        "rubric": rubric,
                    },
                    verification=validation["verification_report"],
                    repaired_ids=sorted(question_ids),
                )
                validation = self._draft_validation(
                    validation,
                    error=draft_error,
                    verification=validation["verification_report"],
                )
                next_publication_status = self.DRAFT_STATUS
            else:
                self._require_persistable(validation)
                validation = self._verified_validation(validation)
                next_publication_status = self.VERIFIED_STATUS

            await self._add_duplicate_findings(validation, {"questions": questions, "answer_key": answer_key}, grade, actor)
            with self.SessionLocal() as db:
                exam = self._get_model(db, request.exam_id, actor)
                require_resource_mutation(exam, actor)
                if int(exam.version_id or 1) != expected_version:
                    raise HTTPException(
                        status_code=409,
                        detail="Đề đã được cập nhật ở nơi khác. Vui lòng tải lại và thử lại.",
                    )
                review_status = dict(exam.review_status or {})
                for question_id in question_ids:
                    failure_reasons = hard_failures.get(question_id, [])
                    review_status[question_id] = {
                        "status": (
                            "needs_revision" if failure_reasons else "pending"
                        ),
                        "regenerated": True,
                        "reason": (
                            ", ".join(failure_reasons)
                            if failure_reasons
                            else request.reason
                        ),
                    }
                exam.questions = questions
                exam.answer_key = answer_key
                exam.rubric = rubric
                exam.review_status = review_status
                exam.validation = validation
                exam.publication_status = next_publication_status
                self._commit_exam(db)
                if (
                    publication_status == self.DRAFT_STATUS
                    and next_publication_status == self.VERIFIED_STATUS
                ):
                    logger.info(
                        "exam_draft_verified exam_id=%s owner_user_id=%s",
                        exam.id,
                        exam.owner_user_id,
                    )
                return RegenerateQuestionsResponse(
                    **self._to_full_response(exam).model_dump(),
                    regenerated_question_ids=sorted(question_ids),
                )

    async def list_exams(
        self,
        *,
        grade: int | None = None,
        exam_type: str | None = None,
        limit: int | None = None,
        offset: int = 0,
        actor=None,
    ):
        with self.SessionLocal() as db:
            query = scope_query(db.query(Exam), Exam, actor)
            if grade is not None:
                query = query.filter(Exam.grade == grade)
            if exam_type:
                query = query.filter(Exam.exam_type == exam_type)
            query = query.order_by(Exam.created_at.desc(), Exam.id.desc())
            if offset:
                query = query.offset(offset)
            if limit is not None:
                query = query.limit(limit)
            exams = query.all()
            return [self._to_response(exam) for exam in exams]

    async def get_exam(self, exam_id: int, actor=None):
        with self.SessionLocal() as db:
            return self._to_full_response(self._get_model(db, exam_id, actor))

    async def search_exams(
        self,
        *,
        subject: str | None = None,
        grade: int | None = None,
        exam_type: str | None = None,
        owner_user_id: int | None = None,
        page: int = 1,
        page_size: int = 20,
        actor=None,
    ) -> ExamSearchResponse:
        with self.SessionLocal() as db:
            query = scope_query(db.query(Exam), Exam, actor)
            if subject:
                query = query.filter(Exam.subject.ilike(f"%{subject.strip()}%"))
            if grade is not None:
                query = query.filter(Exam.grade == grade)
            if exam_type:
                query = query.filter(Exam.exam_type == exam_type)
            if owner_user_id is not None:
                query = query.filter(Exam.owner_user_id == owner_user_id)
            total = query.count()
            exams = (
                query.order_by(Exam.created_at.desc(), Exam.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
                .all()
            )
            owner_ids = {exam.owner_user_id for exam in exams if exam.owner_user_id is not None}
            owner_names = dict(
                db.query(User.id, User.name).filter(User.id.in_(owner_ids)).all()
            ) if owner_ids else {}
            return ExamSearchResponse(
                items=[
                    ExamListItem(
                        id=exam.id,
                        exam_number=exam.exam_number,
                        school=exam.school,
                        grade=exam.grade,
                        subject=exam.subject,
                        exam_type=exam.exam_type,
                        duration_minutes=exam.duration_minutes,
                        school_year=exam.school_year,
                        total_score=exam.total_score,
                        owner_user_id=exam.owner_user_id,
                        owner_name=owner_names.get(exam.owner_user_id),
                        school_id=exam.school_id,
                        publication_status=(
                            exam.publication_status or self.VERIFIED_STATUS
                        ),
                        created_at=exam.created_at or datetime.now(timezone.utc),
                    )
                    for exam in exams
                ],
                total=total,
                page=page,
                page_size=page_size,
            )

    async def delete_exam(self, exam_id: int, actor=None) -> ExamDeleteResponse:
        with self.SessionLocal() as db:
            exam = self._get_model(db, exam_id, actor)
            require_resource_mutation(exam, actor)
            db.delete(exam)
            db.commit()
            return ExamDeleteResponse(id=exam_id)

    async def duplicate_exam(self, exam_id: int, actor=None) -> FullExamResponse:
        with self.SessionLocal() as db:
            source = self._get_model(db, exam_id, actor)
            duplicate = Exam(
                school=source.school,
                grade=source.grade,
                subject=source.subject,
                exam_type=source.exam_type,
                duration_minutes=source.duration_minutes,
                school_year=source.school_year,
                total_score=source.total_score,
                matrix=deepcopy(source.matrix),
                summary=deepcopy(source.summary),
                specification=deepcopy(source.specification),
                questions=deepcopy(source.questions),
                answer_key=deepcopy(source.answer_key),
                rubric=deepcopy(source.rubric),
                validation=deepcopy(source.validation),
                resource_package=deepcopy(source.resource_package),
                review_status=self._reset_review_status(source.questions),
                publication_status=(
                    source.publication_status or self.VERIFIED_STATUS
                ),
                **ownership_values(actor),
            )
            db.add(duplicate)
            db.commit()
            db.refresh(duplicate)
            return self._to_full_response(duplicate)

    def _reset_review_status(self, questions) -> dict:
        return review.reset_review_status(questions)

    async def export_docx(self, exam_id: int, actor=None, audience: str = "teacher",
                          document: str = "exam", variant_code: str | None = None) -> StreamingResponse:
        content = await asyncio.to_thread(
            self._render_docx, exam_id, actor, audience, document, variant_code
        )
        filename = f"smart-exam-{exam_id}-{document}-{variant_code or 'original'}.docx"
        return StreamingResponse(
            BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _render_docx(self, exam_id: int, actor=None, audience: str = "teacher",
                     document: str = "exam", variant_code: str | None = None) -> bytes:
        with self.SessionLocal() as db:
            exam = self._get_model(db, exam_id, actor)
            self._require_publishable(exam)
            doc = self.export_service.create_full_docx(
                self._to_export_dict(exam), include_answers=audience == "teacher",
                document=document, variant_code=variant_code,
            )
        buffer = BytesIO()
        doc.save(buffer)
        return buffer.getvalue()

    async def export_pdf(self, exam_id: int, actor=None, audience: str = "teacher",
                         document: str = "exam", variant_code: str | None = None) -> StreamingResponse:
        pdf_bytes = await asyncio.to_thread(
            self._render_pdf, exam_id, actor, audience, document, variant_code
        )
        filename = f"smart-exam-{exam_id}-{document}-{variant_code or 'original'}.pdf"
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    def _render_pdf(self, exam_id: int, actor=None, audience: str = "teacher",
                    document: str = "exam", variant_code: str | None = None) -> bytes:
        with self.SessionLocal() as db:
            exam = self._get_model(db, exam_id, actor)
            self._require_publishable(exam)
            return self.pdf_export_service.create_full_pdf(
                self._to_export_dict(exam), include_answers=audience == "teacher",
                document=document, variant_code=variant_code,
            )

    @staticmethod
    def _commit_exam(db) -> None:
        from app.services.ai.lifecycle import active_operation
        operation = active_operation.get()
        try:
            changed_exams = [row for row in list(db.new) + list(db.dirty) if isinstance(row, Exam)]
            if operation is not None and changed_exams:
                operation.persist(db, changed_exams[0])
            db.commit()
            if operation is not None and changed_exams:
                operation.result_committed = True
        except StaleDataError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Đề đã được cập nhật đồng thời. Vui lòng tải lại và thử lại.",
            ) from exc

    def _create_exam(self, **data) -> Exam:
        request = data.pop("request")
        actor = data.pop("actor", None)
        with self.SessionLocal() as db:
            exam = Exam(
                school=request.school,
                grade=request.grade,
                subject=request.subject,
                exam_type=request.exam_type,
                duration_minutes=request.duration_minutes,
                school_year=request.school_year,
                total_score=request.total_score,
                **ownership_values(actor),
                **data,
            )
            db.add(exam)
            self._commit_exam(db)
            db.refresh(exam)
            return exam

    def _get_model(self, db, exam_id: int, actor=None) -> Exam:
        exam = db.get(Exam, exam_id)
        if not exam:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề kiểm tra")
        return require_resource_access(exam, actor)

    def _to_response(self, exam: Exam):
        return serializers.to_response(exam)

    def _to_full_response(self, exam: Exam) -> FullExamResponse:
        return serializers.to_full_response(exam)

    def _to_export_dict(self, exam: Exam) -> dict:
        return serializers.to_export_dict(exam)

    def _build_variants(self, exam: Exam) -> list[dict]:
        return variants.build_variants(exam)

    def _replace_by_id(self, current: list[dict], replacements: list[dict], key: str) -> list[dict]:
        return review.replace_by_id(current, replacements, key)

    def _apply_review_ids(
        self,
        review_status: dict,
        question_ids: list[str],
        valid_question_ids: set[str],
        *,
        status: str,
    ) -> None:
        review.apply_review_ids(
            review_status, question_ids, valid_question_ids, status=status
        )

    def _curriculum_from_text(self, text: str) -> list[CurriculumItem]:
        return review.curriculum_from_text(text)
