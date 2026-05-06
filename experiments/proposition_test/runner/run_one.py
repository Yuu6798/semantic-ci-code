"""Run ruff / mypy / pytest / semantic-ci on a single candidate package.

Usage:
    python runner/run_one.py <candidate_dir>

<candidate_dir> must contain a package named ``authpkg/`` with the same layout
as the baseline. The script writes a JSON detection report to stdout.

Detection convention:
    "detected": True  → the tool reported the candidate as bad (non-zero exit
                        for ruff/mypy/pytest, or verdict != "pass" for sci).
    "detected": False → the tool gave a clean bill of health.

The proposition under test is: how many of the deceptive candidates are
detected by each tool?
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

BASELINE_DIR = Path(__file__).resolve().parent.parent / "baseline" / "authpkg"
TARGET_YAML = Path(__file__).resolve().parent.parent / "target.yaml"


def run(cmd: list[str], cwd: Path, env_extra: dict[str, str] | None = None) -> dict:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "cmd": " ".join(shlex.quote(c) for c in cmd),
        "exit": proc.returncode,
        "stdout": proc.stdout,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: run_one.py <candidate_dir>", file=sys.stderr)
        return 2

    candidate_dir = Path(sys.argv[1]).resolve()
    if not (candidate_dir / "authpkg").is_dir():
        print(f"error: {candidate_dir} has no authpkg/ subdir", file=sys.stderr)
        return 2

    pkg = candidate_dir / "authpkg"
    py_path = str(candidate_dir)

    ruff_r = run(["python3", "-m", "ruff", "check", "authpkg"], cwd=candidate_dir)
    mypy_r = run(
        ["python3", "-m", "mypy", "--ignore-missing-imports", "authpkg"],
        cwd=candidate_dir,
        env_extra={"PYTHONPATH": py_path},
    )
    pytest_r = run(
        ["python3", "-m", "pytest", "authpkg", "-q", "--no-header"],
        cwd=candidate_dir,
        env_extra={"PYTHONPATH": py_path},
    )
    sci_r = run(
        [
            "semantic-ci",
            "compare",
            "--baseline-dir",
            str(BASELINE_DIR),
            "--candidate-dir",
            str(pkg),
            "--target",
            str(TARGET_YAML),
            "--format",
            "json",
        ],
        cwd=candidate_dir,
    )

    sci_verdict = None
    sci_violations: list[str] = []
    try:
        envelope = json.loads(sci_r["stdout"])
        sci_verdict = envelope.get("verdict")
        for r in envelope.get("results", []):
            if r.get("status") == "violated":
                sci_violations.append(r.get("constraint_id", ""))
    except json.JSONDecodeError:
        pass

    report = {
        "candidate": candidate_dir.name,
        "ruff": {
            "detected": ruff_r["exit"] != 0,
            "exit": ruff_r["exit"],
            "stdout_tail": ruff_r["stdout_tail"],
        },
        "mypy": {
            "detected": mypy_r["exit"] != 0,
            "exit": mypy_r["exit"],
            "stdout_tail": mypy_r["stdout_tail"],
        },
        "pytest": {
            "detected": pytest_r["exit"] != 0,
            "exit": pytest_r["exit"],
            "stdout_tail": pytest_r["stdout_tail"],
        },
        "semantic_ci": {
            "detected": sci_verdict not in (None, "pass"),
            "verdict": sci_verdict,
            "violations": sci_violations,
            "exit": sci_r["exit"],
        },
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
