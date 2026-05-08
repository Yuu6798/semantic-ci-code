from __future__ import annotations

from pathlib import Path

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan
from semantic_ci_code.repair_compiler import RepairCompiler
from semantic_ci_code.repair_compiler.adapters import ClaudeCodeAdapter

from .utils import pre_gen_risk_summary, pre_gen_risk_target, sample_repair_plan

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_claude_code_repair_matches_golden_mixed_plan():
    compiled = RepairCompiler(ClaudeCodeAdapter()).render_repair(
        sample_repair_plan(),
        target=sample_target(),
    )

    assert compiled.rendered == (FIXTURES / "repair_mixed.md").read_text(encoding="utf-8")


def test_claude_code_repair_empty_categories_use_none_marker():
    compiled = RepairCompiler(ClaudeCodeAdapter()).render_repair(
        RepairPlan(result=sample_repair_plan().result.PASS, instructions=()),
        target=None,
    )

    assert compiled.rendered == (FIXTURES / "repair_empty.md").read_text(encoding="utf-8")
    assert compiled.rendered.count("(none)") == 4


def test_claude_code_adapter_renders_severity_and_target_verbatim():
    rendered = (
        RepairCompiler(ClaudeCodeAdapter())
        .render_repair(
            sample_repair_plan(),
            target=sample_target(),
        )
        .rendered
    )

    assert "Severity: `soft`" in rendered
    assert "Kind: `delta`" in rendered
    assert "Target: `api_surface_public`" in rendered
    assert "Operator: `equals`" in rendered


def test_claude_code_pre_gen_matches_golden_and_placeholder_risk_summary():
    compiled = RepairCompiler(ClaudeCodeAdapter()).render_pre_gen(sample_target(), CodeState())

    assert compiled.rendered == (FIXTURES / "pre_gen_feature.md").read_text(encoding="utf-8")
    assert compiled.risk_summary == {
        "would_violate": [],
        "forbidden_zones": [],
        "required_additions": [],
        "template_implications": [],
    }


def test_claude_code_pre_gen_renders_computed_risk_summary():
    compiled = RepairCompiler(ClaudeCodeAdapter()).render_pre_gen(
        pre_gen_risk_target(),
        CodeState(),
        risk_summary=pre_gen_risk_summary(),
    )

    assert compiled.rendered == (FIXTURES / "claude_code_pre_gen_with_risk.md").read_text(
        encoding="utf-8"
    )
    assert compiled.risk_summary == pre_gen_risk_summary()


def test_pre_gen_renders_forbidden_zones_as_multiline_blocks():
    rendered = _render_pre_gen_with_risk(pre_gen_risk_summary())

    assert "## Forbidden Zones" in rendered
    assert "1. `lock_api_surface`" in rendered
    assert "   - Source: `user`" in rendered
    assert "   - Target: `api_surface`" in rendered
    assert "   - Operator: `equals_baseline`" in rendered


def test_pre_gen_renders_required_additions_includes_all_with_expected():
    rendered = _render_pre_gen_with_risk(
        {
            **pre_gen_risk_summary(),
            "required_additions": [
                {
                    "constraint_id": "require_profile_api",
                    "source": "user",
                    "target": "api_surface_delta.added",
                    "operator": "includes_all",
                    "expected": {"kind": "function", "fqn": "pkg.profile"},
                }
            ],
        }
    )

    assert "1. `require_profile_api`" in rendered
    assert "   - Operator: `includes_all`" in rendered
    assert '   - Expected: {"fqn": "pkg.profile", "kind": "function"}' in rendered


def test_pre_gen_renders_required_additions_includes_any_with_any_of():
    rendered = _render_pre_gen_with_risk(
        {
            **pre_gen_risk_summary(),
            "required_additions": [
                {
                    "constraint_id": "require_one_profile_api",
                    "source": "user",
                    "target": "api_surface_delta.added",
                    "operator": "includes_any",
                    "expected_any_of": ["pkg.profile", {"fqn": "pkg.profile_v2"}],
                }
            ],
        }
    )

    assert "1. `require_one_profile_api`" in rendered
    assert "   - Any of:" in rendered
    assert '     - "pkg.profile"' in rendered
    assert '     - {"fqn": "pkg.profile_v2"}' in rendered


def test_pre_gen_renders_would_violate_as_scalar_bullet():
    rendered = _render_pre_gen_with_risk(pre_gen_risk_summary())

    assert "## Risk Areas\n- require_missing_api" in rendered
    assert '- "require_missing_api"' not in rendered


def test_pre_gen_renders_template_implications_as_scalar_bullet():
    rendered = _render_pre_gen_with_risk(pre_gen_risk_summary())

    assert "## Template Implications\n- template:refactor:api_surface_unchanged" in rendered
    assert '- "template:refactor:api_surface_unchanged"' not in rendered


def test_pre_gen_empty_risk_section_renders_none_marker():
    rendered = (
        RepairCompiler(ClaudeCodeAdapter()).render_pre_gen(sample_target(), CodeState()).rendered
    )

    assert "## Risk Areas\n(none)" in rendered
    assert "## Forbidden Zones\n(none)" in rendered
    assert "## Required Additions\n(none)" in rendered
    assert "## Template Implications\n(none)" in rendered


def test_pre_gen_unknown_extra_key_falls_back_to_alphabetical_extras():
    rendered = _render_pre_gen_with_risk(
        {
            **pre_gen_risk_summary(),
            "forbidden_zones": [
                {
                    "constraint_id": "lock_api_surface",
                    "source": "user",
                    "target": "api_surface",
                    "operator": "equals_baseline",
                    "zeta_extra": "last",
                    "alpha_extra": "first",
                }
            ],
        }
    )

    assert rendered.index('   - alpha_extra: "first"') < rendered.index('   - zeta_extra: "last"')


def test_claude_code_adapter_accepts_explicit_risk_summary_without_compiler_context():
    rendered = ClaudeCodeAdapter().render_pre_gen(
        pre_gen_risk_target(),
        CodeState(),
        risk_summary=pre_gen_risk_summary(),
    )

    assert "- require_missing_api" in rendered


def test_claude_code_pre_gen_renders_generation_metadata_when_present():
    rendered = (
        RepairCompiler(ClaudeCodeAdapter())
        .render_pre_gen(
            parse_target_svp_yaml(
                """
intent: metadata transfer
change:
  primary_kind: feature
authorship:
  authors:
    - identity: codex
  generation_metadata:
    tool: claude-code
    model: test-model
"""
            ),
            CodeState(),
        )
        .rendered
    )

    assert '**Generation metadata**: {"model": "test-model", "tool": "claude-code"}' in rendered


def test_claude_code_pre_gen_renders_target_constraints_verbatim():
    rendered = (
        RepairCompiler(ClaudeCodeAdapter())
        .render_pre_gen(
            parse_target_svp_yaml(
                """
intent: constraint transfer
change:
  primary_kind: feature
constraints:
  - id: require_public_api
    kind: delta
    target: api_surface_public
    operator: includes_all
    expected: ["pkg.new_api"]
    severity: soft
    unknown_policy: repair
"""
            ),
            CodeState(),
        )
        .rendered
    )

    assert "## Target Constraints" in rendered
    assert "1. `require_public_api`" in rendered
    assert "Kind: `delta`" in rendered
    assert "Target: `api_surface_public`" in rendered
    assert "Operator: `includes_all`" in rendered
    assert 'Expected: ["pkg.new_api"]' in rendered
    assert "Severity: `soft`" in rendered
    assert "Unknown policy: `repair`" in rendered


def test_claude_code_rendering_is_same_process_deterministic():
    compiler = RepairCompiler(ClaudeCodeAdapter())

    first = compiler.render_repair(sample_repair_plan(), target=sample_target())
    second = compiler.render_repair(sample_repair_plan(), target=sample_target())

    assert first == second
    assert first.rendered == second.rendered
    assert first.rendered.endswith("\n")


def _render_pre_gen_with_risk(risk_summary):
    return (
        RepairCompiler(ClaudeCodeAdapter())
        .render_pre_gen(
            pre_gen_risk_target(),
            CodeState(),
            risk_summary=risk_summary,
        )
        .rendered
    )


def sample_target():
    return parse_target_svp_yaml(
        """
intent: Add profile endpoint
change:
  primary_kind: feature
  allowed_secondary_kinds: [test_update]
"""
    )
