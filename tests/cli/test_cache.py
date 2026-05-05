from __future__ import annotations

import json
import os
import time
import tomllib
from os import pathsep
from pathlib import Path

from semantic_ci_code.cli import code_state_cache
from semantic_ci_code.cli.code_state_cache import (
    CACHE_FORMAT_VERSION,
    CODE_STATE_SCHEMA_VERSION,
    CacheStats,
    cache_key,
    evict_to_budget,
    key_meta,
    write_cached_code_state,
)
from semantic_ci_code.cli.modes import ExecutionMode
from semantic_ci_code.domain.state_schema import CodeState

from .git_helpers import (
    CANDIDATE_SOURCE,
    init_repo,
    init_repo_without_candidate_commit,
    stage_changes,
    write_file,
)
from .helpers import REPO_ROOT, payload, run_semantic_ci


def test_check_uses_cached_codestate_without_calling_extractor_on_second_run(tmp_path: Path):
    repo = init_repo(tmp_path)
    cache_dir = tmp_path / "cache"

    first = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
    )
    second = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
        extra_env=_extractor_bomb_env(tmp_path),
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert payload(second)["verdict"] == "pass"
    assert payload(first)["cache"] == {
        "hit": 0,
        "miss": 2,
        "invalid": 0,
        "write_failed": 0,
        "disabled": False,
    }
    assert payload(second)["cache"] == {
        "hit": 2,
        "miss": 0,
        "invalid": 0,
        "write_failed": 0,
        "disabled": False,
    }


def test_pre_commit_uses_cached_codestate_without_calling_extractor_on_second_run(
    tmp_path: Path,
):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    cache_dir = tmp_path / "cache"

    first = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(cache_dir),
    )
    second = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(cache_dir),
        extra_env=_extractor_bomb_env(tmp_path),
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert payload(first)["cache"]["miss"] == 2
    assert payload(second)["cache"]["hit"] == 2


def test_pre_commit_staged_tree_change_misses_candidate_cache(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    cache_dir = tmp_path / "cache"
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    first = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(cache_dir),
    )
    second = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(cache_dir),
    )

    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE + "\nVALUE_2 = 2\n"})
    third = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(cache_dir),
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert third.returncode == 0
    assert payload(second)["cache"]["hit"] == 2
    assert payload(third)["cache"] == {
        "hit": 1,
        "miss": 1,
        "invalid": 0,
        "write_failed": 0,
        "disabled": False,
    }


def test_cache_key_changes_for_each_axis():
    base = {
        "tree_object_id": "tree-a",
        "package_root_relpath_posix": Path("pkg"),
        "mode": ExecutionMode.SMOKE,
        "dimensions_sorted_tuple": ("api_surface", "effects", "imports"),
        "python_xy": "3.11",
        "package_version_value": "0.1.0",
        "code_state_schema_version": CODE_STATE_SCHEMA_VERSION,
        "cache_format_version": CACHE_FORMAT_VERSION,
    }
    baseline = cache_key(**base)

    variants = [
        {"tree_object_id": "tree-b"},
        {"package_root_relpath_posix": Path("other")},
        {"mode": ExecutionMode.FULL},
        {"dimensions_sorted_tuple": None},
        {"python_xy": "3.12"},
        {"package_version_value": "0.2.0"},
        {"cache_format_version": CACHE_FORMAT_VERSION + 1},
    ]

    for variant in variants:
        changed = {**base, **variant}
        assert cache_key(**changed) != baseline


def test_cache_package_version_uses_source_fingerprint_when_metadata_is_unknown(monkeypatch):
    monkeypatch.setattr(code_state_cache, "package_version", lambda: "0.0.0+unknown")
    monkeypatch.setattr(code_state_cache, "_source_fingerprint", lambda: "abc123")

    assert code_state_cache.cache_package_version() == "0.0.0+unknown.source.abc123"


def test_unknown_package_metadata_source_fingerprint_invalidates_cache_key(monkeypatch):
    base = {
        "tree_object_id": "tree-a",
        "package_root_relpath_posix": Path("pkg"),
        "mode": ExecutionMode.SMOKE,
        "dimensions_sorted_tuple": ("api_surface", "effects", "imports"),
        "python_xy": "3.11",
    }

    monkeypatch.setattr(code_state_cache, "package_version", lambda: "0.0.0+unknown")
    monkeypatch.setattr(code_state_cache, "_source_fingerprint", lambda: "source-a")
    before = code_state_cache.key_for_state(**base)

    monkeypatch.setattr(code_state_cache, "_source_fingerprint", lambda: "source-b")
    after = code_state_cache.key_for_state(**base)

    assert after != before


def test_installed_package_metadata_is_used_without_source_fingerprint(monkeypatch):
    monkeypatch.setattr(code_state_cache, "package_version", lambda: "1.2.3")
    monkeypatch.setattr(
        code_state_cache,
        "_source_fingerprint",
        lambda: (_ for _ in ()).throw(AssertionError("source fingerprint should not run")),
    )

    assert code_state_cache.cache_package_version() == "1.2.3"


def test_cache_verdict_matches_no_cache_byte_for_byte(tmp_path: Path):
    repo = init_repo(tmp_path)
    cache_dir = tmp_path / "cache"

    uncached = run_semantic_ci(repo, "check", "--format", "json", "--no-fetch", "--no-cache")
    cached = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
    )

    assert uncached.returncode == 0
    assert cached.returncode == 0
    assert _without_cache(payload(cached)) == _without_cache(payload(uncached))
    assert payload(uncached)["cache"]["disabled"] is True
    assert payload(cached)["cache"]["disabled"] is False


def test_smoke_and_full_cache_entries_are_separate(tmp_path: Path):
    repo = init_repo(tmp_path)
    cache_dir = tmp_path / "cache"

    smoke = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "smoke",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
    )
    full = run_semantic_ci(
        repo,
        "check",
        "--mode",
        "full",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
    )

    assert smoke.returncode == 0
    assert full.returncode == 0
    assert len(tuple((cache_dir / "code_state").glob("*.json"))) == 4


def test_no_cache_flag_and_env_skip_cache_file_creation(tmp_path: Path):
    repo = init_repo(tmp_path)

    flag_dir = tmp_path / "flag-cache"
    env_dir = tmp_path / "env-cache"
    flag = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--no-cache",
        "--cache-dir",
        str(flag_dir),
    )
    env = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(env_dir),
        extra_env={"SEMANTIC_CI_NO_CACHE": "1"},
    )

    assert flag.returncode == 0
    assert env.returncode == 0
    assert not flag_dir.exists()
    assert not env_dir.exists()
    assert payload(flag)["cache"]["disabled"] is True
    assert payload(env)["cache"]["disabled"] is True


def test_pre_commit_no_cache_flag_and_env_skip_cache_file_creation(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})

    flag_dir = tmp_path / "flag-cache"
    env_dir = tmp_path / "env-cache"
    flag = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--no-cache",
        "--cache-dir",
        str(flag_dir),
    )
    env = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(env_dir),
        extra_env={"SEMANTIC_CI_NO_CACHE": "1"},
    )

    assert flag.returncode == 0
    assert env.returncode == 0
    assert not flag_dir.exists()
    assert not env_dir.exists()
    assert payload(flag)["cache"]["disabled"] is True
    assert payload(env)["cache"]["disabled"] is True


def test_cache_dir_override_accepts_relative_and_absolute_paths(tmp_path: Path):
    repo = init_repo(tmp_path)
    relative_dir = Path("relative-cache")
    absolute_dir = tmp_path / "absolute-cache"

    relative = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(relative_dir),
    )
    absolute = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(absolute_dir),
    )

    assert relative.returncode == 0
    assert absolute.returncode == 0
    assert (repo / relative_dir / "code_state").exists()
    assert (absolute_dir / "code_state").exists()


def test_pre_commit_cache_dir_override_accepts_relative_and_absolute_paths(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    relative_dir = Path("relative-cache")
    absolute_dir = tmp_path / "absolute-cache"

    relative = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(relative_dir),
    )
    absolute = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        "--cache-dir",
        str(absolute_dir),
    )

    assert relative.returncode == 0
    assert absolute.returncode == 0
    assert (repo / relative_dir / "code_state").exists()
    assert (absolute_dir / "code_state").exists()


def test_package_root_is_normalized_before_tree_object_id(tmp_path: Path):
    repo = init_repo(tmp_path)
    cache_dir = tmp_path / "cache"

    result = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--package-root",
        "src/..",
        "--cache-dir",
        str(cache_dir),
    )

    assert result.returncode == 0
    assert len(tuple((cache_dir / "code_state").glob("*.json"))) == 2


def test_package_root_cannot_escape_repo_for_cache_key(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--package-root",
        "..",
    )

    assert result.returncode == 2
    assert "package_root must stay within repo for check" in result.stderr


def test_corrupt_cache_is_miss_and_overwritten(tmp_path: Path):
    repo = init_repo(tmp_path)
    cache_dir = tmp_path / "cache"
    first = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
    )
    cache_file = next((cache_dir / "code_state").glob("*.json"))
    cache_file.write_text("{not json", encoding="utf-8")

    second = run_semantic_ci(
        repo,
        "--verbose",
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--cache-dir",
        str(cache_dir),
    )

    assert first.returncode == 0
    assert second.returncode == 0
    assert "cache invalid:" in second.stderr
    assert payload(second)["cache"] == {
        "hit": 1,
        "miss": 1,
        "invalid": 1,
        "write_failed": 0,
        "disabled": False,
    }
    assert json.loads(cache_file.read_text(encoding="utf-8"))["cache_format_version"] == 1


def test_cache_format_version_mismatch_is_invalid(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    key = "a" * 64
    messages: list[str] = []
    write_cached_code_state(
        cache_dir,
        key,
        state=CodeState(),
        meta=key_meta(
            tree_object_id="tree",
            package_root_relpath_posix=Path("."),
            mode=ExecutionMode.FULL,
            dimensions_sorted_tuple=None,
        ),
    )
    cache_file = cache_dir / "code_state" / f"{key}.json"
    data = json.loads(cache_file.read_text(encoding="utf-8"))
    data["cache_format_version"] = CACHE_FORMAT_VERSION + 1
    cache_file.write_text(json.dumps(data), encoding="utf-8")

    assert code_state_cache.read_cached_code_state(cache_dir, key, log=messages.append) is None
    assert any("cache invalid:" in message for message in messages)


def test_atomic_write_leaves_no_tmp_on_success_and_no_json_on_replace_failure(
    tmp_path: Path,
    monkeypatch,
):
    cache_dir = tmp_path / "cache"
    key = "b" * 64
    meta = key_meta(
        tree_object_id="tree",
        package_root_relpath_posix=Path("."),
        mode=ExecutionMode.FULL,
        dimensions_sorted_tuple=None,
    )

    write_cached_code_state(cache_dir, key, state=CodeState(), meta=meta)
    assert not tuple((cache_dir / "code_state").glob("*.tmp"))

    failing_dir = tmp_path / "failing"
    messages: list[str] = []
    stats = CacheStats()

    def _raise_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(code_state_cache.os, "replace", _raise_replace)
    write_cached_code_state(
        failing_dir,
        key,
        state=CodeState(),
        meta=meta,
        stats=stats,
        log=messages.append,
    )

    assert any("cache write failed:" in message for message in messages)
    assert stats.write_failed == 1
    assert not (failing_dir / "code_state" / f"{key}.json").exists()
    assert not tuple((failing_dir / "code_state").glob("*.tmp"))


def test_allow_dirty_skips_candidate_cache_but_keeps_baseline_cache(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)
    cache_dir = tmp_path / "cache"

    result = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--no-fetch",
        "--allow-dirty",
        "--cache-dir",
        str(cache_dir),
    )

    assert result.returncode == 0
    assert len(tuple((cache_dir / "code_state").glob("*.json"))) == 1


def test_other_subcommands_do_not_create_cache_files(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    write_file(repo / "mod.py", CANDIDATE_SOURCE)
    cache_root = repo / ".semantic-ci" / "cache"

    observe = run_semantic_ci(repo, "observe", "--package-root", ".", "--format", "json")
    pre_commit = run_semantic_ci(repo, "pre-commit", "--format", "json")

    assert observe.returncode == 0
    assert pre_commit.returncode == 0
    assert not cache_root.exists()


def test_non_cache_subcommands_emit_disabled_cache_stats(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    compare = run_semantic_ci(
        REPO_ROOT,
        "compare",
        "--baseline-dir",
        "tests/fixtures/cli/compare/baseline_pkg",
        "--candidate-dir",
        "tests/fixtures/cli/compare/candidate_pkg",
        "--target",
        "tests/fixtures/cli/compare/target_pass.yaml",
        "--format",
        "json",
    )
    observe = run_semantic_ci(
        REPO_ROOT,
        "observe",
        "--package-root",
        "tests/fixtures/cli/observe_pkg",
        "--format",
        "json",
    )
    compile_result = run_semantic_ci(
        REPO_ROOT,
        "compile",
        "--target",
        "tests/fixtures/cli/compile/target_minimal.yaml",
        "--format",
        "json",
    )
    pre_commit = run_semantic_ci(repo, "pre-commit", "--format", "json")

    for result in (compare, observe, compile_result, pre_commit):
        assert result.returncode == 0
        assert payload(result)["schema_version"] == "3"
        assert payload(result)["cache"] == {
            "hit": 0,
            "miss": 0,
            "invalid": 0,
            "write_failed": 0,
            "disabled": True if payload(result)["subcommand"] != "pre-commit" else False,
        }


def test_eviction_removes_oldest_entries_to_low_water(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    old = _write_cache_blob(cache_dir / "code_state" / "old.json", "a" * 80, mtime=10)
    middle = _write_cache_blob(cache_dir / "code_state" / "middle.json", "b" * 80, mtime=20)
    newest = _write_cache_blob(cache_dir / "code_state" / "newest.json", "c" * 80, mtime=30)

    removed = evict_to_budget(cache_dir, 100)

    assert removed == (old, middle)
    assert not old.exists()
    assert not middle.exists()
    assert newest.exists()
    assert _cache_size(cache_dir) <= 80


def test_eviction_does_not_run_when_under_budget_or_budget_zero(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    entry = _write_cache_blob(cache_dir / "code_state" / "entry.json", "a" * 20, mtime=10)

    assert evict_to_budget(cache_dir, 100) == ()
    assert entry.exists()
    assert evict_to_budget(cache_dir, 0) == ()
    assert entry.exists()


def test_negative_cache_max_bytes_is_usage_error(tmp_path: Path):
    repo = init_repo(tmp_path)

    result = run_semantic_ci(
        repo,
        "check",
        "--format",
        "json",
        "--cache-max-bytes",
        "-1",
    )

    assert result.returncode == 2
    assert "cache max bytes must be non-negative" in result.stderr


def test_eviction_keeps_new_tmp_but_removes_stale_tmp(tmp_path: Path):
    cache_dir = tmp_path / "cache"
    old_tmp = _write_cache_blob(cache_dir / "code_state" / "old.json.tmp", "a" * 80, mtime=10)
    new_tmp = _write_cache_blob(
        cache_dir / "code_state" / "new.json.tmp",
        "b" * 80,
        mtime=time.time(),
    )
    json_entry = _write_cache_blob(cache_dir / "code_state" / "entry.json", "c" * 80, mtime=20)

    evict_to_budget(cache_dir, 50)

    assert not old_tmp.exists()
    assert not json_entry.exists()
    assert new_tmp.exists()


def test_eviction_unlink_error_is_warning_not_exception(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / "cache"
    _write_cache_blob(cache_dir / "code_state" / "entry.json", "a" * 120, mtime=10)
    messages: list[str] = []

    def _raise_unlink(self, *args, **kwargs):
        raise OSError("unlink failed")

    monkeypatch.setattr(Path, "unlink", _raise_unlink)

    assert evict_to_budget(cache_dir, 100, log=messages.append) == ()
    assert any("cache eviction failed:" in message for message in messages)


def test_project_dependencies_are_unchanged():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["dependencies"] == ["pydantic>=2.0", "PyYAML>=6.0"]


def _extractor_bomb_env(tmp_path: Path) -> dict[str, str]:
    root = tmp_path / "sitecustomize"
    root.mkdir(exist_ok=True)
    (root / "sitecustomize.py").write_text(
        """
from semantic_ci_code import pipeline


def _boom(*args, **kwargs):
    raise RuntimeError("extractor should not be called on cache hit")


pipeline.extract_python_code_state = _boom
""",
        encoding="utf-8",
    )
    return {"PYTHONPATH": f"{root}{pathsep}{REPO_ROOT / 'src'}"}


def _write_cache_blob(path: Path, content: str, *, mtime: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))
    return path


def _cache_size(cache_dir: Path) -> int:
    return sum(path.stat().st_size for path in cache_dir.rglob("*") if path.is_file())


def _without_cache(data: dict) -> dict:
    copied = dict(data)
    copied.pop("cache", None)
    return copied
