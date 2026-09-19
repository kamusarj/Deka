"""Opt-in RAG grounding of a specification against teacher-uploaded documents."""

from __future__ import annotations

import re
import unicodedata

from app.services.curriculum import load_curriculum
from app.core.config import settings


def _normalise(value) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip(" .,:;!?-")


def _local_context(grade: int, spec: dict) -> dict:
    """Retrieve server-owned topic context without calling the model.

    Curriculum JSON is a scope source, not a textbook. We therefore expose its
    summary and objective keywords as context while retaining an explicit
    `curriculum_scope` grounding level instead of pretending it proves a
    scientific answer.
    """

    curriculum = load_curriculum(grade)
    topic_name = _normalise(spec.get("topic"))
    achievement = _normalise(spec.get("achievement"))
    topic = next(
        (
            item for item in curriculum.get("topics", [])
            if _normalise(item.get("name")) == topic_name
        ),
        None,
    )
    if not topic:
        return {}
    objective = next(
        (
            item for item in topic.get("learning_objectives", [])
            if _normalise(item.get("text")) == achievement
        ),
        None,
    )
    summary = str(topic.get("summary") or "").strip()
    keywords = [str(value).strip() for value in (objective or {}).get("keywords", []) if str(value).strip()]
    context_parts = [summary]
    if keywords:
        context_parts.append(f"Thuật ngữ trọng tâm: {', '.join(keywords)}.")
    return {
        "topic_id": topic.get("id"),
        "objective_id": (objective or {}).get("id"),
        "topic_summary": summary or None,
        "objective_keywords": keywords,
        "source_context": " ".join(part for part in context_parts if part),
    }


def apply_local_sources(specification, *, grade: int) -> list[dict]:
    """Attach an explicit controlled-curriculum locator before optional RAG."""
    enriched = []
    for spec in specification:
        topic = str(spec.get("topic") or "").strip()
        achievement = str(spec.get("achievement") or "").strip()
        local_context = _local_context(grade, spec)
        enriched.append(
            {
                **spec,
                **local_context,
                "source": {
                    "source_type": "local_json",
                    "source_name": f"khtn_grade_{grade}.json",
                    "source_page": None,
                    "source_section": (
                        f"Chủ đề: {topic} · Yêu cầu cần đạt" if topic else "Yêu cầu cần đạt"
                    ),
                    "source_excerpt": achievement or None,
                    "confidence_score": 1.0,
                },
            }
        )
    return enriched


def apply_rag_sources(
    knowledge_base,
    specification,
    *,
    document_ids,
    actor=None,
) -> list[dict]:
    """Tag specs whose content matches an uploaded document.

    Only uploaded documents are indexed, so a hit means the content really came
    from the teacher's own material. With no documents — or no match — the spec
    is returned untouched and downstream keeps the default `local_json` source.
    """
    if not document_ids:
        return specification

    retriever = knowledge_base.build_retriever(
        grade=None, document_ids=document_ids, actor=actor,
    )
    if not retriever.chunks:
        return specification

    enriched = []
    for spec in specification:
        # Mandatory calculations were planned against an exact local objective
        # and its grade-aware formula allowlist.  A merely similar RAG hit must
        # not replace that authoritative capability with weaker text matching.
        if spec.get("requires_calculation"):
            enriched.append(spec)
            continue
        query = " ".join(
            str(part)
            for part in (
                spec.get("topic"),
                spec.get("knowledge_unit"),
                spec.get("achievement"),
            )
            if part
        )
        hits = retriever.retrieve(query, k=settings.RAG_TOP_K)
        if not hits:
            enriched.append(spec)
            continue
        chunk = hits[0]["chunk"]
        metadata = chunk["metadata"]
        enriched.append(
            {
                **spec,
                "rag_context": chunk["text"],
                "source_context": "\n\n".join(hit["chunk"]["text"] for hit in hits),
                "retrieved_context": [{"text": hit["chunk"]["text"], "chunk_id": hit["chunk"]["id"], "metadata": hit["chunk"]["metadata"]} for hit in hits],
                "source": {
                    "source_type": "rag_retrieval",
                    "source_name": metadata.get("source_name"),
                    "source_page": metadata.get("source_page"),
                    "source_section": metadata.get("source_section"),
                    "source_excerpt": chunk["text"],
                    "confidence_score": round(float(hits[0]["score"]), 4),
                    "doc_id": metadata.get("doc_id"),
                    "retrieved_chunk_id": chunk["id"],
                },
            }
        )
    return enriched
