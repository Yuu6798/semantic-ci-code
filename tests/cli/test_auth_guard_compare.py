from __future__ import annotations

from .helpers import REPO_ROOT, parse_json, run_semantic_ci

FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "cli" / "auth_guard"


def _compare(candidate: str):
    return run_semantic_ci(
        REPO_ROOT,
        "compare",
        "--baseline-dir",
        str(FIXTURE_ROOT / "baseline"),
        "--candidate-dir",
        str(FIXTURE_ROOT / candidate),
        "--target",
        str(FIXTURE_ROOT / "target.yaml"),
        "--format",
        "json",
    )


def test_auth_guard_compare_fixture_fails_when_guard_is_removed():
    result = _compare("candidate_fail")

    assert result.returncode == 1, result.stderr
    assert parse_json(result.stdout)["verdict"] == "fail"


def test_auth_guard_compare_fixture_passes_when_guard_is_kept():
    result = _compare("candidate_pass")

    assert result.returncode == 0, result.stderr
    assert parse_json(result.stdout)["verdict"] == "pass"
