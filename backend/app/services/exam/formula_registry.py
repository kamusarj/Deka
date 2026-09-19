"""Curriculum-aware capabilities for safe KHTN numerical verification.

The registry is intentionally metadata-only: solver functions remain a fixed
mapping in ``numerical_verifier``. Local curriculum grounding requires an exact
objective id. Teacher-uploaded RAG grounding requires both an allowed grade and
scientific cues in the retrieved passage/selected target.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from app.services.curriculum import load_curriculum


@dataclass(frozen=True)
class FormulaCapability:
    formula_id: str
    grades: frozenset[int]
    objective_ids: frozenset[str]
    source_cues: tuple[str, ...]
    targets: frozenset[str]
    relationship: str


def _capability(
    formula_id: str,
    *,
    grades: tuple[int, ...],
    objectives: tuple[str, ...] = (),
    cues: tuple[str, ...],
    targets: tuple[str, ...],
    relationship: str,
) -> FormulaCapability:
    return FormulaCapability(
        formula_id=formula_id,
        grades=frozenset(grades),
        objective_ids=frozenset(objectives),
        source_cues=cues,
        targets=frozenset(targets),
        relationship=relationship,
    )


FORMULA_CAPABILITIES: dict[str, FormulaCapability] = {
    "RELATIVE_MOLECULAR_MASS": _capability(
        "RELATIVE_MOLECULAR_MASS",
        grades=(7,), objectives=("khtn7_obj_009",),
        cues=("khối lượng phân tử", "phan tu khoi"), targets=("mr",),
        relationship="Mr = Σ(Ar × số nguyên tử)",
    ),
    "SPEED": _capability(
        "SPEED",
        grades=(7,), objectives=("khtn7_obj_012",),
        cues=("tốc độ", "quãng đường"), targets=("v", "s", "t"),
        relationship="v = s / t",
    ),
    "MASS_MOLES": _capability(
        "MASS_MOLES",
        grades=(8,), objectives=("khtn8_obj_010",),
        cues=("mol", "khối lượng mol"), targets=("m", "n", "molar_mass"),
        relationship="m = n × M",
    ),
    "MOLAR_MASS_FROM_COMPOSITION": _capability(
        "MOLAR_MASS_FROM_COMPOSITION",
        grades=(8,), objectives=("khtn8_obj_007",),
        cues=("khối lượng mol", "công thức hóa học"), targets=("molar_mass",),
        relationship="M = Σ(Ar × số nguyên tử)",
    ),
    "MOLAR_GAS_VOLUME_STP": _capability(
        "MOLAR_GAS_VOLUME_STP",
        grades=(8,), objectives=("khtn8_obj_008", "khtn8_obj_010"),
        cues=("thể tích mol", "điều kiện chuẩn", "22,4 lít", "22.4 lít"),
        targets=("v", "n"), relationship="V = n × 22,4 L (điều kiện chuẩn)",
    ),
    "GAS_RELATIVE_DENSITY_H2": _capability(
        "GAS_RELATIVE_DENSITY_H2",
        grades=(8,), objectives=("khtn8_obj_009",),
        cues=("tỉ khối", "khí so với hydrogen", "khí so với hidro"),
        targets=("d_h2", "molar_mass"), relationship="d(A/H₂) = M(A) / 2",
    ),
    "CONCENTRATION_PERCENT": _capability(
        "CONCENTRATION_PERCENT",
        grades=(8,), objectives=("khtn8_obj_012", "khtn8_obj_013", "khtn8_obj_014"),
        cues=("nồng độ phần trăm", "nồng độ dung dịch"),
        targets=("concentration",), relationship="C% = m chất tan / m dung dịch × 100%",
    ),
    "DENSITY": _capability(
        "DENSITY",
        grades=(8,), objectives=("khtn8_obj_016", "khtn8_obj_017"),
        cues=("khối lượng riêng",), targets=("d", "m", "v"), relationship="D = m / V",
    ),
    # The seed curriculum asks students to explain pressure rather than
    # explicitly calculate it. Therefore this capability is RAG-only until a
    # controlled source passage actually supplies the quantitative relation.
    "PRESSURE": _capability(
        "PRESSURE",
        grades=(8,), cues=("p = f / s", "áp suất bằng lực", "công thức áp suất"),
        targets=("p", "f", "s"), relationship="p = F / S",
    ),
    "MOMENT": _capability(
        "MOMENT",
        grades=(8,), objectives=("khtn8_obj_021", "khtn8_obj_022"),
        cues=("moment lực", "mô men lực", "cánh tay đòn"),
        targets=("m", "f", "d"), relationship="M = F × d",
    ),
    "OHM": _capability(
        "OHM",
        grades=(8,), objectives=("khtn8_obj_028",),
        cues=("định luật ohm", "điện trở", "u = i"),
        targets=("u", "i", "r"), relationship="U = I × R",
    ),
    "HEAT": _capability(
        "HEAT",
        grades=(8,), objectives=("khtn8_obj_032",),
        cues=("nhiệt lượng", "nhiệt dung riêng"), targets=("q",),
        relationship="Q = m × c × Δt",
    ),
    "KINETIC_ENERGY": _capability(
        "KINETIC_ENERGY",
        grades=(9,), objectives=("khtn9_obj_001", "khtn9_obj_004"),
        cues=("động năng",), targets=("kinetic_energy", "wd"),
        relationship="Wđ = 1/2 × m × v²",
    ),
    "POTENTIAL_ENERGY": _capability(
        "POTENTIAL_ENERGY",
        grades=(9,), objectives=("khtn9_obj_002", "khtn9_obj_004"),
        cues=("thế năng",), targets=("potential_energy", "wt"),
        relationship="Wt = m × g × h",
    ),
    "MECHANICAL_ENERGY": _capability(
        "MECHANICAL_ENERGY",
        grades=(9,), objectives=("khtn9_obj_003", "khtn9_obj_005"),
        cues=("năng lượng cơ học", "bảo toàn năng lượng"),
        targets=("mechanical_energy", "kinetic_energy", "potential_energy"),
        relationship="W = Wđ + Wt",
    ),
    "ELECTRIC_POWER": _capability(
        "ELECTRIC_POWER",
        grades=(9,), objectives=("khtn9_obj_007",),
        cues=("công suất điện",), targets=("p", "u", "i"), relationship="P = U × I",
    ),
    "ELECTRIC_ENERGY": _capability(
        "ELECTRIC_ENERGY",
        grades=(9,), objectives=("khtn9_obj_007",),
        cues=("năng lượng điện", "điện năng tiêu thụ"),
        targets=("e", "p", "t"), relationship="E = P × t",
    ),
    "SERIES_RESISTANCE": _capability(
        "SERIES_RESISTANCE",
        grades=(9,), objectives=("khtn9_obj_009",),
        cues=("điện trở tương đương", "mạch nối tiếp"), targets=("r",),
        relationship="R = R₁ + R₂ + …",
    ),
    "PARALLEL_RESISTANCE_TWO": _capability(
        "PARALLEL_RESISTANCE_TWO",
        grades=(9,), objectives=("khtn9_obj_009",),
        cues=("điện trở tương đương", "mạch song song"), targets=("r",),
        relationship="R = R₁R₂ / (R₁ + R₂)",
    ),
    "DATA_DIFFERENCE": _capability(
        "DATA_DIFFERENCE",
        grades=(6, 7, 8, 9),
        cues=("bảng số liệu", "dữ liệu", "chênh lệch", "thay đổi"),
        targets=("difference", "change"), relationship="Δ = giá trị cuối − giá trị đầu",
    ),
    "PERCENT_CHANGE": _capability(
        "PERCENT_CHANGE",
        grades=(6, 7, 8, 9),
        cues=("bảng số liệu", "dữ liệu", "phần trăm thay đổi", "tỉ lệ thay đổi"),
        targets=("percent_change",), relationship="%Δ = Δ / giá trị đầu × 100%",
    ),
}


KNOWN_VALUE_SYMBOL_CONTRACTS: dict[str, str] = {
    "RELATIVE_MOLECULAR_MASS": "ar_1,count_1, ar_2,count_2, ...; đơn vị của mọi giá trị là '1'",
    "SPEED": "s (quãng đường), t (thời gian), v (tốc độ)",
    "MASS_MOLES": "m (khối lượng), n (số mol), molar_mass (khối lượng mol)",
    "MOLAR_MASS_FROM_COMPOSITION": "ar_1,count_1, ar_2,count_2, ...; đơn vị của mọi giá trị là '1'",
    "MOLAR_GAS_VOLUME_STP": "n (số mol), v (thể tích)",
    "GAS_RELATIVE_DENSITY_H2": "molar_mass (khối lượng mol), d_h2 (tỉ khối so với H2)",
    "CONCENTRATION_PERCENT": "m_solute (khối lượng chất tan), m_solution (khối lượng dung dịch)",
    "DENSITY": "d (khối lượng riêng), m (khối lượng), v (thể tích)",
    "PRESSURE": "p (áp suất), f (lực), s (diện tích)",
    "MOMENT": "m (moment lực), f (lực), d (cánh tay đòn)",
    "OHM": "u (điện áp), i (cường độ dòng điện), r (điện trở)",
    "HEAT": "m (khối lượng), c (nhiệt dung riêng), delta_t (độ tăng nhiệt độ)",
    "KINETIC_ENERGY": "m (khối lượng), v (tốc độ)",
    "POTENTIAL_ENERGY": "m (khối lượng), g (gia tốc trọng trường), h (độ cao)",
    "MECHANICAL_ENERGY": "mechanical_energy, kinetic_energy, potential_energy",
    "ELECTRIC_POWER": "p (công suất), u (điện áp), i (cường độ dòng điện)",
    "ELECTRIC_ENERGY": "e (điện năng), p (công suất), t (thời gian)",
    "SERIES_RESISTANCE": "r_1,r_2,... (các điện trở thành phần)",
    "PARALLEL_RESISTANCE_TWO": "r_1,r_2 (đúng hai điện trở thành phần)",
    "DATA_DIFFERENCE": "initial (giá trị đầu), final (giá trị cuối)",
    "PERCENT_CHANGE": "initial (giá trị đầu), final (giá trị cuối)",
}


def _plain(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or "").lower())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn").replace("đ", "d")
    return re.sub(r"\s+", " ", text).strip()


def _target(value: object) -> str:
    aliases = {
        "speed": "v", "distance": "s", "time": "t",
        "mass": "m", "amount": "n", "volume": "v",
        "concentration_percent": "concentration",
    }
    normalized = _plain(value).replace("-", "_").replace(" ", "_")
    return aliases.get(normalized, normalized)


def capability_issues(
    formula_id: object,
    *,
    grade: int,
    target_symbol: object,
    spec: dict,
    knowledge_target: str,
    source_context: str,
) -> list[tuple[str, str]]:
    formula_key = str(formula_id or "").upper()
    capability = FORMULA_CAPABILITIES.get(formula_key)
    if capability is None:
        return [("formula_unsupported", f"Công thức {formula_key or '(trống)'} chưa có solver an toàn.")]
    issues: list[tuple[str, str]] = []
    if grade not in capability.grades:
        issues.append(("formula_grade_mismatch", f"Công thức {formula_key} không được bật cho KHTN lớp {grade}."))
    target = _target(target_symbol)
    if target not in capability.targets:
        issues.append(("formula_target_invalid", f"Biến cần tìm {target or '(trống)'} không được hỗ trợ cho {formula_key}."))

    source_type = str((spec.get("source") or {}).get("source_type") or "")
    objective_id = str(spec.get("objective_id") or "")
    if source_type == "local_json":
        grounded = bool(objective_id and objective_id in capability.objective_ids)
    else:
        haystack = _plain(" ".join((knowledge_target, source_context, str(spec.get("topic") or ""))))
        grounded = any(_plain(cue) in haystack for cue in capability.source_cues)
    if not grounded:
        issues.append(("formula_not_grounded", f"Công thức {formula_key} không được phép bởi objective/source đã kiểm soát."))
    return issues


def allowed_formula_ids(*, grade: int, spec: dict, knowledge_target: str, source_context: str) -> list[str]:
    allowed = []
    for formula_id, capability in FORMULA_CAPABILITIES.items():
        if grade not in capability.grades:
            continue
        # Prompt allowlisting is target-agnostic because the model may solve a
        # valid rearrangement, but it must pass the same source grounding rule.
        source_type = str((spec.get("source") or {}).get("source_type") or "")
        objective_id = str(spec.get("objective_id") or "")
        if source_type == "local_json":
            grounded = bool(objective_id and objective_id in capability.objective_ids)
        else:
            haystack = _plain(" ".join((knowledge_target, source_context, str(spec.get("topic") or ""))))
            grounded = any(_plain(cue) in haystack for cue in capability.source_cues)
        if grounded:
            allowed.append(formula_id)
    return allowed


def local_calculation_candidates(*, grade: int, curriculum: list) -> list[dict]:
    """Resolve selected curriculum rows to exact formula-capable objectives.

    This uses the same grade/objective allowlist as prompt construction and the
    numerical verifier.  It deliberately does not infer capability from broad
    topic words, so an unsatisfied requirement fails before provider work.
    """

    controlled = load_curriculum(grade)
    controlled_topics = {
        _plain(topic.get("name")): topic
        for topic in controlled.get("topics", [])
    }
    candidates: list[dict] = []
    for lesson_index, lesson in enumerate(curriculum):
        if isinstance(lesson, dict):
            topic_name = lesson.get("topic")
            achievements = lesson.get("achievements", [])
        else:
            topic_name = getattr(lesson, "topic", None)
            achievements = getattr(lesson, "achievements", [])
        topic = controlled_topics.get(_plain(topic_name))
        if not topic:
            continue
        objectives = {
            _plain(objective.get("text")): objective
            for objective in topic.get("learning_objectives", [])
        }
        for achievement in achievements:
            objective = objectives.get(_plain(achievement))
            if not objective:
                continue
            objective_id = str(objective.get("id") or "")
            formula_ids = sorted(
                formula_id
                for formula_id, capability in FORMULA_CAPABILITIES.items()
                if grade in capability.grades
                and objective_id in capability.objective_ids
            )
            if formula_ids:
                candidates.append(
                    {
                        "lesson_index": lesson_index,
                        "achievement": str(objective.get("text") or achievement),
                        "objective_id": objective_id,
                        "formula_ids": formula_ids,
                    }
                )
    return candidates


def prompt_capability(formula_id: str) -> dict:
    capability = FORMULA_CAPABILITIES[formula_id]
    return {
        "formula_id": formula_id,
        "relationship": capability.relationship,
        "allowed_targets": sorted(capability.targets),
        "known_value_symbol_contract": KNOWN_VALUE_SYMBOL_CONTRACTS[formula_id],
    }
