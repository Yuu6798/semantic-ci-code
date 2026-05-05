from __future__ import annotations

from argparse import Namespace
from contextlib import nullcontext
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
from semantic_ci_code.cli.git_diff import numstat_range
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
from semantic_ci_code.cli.modes import dimensions_for_mode, resolve_execution_mode
from semantic_ci_code.cli.output.json_formatter import build_payload
from semantic_ci_code.cli.target_loader import (
    TargetUsageError,
    discover_target,
    load_compiled_target,
)
from semantic_ci_code.cli.worktree import materialize_ref
from semantic_ci_code.compiler import CompileError
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.evaluator import evaluate_constraints
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
        mode = resolve_execution_mode(args.mode)
        dimensions = dimensions_for_mode(mode)
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
                baseline = extract_python_code_state(baseline_root, dimensions=dimensions)
                if args.verbose:
                    _stderr(f"extracting candidate package_root={candidate_root}")
                candidate = extract_python_code_state(candidate_root, dimensions=dimensions)

        delta = compute_code_state_delta(baseline, candidate)
        entries = (
            numstat_range(root, baseline_ref)
            if args.allow_dirty
            else numstat_range(root, baseline_ref, candidate_ref)
        )
        files_touched, loc_delta = summarize_numstat(entries)
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
            "check",
            compiled=compiled,
            verdict=verdict,
            repair_plan=repair_plan,
            files_touched=files_touched,
            loc_delta=loc_delta,
            mode=mode.value,
        )
        output_status = _write_output(
            _render_payload(payload, args, subcommand="check"), args.output
        )
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
