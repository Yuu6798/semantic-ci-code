from __future__ import annotations

from pathlib import Path

import pytest

from semantic_ci_code.framework.extract_config import (
    ExtractConfig,
    ExtractConfigError,
    load_extract_config,
    matches_exclude,
)


def _write_pyproject(root: Path, body: str) -> None:
    (root / "pyproject.toml").write_text(body, encoding="utf-8")


def test_load_extract_config_searches_upward_from_package_root(tmp_path: Path):
    package_root = tmp_path / "src" / "pkg"
    package_root.mkdir(parents=True)
    _write_pyproject(
        tmp_path,
        """
[tool.semantic_ci_code.extract]
exclude = ["generated", "**/*_pb2.py"]
""".strip(),
    )

    config = load_extract_config(package_root)

    assert config.patterns == ("generated", "**/*_pb2.py")
    assert config.config_root == tmp_path.resolve()
    assert config.source_path == (tmp_path / "pyproject.toml").resolve()


def test_load_extract_config_respects_search_boundary(tmp_path: Path):
    tree_root = tmp_path / "tree"
    package_root = tree_root / "src" / "pkg"
    package_root.mkdir(parents=True)
    _write_pyproject(
        tmp_path,
        """
[tool.semantic_ci_code.extract]
exclude = ["outside"]
""".strip(),
    )

    config = load_extract_config(package_root, search_boundary=tree_root)

    assert config.patterns == ()
    assert config.source_path is None
    assert config.config_root == package_root.resolve()


def test_load_extract_config_finds_pyproject_at_search_boundary(tmp_path: Path):
    tree_root = tmp_path / "tree"
    package_root = tree_root / "src" / "pkg"
    package_root.mkdir(parents=True)
    _write_pyproject(
        tree_root,
        """
[tool.semantic_ci_code.extract]
exclude = ["src/generated"]
""".strip(),
    )

    config = load_extract_config(package_root, search_boundary=tree_root)

    assert config.patterns == ("src/generated",)
    assert config.source_path == (tree_root / "pyproject.toml").resolve()


def test_missing_extract_section_is_empty_config(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    _write_pyproject(tmp_path, "[tool.semantic_ci_code.cache]\nmax = 1\n")

    config = load_extract_config(package_root)

    assert config.patterns == ()
    assert config.source_path == (tmp_path / "pyproject.toml").resolve()


def test_unknown_extract_key_is_rejected(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    _write_pyproject(
        tmp_path,
        """
[tool.semantic_ci_code.extract]
exlude = ["broken"]
""".strip(),
    )

    with pytest.raises(ExtractConfigError, match="unknown .*exlude"):
        load_extract_config(package_root)


@pytest.mark.parametrize(
    ("pattern", "message"),
    [
        ("", "empty pattern"),
        ("/abs/foo", "absolute"),
        ("../outside", "parent traversal"),
        ("tests\\fixtures", "backslashes"),
    ],
)
def test_invalid_patterns_are_rejected(tmp_path: Path, pattern: str, message: str):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    _write_pyproject(
        tmp_path,
        f"""
[tool.semantic_ci_code.extract]
exclude = [{pattern!r}]
""".strip(),
    )

    with pytest.raises(ExtractConfigError, match=message):
        load_extract_config(package_root)


def test_non_string_pattern_is_rejected(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    _write_pyproject(
        tmp_path,
        """
[tool.semantic_ci_code.extract]
exclude = [123]
""".strip(),
    )

    with pytest.raises(ExtractConfigError, match="expected string"):
        load_extract_config(package_root)


def test_matches_exclude_uses_config_root_relative_paths(tmp_path: Path):
    config = ExtractConfig(
        patterns=(
            "tests/fixtures/syntax_error",
            "examples/broken/**",
            "**/*_pb2.py",
            "src/pkg/*.gen.py",
        ),
        config_root=tmp_path,
        source_path=tmp_path / "pyproject.toml",
    )

    cases = {
        "tests/fixtures/syntax_error/bad.py": "tests/fixtures/syntax_error",
        "examples/broken/deep/bad.py": "examples/broken/**",
        "src/pkg/nested/foo_pb2.py": "**/*_pb2.py",
        "src/pkg/model.gen.py": "src/pkg/*.gen.py",
    }
    for raw_path, expected_pattern in cases.items():
        path = tmp_path / raw_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        assert matches_exclude(path, config) == expected_pattern

    nested = tmp_path / "src" / "pkg" / "nested" / "model.gen.py"
    nested.parent.mkdir(parents=True, exist_ok=True)
    nested.write_text("", encoding="utf-8")
    assert matches_exclude(nested, config) is None


def test_candidate_outside_config_root_is_not_excluded(tmp_path: Path):
    config = ExtractConfig(
        patterns=("**/*.py",),
        config_root=tmp_path / "repo",
        source_path=tmp_path / "repo" / "pyproject.toml",
    )
    outside = tmp_path / "outside.py"
    outside.write_text("", encoding="utf-8")

    assert matches_exclude(outside, config) is None
