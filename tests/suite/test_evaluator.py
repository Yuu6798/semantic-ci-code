from __future__ import annotations

import pytest

from semantic_ci_code.evaluator.evaluator import VerdictResult
from semantic_ci_code.suite.evaluator import SuiteResult, combine_verdict


@pytest.mark.parametrize(
    ("code", "security", "expected"),
    [
        (VerdictResult.PASS, "pass", SuiteResult.PASS),
        (VerdictResult.REPAIR, "pass", SuiteResult.REPAIR),
        (VerdictResult.FAIL, "pass", SuiteResult.FAIL),
        (VerdictResult.PASS, "fail", SuiteResult.FAIL),
        (VerdictResult.REPAIR, "fail", SuiteResult.FAIL),
        (VerdictResult.FAIL, "fail", SuiteResult.FAIL),
        (VerdictResult.PASS, "unknown", SuiteResult.UNKNOWN),
        (VerdictResult.REPAIR, "unknown", SuiteResult.UNKNOWN),
        (VerdictResult.FAIL, "unknown", SuiteResult.UNKNOWN),
    ],
)
def test_combine_verdict_precedence_table(code, security, expected):
    verdict = combine_verdict(code, security)

    assert verdict.code is code
    assert verdict.security == security
    assert verdict.final is expected
