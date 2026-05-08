from __future__ import annotations

from pathlib import Path

from semantic_ci_code.framework.extract_config import ExtractConfig
from semantic_ci_code.module_graph import extract_python_module_graph


def test_excluded_module_is_removed_from_nodes_and_edges(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "a.py").write_text("import b\n", encoding="utf-8")
    (package_root / "b.py").write_text("VALUE = 1\n", encoding="utf-8")
    config = ExtractConfig(
        patterns=("b.py",),
        config_root=package_root,
        source_path=package_root / "pyproject.toml",
    )

    graph = extract_python_module_graph(package_root, extract_config=config)

    by_module = {entry.module: entry for entry in graph}
    assert set(by_module) == {"pkg", "a"}
    assert by_module["a"].imports == ()
    assert "b" not in {imported for entry in graph for imported in entry.imports}
