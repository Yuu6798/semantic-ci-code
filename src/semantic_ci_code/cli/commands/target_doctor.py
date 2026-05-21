"""`semantic-ci target-doctor` — Advisor surface command.

Renders authoring hazards (D1 / D3 / D4 / P1 / P2 / S1) detected on a
`target.yaml`. Advisor surface (`docs/code_semantic_ci_design.md §23.3.1`):
the verdict is not computed and advisory presence does not change the exit
code. Usage / configuration errors return 2; engine / git failures return 3;
unhandled exceptions return 4 (`docs/exit_codes.md`).
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from semantic_ci_code.authoring import detect_advisories
from semantic_ci_code.cli.command_support import (
    engine_error,
    internal_bug,
    usage_error,
    write_output,
)
from semantic_ci_code.cli.git_diff import numstat_range
from semantic_ci_code.cli.git_runtime import (
    GitError,
    GitNotFoundError,
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


class TargetDoctorUsageError(ValueError):
    """target-doctor input rejected at the CLI boundary."""


def run_target_doctor(args: Namespace) -> int:
    try:
        target_path = discover_target(args.target, cwd=Path.cwd())
        compiled = load_compiled_target(target_path)
        package_root = _resolve_package_root(args.package_root)
        files_touched = _resolve_files_touched(args, package_root=package_root)
        advisories = detect_advisories(
            compiled,
            package_root=package_root,
            files_touched=files_touched,
        )
        payload = build_doctor_payload(advisories)
        if args.format == "json":
            output = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        else:
            output = format_doctor_human(advisories)
        return write_output(output, args.output)
    except TargetUsageError as exc:
        return usage_error(exc)
    except TargetDoctorUsageError as exc:
        return usage_error(exc)
    except CompileError as exc:
        return engine_error(exc, args, prefix="CompileError")
    except GitNotFoundError as exc:
        return engine_error(exc, args, prefix="git unavailable")
    except GitError as exc:
        return engine_error(exc, args, prefix="git error")
    except Exception as exc:
        return internal_bug(exc, args)


def _resolve_package_root(raw: str | None) -> Path:
    raw_path = Path(raw or ".")
    if raw_path.is_absolute() or raw_path.drive:
        raise TargetDoctorUsageError(
            f"--package-root must be relative for target-doctor: {raw_path}"
        )

    parts: list[str] = []
    for part in raw_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise TargetDoctorUsageError(
                    f"--package-root must stay within repo for target-doctor: {raw_path}"
                )
            parts.pop()
            continue
        parts.append(part)
    normalized = Path(*parts) if parts else Path(".")

    base = Path.cwd()
    if is_git_available():
        try:
            base = repo_root(Path.cwd())
        except GitError:
            base = Path.cwd()

    resolved_base = base.resolve()
    candidate = (resolved_base / normalized).resolve()
    if not candidate.is_relative_to(resolved_base):
        raise TargetDoctorUsageError(f"--package-root escapes repo root via symlink: {candidate}")
    if not candidate.exists():
        raise TargetDoctorUsageError(f"--package-root does not exist: {candidate}")
    if not candidate.is_dir():
        raise TargetDoctorUsageError(f"--package-root is not a directory: {candidate}")
    return candidate


def _resolve_files_touched(
    args: Namespace,
    *,
    package_root: Path,
) -> tuple[Path, ...] | None:
    """Resolve the candidate diff file list for D4, filtered to the
    `--package-root` slice.

    `semantic-ci check` extracts only inside `--package-root`, so D4's
    "vacuous PASS" hazard applies whenever the in-scope slice has no
    Python diff — even if other parts of the repo do. We filter the
    repo-wide numstat to paths under `package_root` before
    classification.

    When the user passes `--baseline-rev` or `--candidate-rev`, git
    failures surface as exit 3. When neither is passed and git is
    unavailable / no repo / no baseline, D4 is silently skipped (returns
    `None`).
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

    # Include both sides of rename entries so D4 can see Python touches
    # on either side. A `foo.py -> bar.txt` rename has new path
    # `bar.txt` and `old_path=foo.py`; dropping `old_path` would let D4
    # misclassify the diff as non-Python and emit a vacuous-pass
    # warning even though the validator would extract a Python delta
    # (api_surface_delta.removed_public on the old name).
    paths: list[Path] = []
    for entry in entries:
        paths.append(entry.path)
        if entry.old_path is not None:
            paths.append(entry.old_path)

    # Filter to the in-scope slice: numstat paths are repo-relative,
    # so we resolve under `root` and check whether they land inside
    # `package_root`. Diffs outside package_root are extracted as
    # nothing by `semantic-ci check`, so they cannot prevent a
    # vacuous PASS on the in-scope slice.
    package_root_resolved = package_root.resolve()
    filtered: list[Path] = []
    for path in paths:
        full = (root / path).resolve()
        try:
            if full.is_relative_to(package_root_resolved):
                filtered.append(path)
        except (OSError, ValueError):
            continue
    return tuple(filtered)
