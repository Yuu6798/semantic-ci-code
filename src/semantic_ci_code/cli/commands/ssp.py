"""`semantic-ci ssp` command group."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from pydantic import ValidationError

from semantic_ci_code.cli.command_support import (
    internal_bug,
    usage_error,
    write_output,
)
from semantic_ci_code.cli.exit_codes import ENGINE_ERROR, FAIL, SUCCESS
from semantic_ci_code.cli.output.json_formatter import dump_json
from semantic_ci_code.ssp.adapters.pip_audit import PipAuditAdapter
from semantic_ci_code.ssp.adapters.semgrep import SemgrepAdapter
from semantic_ci_code.ssp.delta import compute_delta
from semantic_ci_code.ssp.human_format import format_human
from semantic_ci_code.ssp.models import (
    ScanEndpoint,
    SensorOutput,
    SensorSpec,
    SSPEngine,
    SSPEnvelope,
)
from semantic_ci_code.ssp.sarif import ssp_to_sarif


def run_ssp(args: Namespace) -> int:
    try:
        if args.ssp_subcommand == "scan":
            envelope = _scan_envelope(args)
        elif args.ssp_subcommand == "from-json":
            envelope = _from_json_envelope(args)
        else:
            return usage_error(ValueError("missing SSP subcommand"))
        rendered = _render_envelope(envelope, args.format)
        write_code = write_output(rendered, args.output)
        if write_code != SUCCESS:
            return write_code
        return _exit_code(envelope)
    except (OSError, ValueError, ValidationError) as exc:
        return usage_error(exc)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        return internal_bug(exc, args)


def _scan_envelope(args: Namespace) -> SSPEnvelope:
    baseline_dir = _existing_dir(Path(args.baseline_dir), label="--baseline-dir")
    candidate_dir = _existing_dir(Path(args.candidate_dir), label="--candidate-dir")
    sensor = args.sensor
    if sensor == "semgrep":
        if args.config is None:
            raise ValueError("--config is required when --sensor=semgrep")
        ruleset = _existing_file(Path(args.config), label="--config")
        package_root = Path(args.package_root)
        baseline_result = SemgrepAdapter().scan(
            _resolve_package_root(baseline_dir, package_root),
            ruleset=ruleset,
            repo_root=baseline_dir,
        )
        candidate_result = SemgrepAdapter().scan(
            _resolve_package_root(candidate_dir, package_root),
            ruleset=ruleset,
            repo_root=candidate_dir,
        )
    elif sensor == "pip-audit":
        baseline_result = PipAuditAdapter().scan(
            requirements=_requirements_file(baseline_dir),
            repo_root=baseline_dir,
        )
        candidate_result = PipAuditAdapter().scan(
            requirements=_requirements_file(candidate_dir),
            repo_root=candidate_dir,
        )
    else:
        raise ValueError(f"unknown SSP sensor: {sensor}")

    return _build_envelope(
        baseline_result.output,
        candidate_result.output,
        sensor_spec=candidate_result.sensor_spec,
        scan_mode="real",
        baseline=ScanEndpoint(kind="git-tree", ref=str(baseline_dir)),
        candidate=ScanEndpoint(kind="git-tree", ref=str(candidate_dir)),
    )


def _from_json_envelope(args: Namespace) -> SSPEnvelope:
    baseline_path = _existing_file(Path(args.baseline), label="--baseline")
    candidate_path = _existing_file(Path(args.candidate), label="--candidate")
    baseline = _load_sensor_output(baseline_path)
    candidate = _load_sensor_output(candidate_path)
    return _build_envelope(
        baseline,
        candidate,
        sensor_spec=SensorSpec(id=candidate.sensor_id, version=candidate.sensor_version),
        scan_mode="virtual",
        baseline=ScanEndpoint(kind="prebuilt", ref=str(baseline_path)),
        candidate=ScanEndpoint(kind="prebuilt", ref=str(candidate_path)),
    )


def _build_envelope(
    baseline_output: SensorOutput,
    candidate_output: SensorOutput,
    *,
    sensor_spec: SensorSpec,
    scan_mode: str,
    baseline: ScanEndpoint,
    candidate: ScanEndpoint,
) -> SSPEnvelope:
    delta = compute_delta(baseline_output, candidate_output)
    return SSPEnvelope(
        engine=SSPEngine(
            scan_mode=scan_mode,
            baseline=baseline,
            candidate=candidate,
            sensors=(sensor_spec,),
        ),
        deltas_by_sensor={delta.sensor_id: delta},
        aggregate_verdict=delta.status,
    )


def _render_envelope(envelope: SSPEnvelope, output_format: str) -> str:
    if output_format == "json":
        return dump_json(envelope.model_dump(mode="json"))
    if output_format == "human":
        return format_human(envelope)
    if output_format == "sarif":
        return ssp_to_sarif(envelope)
    raise ValueError(f"unsupported SSP output format: {output_format}")


def _exit_code(envelope: SSPEnvelope) -> int:
    if envelope.aggregate_verdict == "fail":
        return FAIL
    if envelope.aggregate_verdict == "unknown":
        return ENGINE_ERROR
    return SUCCESS


def _load_sensor_output(path: Path) -> SensorOutput:
    return SensorOutput.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _existing_dir(path: Path, *, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {path}")
    if not resolved.is_dir():
        raise ValueError(f"{label} is not a directory: {path}")
    return resolved


def _existing_file(path: Path, *, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise ValueError(f"{label} does not exist: {path}")
    if not resolved.is_file():
        raise ValueError(f"{label} is not a file: {path}")
    return resolved


def _resolve_package_root(root: Path, package_root: Path) -> Path:
    candidate = package_root if package_root.is_absolute() else root / package_root
    return _existing_dir(candidate, label="--package-root")


def _requirements_file(root: Path) -> Path | None:
    path = root / "requirements.txt"
    return path if path.exists() else None
