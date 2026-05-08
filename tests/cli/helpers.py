from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


@dataclass(frozen=True)
class InprocResult:
    returncode: int
    stdout: str
    stderr: str


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
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "semantic_ci_code.cli", *args],
        cwd=cwd,
        env=cli_env(hash_seed=hash_seed, extra_env=extra_env),
        input=stdin_text,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


@contextmanager
def _captured_console(stdin_text: str | None):
    saved_stdout, saved_stderr, saved_stdin = sys.stdout, sys.stderr, sys.stdin
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    sys.stdout = stdout_buffer
    sys.stderr = stderr_buffer
    if stdin_text is not None:
        sys.stdin = io.StringIO(stdin_text)
    try:
        yield stdout_buffer, stderr_buffer
    finally:
        sys.stdout = saved_stdout
        sys.stderr = saved_stderr
        sys.stdin = saved_stdin


@contextmanager
def _patched_env(extra_env: dict[str, str] | None):
    if not extra_env:
        yield
        return

    saved = {key: os.environ.get(key) for key in extra_env}
    os.environ.update(extra_env)
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_semantic_ci_inproc(
    cwd: Path,
    *args: str,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
    stdin_text: str | None = None,
) -> InprocResult:
    # PYTHONHASHSEED only takes effect at process startup. Tests that vary it
    # should call run_semantic_ci_subprocess explicitly.
    del hash_seed
    from semantic_ci_code.cli.main import main

    saved_cwd = Path.cwd()
    try:
        os.chdir(cwd)
        with _patched_env(extra_env), _captured_console(stdin_text) as (stdout, stderr):
            try:
                returncode = main(list(args))
            except SystemExit as exc:
                returncode = exc.code if isinstance(exc.code, int) else 1
        return InprocResult(returncode, stdout.getvalue(), stderr.getvalue())
    finally:
        os.chdir(saved_cwd)


def run_semantic_ci_subprocess(
    cwd: Path,
    *args: str,
    hash_seed: str = "1",
    extra_env: dict[str, str] | None = None,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return run_module(
        cwd,
        *args,
        hash_seed=hash_seed,
        extra_env=extra_env,
        stdin_text=stdin_text,
    )


run_semantic_ci = run_semantic_ci_inproc


def parse_json(stdout: str) -> dict:
    return json.loads(stdout)


def payload(result: subprocess.CompletedProcess[str]) -> dict:
    return parse_json(result.stdout)


def strip_ansi(text: str) -> str:
    return ANSI_RE.sub("", text)
