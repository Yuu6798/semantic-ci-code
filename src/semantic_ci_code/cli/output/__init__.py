from __future__ import annotations

import os
import sys
from pathlib import Path

from semantic_ci_code.cli.output.human_formatter import format_human
from semantic_ci_code.cli.output.json_formatter import dump_json

__all__ = [
    "dump_json",
    "format_human",
    "resolve_format",
    "use_color",
]


def resolve_format(
    explicit: str | None,
    output_path: str | Path | None,
    *,
    subcommand: str,
) -> str:
    if explicit:
        return explicit
    if output_path is not None:
        return "json"
    if subcommand == "observe":
        return "json"
    return "human" if sys.stdout.isatty() else "json"


def use_color(no_color_flag: bool) -> bool:
    if no_color_flag:
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty()
