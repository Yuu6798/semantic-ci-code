from __future__ import annotations

from typing import Any

from semantic_ci_code.cli.output._color import colored

_CATEGORY_ORDER = ("fix_required", "suggested", "unresolved", "info")
_CATEGORY_LABEL = {
    "fix_required": "FIX",
    "suggested": "SUGGEST",
    "unresolved": "UNRESOLVED",
    "info": "INFO",
}
_CATEGORY_COLOR = {
    "fix_required": "red",
    "suggested": "yellow",
    "unresolved": "cyan",
    "info": "gray",
}
_VERDICT_COLOR = {
    "pass": "green",
    "repair": "yellow",
    "fail": "red",
}


def format_human(payload: dict[str, Any], *, use_color: bool) -> str:
    lines: list[str] = []
    lines.append(f"Intent: {payload.get('intent') or '-'}")
    lines.append(f"Primary kind: {payload.get('primary_kind') or '-'}")
    lines.append("")
    lines.append(_verdict_line(payload, use_color=use_color))

    instructions = payload.get("repair_plan", {}).get("instructions", [])
    for category in _CATEGORY_ORDER:
        items = [item for item in instructions if item["category"] == category]
        for item in items:
            lines.append("")
            lines.extend(_instruction_lines(item, use_color=use_color))

    return "\n".join(lines) + "\n"


def _verdict_line(payload: dict[str, Any], *, use_color: bool) -> str:
    verdict = str(payload["verdict"]).upper()
    marker = "✓" if payload["verdict"] == "pass" else "✗"
    summary = payload["summary"]
    text = (
        f"{marker} Verdict: {verdict}  "
        f"({summary['fix_required']} fix_required, "
        f"{summary['suggested']} suggested, "
        f"{summary['info']} info, "
        f"{summary['unresolved']} unresolved, "
        f"{summary['satisfied']} satisfied)"
    )
    return colored(text, _VERDICT_COLOR.get(payload["verdict"], "gray"), enabled=use_color)


def _instruction_lines(item: dict[str, Any], *, use_color: bool) -> list[str]:
    label = _CATEGORY_LABEL[item["category"]]
    header = f"[{label}] {item['repair_code']}  {item['constraint_id']}"
    return [
        colored(header, _CATEGORY_COLOR[item["category"]], enabled=use_color),
        f"  target:    {item['target']}",
        f"  operator:  {item['operator']}",
        f"  message:   {item['message']}",
    ]
