from app.api.response_privacy import ContentPrivacyRoute
import asyncio
from app.services.ai.operations import run_billable
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.config import settings
from app.models.user import User
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentLibrary,
    DocumentSharingRequest,
    DocumentReviewRequest,
)
from app.services.auth_service import get_current_user, require_content_writer, require_super_admin
from app.services.document_service import DocumentService

router = APIRouter(route_class=ContentPrivacyRoute, prefix="/documents", tags=["documents"])
document_service = DocumentService()
UPLOAD_READ_CHUNK_SIZE = 1024 * 1024


async def _read_upload_limited(file: UploadFile) -> bytes:
    """Read at most the configured number of file bytes, independent of headers."""
    limit = settings.MAX_UPLOAD_SIZE_BYTES
    chunks: list[bytes] = []
    size = 0

    while chunk := await file.read(min(UPLOAD_READ_CHUNK_SIZE, limit - size + 1)):
        size += len(chunk)
        if size > limit:
            limit_mb = limit / (1024 * 1024)
            display_limit = f"{limit_mb:g} MB"
            raise HTTPException(
                status_code=413,
                detail=f"Tệp vượt quá giới hạn tải lên {display_limit}.",
            )
        chunks.append(chunk)

    return b"".join(chunks)


@router.post("/upload", response_model=DocumentDetailResponse)
async def upload_document(
    file: UploadFile = File(...),
    grade: int | None = Form(default=None, ge=6, le=9),
    ocr_mode: Literal["auto", "native", "ocr"] = Form(default="auto"),
    user: User = Depends(require_content_writer),
):
    """Native-first PDF/Office/image ingestion with selective OCR."""
    data = await _read_upload_limited(file)
    return await run_billable(user, lambda: asyncio.to_thread(
        document_service.save_document,
        filename=file.filename or "document",
        data=data,
        grade=grade,
        actor=user,
        ocr_mode=ocr_mode,
    ), "document_upload")


@router.get("", response_model=list[DocumentResponse])
async def list_documents(grade: int | None = None, library: DocumentLibrary = "all", user: User = Depends(get_current_user)):
    """Danh sách tài liệu đã upload (lọc theo khối lớp tùy chọn)."""
    return document_service.list_documents(grade=grade, actor=user, library=library)


@router.patch("/{document_id}/sharing", response_model=DocumentDetailResponse)
def update_sharing(document_id: int, request: DocumentSharingRequest,
                   user: User = Depends(require_content_writer)):
    return document_service.update_sharing(document_id, request, actor=user)


@router.post("/{document_id}/review", response_model=DocumentDetailResponse)
def review_sharing(document_id: int, request: DocumentReviewRequest,
                   user: User = Depends(require_super_admin)):
    return document_service.review_sharing(document_id, request, actor=user)


@router.get("/{document_id}", response_model=DocumentDetailResponse)
async def get_document(document_id: int, user: User = Depends(get_current_user)):
    """Chi tiết tài liệu kèm toàn bộ text đã trích xuất."""
    return document_service.get_document(document_id, actor=user)


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: int, user: User = Depends(require_content_writer)):
    """Xóa tài liệu (xóa cả file trên đĩa)."""
    return document_service.delete_document(document_id, actor=user)
