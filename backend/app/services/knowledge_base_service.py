"""KnowledgeBaseService: build the RAG index and retrieve from it.

Selection is behind `BaseRetriever.retrieve`. `EmbeddingRetriever` is used when
embeddings are configured; otherwise — and whenever setting one up fails —
retrieval falls back to the offline, deterministic `BM25Retriever`. Query
diagnostics report which backend actually answered. The app therefore keeps
working with no API key, which is the Phase 1 promise.
"""

import logging
from collections import Counter

from app.core.config import settings
from app.rag import (
    BaseRetriever,
    BM25Retriever,
    EmbeddingRetriever,
    FallbackRetriever,
    build_chunks,
    resolve_embedder,
)
from app.services.document_service import DocumentService
from app.rag.hybrid import HybridRetriever, RelevanceReranker
from app.rag.vector_store import shared_vector_store

logger = logging.getLogger("app.rag")


class KnowledgeBaseService:
    def __init__(self):
        self.document_service = DocumentService()

    def _chunks(self, *, grade: int | None, document_ids: list[int], actor=None) -> list[dict]:
        from app.services.ai.lifecycle import active_operation, checkpoint
        operation = active_operation.get()
        if operation is not None:
            operation.document_ids.update(document_ids)
            checkpoint()
        documents = self.document_service.get_documents_for_rag(document_ids, actor=actor)
        return build_chunks(grade=grade, documents=documents)

    def build_retriever(
        self,
        *,
        grade: int | None = None,
        document_ids: list[int] | None = None,
        actor=None,
    ) -> BaseRetriever:
        chunks = self._chunks(grade=grade, document_ids=document_ids or [], actor=actor)
        return self._retriever_for(chunks)

    @staticmethod
    def _retriever_for(chunks: list[dict]) -> BaseRetriever:
        try:
            embedder = resolve_embedder() if settings.VECTOR_RETRIEVAL_ENABLED else None
        except Exception as exc:
            logger.warning("Embedding setup failed, using BM25: %s", type(exc).__name__)
            embedder = None

        if settings.HYBRID_RETRIEVAL_ENABLED:
            return HybridRetriever(
                chunks,
                lexical=BM25Retriever(chunks) if settings.LEXICAL_RETRIEVAL_ENABLED else None,
                vector=EmbeddingRetriever(chunks, embedder, vector_store=shared_vector_store(embedder.name)) if embedder else None,
                reranker=RelevanceReranker() if settings.RERANKER_ENABLED else None,
            )

        if not settings.LEXICAL_RETRIEVAL_ENABLED:
            return HybridRetriever(chunks, vector=EmbeddingRetriever(chunks, embedder, vector_store=shared_vector_store(embedder.name)) if embedder else None)
        if embedder is None:
            return BM25Retriever(chunks)

        # A provider outage must degrade retrieval quality, not break generation.
        return FallbackRetriever(
            EmbeddingRetriever(
                chunks,
                embedder,
                vector_store=shared_vector_store(embedder.name),
            ),
            BM25Retriever(chunks),
        )

    def retriever_backend(self) -> str:
        """Which backend the next index build would use. For diagnostics."""
        try:
            vector = settings.VECTOR_RETRIEVAL_ENABLED and resolve_embedder() is not None
            if settings.HYBRID_RETRIEVAL_ENABLED:
                return "hybrid" if vector and settings.LEXICAL_RETRIEVAL_ENABLED else "embedding" if vector else "bm25" if settings.LEXICAL_RETRIEVAL_ENABLED else "disabled"
            return "embedding" if vector else "bm25" if settings.LEXICAL_RETRIEVAL_ENABLED else "disabled"
        except Exception:
            return "bm25"

    def index_stats(self, *, grade: int | None, document_ids: list[int], actor=None) -> dict:
        chunks = self._chunks(grade=grade, document_ids=document_ids, actor=actor)
        by_source: Counter = Counter(chunk["metadata"]["source_type"] for chunk in chunks)
        return {
            "chunk_count": len(chunks),
            "by_source_type": dict(by_source),
            "sample_chunks": [
                {"id": chunk["id"], "text": chunk["text"][:200], "metadata": chunk["metadata"]}
                for chunk in chunks[:3]
            ],
        }

    def query(
        self,
        *,
        query: str,
        grade: int | None = None,
        document_ids: list[int] | None = None,
        k: int | None = None,
        actor=None,
    ) -> list[dict]:
        results, _backend = self.query_with_backend(
            query=query,
            grade=grade,
            document_ids=document_ids,
            k=k,
            actor=actor,
        )
        return results

    def query_with_backend(
        self,
        *,
        query: str,
        grade: int | None = None,
        document_ids: list[int] | None = None,
        k: int | None = None,
        actor=None,
    ) -> tuple[list[dict], str]:
        """Return hits and the backend that actually answered this query."""
        retriever = self.build_retriever(
            grade=grade, document_ids=document_ids or [], actor=actor
        )
        raw_results = retriever.retrieve(query, k or settings.RAG_TOP_K)
        backend = self._active_backend(retriever)
        return self._format_results(raw_results), backend

    @staticmethod
    def _active_backend(retriever: BaseRetriever) -> str:
        if isinstance(retriever, HybridRetriever):
            return retriever.backend
        if isinstance(retriever, FallbackRetriever):
            return "bm25" if retriever.used_fallback else "embedding"
        if isinstance(retriever, EmbeddingRetriever):
            return "embedding"
        return "bm25"

    @staticmethod
    def _format_results(results: list[dict]) -> list[dict]:
        return [
            {
                "id": item["chunk"]["id"],
                "text": item["chunk"]["text"],
                "score": round(item["score"], 4),
                "metadata": {
                    **item["chunk"]["metadata"],
                    **({"retrieval": item["retrieval"]} if "retrieval" in item else {}),
                },
            }
            for item in results
        ]
