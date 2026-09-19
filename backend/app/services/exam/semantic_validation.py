"""Deterministic pre-persistence quality rules for generated KHTN items."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import re
import unicodedata

from app.services.exam.generation_planning import GenerationPlan, INSTRUCTIONAL_VERBS
from app.services.exam.formula_registry import capability_issues
from app.services.exam.numerical_verifier import validate_calculation


@dataclass(frozen=True)
class SemanticIssue:
    code: str
    severity: str
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


META_LANGUAGE = (
    "có thể bỏ qua",
    "không cần hiểu",
    "chỉ cần ghi nhớ",
    "không cần học",
    "phù hợp với yêu cầu",
    "không phù hợp với yêu cầu",
    "theo yêu cầu cần đạt",
    "căn cứ kiến thức cho biết",
    "đối chiếu với căn cứ kiến thức",
    "kiến thức này không quan trọng",
)
MISSING_ANSWER_MARKERS = (
    "bản ghi cũ chưa",
    "bản ghi này chưa",
    "cần tạo lại ý kiến thức",
)
GENERIC_EXPLANATIONS = (
    "đáp án đúng theo công thức",
    "phương án này đúng",
    "phương án này sai",
    "phù hợp trực tiếp với căn cứ",
    "không khớp với căn cứ kiến thức",
    "đúng theo yêu cầu",
    "sai theo yêu cầu",
)

def _plain(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(character for character in text if unicodedata.category(character) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip(" .,:;!?-–—")


def _texts(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _texts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _texts(child)


def _issue(code: str, message: str, severity: str = "major") -> SemanticIssue:
    return SemanticIssue(code=code, severity=severity, message=message)


def _answer_content(answer: dict) -> list[str]:
    values: list[str] = []
    for key in ("correct_answer", "explanation", "model_answer", "key_points", "option_explanations", "answers"):
        values.extend(_texts(answer.get(key)))
    return values


def _objective_copied(spec: dict, question: dict, answer: dict) -> bool:
    objective = _plain(spec.get("achievement"))
    if not objective:
        return False
    candidates = list(_texts(question.get("options"))) + _answer_content(answer)
    objective_tokens = set(objective.split())
    for candidate in candidates:
        normalized = _plain(candidate)
        if not normalized:
            continue
        if normalized == objective or (len(objective) >= 20 and objective in normalized):
            return True
        tokens = set(normalized.split())
        token_overlap = len(tokens & objective_tokens) / max(1, len(objective_tokens))
        if SequenceMatcher(None, objective, normalized).ratio() >= 0.82 and token_overlap >= 0.75:
            return True
        # Starting a marking point with an instructional verb (for example
        # "Nêu được quang hợp hấp thụ CO2...") is not, by itself, a copied
        # curriculum objective.  Require substantial objective-token overlap
        # so scientific answer content is not rejected as meta-learning text.
        if (
            any(normalized.startswith(_plain(verb)) for verb in INSTRUCTIONAL_VERBS)
            and token_overlap >= 0.6
        ):
            return True
    return False


def _has_markdown_table(content: str) -> bool:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return any(
        "|" in lines[index]
        and index + 1 < len(lines)
        and re.search(r"\|?\s*:?-{3,}", lines[index + 1])
        for index in range(len(lines))
    )


def _has_visual_payload(question: dict) -> bool:
    content = str(question.get("content") or "")
    return bool(
        _has_markdown_table(content)
        or re.search(r"!\[[^\]]*\]\([^)]*\)|<img\b", content, flags=re.IGNORECASE)
        or question.get("image")
        or question.get("attachments")
        or any(block.get("type") in {"table", "image", "diagram"} for block in question.get("rich_content") or [])
    )


def _target_overlap(plan: GenerationPlan, question: dict) -> bool:
    stop = {"cua", "va", "trong", "mot", "cac", "cho", "voi", "ve", "la", "duoc"}
    target = {token for token in _plain(plan.knowledge_target).split() if len(token) >= 3 and token not in stop}
    content = set(_plain(question.get("content")).split())
    return bool(target & content) if target else False


def _comparison_pair_covered(plan: GenerationPlan, question: dict) -> bool:
    """Accept a comparison expressed by covering both named objects.

    True/false stems often introduce the pair and let their child statements
    perform the distinction, so requiring a literal comparison verb in the
    stem rejects otherwise valid items.
    """

    target_parts = re.split(r"\s+(?:va|voi)\s+", _plain(plan.knowledge_target), maxsplit=1)
    if len(target_parts) != 2:
        return False
    stop = {
        "cua",
        "va",
        "voi",
        "trong",
        "mot",
        "cac",
        "cho",
        "ve",
        "la",
        "duoc",
        "su",
        "qua",
        "trinh",
    }
    significant_parts = [
        {token for token in part.split() if len(token) >= 3 and token not in stop}
        for part in target_parts
    ]
    if any(not tokens for tokens in significant_parts):
        return False
    student_facing_text = _plain(
        " ".join(
            _texts(
                {
                    "content": question.get("content"),
                    "options": question.get("options"),
                    "statements": question.get("statements"),
                    "sub_questions": question.get("sub_questions"),
                }
            )
        )
    )
    return all(any(token in student_facing_text for token in tokens) for tokens in significant_parts)


def _validate_mc(question: dict, answer: dict) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    options = question.get("options")
    if not isinstance(options, dict) or set(options) != {"A", "B", "C", "D"}:
        issues.append(_issue("mcq_options_invalid", "Trắc nghiệm một lựa chọn phải có đúng A/B/C/D."))
        return issues
    normalized_options = [_plain(value) for value in options.values()]
    if any(not value for value in normalized_options) or len(set(normalized_options)) != 4:
        issues.append(_issue("mcq_options_duplicate", "Các phương án phải đầy đủ và khác nhau."))
    correct = str(answer.get("correct_answer") or question.get("correct_answer") or "").upper()
    if correct not in options:
        issues.append(_issue("mcq_correct_answer_invalid", "Đáp án đúng không trỏ tới phương án được hiển thị."))
    explanations = answer.get("option_explanations")
    if not isinstance(explanations, dict) or set(explanations) != set(options):
        issues.append(_issue("mcq_option_explanations_incomplete", "Mỗi phương án cần một giải thích khoa học riêng."))
    elif any(len(_plain(value)) < 20 for value in explanations.values()):
        issues.append(_issue("mcq_option_explanation_too_short", "Giải thích phương án phải nêu lý do cụ thể, không chỉ kết luận đúng/sai."))
    return issues


def _validate_true_false(question: dict, answer: dict) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    statements = question.get("statements")
    if not isinstance(statements, list) or len(statements) != 4:
        return [_issue("true_false_statement_count", "Câu đúng/sai phải có đúng bốn phát biểu con.")]
    ids = []
    for statement in statements:
        statement_id = statement.get("id") if isinstance(statement, dict) else None
        content = _plain(statement.get("content")) if isinstance(statement, dict) else ""
        if not statement_id or len(content.split()) < 4 or not isinstance(statement.get("is_true"), bool):
            issues.append(_issue("true_false_statement_invalid", "Mỗi phát biểu phải hoàn chỉnh và có giá trị đúng/sai độc lập."))
        ids.append(statement_id)
    supplied = {
        item.get("statement_id"): item
        for item in (answer.get("answers") or [])
        if isinstance(item, dict)
    }
    if set(supplied) != set(ids):
        issues.append(_issue("true_false_answers_incomplete", "Đáp án phải giải thích đúng bốn phát biểu được hiển thị."))
    for statement in statements:
        if statement.get("is_true") is not False:
            continue
        explanation = _plain((supplied.get(statement.get("id")) or {}).get("explanation"))
        correction_markers = ("sai", "dung la", "phai la", "thuc te", "trong khi", "khong phai", "chinh xac la")
        if len(explanation.split()) < 8 or not any(marker in explanation for marker in correction_markers):
            issues.append(_issue("false_statement_not_corrected", f"Giải thích phát biểu {statement.get('id')} phải chỉ ra phần sai và nêu kiến thức đúng."))
    return issues


def _validate_short_answer(question: dict, answer: dict) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    if question.get("options") or question.get("statements"):
        issues.append(_issue("short_answer_fake_options", "Câu trả lời ngắn không được có phương án hoặc phát biểu đúng/sai."))
    correct_answer = _plain(answer.get("correct_answer"))
    if not correct_answer:
        issues.append(_issue("short_answer_missing", "Câu trả lời ngắn thiếu đáp án dự kiến."))
    elif len(correct_answer.split()) > 5:
        issues.append(_issue("short_answer_too_long", "Đáp án trả lời ngắn phải là một thuật ngữ, số hoặc cụm tối đa năm từ."))
    content = _plain(question.get("content"))
    open_ended_markers = (
        "vi sao",
        "giai thich",
        "trinh bay",
        "mo ta",
        "nhu the nao",
        "phan tich",
        "neu muc dich",
        "muc dich cua",
    )
    if any(marker in content for marker in open_ended_markers):
        issues.append(
            _issue(
                "short_answer_open_ended",
                "Câu trả lời ngắn đang yêu cầu diễn giải; hãy hỏi một thuật ngữ, số hoặc cụm danh từ duy nhất.",
            )
        )
    return issues


def _validate_essay(question: dict, answer: dict, rubric: dict | None) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    if question.get("options") or question.get("statements"):
        issues.append(_issue("essay_objective_shape", "Câu tự luận không được dùng cấu trúc phương án/đúng-sai."))
    if len(_plain(answer.get("model_answer")).split()) < 12:
        issues.append(_issue("essay_model_answer_shallow", "Đáp án tự luận phải chứa kiến thức khoa học thực tế và đủ ý."))
    key_points = [point for point in (answer.get("key_points") or []) if len(_plain(point).split()) >= 3]
    if len(key_points) < 2:
        issues.append(_issue("essay_key_points_generic", "Đáp án tự luận cần ít nhất hai ý khoa học cụ thể."))
    criteria = (rubric or {}).get("criteria") or []
    if not criteria:
        issues.append(_issue("essay_rubric_missing", "Câu tự luận thiếu rubric theo ý khoa học."))
    else:
        rubric_text = " ".join(_texts(criteria))
        if any(phrase in _plain(rubric_text) for phrase in ("tra loi day du", "du y chinh")) and len(key_points) < 3:
            issues.append(_issue("essay_rubric_generic", "Rubric đang chấm chung chung thay vì phân điểm theo ý khoa học."))
    return issues


def validate_generated_item(
    *,
    question: dict,
    answer: dict,
    rubric: dict | None,
    spec: dict,
    plan: GenerationPlan,
    calculation: dict | None = None,
) -> list[SemanticIssue]:
    issues: list[SemanticIssue] = []
    from app.services.math_rendering import require_renderable_math
    from app.services.rich_content import normalize_blocks
    try:
        normalize_blocks(question.get("rich_content"))
        for value in [*_texts(question), *_answer_content(answer), *_texts(rubric or {})]:
            if not value.startswith("data:image/"):
                require_renderable_math(value)
    except (ValueError, OSError):
        issues.append(_issue("rich_content_invalid", "Công thức hoặc nội dung bổ sung chưa render được; cần chỉnh lại.", "critical"))
    if any(block.get("type") == "image" for block in question.get("rich_content") or []):
        issues.append(_issue("image_requires_teacher_review", "Hãy đối chiếu ảnh gốc: kiểm định văn bản chỉ dùng chú thích, không xác nhận nội dung điểm ảnh.", "minor"))
    scope_guard = (question.get("metadata") or {}).get("scope_guard") or {}
    if scope_guard.get("status") == "replaced":
        issues.append(
            _issue(
                "generated_shape_replaced",
                "Payload AI thiếu hoặc sai cấu trúc theo loại câu hỏi; phải sinh lại thay vì lưu bản thay thế.",
                "critical",
            )
        )
    all_text = " ".join(_texts(question)) + " " + " ".join(_answer_content(answer))
    normalized_all = _plain(all_text)
    answer_text = _plain(" ".join(_answer_content(answer)))
    if any(_plain(marker) in answer_text for marker in MISSING_ANSWER_MARKERS):
        issues.append(_issue("answer_content_missing", "Đáp án chứa thông báo thiếu nội dung thay cho lời giải khoa học.", "critical"))
    for phrase in META_LANGUAGE:
        if _plain(phrase) in normalized_all:
            issues.append(_issue("meta_learning_language", f"Nội dung chứa ngôn ngữ meta-learning bị cấm: “{phrase}”.", "critical"))
            break
    if _objective_copied(spec, question, answer):
        issues.append(_issue("learning_objective_copy", "Yêu cầu cần đạt bị dùng như đáp án/nội dung khoa học.", "critical"))
    if plan.grounding_mode == "missing":
        issues.append(_issue("source_context_missing", "Không có ngữ cảnh nguồn được kiểm soát cho câu hỏi.", "critical"))
    if not _target_overlap(plan, question):
        issues.append(_issue("knowledge_target_missing", "Câu hỏi không thể hiện rõ mục tiêu kiến thức đã chọn."))

    content = str(question.get("content") or "")
    content_plain = _plain(content)
    if any(reference in content_plain for reference in ("bang duoi", "bang sau", "bieu do", "do thi", "hinh duoi", "hinh sau")) and not _has_visual_payload(question):
        issues.append(_issue("referenced_material_missing", "Câu hỏi nhắc tới bảng/biểu đồ/hình nhưng payload không chứa dữ liệu đó.", "critical"))

    intent_cues = {
        "function": ("chuc nang", "vai tro"),
        "structure": ("cau tao", "bo phan", "thanh phan"),
        "comparison": (
            "so sanh",
            "so voi",
            "phan biet",
            "khac nhau",
            "khac biet",
            "diem giong",
            "diem khac",
        ),
        "cause_effect": (
            "vi sao",
            "nguyen nhan",
            "he qua",
            "anh huong",
            # A closed short-answer item can test a directional causal
            # relationship without requesting an open-ended explanation.
            "tang hay giam",
        ),
        "calculation": ("tinh", "bao nhieu"),
        "data_calculation": ("tinh", "chenh lech", "tang bao nhieu", "phan tram"),
        "experiment": ("thi nghiem", "bien", "dung cu", "quan sat", "ket luan"),
    }
    cues = intent_cues.get(plan.knowledge_intent)
    intent_is_explicit = bool(cues and any(cue in content_plain for cue in cues))
    intent_is_structural_comparison = (
        plan.knowledge_intent == "comparison"
        and _comparison_pair_covered(plan, question)
    )
    if cues and not intent_is_explicit and not intent_is_structural_comparison:
        issues.append(_issue("knowledge_intent_mismatch", f"Cách hỏi không thể hiện intent {plan.knowledge_intent}."))

    explanation = _plain(answer.get("explanation") or answer.get("model_answer"))
    if question.get("type") != "true_false":
        if len(explanation.split()) < 10:
            issues.append(_issue("explanation_too_shallow", "Lời giải chưa nêu đủ lý do khoa học."))
        if any(_plain(phrase) in explanation for phrase in GENERIC_EXPLANATIONS):
            issues.append(_issue("explanation_generic", "Lời giải dùng kết luận chung chung thay vì giải thích khoa học."))

    question_type = question.get("type")
    if question_type == "multiple_choice":
        issues.extend(_validate_mc(question, answer))
    elif question_type == "true_false":
        issues.extend(_validate_true_false(question, answer))
    elif question_type == "short_answer":
        issues.extend(_validate_short_answer(question, answer))
    elif question_type == "essay":
        issues.extend(_validate_essay(question, answer, rubric))
    else:
        issues.append(_issue("question_type_unsupported", f"Loại câu hỏi không được hỗ trợ: {question_type}", "critical"))

    if plan.reasoning_mode == "quantitative" or calculation is not None:
        formula_id = str((calculation or {}).get("formula_id") or "")
        issues.extend(
            _issue(code, message, "critical")
            for code, message in capability_issues(
                formula_id,
                grade=plan.grade,
                target_symbol=(calculation or {}).get("target_symbol"),
                spec=spec,
                knowledge_target=plan.knowledge_target,
                source_context=plan.source_context,
            )
        )
        issues.extend(
            _issue(item.code, item.message, "critical")
            for item in validate_calculation(calculation, question, answer)
        )
    return list({(item.code, item.message): item for item in issues}.values())


def blocking_issues(issues: list[SemanticIssue]) -> list[SemanticIssue]:
    return [issue for issue in issues if issue.severity in {"critical", "major"}]
