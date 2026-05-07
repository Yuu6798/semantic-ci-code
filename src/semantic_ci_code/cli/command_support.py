from __future__ import annotations

import sys
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from semantic_ci_code.cli.exit_codes import ENGINE_ERROR, FAIL, INTERNAL_BUG, SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.output import dump_json, format_human, resolve_format, use_color
from semantic_ci_code.cli.output_gh_actions import format_gh_actions
from semantic_ci_code.cli.output_sarif import format_sarif
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
    if output_format == "sarif":
        return format_sarif(payload)
    if output_format == "gh-actions":
        if args.output is not None:
            raise ValueError("gh-actions format does not support --output")
        return format_gh_actions(payload)
    return human_renderer(payload, use_color=use_color(getattr(args, "no_color", False)))


def _usage_error(exc: BaseException) -> int:
    _stderr(_one_line(str(exc)))
    return USAGE_ERROR


def _engine_error(
    exc: BaseException,
    args: Any,
    *,
    prefix: str | None = None,
    show_traceback: bool = False,
) -> int:
    message = _one_line(str(exc))
    if prefix:
        message = f"{prefix}: {message}"
    _stderr(message)
    if show_traceback and args.verbose:
        traceback.print_exc(file=sys.stderr)
    return ENGINE_ERROR


def _internal_bug(exc: BaseException, args: Any) -> int:
    _stderr(f"internal error: {_one_line(str(exc))}; rerun with --verbose for traceback")
    if args.verbose:
        traceback.print_exc(file=sys.stderr)
    return INTERNAL_BUG


stderr = _stderr
one_line = _one_line
write_output = _write_output
exit_code_for = _exit_code_for
render_payload = _render_payload
usage_error = _usage_error
engine_error = _engine_error
internal_bug = _internal_bug

__all__ = [
    "engine_error",
    "exit_code_for",
    "internal_bug",
    "one_line",
    "render_payload",
    "stderr",
    "usage_error",
    "write_output",
]
