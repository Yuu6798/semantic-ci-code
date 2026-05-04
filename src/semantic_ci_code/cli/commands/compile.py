from __future__ import annotations

import sys
import traceback
from argparse import Namespace
from pathlib import Path

from semantic_ci_code.cli.exit_codes import ENGINE_ERROR, INTERNAL_BUG, SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.output import dump_json, resolve_format, use_color
from semantic_ci_code.cli.output.human_formatter import format_compile_human
from semantic_ci_code.cli.output.json_formatter import build_compile_payload
from semantic_ci_code.cli.target_loader import (
    TargetUsageError,
    discover_target,
    load_compiled_target,
)
from semantic_ci_code.compiler import CompileError


def run_compile(args: Namespace) -> int:
    try:
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)
        payload = build_compile_payload(compiled)
        output_format = resolve_format(args.format, args.output, subcommand="compile")
        output = (
            dump_json(payload)
            if output_format == "json"
            else format_compile_human(payload, use_color=use_color(args.no_color))
        )
        return _write_output(output, args.output)
    except TargetUsageError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except ValueError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except OSError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except CompileError as exc:
        _stderr(_one_line(str(exc)))
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return ENGINE_ERROR
    except Exception as exc:
        _stderr(f"internal error: {_one_line(str(exc))}; rerun with --verbose for traceback")
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return INTERNAL_BUG


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


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _one_line(message: str) -> str:
    return message.splitlines()[0] if message else ""
