from __future__ import annotations

import hashlib
import json

import pytest
from pydantic import ValidationError

from semantic_ci_code.sensor.models import (
    SASTSecurityFinding,
    Suppression,
    canonical_id_for_identity,
)
from semantic_ci_code.ssp.fingerprint import _digest_array as ssp_digest_array

from .helpers import (
    sast_components,
    sast_finding,
    suppression_components,
    suppression_for,
)


def test_canonical_id_uses_ssp_digest_byte_encoding_for_non_ascii_identity():
    components = sast_components(
        "python.security.eval",
        qualified_name="pkg.サービス.実行",
        normalized_text="評価(入力)",
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
        qualified_name="pkg.サービス.実行",
        normalized_text="評価(入力)",
    )
    payload = {
        "kind": "sast",
        "sensor_id": "semgrep",
        "canonical_id": canonical_id_for_identity(components),
        "identity_components": components,
        "severity": "high",
        "message": "finding",
        "rule_id": "python.security.eval",
        "module_path": "src/app.py",
        "qualified_name": "pkg.サービス.実行",
        "normalized_text": "評価(入力)",
    }

    finding = SASTSecurityFinding.model_validate(payload)

    assert finding.canonical_id == canonical_id_for_identity(finding.identity_components)


def test_canonical_id_rejects_empty_identity_components():
    with pytest.raises(ValueError, match="must not be empty"):
        canonical_id_for_identity(())


def test_suppression_rejects_version_prefix_tampering():
    finding = sast_finding()
    suppression = suppression_for(finding.canonical_id)
    payload = suppression.model_dump(mode="json")
    payload["canonical_id"] = "v2:" + suppression.canonical_id.split(":", 1)[1]

    with pytest.raises(ValidationError):
        Suppression.model_validate(payload)


def test_suppression_validator_recomputes_canonical_id_from_identity_components():
    finding = sast_finding()
    components = suppression_components(finding.canonical_id)
    suppression = Suppression(
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        finding_canonical_id=finding.canonical_id,
        reason="accepted test fixture",
    )

    assert suppression.canonical_id == canonical_id_for_identity(suppression.identity_components)
