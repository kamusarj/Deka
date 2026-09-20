"""Dịch vụ quản lý tài liệu upload: lưu file, trích xuất, CRUD.

Native extraction được ưu tiên; DocumentProcessor thực hiện OCR khi cần.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import settings
from app.core.database import get_session_factory, init_db
from app.extractors import InvalidDocumentError, UnsupportedDocumentError
from app.extractors.document_processor import DocumentProcessor
from app.models.document import UploadedDocument
from app.models.document_cleanup import DocumentCleanup
from app.models.user import User
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentSharingRequest,
    DocumentReviewRequest,
)
from app.services.authorization import ownership_values, require_resource_mutation
from app.services.audit_service import record_audit
from app.services.document_access import (
    document_access_filter, can_manage_document, can_share_document_with_school,
    can_review_document,
)


PREVIEW_LENGTH = 500
logger = logging.getLogger("deka")


class DocumentService:
    def __init__(self):
        init_db()
        self.SessionLocal = get_session_factory()
        self.upload_dir = self._resolve_upload_dir()

    def _resolve_upload_dir(self) -> Path:
        upload_path = Path(settings.UPLOAD_DIR)
        if not upload_path.is_absolute():
            # backend root = parents[2] của app/services/document_service.py
            upload_path = Path(__file__).resolve().parents[2] / upload_path
        upload_path.mkdir(parents=True, exist_ok=True)
        return upload_path

    def save_document(self, *, filename: str, data: bytes, grade: int | None = None, actor=None, ocr_mode: str = "auto") -> DocumentDetailResponse:
        try:
            extracted = DocumentProcessor().process(filename, data, ocr_mode=ocr_mode)
        except (UnsupportedDocumentError, InvalidDocumentError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

        from app.services.ai.lifecycle import checkpoint
        checkpoint()
        if actor is not None:
            with self.SessionLocal() as db:
                self._check_upload_quota(db, actor.id, len(data))
        stored_filename = f"{uuid4().hex}_{Path(filename).name}"
        stored_path = self.upload_dir / stored_filename

        with self.SessionLocal() as db:
            if actor is not None:
                from app.services.ai.lifecycle import active_operation, check_authority
                operation = active_operation.get()
                if operation is not None:
                    check_authority(db, operation, lock=True)
                else:
                    db.execute(update(User).where(User.id == actor.id).values(token_version=User.token_version))
                self._check_upload_quota(db, actor.id, len(data))
            next_id = None
            if db.get_bind().dialect.name == 'sqlite':
                # SQLite legacy tables lack AUTOINCREMENT. Acquire the writer
                # lock before choosing an ID above retained tombstones.
                db.execute(update(UploadedDocument).where(UploadedDocument.id == -1).values(id=-1))
                next_id = max(db.scalar(select(func.max(UploadedDocument.id))) or 0,
                              db.scalar(select(func.max(DocumentCleanup.document_id))) or 0) + 1
            document = UploadedDocument(
                id=next_id,
                filename=Path(filename).name,
                stored_filename=stored_filename,
                file_type=extracted["file_type"],
                size=len(data),
                extracted_text=extracted["text"],
                parsed_data=extracted["parsed_data"],
                status="extracted",
                grade=grade,
                **ownership_values(actor),
            )
            db.add(document)
            try:
                stored_path.write_bytes(data)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                try:
                    stored_path.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    logger.error(
                        "Không thể dọn file %s sau khi lưu DB thất bại: %s",
                        stored_path,
                        cleanup_error,
                    )
                raise
            db.refresh(document)
            return self._to_detail(document, actor)

    @staticmethod
    def _check_upload_quota(db, user_id, incoming_bytes):
        count, total = db.execute(select(func.count(), func.coalesce(func.sum(UploadedDocument.size), 0))
            .where(UploadedDocument.owner_user_id == user_id)).one()
        if count >= settings.MAX_DOCUMENTS_PER_USER or total + incoming_bytes > settings.MAX_DOCUMENT_BYTES_PER_USER:
            raise HTTPException(413, 'Thư viện đã đạt giới hạn lưu trữ. Hãy xóa bớt tài liệu trước khi tải lên.')

    def list_documents(self, grade: int | None = None, actor=None, library: str = "all") -> list[DocumentResponse]:
        with self.SessionLocal() as db:
            query = db.query(UploadedDocument).filter(document_access_filter(actor))
            if library == "mine":
                query = query.filter(UploadedDocument.owner_user_id == getattr(actor, "id", -1))
            elif library == "school":
                query = query.filter(UploadedDocument.sharing_scope == "school", UploadedDocument.school_id == getattr(actor, "school_id", -1))
            elif library == "system":
                query = query.filter(UploadedDocument.sharing_scope == "system", UploadedDocument.sharing_status == "approved")
            elif library == "pending":
                if actor is None or actor.role != "super_admin":
                    raise HTTPException(status_code=403, detail="Chỉ Super Admin được xem hàng chờ duyệt")
                query = query.filter(UploadedDocument.sharing_scope == "system", UploadedDocument.sharing_status == "pending")
            elif library != "all":
                raise HTTPException(status_code=422, detail="Bộ lọc thư viện không hợp lệ")
            if grade is not None:
                query = query.filter(UploadedDocument.grade == grade)
            documents = query.order_by(
                UploadedDocument.created_at.desc(), UploadedDocument.id.desc()
            ).all()
            return [self._to_response(document, actor) for document in documents]

    def get_document(self, document_id: int, actor=None) -> DocumentDetailResponse:
        with self.SessionLocal() as db:
            return self._to_detail(self._get_model(db, document_id, actor), actor)

    def delete_document(self, document_id: int, actor=None) -> DocumentDeleteResponse:
        with self.SessionLocal() as db:
            document = self._get_model(db, document_id, actor)
            require_resource_mutation(document, actor)
            self._stored_path(document.stored_filename)
            if actor is not None and not can_manage_document(document, actor):
                raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
            record_audit(db, actor=actor, action="document.deleted", target_type="document",
                         target_id=document.id, school_id=document.school_id,
                         details={"scope": document.sharing_scope})
            job = DocumentCleanup(document_id=document.id, owner_user_id=getattr(document, "owner_user_id", None),
                                  stored_filename=document.stored_filename)
            db.add(job)
            db.delete(document)
            try:
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

            cleanup_id = job.id
        from app.services.document_cleanup import cleanup_one
        cleanup_one(self.SessionLocal, cleanup_id, upload_dir=self.upload_dir)
        return DocumentDeleteResponse(id=document_id)

    def _stored_path(self, stored_filename: str) -> Path:
        normalized = str(stored_filename).replace("\\", "/")
        basename = Path(normalized).name
        if not basename or basename in {".", ".."} or basename != normalized:
            logger.error("Từ chối tên file lưu trữ không an toàn: %r", stored_filename)
            raise HTTPException(status_code=500, detail="Tên file lưu trữ không hợp lệ")
        return self.upload_dir / basename

    def get_documents_for_rag(self, document_ids: list[int], actor=None) -> list[UploadedDocument]:
        """Resolve current sharing permissions before using any cached vectors."""
        if not document_ids:
            return []
        with self.SessionLocal() as db:
            documents = db.query(UploadedDocument).filter(
                document_access_filter(actor), UploadedDocument.id.in_(document_ids),
            ).all()
            if {document.id for document in documents} != set(document_ids):
                raise HTTPException(status_code=404, detail="Tài liệu đã bị xóa hoặc bạn không còn quyền sử dụng. Vui lòng chọn lại nguồn.")
            return documents

    def _get_model(self, db, document_id: int, actor=None) -> UploadedDocument:
        document = db.query(UploadedDocument).filter(
            UploadedDocument.id == document_id, document_access_filter(actor),
        ).first()
        if not document:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
        return document

    @staticmethod
    def _check_version(document, version_id):
        if document.version_id != version_id:
            raise HTTPException(status_code=409, detail="Tài liệu đã được cập nhật. Vui lòng tải lại trước khi tiếp tục.")

    @staticmethod
    def _commit_sharing(db):
        try:
            db.commit()
        except StaleDataError as error:
            db.rollback()
            raise HTTPException(status_code=409, detail="Tài liệu đã được cập nhật. Vui lòng tải lại trước khi tiếp tục.") from error

    def update_sharing(self, document_id: int, request: DocumentSharingRequest, *, actor):
        with self.SessionLocal() as db:
            document = self._get_model(db, document_id, actor)
            if not can_manage_document(document, actor):
                raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu")
            self._check_version(document, request.version_id)
            if request.scope == "school" and not can_share_document_with_school(document, actor):
                raise HTTPException(status_code=400, detail="Chỉ chia sẻ trong trường khi bạn thuộc trường của tài liệu này")
            if document.sharing_scope == request.scope and not (
                request.scope == "system" and document.sharing_status == "rejected"
            ):
                return self._to_detail(document, actor)
            previous = {"scope": document.sharing_scope, "status": document.sharing_status}
            document.sharing_scope = request.scope
            document.sharing_status = "pending" if request.scope == "system" else "none"
            document.reviewed_by_user_id = None
            document.reviewed_at = None
            document.review_note = ""
            record_audit(db, actor=actor, action="document.sharing_changed", target_type="document",
                         target_id=document.id, school_id=document.school_id,
                         details={"before": previous, "scope": document.sharing_scope, "status": document.sharing_status})
            self._commit_sharing(db)
            db.refresh(document)
            return self._to_detail(document, actor)

    def review_sharing(self, document_id: int, request: DocumentReviewRequest, *, actor):
        if actor is None or actor.role != "super_admin":
            raise HTTPException(status_code=403, detail="Chỉ Super Admin được duyệt chia sẻ toàn hệ thống")
        with self.SessionLocal() as db:
            document = self._get_model(db, document_id, actor)
            self._check_version(document, request.version_id)
            if not can_review_document(document, actor) or (
                document.sharing_status == "approved" and request.decision == "approve"
            ):
                raise HTTPException(status_code=409, detail="Tài liệu không còn yêu cầu duyệt phù hợp")
            document.sharing_status = "approved" if request.decision == "approve" else "rejected"
            document.reviewed_by_user_id = actor.id
            document.reviewed_at = datetime.now(timezone.utc)
            document.review_note = request.note.strip()
            record_audit(db, actor=actor, action=f"document.sharing_{document.sharing_status}",
                         target_type="document", target_id=document.id, school_id=document.school_id,
                         details={"scope": document.sharing_scope, "status": document.sharing_status})
            self._commit_sharing(db)
            db.refresh(document)
            return self._to_detail(document, actor)

    def _to_response(self, document: UploadedDocument, actor=None) -> DocumentResponse:
        text = document.extracted_text or ""
        return DocumentResponse(
            id=document.id,
            owner_user_id=document.owner_user_id,
            school_id=document.school_id,
            sharing_scope=document.sharing_scope,
            sharing_status=document.sharing_status,
            review_note=document.review_note if can_manage_document(document, actor) else "",
            reviewed_at=document.reviewed_at,
            version_id=document.version_id,
            can_manage=can_manage_document(document, actor),
            can_share_school=can_share_document_with_school(document, actor),
            can_review=can_review_document(document, actor),
            filename=document.filename,
            file_type=document.file_type,
            size=document.size,
            status=document.status,
            grade=document.grade,
            text_preview=text[:PREVIEW_LENGTH],
            text_length=len(text),
            parsed_data=document.parsed_data,
            created_at=document.created_at,
        )

    def _to_detail(self, document: UploadedDocument, actor=None) -> DocumentDetailResponse:
        base = self._to_response(document, actor)
        return DocumentDetailResponse(
            **base.model_dump(),
            extracted_text=document.extracted_text or "",
        )
