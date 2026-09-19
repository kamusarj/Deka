"""Shared, scope-aware duplicate checks for generation, edits and bank writes.

Similarity is evidence, not calibrated probability. Fuzzy/semantic findings are
warnings; an identical teaching task can be rejected at the bank write boundary.
No generative LLM judge is needed. Different numerical data are distinct tasks.
"""

from __future__ import annotations

import json
from hashlib import sha256
import re
import unicodedata
from difflib import SequenceMatcher

from app.core.config import settings
from app.models.bank_question import BankQuestion
from app.rag.embeddings import resolve_embedder
from app.rag.retriever import BM25Retriever, EmbeddingRetriever
from app.rag.vector_store import shared_vector_store
from app.services.authorization import scope_query


def normalize_question(text) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return " ".join(re.findall(r"\w+|[+−=*/<>]", value))


def _options(question):
    options = question.get("options") or {}
    if isinstance(options, list):
        return {str(item.get("key", index)): item.get("text", "") for index, item in enumerate(options) if isinstance(item, dict)}
    return options if isinstance(options, dict) else {}


def task_text(question: dict) -> str:
    parts = [str(question.get("content") or "")]
    parts.extend(sorted(str(value) for value in _options(question).values()))
    for field in ("statements", "sub_questions"):
        parts.extend(str(item.get("content") or "") for item in (question.get(field) or []) if isinstance(item, dict))
    # Rich tables/diagrams carry task data and must participate in equality.
    if question.get("rich_content"):
        rich = [{**block, "src": "image-sha256:" + sha256(str(block.get("src", "")).encode()).hexdigest()} if block.get("type") == "image" else block for block in question["rich_content"]]
        parts.append(json.dumps(rich, ensure_ascii=False, sort_keys=True))
    return "\n".join(parts)


def answer_text(question: dict) -> str:
    answer = question.get("answer") or {}
    answer = answer.get("answer", answer) if isinstance(answer, dict) else {}
    correct = question.get("correct_answer") or answer.get("correct_answer")
    if question.get("type") == "multiple_choice":
        return normalize_question(_options(question).get(str(correct), correct))
    if question.get("type") == "true_false":
        truth = {item.get("statement_id"): item.get("is_true") for item in (answer.get("answers") or []) if isinstance(item, dict)}
        return json.dumps(sorted((normalize_question(item.get("content")), str(item.get("is_true", truth.get(item.get("id"))))) for item in (question.get("statements") or []) if isinstance(item, dict)))
    return normalize_question(correct or question.get("model_answer") or answer.get("model_answer"))


def _context(question, key):
    return question.get(key) or (question.get("metadata") or {}).get(key)


def compare_questions(question: dict, candidate: dict, *, vector_score: float | None = None) -> dict | None:
    if question.get("type") != candidate.get("type"):
        return None
    left, right = task_text(question), task_text(candidate)
    if not left.strip() or not right.strip():
        return None
    # Preserve signs, decimal separators and numeric values; same formula alone
    # must never collapse questions with different givens.
    numbers = lambda value: sorted(re.findall(r"[-+]?\d+(?:[.,]\d+)?", value))
    if numbers(left) != numbers(right):
        return None
    for key in ("reasoning_mode", "difficulty"):
        a, b = _context(question, key), _context(candidate, key)
        if a and b and a != b:
            return None
    a, b = normalize_question(left), normalize_question(right)
    left_answer, right_answer = answer_text(question), answer_text(candidate)
    same_answer = not left_answer or not right_answer or left_answer == right_answer
    fuzzy = SequenceMatcher(None, a, b, autojunk=False).ratio()
    duplicate_type, confidence, decision = None, 0.0, "warn"
    if a == b:
        duplicate_type, confidence = "exact", 1.0
        # Identical stems with conflicting keys still need human attention.
        decision = "reject" if same_answer else "warn"
    elif fuzzy >= settings.DUPLICATE_FUZZY_THRESHOLD and same_answer:
        duplicate_type, confidence = "fuzzy", fuzzy
    elif vector_score is not None and vector_score >= settings.DUPLICATE_WARNING_THRESHOLD:
        duplicate_type, confidence = "semantic", vector_score
        # A shared knowledge target is insufficient. Require answer agreement
        # for a strong semantic match; borderline results remain suggestions.
        if not same_answer:
            return None
    if duplicate_type is None:
        return None
    confirmed = duplicate_type != "semantic" or confidence >= settings.DUPLICATE_SEMANTIC_THRESHOLD
    return {
        "is_duplicate": confirmed,
        "duplicate_type": duplicate_type,
        "confidence": round(confidence, 6),
        "matched_question_id": str(candidate.get("id", "")),
        "decision": decision,
        "severity": "ERROR" if decision == "reject" else "WARNING",
        "reason": "Nội dung câu hỏi trùng nhưng đáp án khác nhau; cần kiểm tra." if not same_answer else "Câu hỏi có nội dung hoặc nhiệm vụ tương tự; hãy kiểm tra trước khi sử dụng.",
    }


class DuplicateDetector:
    def __init__(self, candidates: list[dict], *, embedder=None, resolve_provider=True):
        self.candidates = candidates
        self.by_id = {str(item["id"]): item for item in candidates}
        self.exact: dict[str, list[dict]] = {}
        self.chunks = []
        for item in candidates:
            text = task_text(item)
            self.exact.setdefault(normalize_question(text), []).append(item)
            self.chunks.append({"id": f"bank_{item['id']}", "text": text, "metadata": {"question_id": str(item["id"])}})
        self.lexical = BM25Retriever(self.chunks)
        self.vector = None
        self.semantic_available = False
        try:
            embedder = embedder or (resolve_embedder() if resolve_provider and settings.VECTOR_RETRIEVAL_ENABLED else None)
            if embedder:
                self.vector = EmbeddingRetriever(self.chunks, embedder, vector_store=shared_vector_store(embedder.name))
                self.semantic_available = True
        except Exception:
            self.semantic_available = False

    def check(self, question: dict, *, exclude_ids=()) -> list[dict]:
        exclude_ids = {str(value) for value in exclude_ids}
        text = task_text(question)
        candidate_ids = {str(item["id"]) for item in self.exact.get(normalize_question(text), [])}
        candidate_ids.update(hit["chunk"]["metadata"]["question_id"] for hit in self.lexical.retrieve(text, settings.DUPLICATE_CANDIDATE_LIMIT))
        vector_scores = {}
        if self.vector:
            try:
                for hit in self.vector.retrieve(text, settings.DUPLICATE_CANDIDATE_LIMIT):
                    key = hit["chunk"]["metadata"]["question_id"]
                    candidate_ids.add(key)
                    vector_scores[key] = hit["score"]
            except Exception:
                self.vector = None
                self.semantic_available = False
        result = []
        for candidate_id in sorted(candidate_ids - exclude_ids):
            match = compare_questions(question, self.by_id[candidate_id], vector_score=vector_scores.get(candidate_id))
            if match:
                result.append(match)
        return sorted(result, key=lambda item: (-item["confidence"], item["matched_question_id"]))


def bank_candidates(db, actor=None, *, grade=None) -> list[dict]:
    query = scope_query(db.query(BankQuestion), BankQuestion, actor)
    if grade is not None:
        query = query.filter((BankQuestion.grade == grade) | BankQuestion.grade.is_(None))
    return [{"id": str(row.id), "content": row.content, "type": row.type,
             "difficulty": row.difficulty, "options": row.options, "statements": row.statements,
             "sub_questions": row.sub_questions, "answer": row.answer,
             "metadata": getattr(row, "content_metadata", None) or {},
             "rich_content": getattr(row, "rich_content", None)} for row in query.all()]


def exam_duplicate_report(questions, answer_key, bank, *, embedder=None, resolve_provider=True):
    answers = {item["question_id"]: item for item in answer_key}
    local = [{**q, "answer": answers.get(q["id"], {})} for q in questions]
    bank_detector = DuplicateDetector(bank, embedder=embedder, resolve_provider=resolve_provider)
    local_detector = DuplicateDetector(local, embedder=embedder, resolve_provider=resolve_provider)
    findings = []
    earlier = set()
    for question in local:
        for scope, detector, excluded in (
            ("exam", local_detector, set(local_detector.by_id) - earlier),
            ("bank", bank_detector, set()),
        ):
            for match in detector.check(question, exclude_ids=excluded):
                # Generation retains the existing warning-based duplicate policy.
                findings.append({**match, "question_id": question["id"], "question_number": question.get("number"), "scope": scope, "severity": "WARNING", "decision": "warn"})
        earlier.add(question["id"])
    return {"findings": findings, "semantic_available": bank_detector.semantic_available and local_detector.semantic_available}
