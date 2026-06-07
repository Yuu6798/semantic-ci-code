from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_ROOT = REPO_ROOT / "examples"

CASES = (
    "01-tests-pass-intent-fails",
    "02-imports-same-effects-change",
    "03-api-same-complexity-grows",
    "04-llm-style-intent-drift",
)

EXIT_CODE_RE = re.compile(r"^Expected exit code:\s*`(?P<value>\d+)`$", re.MULTILINE)
VERDICT_RE = re.compile(r"^Expected verdict:\s*`(?P<value>pass|repair|fail)`$", re.MULTILINE)


def _documented_expectations(case_dir: Path) -> tuple[str, int]:
    readme = (case_dir / "README.md").read_text(encoding="utf-8")
    verdict_match = VERDICT_RE.search(readme)
    exit_code_match = EXIT_CODE_RE.search(readme)
    assert verdict_match is not None, f"{case_dir.name} README missing expected verdict"
    assert exit_code_match is not None, f"{case_dir.name} README missing expected exit code"
    return verdict_match.group("value"), int(exit_code_match.group("value"))


def _run_semantic_ci_compare(case_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "1"
    return subprocess.run(
        [
            "semantic-ci",
            "compare",
            "--baseline-dir",
            str(case_dir / "baseline"),
            "--candidate-dir",
            str(case_dir / "candidate"),
            "--target",
            str(case_dir / "target.yaml"),
            "--format",
            "json",
        ],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize("case_name", CASES)
def test_example_documented_exit_code_matches_compare_result(case_name: str):
    case_dir = EXAMPLES_ROOT / case_name
    expected_verdict, expected_exit_code = _documented_expectations(case_dir)

    result = _run_semantic_ci_compare(case_dir)

    assert result.returncode == expected_exit_code, result.stderr
    assert json.loads(result.stdout)["verdict"] == expected_verdict
