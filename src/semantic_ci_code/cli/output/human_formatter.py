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
    "unknown": "cyan",
}


def format_human(payload: dict[str, Any], *, use_color: bool) -> str:
    lines: list[str] = []
    if payload.get("mode") == "smoke":
        lines.append("[smoke mode] partial CodeState (api_surface, imports, effects only)")
    lines.append(f"Intent: {payload.get('intent') or '-'}")
    lines.append(f"Primary kind: {payload.get('primary_kind') or '-'}")
    lines.append("")
    lines.append(_verdict_line(payload, use_color=use_color))
    lines.extend(_suite_lines(payload, use_color=use_color))

    instructions = payload.get("repair_plan", {}).get("instructions", [])
    for category in _CATEGORY_ORDER:
        items = [item for item in instructions if item["category"] == category]
        for item in items:
            lines.append("")
            lines.extend(_instruction_lines(item, use_color=use_color))

    lines.append("")
    lines.append(_cache_line(payload))
    return "\n".join(lines) + "\n"


def format_compile_human(payload: dict[str, Any], *, use_color: bool) -> str:
    target = payload["compiled_target"]
    constraints = target["constraints"]
    secondary = target["allowed_secondary_kinds"]
    lines: list[str] = [
        f"Intent: {target['intent']}",
        f"Primary kind: {target['primary_kind']}",
        f"Allowed secondary: {', '.join(secondary) if secondary else '-'}",
        f"Constraints: {len(constraints)}",
    ]
    api_allow = target.get("api_surface_policy", {}).get("allow_changes", [])
    effect_allow = target.get("effects_policy", {}).get("allow_new", [])
    if api_allow:
        lines.append(f"API allow changes: {len(api_allow)}")
    if effect_allow:
        lines.append(f"Effect allow new: {len(effect_allow)}")
    lines.append("")

    for index, constraint in enumerate(constraints):
        if index:
            lines.append("")
        lines.extend(_compiled_constraint_lines(constraint, use_color=use_color))

    lines.append("")
    lines.append(_cache_line(payload))
    return "\n".join(lines).rstrip() + "\n"


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
        f"{summary['satisfied']} satisfied, "
        f"{summary.get('skipped', 0)} skipped)"
    )
    return colored(text, _VERDICT_COLOR.get(payload["verdict"], "gray"), enabled=use_color)


def _suite_lines(payload: dict[str, Any], *, use_color: bool) -> list[str]:
    security = payload.get("security")
    suite_verdict = payload.get("suite_verdict")
    if security is None or suite_verdict is None:
        return []
    security_verdict = security["verdict"]
    lines = [
        colored(
            f"Security verdict: {str(security_verdict).upper()}  (as_of={security['as_of']})",
            _VERDICT_COLOR.get(security_verdict, "gray"),
            enabled=use_color,
        ),
        colored(
            f"Suite final: {str(suite_verdict).upper()}",
            _VERDICT_COLOR.get(suite_verdict, "gray"),
            enabled=use_color,
        ),
    ]
    for sensor in security.get("sensors", []):
        lines.extend(_security_sensor_lines(sensor, use_color=use_color))
    return lines


def _security_sensor_lines(sensor: dict[str, Any], *, use_color: bool) -> list[str]:
    status = sensor["status"]
    lines = [
        colored(
            f"  [{sensor['sensor_id']}] {str(status).upper()}  "
            f"added={len(sensor.get('added', []))} "
            f"removed={len(sensor.get('removed', []))} "
            f"suppressed={len(sensor.get('suppressed', []))} "
            f"unchanged={sensor.get('unchanged_count', 0)}",
            _VERDICT_COLOR.get(status, "gray"),
            enabled=use_color,
        )
    ]
    drift_reason = sensor.get("drift_reason")
    if drift_reason:
        lines.append(f"    drift: {drift_reason}")
    for finding in sensor.get("added", []):
        lines.append("    + " + _security_finding_summary(finding))
    if sensor.get("suppressed"):
        lines.append(f"    suppressed: {len(sensor['suppressed'])}")
    return lines


def _security_finding_summary(finding: dict[str, Any]) -> str:
    if finding.get("category") == "sast":
        rule = finding.get("rule_id") or finding.get("canonical_id")
        location = finding.get("module_path") or "-"
        source_span = finding.get("source_span") or {}
        if source_span.get("start_line") is not None:
            location = f"{location}:{source_span['start_line']}"
        return f"{rule} [{finding.get('severity')}] at {location} - {finding.get('message') or '-'}"
    advisory = finding.get("advisory_id") or finding.get("canonical_id")
    package = finding.get("package_name") or "-"
    version = finding.get("installed_version") or "-"
    return (
        f"{advisory} [{finding.get('severity')}] for {package} {version} - "
        f"{finding.get('message') or '-'}"
    )


def _instruction_lines(item: dict[str, Any], *, use_color: bool) -> list[str]:
    if item["status"] == "skipped":
        header = f"[SKIPPED] {item['repair_code']}  {item['constraint_id']}"
        if not use_color:
            header = f"~ {header}"
        color = "gray"
    else:
        label = _CATEGORY_LABEL[item["category"]]
        header = f"[{label}] {item['repair_code']}  {item['constraint_id']}"
        color = _CATEGORY_COLOR[item["category"]]
    lines = [
        colored(header, color, enabled=use_color),
        f"  target:    {item['target']}",
        f"  operator:  {item['operator']}",
        f"  message:   {item['message']}",
    ]
    cause = item.get("unknown_cause")
    if cause:
        lines.append(f"  cause:     {cause}")
    return lines


def _compiled_constraint_lines(item: dict[str, Any], *, use_color: bool) -> list[str]:
    label = item["source"].upper()
    color = "cyan" if item["source"] == "template" else "yellow"
    lines = [
        colored(f"[{label}] {item['id']}", color, enabled=use_color),
        f"  kind:           {item['kind']}",
        f"  target:         {item['target']}",
        f"  operator:       {item['operator']}",
        f"  severity:       {item['severity']}",
        f"  unknown_policy: {item['unknown_policy']}",
    ]
    if item["tolerance"] is not None:
        lines.append(f"  tolerance:      {item['tolerance']}")
    if item["evidence_required"]:
        lines.append("  evidence_required: true")
    if item["scope"] is not None:
        lines.append(f"  scope:          {item['scope']}")
    if item["expected"] is not None:
        lines.append(f"  expected:       {item['expected']}")
    return lines


def _cache_line(payload: dict[str, Any]) -> str:
    cache = payload.get("cache") or {}
    return (
        "cache: "
        f"hit={cache.get('hit', 0)} "
        f"miss={cache.get('miss', 0)} "
        f"invalid={cache.get('invalid', 0)} "
        f"write_failed={cache.get('write_failed', 0)} "
        f"disabled={str(cache.get('disabled', True)).lower()}"
    )
