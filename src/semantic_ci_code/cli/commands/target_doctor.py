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
        files_touched = _resolve_files_touched(args)
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
    candidate = Path(raw or ".").resolve()
    if not candidate.exists():
        raise TargetDoctorUsageError(f"--package-root does not exist: {candidate}")
    if not candidate.is_dir():
        raise TargetDoctorUsageError(f"--package-root is not a directory: {candidate}")
    return candidate


def _resolve_files_touched(args: Namespace) -> tuple[Path, ...] | None:
    """Resolve the candidate diff file list for D4.

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

    return tuple(entry.path for entry in entries)
