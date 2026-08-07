from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from semantic_ci_code.sensor.adapters.llm import (
    LLM_ENSEMBLE_ADAPTER_VERSION,
    LLM_ENSEMBLE_SENSOR_ID,
    LLMSensorProvenance,
    RawLLMFinding,
    aggregate_advisory_states,
    project_to_canonical,
)
from semantic_ci_code.sensor.models import (
    LLMSecurityFinding,
    SensorProvenance,
    SensorState,
    SourceSpan,
)

AGGREGATE_SOURCE = (
    Path(__file__).parents[3]
    / "src"
    / "semantic_ci_code"
    / "sensor"
    / "adapters"
    / "llm"
    / "aggregate.py"
)


def test_aggregate_deduplicates_same_anchor_by_reprojecting_to_ensemble_sensor():
    codex_finding = _finding("codex-security", severity="medium", message="codex")
    claude_finding = _finding("claude-security", severity="high", message="claude")

    aggregation = aggregate_advisory_states(
        (
            _state("codex-security", model_id="codex", finding=codex_finding),
            _state("claude-security", model_id="claude", finding=claude_finding),
        )
    )

    assert tuple(aggregation.state.provenance_by_sensor) == (LLM_ENSEMBLE_SENSOR_ID,)
    assert len(aggregation.state.findings) == 1
    [ensemble_finding] = aggregation.state.findings
    assert isinstance(ensemble_finding, LLMSecurityFinding)
    assert ensemble_finding.sensor_id == LLM_ENSEMBLE_SENSOR_ID
    assert ensemble_finding.severity == "high"
    assert ensemble_finding.canonical_id not in {
        codex_finding.canonical_id,
        claude_finding.canonical_id,
    }
    assert tuple(member.sensor_id for member in aggregation.members) == (
        "claude-security",
        "codex-security",
    )


def test_aggregate_uses_protocol_projection_helper_not_identity_digest_directly():
    source = AGGREGATE_SOURCE.read_text(encoding="utf-8")

    assert "canonical_id_for_identity" not in source
    assert "project_to_canonical(" in source


def test_aggregate_conflict_resolution_uses_max_severity_and_member_order_tiebreak():
    z_finding = _finding(
        "z-sensor",
        severity="info",
        message="z message",
        source_span=SourceSpan(start_line=9, end_line=9, start_col=0, end_col=1),
    )
    a_finding = _finding(
        "a-sensor",
        severity="critical",
        message="a message",
        source_span=SourceSpan(start_line=1, end_line=1, start_col=0, end_col=1),
    )

    aggregation = aggregate_advisory_states(
        (
            _state("z-sensor", model_id="z-model", finding=z_finding),
            _state("a-sensor", model_id="a-model", finding=a_finding),
        )
    )

    [finding] = aggregation.state.findings
    assert finding.severity == "critical"
    assert finding.message == "a message"
    assert finding.source_span == a_finding.source_span


def test_aggregate_rejects_non_llm_state_instead_of_silently_skipping_it():
    llm_state = _state(
        "codex-security",
        model_id="codex",
        finding=_finding("codex-security", severity="medium", message="codex"),
    )
    deterministic_state = SensorState(
        provenance_by_sensor={
            "semgrep": SensorProvenance(
                sensor_id="semgrep",
                sensor_version="semgrep-v1",
            )
        },
        findings=(),
    )

    with pytest.raises(ValueError, match="only accepts LLM advisory provenance"):
        aggregate_advisory_states((llm_state, deterministic_state))


def test_aggregate_is_input_order_invariant():
    first = _state(
        "z-sensor",
        model_id="z-model",
        prompt_hash="sha256:z",
        finding=_finding("z-sensor", severity="low", message="z"),
    )
    second = _state(
        "a-sensor",
        model_id="a-model",
        prompt_hash="sha256:a",
        finding=_finding("a-sensor", severity="critical", message="a"),
    )

    forward = aggregate_advisory_states((first, second))
    reverse = aggregate_advisory_states((second, first))

    assert forward.state.model_dump(mode="json") == reverse.state.model_dump(mode="json")
    assert [item.model_dump(mode="json") for item in forward.members] == [
        item.model_dump(mode="json") for item in reverse.members
    ]


def test_aggregate_tolerates_partial_member_errors_but_errors_when_all_members_fail():
    complete = _state(
        "codex-security",
        model_id="codex",
        finding=_finding("codex-security", severity="medium", message="codex"),
    )
    failed = _state(
        "claude-security",
        model_id="claude",
        status="timeout",
        error_message="claude timed out",
    )

    partial = aggregate_advisory_states((failed, complete))

    assert partial.state.provenance_by_sensor[LLM_ENSEMBLE_SENSOR_ID].status == "complete"
    assert len(partial.state.findings) == 1
    assert {member.status for member in partial.members} == {"complete", "timeout"}

    all_failed = aggregate_advisory_states(
        (
            failed,
            _state(
                "gemini-security",
                model_id="gemini",
                status="error",
                error_message="gemini failed",
            ),
        )
    )

    provenance = all_failed.state.provenance_by_sensor[LLM_ENSEMBLE_SENSOR_ID]
    assert provenance.status == "error"
    assert all_failed.state.findings == ()
    assert "claude-security/claude timeout" in provenance.error_message
    assert "gemini-security/gemini error" in provenance.error_message


def test_aggregate_provenance_is_derived_deterministically_from_members():
    first = _state(
        "z-sensor",
        model_id="z-model",
        prompt_hash="sha256:z",
        finding=_finding("z-sensor", severity="low", message="z"),
    )
    second = _state(
        "a-sensor",
        model_id="a-model",
        prompt_hash="sha256:a",
        finding=_finding("a-sensor", severity="critical", message="a"),
    )

    aggregation = aggregate_advisory_states((first, second))
    provenance = aggregation.state.provenance_by_sensor[LLM_ENSEMBLE_SENSOR_ID]

    assert provenance.adapter_version == LLM_ENSEMBLE_ADAPTER_VERSION
    assert provenance.model_id == "ensemble:a-model,z-model"
    expected_pairs = [["a-model", "sha256:a"], ["z-model", "sha256:z"]]
    expected_payload = json.dumps(
        expected_pairs,
        ensure_ascii=False,
        sort_keys=False,
        separators=(",", ":"),
    )
    assert provenance.prompt_hash == (
        "sha256:" + hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
    )
    assert provenance.model_dump(mode="json") == aggregate_advisory_states(
        (second, first)
    ).state.provenance_by_sensor[LLM_ENSEMBLE_SENSOR_ID].model_dump(mode="json")


def _state(
    sensor_id: str,
    *,
    model_id: str,
    prompt_hash: str | None = None,
    finding: LLMSecurityFinding | None = None,
    status: str = "complete",
    error_message: str | None = None,
) -> SensorState:
    provenance = LLMSensorProvenance(
        sensor_id=sensor_id,
        sensor_version=f"{sensor_id}-v1",
        adapter_version=f"{sensor_id}-adapter",
        identity_algorithm_version="v1",
        model_id=model_id,
        prompt_hash=prompt_hash or f"sha256:{model_id}",
        non_reproducible=True,
        status=status,  # type: ignore[arg-type]
        error_message=error_message,
    )
    findings = () if finding is None else (finding,)
    return SensorState(
        provenance_by_sensor={sensor_id: provenance},
        findings=tuple(sorted(findings, key=lambda item: item.canonical_id)),
    )


def _finding(
    sensor_id: str,
    *,
    severity: str,
    message: str,
    source_span: SourceSpan | None = None,
) -> LLMSecurityFinding:
    return project_to_canonical(
        RawLLMFinding(
            finding_class="missing-authz",
            module_path="src/app.py",
            qualified_name="src.app.handler",
            anchor_kind="absence",
            expected_property="requires authorization guard",
            ordinal=0,
            severity=severity,  # type: ignore[arg-type]
            message=message,
            source_span=source_span,
        ),
        sensor_id=sensor_id,
    )
