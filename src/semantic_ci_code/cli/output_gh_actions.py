from __future__ import annotations

from typing import Any

from semantic_ci_code.cli.output_locations import find_file_line, normalize_annotation_path


def format_gh_actions(payload: dict[str, Any]) -> str:
    """Render repair instructions as deterministic GitHub Actions commands."""

    lines = [_workflow_command(instruction) for instruction in _instructions(payload)]
    return "".join(f"{line}\n" for line in lines)


def _instructions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    plan = payload.get("repair_plan") or {}
    return list(plan.get("instructions", []))


def _workflow_command(instruction: dict[str, Any]) -> str:
    command = _command_name(instruction)
    properties = _properties(instruction)
    message = (
        f"{instruction['repair_code']} {instruction['constraint_id']}: {instruction['message']}"
    )
    if properties:
        rendered = ",".join(f"{key}={_escape_property(value)}" for key, value in properties.items())
        return f"::{command} {rendered}::{_escape_message(message)}"
    return f"::{command}::{_escape_message(message)}"


def _command_name(instruction: dict[str, Any]) -> str:
    category = instruction["category"]
    if category == "fix_required":
        return "error"
    if category == "suggested":
        return "warning"
    return "notice"


def _properties(instruction: dict[str, Any]) -> dict[str, str]:
    found = find_file_line(instruction)
    properties: dict[str, str] = {}
    if found is None:
        return properties
    file_path, line = found
    properties["file"] = normalize_annotation_path(file_path)
    if line is not None:
        properties["line"] = str(line)
    return properties


def _escape_message(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(value: str) -> str:
    return _escape_message(value).replace(":", "%3A").replace(",", "%2C")
