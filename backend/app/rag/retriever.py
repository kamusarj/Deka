"""Retriever cho RAG.

`BM25Retriever` chạy offline, thuần Python, tất định — không cần API key và
luôn là fallback khi không cấu hình embeddings.
`EmbeddingRetriever` dùng embeddings (Gemini) + cache vector trong ChromaDB,
**cùng chữ ký `retrieve(query, k)`** nên nơi gọi không phải sửa gì.
"""

import logging
import math
import re
from hashlib import sha256
from abc import ABC, abstractmethod
from collections import Counter
from app.services.ai.errors import AccountingError

logger = logging.getLogger("app.rag")

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tách từ đơn giản, tất định: lowercase + lấy các cụm ký tự chữ/số (Unicode)."""
    return _TOKEN_RE.findall((text or "").lower())


class BaseRetriever(ABC):
    """Interface chung. Mọi retriever trả về list[{"chunk", "score"}] giảm dần theo score."""

    @abstractmethod
    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        raise NotImplementedError


class BM25Retriever(BaseRetriever):
    def __init__(self, chunks: list[dict], *, k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1 = k1
        self.b = b

        self._doc_tokens = [tokenize(chunk["text"]) for chunk in self.chunks]
        self._doc_freqs = [Counter(tokens) for tokens in self._doc_tokens]
        self._doc_len = [len(tokens) for tokens in self._doc_tokens]
        self._avgdl = (sum(self._doc_len) / len(self._doc_len)) if self._doc_len else 0.0

        df: Counter = Counter()
        for freqs in self._doc_freqs:
            df.update(freqs.keys())
        self._n = len(self.chunks)
        # IDF kiểu BM25+ (cộng 1 trong log) để luôn không âm.
        self._idf = {
            term: math.log(1 + (self._n - count + 0.5) / (count + 0.5))
            for term, count in df.items()
        }

    def _score(self, query_terms: list[str], index: int) -> float:
        if self._avgdl == 0:
            return 0.0
        freqs = self._doc_freqs[index]
        length = self._doc_len[index]
        score = 0.0
        for term in query_terms:
            tf = freqs.get(term, 0)
            if tf == 0:
                continue
            idf = self._idf.get(term, 0.0)
            denominator = tf + self.k1 * (1 - self.b + self.b * length / self._avgdl)
            score += idf * (tf * (self.k1 + 1)) / denominator
        return score

    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        query_terms = tokenize(query)
        scored = [
            {"chunk": chunk, "score": self._score(query_terms, index), "_index": index}
            for index, chunk in enumerate(self.chunks)
        ]
        # Bỏ chunk không khớp; tie-break tất định theo vị trí gốc.
        relevant = [item for item in scored if item["score"] > 0]
        relevant.sort(key=lambda item: (-item["score"], item["_index"]))
        return [{"chunk": item["chunk"], "score": item["score"]} for item in relevant[:k]]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


class EmbeddingRetriever(BaseRetriever):
    """Semantic retrieval over chunk embeddings.

    Vectors are read from `vector_store` when available and only the missing
    chunks are sent to the embedder, so repeated queries over the same
    documents cost nothing extra.

    Scores are cosine similarities in [-1, 1]; only positive matches are
    returned, matching BM25Retriever's "no match means no result" contract.
    """

    #: Similarity below this is treated as noise rather than a match.
    MIN_SCORE = 0.0

    def __init__(self, chunks: list[dict], embedder, *, vector_store=None):
        self.chunks = list(chunks)
        self.embedder = embedder
        self.vector_store = vector_store
        self._vectors: list[list[float]] | None = None

    def _ensure_vectors(self) -> list[list[float]]:
        if self._vectors is not None:
            return self._vectors

        # A teacher edit must never reuse a vector belonging to older content.
        ids = [f"user_{chunk.get('metadata', {}).get('user_id', 'shared')}:{chunk['id']}:{sha256(chunk['text'].encode()).hexdigest()[:24]}" for chunk in self.chunks]
        cached = self.vector_store.fetch(ids) if self.vector_store else {}

        keyed = list(zip(ids, self.chunks, strict=True))
        missing = [(key, chunk) for key, chunk in keyed if key not in cached]
        if missing:
            from app.core.config import settings
            fresh = []
            for start in range(0, len(missing), settings.RAG_EMBEDDING_BATCH_SIZE):
                fresh.extend(self.embedder.embed([chunk["text"] for _, chunk in missing[start:start + settings.RAG_EMBEDDING_BATCH_SIZE]]))
            for (key, _chunk), vector in zip(missing, fresh, strict=True):
                cached[key] = vector
            if self.vector_store:
                self.vector_store.store(
                    [key for key, _ in missing],
                    [cached[key] for key, _ in missing],
                    [chunk["text"] for _, chunk in missing],
                )

        self._vectors = [cached.get(key, []) for key in ids]
        return self._vectors

    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        if not self.chunks or not (query or "").strip():
            return []

        vectors = self._ensure_vectors()
        query_vector = self.embedder.embed_query(query)

        scored = [
            {
                "chunk": chunk,
                "score": cosine_similarity(query_vector, vector),
                "_index": index,
            }
            for index, (chunk, vector) in enumerate(
                zip(self.chunks, vectors, strict=True)
            )
        ]
        relevant = [item for item in scored if item["score"] > self.MIN_SCORE]
        relevant.sort(key=lambda item: (-item["score"], item["_index"]))
        return [{"chunk": item["chunk"], "score": item["score"]} for item in relevant[:k]]


class FallbackRetriever(BaseRetriever):
    """Try the primary retriever; on failure answer from the fallback.

    A provider outage mid-generation must degrade retrieval quality, not break
    exam generation. Once the primary has failed the fallback is used for the
    rest of this retriever's life, so one broken index does not retry on every
    single specification row.
    """

    def __init__(self, primary: BaseRetriever, fallback: BaseRetriever):
        self.primary = primary
        self.fallback = fallback
        self.used_fallback = False

    @property
    def chunks(self) -> list[dict]:
        return self.fallback.chunks

    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        if self.used_fallback:
            return self.fallback.retrieve(query, k)
        try:
            return self.primary.retrieve(query, k)
        except AccountingError:
            raise
        except Exception as exc:
            self.used_fallback = True
            logger.warning("Embedding retrieval failed, falling back to BM25: %s", type(exc).__name__)
            return self.fallback.retrieve(query, k)
