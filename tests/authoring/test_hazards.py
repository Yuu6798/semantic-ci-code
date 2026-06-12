from __future__ import annotations

from pathlib import Path

from semantic_ci_code.authoring.hazards import detect_advisories
from semantic_ci_code.authoring.nested_defs import NestedDefGrowth
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
