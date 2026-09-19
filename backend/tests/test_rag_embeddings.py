"""Embedding retrieval, vector caching, and the BM25 fallback path.

Everything here runs offline with a stub embedder — that is the contract: the
app must never require an API key to work.
"""

import logging

import pytest

from app.core.config import settings
from app.rag import (
    BM25Retriever,
    EmbeddingRetriever,
    FallbackRetriever,
    cosine_similarity,
    embeddings_configured,
    resolve_embedder,
)
from app.rag.embeddings import BaseEmbedder, GeminiEmbedder
from app.rag.vector_store import ChromaVectorStore, collection_name, open_vector_store
from app.services.knowledge_base_service import KnowledgeBaseService


class StubEmbedder(BaseEmbedder):
    """Deterministic 3-D vectors keyed by which topic word a text mentions."""

    name = "stub:v1"

    TOPICS = {"tuần hoàn": [1.0, 0.0, 0.0], "hô hấp": [0.0, 1.0, 0.0], "tiêu hóa": [0.0, 0.0, 1.0]}

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vectors = []
        for text in texts:
            lowered = (text or "").lower()
            match = next(
                (vector for topic, vector in self.TOPICS.items() if topic in lowered), None
            )
            vectors.append(list(match) if match else [0.0, 0.0, 0.0])
        return vectors


class ExplodingEmbedder(BaseEmbedder):
    name = "boom:v1"

    def embed(self, texts):
        raise RuntimeError("provider unreachable")


def make_chunks():
    return [
        {"id": "c1", "text": "Hệ tuần hoàn gồm tim và mạch máu.", "metadata": {"doc_id": 1}},
        {"id": "c2", "text": "Hệ hô hấp trao đổi khí ở phổi.", "metadata": {"doc_id": 1}},
        {"id": "c3", "text": "Hệ tiêu hóa hấp thụ chất dinh dưỡng.", "metadata": {"doc_id": 1}},
    ]


# ── cosine similarity ───────────────────────────────────────────────────────

def test_cosine_similarity_of_identical_vectors_is_one():
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_similarity_of_orthogonal_vectors_is_zero():
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


@pytest.mark.parametrize(
    ("left", "right"),
    [([], [1.0]), ([1.0], []), ([1.0, 2.0], [1.0]), ([0.0, 0.0], [1.0, 1.0])],
)
def test_cosine_similarity_degenerate_inputs_score_zero(left, right):
    assert cosine_similarity(left, right) == 0.0


# ── EmbeddingRetriever ──────────────────────────────────────────────────────

def test_embedding_retriever_ranks_the_semantically_closest_chunk_first():
    retriever = EmbeddingRetriever(make_chunks(), StubEmbedder())

    results = retriever.retrieve("Câu hỏi về hô hấp", k=2)

    assert results[0]["chunk"]["id"] == "c2"
    assert results[0]["score"] == pytest.approx(1.0)


def test_embedding_retriever_drops_unrelated_chunks():
    retriever = EmbeddingRetriever(make_chunks(), StubEmbedder())

    results = retriever.retrieve("Câu hỏi về tiêu hóa", k=5)

    # Only the matching topic has a non-zero cosine against the query vector.
    assert [item["chunk"]["id"] for item in results] == ["c3"]


def test_embedding_retriever_returns_nothing_for_an_unknown_topic():
    retriever = EmbeddingRetriever(make_chunks(), StubEmbedder())
    assert retriever.retrieve("chủ đề hoàn toàn khác", k=5) == []


def test_embedding_retriever_handles_an_empty_index_and_blank_query():
    assert EmbeddingRetriever([], StubEmbedder()).retrieve("hô hấp") == []
    assert EmbeddingRetriever(make_chunks(), StubEmbedder()).retrieve("   ") == []


def test_chunks_are_embedded_once_across_repeated_queries():
    embedder = StubEmbedder()
    retriever = EmbeddingRetriever(make_chunks(), embedder)

    retriever.retrieve("hô hấp")
    retriever.retrieve("tiêu hóa")

    # 1 batch for the chunks, then one single-text call per query.
    assert len(embedder.calls[0]) == 3
    assert [len(call) for call in embedder.calls[1:]] == [1, 1]


def test_embedding_retriever_respects_k():
    retriever = EmbeddingRetriever(make_chunks(), StubEmbedder())
    # Give every chunk the same vector so all three match; k must still cap it.
    retriever._vectors = [list(StubEmbedder.TOPICS["hô hấp"])] * 3
    assert len(retriever.retrieve("hô hấp", k=2)) == 2


# ── vector store caching ────────────────────────────────────────────────────

class FakeCollection:
    def __init__(self, seed=None):
        self.data = dict(seed or {})
        self.upserts = 0

    def get(self, ids, include=None):
        found = {chunk_id: self.data[chunk_id] for chunk_id in ids if chunk_id in self.data}
        return {"ids": list(found), "embeddings": list(found.values())}

    def upsert(self, ids, embeddings, documents, metadatas=None):
        self.upserts += 1
        self.metadatas = metadatas
        self.data.update(dict(zip(ids, embeddings, strict=True)))


def test_cached_vectors_are_not_re_embedded():
    store = ChromaVectorStore(FakeCollection())
    EmbeddingRetriever(make_chunks(), StubEmbedder(), vector_store=store).retrieve("warm cache")
    embedder = StubEmbedder()

    EmbeddingRetriever(make_chunks(), embedder, vector_store=store).retrieve("tuần hoàn")

    # Only the query was embedded; every chunk came from the cache.
    assert embedder.calls == [["tuần hoàn"]]


def test_missing_vectors_are_embedded_and_written_back():
    collection = FakeCollection()
    store = ChromaVectorStore(collection)

    EmbeddingRetriever(make_chunks(), StubEmbedder(), vector_store=store).retrieve("hô hấp")

    assert collection.upserts == 1
    assert {key.split(":")[0] for key in collection.data} == {"user_shared"}
    assert {key.split(":")[1] for key in collection.data} == {"c1", "c2", "c3"}


def test_a_broken_vector_store_does_not_break_retrieval():
    class BrokenCollection:
        def get(self, *args, **kwargs):
            raise RuntimeError("chroma down")

        def upsert(self, *args, **kwargs):
            raise RuntimeError("chroma down")

    retriever = EmbeddingRetriever(
        make_chunks(), StubEmbedder(), vector_store=ChromaVectorStore(BrokenCollection())
    )

    assert retriever.retrieve("hô hấp")[0]["chunk"]["id"] == "c2"


def test_collection_name_is_slugified_and_bounded():
    assert collection_name("gemini:text-embedding-004") == "rag-gemini-text-embedding-004"
    assert len(collection_name("x" * 200)) <= 63


def test_vector_store_is_absent_when_chroma_is_disabled(monkeypatch):
    monkeypatch.setattr(settings, "RAG_USE_CHROMA", False)
    assert open_vector_store("stub:v1") is None


# ── fallback ────────────────────────────────────────────────────────────────

def test_fallback_retriever_answers_from_bm25_when_embedding_fails(caplog):
    chunks = make_chunks()
    retriever = FallbackRetriever(
        EmbeddingRetriever(chunks, ExplodingEmbedder()), BM25Retriever(chunks)
    )

    with caplog.at_level(logging.WARNING, logger="app.rag"):
        results = retriever.retrieve("hô hấp phổi", k=3)

    assert retriever.used_fallback is True
    assert results and results[0]["chunk"]["id"] == "c2"
    assert "falling back to BM25" in caplog.text


def test_fallback_retriever_stops_retrying_the_broken_primary():
    chunks = make_chunks()
    embedder = ExplodingEmbedder()
    primary = EmbeddingRetriever(chunks, embedder)
    calls = {"n": 0}

    original = primary.retrieve

    def counting(query, k=5):
        calls["n"] += 1
        return original(query, k)

    primary.retrieve = counting
    retriever = FallbackRetriever(primary, BM25Retriever(chunks))

    retriever.retrieve("hô hấp")
    retriever.retrieve("tuần hoàn")
    retriever.retrieve("tiêu hóa")

    assert calls["n"] == 1


def test_fallback_retriever_exposes_chunks_for_the_empty_index_check():
    chunks = make_chunks()
    retriever = FallbackRetriever(
        EmbeddingRetriever(chunks, StubEmbedder()), BM25Retriever(chunks)
    )
    assert len(retriever.chunks) == 3


# ── embedder selection ──────────────────────────────────────────────────────

def test_embeddings_are_not_configured_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert embeddings_configured() is False


def test_auto_mode_falls_back_to_bm25_without_a_key(monkeypatch):
    monkeypatch.setattr(settings, "RAG_RETRIEVER", "auto")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")
    assert resolve_embedder() is None


def test_auto_mode_uses_embeddings_when_a_key_exists(monkeypatch):
    monkeypatch.setattr(settings, "RAG_RETRIEVER", "auto")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    assert isinstance(resolve_embedder(), GeminiEmbedder)


def test_bm25_mode_never_embeds_even_with_a_key(monkeypatch):
    monkeypatch.setattr(settings, "RAG_RETRIEVER", "bm25")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    assert resolve_embedder() is None


def test_embedding_mode_without_a_key_warns_and_falls_back(monkeypatch, caplog):
    monkeypatch.setattr(settings, "RAG_RETRIEVER", "embedding")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    with caplog.at_level(logging.WARNING, logger="app.rag"):
        assert resolve_embedder() is None

    assert "falling back to BM25" in caplog.text


# ── service wiring ──────────────────────────────────────────────────────────

def test_knowledge_base_uses_bm25_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "HYBRID_RETRIEVAL_ENABLED", False)
    monkeypatch.setattr(settings, "RAG_RETRIEVER", "auto")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "")

    retriever = KnowledgeBaseService._retriever_for(make_chunks())

    assert isinstance(retriever, BM25Retriever)
    assert KnowledgeBaseService().retriever_backend() == "bm25"


def test_knowledge_base_wraps_embeddings_with_a_bm25_fallback(monkeypatch):
    monkeypatch.setattr(settings, "HYBRID_RETRIEVAL_ENABLED", False)
    monkeypatch.setattr(settings, "RAG_RETRIEVER", "auto")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "RAG_USE_CHROMA", False)

    retriever = KnowledgeBaseService._retriever_for(make_chunks())

    assert isinstance(retriever, FallbackRetriever)
    assert isinstance(retriever.primary, EmbeddingRetriever)
    assert isinstance(retriever.fallback, BM25Retriever)
    assert KnowledgeBaseService().retriever_backend() == "embedding"


def test_knowledge_base_falls_back_when_embedder_setup_raises(monkeypatch):
    monkeypatch.setattr(settings, "HYBRID_RETRIEVAL_ENABLED", False)
    def boom():
        raise RuntimeError("bad config")

    monkeypatch.setattr("app.services.knowledge_base_service.resolve_embedder", boom)

    assert isinstance(KnowledgeBaseService._retriever_for(make_chunks()), BM25Retriever)
