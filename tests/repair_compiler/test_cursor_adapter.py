from __future__ import annotations

from pathlib import Path

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.evaluator import VerdictResult
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan
from semantic_ci_code.repair_compiler import RepairCompiler
from semantic_ci_code.repair_compiler.adapters import CursorAdapter

from .utils import pre_gen_risk_summary, pre_gen_risk_target, sample_repair_plan

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_cursor_repair_matches_golden_mixed_plan():
    compiled = RepairCompiler(CursorAdapter()).render_repair(
        sample_repair_plan(),
        target=sample_target(),
    )

    assert compiled.rendered == (FIXTURES / "cursor_repair_mixed.mdc").read_text(encoding="utf-8")


def test_cursor_repair_empty_categories_use_none_marker():
    compiled = RepairCompiler(CursorAdapter()).render_repair(
        RepairPlan(result=VerdictResult.PASS, instructions=()),
        target=None,
    )

    assert compiled.rendered == (FIXTURES / "cursor_repair_empty.mdc").read_text(encoding="utf-8")


def test_cursor_pre_gen_matches_golden():
    compiled = RepairCompiler(CursorAdapter()).render_pre_gen(sample_target(), CodeState())

    assert compiled.rendered == (FIXTURES / "cursor_pre_gen_feature.mdc").read_text(
        encoding="utf-8"
    )


def test_cursor_pre_gen_renders_computed_risk_summary():
    compiled = RepairCompiler(CursorAdapter()).render_pre_gen(
        pre_gen_risk_target(),
        CodeState(),
        risk_summary=pre_gen_risk_summary(),
    )

    assert compiled.rendered == (FIXTURES / "cursor_pre_gen_with_risk.mdc").read_text(
        encoding="utf-8"
    )
    assert compiled.risk_summary == pre_gen_risk_summary()


def test_cursor_adapter_renders_kind_severity_target_and_operator_verbatim():
    rendered = (
        RepairCompiler(CursorAdapter())
        .render_repair(
            sample_repair_plan(),
            target=sample_target(),
        )
        .rendered
    )

    assert "Kind: `delta`" in rendered
    assert "Severity: `soft`" in rendered
    assert "Target: `api_surface_public`" in rendered
    assert "Operator: `equals`" in rendered


def test_cursor_frontmatter_uses_default_python_glob_when_scope_files_empty():
    rendered = (
        RepairCompiler(CursorAdapter()).render_repair(sample_repair_plan(), target=None).rendered
    )

    assert '  - "**/*.py"' in rendered
    assert "alwaysApply: false" in rendered


def test_cursor_frontmatter_uses_scope_files_in_input_order():
    rendered = RepairCompiler(CursorAdapter()).render_pre_gen(scoped_target(), CodeState()).rendered

    assert '  - "src/**/*.py"\n  - "tests/**/*.py"' in rendered
    assert "alwaysApply: true" in rendered


def test_cursor_frontmatter_escapes_double_quoted_globs():
    rendered = (
        RepairCompiler(CursorAdapter()).render_pre_gen(quoted_scope_target(), CodeState()).rendered
    )

    assert 'description: "Semantic CI plan validation guidance"' in rendered
    assert '  - "src/\\"quoted\\"/**/*.py"' in rendered


def test_cursor_pre_gen_renders_target_constraints():
    rendered = RepairCompiler(CursorAdapter()).render_pre_gen(scoped_target(), CodeState()).rendered

    assert "## Target Constraints" in rendered
    assert "1. `require_public_api`" in rendered
    assert "Kind: `delta`" in rendered
    assert "Target: `api_surface_public`" in rendered
    assert "Operator: `includes_all`" in rendered
    assert 'Expected: ["pkg.new_api"]' in rendered
    assert "Severity: `soft`" in rendered
    assert "Unknown policy: `repair`" in rendered


def test_cursor_rendering_is_same_process_deterministic():
    compiler = RepairCompiler(CursorAdapter())

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


def scoped_target():
    return parse_target_svp_yaml(
        """
intent: Add profile endpoint
change:
  primary_kind: feature
  allowed_secondary_kinds: [test_update]
  scope:
    files:
      - src/**/*.py
      - tests/**/*.py
authorship:
  authors:
    - identity: codex
  generation_metadata:
    tool: cursor
constraints:
  - id: require_public_api
    kind: delta
    target: api_surface_public
    operator: includes_all
    expected: ["pkg.new_api"]
    severity: soft
    unknown_policy: repair
"""
    )


def quoted_scope_target():
    return parse_target_svp_yaml(
        """
intent: Add profile endpoint
change:
  primary_kind: feature
  scope:
    files:
      - src/"quoted"/**/*.py
"""
    )
