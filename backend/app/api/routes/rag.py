from app.api.response_privacy import ContentPrivacyRoute
import asyncio
from app.services.ai.operations import run_billable

from fastapi import APIRouter, Depends

from app.schemas.rag import (
    RagIndexRequest,
    RagIndexResponse,
    RagQueryRequest,
    RagQueryResponse,
)
from app.services.knowledge_base_service import KnowledgeBaseService
from app.models.user import User
from app.services.auth_service import require_ai_request

router = APIRouter(route_class=ContentPrivacyRoute, prefix="/rag", tags=["rag"])
kb_service = KnowledgeBaseService()


@router.post("/index", response_model=RagIndexResponse)
async def build_index(request: RagIndexRequest, user: User = Depends(require_ai_request)):
    """Build (in-memory) index từ curriculum(grade) + tài liệu đã chọn; trả thống kê."""
    stats = await run_billable(user, lambda: asyncio.to_thread(
        kb_service.index_stats,
        grade=request.grade,
        document_ids=request.document_ids,
        actor=user,
    ), "rag_index")
    return RagIndexResponse(
        document_ids=request.document_ids,
        grade=request.grade,
        retriever=kb_service.retriever_backend(),
        **stats,
    )


@router.post("/query", response_model=RagQueryResponse)
async def query_index(request: RagQueryRequest, user: User = Depends(require_ai_request)):
    """Debug: truy xuất chunk liên quan tới `query`.

    Dùng embeddings khi đã cấu hình, ngược lại BM25 offline. Trường `retriever`
    trong response cho biết backend nào đã trả lời.
    """
    hits, retriever = await run_billable(user, lambda: asyncio.to_thread(
        kb_service.query_with_backend,
        query=request.query,
        grade=request.grade,
        document_ids=request.document_ids,
        k=request.k,
        actor=user,
    ), "rag_query")
    return RagQueryResponse(
        query=request.query,
        hits=hits,
        count=len(hits),
        retriever=retriever,
    )
