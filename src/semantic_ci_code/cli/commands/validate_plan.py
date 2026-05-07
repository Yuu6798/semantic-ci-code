from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from semantic_ci_code.cli.command_support import (
    engine_error,
    internal_bug,
    usage_error,
    write_output,
)
from semantic_ci_code.cli.git_runtime import (
    GitError,
    GitNotFoundError,
    is_git_available,
    repo_root,
    resolve_baseline,
)
from semantic_ci_code.cli.output.json_formatter import dump_json, package_version
from semantic_ci_code.cli.target_loader import TargetUsageError, discover_target
from semantic_ci_code.cli.worktree import materialize_ref
from semantic_ci_code.compiler import CompileError
from semantic_ci_code.domain.state_schema import CodeState
from semantic_ci_code.framework.target_svp import TargetSVP, parse_target_svp_yaml
from semantic_ci_code.pipeline import ExtractorError, extract_python_code_state
from semantic_ci_code.repair_compiler import RepairCompiler, get_adapter
from semantic_ci_code.repair_compiler.adapters import register_builtin_adapters
from semantic_ci_code.repair_compiler.risk_summary import compute_risk_summary
from semantic_ci_code.repair_compiler.types import Adapter, CompiledPreGen

_VALIDATE_PLAN_SCHEMA_VERSION = "1"


class ValidatePlanUsageError(ValueError):
    pass


def run_validate_plan(args: Namespace) -> int:
    try:
        register_builtin_adapters()
        target_path = discover_target(args.target, cwd=Path.cwd())
        target = _load_target(target_path)
        baseline = _load_baseline_state(args)
        risk_summary = compute_risk_summary(target, baseline)
        adapter = _adapter(args.adapter)
        compiled = RepairCompiler(adapter).render_pre_gen(
            target,
            baseline,
            risk_summary=risk_summary,
        )
        output = (
            dump_json(_build_validate_plan_payload(compiled))
            if args.format == "json"
            else compiled.rendered
        )
        return write_output(output, args.output)
    except (TargetUsageError, ValidatePlanUsageError, OSError, CompileError) as exc:
        return usage_error(exc)
    except ExtractorError as exc:
        return engine_error(exc, args, prefix="extractor failed", show_traceback=True)
    except GitNotFoundError as exc:
        return usage_error(exc)
    except GitError as exc:
        return usage_error(exc)
    except Exception as exc:
        return internal_bug(exc, args)


def _load_target(path: Path) -> TargetSVP:
    try:
        return parse_target_svp_yaml(path)
    except (ValueError, ValidationError, yaml.YAMLError) as exc:
        raise ValidatePlanUsageError(f"invalid target: {exc}") from exc


def _load_baseline_state(args: Namespace) -> CodeState:
    package_root = _package_root_relative(args.package_root)
    if args.baseline_rev is not None and args.baseline_dir is not None:
        raise ValidatePlanUsageError("pass either --baseline-rev or --baseline-dir, not both")

    if args.baseline_dir is not None:
        baseline_dir = _resolve_dir(args.baseline_dir, "baseline")
        return extract_python_code_state(_resolve_package_root(baseline_dir, package_root))

    if args.baseline_rev is not None:
        if not is_git_available():
            raise GitNotFoundError("git is required for --baseline-rev")
        root = repo_root(Path.cwd())
        return _extract_ref_state(root, args.baseline_rev, package_root)

    if not is_git_available():
        return CodeState()

    try:
        root = repo_root(Path.cwd())
        baseline_ref = resolve_baseline(None, repo_root=root, no_fetch=args.no_fetch)
    except GitError:
        return CodeState()
    return _extract_ref_state(root, baseline_ref, package_root)


def _extract_ref_state(root: Path, ref: str, package_root: Path) -> CodeState:
    with materialize_ref(root, ref, prefix="semantic-ci-baseline-") as baseline_dir:
        return extract_python_code_state(_resolve_package_root(baseline_dir, package_root))


def _package_root_relative(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute() or path.drive:
        raise ValidatePlanUsageError(f"package_root must be relative: {path}")
    parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValidatePlanUsageError(f"package_root must stay within baseline: {path}")
            parts.pop()
            continue
        parts.append(part)
    return Path(*parts) if parts else Path(".")


def _resolve_package_root(root: Path, package_root: Path) -> Path:
    root = root.resolve()
    path = (root / package_root).resolve()
    if not path.is_relative_to(root):
        raise ValidatePlanUsageError(f"package_root escapes baseline: {path}")
    if not path.exists():
        raise ValidatePlanUsageError(f"baseline package_root does not exist: {path}")
    if not path.is_dir():
        raise ValidatePlanUsageError(f"baseline package_root is not a directory: {path}")
    return path


def _resolve_dir(raw_path: str, label: str) -> Path:
    path = Path(raw_path).resolve()
    if not path.exists():
        raise ValidatePlanUsageError(f"{label} directory does not exist: {path}")
    if not path.is_dir():
        raise ValidatePlanUsageError(f"{label} path is not a directory: {path}")
    return path


def _adapter(name: str) -> Adapter:
    try:
        return get_adapter(name)
    except KeyError as exc:
        raise ValidatePlanUsageError(f"unknown adapter: {name}") from exc


def _build_validate_plan_payload(compiled: CompiledPreGen) -> dict[str, Any]:
    return {
        "schema_version": _VALIDATE_PLAN_SCHEMA_VERSION,
        "subcommand": "validate-plan",
        "adapter_name": compiled.adapter_name,
        "rendered": compiled.rendered,
        "metadata": compiled.metadata,
        "risk_summary": compiled.risk_summary,
        "engine": {
            "extractor_pyver": f"{sys.version_info.major}.{sys.version_info.minor}",
            "package_version": package_version(),
        },
    }
