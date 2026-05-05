from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from semantic_ci_code.cli.command_support import (
    _engine_error,
    _internal_bug,
    _render_payload,
    _usage_error,
    _write_output,
)
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
        if args.format in {"sarif", "gh-actions"}:
            raise ValueError(f"{args.format} format is not supported for compile")
        if args.target is not None and args.target_path is not None:
            raise ValueError("pass target either positionally or with --target, not both")
        target_path = discover_target(args.target or args.target_path, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)
        payload = build_compile_payload(compiled)
        output = _render_payload(
            payload,
            args,
            subcommand="compile",
            human_renderer=format_compile_human,
        )
        return _write_output(output, args.output)
    except TargetUsageError as exc:
        return _usage_error(exc)
    except ValueError as exc:
        return _usage_error(exc)
    except OSError as exc:
        return _usage_error(exc)
    except CompileError as exc:
        return _engine_error(exc, args, show_traceback=True)
    except Exception as exc:
        return _internal_bug(exc, args)
