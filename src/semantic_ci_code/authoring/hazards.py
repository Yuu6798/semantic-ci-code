"""Authoring hazard detectors for `semantic-ci target-doctor`.

Each `detect_*` function inspects a `CompiledTarget` (and optional
package-root or files-touched context) and returns zero or one `Advisory`.
The combined entrypoint `detect_advisories` returns a deterministically
ordered tuple. All detectors are pure: no network, no LLM, no I/O outside
of reading `package_root` for D1.

The advisor surface never participates in the verdict
(`docs/code_semantic_ci_design.md §23.3.1`); detection or non-detection
does not change exit codes.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from semantic_ci_code.authoring.advisory import Advisory
from semantic_ci_code.compiler.target_compiler import (
    CompiledConstraint,
    CompiledTarget,
    ConstraintSource,
)
from semantic_ci_code.compiler.templates import TEMPLATE_CONSTRAINTS
from semantic_ci_code.domain.state_schema import ChangeKind
from semantic_ci_code.framework.constraint_types import (
    ConstraintKind,
    Operator,
    Severity,
    UnknownPolicy,
)

_ADVISORY_ORDER = (
    "ADVISORY-D1",
    "ADVISORY-D3",
    "ADVISORY-D4",
    "ADVISORY-P1",
    "ADVISORY-P2",
    "ADVISORY-S1",
)

_TEST_SURFACE_DELTA_PREFIX = "test_surface_delta"
_ADDITION_FORCING_OPERATORS = frozenset(
    {
        Operator.EQUALS,
        Operator.INCLUDES_ALL,
        Operator.INCLUDES_ANY,
        Operator.SUPERSET_OF,
    }
)
# When applied to a `_delta.added` / `.new_cases` target with a
# **non-empty** `expected`, these operators require the observed delta
# to contain at least one item — a real positive addition assertion.
# `equals ["x"]` forces observed == ["x"] (non-empty),
# `includes_all` / `includes_any` / `superset_of` with non-empty
# expected force observed ⊇ expected (and therefore non-empty).
# Empty-expected variants (`equals []`, `includes_all []`,
# `superset_of []`) are vacuously satisfied by an empty observed delta
# and must NOT suppress ADVISORY-P1 / P2.
# `not_equals expected: []` is handled separately in
# `_is_positive_addition`. `SUPERSET_OF_BASELINE` is excluded because it
# has no `expected` parameter and cannot guarantee a non-empty
# addition by itself (an empty baseline + empty delta is satisfied).
_NON_PYTHON_SUFFIXES = frozenset(
    {
        ".md",
        ".rst",
        ".txt",
        ".yml",
        ".yaml",
        ".toml",
        ".cfg",
        ".ini",
        ".json",
        ".lock",
    }
)
_NON_PYTHON_BASENAMES = frozenset(
    {
        "Makefile",
        "Dockerfile",
        ".gitignore",
        ".gitattributes",
        ".pre-commit-config.yaml",
        "LICENSE",
        "MANIFEST.in",
    }
)


def detect_advisories(
    target: CompiledTarget,
    *,
    package_root: Path | None = None,
    files_touched: tuple[Path, ...] | None = None,
) -> tuple[Advisory, ...]:
    """Run every detector and return the advisories in canonical order.

    `package_root` is required for D1; when omitted the detector is
    skipped silently. `files_touched` is required for D4; when omitted
    (e.g. git not available) the detector is skipped.
    """
    advisories: list[Advisory] = []
    if package_root is not None:
        advisories.extend(detect_d1(target, package_root=package_root))
    advisories.extend(detect_d3(target))
    if files_touched is not None:
        advisories.extend(detect_d4(target, files_touched=files_touched))
    advisories.extend(detect_p1(target))
    advisories.extend(detect_p2(target))
    advisories.extend(detect_s1(target))
    return tuple(_sorted(advisories))


def detect_d1(
    target: CompiledTarget,
    *,
    package_root: Path,
) -> tuple[Advisory, ...]:
    """`test_surface_*` constraint exists, but no test files visible under root."""
    test_constraints = tuple(c for c in target.constraints if _is_test_surface_target(c.target))
    if not test_constraints:
        return ()
    if _has_python_test_files(package_root):
        return ()
    advisories: list[Advisory] = []
    for constraint in test_constraints:
        advisories.append(
            Advisory(
                code="ADVISORY-D1",
                message=(
                    f"constraint {constraint.id!r} targets {constraint.target} but "
                    f"no Python test files (test_*.py / *_test.py / tests/) were found "
                    f"under --package-root={package_root}. The extractor produces an "
                    f"empty test_surface, so this constraint may fire on noise. Either "
                    f"widen --package-root or remove the constraint."
                ),
                evidence={
                    "constraint_id": constraint.id,
                    "target": constraint.target,
                    "package_root": str(package_root),
                },
            )
        )
    return tuple(advisories)


def detect_d3(target: CompiledTarget) -> tuple[Advisory, ...]:
    """User constraint duplicates a template-expanded constraint."""
    template_constraints = TEMPLATE_CONSTRAINTS.get(target.primary_kind, ())
    if not template_constraints:
        return ()
    user_constraints = tuple(c for c in target.constraints if c.source is ConstraintSource.USER)
    advisories: list[Advisory] = []
    for user_c in user_constraints:
        for template_c in template_constraints:
            if _constraints_collide(user_c, template_c):
                advisories.append(
                    Advisory(
                        code="ADVISORY-D3",
                        message=(
                            f"user constraint {user_c.id!r} duplicates the template "
                            f"constraint {template_c.id!r} expanded by primary_kind="
                            f"{target.primary_kind.value} (same kind/target/operator/"
                            f"expected). Remove the user constraint or tighten/scope "
                            f"it instead."
                        ),
                        evidence={
                            "user_constraint_id": user_c.id,
                            "template_constraint_id": template_c.id,
                            "primary_kind": target.primary_kind.value,
                            "target": user_c.target,
                            "operator": user_c.operator.value,
                        },
                    )
                )
                break
    return tuple(advisories)


def detect_d4(
    target: CompiledTarget,
    *,
    files_touched: tuple[Path, ...],
) -> tuple[Advisory, ...]:
    """Lock-only target + non-Python diff = vacuous PASS."""
    if not files_touched:
        return ()
    if any(_is_python_path(path) for path in files_touched):
        return ()
    if not _is_lock_only_target(target):
        return ()
    return (
        Advisory(
            code="ADVISORY-D4",
            message=(
                f"primary_kind={target.primary_kind.value} expands lock-only "
                f"constraints, and the candidate diff touches no Python files "
                f"({len(files_touched)} non-Python file(s)). The verdict will "
                f"be a vacuous PASS — the engine extracted nothing relevant. "
                f"Pair this PR with the appropriate non-Python gate (lint, "
                f"schema check, workflow validator)."
            ),
            evidence={
                "primary_kind": target.primary_kind.value,
                "files_touched_count": len(files_touched),
                "sample_files": [str(p) for p in files_touched[:5]],
            },
        ),
    )


def detect_p1(target: CompiledTarget) -> tuple[Advisory, ...]:
    """`primary_kind=feature` but no positive addition constraint."""
    if target.primary_kind is not ChangeKind.FEATURE:
        return ()
    if any(_is_positive_addition(c) for c in target.constraints):
        return ()
    return (
        Advisory(
            code="ADVISORY-P1",
            message=(
                "primary_kind=feature has no positive addition constraint "
                "(e.g. includes_all / includes_any / not_equals expected: [] "
                "against api_surface_delta.added or test_surface_delta.new_cases). "
                "The verdict will pass vacuously even if the feature is not "
                "implemented. Add a constraint asserting the new surface."
            ),
            evidence={"primary_kind": "feature"},
        ),
    )


def detect_p2(target: CompiledTarget) -> tuple[Advisory, ...]:
    """`primary_kind=bugfix` but no test_surface_delta.new_cases expectation."""
    if target.primary_kind is not ChangeKind.BUGFIX:
        return ()
    if any(_targets_new_test_cases(c) for c in target.constraints):
        return ()
    return (
        Advisory(
            code="ADVISORY-P2",
            message=(
                "primary_kind=bugfix has no test_surface_delta.new_cases "
                "expectation (e.g. includes_all / not_equals expected: [] "
                "against test_surface_delta.new_cases). A bugfix without a "
                "regression test asserts no behavioural lock. Add a constraint "
                "requiring the new test, or relax primary_kind."
            ),
            evidence={"primary_kind": "bugfix"},
        ),
    )


def detect_s1(target: CompiledTarget) -> tuple[Advisory, ...]:
    """`severity: info` paired with `unknown_policy in {fail, repair}`.

    After Brief D1-4, authoring-cause UNKNOWN forces `verdict: fail`
    irrespective of `unknown_policy`. The remaining hazard is for
    *extraction-cause* and *open_runtime* UNKNOWN, where `unknown_policy`
    still governs. `severity: info` should keep a constraint out of the
    verdict, but `unknown_policy: fail|repair` re-arms the constraint
    on those UNKNOWN branches.
    """
    advisories: list[Advisory] = []
    for constraint in target.constraints:
        if constraint.source is not ConstraintSource.USER:
            continue
        if constraint.severity is not Severity.INFO:
            continue
        if constraint.unknown_policy not in {UnknownPolicy.FAIL, UnknownPolicy.REPAIR}:
            continue
        advisories.append(
            Advisory(
                code="ADVISORY-S1",
                message=(
                    f"constraint {constraint.id!r} has severity=info but "
                    f"unknown_policy={constraint.unknown_policy.value}. info "
                    f"keeps a violated result out of the verdict, but the "
                    f"non-ignore unknown_policy still routes extraction-cause / "
                    f"open_runtime UNKNOWN results into the verdict. For a fully "
                    f"informational constraint use unknown_policy=ignore."
                ),
                evidence={
                    "constraint_id": constraint.id,
                    "severity": constraint.severity.value,
                    "unknown_policy": constraint.unknown_policy.value,
                },
            )
        )
    return tuple(advisories)


def _sorted(advisories: Iterable[Advisory]) -> list[Advisory]:
    order = {code: index for index, code in enumerate(_ADVISORY_ORDER)}

    def sort_key(advisory: Advisory) -> tuple[int, str]:
        constraint_id = str(advisory.evidence.get("constraint_id", ""))
        return (order[advisory.code], constraint_id)

    return sorted(advisories, key=sort_key)


def _is_test_surface_target(path: str) -> bool:
    """Match `test_surface_delta` and any `test_surface_delta.<sub>` path.

    Per `docs/brief_8_planning.md §6.3.1`, ADVISORY-D1 is scoped to
    delta-mode test_surface targets. State-mode `test_surface` is not
    in scope: `equals_baseline` against an empty extraction matches an
    equally-empty baseline extracted with the same package_root, so it
    does not fire on visibility loss.
    """
    head = path.split(".", 1)[0]
    return head == _TEST_SURFACE_DELTA_PREFIX


def _has_python_test_files(package_root: Path) -> bool:
    if not package_root.exists() or not package_root.is_dir():
        return False
    for entry in package_root.rglob("*.py"):
        name = entry.name
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
        if "tests" in entry.parts or "test" in entry.parts:
            return True
    return False


def _constraints_collide(
    user_c: CompiledConstraint,
    template_c: CompiledConstraint,
) -> bool:
    return (
        user_c.kind == template_c.kind
        and user_c.target == template_c.target
        and user_c.operator == template_c.operator
        and _canonicalize_expected(user_c.expected) == _canonicalize_expected(template_c.expected)
    )


def _canonicalize_expected(value: object) -> object:
    """Recursively normalize dict/list/tuple to a canonical form.

    The compiler's `_freeze_expected` only flattens top-level lists into
    tuples, leaving nested structures inside dicts untouched. Templates
    store nested values as tuples (e.g.
    `{"added": (), "removed": ()}`) while a YAML user constraint of the
    same shape stays as `{"added": [], "removed": []}`. Direct `==`
    would treat them as different, suppressing ADVISORY-D3. This helper
    normalizes both sides before comparison.
    """
    if isinstance(value, dict):
        return tuple((key, _canonicalize_expected(item)) for key, item in sorted(value.items()))
    if isinstance(value, list | tuple):
        return tuple(_canonicalize_expected(item) for item in value)
    return value


def _is_python_path(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return True
    if suffix in _NON_PYTHON_SUFFIXES:
        return False
    if path.name in _NON_PYTHON_BASENAMES:
        return False
    # Files in .github/, docs/, .githooks/ etc. without a recognised suffix
    # are treated as non-Python (they cannot affect a Python CodeState).
    return False


def _is_lock_only_target(target: CompiledTarget) -> bool:
    """True if every verdict-participating constraint is lock-only.

    Verdict-participating means the evaluator can fail on the
    constraint (see `_participates_in_verdict`). A refactor target
    with hard lock templates plus an extra constraint that the
    evaluator silently skips (info severity / repair kind /
    changed_only_in operator) still passes vacuously on an empty
    delta — the hard locks pass trivially and the skipped constraint
    is ignored — so D4 must still fire.
    """
    verdict_participating = tuple(c for c in target.constraints if _participates_in_verdict(c))
    if not verdict_participating:
        return False
    for constraint in verdict_participating:
        if not _is_lock_only_constraint(constraint):
            return False
    return True


def _participates_in_verdict(constraint: CompiledConstraint) -> bool:
    """True if the evaluator can route this constraint into the verdict.

    Three constraint shapes are unconditionally non-participating:

    - `severity: info` — Advisor channel, never affects verdict
      (`docs/code_semantic_ci_design.md §23.3`).
    - `kind: repair` — `evaluator.evaluator._evaluate_constraint`
      returns SKIPPED (`reason="repair_kind_p1"`) before any
      operator dispatch.
    - `operator: changed_only_in` — same evaluator surface returns
      SKIPPED (`reason="changed_only_in_p1"`).

    These filters mirror the runtime semantics so target-doctor's
    classification reflects what the verdict can actually conclude.
    """
    if constraint.severity is Severity.INFO:
        return False
    if constraint.kind is ConstraintKind.REPAIR:
        return False
    if constraint.operator is Operator.CHANGED_ONLY_IN:
        return False
    return True


def _is_lock_only_constraint(constraint: CompiledConstraint) -> bool:
    operator = constraint.operator
    expected = constraint.expected
    if operator in {
        Operator.EQUALS_BASELINE,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
        Operator.UNCHANGED,
    }:
        return True
    if operator is Operator.EQUALS:
        if _is_empty_collection(expected):
            return True
        if isinstance(expected, dict) and all(
            _is_empty_collection(value) for value in expected.values()
        ):
            return True
    if operator is Operator.EXCLUDES_ALL:
        return True
    if operator is Operator.SUBSET_OF:
        # `subset_of [...]` and `subset_of []` are both vacuously
        # satisfied by an empty observed delta (`[]` is a subset of any
        # set, including the empty set), so a target whose only
        # non-template constraint is a subset_of allow-list still
        # passes vacuously on a config-only diff.
        return True
    return False


def _is_empty_collection(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str | bytes):
        return False
    if isinstance(value, list | tuple | set | frozenset):
        return len(value) == 0
    return False


def _is_positive_addition(constraint: CompiledConstraint) -> bool:
    """True if this constraint forces a non-empty observed delta AND
    participates in the verdict.

    Three filters apply (each independently essential to the P1 / P2
    "vacuous PASS" semantics):

    1. `_participates_in_verdict(constraint)` — INFO severity, repair
       kind, and `changed_only_in` operator are unconditionally
       SKIPPED by the evaluator and never change the verdict.
    2. The target points at an addition dimension (`_delta.added`,
       `_delta.added_cases`, `.new_cases`).
    3. The operator + expected combination forces observed != []:
       `equals` / `includes_all` / `includes_any` / `superset_of` with
       non-empty expected qualify; `not_equals expected: []` qualifies;
       empty expected variants do not (vacuous).
    """
    if not _participates_in_verdict(constraint):
        return False
    if not _targets_added_dimension(constraint.target):
        return False
    if constraint.operator in _ADDITION_FORCING_OPERATORS:
        return not _is_empty_collection(constraint.expected)
    if constraint.operator is Operator.NOT_EQUALS and _is_empty_collection(constraint.expected):
        return True
    return False


def _targets_added_dimension(path: str) -> bool:
    return "_delta.added" in path or ".new_cases" in path


def _targets_new_test_cases(constraint: CompiledConstraint) -> bool:
    if "test_surface_delta" not in constraint.target:
        return False
    if "new_cases" not in constraint.target and "added" not in constraint.target:
        return False
    return _is_positive_addition(constraint)
