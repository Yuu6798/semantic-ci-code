"""Semgrep adapter for SSP SAST sensor output."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, cast

from semantic_ci_code.ssp.adapters.qualified_name import qualified_name_for_line
from semantic_ci_code.ssp.models import (
    Normalization,
    SASTFinding,
    SensorOutput,
    SensorSpec,
    Severity,
    SourceSpan,
)
from semantic_ci_code.ssp.python_profile import normalization_method, normalize_text

_SEMGREP_COMMAND = "semgrep"
_SEMGREP_NORMAL_EXIT_CODES = frozenset({0, 1})
_SEVERITY_MAP: dict[str, Severity] = {
    "ERROR": "critical",
    "WARNING": "medium",
    "INFO": "info",
}


@dataclass(frozen=True)
class SemgrepScanResult:
    """Semgrep scan output plus the sensor spec used by SSP envelopes."""

    output: SensorOutput
    sensor_spec: SensorSpec


class SemgrepAdapter:
    """Run Semgrep and convert JSON results into SSP SAST findings."""

    sensor_id = "semgrep"

    def scan(self, target_dir: Path, *, ruleset: Path, repo_root: Path) -> SemgrepScanResult:
        """Invoke Semgrep and return deterministic SSP sensor output."""

        resolved_repo_root = repo_root.resolve()
        resolved_target_dir = _resolve_against(target_dir, base=resolved_repo_root)
        resolved_ruleset = _resolve_against(ruleset, base=resolved_repo_root)
        ruleset_hash = _ruleset_hash(resolved_ruleset)
        command = [
            _SEMGREP_COMMAND,
            "--json",
            "--metrics=off",
            "--disable-version-check",
            "--no-rewrite-rule-ids",
            "--config",
            str(ruleset),
            str(target_dir),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=resolved_repo_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return self._error_result(
                "semgrep executable not found",
                ruleset_hash=ruleset_hash,
                error=exc,
            )

        if completed.returncode not in _SEMGREP_NORMAL_EXIT_CODES:
            return self._error_result(
                f"semgrep exited with code {completed.returncode}: {completed.stderr.strip()}",
                ruleset_hash=ruleset_hash,
            )

        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            return self._error_result(
                f"semgrep returned invalid JSON: {exc}",
                ruleset_hash=ruleset_hash,
            )

        return self.from_json(
            payload,
            target_dir=resolved_target_dir,
            ruleset=resolved_ruleset,
            repo_root=resolved_repo_root,
            ruleset_hash=ruleset_hash,
        )

    def from_json(
        self,
        payload: Mapping[str, Any],
        *,
        target_dir: Path,
        ruleset: Path,
        repo_root: Path,
        ruleset_hash: str | None = None,
    ) -> SemgrepScanResult:
        """Convert a Semgrep JSON payload into SSP sensor output."""

        resolved_repo_root = repo_root.resolve()
        resolved_target_dir = _resolve_against(target_dir, base=resolved_repo_root)
        resolved_ruleset = _resolve_against(ruleset, base=resolved_repo_root)
        version = _semgrep_version(payload)
        resolved_ruleset_hash = (
            ruleset_hash if ruleset_hash is not None else _ruleset_hash(resolved_ruleset)
        )
        semgrep_errors = _reported_errors(payload)
        if semgrep_errors:
            return self._error_result(
                "semgrep reported errors: " + "; ".join(semgrep_errors),
                ruleset_hash=resolved_ruleset_hash,
            )
        scanned_path_error = _scanned_path_coverage_error(
            payload,
            target_dir=resolved_target_dir,
            repo_root=resolved_repo_root,
        )
        if scanned_path_error is not None:
            return self._error_result(
                scanned_path_error,
                ruleset_hash=resolved_ruleset_hash,
            )
        findings = tuple(
            sorted(
                (
                    self._finding_from_result(
                        result,
                        target_dir=resolved_target_dir,
                        repo_root=resolved_repo_root,
                    )
                    for result in _result_items(payload)
                ),
                key=_finding_sort_key,
            )
        )
        output = SensorOutput(
            sensor_id=self.sensor_id,
            sensor_version=version,
            status="complete",
            findings=findings,
        )
        sensor_spec = SensorSpec(
            id=self.sensor_id,
            version=version,
            ruleset_hash=resolved_ruleset_hash,
        )
        return SemgrepScanResult(output=output, sensor_spec=sensor_spec)

    def _finding_from_result(
        self,
        result: Mapping[str, Any],
        *,
        target_dir: Path,
        repo_root: Path,
    ) -> SASTFinding:
        path_text = str(result.get("path", ""))
        source_path, module_path = _source_paths(
            path_text,
            target_dir=target_dir,
            repo_root=repo_root,
        )
        start = _location(result.get("start"))
        end = _location(result.get("end"))
        source_span = SourceSpan(
            start_line=start[0],
            start_col=start[1],
            end_line=end[0],
            end_col=end[1],
        )
        extra = result.get("extra")
        if not isinstance(extra, Mapping):
            extra = {}
        matched_source = _matched_source(extra, source_path=source_path, source_span=source_span)
        severity = _SEVERITY_MAP.get(str(extra.get("severity", "INFO")).upper(), "info")

        return SASTFinding(
            rule_id=str(result.get("check_id", "")),
            module_path=module_path,
            qualified_name=qualified_name_for_line(
                source_path,
                repo_root=repo_root,
                line=start[0],
            ),
            normalized_text=normalize_text(matched_source),
            ordinal=None,
            fingerprint=None,
            severity=severity,
            message=str(extra.get("message", "")),
            source_span=source_span,
            normalization=cast(Normalization, normalization_method(matched_source)),
        )

    def _error_result(
        self,
        message: str,
        *,
        ruleset_hash: str | None,
        error: BaseException | None = None,
    ) -> SemgrepScanResult:
        detail = f"{message}: {error}" if error is not None else message
        output = SensorOutput(
            sensor_id=self.sensor_id,
            sensor_version="",
            status="error",
            findings=(),
            error_message=detail,
        )
        sensor_spec = SensorSpec(
            id=self.sensor_id,
            version="",
            ruleset_hash=ruleset_hash,
        )
        return SemgrepScanResult(output=output, sensor_spec=sensor_spec)


def _ruleset_hash(ruleset: Path) -> str | None:
    try:
        data = ruleset.read_bytes()
    except OSError:
        return None
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _resolve_against(path: Path, *, base: Path) -> Path:
    return path if path.is_absolute() else base / path


def _result_items(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    results = payload.get("results", ())
    if not isinstance(results, Sequence) or isinstance(results, (str, bytes)):
        return ()
    return tuple(item for item in results if isinstance(item, Mapping))


def _reported_errors(payload: Mapping[str, Any]) -> tuple[str, ...]:
    errors = payload.get("errors", ())
    if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes)):
        return ()
    return tuple(_error_message(error) for error in errors if error)


def _error_message(error: object) -> str:
    if isinstance(error, Mapping):
        message = error.get("message") or error.get("type") or error
        return str(message)
    return str(error)


def _semgrep_version(payload: Mapping[str, Any]) -> str:
    version = payload.get("version") or payload.get("semgrep_version")
    return str(version) if version is not None else ""


def _source_paths(path_text: str, *, target_dir: Path, repo_root: Path) -> tuple[Path, str]:
    normalized = path_text.replace("\\", "/")
    raw_path = Path(normalized)
    if raw_path.is_absolute():
        source_path = raw_path
        try:
            module_path = raw_path.resolve().relative_to(repo_root.resolve()).as_posix()
        except (OSError, ValueError):
            module_path = PurePosixPath(normalized).as_posix()
    else:
        relative = PurePosixPath(normalized)
        normalized_path = relative.as_posix()
        target_prefix = _repo_relative_path(target_dir, repo_root=repo_root)
        if target_prefix and (
            normalized_path == target_prefix or normalized_path.startswith(target_prefix + "/")
        ):
            source_path = repo_root.joinpath(*relative.parts)
            module_path = normalized_path
        elif target_dir.is_file():
            source_path = target_dir
            module_path = target_prefix or normalized_path
        elif target_dir.resolve() != repo_root.resolve():
            source_path = target_dir.joinpath(*relative.parts)
            module_path = _repo_relative_path(source_path, repo_root=repo_root) or normalized_path
        else:
            source_path = repo_root.joinpath(*relative.parts)
            module_path = normalized_path
    return source_path, module_path


def _matched_source(
    extra: Mapping[str, Any],
    *,
    source_path: Path,
    source_span: SourceSpan,
) -> str:
    lines = extra.get("lines")
    if isinstance(lines, str) and lines:
        return lines
    return _source_text_for_span(source_path, source_span)


def _source_text_for_span(source_path: Path, source_span: SourceSpan) -> str:
    try:
        source_lines = source_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return ""
    start_line = source_span.start_line - 1
    end_line = source_span.end_line - 1
    if start_line < 0 or start_line >= len(source_lines):
        return ""
    selected = source_lines[start_line : min(end_line + 1, len(source_lines))]
    if not selected:
        return ""
    start_col = _span_col_index(source_span.start_col)
    end_col = _span_col_index(source_span.end_col)
    if len(selected) == 1:
        return selected[0][start_col:end_col]
    selected[0] = selected[0][start_col:]
    selected[-1] = selected[-1][:end_col]
    return "\n".join(selected)


def _span_col_index(column: int) -> int:
    return max(column - 1, 0)


def _repo_relative_path(path: Path, *, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _scanned_path_coverage_error(
    payload: Mapping[str, Any],
    *,
    target_dir: Path,
    repo_root: Path,
) -> str | None:
    expected = _expected_python_paths(target_dir, repo_root=repo_root)
    if not expected:
        return None
    scanned = _reported_scanned_paths(payload)
    if scanned is None:
        return "semgrep did not report scanned paths"
    reported = {
        _source_paths(path_text, target_dir=target_dir, repo_root=repo_root)[1]
        for path_text in scanned
    }
    missing = tuple(sorted(expected - reported))
    if missing:
        return "semgrep did not scan expected target files: " + ", ".join(missing)
    return None


def _reported_scanned_paths(payload: Mapping[str, Any]) -> tuple[str, ...] | None:
    paths = payload.get("paths")
    if not isinstance(paths, Mapping):
        return None
    scanned = paths.get("scanned")
    if not isinstance(scanned, Sequence) or isinstance(scanned, (str, bytes)):
        return None
    return tuple(str(path) for path in scanned)


def _expected_python_paths(target_dir: Path, *, repo_root: Path) -> set[str]:
    if target_dir.is_file():
        if target_dir.suffix != ".py":
            return set()
        relative = _repo_relative_path(target_dir, repo_root=repo_root)
        return {relative} if relative else set()
    if not target_dir.exists():
        return set()
    return {
        relative
        for relative in (
            _repo_relative_path(path, repo_root=repo_root)
            for path in sorted(target_dir.rglob("*.py"))
            if path.is_file()
        )
        if relative
    }


def _location(value: object) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        return (1, 0)
    line = _positive_int(value.get("line"), default=1)
    col = _non_negative_int(value.get("col"), default=0)
    return (line, col)


def _positive_int(value: object, *, default: int) -> int:
    if isinstance(value, int) and value >= 1:
        return value
    return default


def _non_negative_int(value: object, *, default: int) -> int:
    if isinstance(value, int) and value >= 0:
        return value
    return default


def _finding_sort_key(finding: SASTFinding) -> tuple[str, tuple[int, int, int, int], str, str]:
    span = finding.source_span.sort_key() if finding.source_span is not None else (0, 0, 0, 0)
    return (finding.module_path, span, finding.rule_id, finding.message)
