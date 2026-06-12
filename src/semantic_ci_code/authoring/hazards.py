"""Authoring hazard detectors for `semantic-ci target-doctor`.

Each `detect_*` function inspects a `CompiledTarget` (and optional
package-root, files-touched, or nested-def-growth context) and returns zero
or one `Advisory`. The combined entrypoint `detect_advisories` returns a
deterministically ordered tuple. All detectors are pure: no network, no
LLM, no I/O outside of reading `package_root` for D1 — diff-derived
context (D4 / D6) is computed by the CLI layer and passed in.

The advisor surface never participates in the verdict
(`docs/code_semantic_ci_design.md §23.3.1`); detection or non-detection
does not change exit codes.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from semantic_ci_code.authoring.advisory import Advisory
from semantic_ci_code.authoring.nested_defs import NestedDefGrowth, VisibleDefGrowth
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
    "ADVISORY-D6",
    "ADVISORY-D7",
    "ADVISORY-I1",
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
    nested_def_growth: tuple[NestedDefGrowth, ...] | None = None,
    visible_def_growth: tuple[VisibleDefGrowth, ...] | None = None,
) -> tuple[Advisory, ...]:
    """Run every detector and return the advisories in canonical order.

    `package_root` is required for D1; when omitted the detector is
    skipped silently. `files_touched` is required for D4,
    `nested_def_growth` for D6, and `visible_def_growth` for D7; when
    omitted (e.g. git not available) the corresponding detector is
    skipped.
    """
    advisories: list[Advisory] = []
    if package_root is not None:
        advisories.extend(detect_d1(target, package_root=package_root))
    advisories.extend(detect_d3(target))
    if files_touched is not None:
        advisories.extend(detect_d4(target, files_touched=files_touched))
    if nested_def_growth is not None:
        advisories.extend(detect_d6(target, nested_def_growth=nested_def_growth))
    if visible_def_growth is not None:
        advisories.extend(detect_d7(target, visible_def_growth=visible_def_growth))
    advisories.extend(detect_i1(target))
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
    """Lock-only target + no in-scope Python diff = vacuous PASS.

    An empty `files_touched` tuple is treated as "no Python in scope":
    `_resolve_files_touched` filters the numstat to paths inside
    `--package-root`, so an empty result means every diff path was
    out-of-scope (or the PR has no diff). Either way, a lock-only
    target gates nothing relevant and passes vacuously. `None`
    indicates that D4 is inapplicable (git unavailable) and is
    filtered out by the caller before reaching this detector.
    """
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


def detect_d6(
    target: CompiledTarget,
    *,
    nested_def_growth: tuple[NestedDefGrowth, ...],
) -> tuple[Advisory, ...]:
    """Complexity constraint + nested-def growth = displaced complexity.

    `python_complexity_extractor` stops descent at nested def boundaries
    (`api_surface` emission parity), so a refactor that moves an outer
    function's body into function-nested helpers reports a large
    cyclomatic/cognitive drop while the real complexity is unchanged —
    the lock passes and the verdict silently endorses the displacement
    (D6, sibling of D4's vacuous PASS). The detector fires when the
    target declares a verdict-participating `complexity_delta` constraint
    AND the candidate diff grows the nested-def count in at least one
    in-scope Python file. Growth is a heuristic displacement signal, not
    proof — the advisory asks for review, never seats the verdict.

    An empty `nested_def_growth` tuple means "diff inspected, no Python
    files with parseable content on both sides"; `None` (inapplicable,
    git unavailable) is filtered out by the caller before reaching this
    detector — mirroring D4's `files_touched` contract.
    """
    complexity_constraints = tuple(
        c
        for c in target.constraints
        if _is_complexity_delta_target(c.target) and _participates_in_verdict(c)
    )
    if not complexity_constraints:
        return ()
    grown = tuple(g for g in nested_def_growth if g.candidate_count > g.baseline_count)
    if not grown:
        return ()
    total_added = sum(g.candidate_count - g.baseline_count for g in grown)
    constraint_ids = ", ".join(repr(c.id) for c in complexity_constraints)
    return (
        Advisory(
            code="ADVISORY-D6",
            message=(
                f"the candidate diff adds {total_added} nested function "
                f"definition(s) across {len(grown)} file(s), and the target "
                f"declares complexity_delta constraint(s) ({constraint_ids}). "
                f"The complexity extractor does not descend into nested "
                f"functions, so complexity moved into nested helpers vanishes "
                f"from cyclomatic/cognitive numbers — a reported decrease may "
                f"be displacement, not simplification. Review whether the new "
                f"nested helpers should be module-level functions (which are "
                f"extracted and constrained) instead."
            ),
            evidence={
                "constraint_ids": [c.id for c in complexity_constraints],
                "nested_defs_added": total_added,
                "grown_files_count": len(grown),
                "files": [
                    {
                        "path": g.path,
                        "baseline_nested_defs": g.baseline_count,
                        "candidate_nested_defs": g.candidate_count,
                    }
                    for g in grown[:5]
                ],
            },
        ),
    )


def detect_d7(
    target: CompiledTarget,
    *,
    visible_def_growth: tuple[VisibleDefGrowth, ...],
) -> tuple[Advisory, ...]:
    """Refactor + cyclomatic no-increase lock + extract-method shape.

    `complexity_delta.cyclomatic` is the **summed** cyclomatic delta over
    extractor-visible functions, and every function starts at base 1. An
    extract-method refactor therefore micro-increases the sum by +1 per
    extracted helper even when every branch is preserved — a
    `primary_kind: refactor` target locking `cyclomatic <= 0` is
    structurally guaranteed to FAIL on exactly the refactor it means to
    endorse (D7, `docs/dogfooding_findings_tracker.md`). Cognitive is the
    metric that drops under extraction.

    The detector fires when the target is a refactor, declares a
    verdict-participating `complexity_delta.cyclomatic` constraint whose
    shape rejects every positive observed delta (tolerance included —
    see `_forbids_cyclomatic_increase`), AND the candidate diff grows
    the extractor-visible def count **net across the in-scope diff**
    (the extract-method shape). The net comparison matters because the
    cyclomatic delta is summed over the whole extracted state: a
    refactor that merely relocates a function between files (+1 in one
    file, -1 in another) cancels out and cannot trip the lock, so
    per-file growth alone must not warn (Codex review P2). Growth is a
    heuristic shape signal, not proof — the advisory recommends a
    metric, it never seats the verdict. `None` (inapplicable, git
    unavailable) is filtered out by the caller, mirroring D4 / D6.
    """
    if target.primary_kind is not ChangeKind.REFACTOR:
        return ()
    cyclomatic_locks = tuple(
        c
        for c in target.constraints
        if _is_cyclomatic_leaf_target(c.target)
        and _participates_in_verdict(c)
        and _forbids_cyclomatic_increase(c)
    )
    if not cyclomatic_locks:
        return ()
    net_added = sum(g.candidate_count - g.baseline_count for g in visible_def_growth)
    if net_added <= 0:
        return ()
    grown = tuple(g for g in visible_def_growth if g.candidate_count > g.baseline_count)
    if not grown:
        return ()
    constraint_ids = ", ".join(repr(c.id) for c in cyclomatic_locks)
    return (
        Advisory(
            code="ADVISORY-D7",
            message=(
                f"primary_kind=refactor locks complexity_delta.cyclomatic against "
                f"any increase ({constraint_ids}), and the candidate diff adds "
                f"{net_added} extractor-visible function definition(s) net across "
                f"the in-scope diff — the extract-method shape. The cyclomatic "
                f"delta is summed over functions and each function starts at base "
                f"1, so a faithful extract-method refactor is mathematically "
                f"guaranteed to micro-increase it; this lock can FAIL on exactly "
                f"the refactor it means to endorse. If the intent is 'no "
                f"complexity growth', constrain complexity_delta.cognitive "
                f"instead (it drops under extraction), or widen the cyclomatic "
                f"allowance by the number of extracted helpers."
            ),
            evidence={
                "constraint_ids": [c.id for c in cyclomatic_locks],
                "visible_defs_added": net_added,
                "grown_files_count": len(grown),
                "files": [
                    {
                        "path": g.path,
                        "baseline_visible_defs": g.baseline_count,
                        "candidate_visible_defs": g.candidate_count,
                    }
                    for g in grown[:5]
                ],
            },
        ),
    )


def detect_i1(target: CompiledTarget) -> tuple[Advisory, ...]:
    """Empty intent degrades repair adapter and validate-plan guidance."""
    if target.intent:
        return ()
    return (
        Advisory(
            code="ADVISORY-I1",
            message=(
                "intent is empty; repair adapters and validate-plan produce higher quality "
                "output when intent describes the change purpose. Set intent in target.yaml "
                "or pass --intent to init."
            ),
            evidence={"intent": ""},
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
    package_root_resolved = package_root.resolve()
    for entry in package_root.rglob("*.py"):
        name = entry.name
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
        # Use parts relative to `package_root` so a parent path
        # component named "tests" (e.g. cloning into
        # `/home/user/tests/myrepo/`) doesn't suppress D1.
        try:
            relative = entry.resolve().relative_to(package_root_resolved)
        except ValueError:
            continue
        if "tests" in relative.parts[:-1] or "test" in relative.parts[:-1]:
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

    Three constraint shapes are non-participating:

    - `kind: repair` — `evaluator.evaluator._evaluate_constraint`
      returns SKIPPED (`reason="repair_kind_p1"`) before any
      operator dispatch.
    - `operator: changed_only_in` — same evaluator surface returns
      SKIPPED (`reason="changed_only_in_p1"`).
    - `severity: info` AND `unknown_policy in {ignore, warn}` —
      severity keeps a VIOLATED result out of the verdict (Advisor
      channel, `docs/code_semantic_ci_design.md §23.3`), and the
      unknown_policy variant cannot route the constraint back in via
      the UNKNOWN branch either.

    `severity: info` paired with `unknown_policy in {fail, repair}` IS
    still considered verdict-participating — the constraint is
    Advisor-only on the VIOLATED branch but the non-ignore
    unknown_policy re-arms it on the UNKNOWN branch (open path /
    extraction failure). This is precisely the configuration
    `detect_s1` flags (`docs/brief_resultstatus_planning.md §1b.3`).
    Filtering it out would let D4 emit "vacuous PASS" even when the
    actual verdict can be FAIL via UNKNOWN.
    """
    if constraint.kind is ConstraintKind.REPAIR:
        return False
    if constraint.operator is Operator.CHANGED_ONLY_IN:
        return False
    if constraint.severity is Severity.INFO:
        if constraint.unknown_policy in {UnknownPolicy.FAIL, UnknownPolicy.REPAIR}:
            return True
        return False
    return True


def _is_lock_only_constraint(constraint: CompiledConstraint) -> bool:
    """True if this constraint is vacuously satisfied by an empty
    observed delta (the verdict can PASS without inspecting any
    Python change).

    **Lock-only classification is restricted to `kind: delta`
    constraints.** `kind: state` constraints read the candidate
    `CodeState` directly, not a delta — an empty Python diff leaves
    the candidate state equal to the baseline state, but a
    state-kind constraint like `imports subset_of []` still fails
    whenever the baseline has any imports. target-doctor cannot know
    baseline content, so the conservative choice is to never classify
    state-kind constraints as lock-only (D4 may stay silent in some
    truly-vacuous cases, but it won't emit "vacuous PASS" when the
    actual verdict is FAIL).

    Three observation modes per operator (all gated on
    `kind == DELTA`):

    - Always-lock: lock regardless of `expected` (baseline-aware
      operators + collection-allow-list operators).
    - Collection-dependent (`equals` / `includes_all` / `superset_of`):
      lock when `expected` is an empty collection or a dict whose
      values are all empty collections.
    - Numeric-dependent: scalar numeric `expected` where observed
      value `0` (empty Python diff) satisfies the operator.
    """
    if constraint.kind is not ConstraintKind.DELTA:
        return False
    # Open-path targets (`python_specific.*` / `typescript_specific.*`)
    # resolve to UNKNOWN at evaluate time, which routes through
    # `unknown_policy` (default FAIL). Even on a config-only diff the
    # verdict can be FAIL, so these constraints cannot be classified
    # as lock-only by target-doctor without runtime knowledge.
    if _is_open_path(constraint.target):
        return False

    operator = constraint.operator
    expected = constraint.expected
    target = constraint.target
    # A "leaf" target points at a flat collection or scalar
    # (`effect_changes.added`, `complexity_delta.cyclomatic`,
    # `api_surface_delta.added.fqns`) rather than a whole-delta
    # mapping (`effect_changes`, `imports_delta`). Collection / scalar
    # operators only have well-defined "vacuous on empty observed"
    # semantics on leaves — on whole mappings the evaluator either
    # type-errors or compares against the structured value, so an
    # empty diff does not guarantee a PASS.
    is_leaf = "." in target

    # Baseline-aware operators work on any target shape: on an empty
    # diff the candidate equals the baseline so the comparison is
    # trivially satisfied.
    if operator in {
        Operator.EQUALS_BASELINE,
        Operator.SUPERSET_OF_BASELINE,
        Operator.NO_NEW_ITEMS,
        Operator.NO_REMOVED_ITEMS,
        Operator.UNCHANGED,
    }:
        return True

    # Collection allow-list operators (`subset_of`, `excludes_all`)
    # only make sense on leaf collections. On whole-delta mappings
    # they fail (e.g. `effect_changes subset_of []` — Codex review
    # Round 13).
    if operator in {Operator.EXCLUDES_ALL, Operator.SUBSET_OF}:
        return is_leaf

    # Expected-dependent: collection or scalar.
    if operator in {Operator.EQUALS, Operator.INCLUDES_ALL, Operator.SUPERSET_OF}:
        # Dict-shape `equals {added: (), removed: ()}` is the
        # whole-delta zero shape that template:refactor:effects_unchanged
        # and template:test_update:effects_unchanged emit. Restrict
        # this shortcut to **template-sourced** constraints — the
        # template registry encodes the canonical zero shape for each
        # whole-delta target, so we trust it. User constraints like
        # `equals {}` or `equals {added: []}` are partial dicts that
        # the evaluator compares against the full `{added: (),
        # removed: ()}` shape and VIOLATES; classifying them as
        # lock-only would let D4 falsely claim "vacuous PASS" when
        # the actual verdict is FAIL.
        if (
            operator is Operator.EQUALS
            and constraint.source is ConstraintSource.TEMPLATE
            and isinstance(expected, dict)
            and expected
            and all(_is_empty_collection(value) for value in expected.values())
        ):
            return True
        # Empty-collection `expected` is vacuous only on a leaf.
        if is_leaf and _is_empty_collection(expected):
            return True
        # Scalar `equals 0` on a delta scalar leaf (`complexity_delta.*`).
        if (
            is_leaf
            and operator is Operator.EQUALS
            and _is_scalar_number(expected)
            and expected == 0
        ):
            return True
        return False

    # `not_equals` is inverted and only meaningful on leaves:
    # `not_equals [non-empty]` on a leaf passes when observed is `[]`
    # (lock); `not_equals []` requires non-empty observed (positive).
    # Scalar `not_equals N` on a scalar leaf passes when observed (0)
    # != N (lock iff N != 0).
    if operator is Operator.NOT_EQUALS:
        if not is_leaf:
            return False
        if _is_scalar_number(expected):
            return expected != 0
        return not _is_empty_collection(expected)

    # Scalar comparison operators only have lock semantics on scalar
    # leaves.
    if is_leaf and _is_scalar_number(expected):
        if operator is Operator.LESS_THAN:
            return 0 < expected
        if operator is Operator.LESS_THAN_OR_EQUAL:
            return 0 <= expected
        if operator is Operator.GREATER_THAN:
            return 0 > expected
        if operator is Operator.GREATER_THAN_OR_EQUAL:
            return 0 >= expected

    # `within_range expected: [low, high]` on a scalar leaf is lock
    # when low <= 0 <= high.
    if (
        is_leaf
        and operator is Operator.WITHIN_RANGE
        and isinstance(expected, list | tuple)
        and len(expected) == 2
        and all(_is_scalar_number(item) for item in expected)
    ):
        low, high = expected
        return low <= 0 <= high

    return False


def _is_scalar_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


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


_SEMANTIC_ADDITION_PATH_PREFIXES: tuple[str, ...] = (
    "api_surface_delta.added",
    "test_surface_delta.new_cases",
)
# Open-path target prefixes: the evaluator resolves these to None /
# UNKNOWN by default and routes them through `unknown_policy`. They
# cannot be reasoned about as "lock-only" or "positive addition"
# without a runtime value.
_OPEN_PATH_PREFIXES: tuple[str, ...] = (
    "python_specific",
    "typescript_specific",
)


def _targets_added_dimension(path: str) -> bool:
    """Restrict positive-addition detection to **semantic** addition
    surfaces (API + test surface) as documented in `brief_8_planning
    §6.3.1` ADVISORY-P1 / P2.

    `loc_delta.added` is a numeric line count that a docs/config diff
    can satisfy without adding any API or test case, so it does not
    qualify as a positive addition. `effect_changes.added` and
    `imports_delta.added` are semantic in their own right but they
    don't represent "a feature shipped" — they're orthogonal axes the
    user must opt into separately.
    """
    return any(
        path == prefix or path.startswith(prefix + ".")
        for prefix in _SEMANTIC_ADDITION_PATH_PREFIXES
    )


def _is_open_path(path: str) -> bool:
    head = path.split(".", 1)[0]
    return head in _OPEN_PATH_PREFIXES


def _is_complexity_delta_target(path: str) -> bool:
    """Match `complexity_delta` and any `complexity_delta.<sub>` path.

    Both whole-delta and leaf (`.cyclomatic` / `.cognitive`) targets are
    deceived equally when complexity is displaced into nested functions,
    so D6 scopes on the path head alone.
    """
    head = path.split(".", 1)[0]
    return head == "complexity_delta"


def _is_cyclomatic_leaf_target(path: str) -> bool:
    """Match the `complexity_delta.cyclomatic` scalar leaf only.

    D7 is cyclomatic-specific: cognitive is the recommended alternative
    (it drops under extraction), so cognitive locks are out of scope, and
    whole-mapping `complexity_delta` locks are D6 territory.
    """
    return path == "complexity_delta.cyclomatic"


def _forbids_cyclomatic_increase(constraint: CompiledConstraint) -> bool:
    """True if the constraint shape rejects every positive observed delta.

    Mirrors the evaluator's tolerance semantics
    (`evaluator.operators._numeric_compare` / `_within_range`): `lt` /
    `le` satisfy when observed `<` / `<=` `expected + tolerance`,
    `within_range` widens to `high + tolerance`, and `equals` matches
    exactly with tolerance NOT applied. The observed
    `complexity_delta.cyclomatic` is an integer, so "rejects every
    increase" reduces to "+1 violates" (Codex review P2 — a declared
    `tolerance` that already budgets the extracted helper must not
    warn):

    - `less_than_or_equal N`: N + tolerance < 1
    - `less_than N`: N + tolerance <= 1
    - `equals N`: N <= 0 (tolerance unused by the evaluator)
    - `within_range [low, high]`: high + tolerance < 1

    Shapes that tolerate at least one extracted helper (`<= 3`,
    `<= 0, tolerance: 1`, ...) are not the D7 false-FAIL trap.
    """
    operator = constraint.operator
    expected = constraint.expected
    tolerance = constraint.tolerance or 0.0
    if operator is Operator.LESS_THAN_OR_EQUAL:
        return _is_scalar_number(expected) and expected + tolerance < 1
    if operator is Operator.LESS_THAN:
        return _is_scalar_number(expected) and expected + tolerance <= 1
    if operator is Operator.EQUALS:
        return _is_scalar_number(expected) and expected <= 0
    if (
        operator is Operator.WITHIN_RANGE
        and isinstance(expected, list | tuple)
        and len(expected) == 2
        and all(_is_scalar_number(item) for item in expected)
    ):
        return expected[1] + tolerance < 1
    return False


def _targets_new_test_cases(constraint: CompiledConstraint) -> bool:
    if "test_surface_delta" not in constraint.target:
        return False
    if "new_cases" not in constraint.target and "added" not in constraint.target:
        return False
    return _is_positive_addition(constraint)
