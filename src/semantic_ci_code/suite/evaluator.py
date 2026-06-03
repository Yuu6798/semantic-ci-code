"""Suite-level verdict aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from semantic_ci_code.evaluator.evaluator import VerdictResult
from semantic_ci_code.sensor.models import SecurityDeltaStatus


class SuiteResult(StrEnum):
    PASS = "pass"
    REPAIR = "repair"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SuiteVerdict:
    code: VerdictResult
    security: SecurityDeltaStatus
    final: SuiteResult


_RANK: dict[SuiteResult, int] = {
    SuiteResult.PASS: 0,
    SuiteResult.REPAIR: 1,
    SuiteResult.FAIL: 2,
    SuiteResult.UNKNOWN: 3,
}


def combine_verdict(
    code_result: VerdictResult,
    security_result: SecurityDeltaStatus,
) -> SuiteVerdict:
    """Combine code and security verdicts with unknown > fail > repair > pass."""

    candidates = (_suite_from_code(code_result), _suite_from_security(security_result))
    final = max(candidates, key=lambda item: _RANK[item])
    return SuiteVerdict(code=code_result, security=security_result, final=final)


def _suite_from_code(result: VerdictResult) -> SuiteResult:
    return SuiteResult(result.value)


def _suite_from_security(result: SecurityDeltaStatus) -> SuiteResult:
    return SuiteResult(result)
