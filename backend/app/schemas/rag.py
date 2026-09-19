from typing import Any

from pydantic import BaseModel, Field


class RagIndexRequest(BaseModel):
    grade: int | None = Field(default=None, ge=6, le=9)
    document_ids: list[int] = Field(default_factory=list, max_length=100)


class RagIndexResponse(BaseModel):
    chunk_count: int
    by_source_type: dict[str, int]
    document_ids: list[int]
    grade: int | None = None
    sample_chunks: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    # "embedding" or "bm25" — which backend answered. Useful when debugging why
    # retrieval quality changed after a config edit.
    retriever: str = "bm25"


class RagQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    grade: int | None = Field(default=None, ge=6, le=9)
    document_ids: list[int] = Field(default_factory=list, max_length=100)
    k: int | None = Field(default=None, ge=1, le=50)


class RagHit(BaseModel):
    id: str
    text: str
    score: float
    metadata: dict[str, Any]


class RagQueryResponse(BaseModel):
    query: str
    hits: list[RagHit]
    count: int
    retriever: str = "bm25"
