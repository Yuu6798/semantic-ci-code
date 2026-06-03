from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from semantic_ci_code.framework.security_policy import SecurityPolicy
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml


def _canonical_id_for_identity(components: tuple[str, ...]) -> str:
    payload = json.dumps(
        list(components),
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    return f"{components[0]}:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def test_security_policy_defaults_are_empty_policy():
    policy = SecurityPolicy()

    assert policy.findings is None
    assert policy.rules is None
    assert policy.scanner is None
    assert policy.suppressions == ()


def test_target_svp_security_namespace_is_optional():
    target = parse_target_svp_yaml(
        """
intent: refactor auth
change:
  primary_kind: refactor
"""
    )

    assert target.security is None


def test_target_svp_security_namespace_loads_policy_shape():
    target = parse_target_svp_yaml(
        """
intent: harden auth
change:
  primary_kind: feature
security:
  findings:
    added:
      severity:
        not_in: [high, critical]
      max_count: 2
  rules:
    deny_added: [sql-injection]
  scanner:
    require_same_ruleset: false
    require_same_sensor_version: true
    require_same_advisory_db: true
  suppressions:
    - canonical_id: "v1:0000000000000000"
      identity_components: ["v1", "sca", "pip-audit", "django", "3.2.0", "PYSEC-1"]
      reason: "accepted false positive"
      expires: "2026-09-01"
      owner: "security-team"
"""
    )

    assert target.security is not None
    assert target.security.findings is not None
    assert target.security.findings.added is not None
    assert target.security.findings.added.severity is not None
    assert target.security.findings.added.severity.not_in == ("high", "critical")
    assert target.security.findings.added.max_count == 2
    assert target.security.rules is not None
    assert target.security.rules.deny_added == ("sql-injection",)
    assert target.security.scanner is not None
    assert target.security.scanner.require_same_ruleset is False
    assert target.security.scanner.require_same_sensor_version is True
    assert target.security.suppressions[0].expires == dt.date(2026, 9, 1)


def test_security_policy_rejects_structural_errors_only():
    with pytest.raises(ValidationError):
        SecurityPolicy.model_validate({"findings": {"added": {"max_count": -1}}})
    with pytest.raises(ValidationError):
        SecurityPolicy.model_validate(
            {
                "suppressions": [
                    {
                        "canonical_id": "bad",
                        "identity_components": ["v1"],
                        "reason": "x",
                        "expires": "2026-09-01",
                        "owner": "security-team",
                    }
                ]
            }
        )
    with pytest.raises(ValidationError):
        SecurityPolicy.model_validate(
            {
                "suppressions": [
                    {
                        "canonical_id": "v1:0000000000000000",
                        "identity_components": ["v1"],
                        "reason": "",
                        "expires": "not-a-date",
                        "owner": "",
                    }
                ]
            }
        )


@pytest.mark.parametrize(
    "components",
    [
        ("v1",),
        ("v1", "unknown", "sensor", "value", "extra", "parts"),
        ("v1", "sast", "semgrep", "rule", "src/app.py", "pkg.fn", "eval(x)"),
        ("v1", "sast", "semgrep", "rule", "src/app.py", "pkg.fn", "eval(x)", "01"),
        ("v1", "sast", "semgrep", "rule", "src/app.py", "pkg.fn", "eval(x)", "not-int"),
        ("v1", "sca", "pip-audit", "django", "3.2.0"),
        ("v1", "sca", "pip-audit", "django", "3.2.0", ""),
    ],
)
def test_security_policy_rejects_malformed_suppression_identity_shape(components):
    canonical_id = _canonical_id_for_identity(components)

    with pytest.raises(ValidationError, match="identity_components"):
        SecurityPolicy.model_validate(
            {
                "suppressions": [
                    {
                        "canonical_id": canonical_id,
                        "identity_components": components,
                        "reason": "malformed identity shape",
                        "expires": "2026-09-01",
                        "owner": "security-team",
                    }
                ]
            }
        )


def test_security_policy_does_not_validate_suppression_hash_in_framework():
    policy = SecurityPolicy.model_validate(
        {
            "suppressions": [
                {
                    "canonical_id": "v1:0000000000000000",
                    "identity_components": ["v1", "sca", "pip-audit", "django", "3.2.0", "PYSEC-1"],
                    "reason": "framework is structure-only",
                    "expires": "2026-09-01",
                    "owner": "security-team",
                }
            ]
        }
    )

    assert policy.suppressions[0].canonical_id == "v1:0000000000000000"


def test_security_policy_module_does_not_import_sensor_layer():
    path = Path("src/semantic_ci_code/framework/security_policy.py")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)

    assert not any(
        item == "semantic_ci_code.sensor" or item.startswith("semantic_ci_code.sensor.")
        for item in imports
    )
