from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from semantic_ci_code.authoring.catalog import CatalogUsageError, build_catalog
from semantic_ci_code.cli.command_support import engine_error, internal_bug, usage_error
from semantic_ci_code.cli.output.catalog_human import format_catalog_human
from semantic_ci_code.cli.output.catalog_json import format_catalog_json
from semantic_ci_code.domain.state_schema import ChangeKind


def run_target_catalog(args: Namespace) -> int:
    try:
        kind_filter = ChangeKind(args.kind) if args.kind is not None else None
        catalog = build_catalog(
            kind_filter=kind_filter,
            target_path_filter=args.target_path,
        )
        rendered = (
            format_catalog_json(catalog) if args.format == "json" else format_catalog_human(catalog)
        )
        return _write_output(rendered, args.output)
    except CatalogUsageError as exc:
        return usage_error(exc)
    except OSError as exc:
        return engine_error(exc, args)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        return internal_bug(exc, args)


def _write_output(rendered: str, output: str | None) -> int:
    if output is None:
        print(rendered, end="")
        return 0
    Path(output).write_text(rendered, encoding="utf-8")
    return 0
