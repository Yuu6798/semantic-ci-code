from __future__ import annotations

from pathlib import Path

from semantic_ci_code.framework.extract_config import ExcludedPath, ExtractConfig
from semantic_ci_code.pipeline import extract_python_code_state


def test_extract_config_filters_files_before_ast_parse(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "good.py").write_text(
        "import os\n\ndef api():\n    print(os.name)\n    return 1\n",
        encoding="utf-8",
    )
    broken = package_root / "fixtures" / "syntax_error" / "bad.py"
    broken.parent.mkdir(parents=True)
    broken.write_text("def broken(:\n", encoding="utf-8")
    config = ExtractConfig(
        patterns=("fixtures/syntax_error",),
        config_root=package_root,
        source_path=package_root / "pyproject.toml",
    )
    reports: list[tuple[ExcludedPath, ...]] = []

    state = extract_python_code_state(
        package_root,
        extract_config=config,
        exclude_reporter=reports.append,
    )

    assert {entry.fqn for entry in state.api_surface} >= {"good.api"}
    assert {entry.fqn for entry in state.effects} == {"good.api"}
    assert {entry.module for entry in state.imports} == {"os"}
    assert {entry.fqn for entry in state.complexity} == {"good.api"}
    assert {entry.module for entry in state.module_graph} == {"pkg", "good"}
    assert len(reports) == 1
    assert [item.relative_path.as_posix() for item in reports[0]] == [
        "fixtures/syntax_error/bad.py"
    ]
    assert reports[0][0].pattern == "fixtures/syntax_error"
