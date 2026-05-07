from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.imports import (
    extract_python_imports,
    extract_python_imports_from_paths,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "imports"


def _entry_tuples(entries):
    return [(entry.module, entry.from_, entry.symbols) for entry in entries]


def _json_payload(entries) -> str:
    return "\n".join(entry.model_dump_json() for entry in entries)


def test_plain_import():
    entries = extract_python_imports("import os\n")

    assert _entry_tuples(entries) == [("os", None, ())]


def test_dotted_import():
    entries = extract_python_imports("import urllib.request\n")

    assert _entry_tuples(entries) == [("urllib.request", None, ())]


def test_aliased_import_loses_alias():
    entries = extract_python_imports("import numpy as np\n")

    assert _entry_tuples(entries) == [("numpy", None, ())]


def test_dotted_aliased_import_loses_alias():
    entries = extract_python_imports("import a.b as c\n")

    assert _entry_tuples(entries) == [("a.b", None, ())]


def test_multi_target_import_emits_one_entry_per_module():
    entries = extract_python_imports("import a, b\n")

    assert _entry_tuples(entries) == [("a", None, ()), ("b", None, ())]


def test_from_import_single_symbol():
    entries = extract_python_imports("from os import path\n")

    assert _entry_tuples(entries) == [("os", None, ("path",))]


def test_from_import_multiple_symbols_sorted():
    entries = extract_python_imports("from os import sep, path\n")

    assert _entry_tuples(entries) == [("os", None, ("path", "sep"))]


def test_from_import_with_alias_keeps_original_name():
    entries = extract_python_imports("from os import path as p\n")

    assert _entry_tuples(entries) == [("os", None, ("path",))]


def test_from_dotted_module_import():
    entries = extract_python_imports("from x.y import z\n")

    assert _entry_tuples(entries) == [("x.y", None, ("z",))]


def test_relative_import_no_module():
    entries = extract_python_imports("from . import sibling\n")

    assert _entry_tuples(entries) == [("", ".", ("sibling",))]


def test_relative_import_no_module_with_alias_loses_alias():
    entries = extract_python_imports("from . import sibling as local_sibling\n")

    assert _entry_tuples(entries) == [("", ".", ("sibling",))]


def test_relative_import_with_module():
    entries = extract_python_imports("from .pkg import x\n")

    assert _entry_tuples(entries) == [("pkg", ".", ("x",))]


def test_double_dot_relative_import():
    entries = extract_python_imports("from ..pkg.sub import y, x\n")

    assert _entry_tuples(entries) == [("pkg.sub", "..", ("x", "y"))]


def test_star_import():
    entries = extract_python_imports("from x import *\n")

    assert _entry_tuples(entries) == [("x", None, ("*",))]


def test_relative_star_import():
    entries = extract_python_imports("from . import *\n")

    assert _entry_tuples(entries) == [("", ".", ("*",))]


def test_future_import_is_emitted_normally():
    entries = extract_python_imports("from __future__ import annotations\n")

    assert _entry_tuples(entries) == [("__future__", None, ("annotations",))]


def test_parenthesized_from_import_is_treated_normally():
    source = """
from os import (
    sep,
    path,
)
""".lstrip()

    entries = extract_python_imports(source)

    assert _entry_tuples(entries) == [("os", None, ("path", "sep"))]


def test_semicolon_imports_emit_each_statement():
    entries = extract_python_imports("import a; import b\n")

    assert _entry_tuples(entries) == [("a", None, ()), ("b", None, ())]


def test_type_checking_block_imports_are_emitted():
    source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import typing_extensions as te
    from . import protocols
""".lstrip()

    entries = extract_python_imports(source)

    assert _entry_tuples(entries) == [
        ("typing", None, ("TYPE_CHECKING",)),
        ("typing_extensions", None, ()),
        ("", ".", ("protocols",)),
    ]


def test_try_except_importerror_emits_both_branches():
    source = """
try:
    import cPickle as pickle
except ImportError:
    import pickle
""".lstrip()

    entries = extract_python_imports(source)

    assert _entry_tuples(entries) == [("cPickle", None, ()), ("pickle", None, ())]


def test_function_local_imports_are_not_emitted():
    source = """
def load():
    import os
    from sys import path
""".lstrip()

    assert extract_python_imports(source) == ()


def test_class_body_imports_are_not_emitted():
    source = """
class Loader:
    import os
    from sys import path
""".lstrip()

    assert extract_python_imports(source) == ()


def test_output_is_sorted_absolute_before_relative():
    source = """
from . import sibling
import zlib
from os import sep, path
from ..pkg import x
import a
""".lstrip()

    entries = extract_python_imports(source)

    assert _entry_tuples(entries) == [
        ("a", None, ()),
        ("os", None, ("path", "sep")),
        ("zlib", None, ()),
        ("", ".", ("sibling",)),
        ("pkg", "..", ("x",)),
    ]


def test_identical_entries_are_deduped_but_distinct_symbol_groups_remain():
    source = """
import os
import os
from pkg import a
from pkg import a
from pkg import b
""".lstrip()

    entries = extract_python_imports(source)

    assert _entry_tuples(entries) == [
        ("os", None, ()),
        ("pkg", None, ("a",)),
        ("pkg", None, ("b",)),
    ]


def test_output_is_deterministic_across_subprocess_invocations():
    source = """
from . import sibling
import zlib
from os import sep, path
import a
""".lstrip()

    first = extract_python_imports(source)
    second = extract_python_imports(source)

    assert _json_payload(first) == _json_payload(second)

    script = f"""
from semantic_ci_code.imports import extract_python_imports
source = {json.dumps(source)}
entries = extract_python_imports(source)
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


def test_directory_path_extraction_uses_package_root():
    entries = extract_python_imports_from_paths(
        [FIXTURE_ROOT / "root.py", FIXTURE_ROOT / "pkg"],
        package_root=FIXTURE_ROOT,
    )

    assert _entry_tuples(entries) == [
        ("cPickle", None, ()),
        ("os", None, ()),
        ("package", None, ("alpha", "beta")),
        ("pickle", None, ()),
        ("urllib.request", None, ()),
        ("", ".", ("sibling",)),
        ("pkg.sub", "..", ("x", "y")),
    ]


def test_path_extraction_rejects_files_outside_package_root(tmp_path):
    outside = tmp_path / "outside.py"
    outside.write_text("import os\n", encoding="utf-8")

    with pytest.raises(ValueError):
        extract_python_imports_from_paths([outside], package_root=FIXTURE_ROOT)


def test_syntax_error_propagates():
    with pytest.raises(SyntaxError):
        extract_python_imports("import .x\n", filename="bad.py")


def test_empty_file_returns_empty_tuple():
    assert extract_python_imports("") == ()
    assert extract_python_imports("# comment only\n") == ()
    assert extract_python_imports('"""docstring only"""\n') == ()


def test_extractor_has_no_forbidden_runtime_imports():
    source = PROJECT_ROOT / "src" / "semantic_ci_code" / "imports" / "python_imports_extractor.py"
    module_source = source.read_text(encoding="utf-8")
    forbidden = ("griffe", "requests", "httpx", "subprocess", "socket")

    for name in forbidden:
        assert f"import {name}" not in module_source
        assert f"from {name}" not in module_source


def test_project_dependencies_are_unchanged():
    import tomllib

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["dependencies"] == [
        "pydantic>=2.0,<3.0",
        "PyYAML>=6.0,<7.0",
    ]
