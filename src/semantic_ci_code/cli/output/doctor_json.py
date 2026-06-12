from __future__ import annotations

from typing import Any

from semantic_ci_code.authoring.advisory import Advisory

DOCTOR_ADVISORY_SCHEMA_VERSION = "advisory-2"


def build_doctor_payload(advisories: tuple[Advisory, ...]) -> dict[str, Any]:
    return {
        "schema_version": DOCTOR_ADVISORY_SCHEMA_VERSION,
        "subcommand": "target-doctor",
        "advisories": [_advisory_payload(a) for a in advisories],
    }


def _advisory_payload(advisory: Advisory) -> dict[str, Any]:
    return {
        "code": advisory.code,
        "severity": advisory.severity,
        "message": advisory.message,
        "evidence": dict(advisory.evidence),
    }
