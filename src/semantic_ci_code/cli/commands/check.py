from __future__ import annotations

import sys
import traceback
from argparse import Namespace
from contextlib import nullcontext
from pathlib import Path

from semantic_ci_code.cli.exit_codes import (
    ENGINE_ERROR,
    FAIL,
    INTERNAL_BUG,
    SUCCESS,
    USAGE_ERROR,
)
from semantic_ci_code.cli.git_runtime import (
    GitCommandError,
    GitConfigError,
    GitError,
    GitNotFoundError,
    is_dirty,
    is_git_available,
    repo_root,
    resolve_baseline,
    resolve_candidate,
)
from semantic_ci_code.cli.output import dump_json, format_human, resolve_format, use_color
from semantic_ci_code.cli.output.json_formatter import build_payload
from semantic_ci_code.cli.target_loader import (
    TargetUsageError,
    discover_target,
    load_compiled_target,
)
from semantic_ci_code.cli.worktree import materialize_ref
from semantic_ci_code.compiler import CompileError
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.evaluator import VerdictResult, evaluate_constraints
from semantic_ci_code.pipeline import ExtractorError, extract_python_code_state
from semantic_ci_code.repair import emit_repair_plan


def run_check(args: Namespace) -> int:
    try:
        if not is_git_available():
            raise GitNotFoundError("git is required for 'check'; install git or use 'compare'")

        root = repo_root(Path.cwd())
        baseline_ref = resolve_baseline(
            args.baseline_rev,
            repo_root=root,
            no_fetch=args.no_fetch,
        )
        candidate_ref = resolve_candidate(args.candidate_rev)
        package_root = _package_root_relative(args.package_root)
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)

        if args.verbose:
            _stderr(f"resolved baseline={baseline_ref} candidate={candidate_ref}")
        if not args.allow_dirty and candidate_ref == "HEAD" and is_dirty(root):
            _stderr(
                "working tree is dirty; using HEAD commit. "
                "pass --allow-dirty to evaluate working directory."
            )

        with materialize_ref(root, baseline_ref, prefix="semantic-ci-baseline-") as baseline_dir:
            candidate_context = (
                nullcontext(root)
                if args.allow_dirty
                else materialize_ref(root, candidate_ref, prefix="semantic-ci-candidate-")
            )
            with candidate_context as candidate_dir:
                baseline_root = _resolve_package_root(baseline_dir, package_root, "baseline")
                candidate_root = _resolve_package_root(candidate_dir, package_root, "candidate")
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
            "check",
            compiled=compiled,
            verdict=verdict,
            repair_plan=repair_plan,
        )
        output_format = resolve_format(args.format, args.output, subcommand="check")
        output = (
            dump_json(payload)
            if output_format == "json"
            else format_human(payload, use_color=use_color(args.no_color))
        )
        output_status = _write_output(output, args.output)
        if output_status != SUCCESS:
            return output_status
        return _exit_code_for(verdict.result, strict_repair=args.strict_repair)
    except TargetUsageError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except ValueError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except CompileError as exc:
        _stderr(_one_line(str(exc)))
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return ENGINE_ERROR
    except ExtractorError as exc:
        _stderr(f"extractor failed: {_one_line(str(exc))}")
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return ENGINE_ERROR
    except GitNotFoundError as exc:
        _stderr(_one_line(str(exc)))
        return ENGINE_ERROR
    except GitConfigError as exc:
        _stderr(_one_line(str(exc)))
        return ENGINE_ERROR
    except GitCommandError as exc:
        _stderr(_one_line(str(exc)))
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return ENGINE_ERROR
    except GitError as exc:
        _stderr(_one_line(str(exc)))
        return ENGINE_ERROR
    except Exception as exc:
        _stderr(f"internal error: {_one_line(str(exc))}; rerun with --verbose for traceback")
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return INTERNAL_BUG


def _package_root_relative(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"package_root must be repo-relative for check: {path}")
    return path


def _resolve_package_root(tree_root: Path, package_root: Path, label: str) -> Path:
    path = (tree_root / package_root).resolve()
    if not path.exists():
        raise ValueError(f"{label} package_root does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} package_root is not a directory: {path}")
    return path


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


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _one_line(message: str) -> str:
    return message.splitlines()[0] if message else ""
