"""Shared utilities for target-doctor advisory package-root handling."""

from __future__ import annotations

from pathlib import Path

from semantic_ci_code.cli.git_runtime import GitError, is_git_available, repo_root


class PackageRootError(ValueError):
    """Rejected --package-root value for advisory detection."""


def resolve_package_root(raw: str | None) -> Path:
    """Resolve and validate --package-root for advisory detection.

    The advisor surface treats --package-root as repo-relative when invoked
    inside a git repository, and cwd-relative otherwise so target-doctor remains
    useful outside git.
    """

    raw_path = Path(raw or ".")
    if raw_path.is_absolute() or raw_path.drive:
        raise PackageRootError(f"--package-root must be relative: {raw_path}")

    parts: list[str] = []
    for part in raw_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise PackageRootError(f"--package-root must stay within repo: {raw_path}")
            parts.pop()
            continue
        parts.append(part)
    normalized = Path(*parts) if parts else Path(".")

    base = Path.cwd()
    if is_git_available():
        try:
            base = repo_root(Path.cwd())
        except GitError:
            base = Path.cwd()

    resolved_base = base.resolve()
    candidate = (resolved_base / normalized).resolve()
    if not candidate.is_relative_to(resolved_base):
        raise PackageRootError(f"--package-root escapes repo root via symlink: {candidate}")
    if not candidate.exists():
        raise PackageRootError(f"--package-root does not exist: {candidate}")
    if not candidate.is_dir():
        raise PackageRootError(f"--package-root is not a directory: {candidate}")
    return candidate
