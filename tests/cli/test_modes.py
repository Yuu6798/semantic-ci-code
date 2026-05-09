from __future__ import annotations

import statistics
import time
from os import pathsep
from pathlib import Path

import pytest

from semantic_ci_code.compiler import compile_target_svp
from semantic_ci_code.domain.state_schema import CodeState, CodeStateDelta, ComplexityDelta
from semantic_ci_code.evaluator import ResultStatus, VerdictResult, evaluate_constraints
from semantic_ci_code.pipeline import SMOKE_DIMENSIONS
from semantic_ci_code.pipeline import python_code_state as code_state_pipeline

from .git_helpers import (
    CANDIDATE_SOURCE,
    TARGET_FAIL,
    init_repo,
    init_repo_without_candidate_commit,
    stage_changes,
)
from .helpers import payload, run_semantic_ci, run_semantic_ci_subprocess

COMPLEXITY_TARGET = """\
intent: smoke should skip expensive dimensions
change:
  primary_kind: feature
constraints:
  - id: complexity_budget
    kind: delta
    target: complexity_delta.cyclomatic
    operator: less_than_or_equal
    expected: 0
"""

REPAIR_TARGET = """\
intent: smoke repair semantics stay unchanged
change:
  primary_kind: feature
constraints:
  - id: unresolved_repair
    kind: delta
    target: python_specific.missing
    operator: equals
    expected: 1
    unknown_policy: repair
"""


def test_check_accepts_smoke_full_and_defaults_to_full(tmp_path: Path):
    repo = init_repo(tmp_path)

    smoke = run_semantic_ci(repo, "check", "--mode", "smoke", "--format", "json", "--no-fetch")
    full = run_semantic_ci(repo, "check", "--mode", "full", "--format", "json", "--no-fetch")
    default = run_semantic_ci(repo, "check", "--format", "json", "--no-fetch")

    assert smoke.returncode == 0
    assert payload(smoke)["mode"] == "smoke"
    assert full.returncode == 0
    assert payload(full)["mode"] == "full"
    assert default.returncode == 0
    assert payload(default)["mode"] == "full"


def test_pre_commit_accepts_smoke_full_and_defaults_to_full(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)

    smoke = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    full = run_semantic_ci(repo, "pre-commit", "--mode", "full", "--format", "json")
    default = run_semantic_ci(repo, "pre-commit", "--format", "json")

    assert smoke.returncode == 0
    assert payload(smoke)["mode"] == "smoke"
    assert full.returncode == 0
    assert payload(full)["mode"] == "full"
    assert default.returncode == 0
    assert payload(default)["mode"] == "full"


def test_invalid_mode_flag_exits_usage_error(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)

    result = run_semantic_ci(repo, "pre-commit", "--mode", "quick", "--format", "json")

    assert result.returncode == 2


def test_semantic_ci_mode_env_overrides_default_and_flag_wins(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)

    from_env = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        extra_env={"SEMANTIC_CI_MODE": "smoke"},
    )
    flag_wins = run_semantic_ci(
        repo,
        "pre-commit",
        "--mode",
        "full",
        "--format",
        "json",
        extra_env={"SEMANTIC_CI_MODE": "smoke"},
    )
    invalid_env = run_semantic_ci(
        repo,
        "pre-commit",
        "--format",
        "json",
        extra_env={"SEMANTIC_CI_MODE": "quick"},
    )

    assert from_env.returncode == 0
    assert payload(from_env)["mode"] == "smoke"
    assert flag_wins.returncode == 0
    assert payload(flag_wins)["mode"] == "full"
    assert invalid_env.returncode == 2


def test_smoke_extracts_only_api_surface_imports_and_effects(tmp_path: Path, monkeypatch):
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "mod.py").write_text("import os\n\ndef f():\n    print(os.name)\n", encoding="utf-8")
    calls: list[str] = []

    def record(name: str):
        def _inner(*args, **kwargs):
            calls.append(name)
            return ()

        return _inner

    monkeypatch.setattr(code_state_pipeline, "_extract_api_surface", record("api_surface"))
    monkeypatch.setattr(code_state_pipeline, "_extract_effects", record("effects"))
    monkeypatch.setattr(code_state_pipeline, "_extract_imports", record("imports"))
    monkeypatch.setattr(
        code_state_pipeline,
        "_extract_complexity",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("complexity called")),
    )
    monkeypatch.setattr(
        code_state_pipeline,
        "_extract_test_surface",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("test_surface called")),
    )
    monkeypatch.setattr(
        code_state_pipeline,
        "_extract_module_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("module_graph called")),
    )

    state = code_state_pipeline.extract_python_code_state(package, dimensions=SMOKE_DIMENSIONS)

    assert state.complexity == ()
    assert state.test_surface == ()
    assert state.module_graph == ()
    assert calls == ["api_surface", "effects", "imports"]


def test_smoke_routes_unextracted_dimension_constraints_to_skipped():
    target = compile_target_svp(COMPLEXITY_TARGET)
    verdict = evaluate_constraints(
        target,
        CodeStateDelta(complexity_delta=ComplexityDelta(cyclomatic=5)),
        baseline=CodeState(),
        candidate=CodeState(),
        extracted_dimensions=SMOKE_DIMENSIONS,
    )

    assert verdict.result is VerdictResult.PASS
    assert verdict.results[-1].status is ResultStatus.SKIPPED
    assert verdict.results[-1].error_code == "E_DIMENSION_SKIPPED"


def test_smoke_json_envelope_reports_mode_and_skipped_summary(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    (repo / "target.yaml").write_text(COMPLEXITY_TARGET, encoding="utf-8")
    stage_changes(repo, {"mod.py": "VALUE = 1\n\ndef existing():\n    return VALUE\n"})

    result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    data = payload(result)

    assert result.returncode == 0
    assert data["schema_version"] == "5"
    assert data["mode"] == "smoke"
    assert data["summary"]["skipped"] == 1
    assert data["results"][-1]["status"] == "skipped"


def test_smoke_human_output_marks_partial_mode_and_skipped_constraints(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    (repo / "target.yaml").write_text(COMPLEXITY_TARGET, encoding="utf-8")
    stage_changes(repo, {"mod.py": "VALUE = 1\n\ndef existing():\n    return VALUE\n"})

    no_color = run_semantic_ci(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "human",
        "--no-color",
    )
    color = run_semantic_ci(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "human",
        extra_env={"FORCE_COLOR": "1"},
    )

    assert no_color.returncode == 0
    assert "[smoke mode] partial CodeState" in no_color.stdout
    assert "~ [SKIPPED]" in no_color.stdout
    assert color.returncode == 0
    assert "\x1b[90m[SKIPPED]" in color.stdout


def test_smoke_verdict_exit_matrix_matches_full_semantics(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(
        repo,
        {"mod.py": CANDIDATE_SOURCE},
    )

    pass_result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    (repo / "target.yaml").write_text(REPAIR_TARGET, encoding="utf-8")
    repair_result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")
    repair_strict = run_semantic_ci(
        repo,
        "pre-commit",
        "--mode",
        "smoke",
        "--format",
        "json",
        "--strict-repair",
    )
    (repo / "target.yaml").write_text(TARGET_FAIL, encoding="utf-8")
    fail_result = run_semantic_ci(repo, "pre-commit", "--mode", "smoke", "--format", "json")

    assert pass_result.returncode == 0
    assert payload(pass_result)["verdict"] == "pass"
    assert repair_result.returncode == 0
    assert payload(repair_result)["verdict"] == "repair"
    assert repair_strict.returncode == 1
    assert payload(repair_strict)["verdict"] == "repair"
    assert fail_result.returncode == 1
    assert payload(fail_result)["verdict"] == "fail"


@pytest.mark.slow
def test_smoke_is_faster_than_full(tmp_path: Path):
    repo = init_repo_without_candidate_commit(tmp_path)
    stage_changes(repo, {"mod.py": CANDIDATE_SOURCE})
    extra_env = _slow_full_only_dimensions_env(tmp_path)
    runs = 3

    full_times = [_timed_pre_commit(repo, "full", extra_env=extra_env) for _ in range(runs)]
    smoke_times = [_timed_pre_commit(repo, "smoke", extra_env=extra_env) for _ in range(runs)]

    assert statistics.median(smoke_times) <= statistics.median(full_times) * 0.7


def _timed_pre_commit(
    repo: Path,
    mode: str,
    *,
    extra_env: dict[str, str] | None = None,
) -> float:
    start = time.perf_counter()
    result = run_semantic_ci_subprocess(
        repo,
        "pre-commit",
        "--mode",
        mode,
        "--format",
        "json",
        "--no-cache",
        extra_env=extra_env,
    )
    elapsed = time.perf_counter() - start
    assert result.returncode == 0, result.stderr
    return elapsed


def _slow_full_only_dimensions_env(tmp_path: Path) -> dict[str, str]:
    sitecustomize_root = tmp_path / "sitecustomize"
    sitecustomize_root.mkdir()
    (sitecustomize_root / "sitecustomize.py").write_text(
        """
import time

from semantic_ci_code.pipeline import python_code_state as pipeline


def _slow(name):
    original = getattr(pipeline, name)

    def _wrapped(*args, **kwargs):
        time.sleep(0.4)
        return original(*args, **kwargs)

    return _wrapped


pipeline._extract_complexity = _slow("_extract_complexity")
pipeline._extract_test_surface = _slow("_extract_test_surface")
pipeline._extract_module_graph = _slow("_extract_module_graph")
""",
        encoding="utf-8",
    )
    src_root = Path(__file__).resolve().parents[2] / "src"
    return {"PYTHONPATH": f"{sitecustomize_root}{pathsep}{src_root}"}
