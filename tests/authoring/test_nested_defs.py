from __future__ import annotations

from semantic_ci_code.authoring.nested_defs import NestedDefGrowth, count_nested_defs


def test_module_level_defs_are_not_nested():
    source = "def foo(): return 1\n\nasync def bar(): return 2\n"
    assert count_nested_defs(source) == 0


def test_methods_of_module_level_class_are_not_nested():
    source = "class A:\n    def method(self): return 1\n"
    assert count_nested_defs(source) == 0


def test_def_inside_function_counts():
    source = "def outer():\n    def helper(): return 1\n    return helper()\n"
    assert count_nested_defs(source) == 1


def test_async_def_inside_function_counts():
    source = "def outer():\n    async def helper(): return 1\n    return helper\n"
    assert count_nested_defs(source) == 1


def test_deeply_nested_defs_count_each_level():
    source = (
        "def outer():\n"
        "    def middle():\n"
        "        def inner(): return 1\n"
        "        return inner()\n"
        "    return middle()\n"
    )
    assert count_nested_defs(source) == 2


def test_method_of_class_inside_function_counts():
    # Neither the class nor its method is extractor-visible
    # (api_surface parity: only module-level classes' direct methods).
    source = (
        "def outer():\n"
        "    class Local:\n"
        "        def method(self): return 1\n"
        "    return Local\n"
    )
    assert count_nested_defs(source) == 1


def test_def_inside_method_counts():
    source = (
        "class A:\n"
        "    def method(self):\n"
        "        def helper(): return 1\n"
        "        return helper()\n"
    )
    assert count_nested_defs(source) == 1


def test_lambda_does_not_count():
    source = "def outer():\n    return lambda x: x + 1\n"
    assert count_nested_defs(source) == 0


def test_def_inside_module_scope_compound_statement_is_not_nested():
    # The extractor emits defs inside module-scope compound statements
    # (e.g. `if TYPE_CHECKING:`), so they are not displacement targets.
    source = "if True:\n    def foo(): return 1\n"
    assert count_nested_defs(source) == 0


def test_syntax_error_returns_none():
    assert count_nested_defs("def broken(:\n") is None


def test_empty_source_counts_zero():
    assert count_nested_defs("") == 0


def test_growth_record_is_frozen_and_comparable():
    growth = NestedDefGrowth(path="src/mod.py", baseline_count=0, candidate_count=2)
    assert growth.candidate_count > growth.baseline_count
