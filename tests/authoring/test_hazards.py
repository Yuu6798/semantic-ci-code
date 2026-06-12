from __future__ import annotations

from pathlib import Path

from semantic_ci_code.authoring.hazards import detect_advisories
from semantic_ci_code.authoring.nested_defs import NestedDefGrowth, VisibleDefGrowth
from semantic_ci_code.compiler.target_compiler import compile_target_svp


def _compile_target(yaml_text: str):
    return compile_target_svp(yaml_text, filename="<test-target>")


def test_detect_i1_empty_intent_fires():
    target = _compile_target('intent: ""\nchange:\n  primary_kind: refactor\nconstraints: []\n')

    advisories = detect_advisories(target)
    i1 = [advisory for advisory in advisories if advisory.code == "ADVISORY-I1"]

    assert len(i1) == 1
    assert "pass --intent to init" in i1[0].message
    assert i1[0].evidence == {"intent": ""}


def test_detect_i1_nonempty_intent_silent():
    target = _compile_target(
        "intent: add endpoint\nchange:\n  primary_kind: refactor\nconstraints: []\n"
    )

    advisories = detect_advisories(target)

    assert "ADVISORY-I1" not in [advisory.code for advisory in advisories]


def test_detect_i1_whitespace_only_is_not_empty():
    target = _compile_target('intent: "   "\nchange:\n  primary_kind: refactor\nconstraints: []\n')

    advisories = detect_advisories(target)

    assert "ADVISORY-I1" not in [advisory.code for advisory in advisories]


def test_advisory_order_i1_between_d4_and_p1():
    target = _compile_target('intent: ""\nchange:\n  primary_kind: feature\nconstraints: []\n')

    advisories = detect_advisories(target, files_touched=(Path("README.md"),))
    codes = [advisory.code for advisory in advisories]

    assert "ADVISORY-D4" in codes
    assert "ADVISORY-I1" in codes
    assert "ADVISORY-P1" in codes
    assert codes.index("ADVISORY-D4") < codes.index("ADVISORY-I1") < codes.index("ADVISORY-P1")


# ---------------------------------------------------------------------------
# ADVISORY-D6 — complexity constraint + nested-def growth = displacement
# ---------------------------------------------------------------------------

_COMPLEXITY_TARGET = (
    "intent: simplify hot path\n"
    "change:\n"
    "  primary_kind: refactor\n"
    "constraints:\n"
    "  - id: cc_lock\n"
    "    kind: delta\n"
    "    target: complexity_delta.cyclomatic\n"
    "    operator: less_than_or_equal\n"
    "    expected: 0\n"
)


def _growth(path: str = "src/mod.py", baseline: int = 0, candidate: int = 2) -> NestedDefGrowth:
    return NestedDefGrowth(path=path, baseline_count=baseline, candidate_count=candidate)


def test_detect_d6_fires_on_complexity_constraint_with_growth():
    target = _compile_target(_COMPLEXITY_TARGET)

    advisories = detect_advisories(target, nested_def_growth=(_growth(),))
    d6 = [advisory for advisory in advisories if advisory.code == "ADVISORY-D6"]

    assert len(d6) == 1
    assert "nested" in d6[0].message
    assert d6[0].evidence["constraint_ids"] == ["cc_lock"]
    assert d6[0].evidence["nested_defs_added"] == 2
    assert d6[0].evidence["grown_files_count"] == 1
    assert d6[0].evidence["files"] == [
        {"path": "src/mod.py", "baseline_nested_defs": 0, "candidate_nested_defs": 2}
    ]


def test_detect_d6_fires_on_cognitive_leaf_and_whole_mapping():
    yaml_text = (
        "intent: simplify\n"
        "change:\n"
        "  primary_kind: refactor\n"
        "constraints:\n"
        "  - id: cognitive_lock\n"
        "    kind: delta\n"
        "    target: complexity_delta.cognitive\n"
        "    operator: less_than_or_equal\n"
        "    expected: 0\n"
    )
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, nested_def_growth=(_growth(),))
    d6 = [advisory for advisory in advisories if advisory.code == "ADVISORY-D6"]

    assert len(d6) == 1
    assert d6[0].evidence["constraint_ids"] == ["cognitive_lock"]


def test_detect_d6_silent_without_complexity_constraint():
    target = _compile_target(
        "intent: refactor\nchange:\n  primary_kind: refactor\nconstraints: []\n"
    )

    advisories = detect_advisories(target, nested_def_growth=(_growth(),))

    assert "ADVISORY-D6" not in [advisory.code for advisory in advisories]


def test_detect_d6_silent_without_growth():
    target = _compile_target(_COMPLEXITY_TARGET)

    advisories = detect_advisories(
        target,
        nested_def_growth=(
            _growth(baseline=2, candidate=2),
            _growth(path="src/other.py", baseline=3, candidate=1),
        ),
    )

    assert "ADVISORY-D6" not in [advisory.code for advisory in advisories]


def test_detect_d6_silent_on_empty_growth_tuple():
    target = _compile_target(_COMPLEXITY_TARGET)

    advisories = detect_advisories(target, nested_def_growth=())

    assert "ADVISORY-D6" not in [advisory.code for advisory in advisories]


def test_detect_d6_skipped_when_context_is_none():
    target = _compile_target(_COMPLEXITY_TARGET)

    advisories = detect_advisories(target, nested_def_growth=None)

    assert "ADVISORY-D6" not in [advisory.code for advisory in advisories]


def test_detect_d6_ignores_non_verdict_participating_constraint():
    yaml_text = (
        "intent: simplify\n"
        "change:\n"
        "  primary_kind: refactor\n"
        "constraints:\n"
        "  - id: cc_info\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        "    operator: less_than_or_equal\n"
        "    expected: 0\n"
        "    severity: info\n"
        "    unknown_policy: ignore\n"
    )
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, nested_def_growth=(_growth(),))

    assert "ADVISORY-D6" not in [advisory.code for advisory in advisories]


def test_detect_d6_evidence_truncates_files_to_five():
    target = _compile_target(_COMPLEXITY_TARGET)
    growth = tuple(_growth(path=f"src/mod_{i}.py") for i in range(7))

    advisories = detect_advisories(target, nested_def_growth=growth)
    d6 = [advisory for advisory in advisories if advisory.code == "ADVISORY-D6"]

    assert len(d6) == 1
    assert d6[0].evidence["grown_files_count"] == 7
    assert d6[0].evidence["nested_defs_added"] == 14
    assert len(d6[0].evidence["files"]) == 5


def test_advisory_order_d6_between_d4_and_i1():
    yaml_text = (
        'intent: ""\n'
        "change:\n"
        "  primary_kind: refactor\n"
        "constraints:\n"
        "  - id: cc_lock\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        "    operator: less_than_or_equal\n"
        "    expected: 0\n"
    )
    target = _compile_target(yaml_text)

    advisories = detect_advisories(
        target,
        files_touched=(Path("README.md"),),
        nested_def_growth=(_growth(),),
    )
    codes = [advisory.code for advisory in advisories]

    assert "ADVISORY-D4" in codes
    assert "ADVISORY-D6" in codes
    assert "ADVISORY-I1" in codes
    assert codes.index("ADVISORY-D4") < codes.index("ADVISORY-D6") < codes.index("ADVISORY-I1")


# ---------------------------------------------------------------------------
# ADVISORY-D7 — refactor + cyclomatic no-increase lock + extract-method shape
# ---------------------------------------------------------------------------


def _cyclomatic_refactor_target(operator: str = "less_than_or_equal", expected: str = "0") -> str:
    return (
        "intent: extract helpers\n"
        "change:\n"
        "  primary_kind: refactor\n"
        "constraints:\n"
        "  - id: cc_no_increase\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        f"    operator: {operator}\n"
        f"    expected: {expected}\n"
    )


def _visible_growth(
    path: str = "src/mod.py", baseline: int = 1, candidate: int = 3
) -> VisibleDefGrowth:
    return VisibleDefGrowth(path=path, baseline_count=baseline, candidate_count=candidate)


def test_detect_d7_fires_on_refactor_cyclomatic_lock_with_extraction():
    target = _compile_target(_cyclomatic_refactor_target())

    advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))
    d7 = [advisory for advisory in advisories if advisory.code == "ADVISORY-D7"]

    assert len(d7) == 1
    assert "cognitive" in d7[0].message
    assert d7[0].evidence["constraint_ids"] == ["cc_no_increase"]
    assert d7[0].evidence["visible_defs_added"] == 2
    assert d7[0].evidence["files"] == [
        {"path": "src/mod.py", "baseline_visible_defs": 1, "candidate_visible_defs": 3}
    ]


def test_detect_d7_fires_on_equals_zero_and_within_range_shapes():
    for operator, expected in (("equals", "0"), ("within_range", "[-5, 0]"), ("less_than", "1")):
        target = _compile_target(_cyclomatic_refactor_target(operator, expected))
        advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))
        codes = [advisory.code for advisory in advisories]
        assert "ADVISORY-D7" in codes, f"{operator} {expected} should fire"


def test_detect_d7_silent_when_allowance_tolerates_increase():
    for operator, expected in (("less_than_or_equal", "3"), ("within_range", "[-5, 2]")):
        target = _compile_target(_cyclomatic_refactor_target(operator, expected))
        advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))
        assert "ADVISORY-D7" not in [advisory.code for advisory in advisories], (
            f"{operator} {expected} should stay silent"
        )


def test_detect_d7_silent_for_non_refactor_kind():
    yaml_text = _cyclomatic_refactor_target().replace(
        "primary_kind: refactor", "primary_kind: feature"
    )
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))

    assert "ADVISORY-D7" not in [advisory.code for advisory in advisories]


def test_detect_d7_silent_for_cognitive_target():
    yaml_text = _cyclomatic_refactor_target().replace(
        "complexity_delta.cyclomatic", "complexity_delta.cognitive"
    )
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))

    assert "ADVISORY-D7" not in [advisory.code for advisory in advisories]


def test_detect_d7_silent_without_visible_growth():
    target = _compile_target(_cyclomatic_refactor_target())

    advisories = detect_advisories(
        target,
        visible_def_growth=(
            _visible_growth(baseline=3, candidate=3),
            _visible_growth(path="src/other.py", baseline=4, candidate=2),
        ),
    )

    assert "ADVISORY-D7" not in [advisory.code for advisory in advisories]


def test_detect_d7_skipped_when_context_is_none():
    target = _compile_target(_cyclomatic_refactor_target())

    advisories = detect_advisories(target, visible_def_growth=None)

    assert "ADVISORY-D7" not in [advisory.code for advisory in advisories]


def test_detect_d7_ignores_non_verdict_participating_constraint():
    yaml_text = _cyclomatic_refactor_target() + "    severity: info\n    unknown_policy: ignore\n"
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))

    assert "ADVISORY-D7" not in [advisory.code for advisory in advisories]


def test_advisory_order_d7_between_d6_and_i1():
    yaml_text = (
        'intent: ""\n'
        "change:\n"
        "  primary_kind: refactor\n"
        "constraints:\n"
        "  - id: cc_no_increase\n"
        "    kind: delta\n"
        "    target: complexity_delta.cyclomatic\n"
        "    operator: less_than_or_equal\n"
        "    expected: 0\n"
    )
    target = _compile_target(yaml_text)

    advisories = detect_advisories(
        target,
        nested_def_growth=(_growth(),),
        visible_def_growth=(_visible_growth(),),
    )
    codes = [advisory.code for advisory in advisories]

    assert "ADVISORY-D6" in codes
    assert "ADVISORY-D7" in codes
    assert "ADVISORY-I1" in codes
    assert codes.index("ADVISORY-D6") < codes.index("ADVISORY-D7") < codes.index("ADVISORY-I1")


def test_detect_d7_silent_on_net_zero_relocation():
    """Codex review P2: relocating a function between files (+1 / -1)
    cancels in the summed cyclomatic delta — the lock can still pass, so
    per-file growth alone must not warn."""
    target = _compile_target(_cyclomatic_refactor_target())

    advisories = detect_advisories(
        target,
        visible_def_growth=(
            _visible_growth(path="src/dst.py", baseline=1, candidate=2),
            _visible_growth(path="src/src.py", baseline=2, candidate=1),
        ),
    )

    assert "ADVISORY-D7" not in [advisory.code for advisory in advisories]


def test_detect_d7_reports_net_growth_with_partial_shrinkage():
    target = _compile_target(_cyclomatic_refactor_target())

    advisories = detect_advisories(
        target,
        visible_def_growth=(
            _visible_growth(path="src/dst.py", baseline=1, candidate=3),
            _visible_growth(path="src/src.py", baseline=2, candidate=1),
        ),
    )
    d7 = [advisory for advisory in advisories if advisory.code == "ADVISORY-D7"]

    assert len(d7) == 1
    assert d7[0].evidence["visible_defs_added"] == 1
    assert d7[0].evidence["files"] == [
        {"path": "src/dst.py", "baseline_visible_defs": 1, "candidate_visible_defs": 3}
    ]


def test_detect_d7_silent_when_tolerance_budgets_the_increase():
    """Codex review P2: the evaluator applies `tolerance` to numeric
    comparisons (`<= 0, tolerance: 1` allows +1), so a target that
    already budgets the extracted helper must not warn."""
    for operator, expected, tolerance in (
        ("less_than_or_equal", "0", "1"),
        ("within_range", "[-5, 0]", "1"),
        ("less_than", "1", "0.5"),
    ):
        yaml_text = (
            _cyclomatic_refactor_target(operator, expected) + f"    tolerance: {tolerance}\n"
        )
        target = _compile_target(yaml_text)
        advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))
        assert "ADVISORY-D7" not in [advisory.code for advisory in advisories], (
            f"{operator} {expected} tolerance={tolerance} should stay silent"
        )


def test_detect_d7_fires_when_tolerance_does_not_reach_plus_one():
    yaml_text = _cyclomatic_refactor_target() + "    tolerance: 0.5\n"
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))

    assert "ADVISORY-D7" in [advisory.code for advisory in advisories]


def test_detect_d7_equals_ignores_tolerance():
    # The evaluator's EQUALS dispatch never applies tolerance, so
    # `equals 0, tolerance: 1` still rejects every increase.
    yaml_text = _cyclomatic_refactor_target("equals", "0") + "    tolerance: 1\n"
    target = _compile_target(yaml_text)

    advisories = detect_advisories(target, visible_def_growth=(_visible_growth(),))

    assert "ADVISORY-D7" in [advisory.code for advisory in advisories]
