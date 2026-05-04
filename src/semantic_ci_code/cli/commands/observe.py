from __future__ import annotations

import sys
import traceback
from argparse import Namespace
from pathlib import Path

from semantic_ci_code.cli.exit_codes import ENGINE_ERROR, INTERNAL_BUG, SUCCESS, USAGE_ERROR
from semantic_ci_code.cli.output.json_basic import build_observe_payload, dump_json
from semantic_ci_code.pipeline import (
    ExtractorError,
    extract_python_code_state,
    extract_python_code_state_from_paths,
)

_HUMAN_FALLBACK_WARNING = (
    "human format is not yet implemented; falling back to JSON. Will be added in CSCI-16."
)


def run_observe(args: Namespace) -> int:
    try:
        root = _resolve_package_root(Path(args.package_root))
        if args.verbose:
            _stderr(f"observing package_root={root}")
        state = _extract_state(args, root=root)
        payload = build_observe_payload(state)
        output = dump_json(payload)
        if args.format == "human":
            _stderr(_HUMAN_FALLBACK_WARNING)
        return _write_output(output, args.output)
    except ValueError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except OSError as exc:
        _stderr(_one_line(str(exc)))
        return USAGE_ERROR
    except ExtractorError as exc:
        _stderr(f"extractor failed: {_one_line(str(exc))}")
        return ENGINE_ERROR
    except Exception as exc:
        _stderr(f"internal error: {_one_line(str(exc))}; rerun with --verbose for traceback")
        if args.verbose:
            traceback.print_exc(file=sys.stderr)
        return INTERNAL_BUG


def _extract_state(args: Namespace, *, root: Path):
    if args.paths is None:
        return extract_python_code_state(root)
    paths = tuple(_path_from_cli(raw_path, package_root=root) for raw_path in args.paths)
    return extract_python_code_state_from_paths(paths, package_root=root)


def _resolve_package_root(path: Path) -> Path:
    root = path.resolve()
    if not root.exists():
        raise ValueError(f"package_root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"package_root is not a directory: {root}")
    return root


def _path_from_cli(raw_path: str, *, package_root: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return package_root / path


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


def _stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _one_line(message: str) -> str:
    return message.splitlines()[0] if message else ""
