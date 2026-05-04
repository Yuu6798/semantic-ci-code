from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from semantic_ci_code.cli.command_support import (
    _engine_error,
    _exit_code_for,
    _internal_bug,
    _render_payload,
    _stderr,
    _usage_error,
    _write_output,
)
from semantic_ci_code.cli.output.json_formatter import build_payload
from semantic_ci_code.cli.target_loader import (
    TargetUsageError,
    discover_target,
    load_compiled_target,
)
from semantic_ci_code.compiler import CompileError
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.evaluator import evaluate_constraints
from semantic_ci_code.pipeline import ExtractorError, extract_python_code_state
from semantic_ci_code.repair import emit_repair_plan


def run_compare(args: Namespace) -> int:
    try:
        if args.verbose:
            _stderr("resolving target.yaml")
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)
        baseline_root = _resolve_dir(args.package_root_baseline or args.baseline_dir, "baseline")
        candidate_root = _resolve_dir(
            args.package_root_candidate or args.candidate_dir,
            "candidate",
        )

        if args.verbose:
            _stderr(f"extracting baseline package_root={baseline_root}")
        baseline = extract_python_code_state(baseline_root)
        if args.verbose:
            _stderr(f"extracting candidate package_root={candidate_root}")
        candidate = extract_python_code_state(candidate_root)
        delta = compute_code_state_delta(baseline, candidate)
        verdict = evaluate_constraints(compiled, delta, baseline=baseline, candidate=candidate)
        repair_plan = emit_repair_plan(verdict)
        payload = build_payload(
            "compare",
            compiled=compiled,
            verdict=verdict,
            repair_plan=repair_plan,
        )
        output_status = _write_output(
            _render_payload(payload, args, subcommand="compare"),
            args.output,
        )
        if output_status != 0:
            return output_status
        return _exit_code_for(verdict.result, strict_repair=args.strict_repair)
    except TargetUsageError as exc:
        return _usage_error(exc)
    except ValueError as exc:
        return _usage_error(exc)
    except OSError as exc:
        return _usage_error(exc)
    except CompileError as exc:
        return _engine_error(exc, args, show_traceback=True)
    except ExtractorError as exc:
        return _engine_error(exc, args, prefix="extractor failed", show_traceback=True)
    except Exception as exc:
        return _internal_bug(exc, args)


def _resolve_dir(raw_path: str, label: str) -> Path:
    path = Path(raw_path).resolve()
    if not path.exists():
        raise ValueError(f"{label} directory does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} path is not a directory: {path}")
    return path
