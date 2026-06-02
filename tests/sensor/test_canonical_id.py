from __future__ import annotations

import hashlib
import json

import pytest

from semantic_ci_code.sensor.models import (
    SASTSecurityFinding,
    SensorState,
    canonical_id_for_identity,
)
from semantic_ci_code.ssp.fingerprint import _digest_array as ssp_digest_array

from .helpers import sast_components, sast_finding, sensor_state


def test_canonical_id_uses_ssp_digest_byte_encoding_for_non_ascii_identity():
    components = sast_components(
        "python.security.eval",
        qualified_name="pkg.\u30b5\u30fc\u30d3\u30b9.\u5b9f\u884c",
        normalized_text="\u8a55\u4fa1(\u5165\u529b)",
    )
    expected_digest = hashlib.sha256(
        json.dumps(
            list(components),
            ensure_ascii=False,
            sort_keys=False,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]

    assert canonical_id_for_identity(components) == f"v1:{expected_digest}"
    assert expected_digest == ssp_digest_array(list(components))


def test_adapter_supplied_canonical_id_matches_validator_recalculation():
    components = sast_components(
        "python.security.eval",
        qualified_name="pkg.\u30b5\u30fc\u30d3\u30b9.\u5b9f\u884c",
        normalized_text="\u8a55\u4fa1(\u5165\u529b)",
    )
    payload = {
        "category": "sast",
        "sensor_id": "semgrep",
        "canonical_id": canonical_id_for_identity(components),
        "identity_components": components,
        "severity": "high",
        "message": "finding",
        "rule_id": "python.security.eval",
        "module_path": "src/app.py",
        "qualified_name": "pkg.\u30b5\u30fc\u30d3\u30b9.\u5b9f\u884c",
        "normalized_text": "\u8a55\u4fa1(\u5165\u529b)",
        "ordinal": 0,
    }

    finding = SASTSecurityFinding.model_validate(payload)

    assert finding.canonical_id == canonical_id_for_identity(finding.identity_components)


def test_canonical_id_rejects_empty_identity_components():
    with pytest.raises(ValueError, match="must not be empty"):
        canonical_id_for_identity(())


def test_sast_identity_components_include_ssp_v0_fingerprint_axes():
    components = sast_components(
        "python.security.eval",
        module_path="src/app.py",
        qualified_name="src.app.handler",
        normalized_text="eval(user_input)",
        ordinal=7,
    )

    assert components[3:] == (
        "python.security.eval",
        "src/app.py",
        "src.app.handler",
        "eval(user_input)",
        "7",
    )


def test_sast_ordinal_disambiguates_duplicate_findings_in_sensor_state():
    first = sast_finding("python.security.eval", ordinal=0)
    second = sast_finding("python.security.eval", ordinal=1)

    assert first.canonical_id != second.canonical_id
    state = sensor_state(findings=(first, second))

    assert isinstance(state, SensorState)
    assert len(state.findings) == 2
