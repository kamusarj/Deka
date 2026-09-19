"""Rank fusion and bounded context selection over the existing retrievers."""

from __future__ import annotations

import logging
import math
import re
import unicodedata
from abc import ABC, abstractmethod

from app.core.config import settings
from app.rag.retriever import BaseRetriever, tokenize
from app.services.ai.errors import AccountingError

logger = logging.getLogger("app.rag")


def normalize_query(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def reciprocal_rank_fusion(rankings: dict[str, list[dict]], constant: int = 60) -> list[dict]:
    """One vote per document per channel; one-based ranks and stable ties."""
    if constant < 1:
        raise ValueError("RRF constant must be positive")
    combined: dict[str, dict] = {}
    for channel, hits in rankings.items():
        seen = set()
        for rank, hit in enumerate(hits, 1):
            chunk_id = hit["chunk"]["id"]
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            item = combined.setdefault(chunk_id, {"chunk": hit["chunk"], "score": 0.0, "retrieval": {}})
            item["score"] += 1.0 / (constant + rank)
            item["retrieval"].update({f"{channel}_rank": rank, f"{channel}_score": hit["score"]})
    for item in combined.values():
        item["retrieval"]["rrf_score"] = item["score"]
    return sorted(combined.values(), key=lambda item: (-item["score"], str(item["chunk"]["id"])))


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        """Return the original candidates with a finite rerank_score."""
        raise NotImplementedError


class RelevanceReranker(Reranker):
    """Offline query coverage plus vector relevance; no additional provider call."""

    def rerank(self, query: str, candidates: list[dict]) -> list[dict]:
        terms = set(tokenize(query))
        result = []
        for hit in candidates:
            trace = dict(hit.get("retrieval", {}))
            coverage = len(terms & set(tokenize(hit["chunk"]["text"]))) / max(1, len(terms))
            vector_score = max(0.0, float(trace.get("vector_score", 0.0)))
            weight = settings.RAG_RERANK_LEXICAL_WEIGHT if "vector_score" in trace else 1.0
            score = weight * coverage + (1 - weight) * vector_score
            trace.update(rerank_score=score, reranker="local")
            result.append({**hit, "score": score, "retrieval": trace})
        return sorted(result, key=lambda hit: (-hit["score"], -hit["retrieval"].get("rrf_score", 0), str(hit["chunk"]["id"])))


def rerank_with_fallback(query: str, candidates: list[dict], reranker: Reranker) -> list[dict]:
    try:
        results = reranker.rerank(query, candidates)
        expected = {hit["chunk"]["id"] for hit in candidates}
        if len(results) != len(candidates) or {hit["chunk"]["id"] for hit in results} != expected:
            raise ValueError("Reranker changed the candidate set")
        if any(not math.isfinite(float(hit["score"])) for hit in results):
            raise ValueError("Non-finite reranking score")
        return results
    except Exception:
        logger.warning("Reranker failed; using local relevance fallback", exc_info=False)
        return RelevanceReranker().rerank(query, candidates)


def select_context(hits: list[dict], *, limit: int, token_budget: int) -> list[dict]:
    """Conservative UTF-8 budget, whole chunks, never truncate a source quotation.

    Counting bytes/3 intentionally overestimates many Vietnamese/ASCII tokenizers.
    It is a deterministic planning budget, not provider-specific token accounting.
    """
    if limit <= 0 or token_budget <= 0:
        return []
    selected, seen, used = [], set(), 0
    for hit in hits:
        normalized = normalize_query(hit["chunk"]["text"]).casefold()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cost = max(1, math.ceil(len(hit["chunk"]["text"].encode("utf-8")) / 3))
        if used + cost > token_budget:
            continue
        selected.append(hit)
        used += cost
        if len(selected) >= limit:
            break
    return selected


class HybridRetriever(BaseRetriever):
    def __init__(self, chunks, *, lexical=None, vector=None, reranker=None):
        self.chunks = chunks
        self.lexical = lexical
        self.vector = vector
        self.reranker = reranker
        self.vector_failed = False
        self.backend = "hybrid" if lexical and vector else "embedding" if vector else "bm25"

    def retrieve(self, query: str, k: int = 5) -> list[dict]:
        query = normalize_query(query)
        if not query or k <= 0:
            return []
        count = max(k, settings.RAG_CANDIDATE_LIMIT)
        rankings = {}
        if self.lexical:
            rankings["lexical"] = self.lexical.retrieve(query, count)
        if self.vector and not self.vector_failed:
            try:
                rankings["vector"] = self.vector.retrieve(query, count)
            except AccountingError:
                raise
            except Exception:
                self.vector_failed = True
                logger.warning("Vector retrieval failed; retaining available lexical candidates")
        self.backend = "hybrid" if len(rankings) == 2 else "embedding" if "vector" in rankings else "bm25" if "lexical" in rankings else "disabled"
        hits = reciprocal_rank_fusion(rankings, settings.RAG_RRF_K)
        if self.reranker:
            hits = rerank_with_fallback(query, hits, self.reranker)
        return select_context(hits, limit=k, token_budget=settings.RAG_CONTEXT_TOKEN_BUDGET)
