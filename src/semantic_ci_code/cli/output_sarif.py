from __future__ import annotations

import json
from typing import Any

from semantic_ci_code.cli.output_locations import find_file_line, normalize_annotation_path

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


def format_sarif(payload: dict[str, Any]) -> str:
    """Render a verdict payload as deterministic SARIF 2.1.0 JSON."""

    instructions = _instructions_by_id(payload)
    code_results = [
        _sarif_result(result, instructions.get(result["constraint_id"]))
        for result in payload["results"]
    ]
    security_results = _security_sarif_results(payload.get("security"))
    results = code_results + security_results
    rules = _dedupe_rules(
        [
            *_rules_for_results(payload["results"], instructions),
            *_security_rules_for_results(security_results),
        ]
    )
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


def _dedupe_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for rule in rules:
        by_id.setdefault(rule["id"], rule)
    return list(by_id.values())


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
            "unknown_cause": result.get("unknown_cause"),
            "target": result["target"],
            "operator": result["operator"],
        },
    }
    location = _location(result, instruction)
    if location is not None:
        sarif_result["locations"] = [location]
    return sarif_result


def _security_sarif_results(security: dict[str, Any] | None) -> list[dict[str, Any]]:
    if security is None:
        return []
    results: list[dict[str, Any]] = []
    for sensor in sorted(security.get("sensors", []), key=lambda item: item["sensor_id"]):
        drift_reason = sensor.get("drift_reason")
        if sensor.get("status") == "unknown" and drift_reason:
            results.append(_security_unknown_result(sensor, drift_reason))
        sensor_results: list[dict[str, Any]] = []
        for finding in sorted(sensor.get("added", []), key=lambda item: item["canonical_id"]):
            sensor_results.append(_security_finding_result(finding))
        results.extend(sensor_results)
        if sensor.get("status") == "fail" and not _has_visible_failure(sensor_results):
            results.append(
                _security_policy_result(
                    "security/policy-violation",
                    f"Security policy failed for sensor {sensor['sensor_id']}.",
                    sensor_id=sensor["sensor_id"],
                )
            )
    if security.get("global_count_violated"):
        results.append(
            _security_policy_result(
                "security/policy-global-count",
                "Security policy findings.added.max_count was exceeded.",
                sensor_id=None,
            )
        )
    return results


def _security_finding_result(finding: dict[str, Any]) -> dict[str, Any]:
    rule_id = _security_rule_id(finding)
    message = finding.get("message") or f"Security finding {finding['canonical_id']} was added."
    result: dict[str, Any] = {
        "ruleId": rule_id,
        "level": _security_level(finding.get("severity")),
        "message": {"text": message},
        "properties": {
            "category": finding["category"],
            "sensor_id": finding["sensor_id"],
            "severity": finding["severity"],
            "canonical_id": finding["canonical_id"],
        },
    }
    location = _security_location(finding)
    if location is not None:
        result["locations"] = [location]
    return result


def _security_unknown_result(sensor: dict[str, Any], reason: str) -> dict[str, Any]:
    rule_id = (
        "security/provenance-drift"
        if sensor.get("provenance_changed")
        else "security/sensor-unknown"
    )
    return {
        "ruleId": rule_id,
        "level": "note",
        "message": {"text": reason},
        "properties": {
            "category": "sensor",
            "sensor_id": sensor["sensor_id"],
            "severity": "info",
            "canonical_id": None,
        },
    }


def _security_policy_result(rule_id: str, message: str, *, sensor_id: str | None) -> dict[str, Any]:
    return {
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": message},
        "properties": {
            "category": "policy",
            "sensor_id": sensor_id,
            "severity": "critical",
            "canonical_id": None,
        },
    }


def _has_visible_failure(results: list[dict[str, Any]]) -> bool:
    return any(result["level"] in {"error", "warning"} for result in results)


def _security_rules_for_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for result in results:
        rule_id = result["ruleId"]
        rules.append(
            {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": rule_id},
                "fullDescription": {"text": result["message"]["text"]},
                "properties": {
                    "source": "security",
                    **result.get("properties", {}),
                },
            }
        )
    return rules


def _security_rule_id(finding: dict[str, Any]) -> str:
    if finding["category"] == "sast":
        return f"security/{finding['rule_id']}"
    return f"security/{finding['advisory_id']}"


def _security_level(severity: str | None) -> str:
    if severity in {"critical", "high"}:
        return "error"
    if severity == "medium":
        return "warning"
    return "note"


def _security_location(finding: dict[str, Any]) -> dict[str, Any] | None:
    if finding.get("category") != "sast":
        return None
    source_span = finding.get("source_span")
    if not source_span:
        return None
    region = {
        "startLine": source_span["start_line"],
        "endLine": source_span["end_line"],
        "startColumn": max(1, source_span["start_col"]),
        "endColumn": max(1, source_span["end_col"]),
    }
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": normalize_annotation_path(finding["module_path"])},
            "region": region,
        }
    }


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
