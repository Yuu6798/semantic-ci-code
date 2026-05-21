from __future__ import annotations

import json
from typing import Any


def format_catalog_json(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
