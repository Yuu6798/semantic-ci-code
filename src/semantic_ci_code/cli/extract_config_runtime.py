from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from semantic_ci_code.cli.command_support import stderr
from semantic_ci_code.framework.extract_config import (
    ExcludedPath,
    ExtractConfig,
    load_extract_config,
)

ExcludeReporter = Callable[[tuple[ExcludedPath, ...]], None]


def load_extract_config_for_cli(package_root: Path, args: Any) -> ExtractConfig:
    config = load_extract_config(package_root)
    if getattr(args, "verbose", False):
        if config.source_path is None:
            stderr("loaded extract config: 0 patterns (no pyproject.toml)")
        else:
            stderr(
                f"loaded extract config: {len(config.patterns)} patterns from {config.source_path}"
            )
    return config


def make_exclude_reporter(args: Any) -> ExcludeReporter | None:
    if not getattr(args, "verbose", False):
        return None

    def report(excluded: tuple[ExcludedPath, ...]) -> None:
        stderr(f"excluded by config: {len(excluded)} files")
        for item in excluded[:10]:
            stderr(f"  {item.relative_path.as_posix()} (matched: {item.pattern})")
        remaining = len(excluded) - 10
        if remaining > 0:
            stderr(f"  ... {remaining} more excluded files")

    return report
