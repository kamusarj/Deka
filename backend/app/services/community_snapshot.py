"""Project public teaching content without copying private bank provenance."""


def _fields(value, names):
    if not isinstance(value, dict):
        return {}
    return {name: value[name] for name in names if name in value
            and (value[name] is None or isinstance(value[name], (str, int, float, bool)))}


def _items(value):
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _texts(value):
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _options(value):
    def option(item):
        if isinstance(item, dict):
            return _fields(item, ("key", "text", "content"))
        return item if isinstance(item, (str, int, float)) else None

    if isinstance(value, list):
        return [option(item) for item in value]
    if isinstance(value, dict):
        return {key: option(item) for key, item in value.items()}
    return None


def _rubric(value):
    if not isinstance(value, dict):
        return None
    result = _fields(value, ("total_score",))
    result["grading_guide"] = _texts(value.get("grading_guide"))
    result["criteria"] = [
        {**_fields(item, ("id", "name", "max_score")),
         "levels": [_fields(level, ("score", "description", "criteria"))
                    for level in _items(item.get("levels"))]}
        for item in _items(value.get("criteria"))
    ]
    return result


def _answer(value):
    if not isinstance(value, dict):
        return None
    # Older bank rows wrap the answer and rubric in separate sibling fields.
    answer = value["answer"] if isinstance(value.get("answer"), dict) else value
    result = _fields(answer, ("correct_answer", "explanation", "model_answer", "accept_variations"))
    for name in ("keywords", "key_points"):
        if name in answer:
            result[name] = _texts(answer[name])
    if isinstance(answer.get("option_explanations"), dict):
        result["option_explanations"] = {
            key: text for key, text in answer["option_explanations"].items() if isinstance(text, str)
        }
    if "answers" in answer:
        result["answers"] = [_fields(item, ("statement_id", "is_true", "explanation"))
                             for item in _items(answer["answers"])]
    rubric = _rubric(value.get("rubric") or answer.get("rubric"))
    if rubric is not None:
        result["rubric"] = rubric
    return result


def public_question_snapshot(value: dict) -> dict:
    """Used at publication, reads and copies, including pre-fix topic snapshots.

    Explicit content fields also remove unexpected nested metadata without
    trying to redact user-authored question/solution prose or changing the bank.
    """
    result = _fields(value, ("content", "type", "difficulty", "topic", "grade", "subject"))
    result["tags"] = _texts(value.get("tags"))
    result["options"] = _options(value.get("options"))
    result["statements"] = ([_fields(item, ("id", "content")) for item in _items(value["statements"])]
                            if value.get("statements") is not None else None)
    result["sub_questions"] = ([_fields(item, ("id", "content", "score")) for item in _items(value["sub_questions"])]
                               if value.get("sub_questions") is not None else None)
    result["answer"] = _answer(value.get("answer"))
    if value.get("rich_content"):
        from app.services.rich_content import normalize_blocks
        result["rich_content"] = normalize_blocks(value["rich_content"])
    return result
