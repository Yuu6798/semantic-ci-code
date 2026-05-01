from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml_mapping(path: str | Path) -> dict[str, Any]:
    """Load a YAML file whose root must be a mapping."""
    with Path(path).open(encoding="utf-8") as stream:
        data = yaml.safe_load(stream)

    if data is None:
        msg = "YAML root must be a mapping, got empty document."
        raise ValueError(msg)

    if not isinstance(data, dict):
        msg = "YAML root must be a mapping."
        raise ValueError(msg)

    return data
