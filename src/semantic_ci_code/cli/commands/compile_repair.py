from __future__ import annotations

import json
import sys
from argparse import Namespace
from dataclasses import replace
from pathlib import Path
from typing import Any

from semantic_ci_code.cli.command_support import internal_bug, usage_error, write_output
from semantic_ci_code.cli.output.json_formatter import dump_json, package_version
from semantic_ci_code.repair import RepairPlan, deserialize_repair_plan
from semantic_ci_code.repair_compiler import RepairCompiler, get_adapter
from semantic_ci_code.repair_compiler.adapters import register_builtin_adapters
from semantic_ci_code.repair_compiler.types import Adapter, CompiledRepair

_COMPILE_REPAIR_SCHEMA_VERSION = "1"


class RepairCompileUsageError(ValueError):
    pass


def run_compile_repair(args: Namespace) -> int:
    try:
        register_builtin_adapters()
        payload = _read_input(args.input)
        plan, input_kind = _extract_repair_plan(payload)
        adapter = _adapter(args.adapter)
        compiled = RepairCompiler(adapter).render_repair(plan, target=None)
        compiled = replace(
            compiled,
            metadata={**compiled.metadata, "input_kind": input_kind},
        )
        output = (
            dump_json(_build_compile_repair_payload(compiled))
            if args.format == "json"
            else compiled.rendered
        )
        return write_output(output, args.output)
    except (RepairCompileUsageError, OSError) as exc:
        return usage_error(exc)
    except Exception as exc:
        return internal_bug(exc, args)


def _read_input(path: str | None) -> dict[str, Any]:
    raw = sys.stdin.read() if path is None else _read_file(path)
    if not raw.strip():
        raise RepairCompileUsageError("input JSON is empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RepairCompileUsageError(f"invalid JSON input: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise RepairCompileUsageError("input must be a JSON object")
    return payload


def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise RepairCompileUsageError(str(exc)) from exc


def _extract_repair_plan(payload: dict[str, Any]) -> tuple[RepairPlan, str]:
    if "subcommand" in payload and "repair_plan" in payload:
        repair_plan = payload["repair_plan"]
        if repair_plan is None:
            raise RepairCompileUsageError(
                "verdict envelope has null repair_plan; pass verdicts have nothing to render"
            )
        if not isinstance(repair_plan, dict):
            raise RepairCompileUsageError("verdict envelope repair_plan must be a JSON object")
        return _deserialize_plan(repair_plan), "verdict_envelope"

    if "instructions" in payload and "subcommand" not in payload:
        return _deserialize_plan(payload), "raw_repair_plan"

    raise RepairCompileUsageError(
        "unrecognized input: expected verdict envelope (with subcommand + repair_plan) "
        "or raw RepairPlan (with instructions)"
    )


def _deserialize_plan(payload: dict[str, Any]) -> RepairPlan:
    try:
        return deserialize_repair_plan(payload)
    except ValueError as exc:
        raise RepairCompileUsageError(f"invalid repair_plan: {exc}") from exc


def _adapter(name: str) -> Adapter:
    try:
        return get_adapter(name)
    except KeyError as exc:
        # Argparse choices catch this in normal CLI use; this keeps the helper safe for tests.
        raise RepairCompileUsageError(f"unknown adapter: {name}") from exc


def _build_compile_repair_payload(compiled: CompiledRepair) -> dict[str, Any]:
    return {
        "schema_version": _COMPILE_REPAIR_SCHEMA_VERSION,
        "subcommand": "compile-repair",
        "adapter_name": compiled.adapter_name,
        "rendered": compiled.rendered,
        "metadata": compiled.metadata,
        "engine": {
            "extractor_pyver": f"{sys.version_info.major}.{sys.version_info.minor}",
            "package_version": package_version(),
        },
    }
