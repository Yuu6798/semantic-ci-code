from __future__ import annotations

import os
import subprocess
import sys


def test_render_repair_is_byte_identical_across_hash_seeds():
    outputs = tuple(_run_subprocess(seed) for seed in ("0", "1", "random"))

    assert outputs[0] == outputs[1] == outputs[2]


def _run_subprocess(hash_seed: str) -> str:
    script = r"""
from semantic_ci_code.compiler import ConstraintSource
from semantic_ci_code.evaluator import ConstraintResult, ResultStatus, Verdict, VerdictResult
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)
from semantic_ci_code.framework.target_svp import parse_target_svp_yaml
from semantic_ci_code.repair import emit_repair_plan
from semantic_ci_code.repair_compiler import RepairCompiler
from semantic_ci_code.repair_compiler.adapters import ClaudeCodeAdapter

result = ConstraintResult(
    constraint_id="deterministic",
    source=ConstraintSource.USER,
    kind=ConstraintKind.DELTA,
    target="api_surface_public",
    operator=Operator.EQUALS,
    severity=Severity.SOFT,
    unknown_policy=UnknownPolicy.FAIL,
    tolerance=None,
    evidence_required=False,
    status=ResultStatus.VIOLATED,
    error_code="E_VIOLATION",
    evidence=(("observed", ("a",)), ("expected", ())),
)
target = parse_target_svp_yaml("intent: deterministic\nchange:\n  primary_kind: feature\n")
plan = emit_repair_plan(Verdict(result=VerdictResult.REPAIR, results=(result,)))
compiled = RepairCompiler(ClaudeCodeAdapter()).render_repair(plan, target=target)
print(compiled.rendered, end="")
"""
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = "src"
    result = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        check=True,
        env=env,
    )
    return result.stdout
