"""Producer-spec contract tests for ``authoring.canonical``.

Each test case is derived from the producer-side spec documented in
``src/semantic_ci_code/authoring/canonical.py`` — extractor / evaluator
output shapes the predicates MUST accept, plus near-miss shapes the
predicates MUST reject. Adding a new canonical form here without updating
the producer (or vice versa) should make the relevant test fail
explicitly.
"""

from __future__ import annotations

import pytest

from semantic_ci_code.authoring.canonical import (
    is_canonical_fqn,
    is_canonical_fqn_prefix,
    is_canonical_test_id,
)


@pytest.mark.parametrize(
    "value",
    [
        "pkg.symbol",
        "pkg.module.symbol",
        "pkg.module.Class.method",
        "a.b",
        "_private.helper",
        "pkg.module._private",
    ],
)
def test_canonical_fqn_accepts_extractor_emitted_shapes(value: str) -> None:
    assert is_canonical_fqn(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "pkg",
        ".pkg.symbol",
        "pkg.symbol.",
        "pkg..symbol",
        "pkg.module::symbol",
        "pkg.module symbol",
        "pkg.0bad",
        "pkg.module.",
    ],
)
def test_canonical_fqn_rejects_extractor_never_emits(value: str) -> None:
    assert not is_canonical_fqn(value)


@pytest.mark.parametrize(
    "value",
    [
        "pkg.",
        "pkg.legacy.",
        "pkg.module.sub.",
        "_private.",
    ],
)
def test_canonical_fqn_prefix_accepts_evaluator_allowlist_inputs(value: str) -> None:
    assert is_canonical_fqn_prefix(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "pkg",
        "pkg.legacy",
        "pkg..",
        ".pkg.",
        "pkg::legacy.",
        "pkg.0bad.",
        ".",
    ],
)
def test_canonical_fqn_prefix_rejects_evaluator_unsafe_inputs(value: str) -> None:
    assert not is_canonical_fqn_prefix(value)


def test_canonical_fqn_prefix_rejects_bare_segment_that_would_match_sibling() -> None:
    # The trailing `.` requirement guards against the evaluator's
    # `fqn.startswith("legacy")` accidentally matching `legacy2.Foo`.
    assert not is_canonical_fqn_prefix("legacy")
    assert is_canonical_fqn_prefix("legacy.")


@pytest.mark.parametrize(
    "value",
    [
        "tests/test_x.py::test_y",
        "tests/test_x.py::TestClass::test_method",
        "tests/subdir/test_x.py::test_y",
        "tests/test_x.py::test_y_with_underscore",
        "tests/test_x.py::TestSomething::test_case",
    ],
)
def test_canonical_test_id_accepts_extractor_emitted_shapes(value: str) -> None:
    assert is_canonical_test_id(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "tests/test_x.py",
        "tests/test_x::test_y",  # missing .py
        "/tests/test_x.py::test_y",  # absolute path
        "tests\\test_x.py::test_y",  # backslash separator
        "tests/./test_x.py::test_y",  # `.` segment
        "tests/../test_x.py::test_y",  # `..` segment
        "tests//test_x.py::test_y",  # empty segment
        "tests/test_x.py::test_y::extra::levels",  # >2 name parts
        "tests/test_x.py::helper",  # non-test_ prefix
        "tests/test_x.py::TestClass::helper",  # nested non-test_ method
        "tests/test_x.py::lowercase::test_method",  # nested non-Test class
        "tests/test_x.py::test y",  # space in name
        "tests/test x.py::test_y",  # space in path
        "tests/test_x.py::test_y[param]",  # parametrize bracket
    ],
)
def test_canonical_test_id_rejects_extractor_never_emits(value: str) -> None:
    assert not is_canonical_test_id(value)
