from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from semantic_ci_code.cli.command_support import (
    _engine_error,
    _internal_bug,
    _stderr,
    _usage_error,
    _write_output,
)
from semantic_ci_code.cli.output import dump_json
from semantic_ci_code.cli.output.json_formatter import build_payload
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
        if args.format in {"sarif", "gh-actions"}:
            raise ValueError(f"{args.format} format is not supported for observe")
        root = _resolve_package_root(Path(args.package_root))
        if args.verbose:
            _stderr(f"observing package_root={root}")
        state = _extract_state(args, root=root)
        payload = build_payload("observe", state=state)
        output = dump_json(payload)
        if args.format == "human":
            _stderr(_HUMAN_FALLBACK_WARNING)
        return _write_output(output, args.output)
    except ValueError as exc:
        return _usage_error(exc)
    except OSError as exc:
        return _usage_error(exc)
    except ExtractorError as exc:
        return _engine_error(exc, args, prefix="extractor failed")
    except Exception as exc:
        return _internal_bug(exc, args)


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
