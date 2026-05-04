from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def cli_env(
    *,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = hash_seed
    env["PYTHONPATH"] = str(SRC_ROOT)
    if extra_env:
        env.update(extra_env)
    return env


def run_console(
    cwd: Path,
    *args: str,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["semantic-ci", *args],
        cwd=cwd,
        env=cli_env(hash_seed=hash_seed, extra_env=extra_env),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def run_module(
    cwd: Path,
    *args: str,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "semantic_ci_code.cli", *args],
        cwd=cwd,
        env=cli_env(hash_seed=hash_seed, extra_env=extra_env),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def run_semantic_ci(
    cwd: Path,
    *args: str,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_module(cwd, *args, hash_seed=hash_seed, extra_env=extra_env)


def parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    return parse_json(result.stdout)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)
