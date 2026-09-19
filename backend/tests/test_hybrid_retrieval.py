import math

import pytest

from app.core.config import settings
from app.rag.hybrid import HybridRetriever, RelevanceReranker, reciprocal_rank_fusion, rerank_with_fallback, select_context
from app.rag.retriever import BM25Retriever, EmbeddingRetriever
from app.services.knowledge_base_service import KnowledgeBaseService


def hit(key, text="năng lượng ánh sáng", score=1):
    return {"chunk": {"id": key, "text": text, "metadata": {"doc_id": 4, "source_page": 2}}, "score": score}


def test_rrf_one_based_ranks_and_combined_evidence():
    result = reciprocal_rank_fusion({"lexical": [hit("a"), hit("b")], "vector": [hit("b"), hit("c")]}, 60)
    assert [h["chunk"]["id"] for h in result] == ["b", "a", "c"]
    assert result[0]["score"] == pytest.approx(1 / 62 + 1 / 61)
    assert result[0]["retrieval"]["lexical_rank"] == 2
    assert result[0]["retrieval"]["vector_rank"] == 1
    assert result[0]["chunk"]["metadata"]["source_page"] == 2


def test_rrf_duplicates_and_empty_inputs():
    assert reciprocal_rank_fusion({}) == []
    assert reciprocal_rank_fusion({"lexical": [hit("a"), hit("a")]})[0]["score"] == pytest.approx(1 / 61)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion({}, 0)


class BrokenReranker:
    def rerank(self, query, candidates):
        raise RuntimeError("offline")


@pytest.mark.parametrize("invalid", [None, [], [{**hit("a"), "score": math.nan}]])
def test_reranker_fallback_retains_candidates(invalid):
    class InvalidReranker:
        def rerank(self, query, candidates):
            return invalid
    candidates = reciprocal_rank_fusion({"lexical": [hit("a"), hit("b", "không liên quan")]})
    result = rerank_with_fallback("ánh sáng", candidates, InvalidReranker())
    assert len(result) == 2
    assert result[0]["chunk"]["id"] == "a"
    assert result[0]["retrieval"]["reranker"] == "local"


def test_reranker_failure_and_budget_deduplication():
    candidates = reciprocal_rank_fusion({"lexical": [hit("a"), hit("b"), hit("huge", "x" * 4000)]})
    ranked = rerank_with_fallback("ánh sáng", candidates, BrokenReranker())
    assert [h["chunk"]["id"] for h in select_context(ranked, limit=5, token_budget=64)] == ["a"]


class Embedder:
    name = "hybrid-test"
    def embed(self, texts):
        return [[1, 0] if "lá" in text.casefold() else [0, 1] for text in texts]
    def embed_query(self, text):
        return [1, 0]


def test_hybrid_returns_lexical_and_semantic_candidates():
    chunks = [hit("a", "Lá cây thu nhận ánh sáng")["chunk"], hit("b", "quang hợp tạo glucose")["chunk"]]
    engine = HybridRetriever(chunks, lexical=BM25Retriever(chunks), vector=EmbeddingRetriever(chunks, Embedder()), reranker=RelevanceReranker())
    result = engine.retrieve("quang hợp")
    assert {h["chunk"]["id"] for h in result} == {"a", "b"}
    assert engine.backend == "hybrid"
    assert all("rrf_score" in h["retrieval"] and "rerank_score" in h["retrieval"] for h in result)


def test_hybrid_vector_failure_is_attempted_only_once():
    class Broken:
        calls = 0
        def retrieve(self, query, k):
            self.calls += 1
            raise RuntimeError("offline")
    broken = Broken()
    chunks = [hit("a")["chunk"]]
    engine = HybridRetriever(chunks, lexical=BM25Retriever(chunks), vector=broken)
    assert engine.retrieve("ánh sáng")
    assert engine.retrieve("ánh sáng")
    assert broken.calls == 1 and engine.backend == "bm25"


def test_config_can_disable_each_channel_and_reranker(monkeypatch):
    monkeypatch.setattr(settings, "HYBRID_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(settings, "LEXICAL_RETRIEVAL_ENABLED", False)
    monkeypatch.setattr(settings, "VECTOR_RETRIEVAL_ENABLED", False)
    monkeypatch.setattr(settings, "RERANKER_ENABLED", False)
    engine = KnowledgeBaseService._retriever_for([hit("a")["chunk"]])
    assert engine.retrieve("ánh sáng") == []
    assert engine.backend == "disabled"


def test_cache_does_not_reuse_vectors_after_text_changes():
    class Cache:
        values = {}
        def fetch(self, ids):
            return {key: self.values[key] for key in ids if key in self.values}
        def store(self, ids, vectors, documents):
            self.values.update(zip(ids, vectors))
    cache = Cache()
    first = EmbeddingRetriever([hit("a", "lá")["chunk"]], Embedder(), vector_store=cache)
    assert first.retrieve("lá")
    second = EmbeddingRetriever([hit("a", "phổi")["chunk"]], Embedder(), vector_store=cache)
    assert second.retrieve("lá") == []
    assert len(cache.values) == 2
