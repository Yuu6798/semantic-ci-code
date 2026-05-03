from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.domain.state_schema import ModuleGraphEntry
from semantic_ci_code.imports import extract_python_imports
from semantic_ci_code.module_graph import extract_python_module_graph

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "module_graph"
SAMPLE_PKG_ROOT = FIXTURE_ROOT / "sample_pkg"


def _by_module(entries: tuple[ModuleGraphEntry, ...]) -> dict[str, ModuleGraphEntry]:
    return {entry.module: entry for entry in entries}


def _json_payload(entries: tuple[ModuleGraphEntry, ...]) -> str:
    return "\n".join(entry.model_dump_json() for entry in entries)


def _write(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_empty_package_root_returns_empty_tuple(tmp_path):
    assert extract_python_module_graph(tmp_path) == ()


def test_single_init_only_package_returns_one_entry_with_empty_edges(tmp_path):
    package_root = tmp_path / "only_pkg"
    _write(package_root / "__init__.py", "")

    entries = extract_python_module_graph(package_root)

    assert entries == (ModuleGraphEntry(module="only_pkg"),)


def test_two_modules_with_one_resolved_internal_import(tmp_path):
    _write(tmp_path / "a.py", "import b\n")
    _write(tmp_path / "b.py", "")

    entries = _by_module(extract_python_module_graph(tmp_path))

    assert entries["a"].imports == ("b",)
    assert entries["b"].imported_by == ("a",)


def test_external_import_produces_no_edge():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert "os" not in entries["sample_pkg.foo"].imports


def test_absolute_from_x_import_y_resolves_to_submodule_when_y_is_module():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert entries["sample_pkg.utils"].imports == ("sample_pkg", "sample_pkg.foo")


def test_absolute_from_x_import_y_resolves_to_x_when_y_is_name():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert entries["sample_pkg.scripts.standalone"].imports == ("sample_pkg.utils",)


def test_relative_from_dot_import_y_resolves_to_sibling_module():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert entries["sample_pkg.foo"].imports == (
        "sample_pkg",
        "sample_pkg.bar",
        "sample_pkg.bar.baz",
    )


def test_relative_from_dot_import_y_resolves_to_parent_when_sibling_missing(tmp_path):
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "foo.py", "from . import missing\n")

    entries = _by_module(extract_python_module_graph(tmp_path))

    assert entries["pkg.foo"].imports == ("pkg",)


def test_double_dot_relative_import_resolves(tmp_path):
    _write(tmp_path / "pkg" / "__init__.py", "")
    _write(tmp_path / "pkg" / "util.py", "")
    _write(tmp_path / "pkg" / "sub" / "foo.py", "from .. import util\n")

    entries = _by_module(extract_python_module_graph(tmp_path))

    assert entries["pkg.sub.foo"].imports == ("pkg", "pkg.util")


def test_relative_import_escaping_package_root_produces_no_edge():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert entries["sample_pkg.bar.baz"].imports == ()


def test_top_level_relative_import_produces_no_edge(tmp_path):
    _write(tmp_path / "a.py", "from . import b\n")
    _write(tmp_path / "b.py", "")

    entries = _by_module(extract_python_module_graph(tmp_path))

    assert entries["a"].imports == ()
    assert entries["b"].imported_by == ()


def test_star_import_produces_only_source_module_edge():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert entries["sample_pkg.star_user"].imports == ("sample_pkg",)


def test_init_py_module_name_drops_init_suffix():
    entries = extract_python_module_graph(FIXTURE_ROOT)
    modules = {entry.module for entry in entries}

    assert "sample_pkg" in modules
    assert "sample_pkg.__init__" not in modules
    assert "sample_pkg.bar" in modules
    assert "sample_pkg.bar.__init__" not in modules


def test_imported_by_is_exact_transpose_of_imports():
    entries = extract_python_module_graph(FIXTURE_ROOT)
    by_module = _by_module(entries)

    expected_imported_by = {
        module: tuple(sorted(entry.module for entry in entries if module in entry.imports))
        for module in by_module
    }

    assert {
        module: entry.imported_by for module, entry in by_module.items()
    } == expected_imported_by


def test_circular_imports_keep_both_edges():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert entries["sample_pkg.cycle_a"].imports == ("sample_pkg.cycle_b",)
    assert entries["sample_pkg.cycle_b"].imports == ("sample_pkg.cycle_a",)
    assert entries["sample_pkg.cycle_a"].imported_by == ("sample_pkg.cycle_b",)
    assert entries["sample_pkg.cycle_b"].imported_by == ("sample_pkg.cycle_a",)


def test_self_edges_are_suppressed():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert "sample_pkg" not in entries["sample_pkg"].imports
    assert entries["sample_pkg"].imports == (
        "sample_pkg.bar",
        "sample_pkg.bar.baz",
        "sample_pkg.foo",
    )


def test_each_entry_imports_and_imported_by_are_sorted_ascending():
    entries = extract_python_module_graph(FIXTURE_ROOT)

    for entry in entries:
        assert entry.imports == tuple(sorted(entry.imports))
        assert entry.imported_by == tuple(sorted(entry.imported_by))


def test_output_is_sorted_by_module_name():
    entries = extract_python_module_graph(FIXTURE_ROOT)

    assert [entry.module for entry in entries] == sorted(entry.module for entry in entries)


def test_output_is_deterministic_across_subprocess_invocations():
    first = extract_python_module_graph(FIXTURE_ROOT)
    second = extract_python_module_graph(FIXTURE_ROOT)

    assert _json_payload(first) == _json_payload(second)

    script = f"""
from pathlib import Path
from semantic_ci_code.module_graph import extract_python_module_graph
root = Path({json.dumps(str(FIXTURE_ROOT))})
entries = extract_python_module_graph(root)
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


def test_extractor_reuses_extract_python_imports():
    extractor_source = (
        PROJECT_ROOT
        / "src"
        / "semantic_ci_code"
        / "module_graph"
        / "python_module_graph_extractor.py"
    ).read_text(encoding="utf-8")
    assert "extract_python_imports" in extractor_source

    foo_source = (SAMPLE_PKG_ROOT / "foo.py").read_text(encoding="utf-8")
    import_entries = extract_python_imports(foo_source, filename=str(SAMPLE_PKG_ROOT / "foo.py"))
    assert any(entry.module == "bar" and entry.from_ == "." for entry in import_entries)

    graph = _by_module(extract_python_module_graph(FIXTURE_ROOT))
    assert "sample_pkg.bar" in graph["sample_pkg.foo"].imports


def test_function_local_imports_contribute_no_edges(tmp_path):
    _write(tmp_path / "a.py", "def load():\n    import b\n")
    _write(tmp_path / "b.py", "")

    entries = _by_module(extract_python_module_graph(tmp_path))

    assert entries["a"].imports == ()
    assert entries["b"].imported_by == ()


def test_scripts_directory_without_init_is_still_discovered():
    entries = _by_module(extract_python_module_graph(FIXTURE_ROOT))

    assert "sample_pkg.scripts.standalone" in entries
    assert entries["sample_pkg.scripts.standalone"].imports == ("sample_pkg.utils",)


def test_syntax_error_propagates(tmp_path):
    _write(tmp_path / "bad.py", "def broken(:\n")

    with pytest.raises(SyntaxError):
        extract_python_module_graph(tmp_path)


def test_extractor_has_no_forbidden_runtime_imports():
    source = (
        PROJECT_ROOT
        / "src"
        / "semantic_ci_code"
        / "module_graph"
        / "python_module_graph_extractor.py"
    )
    module_source = source.read_text(encoding="utf-8")
    forbidden = ("griffe", "requests", "httpx", "subprocess", "socket")

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
