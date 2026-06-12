"""`semantic-ci target-doctor` — Advisor surface command.

Renders authoring hazards (D1 / D3 / D4 / D6 / I1 / P1 / P2 / S1) detected
on a `target.yaml`. Advisor surface (`docs/code_semantic_ci_design.md
§23.3.1`): the verdict is not computed and advisory presence does not change
the exit code. Usage / configuration errors return 2; engine / git failures
return 3; unhandled exceptions return 4 (`docs/exit_codes.md`).
"""

from __future__ import annotations

import json
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path

from semantic_ci_code.authoring import detect_advisories
from semantic_ci_code.authoring.nested_defs import NestedDefGrowth, count_nested_defs
from semantic_ci_code.cli.command_support import (
    engine_error,
    internal_bug,
    usage_error,
    write_output,
)
from semantic_ci_code.cli.doctor_support import PackageRootError, resolve_package_root
from semantic_ci_code.cli.git_diff import numstat_range
from semantic_ci_code.cli.git_runtime import (
    GitError,
    GitNotFoundError,
    blob_text,
    is_git_available,
    repo_root,
    resolve_baseline,
    resolve_candidate,
)
from semantic_ci_code.cli.output.doctor_human import format_doctor_human
from semantic_ci_code.cli.output.doctor_json import build_doctor_payload
from semantic_ci_code.cli.target_loader import (
    TargetUsageError,
    discover_target,
    load_compiled_target,
)
from semantic_ci_code.compiler import CompileError


def run_target_doctor(args: Namespace) -> int:
    try:
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)
        package_root = resolve_package_root(args.package_root)
        diff_context = _resolve_diff_context(args, package_root=package_root)
        advisories = detect_advisories(
            compiled,
            package_root=package_root,
            files_touched=diff_context.files_touched if diff_context else None,
            nested_def_growth=diff_context.nested_def_growth if diff_context else None,
        )
        payload = build_doctor_payload(advisories)
        if args.format == "json":
            output = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        else:
            output = format_doctor_human(advisories)
        return write_output(output, args.output)
    except TargetUsageError as exc:
        return usage_error(exc)
    except PackageRootError as exc:
        return usage_error(exc)
    except CompileError as exc:
        return engine_error(exc, args, prefix="CompileError")
    except GitNotFoundError as exc:
        return engine_error(exc, args, prefix="git unavailable")
    except GitError as exc:
        return engine_error(exc, args, prefix="git error")
    except Exception as exc:
        return internal_bug(exc, args)


@dataclass(frozen=True)
class _DiffContext:
    """Candidate-diff context shared by the diff-aware detectors.

    `files_touched` feeds D4 (vacuous PASS on non-Python diffs);
    `nested_def_growth` feeds D6 (complexity displaced into nested
    functions). Both are derived from the same numstat pass so the two
    detectors always describe the same baseline ↔ candidate range.
    """

    files_touched: tuple[Path, ...]
    nested_def_growth: tuple[NestedDefGrowth, ...]


def _resolve_diff_context(
    args: Namespace,
    *,
    package_root: Path,
) -> _DiffContext | None:
    """Resolve the candidate diff for D4 / D6, filtered to the
    `--package-root` slice.

    `semantic-ci check` extracts only inside `--package-root`, so D4's
    "vacuous PASS" hazard applies whenever the in-scope slice has no
    Python diff — even if other parts of the repo do. We filter the
    repo-wide numstat to paths under `package_root` before
    classification. D6 reads the in-scope Python entries' content at
    both revs to compute the nested-def growth signal.

    When the user passes `--baseline-rev` or `--candidate-rev`, git
    failures surface as exit 3. When neither is passed and git is
    unavailable / no repo / no baseline, both detectors are silently
    skipped (returns `None`).
    """
    explicit = args.baseline_rev is not None or args.candidate_rev is not None

    if not is_git_available():
        if explicit:
            raise GitNotFoundError("git is required for --baseline-rev / --candidate-rev")
        return None

    try:
        root = repo_root(Path.cwd())
    except GitError:
        if explicit:
            raise
        return None

    try:
        baseline_ref = resolve_baseline(
            args.baseline_rev,
            repo_root=root,
            no_fetch=True,
        )
    except GitError:
        if explicit:
            raise
        return None

    candidate_ref = resolve_candidate(args.candidate_rev)

    try:
        entries = numstat_range(root, baseline_ref, candidate_ref)
    except GitError:
        if explicit:
            raise
        return None

    # Filter to the in-scope slice: numstat paths are repo-relative,
    # so we resolve under `root` and check whether they land inside
    # `package_root`. Diffs outside package_root are extracted as
    # nothing by `semantic-ci check`, so they cannot prevent a
    # vacuous PASS on the in-scope slice.
    package_root_resolved = package_root.resolve()

    def in_scope(path: Path) -> bool:
        full = (root / path).resolve()
        try:
            return full.is_relative_to(package_root_resolved)
        except (OSError, ValueError):
            return False

    # Include both sides of rename entries so D4 can see Python touches
    # on either side. A `foo.py -> bar.txt` rename has new path
    # `bar.txt` and `old_path=foo.py`; dropping `old_path` would let D4
    # misclassify the diff as non-Python and emit a vacuous-pass
    # warning even though the validator would extract a Python delta
    # (api_surface_delta.removed_public on the old name).
    files_touched: list[Path] = []
    growth: list[NestedDefGrowth] = []
    for entry in entries:
        candidate_path = entry.path
        baseline_path = entry.old_path if entry.old_path is not None else entry.path
        if in_scope(candidate_path):
            files_touched.append(candidate_path)
        if entry.old_path is not None and in_scope(entry.old_path):
            files_touched.append(entry.old_path)

        # D6 signal: nested-def counts on both sides of every in-scope
        # Python entry. A file absent at one rev (added / deleted)
        # contributes 0 on that side, and so does an out-of-scope side:
        # `semantic-ci check --package-root` never observed it, so a
        # rename across the package-root boundary must count as 0 → N
        # (newly in-scope nested defs) rather than N → N (Codex review
        # P2 — matching counts would mask the displacement). A side that
        # fails to parse skips the entry entirely so a syntax error
        # cannot fabricate or suppress a growth signal.
        if candidate_path.suffix.lower() != ".py" and baseline_path.suffix.lower() != ".py":
            continue
        if not (in_scope(candidate_path) or in_scope(baseline_path)):
            continue
        baseline_count = (
            _nested_defs_at(root, baseline_ref, baseline_path) if in_scope(baseline_path) else 0
        )
        candidate_count = (
            _nested_defs_at(root, candidate_ref, candidate_path) if in_scope(candidate_path) else 0
        )
        if baseline_count is None or candidate_count is None:
            continue
        growth.append(
            NestedDefGrowth(
                path=candidate_path.as_posix(),
                baseline_count=baseline_count,
                candidate_count=candidate_count,
            )
        )
    return _DiffContext(files_touched=tuple(files_touched), nested_def_growth=tuple(growth))


def _nested_defs_at(root: Path, ref: str, path: Path) -> int | None:
    """Nested-def count for `path` at `ref`; 0 when absent, None on
    syntax error (caller skips the entry)."""
    if path.suffix.lower() != ".py":
        return 0
    source = blob_text(ref, path.as_posix(), cwd=root)
    if source is None:
        return 0
    return count_nested_defs(source)
