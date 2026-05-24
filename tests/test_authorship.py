from __future__ import annotations

from semantic_ci_code.cli.output.json_formatter import build_compile_payload, build_payload
from semantic_ci_code.compiler import compile_target_svp
from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta
from semantic_ci_code.evaluator import Verdict, VerdictResult, evaluate_constraints
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan, emit_repair_plan

AUTHORSHIP_YAML = """
intent: authorship anchor
change:
  primary_kind: feature
authorship:
  authors:
    - identity: alice@example.com
      signature: sig-1
    - identity: bot:semantic-ci
  declared_at: "2026-05-05T12:00:00Z"
  generation_metadata:
    tool: codex
    model: gpt-test
"""


def test_target_svp_accepts_optional_authorship_metadata():
    target_svp = parse_target_svp_yaml(AUTHORSHIP_YAML)

    assert target_svp.authorship is not None
    assert target_svp.authorship.authors[0].identity == "alice@example.com"
    assert target_svp.authorship.authors[0].signature == "sig-1"
    assert target_svp.authorship.authors[1].identity == "bot:semantic-ci"
    assert target_svp.authorship.declared_at == "2026-05-05T12:00:00Z"
    assert target_svp.authorship.generation_metadata == {
        "tool": "codex",
        "model": "gpt-test",
    }


def test_compile_payload_includes_compiled_target_authorship():
    compiled = compile_target_svp(AUTHORSHIP_YAML)
    payload = build_compile_payload(compiled)

    assert payload["schema_version"] == "6"
    assert payload["compiled_target"]["authorship"] == {
        "authors": [
            {"identity": "alice@example.com", "signature": "sig-1"},
            {"identity": "bot:semantic-ci", "signature": None},
        ],
        "declared_at": "2026-05-05T12:00:00Z",
        "generation_metadata": {"tool": "codex", "model": "gpt-test"},
    }


def test_verdict_payload_carries_target_authorship_or_null():
    compiled = compile_target_svp(AUTHORSHIP_YAML)
    verdict = Verdict(result=VerdictResult.PASS, results=())
    plan = RepairPlan(result=VerdictResult.PASS, instructions=())

    authored = build_payload("compare", compiled=compiled, verdict=verdict, repair_plan=plan)
    unauthored = build_payload(
        "compare",
        compiled=compile_target_svp("intent: no authorship\nchange:\n  primary_kind: feature\n"),
        verdict=verdict,
        repair_plan=plan,
    )

    assert authored["schema_version"] == "6"
    assert authored["target_authorship"]["authors"][0]["identity"] == "alice@example.com"
    assert unauthored["target_authorship"] is None


def test_authorship_value_changes_do_not_affect_verdict_repair_plan_or_summary():
    target_a = """
intent: authorship invariant
change:
  primary_kind: feature
authorship:
  authors:
    - identity: alice@example.com
      signature: sig-a
  declared_at: "2026-05-05T12:00:00Z"
  generation_metadata:
    tool: codex
constraints:
  - id: soft_files_touched
    kind: delta
    target: files_touched
    operator: equals
    expected: 99
    severity: soft
    unknown_policy: fail
"""
    target_b = """
intent: authorship invariant
change:
  primary_kind: feature
authorship:
  authors:
    - identity: bob@example.com
      signature: sig-b
  declared_at: "2026-05-06T12:00:00Z"
  generation_metadata:
    tool: claude
constraints:
  - id: soft_files_touched
    kind: delta
    target: files_touched
    operator: equals
    expected: 99
    severity: soft
    unknown_policy: fail
"""

    payload_a = _evaluate_payload(target_a)
    payload_b = _evaluate_payload(target_b)

    assert payload_a["target_authorship"] != payload_b["target_authorship"]
    assert payload_a["verdict"] == payload_b["verdict"]
    assert payload_a["repair_plan"] == payload_b["repair_plan"]
    assert payload_a["summary"] == payload_b["summary"]


def _evaluate_payload(yaml_source: str):
    compiled = compile_target_svp(yaml_source)
    verdict = evaluate_constraints(
        compiled,
        CodeStateDelta(files_touched=0),
        baseline=CodeState(),
        candidate=CodeState(),
    )
    plan = emit_repair_plan(verdict)
    return build_payload("compare", compiled=compiled, verdict=verdict, repair_plan=plan)
