"""Stable repair-code mapping for CSCI-14 repair plan emission.

Repair codes are intentionally separate from evaluator error codes. Template
constraints get specific ``R_*`` codes so Brief 4 CLI rendering and future
automation can route them without parsing human messages. User constraints and
unknown future evaluator errors fall back to generic codes.

This module hard-codes CSCI-12 template ids as string literals by design. If
``compiler/templates.py`` changes template ids, this static map must be updated
in the same change.
"""

from __future__ import annotations

from typing import Final

from semantic_ci_code.evaluator import ConstraintResult

__all__ = ["REPAIR_CODES", "resolve_repair_code"]

R_API_REMOVED: Final = "R_API_REMOVED"
R_API_CHANGED: Final = "R_API_CHANGED"
R_TYPE_RELATIONS_CHANGED: Final = "R_TYPE_RELATIONS_CHANGED"
R_EFFECTS_CHANGED: Final = "R_EFFECTS_CHANGED"
R_NEW_EFFECT: Final = "R_NEW_EFFECT"
R_TEST_SURFACE_CHANGED: Final = "R_TEST_SURFACE_CHANGED"
R_IMPORTS_CHANGED: Final = "R_IMPORTS_CHANGED"
R_USER_VIOLATION: Final = "R_USER_VIOLATION"
R_PATH_UNRESOLVED: Final = "R_PATH_UNRESOLVED"
R_TYPE_MISMATCH: Final = "R_TYPE_MISMATCH"
R_OPERATOR_TARGET_MISMATCH: Final = "R_OPERATOR_TARGET_MISMATCH"
R_UNSUPPORTED_OPERATOR: Final = "R_UNSUPPORTED_OPERATOR"
R_UNSUPPORTED_REPAIR_KIND: Final = "R_UNSUPPORTED_REPAIR_KIND"
R_EXTRACTION_TIMEOUT: Final = "R_EXTRACTION_TIMEOUT"
R_UNKNOWN: Final = "R_UNKNOWN"

REPAIR_CODES: Final = frozenset(
    {
        R_API_REMOVED,
        R_API_CHANGED,
        R_TYPE_RELATIONS_CHANGED,
        R_EFFECTS_CHANGED,
        R_NEW_EFFECT,
        R_TEST_SURFACE_CHANGED,
        R_IMPORTS_CHANGED,
        R_USER_VIOLATION,
        R_PATH_UNRESOLVED,
        R_TYPE_MISMATCH,
        R_OPERATOR_TARGET_MISMATCH,
        R_UNSUPPORTED_OPERATOR,
        R_UNSUPPORTED_REPAIR_KIND,
        R_EXTRACTION_TIMEOUT,
        R_UNKNOWN,
    }
)

_TEMPLATE_REPAIR_CODE: Final[dict[str, str]] = {
    "template:feature:no_removed_api": R_API_REMOVED,
    "template:refactor:api_surface_unchanged": R_API_CHANGED,
    "template:bugfix:api_surface_unchanged": R_API_CHANGED,
    "template:test_update:api_surface_unchanged": R_API_CHANGED,
    "template:refactor:type_relations_unchanged": R_TYPE_RELATIONS_CHANGED,
    "template:refactor:effects_unchanged": R_EFFECTS_CHANGED,
    "template:test_update:effects_unchanged": R_EFFECTS_CHANGED,
    "template:bugfix:no_new_effects": R_NEW_EFFECT,
    "template:feature:no_new_effects": R_NEW_EFFECT,
    "template:refactor:test_surface_unchanged": R_TEST_SURFACE_CHANGED,
    "template:test_update:imports_unchanged": R_IMPORTS_CHANGED,
}

_ERROR_CODE_REPAIR_CODE: Final[dict[str, str]] = {
    "E_PATH_UNRESOLVED": R_PATH_UNRESOLVED,
    "E_TYPE_MISMATCH": R_TYPE_MISMATCH,
    "E_OPERATOR_TARGET_MISMATCH": R_OPERATOR_TARGET_MISMATCH,
    "E_OPERATOR_UNSUPPORTED_P1": R_UNSUPPORTED_OPERATOR,
    "E_REPAIR_KIND_UNSUPPORTED_P1": R_UNSUPPORTED_REPAIR_KIND,
    "E_DIMENSION_TIMED_OUT": R_EXTRACTION_TIMEOUT,
}


def resolve_repair_code(result: ConstraintResult) -> str:
    """Resolve a CSCI-13 result into one stable CSCI-14 repair code."""

    if result.error_code is None:
        return R_UNKNOWN

    if result.error_code == "E_VIOLATION":
        return _TEMPLATE_REPAIR_CODE.get(result.constraint_id, R_USER_VIOLATION)

    return _ERROR_CODE_REPAIR_CODE.get(result.error_code, R_UNKNOWN)
