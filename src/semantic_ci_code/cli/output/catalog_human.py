from __future__ import annotations

import json
from typing import Any


def format_catalog_human(catalog: dict[str, Any]) -> str:
    lines: list[str] = [
        f"target-catalog ({catalog['schema_version']})",
        "",
        "primary_kinds",
    ]
    lines.extend(f"- {kind}" for kind in catalog["primary_kinds"])

    lines.append("")
    lines.append("targets")
    for path, entry in catalog["targets"].items():
        lines.append(f"- {path}")
        lines.append(f"  kind: {entry['kind']}")
        lines.append(f"  category: {entry['category']}")
        if "match_schema" in entry:
            schema = entry["match_schema"]
            optional = _join(schema["optional_keys"])
            forbidden = _join(schema["forbidden_keys"])
            required = " or ".join(schema.get("required_any_keys", ())) or schema["required_key"]
            lines.append(f"  match_schema: required={required}")
            lines.append(f"    optional: {optional}")
            lines.append(f"    forbidden: {forbidden}")
        lines.append(f"  operators: {_join(entry['operators'])}")

    lines.append("")
    lines.append("templates")
    for kind, entry in catalog["templates"].items():
        lines.append(f"- {kind}")
        constraints = entry["expanded_constraints"]
        if not constraints:
            lines.append("  (none)")
            continue
        for constraint in constraints:
            lines.append(
                "  - "
                f"{constraint['kind']} {constraint['target']} "
                f"{constraint['operator']} expected={_format_value(constraint['expected'])} "
                f"severity={constraint['severity']} unknown_policy={constraint['unknown_policy']}"
            )

    lines.append("")
    lines.append("operators")
    for operator, entry in catalog["operators"].items():
        lines.append(f"- {operator}")
        lines.append(f"  class: {entry['class']}")
        lines.append(f"  applies_to_collection: {_join(entry['applies_to_collection'])}")
        lines.append(f"  evidence_emits: {_join(entry['evidence_emits'])}")
    lines.append("")
    return "\n".join(lines)


def _join(values: Any) -> str:
    if isinstance(values, dict):
        keys = sorted(values)
        return ", ".join(keys) if keys else "(none)"
    if not values:
        return "(none)"
    return ", ".join(str(value) for value in values)


def _format_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
