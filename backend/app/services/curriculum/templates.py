import json

from app.services.curriculum.constants import template_path
from app.services.curriculum.json_io import read_json


def list_templates(template_type: str) -> list[dict]:
    path = template_path(template_type)
    if path is None or not path.exists():
        return []

    try:
        data = read_json(path)
    except json.JSONDecodeError:
        return []

    return data.get("templates", [])


def load_template(template_type: str, template_id: str) -> dict | None:
    return next(
        (
            template
            for template in list_templates(template_type)
            if template.get("id") == template_id
        ),
        None,
    )
