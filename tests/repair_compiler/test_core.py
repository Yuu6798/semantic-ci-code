from __future__ import annotations

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan
from semantic_ci_code.repair_compiler import RepairCompiler
from semantic_ci_code.repair_compiler.types import Adapter

from .utils import sample_repair_plan


class MockAdapter:
    name = "mock"
    output_format = "text"
    schema_version = "1"

    def render_repair(self, plan: RepairPlan, target):
        assert plan.instructions
        return "repair output"

    def render_pre_gen(self, target, baseline_state: CodeState):
        assert target.intent == "Add profile endpoint"
        assert baseline_state == CodeState()
        return "pre-gen output\n"


def test_repair_compiler_dispatches_repair_and_builds_metadata():
    adapter: Adapter = MockAdapter()
    target = sample_target()
    compiled = RepairCompiler(adapter).render_repair(sample_repair_plan(), target=target)

    assert compiled.adapter_name == "mock"
    assert compiled.output_format == "text"
    assert compiled.rendered == "repair output\n"
    assert compiled.metadata["schema_version"] == "1"
    assert compiled.metadata["adapter_name"] == "mock"
    assert compiled.metadata["adapter_version"] == "1"
    assert compiled.metadata["intent"] == "Add profile endpoint"
    assert compiled.metadata["primary_kind"] == "feature"
    assert compiled.metadata["constraint_count"] == 4
    assert compiled.metadata["render_timestamp"] is None
    assert compiled.metadata["input_kind"] == "raw_repair_plan"
    assert hash(compiled)


def test_repair_compiler_allows_target_none_for_repair_metadata():
    compiled = RepairCompiler(MockAdapter()).render_repair(sample_repair_plan(), target=None)

    assert compiled.metadata["intent"] == ""
    assert compiled.metadata["primary_kind"] == ""
    assert compiled.rendered.endswith("\n")


def test_repair_compiler_dispatches_pre_gen_with_placeholder_risk_summary():
    target = sample_target()
    compiled = RepairCompiler(MockAdapter()).render_pre_gen(target, CodeState())

    assert compiled.rendered == "pre-gen output\n"
    assert compiled.metadata["intent"] == "Add profile endpoint"
    assert compiled.metadata["primary_kind"] == "feature"
    assert compiled.metadata["constraint_count"] == 0
    assert compiled.metadata["input_kind"] == "target_svp"
    assert compiled.risk_summary == {
        "would_violate": [],
        "forbidden_zones": [],
        "required_additions": [],
        "template_implications": [],
    }
    assert hash(compiled)


def sample_target():
    return parse_target_svp_yaml(
        """
intent: Add profile endpoint
change:
  primary_kind: feature
  allowed_secondary_kinds: [test_update]
"""
    )
