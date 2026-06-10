from __future__ import annotations

import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from semantic_ci_code.cli.git_runtime import GitCommandError, ensure_safe_ref, run_git


@contextmanager
def materialize_ref(repo_root: Path, ref: str, *, prefix: str) -> Iterator[Path]:
    ensure_safe_ref(ref)
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
        worktree_path = Path(temp_dir)
        run_git(
            ["worktree", "add", "--detach", str(worktree_path), ref],
            cwd=repo_root,
            timeout=None,
        )
        try:
            yield worktree_path
        finally:
            try:
                run_git(
                    ["worktree", "remove", "--force", str(worktree_path)],
                    cwd=repo_root,
                    timeout=None,
                )
            except GitCommandError as exc:
                print(
                    f"warning: failed to remove git worktree {worktree_path}: {exc}",
                    file=sys.stderr,
                )
