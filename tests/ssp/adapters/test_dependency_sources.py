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


def test_discovery_selects_named_pylock_before_pyproject(tmp_path: Path):
    (tmp_path / "pylock.prod.toml").write_text("[packages]\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
dependencies = ["requests==2.32.0"]
""".lstrip(),
        encoding="utf-8",
    )

    source = discover_dependency_source(tmp_path)

    assert source.kind == "pylock"
    assert source.path == tmp_path.resolve() / "pylock.prod.toml"


def test_discovery_prefers_default_pylock_over_named_pylock(tmp_path: Path):
    (tmp_path / "pylock.z.toml").write_text("[packages]\n", encoding="utf-8")
    (tmp_path / "pylock.toml").write_text("[packages]\n", encoding="utf-8")

    source = discover_dependency_source(tmp_path)

    assert source.kind == "pylock"
    assert source.path == tmp_path.resolve() / "pylock.toml"


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


def test_lock_translation_respects_selected_dependency_groups(tmp_path: Path):
    (tmp_path / "poetry.lock").write_text(
        """
[[package]]
name = "django"
version = "3.2.0"
groups = ["main"]

[[package]]
name = "requests"
version = "2.32.0"
groups = ["default"]

[[package]]
name = "mkdocs"
version = "1.6.0"
groups = ["docs"]

[[package]]
name = "pytest"
version = "8.3.0"
groups = ["test"]
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0", "requests==2.32.0")


def test_uv_lock_translation_excludes_root_dev_dependencies(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example-app"
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        """
[[package]]
name = "example-app"
version = "0.1.0"
dev-dependencies = [
  { name = "pytest" },
  { name = "ruff" },
]

[[package]]
name = "django"
version = "3.2.0"

[[package]]
name = "pytest"
version = "8.3.0"

[[package]]
name = "ruff"
version = "0.9.0"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0",)


def test_uv_lock_translation_excludes_root_dependency_groups(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example-app"
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        """
[[package]]
name = "example-app"
version = "0.1.0"

[package.dependency-groups]
docs = ["mkdocs>=1.6"]
test = [{ name = "pytest" }]

[[package]]
name = "django"
version = "3.2.0"

[[package]]
name = "mkdocs"
version = "1.6.0"

[[package]]
name = "pytest"
version = "8.3.0"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0",)


def test_uv_lock_translation_excludes_dev_dependency_closure(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example-app"
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        """
[[package]]
name = "example-app"
version = "0.1.0"
dependencies = [{ name = "django" }]
dev-dependencies = [{ name = "pytest" }]

[[package]]
name = "django"
version = "3.2.0"
dependencies = [{ name = "shared" }]

[[package]]
name = "pytest"
version = "8.3.0"
dependencies = [{ name = "pluggy" }, { name = "shared" }]

[[package]]
name = "pluggy"
version = "1.5.0"

[[package]]
name = "shared"
version = "1.0.0"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0", "shared==1.0.0")


def test_uv_lock_translation_excludes_optional_dependency_closure(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example-app"
""".lstrip(),
        encoding="utf-8",
    )
    (tmp_path / "uv.lock").write_text(
        """
[[package]]
name = "example-app"
version = "0.1.0"
dependencies = [{ name = "django" }]

[package.optional-dependencies]
speedups = [{ name = "orjson" }]

[[package]]
name = "django"
version = "3.2.0"
dependencies = [{ name = "shared" }]

[[package]]
name = "orjson"
version = "3.10.0"
dependencies = [{ name = "extra-helper" }, { name = "shared" }]

[[package]]
name = "extra-helper"
version = "1.0.0"

[[package]]
name = "shared"
version = "1.0.0"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0", "shared==1.0.0")


def test_lock_translation_respects_legacy_group_and_category_fields(tmp_path: Path):
    (tmp_path / "pdm.lock").write_text(
        """
[[package]]
name = "django"
version = "3.2.0"
group = "default"

[[package]]
name = "requests"
version = "2.32.0"
category = "main"

[[package]]
name = "sphinx"
version = "8.1.0"
group = "docs"

[[package]]
name = "pytest"
version = "8.3.0"
category = "dev"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0", "requests==2.32.0")


def test_lock_translation_invalid_group_metadata_is_fail_closed(tmp_path: Path):
    (tmp_path / "poetry.lock").write_text(
        """
[[package]]
name = "django"
version = "3.2.0"
groups = "main"
""".lstrip(),
        encoding="utf-8",
    )

    source = discover_dependency_source(tmp_path)

    try:
        generated_requirements_for_source(source)
    except DependencySourceError as exc:
        assert "poetry.lock" in str(exc)
        assert "invalid groups" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("expected DependencySourceError")


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


def test_lock_translation_prerelease_marker_comparison_does_not_crash(tmp_path: Path):
    (tmp_path / "pdm.lock").write_text(
        """
[[package]]
name = "django"
version = "3.2.0"
marker = "python_full_version >= '3.0.0a0'"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("django==3.2.0",)


def test_lock_translation_respects_wildcard_version_marker_equality(tmp_path: Path):
    (tmp_path / "pdm.lock").write_text(
        """
[[package]]
name = "included"
version = "1.0.0"
marker = "python_version == '3.*'"

[[package]]
name = "also-included"
version = "1.0.0"
marker = "'3.*' == python_version"

[[package]]
name = "excluded"
version = "1.0.0"
marker = "python_version == '999.*'"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("also-included==1.0.0", "included==1.0.0")


def test_lock_translation_respects_wildcard_version_marker_inequality(tmp_path: Path):
    (tmp_path / "pdm.lock").write_text(
        """
[[package]]
name = "included"
version = "1.0.0"
marker = "python_version != '999.*'"

[[package]]
name = "excluded"
version = "1.0.0"
marker = "python_version != '3.*'"
""".lstrip(),
        encoding="utf-8",
    )

    generated = generated_requirements_for_source(discover_dependency_source(tmp_path))

    assert generated.lines == ("included==1.0.0",)


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
