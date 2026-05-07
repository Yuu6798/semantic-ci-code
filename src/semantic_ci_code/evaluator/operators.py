from __future__ import annotations

from dataclasses import dataclass
from numbers import Real
from typing import Final

from pydantic import BaseModel

from semantic_ci_code.domain.state_schema import JsonValue
from semantic_ci_code.framework.constraint_types import Operator
from semantic_ci_code.framework.match_schema import match_item

STATUS_SATISFIED: Final = "satisfied"
STATUS_VIOLATED: Final = "violated"
STATUS_UNKNOWN: Final = "unknown"

E_VIOLATION: Final = "E_VIOLATION"
E_TYPE_MISMATCH: Final = "E_TYPE_MISMATCH"

BASELINE_OPERATORS: Final = frozenset(
    {
        Operator.EQUALS_BASELINE,
        Operator.NOT_EQUALS_BASELINE,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
        Operator.UNCHANGED,
        Operator.CHANGED,
    }
)

PURE_OPERATORS: Final = frozenset(
    {
        Operator.EQUALS,
        Operator.NOT_EQUALS,
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.EXCLUDES_ALL,
        Operator.SUBSET_OF,
        Operator.SUPERSET_OF,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
        Operator.WITHIN_RANGE,
    }
)


class CanonicalMapping(tuple):
    """Tuple marker for dicts canonicalized by evaluator evidence.

    Plain JSON arrays can legitimately contain two-item string tuples. The
    marker lets renderers reconstruct only dict-origin records as objects.
    """


@dataclass(frozen=True)
class OperatorOutcome:
    status: str
    error_code: str | None
    evidence: tuple[tuple[str, JsonValue], ...]


def evaluate_pure_operator(
    operator: Operator,
    resolved: object,
    expected: object,
    *,
    tolerance: float | None,
) -> OperatorOutcome:
    try:
        if operator is Operator.EQUALS:
            return _boolean_outcome(
                _canon(resolved) == _canon(expected),
                observed=resolved,
                expected=expected,
            )
        if operator is Operator.NOT_EQUALS:
            return _boolean_outcome(
                _canon(resolved) != _canon(expected),
                observed=resolved,
                expected=expected,
            )
        if operator is Operator.INCLUDES_ALL:
            return _includes_all(resolved, expected)
        if operator is Operator.INCLUDES_ANY:
            return _includes_any(resolved, expected)
        if operator is Operator.EXCLUDES_ALL:
            return _excludes_all(resolved, expected)
        if operator is Operator.SUBSET_OF:
            return _subset_of(resolved, expected)
        if operator is Operator.SUPERSET_OF:
            return _superset_of(resolved, expected)
        if operator is Operator.LESS_THAN:
            return _numeric_compare(resolved, expected, tolerance=tolerance, relation="lt")
        if operator is Operator.LESS_THAN_OR_EQUAL:
            return _numeric_compare(resolved, expected, tolerance=tolerance, relation="le")
        if operator is Operator.GREATER_THAN:
            return _numeric_compare(resolved, expected, tolerance=tolerance, relation="gt")
        if operator is Operator.GREATER_THAN_OR_EQUAL:
            return _numeric_compare(resolved, expected, tolerance=tolerance, relation="ge")
        if operator is Operator.WITHIN_RANGE:
            return _within_range(resolved, expected, tolerance=tolerance)
    except TypeError:
        return _unknown_type_mismatch(observed=resolved, expected=expected)

    raise AssertionError(f"Unsupported pure operator dispatch: {operator}")


def evaluate_baseline_operator(
    operator: Operator,
    baseline: object,
    candidate: object,
    *,
    tolerance: float | None,
) -> OperatorOutcome:
    try:
        if operator in {Operator.EQUALS_BASELINE, Operator.UNCHANGED}:
            return _equals_baseline(baseline, candidate)
        if operator in {Operator.NOT_EQUALS_BASELINE, Operator.CHANGED}:
            return _baseline_boolean_outcome(
                _canon(candidate) != _canon(baseline),
                baseline=baseline,
                candidate=candidate,
            )
        if operator is Operator.SUPERSET_OF_BASELINE:
            return _baseline_superset_of(baseline, candidate)
        if operator is Operator.NO_NEW_ITEMS:
            return _no_new_items(baseline, candidate)
        if operator is Operator.NO_REMOVED_ITEMS:
            return _no_removed_items(baseline, candidate)
    except TypeError:
        return _unknown_type_mismatch(baseline=baseline, candidate=candidate)

    raise AssertionError(f"Unsupported baseline operator dispatch: {operator}")


def _includes_all(resolved: object, expected: object) -> OperatorOutcome:
    observed_items = _collection_items(resolved)
    expected_items = _collection_items(expected)
    if observed_items is None or expected_items is None:
        return _unknown_type_mismatch(observed=resolved, expected=expected)
    missing = tuple(
        expected_item
        for expected_item in expected_items
        if not _any_observed_matches(expected_item, observed_items)
    )
    return _set_outcome(not missing, observed_items, expected_items, missing=missing)


def _includes_any(resolved: object, expected: object) -> OperatorOutcome:
    observed_items = _collection_items(resolved)
    expected_items = _collection_items(expected)
    if observed_items is None or expected_items is None:
        return _unknown_type_mismatch(observed=resolved, expected=expected)
    common = tuple(
        expected_item
        for expected_item in expected_items
        if _any_observed_matches(expected_item, observed_items)
    )
    return _set_outcome(bool(common), observed_items, expected_items, common=common)


def _excludes_all(resolved: object, expected: object) -> OperatorOutcome:
    observed_items = _collection_items(resolved)
    expected_items = _collection_items(expected)
    if observed_items is None or expected_items is None:
        return _unknown_type_mismatch(observed=resolved, expected=expected)
    matched = _matched_pairs(expected_items, observed_items)
    return _set_outcome(not matched, observed_items, expected_items, matched=matched)


def _subset_of(resolved: object, expected: object) -> OperatorOutcome:
    observed_items = _collection_items(resolved)
    expected_items = _collection_items(expected)
    if observed_items is None or expected_items is None:
        return _unknown_type_mismatch(observed=resolved, expected=expected)
    extra = tuple(
        observed_item
        for observed_item in observed_items
        if not _any_expected_matches(observed_item, expected_items)
    )
    return _set_outcome(not extra, observed_items, expected_items, extra=extra)


def _superset_of(resolved: object, expected: object) -> OperatorOutcome:
    observed_items = _collection_items(resolved)
    expected_items = _collection_items(expected)
    if observed_items is None or expected_items is None:
        return _unknown_type_mismatch(observed=resolved, expected=expected)
    missing = tuple(
        expected_item
        for expected_item in expected_items
        if not _any_observed_matches(expected_item, observed_items)
    )
    return _set_outcome(not missing, observed_items, expected_items, missing=missing)


def _equals_baseline(baseline: object, candidate: object) -> OperatorOutcome:
    if _canon(candidate) == _canon(baseline):
        return _baseline_boolean_outcome(True, baseline=baseline, candidate=candidate)
    baseline_items = _collection_items(baseline)
    candidate_items = _collection_items(candidate)
    if baseline_items is None or candidate_items is None:
        return _baseline_boolean_outcome(False, baseline=baseline, candidate=candidate)
    added = tuple(item for item in candidate_items if item not in baseline_items)
    removed = tuple(item for item in baseline_items if item not in candidate_items)
    return _baseline_set_outcome(
        False,
        baseline_items,
        candidate_items,
        added=added,
        removed=removed,
    )


def _baseline_superset_of(baseline: object, candidate: object) -> OperatorOutcome:
    baseline_items = _collection_items(baseline)
    candidate_items = _collection_items(candidate)
    if baseline_items is None or candidate_items is None:
        return _unknown_type_mismatch(baseline=baseline, candidate=candidate)
    missing = tuple(item for item in baseline_items if item not in candidate_items)
    return _baseline_set_outcome(not missing, baseline_items, candidate_items, missing=missing)


def _no_new_items(baseline: object, candidate: object) -> OperatorOutcome:
    baseline_items = _collection_items(baseline)
    candidate_items = _collection_items(candidate)
    if baseline_items is None or candidate_items is None:
        return _unknown_type_mismatch(baseline=baseline, candidate=candidate)
    extra = tuple(item for item in candidate_items if item not in baseline_items)
    return _baseline_set_outcome(not extra, baseline_items, candidate_items, extra=extra)


def _no_removed_items(baseline: object, candidate: object) -> OperatorOutcome:
    baseline_items = _collection_items(baseline)
    candidate_items = _collection_items(candidate)
    if baseline_items is None or candidate_items is None:
        return _unknown_type_mismatch(baseline=baseline, candidate=candidate)
    missing = tuple(item for item in baseline_items if item not in candidate_items)
    return _baseline_set_outcome(not missing, baseline_items, candidate_items, missing=missing)


def _numeric_compare(
    resolved: object,
    expected: object,
    *,
    tolerance: float | None,
    relation: str,
) -> OperatorOutcome:
    if not _is_number(resolved) or not _is_number(expected):
        return _unknown_type_mismatch(observed=resolved, expected=expected)

    tol = tolerance or 0.0
    if relation == "lt":
        satisfied = resolved < expected + tol
    elif relation == "le":
        satisfied = resolved <= expected + tol
    elif relation == "gt":
        satisfied = resolved > expected - tol
    elif relation == "ge":
        satisfied = resolved >= expected - tol
    else:
        raise AssertionError(f"Unknown numeric relation: {relation}")

    return _boolean_outcome(satisfied, observed=resolved, expected=expected, tolerance=tol)


def _within_range(
    resolved: object,
    expected: object,
    *,
    tolerance: float | None,
) -> OperatorOutcome:
    if not _is_number(resolved):
        return _unknown_type_mismatch(observed=resolved, expected=expected)
    expected_range = _canon(expected)
    if (
        not isinstance(expected_range, tuple)
        or len(expected_range) != 2
        or not _is_number(expected_range[0])
        or not _is_number(expected_range[1])
    ):
        return _unknown_type_mismatch(observed=resolved, expected=expected)

    tol = tolerance or 0.0
    low = expected_range[0] - tol
    high = expected_range[1] + tol
    return _boolean_outcome(
        low <= resolved <= high,
        observed=resolved,
        expected=expected,
        lower=low,
        upper=high,
        tolerance=tol,
    )


def _boolean_outcome(satisfied: bool, **evidence: object) -> OperatorOutcome:
    status = STATUS_SATISFIED if satisfied else STATUS_VIOLATED
    error_code = None if satisfied else E_VIOLATION
    return OperatorOutcome(status, error_code, _evidence(**evidence))


def _baseline_boolean_outcome(
    satisfied: bool,
    *,
    baseline: object,
    candidate: object,
) -> OperatorOutcome:
    status = STATUS_SATISFIED if satisfied else STATUS_VIOLATED
    error_code = None if satisfied else E_VIOLATION
    return OperatorOutcome(
        status,
        error_code,
        _evidence(baseline=baseline, candidate=candidate),
    )


def _set_outcome(
    satisfied: bool,
    observed_items: tuple[object, ...],
    expected_items: tuple[object, ...],
    **details: tuple[object, ...],
) -> OperatorOutcome:
    status = STATUS_SATISFIED if satisfied else STATUS_VIOLATED
    error_code = None if satisfied else E_VIOLATION
    evidence = {
        "observed": _sorted_values(observed_items),
        "expected": _sorted_values(expected_items),
    }
    evidence.update({key: _sorted_values(value) for key, value in details.items() if value})
    return OperatorOutcome(status, error_code, _evidence(**evidence))


def _baseline_set_outcome(
    satisfied: bool,
    baseline_items: tuple[object, ...],
    candidate_items: tuple[object, ...],
    **details: tuple[object, ...],
) -> OperatorOutcome:
    status = STATUS_SATISFIED if satisfied else STATUS_VIOLATED
    error_code = None if satisfied else E_VIOLATION
    evidence = {
        "baseline": _sorted_values(baseline_items),
        "candidate": _sorted_values(candidate_items),
    }
    evidence.update({key: _sorted_values(value) for key, value in details.items() if value})
    return OperatorOutcome(status, error_code, _evidence(**evidence))


def _unknown_type_mismatch(**evidence: object) -> OperatorOutcome:
    return OperatorOutcome(
        STATUS_UNKNOWN,
        E_TYPE_MISMATCH,
        _evidence(**evidence),
    )


def _collection_items(value: object) -> tuple[object, ...] | None:
    canon = _canon(value)
    if isinstance(canon, str | bytes):
        return None
    if isinstance(canon, tuple):
        return _sorted_values(frozenset(canon))
    if isinstance(canon, frozenset):
        return _sorted_values(canon)
    return None


def _is_number(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def _evidence(**items: object) -> tuple[tuple[str, JsonValue], ...]:
    return tuple((key, _canon(value)) for key, value in sorted(items.items()))


def _any_observed_matches(expected_item: object, observed_items: tuple[object, ...]) -> bool:
    return any(match_item(expected_item, observed_item) for observed_item in observed_items)


def _any_expected_matches(observed_item: object, expected_items: tuple[object, ...]) -> bool:
    return any(match_item(expected_item, observed_item) for expected_item in expected_items)


def _matched_pairs(
    expected_items: tuple[object, ...],
    observed_items: tuple[object, ...],
) -> tuple[object, ...]:
    pairs = []
    for expected_item in expected_items:
        for observed_item in observed_items:
            if match_item(expected_item, observed_item):
                pairs.append(
                    CanonicalMapping(
                        (
                            ("expected_item", expected_item),
                            ("observed_record", observed_item),
                        )
                    )
                )
    return _sorted_values(frozenset(pairs))


def _sorted_values(values: frozenset[object] | tuple[object, ...]) -> tuple[object, ...]:
    return tuple(sorted(values, key=repr))


def _canon(value: object) -> object:
    if isinstance(value, BaseModel):
        return _canon(value.model_dump(mode="json"))
    if isinstance(value, CanonicalMapping):
        return CanonicalMapping((key, _canon(item)) for key, item in value)
    if isinstance(value, list | tuple):
        return tuple(_canon(item) for item in value)
    if isinstance(value, dict):
        return CanonicalMapping((key, _canon(item)) for key, item in sorted(value.items()))
    if isinstance(value, set | frozenset):
        return frozenset(_canon(item) for item in value)
    return value
