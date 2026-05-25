from __future__ import annotations

import math
from argparse import Namespace
from contextlib import AbstractContextManager, ExitStack, nullcontext
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
from semantic_ci_code.cli.git_diff import numstat_cached, numstat_range
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
from semantic_ci_code.cli.staged_index import export_staged_index
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
from semantic_ci_code.pipeline import (
    CodeStateExtraction,
    ExtractorError,
    extract_python_code_state_result,
)
from semantic_ci_code.repair import emit_repair_plan

_VOLATILE_SOURCES = frozenset(("working-tree", "staged-index"))


def run_check(args: Namespace) -> int:
    try:
        baseline_source = args.baseline_source
        candidate_source = args.candidate_source
        baseline_volatile = _is_volatile_source(baseline_source)
        candidate_volatile = _is_volatile_source(candidate_source)
        baseline_rev_explicit = args.baseline_rev is not None
        candidate_rev_explicit = args.candidate_rev is not None
        _reject_incompatible_rev(
            side="baseline",
            source=baseline_source,
            explicit_rev=baseline_rev_explicit,
        )
        _reject_incompatible_rev(
            side="candidate",
            source=candidate_source,
            explicit_rev=candidate_rev_explicit,
        )

        if not is_git_available():
            raise GitNotFoundError("git is required for 'check'; install git or use 'compare'")

        root = repo_root(Path.cwd())
        baseline_ref = _resolve_baseline_ref(args, repo_root=root)
        candidate_ref = resolve_candidate(args.candidate_rev)
        baseline_rev = None if baseline_volatile else _resolve_commit_sha(root, baseline_ref)
        candidate_rev = None if candidate_volatile else _resolve_commit_sha(root, candidate_ref)
        package_root = _package_root_relative(args.package_root)
        mode = resolve_execution_mode(args.mode)
        dimensions = dimensions_for_mode(mode)
        dimensions_tuple = dimensions_for_cache(dimensions)
        use_cache = not cache_disabled(no_cache_flag=args.no_cache)
        extractor_timeout = _extractor_timeout(args.extractor_timeout)
        if extractor_timeout is not None:
            use_cache = False
        cache_root = resolve_cache_root(args.cache_dir, repo_root=root, cwd=Path.cwd())
        cache_max_bytes = resolve_cache_max_bytes(args.cache_max_bytes) if use_cache else 0
        cache_stats = CacheStats(disabled=not use_cache)
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)

        if args.verbose:
            _stderr(
                f"resolved baseline={baseline_ref} ({baseline_source}) "
                f"candidate={candidate_ref} ({candidate_source})"
            )
        if candidate_source == "working-tree" and args.verbose and not is_dirty(root):
            _stderr(
                "note: candidate source = working tree (no uncommitted changes "
                "detected; equivalent to HEAD)."
            )
        if baseline_source == candidate_source and baseline_volatile:
            _stderr(
                "warning: baseline and candidate resolve to the same "
                f"{baseline_source} snapshot; verdict will report no drift by construction."
            )

        with ExitStack() as stack:
            baseline_dir = stack.enter_context(
                _source_context(
                    root,
                    source=baseline_source,
                    ref=baseline_ref,
                    prefix="semantic-ci-baseline-",
                )
            )
            candidate_dir = stack.enter_context(
                _source_context(
                    root,
                    source=candidate_source,
                    ref=candidate_ref,
                    prefix="semantic-ci-candidate-",
                )
            )
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
            baseline_extraction = _extract_code_state(
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
                use_cache=use_cache and not baseline_volatile,
                cache_stats=cache_stats,
                cache_max_bytes=cache_max_bytes,
                timeout_seconds=extractor_timeout,
                verbose=args.verbose,
            )
            if args.verbose:
                _stderr(f"extracting candidate package_root={candidate_root}")
            candidate_extraction = _extract_code_state(
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
                use_cache=use_cache and not candidate_volatile,
                cache_stats=cache_stats,
                cache_max_bytes=cache_max_bytes,
                timeout_seconds=extractor_timeout,
                verbose=args.verbose,
            )

        baseline = baseline_extraction.state
        candidate = candidate_extraction.state
        timed_out_dimensions = (
            baseline_extraction.timed_out_dimensions | candidate_extraction.timed_out_dimensions
        )
        if args.verbose and timed_out_dimensions:
            _stderr("extractor timed out dimensions: " + ", ".join(sorted(timed_out_dimensions)))

        delta = compute_code_state_delta(baseline, candidate)
        entries = _numstat_entries(
            root,
            baseline_source=baseline_source,
            baseline_ref=baseline_ref,
            candidate_source=candidate_source,
            candidate_ref=candidate_ref,
        )
        files_touched, loc_delta = summarize_numstat(entries)
        delta = overlay_delta(delta, files_touched=files_touched, loc_delta=loc_delta)
        verdict = evaluate_constraints(
            compiled,
            delta,
            baseline=baseline,
            candidate=candidate,
            extracted_dimensions=dimensions,
            baseline_timed_out_dimensions=baseline_extraction.timed_out_dimensions,
            candidate_timed_out_dimensions=candidate_extraction.timed_out_dimensions,
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
            baseline_source=baseline_source,
            baseline_rev=baseline_rev,
            candidate_source=candidate_source,
            candidate_rev=candidate_rev,
            timed_out_dimensions=timed_out_dimensions,
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


def _is_volatile_source(source: str) -> bool:
    return source in _VOLATILE_SOURCES


def _reject_incompatible_rev(*, side: str, source: str, explicit_rev: bool) -> None:
    if _is_volatile_source(source) and explicit_rev:
        raise ValueError(f"error: --{side}-source={source} is incompatible with --{side}-rev")


def _extractor_timeout(raw: float | None) -> float | None:
    if raw is None:
        return None
    if not math.isfinite(raw) or raw <= 0:
        raise ValueError("--extractor-timeout must be a finite value greater than 0 seconds")
    return raw


def _resolve_baseline_ref(args: Namespace, *, repo_root: Path) -> str:
    if args.baseline_rev is not None:
        return args.baseline_rev
    if args.baseline_source == "commit" and args.candidate_source == "staged-index":
        return "HEAD"
    if args.baseline_source == "commit":
        return resolve_baseline(
            None,
            repo_root=repo_root,
            no_fetch=args.no_fetch,
        )
    # Volatile baselines do not have a commit ref. Keep a stable placeholder
    # for helper signatures; callers must gate ref usage on source == "commit".
    return "HEAD"


def _source_context(
    repo_root: Path,
    *,
    source: str,
    ref: str,
    prefix: str,
) -> AbstractContextManager[Path]:
    if source == "commit":
        return materialize_ref(repo_root, ref, prefix=prefix)
    if source == "working-tree":
        return nullcontext(repo_root)
    if source == "staged-index":
        return export_staged_index(repo_root, prefix=prefix)
    raise ValueError(f"unknown source: {source}")


def _numstat_entries(
    repo_root: Path,
    *,
    baseline_source: str,
    baseline_ref: str,
    candidate_source: str,
    candidate_ref: str,
):
    if baseline_source != "commit":
        return ()
    if candidate_source == "commit":
        return numstat_range(repo_root, baseline_ref, candidate_ref)
    if candidate_source == "working-tree":
        return numstat_range(repo_root, baseline_ref)
    if candidate_source == "staged-index":
        return numstat_cached(repo_root, baseline_ref)
    raise ValueError(f"unknown candidate source: {candidate_source}")


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
    timeout_seconds: float | None,
    verbose: bool,
) -> CodeStateExtraction:
    if timeout_seconds is not None:
        use_cache = False

    if not use_cache:
        return extract_python_code_state_result(
            resolved_package_root,
            dimensions=dimensions,
            extract_config=extract_config,
            timeout_seconds=timeout_seconds,
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
        return CodeStateExtraction(state=cached, timed_out_dimensions=frozenset())

    extraction = extract_python_code_state_result(
        resolved_package_root,
        dimensions=dimensions,
        extract_config=extract_config,
        exclude_reporter=make_exclude_reporter(Namespace(verbose=verbose)),
    )
    write_cached_code_state(
        cache_root,
        key,
        state=extraction.state,
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
    return extraction
