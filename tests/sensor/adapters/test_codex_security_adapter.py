from __future__ import annotations

import json
from pathlib import Path

import pytest

from semantic_ci_code.domain.state_schema import APISurfaceEntry, CodeState, RenameEntry
from semantic_ci_code.sensor.adapters.llm import (
    CODEX_SECURITY_SENSOR_ADAPTER_VERSION,
    CODEX_SECURITY_SENSOR_ID,
    CodexSecurityAdapter,
    RawLLMFinding,
    sensor_state_from_codex_security_json,
)
from semantic_ci_code.sensor.advisory import compute_advisory_reprojection
from semantic_ci_code.sensor.delta import compute_security_delta
from semantic_ci_code.sensor.models import LLMSecurityFinding, SensorState

FIXTURES = Path(__file__).parents[1] / "fixtures"
COMPLETE_FIXTURE = FIXTURES / "codex_security_complete.json"
ERROR_FIXTURE = FIXTURES / "codex_security_error.json"
ADAPTER_SOURCE = (
    Path(__file__).parents[3]
    / "src"
    / "semantic_ci_code"
    / "sensor"
    / "adapters"
    / "llm"
    / "codex_security.py"
)


def _payload(path: Path = COMPLETE_FIXTURE) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _empty_sensor_state() -> SensorState:
    return SensorState(provenance_by_sensor={}, findings=())


def _site(
    fqn: str,
    *,
    decorators: tuple[str, ...] = (),
) -> APISurfaceEntry:
    return APISurfaceEntry(
        fqn=fqn,
        kind="function",
        visibility="public",
        decorators=decorators,
    )


def test_codex_security_adapter_implements_recorded_fixture_protocol():
    adapter = CodexSecurityAdapter.from_json(_payload())

    raw_findings = adapter.scan_candidate(CodeState())
    provenance = adapter.provenance()

    assert adapter.sensor_id == CODEX_SECURITY_SENSOR_ID
    assert len(raw_findings) == 3
    assert all(isinstance(finding, RawLLMFinding) for finding in raw_findings)
    assert provenance.sensor_id == CODEX_SECURITY_SENSOR_ID
    assert provenance.sensor_version == "codex-security-fixture-v1"
    assert provenance.adapter_version == CODEX_SECURITY_SENSOR_ADAPTER_VERSION
    assert provenance.model_id == "gpt-5-codex-security"
    assert provenance.prompt_hash == "sha256:prompt-fixture"
    assert provenance.non_reproducible is True
    assert provenance.status == "complete"


def test_codex_security_from_json_translates_fixture_to_advisory_sensor_state():
    state = sensor_state_from_codex_security_json(_payload())

    provenance = state.provenance_by_sensor[CODEX_SECURITY_SENSOR_ID]
    assert provenance.non_reproducible is True
    assert provenance.status == "complete"
    assert len(state.findings) == 3
    assert tuple(finding.canonical_id for finding in state.findings) == tuple(
        sorted(finding.canonical_id for finding in state.findings)
    )

    finding = next(
        item
        for item in state.findings
        if isinstance(item, LLMSecurityFinding)
        and item.qualified_name == "src.renamed.secure_endpoint"
    )
    assert finding.module_path == "src/renamed.py"
    assert finding.ordinal == 0
    assert finding.identity_components == (
        "v1",
        "llm",
        CODEX_SECURITY_SENSOR_ID,
        finding.finding_class,
        finding.module_path,
        finding.qualified_name,
        finding.anchor_kind,
        finding.expected_property,
        str(finding.ordinal),
    )
    assert finding.source_span is not None
    assert finding.source_span.start_col == 4


def test_codex_security_projection_is_centralized_in_protocol_helper():
    source = ADAPTER_SOURCE.read_text(encoding="utf-8")

    assert "canonical_id_for_identity" not in source
    assert "project_to_canonical(finding, sensor_id=self.sensor_id)" in source


@pytest.mark.parametrize("missing_key", ["model_id", "prompt_hash"])
def test_codex_security_rejects_missing_or_empty_attribution_fields(missing_key: str):
    payload = _payload()
    payload[missing_key] = ""

    with pytest.raises(ValueError, match=missing_key):
        CodexSecurityAdapter(payload)

    del payload[missing_key]
    with pytest.raises(ValueError, match=missing_key):
        CodexSecurityAdapter(payload)


def test_codex_security_non_complete_payload_has_error_provenance_and_empty_findings():
    state = sensor_state_from_codex_security_json(_payload(ERROR_FIXTURE))

    provenance = state.provenance_by_sensor[CODEX_SECURITY_SENSOR_ID]
    assert provenance.status == "error"
    assert provenance.error_message == "recorded Codex Security run failed"
    assert state.findings == ()


def test_codex_security_non_complete_payload_requires_error_message():
    payload = _payload(ERROR_FIXTURE)
    payload["error_message"] = None

    with pytest.raises(ValueError, match="requires error_message"):
        CodexSecurityAdapter(payload)


def test_codex_security_findings_are_parsed_through_raw_llm_finding_validators():
    payload = _payload()
    findings = payload["findings"]
    assert isinstance(findings, list)
    first = dict(findings[0])
    first["expected_property"] = ""
    payload["findings"] = [first]

    with pytest.raises(ValueError, match="absence LLM findings require expected_property"):
        CodexSecurityAdapter(payload)


def test_codex_security_assigns_missing_ordinals_by_group_occurrence_order():
    payload = _payload()
    payload["findings"] = [
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "first",
        },
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "second",
        },
    ]

    adapter = CodexSecurityAdapter(payload)

    assert tuple(finding.ordinal for finding in adapter.scan_candidate(CodeState())) == (0, 1)
    state = adapter.sensor_state()
    assert len({finding.canonical_id for finding in state.findings}) == 2


def test_codex_security_respects_explicit_ordinals():
    payload = _payload()
    payload["findings"] = [
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "explicit ordinal",
            "ordinal": 7,
        }
    ]

    adapter = CodexSecurityAdapter(payload)

    assert tuple(finding.ordinal for finding in adapter.scan_candidate(CodeState())) == (7,)


def test_codex_security_assigns_implicit_ordinal_after_reserved_explicit_ordinal():
    payload = _payload()
    payload["findings"] = [
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "explicit first",
            "ordinal": 0,
        },
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "implicit second",
        },
    ]

    adapter = CodexSecurityAdapter(payload)

    assert tuple(finding.ordinal for finding in adapter.scan_candidate(CodeState())) == (0, 1)


def test_codex_security_rejects_duplicate_explicit_ordinals():
    payload = _payload()
    payload["findings"] = [
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "first",
            "ordinal": 2,
        },
        {
            "finding_class": "missing-authz",
            "module_path": "src/app.py",
            "qualified_name": "src.app.handler",
            "anchor_kind": "absence",
            "expected_property": "requires authorization guard",
            "severity": "high",
            "message": "second",
            "ordinal": 2,
        },
    ]

    with pytest.raises(ValueError, match="duplicate Codex Security ordinal"):
        CodexSecurityAdapter(payload)


def test_codex_security_sensor_state_is_rejected_by_verdict_security_delta_path():
    state = sensor_state_from_codex_security_json(_payload())

    with pytest.raises(ValueError, match="LLM findings are advisory-only"):
        compute_security_delta(_empty_sensor_state(), state)


def test_codex_security_fixture_connects_to_advisory_reprojection_with_renames():
    state = sensor_state_from_codex_security_json(_payload())
    findings = tuple(
        finding for finding in state.findings if isinstance(finding, LLMSecurityFinding)
    )
    baseline = CodeState(
        api_surface=(
            _site("src.app.open_endpoint", decorators=()),
            _site("src.original.secure_endpoint", decorators=("login_required",)),
        )
    )
    renames = (RenameEntry(old_path="src/original.py", new_path="src/renamed.py"),)

    result = compute_advisory_reprojection(findings, baseline, renames=renames)

    assert {finding.qualified_name for finding in result.pre_existing} == {"src.app.open_endpoint"}
    assert {finding.qualified_name for finding in result.added} == {
        "src.fetch.load_url",
        "src.renamed.secure_endpoint",
    }


def test_codex_security_translation_is_deterministic_for_same_payload():
    first = sensor_state_from_codex_security_json(_payload()).model_dump(mode="json")
    second = sensor_state_from_codex_security_json(_payload()).model_dump(mode="json")

    assert first == second
    assert json.dumps(first, sort_keys=True, ensure_ascii=False) == json.dumps(
        second,
        sort_keys=True,
        ensure_ascii=False,
    )
