from __future__ import annotations

import pytest

from semantic_ci_code.sensor.adapters.llm import RawLLMFinding, project_to_canonical


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
