from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.domain.state_schema import TestSurfaceEntry as SurfaceEntry
from semantic_ci_code.test_surface import (
    extract_python_test_surface,
    extract_python_test_surface_from_paths,
)

# Fixture files under tests/fixtures/test_surface contain test_* functions
# intentionally. Their filenames must stay sample_*.py so project pytest does
# not collect them as real tests.

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "test_surface"


def _by_function(entries: tuple[SurfaceEntry, ...]) -> dict[str, SurfaceEntry]:
    return {entry.test_function: entry for entry in entries}


def _entry_tuple(entry: SurfaceEntry) -> tuple[str, str, int | None, int | None]:
    return entry.test_file, entry.test_function, entry.asserts, entry.parametrize_count


def _json_payload(entries: tuple[SurfaceEntry, ...]) -> str:
    return "\n".join(entry.model_dump_json() for entry in entries)


def test_trivial_test_function_one_assert_no_parametrize():
    source = """
def test_trivial():
    assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert _entry_tuple(entry) == ("sample.py", "test_trivial", 1, None)


def test_multiple_asserts_counted():
    source = """
def test_multi():
    assert a
    assert b
    assert c
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.asserts == 3


def test_parametrize_single_decorator_counts_cases():
    source = """
@pytest.mark.parametrize("x", [1, 2, 3])
def test_param(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert _entry_tuple(entry) == ("sample.py", "test_param", 1, 3)


def test_stacked_parametrize_multiplies_case_counts():
    source = """
@pytest.mark.parametrize("x", [1, 2])
@pytest.mark.parametrize("y", [10, 20, 30])
def test_stacked(x, y):
    assert x + y
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count == 6


def test_parametrize_with_tuple_cases_counts_one_per_tuple():
    source = """
@pytest.mark.parametrize("a,b", [(1, 2), (3, 4)])
def test_tuple_cases(a, b):
    assert a + b
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count == 2


def test_dynamic_argvalues_yields_none_parametrize_count():
    source = """
CASES = [1, 2, 3]
@pytest.mark.parametrize("x", CASES)
def test_dynamic(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count is None


def test_parametrize_empty_list_yields_zero_count():
    source = """
@pytest.mark.parametrize("x", [])
def test_empty(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count == 0


def test_class_style_test_method_uses_double_colon_format():
    source = """
class TestKlass:
    def test_method(self):
        assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert _entry_tuple(entry) == ("sample.py", "TestKlass::test_method", 1, None)


def test_assert_in_nested_helper_not_counted_in_outer():
    source = """
def test_nested_helper():
    def helper():
        assert False
    assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.asserts == 1


def test_non_test_named_function_not_emitted():
    source = """
def helper():
    assert True
""".lstrip()

    assert extract_python_test_surface(source, test_file="sample.py") == ()


def test_test_named_method_in_non_test_class_not_emitted():
    source = """
class HelperClass:
    def test_should_not_be_emitted(self):
        assert True
""".lstrip()

    assert extract_python_test_surface(source, test_file="sample.py") == ()


def test_non_test_method_in_test_class_not_emitted():
    source = """
class TestKlass:
    def helper(self):
        assert True
""".lstrip()

    assert extract_python_test_surface(source, test_file="sample.py") == ()


def test_nested_test_function_not_emitted():
    source = """
def test_outer():
    def test_inner():
        assert False
    assert True
""".lstrip()

    entries = extract_python_test_surface(source, test_file="sample.py")

    assert [entry.test_function for entry in entries] == ["test_outer"]


def test_nested_test_class_not_emitted():
    source = """
class TestOuter:
    class TestInner:
        def test_method(self):
            assert False
""".lstrip()

    assert extract_python_test_surface(source, test_file="sample.py") == ()


def test_async_test_function_emitted():
    source = """
async def test_async():
    assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert _entry_tuple(entry) == ("sample.py", "test_async", 1, None)


def test_async_test_method_emitted():
    source = """
class TestAsync:
    async def test_method(self):
        assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert _entry_tuple(entry) == ("sample.py", "TestAsync::test_method", 1, None)


def test_bare_parametrize_import_recognized():
    source = """
from pytest.mark import parametrize

@parametrize("x", [1, 2])
def test_bare(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count == 2


def test_mark_parametrize_attribute_recognized():
    source = """
@mark.parametrize("x", [1, 2])
def test_mark(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count == 2


def test_parametrize_keyword_argvalues_recognized():
    source = """
@pytest.mark.parametrize("x", argvalues=[1, 2])
def test_keyword(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count == 2


def test_parametrize_missing_argvalues_yields_none():
    source = """
@parametrize([1, 2])
def test_wrong_api(x):
    assert x
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count is None


def test_non_parametrize_decorators_are_ignored():
    source = """
@pytest.mark.skip
@fixture
def test_skip_marker():
    assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.parametrize_count is None


def test_unittest_assertEqual_not_counted_as_assert():
    source = """
class TestCase(unittest.TestCase):
    def test_equal(self):
        self.assertEqual(1, 1)
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.asserts == 0


def test_pytest_raises_with_block_not_counted_as_assert():
    source = """
def test_raises():
    with pytest.raises(ValueError):
        int("x")
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.asserts == 0


def test_assert_with_message_counts_as_one():
    source = """
def test_message():
    assert value, "message"
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.asserts == 1


def test_test_class_with_init_still_emits_in_p1():
    source = """
class TestWithInit:
    def __init__(self):
        self.value = 1

    def test_method(self):
        assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.test_function == "TestWithInit::test_method"


def test_testdata_class_with_test_method_emits_lexically():
    source = """
class TestData:
    def test_payload(self):
        assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.test_function == "TestData::test_payload"


def test_walrus_and_unpacking_do_not_affect_assert_count():
    source = """
def test_body():
    (a, b) = (1, 2)
    if (value := a + b):
        pass
    assert value
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.asserts == 1


def test_module_scope_compound_definitions_are_emitted():
    source = """
if TYPE_CHECKING:
    def test_type_only():
        assert True
""".lstrip()

    entry = extract_python_test_surface(source, test_file="sample.py")[0]

    assert entry.test_function == "test_type_only"


def test_duplicate_test_functions_keep_first_entry():
    source = """
def test_duplicate():
    assert True

def test_duplicate():
    assert True
    assert True
""".lstrip()

    entries = extract_python_test_surface(source, test_file="sample.py")

    assert len(entries) == 1
    assert entries[0].asserts == 1


def test_path_extraction_uses_posix_relative_test_file():
    entries = extract_python_test_surface_from_paths(
        [FIXTURE_ROOT / "sample_module_tests.py"],
        package_root=FIXTURE_ROOT,
    )
    by_function = _by_function(entries)

    assert by_function["test_fixture_one"].test_file == "sample_module_tests.py"
    assert by_function["test_fixture_multi"].asserts == 2


def test_directory_path_expands_to_python_files():
    entries = extract_python_test_surface_from_paths([FIXTURE_ROOT], package_root=FIXTURE_ROOT)
    functions = {entry.test_function for entry in entries}

    assert "test_fixture_one" in functions
    assert "TestFixture::test_method" in functions
    assert "test_param" in functions
    assert "test_async_fixture" in functions


def test_path_extraction_rejects_files_outside_package_root(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("def test_outside():\n    assert True\n", encoding="utf-8")

    with pytest.raises(ValueError):
        extract_python_test_surface_from_paths([outside], package_root=FIXTURE_ROOT)


def test_output_is_sorted_by_test_file_then_test_function():
    entries = extract_python_test_surface_from_paths(
        [
            FIXTURE_ROOT / "sample_param_tests.py",
            FIXTURE_ROOT / "sample_module_tests.py",
        ],
        package_root=FIXTURE_ROOT,
    )

    assert [(entry.test_file, entry.test_function) for entry in entries] == sorted(
        (entry.test_file, entry.test_function) for entry in entries
    )


def test_output_is_deterministic_across_subprocess_invocations():
    source = """
@pytest.mark.parametrize("x", [1, 2])
def test_zed(x):
    assert x

def test_alpha():
    assert True
""".lstrip()

    first = extract_python_test_surface(source, test_file="sample.py")
    second = extract_python_test_surface(source, test_file="sample.py")

    assert _json_payload(first) == _json_payload(second)

    script = f"""
from semantic_ci_code.test_surface import extract_python_test_surface
source = {json.dumps(source)}
entries = extract_python_test_surface(source, test_file="sample.py")
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


def test_syntax_error_propagates():
    with pytest.raises(SyntaxError):
        extract_python_test_surface("def broken(:\n", test_file="bad.py", filename="bad.py")


def test_empty_file_returns_empty_tuple():
    assert extract_python_test_surface("", test_file="empty.py") == ()
    assert extract_python_test_surface("# comment only\n", test_file="comments.py") == ()
    assert extract_python_test_surface('"""docstring only"""\n', test_file="docstring.py") == ()


def test_file_with_no_tests_returns_empty_tuple():
    assert extract_python_test_surface("value = 1\n", test_file="sample.py") == ()


def test_module_docstring_contains_collection_rules():
    import semantic_ci_code.test_surface.python_test_surface_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "Collection rules:" in doc
    assert "Pytest-name-convention static recognition" in doc
    assert "Module-level ``def test_<name>(...)``" in doc
    assert "``class Test<X>`` with an ``__init__`` method | emit anyway in P1" in doc


def test_module_docstring_contains_asserts_rule():
    import semantic_ci_code.test_surface.python_test_surface_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "Asserts rule:" in doc
    assert "Count ``ast.Assert`` nodes inside the test function body." in doc
    assert "set ``asserts = 0``" in doc
    assert "unittest.TestCase.assertEqual" in doc


def test_module_docstring_contains_parametrize_rule():
    import semantic_ci_code.test_surface.python_test_surface_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "Parametrize count rule:" in doc
    assert "final ``attr`` is" in doc
    assert '``"parametrize"``' in doc
    assert "multiplication (cartesian product" in doc


def test_module_docstring_contains_stdlib_over_pytest_rationale():
    import semantic_ci_code.test_surface.python_test_surface_extractor as extractor

    doc = extractor.__doc__ or ""

    assert "stdlib ``ast`` instead of ``pytest --collect-only``" in doc
    assert "zero dependencies" in doc
    assert "deterministic output" in doc
    assert "no import side effects" in doc
    assert "no subprocess" in doc


def test_extractor_has_no_forbidden_runtime_imports():
    source = (
        PROJECT_ROOT
        / "src"
        / "semantic_ci_code"
        / "test_surface"
        / "python_test_surface_extractor.py"
    )
    module_source = source.read_text(encoding="utf-8")
    forbidden = ("pytest", "radon", "lizard", "griffe", "requests", "httpx", "subprocess", "socket")
    tree = ast.parse(module_source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module.split(".", maxsplit=1)[0])

    for name in forbidden:
        assert name not in imported_modules


def test_project_dependencies_are_unchanged():
    import tomllib

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["dependencies"] == [
        "pydantic>=2.0",
        "PyYAML>=6.0",
    ]


def test_fixture_files_are_not_collected_as_real_tests():
    forbidden = list(FIXTURE_ROOT.glob("test_*.py")) + list(FIXTURE_ROOT.glob("*_test.py"))

    assert forbidden == []
