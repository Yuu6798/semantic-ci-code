from __future__ import annotations

from pathlib import Path

from .git_helpers import BASELINE_SOURCE, git, init_repo, write_file
from .helpers import payload, run_semantic_ci

TARGET_WITH_RISK = """\
intent: validate profile endpoint plan
change:
  primary_kind: refactor
  scope:
    files:
      - src/**/*.py
constraints:
  - id: lock_api_surface
    kind: delta
    target: api_surface
    operator: equals_baseline
  - id: require_missing_api
    kind: state
    target: api_surface
    operator: includes_all
    expected:
      - pkg.profile
"""


def test_validate_plan_outputs_text_for_claude_code_with_baseline_dir(tmp_path: Path):
    pkg = tmp_path / "pkg"
    write_file(pkg / "mod.py", BASELINE_SOURCE)
    target = tmp_path / "target.yaml"
    write_file(target, TARGET_WITH_RISK)

    result = run_semantic_ci(
        tmp_path,
        "validate-plan",
        "--target",
        str(target),
        "--adapter",
        "claude-code",
        "--baseline-dir",
        str(pkg),
    )

    assert result.returncode == 0
    assert "# Plan Validation - Pre-Generation Guidance" in result.stdout
    assert "## Risk Areas" in result.stdout
    assert "- require_missing_api" in result.stdout
    assert result.stderr == ""


def test_validate_plan_json_envelope_contains_risk_summary(tmp_path: Path):
    pkg = tmp_path / "pkg"
    write_file(pkg / "mod.py", BASELINE_SOURCE)
    target = tmp_path / "target.yaml"
    write_file(target, TARGET_WITH_RISK)

    result = run_semantic_ci(
        tmp_path,
        "validate-plan",
        "--target",
        str(target),
        "--adapter",
        "codex",
        "--baseline-dir",
        str(pkg),
        "--format",
        "json",
    )
    data = payload(result)

    assert result.returncode == 0
    assert data["schema_version"] == "1"
    assert data["subcommand"] == "validate-plan"
    assert data["adapter_name"] == "codex"
    assert data["risk_summary"]["would_violate"] == ["require_missing_api"]
    assert set(data["risk_summary"]) == {
        "would_violate",
        "forbidden_zones",
        "required_additions",
        "template_implications",
    }
    assert data["rendered"].startswith("[INTENT]\n")
    assert data["engine"]["package_version"]


def test_validate_plan_writes_output_file(tmp_path: Path):
    pkg = tmp_path / "pkg"
    write_file(pkg / "mod.py", BASELINE_SOURCE)
    target = tmp_path / "target.yaml"
    output = tmp_path / "plan.mdc"
    write_file(target, TARGET_WITH_RISK)

    result = run_semantic_ci(
        tmp_path,
        "validate-plan",
        "--target",
        str(target),
        "--adapter",
        "cursor",
        "--baseline-dir",
        str(pkg),
        "--output",
        str(output),
    )

    assert result.returncode == 0
    assert result.stdout == ""
    assert output.read_text(encoding="utf-8").startswith("---\n")


def test_validate_plan_supports_baseline_rev(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_WITH_RISK)
    baseline = git(repo, "rev-parse", "origin/main").stdout.strip()

    result = run_semantic_ci(
        repo,
        "validate-plan",
        "--target",
        "target.yaml",
        "--adapter",
        "claude-code",
        "--baseline-rev",
        baseline,
    )

    assert result.returncode == 0
    assert "validate profile endpoint plan" in result.stdout


def test_validate_plan_default_baseline_resolution_uses_git_fallback(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_WITH_RISK)

    result = run_semantic_ci(
        repo,
        "validate-plan",
        "--target",
        "target.yaml",
        "--adapter",
        "codex",
        "--no-fetch",
    )

    assert result.returncode == 0
    assert "[RISK AREAS]" in result.stdout


def test_validate_plan_falls_back_to_empty_baseline_when_no_git_baseline(tmp_path: Path):
    target = tmp_path / "target.yaml"
    write_file(target, TARGET_WITH_RISK)

    result = run_semantic_ci(
        tmp_path,
        "validate-plan",
        "--target",
        str(target),
        "--adapter",
        "cursor",
        "--format",
        "json",
    )
    data = payload(result)

    assert result.returncode == 0
    assert data["risk_summary"]["would_violate"] == ["require_missing_api"]


def test_validate_plan_missing_target_exits_two(tmp_path: Path):
    result = run_semantic_ci(
        tmp_path,
        "validate-plan",
        "--target",
        str(tmp_path / "missing.yaml"),
        "--adapter",
        "claude-code",
    )

    assert result.returncode == 2
    assert "target file not found" in result.stderr


def test_validate_plan_invalid_baseline_rev_exits_two(tmp_path: Path):
    repo = init_repo(tmp_path)
    write_file(repo / "target.yaml", TARGET_WITH_RISK)

    result = run_semantic_ci(
        repo,
        "validate-plan",
        "--target",
        "target.yaml",
        "--adapter",
        "claude-code",
        "--baseline-rev",
        "not-a-ref",
    )

    assert result.returncode == 2
    assert result.stdout == ""


def test_validate_plan_requires_adapter(tmp_path: Path):
    target = tmp_path / "target.yaml"
    write_file(target, TARGET_WITH_RISK)

    result = run_semantic_ci(tmp_path, "validate-plan", "--target", str(target))

    assert result.returncode == 2
    assert "required" in result.stderr
