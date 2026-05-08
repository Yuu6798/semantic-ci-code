from __future__ import annotations

from semantic_ci_code.repair_compiler.adapters.markdown import render_risk_section_structured


def test_structured_risk_section_keeps_empty_none_marker():
    assert render_risk_section_structured("Forbidden Zones", []) == [
        "## Forbidden Zones",
        "(none)",
        "",
    ]


def test_structured_risk_section_scalar_fallback_is_single_bullet():
    assert render_risk_section_structured("Risk Areas", ["require_missing_api"]) == [
        "## Risk Areas",
        "- require_missing_api",
        "",
    ]


def test_structured_risk_section_renders_extras_alphabetically():
    rendered = render_risk_section_structured(
        "Forbidden Zones",
        [
            {
                "constraint_id": "lock_api_surface",
                "source": "user",
                "target": "api_surface",
                "operator": "equals_baseline",
                "zeta_extra": "last",
                "alpha_extra": "first",
            }
        ],
    )

    assert rendered == [
        "## Forbidden Zones",
        "1. `lock_api_surface`",
        "   - Source: `user`",
        "   - Target: `api_surface`",
        "   - Operator: `equals_baseline`",
        '   - alpha_extra: "first"',
        '   - zeta_extra: "last"',
        "",
    ]
