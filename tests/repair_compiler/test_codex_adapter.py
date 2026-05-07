from __future__ import annotations

from pathlib import Path

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.evaluator import VerdictResult
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan
from semantic_ci_code.repair_compiler import RepairCompiler
from semantic_ci_code.repair_compiler.adapters import CodexAdapter

from .utils import sample_repair_plan

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_codex_repair_matches_golden_mixed_plan():
    compiled = RepairCompiler(CodexAdapter()).render_repair(
        sample_repair_plan(),
        target=sample_target(),
    )

    assert compiled.rendered == (FIXTURES / "codex_repair_mixed.txt").read_text(encoding="utf-8")


def test_codex_repair_empty_categories_use_none_marker():
    compiled = RepairCompiler(CodexAdapter()).render_repair(
        RepairPlan(result=VerdictResult.PASS, instructions=()),
        target=None,
    )

    assert compiled.rendered == (FIXTURES / "codex_repair_empty.txt").read_text(encoding="utf-8")


def test_codex_pre_gen_matches_golden():
    compiled = RepairCompiler(CodexAdapter()).render_pre_gen(sample_target(), CodeState())

    assert compiled.rendered == (FIXTURES / "codex_pre_gen_feature.txt").read_text(encoding="utf-8")


def test_codex_section_labels_are_fixed_and_ordered():
    rendered = (
        RepairCompiler(CodexAdapter())
        .render_repair(
            sample_repair_plan(),
            target=sample_target(),
        )
        .rendered
    )

    labels = [
        "[INTENT]",
        "[CURRENT VERDICT]",
        "[FIX REQUIRED]",
        "[SUGGESTED]",
        "[INFO]",
        "[UNRESOLVED]",
        "[HINTS]",
    ]
    assert [rendered.index(label) for label in labels] == sorted(
        rendered.index(label) for label in labels
    )


def test_codex_adapter_renders_kind_severity_target_and_operator_verbatim():
    rendered = (
        RepairCompiler(CodexAdapter())
        .render_repair(
            sample_repair_plan(),
            target=sample_target(),
        )
        .rendered
    )

    assert "kind: delta" in rendered
    assert "severity: soft" in rendered
    assert "target: api_surface_public" in rendered
    assert "operator: equals" in rendered


def test_codex_pre_gen_renders_target_constraints():
    rendered = (
        RepairCompiler(CodexAdapter()).render_pre_gen(constrained_target(), CodeState()).rendered
    )

    assert "[TARGET CONSTRAINTS]" in rendered
    assert "1. require_public_api" in rendered
    assert "kind: delta" in rendered
    assert "target: api_surface_public" in rendered
    assert "operator: includes_all" in rendered
    assert 'expected: ["pkg.new_api"]' in rendered
    assert "severity: soft" in rendered
    assert "unknown_policy: repair" in rendered


def test_codex_output_is_ascii_safe_for_unicode_metadata():
    rendered = (
        RepairCompiler(CodexAdapter())
        .render_pre_gen(unicode_metadata_target(), CodeState())
        .rendered
    )

    assert rendered.isascii()
    assert r"\u30c4\u30fc\u30eb" in rendered


def test_codex_rendering_is_same_process_deterministic():
    compiler = RepairCompiler(CodexAdapter())

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


def constrained_target():
    return parse_target_svp_yaml(
        """
intent: Add profile endpoint
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
    )


def unicode_metadata_target():
    return parse_target_svp_yaml(
        """
intent: metadata transfer
change:
  primary_kind: feature
authorship:
  authors:
    - identity: codex
  generation_metadata:
    tool: ツール
"""
    )
