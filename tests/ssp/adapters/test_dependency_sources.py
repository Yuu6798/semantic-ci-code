from __future__ import annotations

from pathlib import Path

from semantic_ci_code.ssp.adapters.dependency_sources import (
    DependencySourceError,
    discover_dependency_source,
    generated_requirements_for_source,
)


def test_discovery_precedence_selects_highest_ranked_source(tmp_path: Path):
    for filename in (
        "pyproject.toml",
        "poetry.lock",
        "pdm.lock",
        "uv.lock",
        "pylock.toml",
        "requirements.txt",
    ):
        (tmp_path / filename).write_text(_content_for(filename), encoding="utf-8")

    source = discover_dependency_source(tmp_path)

    assert source.kind == "requirements"
    assert source.path == tmp_path.resolve() / "requirements.txt"


def test_discovery_precedence_selects_lock_before_pyproject(tmp_path: Path):
    (tmp_path / "uv.lock").write_text(_lock_content(("django", "3.2.0")), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = ["requests==2.32.0"]
""".lstrip(),
        encoding="utf-8",
    )

    source = discover_dependency_source(tmp_path)

    assert source.kind == "uv-lock"
    assert source.path == tmp_path.resolve() / "uv.lock"


def test_baseline_and_candidate_discovery_are_independent(tmp_path: Path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    (baseline / "requirements.txt").write_text("django==3.2.0\n", encoding="utf-8")
    (candidate / "pdm.lock").write_text(_lock_content(("requests", "2.32.0")), encoding="utf-8")

    assert discover_dependency_source(baseline).kind == "requirements"
    assert discover_dependency_source(candidate).kind == "pdm-lock"


def test_lock_translation_sorts_dedups_and_excludes_project_package(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example-app"
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "pdm.lock").write_text(
        _lock_content(
            ("zlib-ng", "1.0.0"),
            ("example_app", "0.1.0"),
            ("django", "3.2.0"),
            ("django", "3.2.0"),
        ),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.no_deps is True
    assert generated.lines == ("django==3.2.0", "zlib-ng==1.0.0")


def test_lock_translation_respects_optional_packages_and_environment_markers(tmp_path: Path):
    (tmp_path / "uv.lock").write_text(
        """
[[package]]
name = "django"
version = "3.2.0"

[[package]]
name = "current"
version = "1.0.0"
marker = "sys_platform != '__semantic_ci_never__'"

[[package]]
name = "windows-only"
version = "1.0.0"
marker = "sys_platform == '__semantic_ci_never__'"

[[package]]
name = "extra-only"
version = "1.0.0"
marker = "extra == 'speedups'"

[[package]]
name = "optional-pkg"
version = "1.0.0"
optional = true
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("current==1.0.0", "django==3.2.0")


def test_lock_translation_missing_version_is_fail_closed(tmp_path: Path):
    (tmp_path / "poetry.lock").write_text(
        """
[[package]]
name = "django"
""".lstrip(),
        encoding="utf-8",
    )

    source = discover_dependency_source(tmp_path)

    assert source.kind == "poetry-lock"
    try:
        generated_requirements_for_source(source)
    except DependencySourceError as exc:
        assert "poetry.lock" in str(exc)
        assert "missing version" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected DependencySourceError")


def test_lock_translation_unsupported_marker_is_fail_closed(tmp_path: Path):
    (tmp_path / "pdm.lock").write_text(
        """
[[package]]
name = "django"
version = "3.2.0"
marker = "unknown_marker_name == 'x'"
""".lstrip(),
        encoding="utf-8",
    )

    source = discover_dependency_source(tmp_path)

    try:
        generated_requirements_for_source(source)
    except DependencySourceError as exc:
        assert "pdm.lock" in str(exc)
        assert "unsupported marker" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected DependencySourceError")


def test_pyproject_static_dependencies_are_used(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = [
  "django>=3.2",
  "requests==2.32.0",
]
""".lstrip(),
        encoding="utf-8",
    )

    source = discover_dependency_source(tmp_path)
    generated = generated_requirements_for_source(source)

    assert source.kind == "pyproject"
    assert generated.no_deps is False
    assert generated.lines == ("django>=3.2", "requests==2.32.0")


def test_pyproject_dynamic_dependencies_are_not_recognized(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dynamic = ["dependencies"]
""".lstrip(),
        encoding="utf-8",
    )

    assert discover_dependency_source(tmp_path).kind == "fallback"


def test_pyproject_without_project_table_is_not_recognized(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[tool.example]
dependencies = ["django"]
""".lstrip(),
        encoding="utf-8",
    )

    assert discover_dependency_source(tmp_path).kind == "fallback"


def test_malformed_pyproject_is_error_source(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project\n", encoding="utf-8")

    source = discover_dependency_source(tmp_path)

    assert source.kind == "error"
    assert source.path == tmp_path.resolve() / "pyproject.toml"
    assert "pyproject.toml" in (source.error_message or "")


def _content_for(filename: str) -> str:
    if filename == "requirements.txt":
        return "django==3.2.0\n"
    if filename == "pylock.toml":
        return "[packages]\n"
    if filename.endswith(".lock"):
        return _lock_content(("django", "3.2.0"))
    return "[project]\ndependencies = ['django==3.2.0']\n"


def _lock_content(*packages: tuple[str, str]) -> str:
    return "\n".join(
        f'[[package]]\nname = "{name}"\nversion = "{version}"\n' for name, version in packages
    )
