from __future__ import annotations

import tempfile
from argparse import Namespace
from collections.abc import Iterator
from contextlib import contextmanager
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
from semantic_ci_code.cli.delta_overlay import overlay_delta, summarize_numstat
from semantic_ci_code.cli.git_diff import numstat_cached, staged_paths
from semantic_ci_code.cli.git_runtime import (
    GitCommandError,
    GitConfigError,
    GitError,
    GitNotFoundError,
    is_git_available,
    repo_root,
    run_git,
)
from semantic_ci_code.cli.modes import dimensions_for_mode, resolve_execution_mode
from semantic_ci_code.cli.output.json_formatter import build_payload
from semantic_ci_code.cli.target_loader import (
    TargetUsageError,
    discover_target,
    load_compiled_target,
)
from semantic_ci_code.cli.worktree import materialize_ref
from semantic_ci_code.compiler import CompiledTarget, CompileError
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.evaluator import Verdict, VerdictResult, evaluate_constraints
from semantic_ci_code.pipeline import ExtractorError, extract_python_code_state
from semantic_ci_code.repair import RepairPlan, emit_repair_plan


def run_pre_commit(args: Namespace) -> int:
    try:
        if not is_git_available():
            raise GitNotFoundError("git is required for 'pre-commit'; install git")

        root = repo_root(Path.cwd())
        package_root = _package_root_relative(args.package_root)
        mode = resolve_execution_mode(args.mode)
        dimensions = dimensions_for_mode(mode)
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)

        if not staged_paths(root):
            return _emit_empty_pass(args, compiled=compiled, mode=mode.value)

        entries = numstat_cached(root)
        files_touched, loc_delta = summarize_numstat(entries)

        with materialize_ref(root, "HEAD", prefix="semantic-ci-baseline-") as baseline_dir:
            with _export_index(root, prefix="semantic-ci-candidate-") as candidate_dir:
                baseline_root = _resolve_package_root(baseline_dir, package_root, "baseline")
                candidate_root = _resolve_package_root(candidate_dir, package_root, "candidate")
                if args.verbose:
                    _stderr(f"extracting baseline package_root={baseline_root}")
                baseline = extract_python_code_state(baseline_root, dimensions=dimensions)
                if args.verbose:
                    _stderr(f"extracting candidate package_root={candidate_root}")
                candidate = extract_python_code_state(candidate_root, dimensions=dimensions)

        delta = compute_code_state_delta(baseline, candidate)
        delta = overlay_delta(delta, files_touched=files_touched, loc_delta=loc_delta)
        verdict = evaluate_constraints(
            compiled,
            delta,
            baseline=baseline,
            candidate=candidate,
            extracted_dimensions=dimensions,
        )
        repair_plan = emit_repair_plan(verdict)
        payload = build_payload(
            "pre-commit",
            compiled=compiled,
            verdict=verdict,
            repair_plan=repair_plan,
            files_touched=files_touched,
            loc_delta=loc_delta,
            mode=mode.value,
        )
        output_status = _render_and_write(payload, args)
        if output_status != 0:
            return output_status
        return _exit_code_for(verdict.result, strict_repair=args.strict_repair)
    except TargetUsageError as exc:
        return _usage_error(exc)
    except ValueError as exc:
        return _usage_error(exc)
    except CompileError as exc:
        return _engine_error(exc, args, show_traceback=True)
    except ExtractorError as exc:
        return _engine_error(exc, args, prefix="extractor failed", show_traceback=True)
    except GitNotFoundError as exc:
        return _engine_error(exc, args)
    except GitConfigError as exc:
        return _engine_error(exc, args)
    except GitCommandError as exc:
        return _engine_error(exc, args, show_traceback=True)
    except GitError as exc:
        return _engine_error(exc, args)
    except Exception as exc:
        return _internal_bug(exc, args)


@contextmanager
def _export_index(repo_root: Path, *, prefix: str) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix=prefix) as temp_dir:
        export_root = Path(temp_dir)
        run_git(
            ["checkout-index", f"--prefix={export_root.as_posix()}/", "-a"],
            cwd=repo_root,
        )
        yield export_root


def _emit_empty_pass(args: Namespace, *, compiled: CompiledTarget, mode: str) -> int:
    verdict = Verdict(result=VerdictResult.PASS, results=())
    repair_plan = RepairPlan(result=VerdictResult.PASS, instructions=())
    payload = build_payload(
        "pre-commit",
        compiled=compiled,
        verdict=verdict,
        repair_plan=repair_plan,
        mode=mode,
    )
    return _render_and_write(payload, args)


def _render_and_write(payload: dict, args: Namespace) -> int:
    return _write_output(_render_payload(payload, args, subcommand="pre-commit"), args.output)


def _package_root_relative(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        raise ValueError(f"package_root must be repo-relative for pre-commit: {path}")
    return path


def _resolve_package_root(tree_root: Path, package_root: Path, label: str) -> Path:
    path = (tree_root / package_root).resolve()
    if not path.exists():
        raise ValueError(f"{label} package_root does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} package_root is not a directory: {path}")
    return path
