"""Cắt nguồn kiến thức thành chunk kèm metadata cho RAG (Phase 2).

Hai nguồn:
- Curriculum local JSON (objective theo topic) -> source_type "local_json".
- Tài liệu giáo viên upload (extracted_text) -> source_type "uploaded_file".

Hàm thuần, không gọi AI. Mỗi chunk là dict:
    {"id": str, "text": str, "metadata": {...}}
"""

from app.core.config import settings
from app.services.curriculum import get_all_topics


def _make_chunk(chunk_id: str, text: str, **metadata) -> dict:
    return {"id": chunk_id, "text": text, "metadata": metadata}


def chunk_text(text: str, chunk_size: int | None = None) -> list[str]:
    """Cắt văn bản dài thành các đoạn ~chunk_size ký tự, tôn trọng ranh giới từ."""
    chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
    words = (text or "").split()
    if not words:
        return []

    chunks = []
    current: list[str] = []
    current_len = 0
    for word in words:
        # +1 cho khoảng trắng nối từ.
        if current and current_len + len(word) + 1 > chunk_size:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(word)
        current_len += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def chunk_curriculum(grade: int) -> list[dict]:
    """Mỗi learning objective của mỗi topic trở thành một chunk."""
    chunks = []
    source_name = f"khtn_grade_{grade}.json"
    for topic in get_all_topics(grade):
        topic_name = topic.get("name", "")
        for objective in topic.get("learning_objectives", []):
            keywords = " ".join(objective.get("keywords", []))
            text = f"{topic_name}. {objective.get('text', '')} {keywords}".strip()
            chunks.append(
                _make_chunk(
                    f"cur_{grade}_{topic.get('id')}_{objective.get('id')}",
                    text,
                    source_type="local_json",
                    source_name=source_name,
                    topic=topic_name,
                    doc_id=None,
                    objective_id=objective.get("id"),
                    grade=grade,
                )
            )
    return chunks


def chunk_document(document, chunk_size: int | None = None) -> list[dict]:
    """Cắt extracted_text của một tài liệu upload thành nhiều chunk.

    `document` có thể là model UploadedDocument hoặc dict tương đương
    (cần có: id, filename, extracted_text, grade).
    """
    get = document.get if isinstance(document, dict) else lambda key, default=None: getattr(document, key, default)
    doc_id = get("id")
    filename = get("filename", f"doc_{doc_id}")
    text = get("extracted_text", "") or ""
    grade = get("grade")
    file_type = get("file_type")
    parsed_data = get("parsed_data", {}) or {}

    chunks = []
    chunk_index = 0

    def append_parts(spans, locator):
        nonlocal chunk_index
        for span in spans:
            piece_text = text[int(span.get("start", 0)):int(span.get("end", 0))]
            for piece in chunk_text(piece_text, chunk_size):
                location = locator(span)
                chunks.append(
                    _make_chunk(
                        f"doc_{doc_id}_{chunk_index}",
                        piece,
                        source_type="uploaded_file",
                        source_name=filename,
                        source_page=location.get("source_page"),
                        source_section=location.get("source_section"),
                        topic=None,
                        doc_id=doc_id, user_id=get("owner_user_id"),
                        chunk_index=chunk_index,
                        grade=grade,
                    )
                )
                chunk_index += 1

    if parsed_data.get("blocks"):
        for block in parsed_data["blocks"]:
            # Tables and formulas are atomic retrieval units. Splitting on
            # whitespace would destroy row alignment and LaTeX expressions.
            content = block.get("normalized_text") or block.get("text", "")
            kind = block.get("content_type", "text")
            pieces = [content] if kind in {"formula", "table"} else chunk_text(content, chunk_size)
            detail = block.get("metadata") or {}
            section = (f"Trang tính: {detail['sheet']}" if detail.get("sheet") else
                       f"Bảng {detail['table']}" if detail.get("table") else
                       f"Đoạn {detail['paragraph']}" if detail.get("paragraph") else
                       f"Khối {block['id']}")
            for piece in pieces:
                if not piece.strip():
                    continue
                chunk = _make_chunk(
                    f"doc_{doc_id}_{block['id']}_{chunk_index}", piece,
                    source_type="uploaded_file", source_name=filename,
                    source_page=block.get("page_number"), source_section=section,
                    content_type=kind, block_id=block["id"], doc_id=doc_id, user_id=get("owner_user_id"),
                    topic=None, chunk_index=chunk_index, grade=grade, **{k: v for k, v in detail.items() if k in {"extraction_method", "ocr_provider"}},
                )
                chunk.update(document_id=doc_id, page_number=block.get("page_number"), content_type=kind, normalized_text=piece)
                chunks.append(chunk)
                chunk_index += 1
        return chunks

    if file_type == "pdf" and parsed_data.get("page_spans"):
        append_parts(
            parsed_data["page_spans"],
            lambda span: {"source_page": span.get("page"), "source_section": None},
        )
    elif file_type == "docx" and parsed_data.get("block_spans"):
        def docx_locator(span):
            if span.get("kind") == "table":
                label = f"Bảng {span.get('table')}, dòng {span.get('row')}"
            else:
                label = f"Đoạn {span.get('paragraph')}"
            return {"source_page": None, "source_section": label}

        append_parts(parsed_data["block_spans"], docx_locator)
    elif file_type == "xlsx" and parsed_data.get("sheet_spans"):
        append_parts(
            parsed_data["sheet_spans"],
            lambda span: {
                "source_page": None,
                "source_section": f"Trang tính: {span.get('sheet')}",
            },
        )
    else:
        # Legacy uploads did not retain page/section spans. The chunk number is
        # useful for retrieval diagnostics but must not be presented as a page.
        for piece in chunk_text(text, chunk_size):
            chunks.append(
                _make_chunk(
                    f"doc_{doc_id}_{chunk_index}",
                    piece,
                    source_type="uploaded_file",
                    source_name=filename,
                    source_page=None,
                    source_section=f"Đoạn trích {chunk_index + 1} (không lưu trang gốc)",
                    topic=None,
                    doc_id=doc_id, user_id=get("owner_user_id"),
                    chunk_index=chunk_index,
                    grade=grade,
                )
            )
            chunk_index += 1
    return chunks


def build_chunks(
    *,
    grade: int | None = None,
    documents: list | None = None,
    chunk_size: int | None = None,
) -> list[dict]:
    """Gộp chunk từ curriculum(grade) (nếu có) + danh sách tài liệu."""
    chunks: list[dict] = []
    if grade is not None:
        chunks.extend(chunk_curriculum(grade))
    for document in documents or []:
        chunks.extend(chunk_document(document, chunk_size))
    return chunks
