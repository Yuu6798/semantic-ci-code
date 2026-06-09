from __future__ import annotations

import pytest

from semantic_ci_code.sensor.adapters.llm import RawLLMFinding, project_to_canonical
from semantic_ci_code.sensor.models import (
    LLMSecurityFinding,
    SensorProvenance,
    SensorState,
    SourceSpan,
    canonical_id_for_identity,
)

from .helpers import llm_components, provenance


def test_llm_security_finding_identity_and_canonical_id_match():
    components = llm_components(
        "missing-authz",
        module_path="src/views.py",
        qualified_name="src.views.account",
        anchor_kind="absence",
        expected_property="requires auth guard",
    )
    finding = LLMSecurityFinding(
        category="llm",
        sensor_id="llm-scout",
        canonical_id=canonical_id_for_identity(components),
        identity_components=components,
        severity="critical",
        finding_class="missing-authz",
        module_path="src/views.py",
        qualified_name="src.views.account",
        anchor_kind="absence",
        expected_property="requires auth guard",
        ordinal=0,
        message="auth guard may be missing",
    )

    assert finding.module_path == "src/views.py"
    assert finding.identity_components == (
        "v1",
        "llm",
        "llm-scout",
        "missing-authz",
        "src/views.py",
        "src.views.account",
        "absence",
        "requires auth guard",
        "0",
    )
    assert finding.canonical_id == canonical_id_for_identity(finding.identity_components)


def test_llm_security_finding_rejects_identity_tampering():
    components = llm_components(expected_property="requires auth guard")

    with pytest.raises(ValueError, match="canonical_id does not match"):
        LLMSecurityFinding(
            category="llm",
            sensor_id="llm-scout",
            canonical_id=canonical_id_for_identity(components[:-1] + ("1",)),
            identity_components=components,
            severity="critical",
            finding_class="missing-authz",
            module_path="src/app.py",
            qualified_name="src.app.handler",
            anchor_kind="absence",
            expected_property="requires auth guard",
            ordinal=0,
        )


@pytest.mark.parametrize(
    "payload,match",
    [
        (
            {"anchor_kind": "absence", "expected_property": ""},
            "absence LLM findings require expected_property",
        ),
        (
            {"anchor_kind": "presence", "expected_property": "requires auth guard"},
            "presence LLM findings must not include expected_property",
        ),
    ],
)
def test_llm_security_finding_validates_anchor_shape(payload: dict[str, str], match: str):
    components = llm_components(
        anchor_kind=payload["anchor_kind"],
        expected_property=payload["expected_property"],
    )

    with pytest.raises(ValueError, match=match):
        LLMSecurityFinding(
            category="llm",
            sensor_id="llm-scout",
            canonical_id=canonical_id_for_identity(components),
            identity_components=components,
            severity="medium",
            finding_class="missing-authz",
            module_path="src/app.py",
            qualified_name="src.app.handler",
            anchor_kind=payload["anchor_kind"],
            expected_property=payload["expected_property"],
            ordinal=0,
        )


def test_project_to_canonical_is_deterministic_and_freezes_advisory_state():
    raw = RawLLMFinding(
        finding_class="idor",
        module_path="src\\billing.py",
        qualified_name="src.billing.account_dashboard",
        anchor_kind="absence",
        expected_property="authorization check",
        ordinal=2,
        severity="high",
        message="missing object-level authorization",
        source_span=SourceSpan(start_line=10, start_col=0, end_line=12, end_col=8),
    )

    first = project_to_canonical(raw, sensor_id="llm-scout")
    second = project_to_canonical(raw, sensor_id="llm-scout")

    assert first == second
    assert first.model_dump_json() == second.model_dump_json()
    assert first.module_path == "src/billing.py"
    state = SensorState(
        provenance_by_sensor={
            "llm-scout": SensorProvenance(
                sensor_id="llm-scout",
                adapter_version="llm-adapter-1",
                model_id="model-x",
                prompt_hash="sha256:prompt",
                non_reproducible=True,
                status="complete",
            )
        },
        findings=(first,),
    )

    assert state.findings == (first,)


def test_sensor_provenance_new_fields_have_defaults_for_deterministic_sensors():
    deterministic = provenance()

    assert deterministic.model_id is None
    assert deterministic.prompt_hash is None
    assert deterministic.non_reproducible is False
