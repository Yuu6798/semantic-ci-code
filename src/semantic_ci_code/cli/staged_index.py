from __future__ import annotations

import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from semantic_ci_code.cli.git_runtime import run_git


@contextmanager
def export_staged_index(repo_root: Path, *, prefix: str) -> Iterator[Path]:
    """Materialize the current staged index into a temporary directory."""

    with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
        export_root = Path(temp_dir)
        run_git(
            ["checkout-index", f"--prefix={export_root.as_posix()}/", "-a"],
            cwd=repo_root,
        )
        yield export_root
