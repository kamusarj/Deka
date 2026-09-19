"""Internal KHTN generation planning.

Learning objectives describe what a learner should be able to do.  This module
turns that instructional wording into a bounded scientific target and keeps the
response type, cognitive level, domain context and reasoning operation separate.
The plan is intentionally ephemeral and is never a database contract.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
import unicodedata
from typing import Literal


Domain = Literal[
    "physics_like",
    "chemistry_like",
    "biology_like",
    "earth_science_like",
    "integrated",
]
KnowledgeIntent = Literal[
    "definition",
    "identification",
    "classification",
    "characteristic",
    "property",
    "structure",
    "function",
    "process",
    "sequence",
    "relationship",
    "cause_effect",
    "comparison",
    "observation",
    "explanation",
    "prediction",
    "measurement",
    "calculation",
    "data_reading",
    "data_interpretation",
    "data_calculation",
    "experiment",
    "evidence_inference",
    "application",
    "safety",
]
ReasoningMode = Literal[
    "factual",
    "conceptual",
    "causal",
    "quantitative",
    "experimental",
    "data_analysis",
    "application",
    "multi_step",
]


INSTRUCTIONAL_VERBS = (
    "trình bày được",
    "mô tả được",
    "nêu được",
    "nhận biết được",
    "giải thích được",
    "thực hiện được",
    "vận dụng được",
    "sử dụng được",
    "phân biệt được",
    "so sánh được",
    "phân loại được",
    "xác định được",
    "tính được",
    "đo được",
    "đọc được",
    "phân tích được",
    "thiết kế được",
    "đề xuất được",
    "viết được",
    "cân bằng được",
    "phát biểu được",
)


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    return "".join(character for character in text if unicodedata.category(character) != "Mn").replace("đ", "d")


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .,:;!?-–—")


def parse_learning_objective(objective: str) -> dict:
    """Return the instructional action and candidate scientific targets.

    This parser is deliberately conservative. It removes only a leading
    curriculum action phrase and never treats the original objective as an
    answer. More detailed scientific decomposition remains a model task bounded
    by the controlled source context.
    """

    cleaned = _clean(objective)
    action = ""
    remainder = cleaned
    for verb in INSTRUCTIONAL_VERBS:
        match = re.match(rf"^{re.escape(verb)}\s+", remainder, flags=re.IGNORECASE)
        if match:
            action = verb.removesuffix(" được")
            remainder = remainder[match.end() :].strip()
            break

    candidates: list[str] = []
    plain_remainder = _plain(remainder)
    # Preserve the shared scientific object while separating structure and
    # function, the common source of the reported circulation regression.
    if "cau tao va chuc nang" in plain_remainder:
        object_scope = re.sub(
            r"^.*?cấu\s+tạo\s+và\s+chức\s+năng\s+(?:của\s+)?",
            "",
            remainder,
            count=1,
            flags=re.IGNORECASE,
        )
        object_scope = _clean(object_scope)
        candidates.extend(
            target for target in (
                f"cấu tạo của {object_scope}",
                f"chức năng của {object_scope}",
            ) if object_scope
        )

    if not candidates:
        segments = [
            _clean(segment)
            for segment in re.split(r"\s*;\s*|\s+đồng thời\s+", remainder)
            if _clean(segment)
        ]
        candidates.extend(segments or ([remainder] if remainder else []))

    return {
        "action": action,
        "knowledge_objects": list(dict.fromkeys(candidates)),
        "scope": remainder,
    }


def _domain(text: str) -> Domain:
    normalized = _plain(text)
    keyword_groups: tuple[tuple[Domain, tuple[str, ...]], ...] = (
        ("biology_like", ("te bao", "co the", "tim", "he tuan hoan", "mach mau", "hong cau", "ho hap", "tieu hoa", "sinh vat", "thuc vat", "dong vat", "di truyen", "sinh san")),
        ("chemistry_like", ("chat", "oxygen", "nguyen tu", "phan tu", "hoa hoc", "dung dich", "mol", "acid", "base", "kim loai", "phan ung")),
        ("earth_science_like", ("trai dat", "thoi tiet", "khi hau", "he mat troi", "dia chat", "mua", "nhiet do khong khi")),
        ("physics_like", ("luc", "toc do", "quang duong", "thoi gian", "ap suat", "dong dien", "dien ap", "nang luong", "nhiet", "am thanh", "anh sang", "khoi luong rieng")),
    )
    scores = {
        domain: sum(
            1
            for keyword in keywords
            if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
        )
        for domain, keywords in keyword_groups
    }
    best = max(scores, key=scores.get)
    return best if scores[best] else "integrated"


def _intent(action: str, target: str, context: str) -> KnowledgeIntent:
    core_text = _plain(" ".join((action, target)))
    action_text = _plain(action)
    has_data = any(token in core_text for token in ("bang so lieu", "bieu do", "do thi", "du lieu"))
    if has_data and action_text == "tinh":
        return "data_calculation"
    if has_data and action_text in {"phan tich", "nhan xet", "giai thich"}:
        return "data_interpretation"
    if has_data and action_text in {"doc", "neu", "xac dinh"}:
        return "data_reading"
    if action_text == "tinh" or "cong thuc" in core_text or "thay so" in core_text:
        return "calculation"
    ordered = (
        ("data_calculation", ("chenh lech", "phan tram thay doi"), ()),
        ("data_interpretation", ("nhan xet bang", "phan tich du lieu", "phan tich bang so lieu", "xu huong", "rut ra ket luan"), ()),
        ("data_reading", ("doc bang", "doc bieu do", "doc gia tri"), ()),
        ("experiment", ("thi nghiem", "bien kiem soat", "dung cu", "quy trinh"), ()),
        ("measurement", ("do duoc", "dung cu do", "don vi do"), ()),
        ("safety", ("an toan", "bao ho", "phong tranh"), ()),
        ("prediction", ("du doan", "du bao", "dieu gi xay ra"), ()),
        ("cause_effect", ("nguyen nhan", "he qua", "anh huong", "vi sao"), ()),
        ("comparison", ("so sanh", "phan biet"), ()),
        ("classification", ("phan loai", "xep loai"), ()),
        ("structure", ("cau tao", "bo phan", "thanh phan"), ()),
        ("function", ("chuc nang", "vai tro"), ()),
        ("sequence", ("thu tu", "cac buoc"), ()),
        ("process", ("qua trinh", "dien bien", "chu trinh"), ()),
        ("relationship", ("moi quan he", "lien he", "phu thuoc"), ()),
        ("property", ("tinh chat",), ()),
        ("characteristic", ("dac diem", "dau hieu"), ()),
        ("definition", ("khai niem", "la gi"), ()),
        ("explanation", ("giai thich",), ()),
        ("application", ("van dung", "ung dung", "thuc tien"), ()),
        ("identification", ("nhan biet", "xac dinh", "neu ten"), ()),
    )
    # The objective's action and scientific target define the requested
    # operation. Source context broadens the available knowledge only; summary
    # prose such as "quang hợp ... và vai trò" must not turn a definition or
    # equation objective into a function question.
    for intent, required, secondary in ordered:
        if any(token in core_text for token in required) and (
            not secondary or any(token in core_text for token in secondary)
        ):
            return intent  # type: ignore[return-value]
    return "identification"


def _reasoning(intent: KnowledgeIntent, difficulty: str) -> ReasoningMode:
    if intent in {"calculation", "data_calculation"}:
        return "quantitative"
    if intent in {"data_reading", "data_interpretation", "evidence_inference"}:
        return "data_analysis"
    if intent in {"experiment", "measurement", "observation"}:
        return "experimental"
    if intent in {"cause_effect", "explanation", "prediction"}:
        return "causal"
    if intent in {"application", "safety"}:
        return "application"
    if difficulty == "van_dung" and intent in {"definition", "identification", "characteristic", "property", "structure", "function"}:
        return "application"
    if difficulty == "van_dung" and intent in {"relationship", "process", "comparison"}:
        return "multi_step"
    if intent in {"definition", "identification", "characteristic", "property", "structure", "function"}:
        return "factual"
    return "conceptual"


SKILLS: dict[ReasoningMode, list[str]] = {
    "factual": ["identify_scientific_object", "recall_source_grounded_knowledge"],
    "conceptual": ["identify_relationship", "compare_scientific_features", "justify_conclusion"],
    "causal": ["identify_cause", "connect_mechanism_to_effect", "check_scientific_direction"],
    "quantitative": ["identify_known_values", "identify_unknown", "select_formula", "normalize_units", "substitute_values", "calculate", "check_unit"],
    "experimental": ["identify_experiment_goal", "identify_variables", "connect_observation_to_conclusion", "check_safety"],
    "data_analysis": ["read_presented_data", "compare_values", "identify_pattern", "draw_scientific_conclusion"],
    "application": ["identify_relevant_knowledge", "apply_to_context", "justify_practical_conclusion"],
    "multi_step": ["decompose_problem", "select_scientific_relationships", "complete_intermediate_steps", "check_final_conclusion"],
}


@dataclass(frozen=True)
class GenerationPlan:
    question_id: str
    grade: int
    strand: str
    domain: Domain
    knowledge_target: str
    knowledge_intent: KnowledgeIntent
    reasoning_mode: ReasoningMode
    cognitive_level: str
    question_type: str
    required_skills: list[str]
    source_context: str
    grounding_mode: Literal["retrieved_source", "curriculum_scope", "missing"]

    def as_prompt_dict(self) -> dict:
        return asdict(self)


def build_generation_plan(spec: dict, *, grade: int) -> GenerationPlan:
    if grade not in {6, 7, 8, 9}:
        raise ValueError("Question generation supports only KHTN grades 6-9")

    parsed = parse_learning_objective(str(spec.get("achievement") or ""))
    targets = parsed["knowledge_objects"] or [
        _clean(spec.get("knowledge_unit") or spec.get("topic") or "kiến thức KHTN")
    ]
    occurrence = int(spec.get("topic_occurrence", 0) or 0)
    target = targets[occurrence % len(targets)]
    context = _clean(spec.get("source_context") or spec.get("rag_context"))
    intent: KnowledgeIntent = (
        "calculation"
        if spec.get("requires_calculation")
        else _intent(parsed["action"], target, context)
    )
    mode = _reasoning(intent, str(spec.get("difficulty") or "nhan_biet"))
    source_type = str((spec.get("source") or {}).get("source_type") or "")
    grounding_mode = (
        "retrieved_source"
        if source_type == "rag_retrieval" and context
        else "curriculum_scope"
        if context
        else "missing"
    )
    domain_text = " ".join(
        str(spec.get(key) or "")
        for key in ("topic", "knowledge_unit", "achievement", "source_context")
    )
    return GenerationPlan(
        question_id=str(spec.get("question_id") or ""),
        grade=grade,
        strand=_clean(spec.get("topic")),
        domain=_domain(domain_text),
        knowledge_target=target,
        knowledge_intent=intent,
        reasoning_mode=mode,
        cognitive_level=str(spec.get("difficulty") or "nhan_biet"),
        question_type=str(spec.get("question_type") or ""),
        required_skills=list(SKILLS[mode]),
        source_context=context,
        grounding_mode=grounding_mode,
    )


def build_generation_plans(specification: list[dict], *, grade: int) -> list[GenerationPlan]:
    return [build_generation_plan(spec, grade=grade) for spec in specification]
