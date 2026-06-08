from __future__ import annotations

import pytest

from semantic_ci_code.compiler import compile_target_svp
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.domain.state_schema import APISurfaceEntry, CodeState
from semantic_ci_code.evaluator import VerdictResult, evaluate_constraints

AUTH_GUARD_TARGET = """
intent: preserve auth guard decorators
change:
  primary_kind: generic
constraints:
  - id: no_removed_auth_guard
    kind: delta
    target: decorators_delta.removed
    operator: excludes_all
    expected:
      - decorator_leaf: login_required
    severity: hard
    unknown_policy: fail
"""


def _state_with_decorators(*decorators: str) -> CodeState:
    return CodeState(
        api_surface=(
            APISurfaceEntry(
                fqn="pkg.views.account",
                kind="function",
                signature="def account():\n    ...",
                visibility="public",
                decorators=decorators,
            ),
        )
    )


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (_state_with_decorators(), VerdictResult.FAIL),
        (_state_with_decorators("auth.login_required"), VerdictResult.PASS),
    ],
)
def test_auth_guard_decorator_delta_engine_contract(candidate: CodeState, expected: VerdictResult):
    """§23.1 mirror: hand-built CodeState is enough to evaluate this facet."""

    compiled = compile_target_svp(AUTH_GUARD_TARGET)
    baseline = _state_with_decorators("auth.login_required")
    delta = compute_code_state_delta(baseline, candidate)

    verdict = evaluate_constraints(compiled, delta, baseline=baseline, candidate=candidate)

    assert verdict.result is expected
