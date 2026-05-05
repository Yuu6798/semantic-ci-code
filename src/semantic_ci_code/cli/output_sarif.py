from __future__ import annotations

import json
from typing import Any

from semantic_ci_code.cli.output_locations import find_file_line, normalize_annotation_path

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def format_sarif(payload: dict[str, Any]) -> str:
    """Render a verdict payload as deterministic SARIF 2.1.0 JSON."""

    instructions = _instructions_by_id(payload)
    results = [
        _sarif_result(result, instructions.get(result["constraint_id"]))
        for result in payload["results"]
    ]
    rules = _rules_for_results(payload["results"], instructions)
    document = {
        "version": SARIF_VERSION,
        "$schema": SARIF_SCHEMA,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "semantic-ci",
                        "informationUri": "https://github.com/Yuu6798/semantic-ci-code",
                        "rules": rules,
                    },
                },
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "properties": {
                            "subcommand": payload["subcommand"],
                            "verdict": payload["verdict"],
                            "mode": payload.get("mode"),
                            "extractor_pyver": payload["engine"]["extractor_pyver"],
                            "package_version": payload["engine"]["package_version"],
                        },
                    },
                ],
                "results": results,
            },
        ],
    }
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _instructions_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    plan = payload.get("repair_plan") or {}
    return {item["constraint_id"]: item for item in plan.get("instructions", [])}


def _rules_for_results(
    results: list[dict[str, Any]],
    instructions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    rules: list[dict[str, Any]] = []
    for result in results:
        rule_id = result["constraint_id"]
        if rule_id in seen:
            continue
        seen.add(rule_id)
        instruction = instructions.get(rule_id)
        message = (
            instruction["message"]
            if instruction is not None
            else f"Constraint {rule_id} evaluated as {result['status']}."
        )
        rules.append(
            {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": rule_id},
                "fullDescription": {"text": message},
                "properties": {
                    "source": result["source"],
                    "kind": result["kind"],
                    "target": result["target"],
                    "operator": result["operator"],
                    "severity": result["severity"],
                    "unknown_policy": result["unknown_policy"],
                    "repair_code": instruction["repair_code"] if instruction else None,
                },
            }
        )
    return rules


def _sarif_result(
    result: dict[str, Any],
    instruction: dict[str, Any] | None,
) -> dict[str, Any]:
    message = (
        instruction["message"]
        if instruction is not None
        else f"Constraint {result['constraint_id']} evaluated as {result['status']}."
    )
    sarif_result: dict[str, Any] = {
        "ruleId": result["constraint_id"],
        "level": _level(result, instruction),
        "message": {"text": message},
        "properties": {
            "status": result["status"],
            "error_code": result["error_code"],
            "target": result["target"],
            "operator": result["operator"],
        },
    }
    location = _location(result, instruction)
    if location is not None:
        sarif_result["locations"] = [location]
    return sarif_result


def _level(result: dict[str, Any], instruction: dict[str, Any] | None) -> str:
    if result["status"] == "satisfied":
        return "none"
    if result["status"] == "skipped":
        return "note"
    category = instruction["category"] if instruction is not None else None
    if category == "fix_required":
        return "error"
    if category == "suggested":
        return "warning"
    return "note"


def _location(
    result: dict[str, Any],
    instruction: dict[str, Any] | None,
) -> dict[str, Any] | None:
    evidence_sources = [result.get("evidence") or {}]
    if instruction is not None:
        evidence_sources.append(instruction.get("extra_evidence") or {})
        evidence_sources.append({"observed": instruction.get("observed")})
    for source in evidence_sources:
        found = find_file_line(source)
        if found is None:
            continue
        file_path, line = found
        region: dict[str, Any] = {}
        if line is not None:
            region["startLine"] = line
        return {
            "physicalLocation": {
                "artifactLocation": {"uri": normalize_annotation_path(file_path)},
                **({"region": region} if region else {}),
            },
        }
    return None
