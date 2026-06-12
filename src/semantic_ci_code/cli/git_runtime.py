from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


class GitError(Exception):
    """Base class for expected git runtime failures."""


class GitNotFoundError(GitError):
    """The git executable is unavailable."""


class GitCommandError(GitError):
    """A git subprocess failed."""

    def __init__(
        self,
        args_or_message: list[str] | str,
        *,
        cwd: Path | None = None,
        returncode: int | None = None,
        stderr: str = "",
    ) -> None:
        if isinstance(args_or_message, str) and cwd is None and returncode is None:
            self.args_list: tuple[str, ...] = ()
            self.cwd = None
            self.returncode = None
            self.stderr = ""
            super().__init__(args_or_message)
            return

        if not isinstance(args_or_message, list) or cwd is None or returncode is None:
            raise TypeError("GitCommandError requires git args, cwd, returncode, and stderr")
        self.args_list = tuple(args_or_message)
        self.cwd = cwd
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(self._message())

    def _message(self) -> str:
        command = "git " + " ".join(self.args_list)
        detail = _one_line(self.stderr)[:200]
        if detail:
            return f"{command} failed with exit {self.returncode}: {detail}"
        return f"{command} failed with exit {self.returncode}"


class GitConfigError(GitError):
    """Repository configuration cannot satisfy the requested check."""

    def __init__(self, message: str, *, tried: tuple[str, ...] = ()) -> None:
        self.tried = tried
        super().__init__(message)


class GitRefError(GitError, ValueError):
    """A user-supplied git ref is empty or option-like.

    Subclasses ValueError so commands that route ValueError to a usage error
    (exit 2) keep that mapping, while GitError-only handlers (target-doctor's
    documented exit-3 git path) also stay correct.
    """


def ensure_safe_ref(ref: str) -> str:
    """Reject refs that git would parse as command-line options.

    Refs are passed to git as positional argv elements, so a leading-dash
    value (e.g. ``--upload-pack=...``) would be consumed as a flag instead of
    a revision. Refuse such values before any subprocess is spawned.
    """

    if not ref or ref.startswith("-"):
        raise GitRefError(
            f"invalid git ref {ref!r}: refs must be non-empty and must not begin with '-'"
        )
    return ref


def is_git_available() -> bool:
    return shutil.which("git") is not None


def run_git(
    args: list[str],
    *,
    cwd: Path,
    timeout: float | None = 30,
    check: bool = True,
) -> str:
    _record_command(args, cwd=cwd)
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GitNotFoundError("git is required for 'check'; install git or use 'compare'") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitCommandError(
            args,
            cwd=cwd,
            returncode=124,
            stderr=f"timed out after {timeout} seconds",
        ) from exc

    if check and completed.returncode != 0:
        raise GitCommandError(
            args,
            cwd=cwd,
            returncode=completed.returncode,
            stderr=completed.stderr,
        )
    return completed.stdout


def ref_exists(ref: str, *, cwd: Path) -> bool:
    ensure_safe_ref(ref)
    try:
        run_git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd=cwd, check=True)
    except GitCommandError:
        return False
    return True


def repo_root(cwd: Path) -> Path:
    output = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    return Path(output.strip()).resolve()


def blob_text(ref: str, path: str, *, cwd: Path) -> str | None:
    """Return the file content at `ref:path`, or None when absent.

    `path` must be repo-relative posix form. The ref is validated; a
    missing path at the ref (added/deleted file on one diff side) is the
    expected miss and maps to None rather than an error.
    """
    ensure_safe_ref(ref)
    try:
        return run_git(["show", f"{ref}:{path}"], cwd=cwd)
    except GitCommandError:
        return None


def tree_object_id(ref: str, subpath: str, *, cwd: Path) -> str:
    ensure_safe_ref(ref)
    spec = f"{ref}^{{tree}}" if subpath == "." else f"{ref}:{subpath}"
    output = run_git(["rev-parse", "--verify", spec], cwd=cwd)
    lines = tuple(line for line in output.splitlines() if line)
    if len(lines) != 1:
        raise GitCommandError(f"git rev-parse produced {len(lines)} object ids for {spec}")
    return lines[0]


def staged_tree_object_id(cwd: Path) -> str:
    output = run_git(["write-tree"], cwd=cwd)
    lines = tuple(line for line in output.splitlines() if line)
    if len(lines) != 1:
        raise GitCommandError(f"git write-tree produced {len(lines)} object ids")
    return lines[0]


def is_dirty(cwd: Path) -> bool:
    return bool(run_git(["status", "--porcelain"], cwd=cwd).strip())


def resolve_baseline(
    explicit: str | None,
    *,
    repo_root: Path,
    no_fetch: bool,
) -> str:
    if explicit is not None:
        return ensure_safe_ref(explicit)

    tried = ("origin/main", "main", "master")
    if not no_fetch:
        run_git(["fetch", "--quiet", "origin", "main"], cwd=repo_root, timeout=60, check=False)

    for ref in tried:
        if ref_exists(ref, cwd=repo_root):
            return ref

    if not no_fetch:
        run_git(
            ["fetch", "--depth=1", "origin", "main:refs/remotes/origin/main"],
            cwd=repo_root,
            timeout=60,
            check=False,
        )
        if ref_exists("origin/main", cwd=repo_root):
            return "origin/main"

    raise GitConfigError(
        "could not resolve baseline ref; tried origin/main, main, master",
        tried=tried,
    )


def resolve_candidate(explicit: str | None) -> str:
    if explicit is not None:
        return ensure_safe_ref(explicit)
    return "HEAD"


def _record_command(args: list[str], *, cwd: Path) -> None:
    log_path = os.environ.get("SEMANTIC_CI_GIT_COMMAND_LOG")
    if not log_path:
        return
    record = {"cwd": str(cwd), "args": ["git", *args]}
    with Path(log_path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, sort_keys=True) + "\n")


def _one_line(message: str) -> str:
    return message.splitlines()[0] if message else ""
