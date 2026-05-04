from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.pipeline import (
    ExtractorError,
    extract_python_code_state,
    extract_python_code_state_from_paths,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "pipeline"
EMPTY_PACKAGE = FIXTURE_ROOT / "empty_package"
SINGLE_MODULE = FIXTURE_ROOT / "single_module"
MULTI_MODULE = FIXTURE_ROOT / "multi_module"
SYNTAX_ERROR = FIXTURE_ROOT / "syntax_error"


def _py_files(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(root.rglob("*.py"), key=lambda path: str(path.resolve())))


def _state_json(state: CodeState) -> str:
    return state.model_dump_json()


def _module_graph_by_name(state: CodeState):
    return {entry.module: entry for entry in state.module_graph}


def test_empty_package_returns_code_state_with_default_fields():
    state = extract_python_code_state(EMPTY_PACKAGE)

    assert isinstance(state, CodeState)
    assert state.api_surface == ()
    assert state.effects == ()
    assert state.imports == ()
    assert state.complexity == ()
    assert state.test_surface == ()
    assert state.module_graph == ()
    assert state.type_relations == ()
    assert state.control_flow == ()
    assert state.data_flow == ()
    assert state.coverage is None
    assert state.python_specific is None
    assert state.typescript_specific is None


def test_single_module_fixture_populates_all_six_extracted_fields():
    state = extract_python_code_state(SINGLE_MODULE)

    assert {entry.fqn for entry in state.api_surface} >= {
        "mod.VALUE",
        "mod.public_api",
        "mod.test_public_api",
    }
    assert {entry.fqn for entry in state.effects} >= {"print"}
    assert any(entry.module == "math" and entry.symbols == ("sqrt",) for entry in state.imports)
    assert {entry.fqn for entry in state.complexity} >= {
        "mod.public_api",
        "mod.test_public_api",
    }
    assert {
        (entry.test_file, entry.test_function, entry.asserts) for entry in state.test_surface
    } == {("mod.py", "test_public_api", 1)}
    assert state.module_graph


def test_whole_package_and_all_paths_variant_are_equivalent():
    whole = extract_python_code_state(MULTI_MODULE)
    from_paths = extract_python_code_state_from_paths(
        _py_files(MULTI_MODULE), package_root=MULTI_MODULE
    )

    assert _state_json(whole) == _state_json(from_paths)


def test_paths_variant_limits_per_file_extractors_but_keeps_whole_repo_module_graph():
    state = extract_python_code_state_from_paths(
        (MULTI_MODULE / "alpha.py",),
        package_root=MULTI_MODULE,
    )
    graph = _module_graph_by_name(state)

    assert {entry.fqn for entry in state.api_surface} == {
        "alpha.ALPHA_VALUE",
        "alpha.alpha",
    }
    assert {entry.fqn for entry in state.complexity} == {"alpha.alpha"}
    assert state.test_surface == ()
    assert {entry.module for entry in state.imports} == {"beta"}
    assert {"multi_module", "alpha", "beta", "gamma"} <= set(graph)
    assert graph["alpha"].imports == ("beta",)
    assert graph["beta"].imports == ("gamma",)


def test_empty_paths_variant_keeps_module_graph_and_empties_per_file_fields():
    state = extract_python_code_state_from_paths((), package_root=MULTI_MODULE)

    assert state.api_surface == ()
    assert state.effects == ()
    assert state.imports == ()
    assert state.complexity == ()
    assert state.test_surface == ()
    assert state.module_graph


def test_paths_variant_is_independent_of_explicit_file_order(tmp_path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    a_path = package_root / "a.py"
    b_path = package_root / "b.py"
    a_path.write_text('def a():\n    print("a")\n', encoding="utf-8")
    b_path.write_text('def b():\n    print("b")\n', encoding="utf-8")

    first = extract_python_code_state_from_paths((a_path, b_path), package_root=package_root)
    second = extract_python_code_state_from_paths((b_path, a_path), package_root=package_root)

    assert _state_json(first) == _state_json(second)


def test_init_only_package_with_api_keeps_module_graph(tmp_path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text(
        "def api():\n    return 1\n",
        encoding="utf-8",
    )

    state = extract_python_code_state(package_root)

    assert {entry.fqn for entry in state.api_surface} == {"pkg.api"}
    assert [entry.module for entry in state.module_graph] == ["pkg"]


def test_syntax_error_is_wrapped_with_extractor_name_and_path():
    with pytest.raises(ExtractorError) as captured:
        extract_python_code_state(SYNTAX_ERROR)

    err = captured.value
    assert err.extractor_name == "api_surface"
    assert err.path is not None
    assert err.path.name == "bad.py"
    assert isinstance(err.__cause__, SyntaxError)
    assert "api_surface" in str(err)
    assert "bad.py" in str(err)


def test_missing_path_fails_fast_with_one_line_error():
    missing = MULTI_MODULE / "missing.py"

    with pytest.raises(ValueError, match="path does not exist"):
        extract_python_code_state_from_paths((missing,), package_root=MULTI_MODULE)


def test_model_dump_json_is_byte_identical_across_two_invocations():
    first = extract_python_code_state(MULTI_MODULE)
    second = extract_python_code_state(MULTI_MODULE)

    assert _state_json(first) == _state_json(second)


def test_model_dump_json_is_byte_identical_across_subprocess_invocations():
    script = f"""
from pathlib import Path
from semantic_ci_code.pipeline import extract_python_code_state
root = Path({json.dumps(str(MULTI_MODULE))})
state = extract_python_code_state(root)
print(state.model_dump_json())
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
