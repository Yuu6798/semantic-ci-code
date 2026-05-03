from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from semantic_ci_code.api_surface import (
    extract_python_api_surface,
    extract_python_api_surface_from_paths,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "api_surface"


def _by_fqn(entries):
    return {entry.fqn: entry for entry in entries}


def _json_payload(entries) -> str:
    return "\n".join(entry.model_dump_json() for entry in entries)


def test_extracts_top_level_function_signature():
    source = """
def add(a: int, b: int = 1) -> int:
    return a + b
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.mod")

    entry = _by_fqn(entries)["pkg.mod.add"]
    assert entry.kind == "function"
    assert entry.signature == "def add(a: int, b: int=1) -> int:\n    ..."
    assert entry.visibility == "public"


def test_extracts_async_function_with_async_prefix():
    source = """
async def fetch(url: str) -> bytes:
    return b""
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.net")

    entry = _by_fqn(entries)["pkg.net.fetch"]
    assert entry.kind == "async_function"
    assert entry.signature == "async def fetch(url: str) -> bytes:\n    ..."


def test_extracts_class_with_bases_in_signature():
    source = """
class Service(Base, metaclass=Meta):
    pass
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.service")

    entry = _by_fqn(entries)["pkg.service.Service"]
    assert entry.kind == "class"
    assert entry.signature == "class Service(Base, metaclass=Meta):\n    ..."


def test_extracts_method_and_async_method_with_classname_in_fqn():
    source = """
class Client:
    def send(self, payload: bytes) -> None:
        pass

    async def close(self) -> None:
        pass
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.client")
    by_fqn = _by_fqn(entries)

    assert by_fqn["pkg.client.Client.send"].kind == "method"
    assert by_fqn["pkg.client.Client.send"].signature == (
        "def send(self, payload: bytes) -> None:\n    ..."
    )
    assert by_fqn["pkg.client.Client.close"].kind == "async_method"
    assert by_fqn["pkg.client.Client.close"].signature == "async def close(self) -> None:\n    ..."


def test_extracts_all_caps_constant_with_no_signature():
    source = """
MAX_RETRIES = 3
not_a_constant = 4
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.settings")

    assert [entry.fqn for entry in entries] == ["pkg.settings.MAX_RETRIES"]
    assert entries[0].kind == "constant"
    assert entries[0].signature is None


def test_visibility_public_private_dunder():
    source = """
def public() -> None:
    pass

def _private() -> None:
    pass

class Klass:
    def __repr__(self) -> str:
        return "Klass()"

    def _hidden(self) -> None:
        pass
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.visibility")
    by_fqn = _by_fqn(entries)

    assert by_fqn["pkg.visibility.public"].visibility == "public"
    assert by_fqn["pkg.visibility._private"].visibility == "private"
    assert by_fqn["pkg.visibility.Klass.__repr__"].visibility == "dunder"
    assert by_fqn["pkg.visibility.Klass._hidden"].visibility == "private"


def test_skips_nested_function_and_nested_class():
    source = """
def outer() -> None:
    def inner() -> None:
        pass

    class Inner:
        pass

class Outer:
    class Nested:
        def method(self) -> None:
            pass
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.nested")
    fqns = {entry.fqn for entry in entries}

    assert "pkg.nested.outer" in fqns
    assert "pkg.nested.Outer" in fqns
    assert "pkg.nested.outer.inner" not in fqns
    assert "pkg.nested.Inner" not in fqns
    assert "pkg.nested.Outer.Nested" not in fqns
    assert "pkg.nested.Outer.Nested.method" not in fqns


def test_decorated_function_preserves_decorators_in_signature():
    source = """
@decorator(arg=1)
def decorated(x: int) -> int:
    return x
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.decorators")

    assert _by_fqn(entries)["pkg.decorators.decorated"].signature == (
        "@decorator(arg=1)\ndef decorated(x: int) -> int:\n    ..."
    )


def test_overload_stubs_each_emit_one_entry():
    source = """
from typing import overload

@overload
def parse(value: int) -> int: ...

@overload
def parse(value: str) -> str: ...

def parse(value):
    return value
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.overloads")
    parse_entries = [entry for entry in entries if entry.fqn == "pkg.overloads.parse"]

    assert len(parse_entries) == 3
    signatures = {entry.signature for entry in parse_entries}
    assert "@overload\ndef parse(value: int) -> int:\n    ..." in signatures
    assert "@overload\ndef parse(value: str) -> str:\n    ..." in signatures
    assert "def parse(value):\n    ..." in signatures


def test_output_is_sorted_and_deterministic_across_invocations():
    source = """
def zed() -> None:
    pass

VALUE = 1

def alpha() -> None:
    pass
""".lstrip()

    first = extract_python_api_surface(source, module_fqn="pkg.det")
    second = extract_python_api_surface(source, module_fqn="pkg.det")

    assert [entry.fqn for entry in first] == [
        "pkg.det.VALUE",
        "pkg.det.alpha",
        "pkg.det.zed",
    ]
    assert _json_payload(first) == _json_payload(second)

    script = f"""
from semantic_ci_code.api_surface import extract_python_api_surface
source = {json.dumps(source)}
entries = extract_python_api_surface(source, module_fqn="pkg.det")
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


def test_module_fqn_derivation_from_package_root():
    entries = extract_python_api_surface_from_paths(
        [
            FIXTURE_ROOT / "simple.py",
            FIXTURE_ROOT / "pkg" / "__init__.py",
            FIXTURE_ROOT / "pkg" / "submodule.py",
        ],
        package_root=FIXTURE_ROOT,
    )
    fqns = {entry.fqn for entry in entries}

    assert "simple.fixture_func" in fqns
    assert "simple.TOP_LEVEL_CONSTANT" in fqns
    assert "pkg.PackageClass" in fqns
    assert "pkg.PackageClass.build" in fqns
    assert "pkg.submodule.SubmoduleClass" in fqns
    assert "pkg.submodule.SubmoduleClass.load" in fqns
    assert all(".__init__." not in fqn for fqn in fqns)


def test_directory_path_expands_to_python_files():
    entries = extract_python_api_surface_from_paths([FIXTURE_ROOT], package_root=FIXTURE_ROOT)

    assert "pkg.submodule.SubmoduleClass" in {entry.fqn for entry in entries}


def test_syntax_error_propagates():
    with pytest.raises(SyntaxError):
        extract_python_api_surface("def broken(:\n", module_fqn="pkg.bad", filename="bad.py")


def test_empty_file_returns_empty_tuple():
    assert extract_python_api_surface("", module_fqn="pkg.empty") == ()
    assert extract_python_api_surface("# comment only\n", module_fqn="pkg.comments") == ()


def test_type_checking_block_definitions_are_emitted():
    source = """
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    def typed_only(value: str) -> str:
        return value
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.types")

    assert _by_fqn(entries)["pkg.types.typed_only"].kind == "function"


def test_conditionally_defined_symbols_are_emitted():
    source = """
if sys.version_info >= (3, 12):
    class Versioned:
        def available(self) -> bool:
            return True
""".lstrip()

    entries = extract_python_api_surface(source, module_fqn="pkg.conditional")
    fqns = {entry.fqn for entry in entries}

    assert "pkg.conditional.Versioned" in fqns
    assert "pkg.conditional.Versioned.available" in fqns


def test_extractor_has_no_forbidden_runtime_imports():
    source = PROJECT_ROOT / "src" / "semantic_ci_code" / "api_surface" / "python_api_extractor.py"
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
