from __future__ import annotations

from semantic_ci_code.cli.output.json_formatter import build_compile_payload, build_payload
from semantic_ci_code.compiler import compile_target_svp
from semantic_ci_code.evaluator import Verdict, VerdictResult
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import RepairPlan

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

    assert payload["schema_version"] == "4"
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

    assert authored["schema_version"] == "4"
    assert authored["target_authorship"]["authors"][0]["identity"] == "alice@example.com"
    assert unauthored["target_authorship"] is None
