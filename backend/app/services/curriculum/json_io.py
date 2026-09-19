import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any:
    """Read one UTF-8 JSON document without applying domain policy."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)
