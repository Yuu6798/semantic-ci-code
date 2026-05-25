from __future__ import annotations

from argparse import Namespace
from contextlib import nullcontext
from pathlib import Path

from semantic_ci_code.cli.code_state_cache import (
    CacheStats,
    cache_disabled,
    current_python_xy,
    dimensions_for_cache,
    effective_exclude_key,
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
from semantic_ci_code.cli.extract_config_runtime import (
    load_extract_config_for_cli,
    make_exclude_reporter,
)
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
    run_git,
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
from semantic_ci_code.compiler import CompileError
from semantic_ci_code.delta import compute_code_state_delta
from semantic_ci_code.evaluator import evaluate_constraints
from semantic_ci_code.framework.extract_config import ExtractConfig, ExtractConfigError
from semantic_ci_code.pipeline import ExtractorError, extract_python_code_state
from semantic_ci_code.repair import emit_repair_plan


def run_check(args: Namespace) -> int:
    try:
        candidate_source = args.candidate_source
        candidate_uses_working_tree = candidate_source == "working-tree"
        candidate_rev_explicit = args.candidate_rev is not None
        if candidate_uses_working_tree and candidate_rev_explicit:
            return _usage_error(
                ValueError(
                    "error: --candidate-source=working-tree is incompatible with --candidate-rev"
                )
            )

        if not is_git_available():
            raise GitNotFoundError("git is required for 'check'; install git or use 'compare'")

        root = repo_root(Path.cwd())
        baseline_ref = resolve_baseline(
            args.baseline_rev,
            repo_root=root,
            no_fetch=args.no_fetch,
        )
        candidate_ref = resolve_candidate(args.candidate_rev)
        baseline_rev = _resolve_commit_sha(root, baseline_ref)
        candidate_rev = (
            None if candidate_uses_working_tree else _resolve_commit_sha(root, candidate_ref)
        )
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

        if args.verbose:
            _stderr(f"resolved baseline={baseline_ref} candidate={candidate_ref}")
        if candidate_uses_working_tree and args.verbose and not is_dirty(root):
            _stderr(
                "note: candidate source = working tree (no uncommitted changes "
                "detected; equivalent to HEAD)."
            )

        with materialize_ref(root, baseline_ref, prefix="semantic-ci-baseline-") as baseline_dir:
            candidate_context = (
                nullcontext(root)
                if candidate_uses_working_tree
                else materialize_ref(root, candidate_ref, prefix="semantic-ci-candidate-")
            )
            with candidate_context as candidate_dir:
                baseline_root = _resolve_package_root(baseline_dir, package_root, "baseline")
                candidate_root = _resolve_package_root(candidate_dir, package_root, "candidate")
                baseline_config = load_extract_config_for_cli(
                    baseline_root,
                    args,
                    search_boundary=baseline_dir,
                )
                candidate_config = load_extract_config_for_cli(
                    candidate_root,
                    args,
                    search_boundary=candidate_dir,
                )
                if args.verbose:
                    _stderr(f"extracting baseline package_root={baseline_root}")
                baseline = _extract_code_state(
                    package_root=package_root,
                    resolved_package_root=baseline_root,
                    tree_root=baseline_dir,
                    extract_config=baseline_config,
                    repo_root=root,
                    ref=baseline_ref,
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
                    tree_root=candidate_dir,
                    extract_config=candidate_config,
                    repo_root=root,
                    ref=candidate_ref,
                    mode=mode,
                    dimensions=dimensions,
                    dimensions_tuple=dimensions_tuple,
                    cache_root=cache_root,
                    use_cache=use_cache and not candidate_uses_working_tree,
                    cache_stats=cache_stats,
                    cache_max_bytes=cache_max_bytes,
                    verbose=args.verbose,
                )

        delta = compute_code_state_delta(baseline, candidate)
        entries = (
            numstat_range(root, baseline_ref)
            if candidate_uses_working_tree
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
            cache_stats=cache_stats,
            baseline_source="commit",
            baseline_rev=baseline_rev,
            candidate_source=candidate_source,
            candidate_rev=candidate_rev,
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
    except ExtractConfigError as exc:
        return _engine_error(exc, args, prefix="extract config error", show_traceback=True)
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
    if path.is_absolute() or path.drive:
        raise ValueError(f"package_root must be repo-relative for check: {path}")
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError(f"package_root must stay within repo for check: {path}")
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


def _resolve_commit_sha(repo_root: Path, ref: str) -> str:
    return run_git(["rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=repo_root).strip()


def _extract_code_state(
    *,
    package_root: Path,
    resolved_package_root: Path,
    tree_root: Path,
    extract_config: ExtractConfig,
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
        return extract_python_code_state(
            resolved_package_root,
            dimensions=dimensions,
            extract_config=extract_config,
            exclude_reporter=make_exclude_reporter(Namespace(verbose=verbose)),
        )

    package_root_posix = package_root_cache_path(package_root)
    tree_id = tree_object_id(ref, package_root_posix.as_posix(), cwd=repo_root)
    python_xy = current_python_xy()
    exclude_key = effective_exclude_key(extract_config, tree_root=tree_root)
    key = key_for_state(
        tree_object_id=tree_id,
        package_root_relpath_posix=package_root_posix,
        mode=mode,
        dimensions_sorted_tuple=dimensions_tuple,
        effective_exclude_key_value=exclude_key,
        python_xy=python_xy,
    )
    log = _stderr if verbose else None
    cached = read_cached_code_state(cache_root, key, stats=cache_stats, log=log)
    if cached is not None:
        return cached

    state = extract_python_code_state(
        resolved_package_root,
        dimensions=dimensions,
        extract_config=extract_config,
        exclude_reporter=make_exclude_reporter(Namespace(verbose=verbose)),
    )
    write_cached_code_state(
        cache_root,
        key,
        state=state,
        meta=key_meta(
            tree_object_id=tree_id,
            package_root_relpath_posix=package_root_posix,
            mode=mode,
            dimensions_sorted_tuple=dimensions_tuple,
            effective_exclude_key_value=exclude_key,
            python_xy=python_xy,
        ),
        stats=cache_stats,
        max_bytes=cache_max_bytes,
        log=log,
    )
    return state
