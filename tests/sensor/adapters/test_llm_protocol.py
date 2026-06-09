from __future__ import annotations

import pytest

from semantic_ci_code.sensor.adapters.llm import (
    LLMSensorProvenance,
    RawLLMFinding,
    project_to_canonical,
)


def test_raw_llm_finding_normalizes_module_path_before_projection():
    raw = RawLLMFinding(
        finding_class="ssrf",
        module_path="src\\fetcher.py",
        qualified_name="src.fetcher.load_url",
        anchor_kind="presence",
        ordinal=0,
        severity="medium",
    )

    finding = project_to_canonical(raw, sensor_id="llm-scout")

    assert raw.module_path == "src/fetcher.py"
    assert finding.module_path == "src/fetcher.py"
    assert finding.identity_components[4] == "src/fetcher.py"


@pytest.mark.parametrize(
    ("anchor_kind", "expected_property", "match"),
    [
        ("absence", "", "absence LLM findings require expected_property"),
        (
            "presence",
            "authorization check",
            "presence LLM findings must not include expected_property",
        ),
    ],
)
def test_raw_llm_finding_validates_anchor_shape(
    anchor_kind: str,
    expected_property: str,
    match: str,
):
    with pytest.raises(ValueError, match=match):
        RawLLMFinding(
            finding_class="missing-authz",
            module_path="src/app.py",
            qualified_name="src.app.handler",
            anchor_kind=anchor_kind,
            expected_property=expected_property,
            ordinal=0,
            severity="high",
        )


def test_llm_sensor_provenance_is_always_non_reproducible():
    provenance = LLMSensorProvenance(
        sensor_id="llm-scout",
        sensor_version="model-x",
        adapter_version="llm-adapter-1",
        model_id="model-x",
        prompt_hash="sha256:prompt",
    )

    assert provenance.non_reproducible is True


def test_llm_sensor_provenance_rejects_reproducible_value():
    with pytest.raises(ValueError):
        LLMSensorProvenance(
            sensor_id="llm-scout",
            sensor_version="model-x",
            adapter_version="llm-adapter-1",
            model_id="model-x",
            prompt_hash="sha256:prompt",
            non_reproducible=False,
        )


@pytest.mark.parametrize(
    "missing_field",
    [
        "model_id",
        "prompt_hash",
    ],
)
def test_llm_sensor_provenance_requires_audit_fields(missing_field: str):
    payload = {
        "sensor_id": "llm-scout",
        "sensor_version": "model-x",
        "adapter_version": "llm-adapter-1",
        "model_id": "model-x",
        "prompt_hash": "sha256:prompt",
    }
    del payload[missing_field]

    with pytest.raises(ValueError):
        LLMSensorProvenance(**payload)
