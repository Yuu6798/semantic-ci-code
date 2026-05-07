from __future__ import annotations

from pathlib import Path

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan
from semantic_ci_code.repair_compiler import RepairCompiler
from semantic_ci_code.repair_compiler.adapters import ClaudeCodeAdapter

from .utils import sample_repair_plan

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


def test_claude_code_pre_gen_matches_golden_and_placeholder_risk_summary():
    compiled = RepairCompiler(ClaudeCodeAdapter()).render_pre_gen(sample_target(), CodeState())

    assert compiled.rendered == (FIXTURES / "pre_gen_feature.md").read_text(encoding="utf-8")
    assert compiled.risk_summary == {
        "would_violate": [],
        "forbidden_zones": [],
        "required_additions": [],
        "template_implications": [],
    }


def test_claude_code_rendering_is_same_process_deterministic():
    compiler = RepairCompiler(ClaudeCodeAdapter())

    first = compiler.render_repair(sample_repair_plan(), target=sample_target())
    second = compiler.render_repair(sample_repair_plan(), target=sample_target())

    assert first == second
    assert first.rendered == second.rendered
    assert first.rendered.endswith("\n")


def sample_target():
    return parse_target_svp_yaml(
        """
intent: Add profile endpoint
change:
  primary_kind: feature
  allowed_secondary_kinds: [test_update]
"""
    )
