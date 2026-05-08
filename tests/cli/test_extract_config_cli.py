from __future__ import annotations

from pathlib import Path

from .helpers import REPO_ROOT, parse_json, run_semantic_ci

COMPILE_TARGET = REPO_ROOT / "tests" / "fixtures" / "cli" / "compile" / "target_minimal.yaml"


def test_observe_honors_extract_exclude_before_parse(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.semantic_ci_code.extract]
exclude = ["pkg/broken"]
""".strip(),
        encoding="utf-8",
    )
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "good.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    broken = package_root / "broken" / "bad.py"
    broken.parent.mkdir()
    broken.write_text("def broken(:\n", encoding="utf-8")

    result = run_semantic_ci(
        tmp_path,
        "--verbose",
        "observe",
        "--package-root",
        str(package_root),
    )

    assert result.returncode == 0
    assert "excluded by config: 1 files" in result.stderr
    assert "pkg/broken/bad.py (matched: pkg/broken)" in result.stderr
    payload = parse_json(result.stdout)
    assert {entry["fqn"] for entry in payload["code_state"]["api_surface"]} >= {"good.ok"}


def test_malformed_extract_config_is_engine_error_for_extraction_command(tmp_path: Path):
    package_root = tmp_path / "pkg"
    package_root.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.semantic_ci_code.extract]
exlude = ["pkg/broken"]
""".strip(),
        encoding="utf-8",
    )

    result = run_semantic_ci(tmp_path, "observe", "--package-root", str(package_root))

    assert result.returncode == 3
    assert "extract config error:" in result.stderr
    assert "exlude" in result.stderr


def test_non_extraction_command_does_not_load_malformed_extract_config(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.semantic_ci_code.extract]
exlude = ["pkg/broken"]
""".strip(),
        encoding="utf-8",
    )

    result = run_semantic_ci(
        tmp_path,
        "compile",
        "--target",
        str(COMPILE_TARGET),
        "--format",
        "json",
    )

    assert result.returncode == 0
    assert parse_json(result.stdout)["subcommand"] == "compile"
    assert result.stderr == ""
