"""ChromaDB-backed cache for chunk embeddings.

Embedding the same chunk on every request would be slow and expensive, so
vectors are persisted and looked up by chunk id. Chroma is optional: when it
cannot be reached the retriever simply embeds in memory for that request.
"""

from __future__ import annotations

import logging
import re
from collections import OrderedDict
from threading import Lock

from app.core.config import settings

logger = logging.getLogger("app.rag")

_COLLECTION_SAFE = re.compile(r"[^A-Za-z0-9_-]+")
_memory_vectors = OrderedDict()
_memory_lock = Lock()


class MemoryVectorStore:
    """Bounded fallback cache shared by document and bank retrieval."""

    def __init__(self, namespace):
        self.namespace = namespace

    def fetch(self, ids):
        with _memory_lock:
            result = {}
            for key in ids:
                cache_key = (self.namespace, key)
                if cache_key in _memory_vectors:
                    result[key] = list(_memory_vectors[cache_key])
                    _memory_vectors.move_to_end(cache_key)
            return result

    def store(self, ids, vectors, documents):
        with _memory_lock:
            for key, vector in zip(ids, vectors, strict=True):
                cache_key = (self.namespace, key)
                _memory_vectors[cache_key] = list(vector)
                _memory_vectors.move_to_end(cache_key)
            while len(_memory_vectors) > settings.RAG_MEMORY_CACHE_SIZE:
                _memory_vectors.popitem(last=False)


def shared_vector_store(embedder_name):
    return open_vector_store(embedder_name) or MemoryVectorStore(embedder_name)


def collection_name(embedder_name: str) -> str:
    """Chroma collection names allow a narrow character set and 3-63 chars."""
    slug = _COLLECTION_SAFE.sub("-", embedder_name).strip("-").lower() or "default"
    return f"rag-{slug}"[:63]


class ChromaVectorStore:
    """Chunk-id -> vector cache. Every method degrades to a no-op on failure."""

    def __init__(self, collection):
        self._collection = collection

    def fetch(self, ids: list[str]) -> dict[str, list[float]]:
        if not ids:
            return {}
        try:
            found = self._collection.get(ids=ids, include=["embeddings"])
        except Exception as exc:
            logger.warning("Chroma lookup failed, embedding in memory instead: %s", type(exc).__name__)
            return {}

        found_ids = list(found.get("ids") or [])
        embeddings = found.get("embeddings")
        if embeddings is None:
            return {}
        return {
            chunk_id: list(vector)
            for chunk_id, vector in zip(found_ids, embeddings, strict=True)
            if vector is not None and len(vector) > 0
        }

    def store(self, ids: list[str], vectors: list[list[float]], documents: list[str]) -> None:
        if not ids:
            return
        try:
            self._collection.upsert(ids=ids, embeddings=vectors, documents=documents,
                                    metadatas=[{"user_id": key.split(":", 1)[0].removeprefix("user_")}
                                               for key in ids])
        except Exception as exc:
            # A cache miss is not a failure — the vectors are already computed.
            logger.warning("Chroma upsert failed, continuing without cache: %s", type(exc).__name__)


def open_vector_store(embedder_name: str) -> ChromaVectorStore | None:
    """Open the cache, or return None when Chroma is off or unreachable."""
    if not settings.RAG_USE_CHROMA:
        return None

    try:
        import chromadb

        if settings.CHROMA_HOST and settings.RAG_CHROMA_MODE == "http":
            client = chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        else:
            client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)

        collection = client.get_or_create_collection(
            name=collection_name(embedder_name),
            metadata={"hnsw:space": "cosine"},
        )
        return ChromaVectorStore(collection)
    except Exception as exc:
        logger.warning("ChromaDB unavailable, embeddings will not be cached: %s", type(exc).__name__)
        return None


def delete_document_vectors(document_id, owner_user_id):
    """Exact legacy prefix mapping; never delete an entire owner/collection."""
    prefix = f'user_{owner_user_id}:doc_{document_id}_'
    with _memory_lock:
        for namespace, key in list(_memory_vectors):
            if key.startswith(prefix):
                _memory_vectors.pop((namespace, key), None)
    if not settings.RAG_USE_CHROMA:
        return
    import chromadb
    client = (chromadb.HttpClient(host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
              if settings.RAG_CHROMA_MODE == 'http' else chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR))
    for entry in client.list_collections():
        name = entry if isinstance(entry, str) else entry.name
        if not name.startswith('rag-'):
            continue
        collection = client.get_collection(name)
        offset = 0
        while True:
            page = collection.get(where={'user_id': str(owner_user_id)}, limit=500, offset=offset, include=[])
            ids = page.get('ids', [])
            if not ids:
                break
            matches = [key for key in ids if key.startswith(prefix)]
            if matches:
                collection.delete(ids=matches)
            offset += len(ids) - len(matches)
            if len(ids) < 500:
                break
