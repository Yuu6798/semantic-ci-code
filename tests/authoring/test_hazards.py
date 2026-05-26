from __future__ import annotations

from pathlib import Path

from semantic_ci_code.authoring.hazards import detect_advisories
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
