"""Embedding functions for the RAG index.

The app must stay fully usable with no provider key, so nothing here is
mandatory: ``resolve_embedder`` returns ``None`` when embeddings are not
configured or not reachable, and the caller falls back to BM25.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from app.core.config import settings
from app.services import ai_runtime

logger = logging.getLogger("app.rag")


class BaseEmbedder(ABC):
    """Turns texts into vectors. Implementations must be batch-friendly."""

    #: Identifies the vectors this embedder produces. Cached collections keyed
    #: by a different name are never mixed with these.
    name: str = "base"

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class GeminiEmbedder(BaseEmbedder):
    """Google `text-embedding-*` models via google-genai."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        self.model = model or settings.RAG_EMBEDDING_MODEL
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.name = f"gemini:{self.model}"

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=ai_runtime.timeout_ms()),
        )
        with ai_runtime.track_call("gemini", self.model, "embed_content") as call:
            response = client.models.embed_content(model=self.model, contents=texts)
            call["response"] = response

        vectors = [list(embedding.values or []) for embedding in (response.embeddings or [])]
        if len(vectors) != len(texts):
            raise ValueError(
                f"Embedding provider returned {len(vectors)} vectors for {len(texts)} texts"
            )
        return vectors


def embeddings_configured() -> bool:
    """True when an embedding provider *could* be used."""
    return bool(settings.RAG_EMBEDDING_MODEL and settings.GEMINI_API_KEY)


def resolve_embedder() -> BaseEmbedder | None:
    """The embedder to use, or None when the index should stay on BM25.

    `RAG_RETRIEVER` decides intent:
      * ``bm25``      — never embed.
      * ``embedding`` — embed; a misconfiguration is a real error worth seeing.
      * ``auto``      — embed only when a key is present (the default).
    """
    mode = (settings.RAG_RETRIEVER or "auto").strip().lower()

    if mode == "bm25":
        return None

    if mode == "embedding":
        if not embeddings_configured():
            logger.warning(
                "RAG_RETRIEVER=embedding but no embedding key/model is configured; "
                "falling back to BM25"
            )
            return None
        return GeminiEmbedder()

    return GeminiEmbedder() if embeddings_configured() else None
