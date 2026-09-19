from types import SimpleNamespace as NS
import pytest
from fastapi import HTTPException
from app.models.document import UploadedDocument
from app.rag.chunking import chunk_document
from app.rag.retriever import EmbeddingRetriever
from app.rag.vector_store import ChromaVectorStore
from app.services.document_service import DocumentService
from app.services.knowledge_base_service import KnowledgeBaseService
from tests.test_ai_credits import accounts
from tests.test_rag_embeddings import FakeCollection, StubEmbedder


def test_owner_is_preserved_in_chunks_and_vector_records():
    doc = {'id': 7, 'owner_user_id': 12, 'filename': 'private.pdf', 'extracted_text': 'hô hấp', 'grade': 8}
    chunks = chunk_document(doc)
    assert all(c['metadata']['user_id'] == 12 for c in chunks)
    collection = FakeCollection()
    EmbeddingRetriever(chunks, StubEmbedder(), vector_store=ChromaVectorStore(collection)).retrieve('hô hấp')
    assert all(key.startswith('user_12:') for key in collection.data)
    assert collection.metadatas == [{'user_id': '12'}]


def test_private_documents_filtered_before_warm_vector_cache(accounts):
    with accounts.sessions.begin() as db:
        for user_id in (1, 2):
            db.add(UploadedDocument(id=user_id, owner_user_id=user_id, filename=f'{user_id}.txt',
                    stored_filename=f'{user_id}.txt', file_type='txt', extracted_text='hô hấp', grade=8))
    documents = DocumentService()
    documents.SessionLocal = accounts.sessions
    owner = NS(id=1, role='teacher', school_id=None)
    other = NS(id=2, role='teacher', school_id=None)
    chunks = chunk_document(documents.get_documents_for_rag([1], actor=owner)[0])
    store = ChromaVectorStore(FakeCollection())
    EmbeddingRetriever(chunks, StubEmbedder(), vector_store=store).retrieve('hô hấp')
    knowledge = KnowledgeBaseService()
    knowledge.document_service = documents
    with pytest.raises(HTTPException) as caught:
        knowledge.build_retriever(grade=8, document_ids=[1], actor=other)
    assert caught.value.status_code == 404
    own_chunks = chunk_document(documents.get_documents_for_rag([2], actor=other)[0])
    hits = EmbeddingRetriever(own_chunks, StubEmbedder(), vector_store=store).retrieve('hô hấp')
    assert hits and {hit['chunk']['metadata']['user_id'] for hit in hits} == {2}
