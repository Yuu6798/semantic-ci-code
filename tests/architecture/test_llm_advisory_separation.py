from __future__ import annotations

import datetime as dt

import pytest

from semantic_ci_code.evaluator import VerdictResult
from semantic_ci_code.sensor.delta import DEFAULT_DRIFT_FIELDS, compute_security_delta
from semantic_ci_code.sensor.models import (
    LLMSecurityFinding,
    SASTSecurityFinding,
    SensorProvenance,
    SensorState,
    canonical_id_for_identity,
)
from semantic_ci_code.suite.evaluator import SuiteResult, combine_verdict
from semantic_ci_code.suite.security import evaluate_security_detail


def _provenance(
    sensor_id: str = "semgrep",
    *,
    ruleset_hash: str | None = "sha256:rules",
    adapter_version: str = "adapter-1",
    model_id: str | None = None,
    prompt_hash: str | None = None,
    non_reproducible: bool = False,
) -> SensorProvenance:
    return SensorProvenance(
        sensor_id=sensor_id,
        sensor_version="tool-1",
        adapter_version=adapter_version,
        ruleset_hash=ruleset_hash,
        model_id=model_id,
        prompt_hash=prompt_hash,
        non_reproducible=non_reproducible,
        status="complete",
    )


def _llm_finding(sensor_id: str = "llm-scout") -> LLMSecurityFinding:
    components = (
        "v1",
        "llm",
        sensor_id,
        "missing-authz",
        "src/app.py",
        "src.app.handler",
        "absence",
        "requires authorization guard",
        "0",
    )
    return LLMSecurityFinding(
        category="llm",
        sensor_id=sensor_id,
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity="critical",
        finding_class="missing-authz",
        module_path="src/app.py",
        qualified_name="src.app.handler",
        anchor_kind="absence",
        expected_property="requires authorization guard",
        ordinal=0,
    )


def _sast_finding(severity: str = "critical") -> SASTSecurityFinding:
    components = (
        "v1",
        "sast",
        "semgrep",
        "python.security.eval",
        "src/app.py",
        "src.app.handler",
        "eval(user_input)",
        "0",
    )
    return SASTSecurityFinding(
        category="sast",
        sensor_id="semgrep",
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity=severity,
        rule_id="python.security.eval",
        module_path="src/app.py",
        qualified_name="src.app.handler",
        normalized_text="eval(user_input)",
        ordinal=0,
    )


def _sensor_state(
    *,
    provenances: tuple[SensorProvenance, ...] | None = None,
    findings: tuple[LLMSecurityFinding | SASTSecurityFinding, ...] = (),
) -> SensorState:
    if provenances is None:
        sensors = sorted({finding.sensor_id for finding in findings} or {"semgrep"})
        provenances = tuple(_provenance(sensor_id=sensor_id) for sensor_id in sensors)
    return SensorState(
        provenance_by_sensor={item.sensor_id: item for item in provenances},
        findings=tuple(sorted(findings, key=lambda finding: finding.canonical_id)),
    )


def test_llm_findings_are_rejected_from_verdict_delta_path():
    baseline = _sensor_state(
        provenances=(
            _provenance(
                sensor_id="llm-scout",
                adapter_version="llm-adapter-1",
                model_id="model-x",
                prompt_hash="sha256:prompt",
                non_reproducible=True,
            ),
        )
    )
    candidate = _sensor_state(
        provenances=(
            _provenance(
                sensor_id="llm-scout",
                adapter_version="llm-adapter-1",
                model_id="model-x",
                prompt_hash="sha256:prompt",
                non_reproducible=True,
            ),
        ),
        findings=(_llm_finding(sensor_id="llm-scout"),),
    )

    with pytest.raises(ValueError, match="advisory-only"):
        compute_security_delta(baseline, candidate)
    with pytest.raises(ValueError, match="advisory-only"):
        evaluate_security_detail(None, baseline, candidate, as_of=dt.date(2026, 6, 9))


def test_deterministic_sast_finding_still_drives_suite_fail():
    candidate = _sensor_state(findings=(_sast_finding(severity="critical"),))

    delta = compute_security_delta(_sensor_state(findings=()), candidate)
    suite = combine_verdict(VerdictResult.PASS, delta.aggregate_status)

    assert delta.aggregate_status == "fail"
    assert suite.final is SuiteResult.FAIL


def test_llm_provenance_fields_do_not_participate_in_drift():
    assert "model_id" not in DEFAULT_DRIFT_FIELDS
    assert "prompt_hash" not in DEFAULT_DRIFT_FIELDS
    assert "non_reproducible" not in DEFAULT_DRIFT_FIELDS

    baseline = _sensor_state(
        provenances=(
            _provenance(
                model_id="model-a",
                prompt_hash="sha256:prompt-a",
                non_reproducible=True,
            ),
        )
    )
    candidate = _sensor_state(
        provenances=(
            _provenance(
                model_id="model-b",
                prompt_hash="sha256:prompt-b",
                non_reproducible=False,
            ),
        )
    )

    delta = compute_security_delta(baseline, candidate)

    assert delta.aggregate_status == "pass"
