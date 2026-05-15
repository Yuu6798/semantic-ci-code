from __future__ import annotations

from semantic_ci_code.authoring.advisory import Advisory


def format_doctor_human(advisories: tuple[Advisory, ...]) -> str:
    if not advisories:
        return "target-doctor: no advisories detected.\n"
    lines: list[str] = [f"target-doctor: {len(advisories)} advisory(s) detected."]
    for advisory in advisories:
        lines.append("")
        lines.append(f"[{advisory.code}] severity={advisory.severity}")
        lines.append(f"  {advisory.message}")
        if advisory.evidence:
            lines.append("  evidence:")
            for key in sorted(advisory.evidence):
                value = advisory.evidence[key]
                lines.append(f"    {key}: {value!r}")
    lines.append("")
    return "\n".join(lines)
