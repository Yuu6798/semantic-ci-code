from __future__ import annotations

import tempfile
from argparse import Namespace
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from semantic_ci_code.cli.code_state_cache import (
    CacheStats,
    cache_disabled,
    current_python_xy,
    dimensions_for_cache,
    key_for_state,
    key_meta,
    package_root_cache_path,
    read_cached_code_state,
    resolve_cache_max_bytes,
    resolve_cache_root,
    write_cached_code_state,
)
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
    staged_tree_object_id,
    tree_object_id,
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
        dimensions_tuple = dimensions_for_cache(dimensions)
        use_cache = not cache_disabled(no_cache_flag=args.no_cache)
        cache_root = resolve_cache_root(args.cache_dir, repo_root=root, cwd=Path.cwd())
        cache_max_bytes = resolve_cache_max_bytes(args.cache_max_bytes) if use_cache else 0
        cache_stats = CacheStats(disabled=not use_cache)
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)

        if not staged_paths(root):
            return _emit_empty_pass(
                args,
                compiled=compiled,
                mode=mode.value,
                cache_stats=cache_stats,
            )

        entries = numstat_cached(root)
        files_touched, loc_delta = summarize_numstat(entries)
        staged_tree = staged_tree_object_id(root)

        with materialize_ref(root, "HEAD", prefix="semantic-ci-baseline-") as baseline_dir:
            with _export_index(root, prefix="semantic-ci-candidate-") as candidate_dir:
                baseline_root = _resolve_package_root(baseline_dir, package_root, "baseline")
                candidate_root = _resolve_package_root(candidate_dir, package_root, "candidate")
                if args.verbose:
                    _stderr(f"extracting baseline package_root={baseline_root}")
                baseline = _extract_code_state(
                    package_root=package_root,
                    resolved_package_root=baseline_root,
                    repo_root=root,
                    ref="HEAD",
                    mode=mode,
                    dimensions=dimensions,
                    dimensions_tuple=dimensions_tuple,
                    cache_root=cache_root,
                    use_cache=use_cache,
                    cache_stats=cache_stats,
                    cache_max_bytes=cache_max_bytes,
                    verbose=args.verbose,
                )
                if args.verbose:
                    _stderr(f"extracting candidate package_root={candidate_root}")
                candidate = _extract_code_state(
                    package_root=package_root,
                    resolved_package_root=candidate_root,
                    repo_root=root,
                    ref=staged_tree,
                    mode=mode,
                    dimensions=dimensions,
                    dimensions_tuple=dimensions_tuple,
                    cache_root=cache_root,
                    use_cache=use_cache,
                    cache_stats=cache_stats,
                    cache_max_bytes=cache_max_bytes,
                    verbose=args.verbose,
                )

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
            cache_stats=cache_stats,
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


def _emit_empty_pass(
    args: Namespace,
    *,
    compiled: CompiledTarget,
    mode: str,
    cache_stats: CacheStats,
) -> int:
    verdict = Verdict(result=VerdictResult.PASS, results=())
    repair_plan = RepairPlan(result=VerdictResult.PASS, instructions=())
    payload = build_payload(
        "pre-commit",
        compiled=compiled,
        verdict=verdict,
        repair_plan=repair_plan,
        mode=mode,
        cache_stats=cache_stats,
    )
    return _render_and_write(payload, args)


def _render_and_write(payload: dict, args: Namespace) -> int:
    return _write_output(_render_payload(payload, args, subcommand="pre-commit"), args.output)


def _package_root_relative(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute() or path.drive:
        raise ValueError(f"package_root must be repo-relative for pre-commit: {path}")
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError(f"package_root must stay within repo for pre-commit: {path}")
            parts.pop()
            continue
        parts.append(part)
    return Path(*parts) if parts else Path(".")


def _resolve_package_root(tree_root: Path, package_root: Path, label: str) -> Path:
    resolved_tree_root = tree_root.resolve()
    path = (resolved_tree_root / package_root).resolve()
    if not path.is_relative_to(resolved_tree_root):
        raise ValueError(f"{label} package_root escapes tree: {path}")
    if not path.exists():
        raise ValueError(f"{label} package_root does not exist: {path}")
    if not path.is_dir():
        raise ValueError(f"{label} package_root is not a directory: {path}")
    return path


def _extract_code_state(
    *,
    package_root: Path,
    resolved_package_root: Path,
    repo_root: Path,
    ref: str,
    mode,
    dimensions: frozenset[str] | None,
    dimensions_tuple: tuple[str, ...] | None,
    cache_root: Path,
    use_cache: bool,
    cache_stats: CacheStats,
    cache_max_bytes: int,
    verbose: bool,
):
    if not use_cache:
        return extract_python_code_state(resolved_package_root, dimensions=dimensions)

    package_root_posix = package_root_cache_path(package_root)
    tree_id = tree_object_id(ref, package_root_posix.as_posix(), cwd=repo_root)
    python_xy = current_python_xy()
    key = key_for_state(
        tree_object_id=tree_id,
        package_root_relpath_posix=package_root_posix,
        mode=mode,
        dimensions_sorted_tuple=dimensions_tuple,
        python_xy=python_xy,
    )
    log = _stderr if verbose else None
    cached = read_cached_code_state(cache_root, key, stats=cache_stats, log=log)
    if cached is not None:
        return cached

    state = extract_python_code_state(resolved_package_root, dimensions=dimensions)
    write_cached_code_state(
        cache_root,
        key,
        state=state,
        meta=key_meta(
            tree_object_id=tree_id,
            package_root_relpath_posix=package_root_posix,
            mode=mode,
            dimensions_sorted_tuple=dimensions_tuple,
            python_xy=python_xy,
        ),
        stats=cache_stats,
        max_bytes=cache_max_bytes,
        log=log,
    )
    return state
