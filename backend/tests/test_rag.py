"""Phase 2 - Part 3: RAG knowledge base offline (BM25)."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.rag import BM25Retriever, FallbackRetriever, chunk_curriculum, chunk_document, chunk_text
from app.schemas.exam import FullExamRequest
from app.services.document_service import DocumentService
from app.services.knowledge_base_service import KnowledgeBaseService


def make_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document

    document = Document()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_exam_service():
    from app.services.exam_service import ExamService

    service = ExamService()
    for agent_name in (
        "resource_agent",
        "matrix_agent",
        "spec_agent",
        "question_agent",
        "answer_agent",
        "validator_agent",
        "verification_agent",
    ):
        getattr(service, agent_name).has_ai = False
    return service


def exam_payload(**overrides):
    payload = {
        "school": "THCS Nguyễn Du",
        "grade": 8,
        "subject": "Khoa học tự nhiên",
        "exam_type": "Giữa học kì I",
        "duration_minutes": 45,
        "school_year": "2025-2026",
        "total_score": 10,
        "curriculum": [
            {
                "topic": "Phản ứng hóa học",
                "periods": 10,
                "achievements": ["Trình bày được khái niệm phản ứng hóa học."],
            },
            {
                "topic": "Dung dịch và nồng độ",
                "periods": 8,
                "achievements": ["Tính được nồng độ phần trăm của dung dịch."],
            },
        ],
        "difficulty_ratio": {"nhan_biet": 30, "thong_hieu": 40, "van_dung": 30},
    }
    payload.update(overrides)
    return payload


# ── Chunking ────────────────────────────────────────────────────


def test_chunk_curriculum_one_chunk_per_objective():
    chunks = chunk_curriculum(8)
    assert len(chunks) > 0
    assert all(chunk["metadata"]["source_type"] == "local_json" for chunk in chunks)
    assert all(chunk["metadata"]["objective_id"] for chunk in chunks)
    # Số chunk = tổng số learning objective.
    from app.services.curriculum_service import get_all_topics

    total_objectives = sum(
        len(topic.get("learning_objectives", [])) for topic in get_all_topics(8)
    )
    assert len(chunks) == total_objectives


def test_chunk_text_splits_long_text():
    text = " ".join(f"từ{i}" for i in range(400))
    pieces = chunk_text(text, chunk_size=100)
    assert len(pieces) > 1
    assert all(len(piece) <= 130 for piece in pieces)  # ranh giới từ, xấp xỉ chunk_size


def test_chunk_document_preserves_pdf_page_locator():
    document = {
        "id": 4,
        "filename": "SGK Hoa 11.pdf",
        "file_type": "pdf",
        "grade": 11,
        "extracted_text": "Cân bằng hóa học\n\nNguyên lí Le Chatelier",
        "parsed_data": {
            "page_spans": [
                {"page": 6, "start": 0, "end": 16},
                {"page": 7, "start": 18, "end": 40},
            ]
        },
    }

    chunks = chunk_document(document, chunk_size=100)

    assert [chunk["metadata"]["source_page"] for chunk in chunks] == [6, 7]
    assert all(chunk["metadata"]["source_name"] == "SGK Hoa 11.pdf" for chunk in chunks)


# ── Retriever ───────────────────────────────────────────────────


def test_bm25_ranks_relevant_chunk_first():
    chunks = [
        {"id": "c1", "text": "Quang hợp ở thực vật và diệp lục", "metadata": {}},
        {"id": "c2", "text": "Phản ứng hóa học và dấu hiệu nhận biết chất mới", "metadata": {}},
        {"id": "c3", "text": "Nồng độ dung dịch và cách pha chế", "metadata": {}},
    ]
    retriever = BM25Retriever(chunks)
    hits = retriever.retrieve("dấu hiệu phản ứng hóa học", k=3)
    assert hits[0]["chunk"]["id"] == "c2"
    assert hits[0]["score"] > 0


def test_bm25_returns_empty_for_no_match():
    retriever = BM25Retriever([{"id": "c1", "text": "alpha beta gamma", "metadata": {}}])
    assert retriever.retrieve("hoàn toàn không liên quan", k=5) == []


# ── Sinh đề: có/không tài liệu ─────────────────────────────────


@pytest.mark.asyncio
async def test_full_exam_without_docs_keeps_local_json_source():
    service = make_exam_service()
    exam = await service.generate_full_exam(FullExamRequest(**exam_payload()))
    assert all(q["source"]["source_type"] == "local_json" for q in exam.questions)
    assert exam.validation["passed"] is True


@pytest.mark.asyncio
async def test_full_exam_with_docs_marks_rag_retrieval_and_passes_validation():
    document_service = DocumentService()
    doc = document_service.save_document(
        filename="tai_lieu_gv.docx",
        data=make_docx_bytes(
            [
                "Phản ứng hóa học là quá trình biến đổi chất, có dấu hiệu nhận biết rõ ràng.",
                "Dung dịch và nồng độ: cách tính nồng độ phần trăm của dung dịch trong thực tiễn.",
            ]
        ),
        grade=8,
    )
    try:
        service = make_exam_service()
        exam = await service.generate_full_exam(
            FullExamRequest(**exam_payload(use_uploaded_docs=[doc.id]))
        )
        source_types = {q["source"]["source_type"] for q in exam.questions}
        assert "rag_retrieval" in source_types
        rag_questions = [q for q in exam.questions if q["source"]["source_type"] == "rag_retrieval"]
        assert rag_questions[0]["source"]["doc_id"] == doc.id
        assert exam.validation["passed"] is True
        assert exam.resource_package["use_uploaded_docs"] == [doc.id]
    finally:
        document_service.delete_document(doc.id)


# ── KnowledgeBaseService + routes ───────────────────────────────


def test_knowledge_base_query_combines_curriculum_and_docs():
    service = KnowledgeBaseService()
    hits = service.query(query="phản ứng hóa học dấu hiệu", grade=8, k=3)
    assert hits
    assert hits[0]["score"] > 0
    assert hits[0]["metadata"]["source_type"] == "local_json"


def test_query_reports_bm25_after_embedding_runtime_fallback(monkeypatch):
    chunks = [
        {
            "id": "c1",
            "text": "phản ứng hóa học tạo thành chất mới",
            "metadata": {"source_type": "local_json"},
        }
    ]
    primary = type(
        "BrokenEmbeddingRetriever",
        (),
        {"retrieve": lambda self, query, k: (_ for _ in ()).throw(RuntimeError("bad key"))},
    )()
    retriever = FallbackRetriever(primary, BM25Retriever(chunks))
    service = KnowledgeBaseService()
    monkeypatch.setattr(service, "build_retriever", lambda **_kwargs: retriever)

    hits, backend = service.query_with_backend(query="phản ứng hóa học")

    assert hits
    assert backend == "bm25"


def test_rag_routes_index_and_query(auth_context):
    client = TestClient(app)

    index = client.post("/api/rag/index", json={"grade": 8}, headers=auth_context["headers"])
    assert index.status_code == 200
    body = index.json()
    assert body["chunk_count"] > 0
    assert body["by_source_type"].get("local_json", 0) > 0

    query = client.post(
        "/api/rag/query",
        json={"query": "nồng độ dung dịch", "grade": 8, "k": 3},
        headers=auth_context["headers"],
    )
    assert query.status_code == 200
    result = query.json()
    assert result["count"] >= 1
    assert result["hits"][0]["score"] > 0
