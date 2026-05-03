from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.api_surface import extract_python_api_surface
from semantic_ci_code.complexity import (
    extract_python_complexity,
    extract_python_complexity_from_paths,
)
from semantic_ci_code.domain.state_schema import ComplexityEntry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "complexity"


def _by_fqn(entries: tuple[ComplexityEntry, ...]) -> dict[str, ComplexityEntry]:
    return {entry.fqn: entry for entry in entries}


def _json_payload(entries: tuple[ComplexityEntry, ...]) -> str:
    return "\n".join(entry.model_dump_json() for entry in entries)


def _metric(entry: ComplexityEntry) -> tuple[int | None, int | None]:
    return entry.cyclomatic, entry.cognitive


def test_trivial_function_is_one_cyclomatic_zero_cognitive():
    source = """
def trivial():
    return 1
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.trivial"]

    assert _metric(entry) == (1, 0)


def test_single_if_is_two_cyclomatic_one_cognitive():
    source = """
def single_if(x):
    if x:
        return 1
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.single_if"]

    assert _metric(entry) == (2, 1)


def test_nested_if_applies_cognitive_nesting_bonus():
    source = """
def nested(x, y):
    if x:
        if y:
            return 1
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.nested"]

    assert _metric(entry) == (3, 3)


def test_elif_chain_uses_same_cognitive_nesting_level():
    source = """
def elif_chain(x):
    if x == 1:
        return 1
    elif x == 2:
        return 2
    elif x == 3:
        return 3
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.elif_chain"]

    assert _metric(entry) == (4, 3)


def test_else_body_nested_if_keeps_cognitive_nesting_bonus():
    source = """
def else_nested(x, y):
    if x:
        return 1
    else:
        if y:
            return 2
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.else_nested"]

    assert _metric(entry) == (3, 3)


def test_boolop_three_operands_adds_two_cyclomatic_and_one_cognitive():
    source = """
def boolop(a, b, c):
    if a and b and c:
        return 1
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.boolop"]

    assert _metric(entry) == (4, 2)


def test_ternary_counts_as_one_decision():
    source = """
def ternary(x):
    return 1 if x else 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.ternary"]

    assert _metric(entry) == (2, 1)


def test_two_except_handlers_count_separately():
    source = """
def two_excepts():
    try:
        do()
    except KeyError:
        return 1
    except ValueError:
        return 2
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.two_excepts"]

    assert _metric(entry) == (3, 2)


def test_match_with_three_cases_is_four_cyclomatic():
    source = """
def match_three(x):
    match x:
        case 1: return "a"
        case 2: return "b"
        case _: return "c"
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.match_three"]

    assert _metric(entry) == (4, 3)


def test_comprehension_with_two_if_clauses():
    source = """
def comp(xs):
    return [x for x in xs if x > 0 if x < 10]
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.comp"]

    assert _metric(entry) == (3, 2)


def test_nested_function_body_excluded_from_parent_count():
    source = """
def outer(x):
    if x:
        return 1

    def inner(y):
        if y:
            return 2
    return 0
""".lstrip()

    entries = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))

    assert _metric(entries["pkg.mod.outer"]) == (2, 1)
    assert "pkg.mod.inner" not in entries


def test_assert_contributes_one_cyclomatic_zero_cognitive():
    source = """
def with_assert(x):
    assert x > 0
    return x
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))["pkg.mod.with_assert"]

    assert _metric(entry) == (2, 0)


def test_assert_with_boolop_counts_boolop_for_both_metrics():
    source = """
def assert_boolop(a, b):
    assert a and b
    return a
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.mod"))[
        "pkg.mod.assert_boolop"
    ]

    assert _metric(entry) == (3, 1)


def test_async_function_uses_same_formula():
    source = """
async def fetch(flag):
    if flag:
        return 1
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.async_mod"))[
        "pkg.async_mod.fetch"
    ]

    assert _metric(entry) == (2, 1)


def test_async_method_emits_with_class_qualified_fqn():
    source = """
class Client:
    async def close(self, force):
        if force:
            return 1
        return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.client"))[
        "pkg.client.Client.close"
    ]

    assert _metric(entry) == (2, 1)


def test_decorator_expression_is_not_walked():
    source = """
@auth.require(perm_a or perm_b or perm_c)
def decorated():
    return 1
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.decorators"))[
        "pkg.decorators.decorated"
    ]

    assert _metric(entry) == (1, 0)


def test_default_argument_expression_is_not_walked():
    source = """
def defaults(value=left or middle or right):
    return value
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.defaults"))[
        "pkg.defaults.defaults"
    ]

    assert _metric(entry) == (1, 0)


def test_annotation_expression_is_not_walked():
    source = """
def annotated(value: A | B) -> C | D:
    return value
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.annotations"))[
        "pkg.annotations.annotated"
    ]

    assert _metric(entry) == (1, 0)


def test_walrus_does_not_inflate_count():
    source = """
def walrus():
    if (value := load()) > 0:
        return value
    return 0
""".lstrip()

    entry = _by_fqn(extract_python_complexity(source, module_fqn="pkg.walrus"))["pkg.walrus.walrus"]

    assert _metric(entry) == (2, 1)


def test_methods_in_nested_class_are_not_emitted():
    source = """
class Outer:
    class Inner:
        def method(self):
            if True:
                return 1
""".lstrip()

    entries = _by_fqn(extract_python_complexity(source, module_fqn="pkg.nested"))

    assert "pkg.nested.Outer.Inner.method" not in entries
    assert entries == {}


def test_lambda_is_not_emitted():
    source = """
handler = lambda x: 1 if x else 0
""".lstrip()

    assert extract_python_complexity(source, module_fqn="pkg.lambda_mod") == ()


def test_module_level_code_is_not_emitted():
    source = """
if enabled:
    value = 1
else:
    value = 0
""".lstrip()

    assert extract_python_complexity(source, module_fqn="pkg.module_code") == ()


def test_empty_function_forms_are_one_cyclomatic_zero_cognitive():
    source = """
def pass_func():
    pass

def ellipsis_func():
    ...
""".lstrip()

    entries = _by_fqn(extract_python_complexity(source, module_fqn="pkg.empty_funcs"))

    assert _metric(entries["pkg.empty_funcs.pass_func"]) == (1, 0)
    assert _metric(entries["pkg.empty_funcs.ellipsis_func"]) == (1, 0)


def test_output_is_sorted_by_fqn():
    source = """
def zed():
    pass

def alpha():
    pass

class Beta:
    def method(self):
        pass
""".lstrip()

    entries = extract_python_complexity(source, module_fqn="pkg.sort")

    assert [entry.fqn for entry in entries] == [
        "pkg.sort.Beta.method",
        "pkg.sort.alpha",
        "pkg.sort.zed",
    ]


def test_duplicate_symbol_entries_keep_first_definition():
    source = """
if TYPE_CHECKING:
    def parse(x):
        if x:
            return 1
        return 0
else:
    def parse(x, y):
        if x:
            if y:
                return 1
        return 0
""".lstrip()

    entries = extract_python_complexity(source, module_fqn="pkg.conditional")

    assert [entry.fqn for entry in entries] == ["pkg.conditional.parse"]
    assert _metric(entries[0]) == (2, 1)


def test_repeated_path_inputs_are_deduped_by_fqn():
    entries = extract_python_complexity_from_paths(
        [FIXTURE_ROOT / "simple.py", FIXTURE_ROOT / "simple.py"],
        package_root=FIXTURE_ROOT,
    )

    fqns = [entry.fqn for entry in entries]

    assert fqns.count("simple.fixture_func") == 1
    assert fqns.count("simple.FixtureClass.method") == 1


def test_output_is_deterministic_across_subprocess_invocations():
    source = """
def zed(flag):
    if flag:
        return 1
    return 0

def alpha(a, b, c):
    if a and b and c:
        return 1
    return 0
""".lstrip()

    first = extract_python_complexity(source, module_fqn="pkg.det")
    second = extract_python_complexity(source, module_fqn="pkg.det")

    assert _json_payload(first) == _json_payload(second)

    script = f"""
from semantic_ci_code.complexity import extract_python_complexity
source = {json.dumps(source)}
entries = extract_python_complexity(source, module_fqn="pkg.det")
print("\\n".join(entry.model_dump_json() for entry in entries))
"""
    env = os.environ.copy()
    src_path = str(PROJECT_ROOT / "src")
    env["PYTHONPATH"] = (
        src_path if not env.get("PYTHONPATH") else os.pathsep.join((src_path, env["PYTHONPATH"]))
    )
    run1 = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )
    run2 = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        env=env,
        text=True,
    )

    assert run1.stdout == run2.stdout
    assert run1.stdout.strip() == _json_payload(first)


def test_module_fqn_derivation_matches_api_surface_helper():
    source = """
def public():
    return 1

class Service:
    def run(self):
        return 1
""".lstrip()

    complexity_fqns = {
        entry.fqn for entry in extract_python_complexity(source, module_fqn="pkg.service")
    }
    api_fqns = {
        entry.fqn
        for entry in extract_python_api_surface(source, module_fqn="pkg.service")
        if entry.kind in {"function", "async_function", "method", "async_method"}
    }

    assert complexity_fqns == api_fqns


def test_path_extraction_with_package_root():
    entries = extract_python_complexity_from_paths(
        [
            FIXTURE_ROOT / "simple.py",
            FIXTURE_ROOT / "pkg",
        ],
        package_root=FIXTURE_ROOT,
    )
    by_fqn = _by_fqn(entries)

    assert _metric(by_fqn["simple.fixture_func"]) == (1, 0)
    assert _metric(by_fqn["simple.FixtureClass.method"]) == (2, 1)
    assert _metric(by_fqn["pkg.package_func"]) == (1, 0)
    assert _metric(by_fqn["pkg.submodule.fetch"]) == (2, 1)
    assert _metric(by_fqn["pkg.submodule.Client.close"]) == (2, 1)
    assert "pkg.nested.Outer.Inner.method" not in by_fqn


def test_directory_path_expands_to_python_files():
    entries = extract_python_complexity_from_paths([FIXTURE_ROOT], package_root=FIXTURE_ROOT)

    assert "pkg.submodule.fetch" in {entry.fqn for entry in entries}


def test_path_extraction_rejects_files_outside_package_root(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("def f():\n    return 1\n", encoding="utf-8")

    with pytest.raises(ValueError):
        extract_python_complexity_from_paths([outside], package_root=FIXTURE_ROOT)


def test_syntax_error_propagates():
    with pytest.raises(SyntaxError):
        extract_python_complexity("def broken(:\n", module_fqn="pkg.bad", filename="bad.py")


def test_empty_file_returns_empty_tuple():
    assert extract_python_complexity("", module_fqn="pkg.empty") == ()
    assert extract_python_complexity("# comment only\n", module_fqn="pkg.comments") == ()
    assert extract_python_complexity('"""docstring only"""\n', module_fqn="pkg.docstring") == ()


def test_module_docstring_contains_cyclomatic_formula():
    import semantic_ci_code.complexity.python_complexity_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "Cyclomatic formula:" in doc
    assert "Start at 1. Walk the function body." in doc
    assert "| ``ast.BoolOp`` (``and`` / ``or``) | +(N-1)" in doc
    assert "``ast.comprehension.ifs`` | +1 per ``if`` clause" in doc


def test_module_docstring_contains_cognitive_formula():
    import semantic_ci_code.complexity.python_complexity_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "Cognitive formula:" in doc
    assert "Start at 0 with ``nesting = 0``." in doc
    assert "cognitive += ``(1 + nesting)``" in doc
    assert "conservative approximation of SonarSource cognitive complexity" in doc


def test_docstring_contains_stdlib_over_radon_lizard_rationale():
    import semantic_ci_code.complexity.python_complexity_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "stdlib ``ast`` instead of ``radon`` or" in doc
    assert "``lizard``" in doc
    assert "zero dependencies" in doc
    assert "deterministic output" in doc
    assert "full control over the formula" in doc
    assert "FQN model" in doc


def test_extractor_has_no_forbidden_runtime_imports():
    source = (
        PROJECT_ROOT / "src" / "semantic_ci_code" / "complexity" / "python_complexity_extractor.py"
    )
    module_source = source.read_text(encoding="utf-8")
    forbidden = ("radon", "lizard", "griffe", "requests", "httpx", "subprocess", "socket")

    for name in forbidden:
        assert f"import {name}" not in module_source
        assert f"from {name}" not in module_source


def test_project_dependencies_are_unchanged():
    import tomllib

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["dependencies"] == [
        "pydantic>=2.0",
        "PyYAML>=6.0",
    ]
