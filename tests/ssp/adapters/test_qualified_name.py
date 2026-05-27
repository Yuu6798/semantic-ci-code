from __future__ import annotations

from pathlib import Path

from semantic_ci_code.ssp.adapters.qualified_name import qualified_name_for_line


def _write_source(tmp_path: Path) -> Path:
    source = tmp_path / "pkg" / "sample.py"
    source.parent.mkdir()
    source.write_text(
        "\n".join(
            [
                "VALUE = 1",
                "",
                "def route(func):",
                "    return func",
                "",
                "def top_level():",
                "    return VALUE",
                "",
                "class Service:",
                "    def method(self):",
                "        return VALUE",
                "",
                "def outer():",
                "    def inner():",
                "        return VALUE",
                "    return inner()",
                "",
                "async def fetch():",
                "    return VALUE",
                "",
                "@route",
                "def decorated():",
                "    return VALUE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return source


def test_qualified_name_for_function_level_finding(tmp_path: Path):
    source = _write_source(tmp_path)

    assert qualified_name_for_line(source, repo_root=tmp_path, line=7) == "pkg.sample.top_level"


def test_qualified_name_for_class_method_finding(tmp_path: Path):
    source = _write_source(tmp_path)

    assert (
        qualified_name_for_line(source, repo_root=tmp_path, line=11) == "pkg.sample.Service.method"
    )


def test_qualified_name_for_module_level_finding(tmp_path: Path):
    source = _write_source(tmp_path)

    assert qualified_name_for_line(source, repo_root=tmp_path, line=1) == "pkg.sample"


def test_qualified_name_for_nested_function_finding(tmp_path: Path):
    source = _write_source(tmp_path)

    assert qualified_name_for_line(source, repo_root=tmp_path, line=15) == "pkg.sample.outer.inner"


def test_qualified_name_for_async_function_finding(tmp_path: Path):
    source = _write_source(tmp_path)

    assert qualified_name_for_line(source, repo_root=tmp_path, line=19) == "pkg.sample.fetch"


def test_qualified_name_for_decorator_line_finding(tmp_path: Path):
    source = _write_source(tmp_path)

    assert qualified_name_for_line(source, repo_root=tmp_path, line=21) == "pkg.sample.decorated"
