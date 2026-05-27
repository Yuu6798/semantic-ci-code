"""One-way SSP envelope to SARIF 2.1.0 conversion."""

from __future__ import annotations

import json

from semantic_ci_code.ssp.models import Finding, SASTFinding, SCAFinding, SSPEnvelope

_SARIF_VERSION = "2.1.0"
_SEVERITY_TO_LEVEL = {
    "critical": "error",
    "high": "error",
    "medium": "warning",
    "low": "note",
    "info": "note",
}


def ssp_to_sarif(envelope: SSPEnvelope) -> str:
    rules: dict[str, dict[str, object]] = {}
    results: list[dict[str, object]] = []
    for sensor_id in sorted(envelope.deltas_by_sensor):
        delta = envelope.deltas_by_sensor[sensor_id]
        for finding in delta.added:
            rule_id = _rule_id(finding)
            rules.setdefault(rule_id, {"id": rule_id, "name": rule_id})
            result: dict[str, object] = {
                "ruleId": rule_id,
                "level": _SEVERITY_TO_LEVEL[finding.severity],
                "message": {"text": _message(finding)},
                "properties": {
                    "sspSensor": sensor_id,
                    "sspCategory": finding.category,
                    "sspSeverity": finding.severity,
                },
            }
            location = _location(finding)
            if location is not None:
                result["locations"] = [location]
            results.append(result)

    payload = {
        "version": _SARIF_VERSION,
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "semantic-ci-ssp",
                        "informationUri": "https://github.com/Yuu6798/semantic-ci-code",
                        "rules": [rules[key] for key in sorted(rules)],
                    }
                },
                "results": sorted(
                    results,
                    key=lambda item: (
                        str(item.get("ruleId", "")),
                        json.dumps(item.get("locations", []), sort_keys=True),
                    ),
                ),
            }
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _rule_id(finding: Finding) -> str:
    if isinstance(finding, SASTFinding):
        return finding.rule_id
    if isinstance(finding, SCAFinding):
        return finding.advisory_id
    return finding.category


def _message(finding: Finding) -> str:
    if isinstance(finding, SCAFinding):
        suffix = f" ({', '.join((finding.package_name, finding.installed_version))})"
    else:
        suffix = ""
    return f"{finding.message}{suffix}".strip()


def _location(finding: Finding) -> dict[str, object] | None:
    if not isinstance(finding, SASTFinding) or finding.source_span is None:
        return None
    span = finding.source_span
    return {
        "physicalLocation": {
            "artifactLocation": {"uri": finding.module_path},
            "region": {
                "startLine": span.start_line,
                "startColumn": span.start_col,
                "endLine": span.end_line,
                "endColumn": span.end_col,
            },
        }
    }
