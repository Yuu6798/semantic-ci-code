from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from semantic_ci_code.cli.exit_codes import FAIL, SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.output import dump_json, format_human, resolve_format, use_color
from semantic_ci_code.evaluator import VerdictResult


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _one_line(message: str) -> str:
    return message.splitlines()[0] if message else ""


def _write_output(output: str, target: str | None) -> int:
    if target is None:
        print(output, end="")
        return SUCCESS
    path = Path(target)
    try:
        path.write_text(output, encoding="utf-8")
    except OSError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    return SUCCESS


def _exit_code_for(result: VerdictResult, *, strict_repair: bool) -> int:
    if result is VerdictResult.FAIL:
        return FAIL
    if result is VerdictResult.REPAIR and strict_repair:
        return FAIL
    return SUCCESS


def _render_payload(
    payload: dict[str, Any],
    args: Any,
    *,
    subcommand: str,
    human_renderer: Callable[..., str] = format_human,
) -> str:
    output_format = resolve_format(args.format, args.output, subcommand=subcommand)
    if output_format == "json":
        return dump_json(payload)
    return human_renderer(payload, use_color=use_color(getattr(args, "no_color", False)))
